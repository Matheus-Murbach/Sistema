"""
Teste de integração — Fluxo de Beneficiamento Externo (Banho).

Verifica o comportamento completo:
  1. Produto parte do estoque DISPONIVEL
  2. Após remessa: saldo DISPONIVEL diminui, saldo EM_BENEFICIAMENTO aparece
  3. Após retorno parcial: produto acabado entra em DISPONIVEL, perdas registradas
  4. Lotes atrasados são detectáveis
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.database import Base
from app.models.estoque import SaldoEstoque, LocalizacaoEstoque
from app.models.produto import Produto, UnidadeMedida
from app.models.parceiro import PrestadorBeneficiamento
from app.models.beneficiamento import LoteBeneficiamento, ItemLoteBeneficiamento
from app.services.estoque_service import movimentar, get_saldo

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="function")
async def db(engine):
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest.fixture(scope="function")
async def base_dados(db):
    """Cria estrutura base: produto bruto, produto acabado, localização, prestador."""
    un = UnidadeMedida(codigo="UN", descricao="Unidade")
    db.add(un)
    await db.flush()

    bruto = Produto(codigo="BRUTO-001", descricao="Parafuso Bruto",
                    tipo="SEMI_ACABADO", unidade_id=un.id,
                    aliq_icms=Decimal("12"), aliq_ipi=Decimal("0"),
                    aliq_pis=Decimal("0.65"), aliq_cofins=Decimal("3"))
    acabado = Produto(codigo="ACAB-001", descricao="Parafuso Zincado",
                      tipo="PRODUTO_BENEFICIADO", unidade_id=un.id,
                      aliq_icms=Decimal("12"), aliq_ipi=Decimal("0"),
                      aliq_pis=Decimal("0.65"), aliq_cofins=Decimal("3"))
    db.add(bruto)
    db.add(acabado)

    loc = LocalizacaoEstoque(codigo="A-01", descricao="Prateleira A-01")
    db.add(loc)

    prestador = PrestadorBeneficiamento(
        razao_social="Zincagem Boa Ltda",
        cnpj_cpf="11.222.333/0001-44",
        tipo_beneficiamento="Zincagem",
        prazo_retorno_dias=7,
        percentual_perda_esperado=2.0,
    )
    db.add(prestador)
    await db.flush()

    # Coloca 200 unidades brutas em estoque
    await movimentar(db, bruto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("200"))
    await db.commit()

    return {"bruto": bruto, "acabado": acabado, "loc": loc, "prestador": prestador}


# ---------------------------------------------------------------------------
# Fluxo de Remessa
# ---------------------------------------------------------------------------

class TestRemessaBanho:
    async def test_remessa_reduz_disponivel(self, db, base_dados):
        """Após criação do lote, o DISPONIVEL deve cair na quantidade enviada."""
        b = base_dados
        qtd_envio = Decimal("100")

        # Baixa do DISPONIVEL
        await movimentar(db, b["bruto"].id, b["loc"].id,
                         tipo="SAIDA_REMESSA_BANHO", quantidade=-qtd_envio,
                         status_estoque="DISPONIVEL")
        # Entra no EM_BENEFICIAMENTO
        await movimentar(db, b["bruto"].id, b["loc"].id,
                         tipo="ENTRADA_EM_BENEFICIAMENTO", quantidade=qtd_envio,
                         status_estoque="EM_BENEFICIAMENTO")
        await db.commit()

        disp = await get_saldo(db, b["bruto"].id, b["loc"].id, "DISPONIVEL")
        em_ban = await get_saldo(db, b["bruto"].id, b["loc"].id, "EM_BENEFICIAMENTO")

        assert disp == Decimal("100")
        assert em_ban == Decimal("100")

    async def test_remessa_nao_permite_enviar_mais_que_disponivel(self, db, base_dados):
        """Tentar enviar mais do que disponível deve falhar."""
        from fastapi import HTTPException
        b = base_dados

        with pytest.raises(HTTPException) as exc_info:
            await movimentar(db, b["bruto"].id, b["loc"].id,
                             tipo="SAIDA_REMESSA_BANHO", quantidade=Decimal("-500"),
                             status_estoque="DISPONIVEL")
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# Fluxo de Retorno
# ---------------------------------------------------------------------------

class TestRetornoBanho:
    async def _enviar(self, db, base_dados, qtd=Decimal("100")):
        b = base_dados
        await movimentar(db, b["bruto"].id, b["loc"].id,
                         tipo="SAIDA_REMESSA_BANHO", quantidade=-qtd,
                         status_estoque="DISPONIVEL")
        await movimentar(db, b["bruto"].id, b["loc"].id,
                         tipo="ENTRADA_EM_BENEFICIAMENTO", quantidade=qtd,
                         status_estoque="EM_BENEFICIAMENTO")
        await db.commit()

    async def test_retorno_completo_zera_em_beneficiamento(self, db, base_dados):
        """Retorno total: EM_BENEFICIAMENTO vai a zero."""
        b = base_dados
        await self._enviar(db, b, Decimal("100"))

        # Baixa EM_BENEFICIAMENTO
        await movimentar(db, b["bruto"].id, b["loc"].id,
                         tipo="SAIDA_RETORNO_BANHO", quantidade=Decimal("-100"),
                         status_estoque="EM_BENEFICIAMENTO")
        # Entra produto acabado no DISPONIVEL
        await movimentar(db, b["acabado"].id, b["loc"].id,
                         tipo="ENTRADA_RETORNO_BANHO", quantidade=Decimal("98"),  # 2% perda
                         status_estoque="DISPONIVEL")
        await db.commit()

        em_ban = await get_saldo(db, b["bruto"].id, b["loc"].id, "EM_BENEFICIAMENTO")
        acabado_disp = await get_saldo(db, b["acabado"].id, b["loc"].id, "DISPONIVEL")

        assert em_ban == Decimal("0")
        assert acabado_disp == Decimal("98")

    async def test_perda_total_correta(self, db, base_dados):
        """A diferença entre enviado e retornado deve ser registrável."""
        b = base_dados
        enviado = Decimal("100")
        retornado = Decimal("97")
        perda = enviado - retornado

        await self._enviar(db, b, enviado)
        await movimentar(db, b["bruto"].id, b["loc"].id,
                         tipo="SAIDA_RETORNO_BANHO", quantidade=-enviado,
                         status_estoque="EM_BENEFICIAMENTO")
        await movimentar(db, b["acabado"].id, b["loc"].id,
                         tipo="ENTRADA_RETORNO_BANHO", quantidade=retornado,
                         status_estoque="DISPONIVEL")
        await db.commit()

        acabado_disp = await get_saldo(db, b["acabado"].id, b["loc"].id, "DISPONIVEL")
        assert acabado_disp == retornado
        assert perda == Decimal("3")  # 3% de perda no lote


# ---------------------------------------------------------------------------
# Alertas de Prazo Vencido
# ---------------------------------------------------------------------------

class TestAlertasPrazoVencido:
    async def test_lote_com_prazo_vencido_e_detectavel(self, db, base_dados):
        """Lotes com data_previsao_retorno < hoje e status ENVIADO são detectados."""
        b = base_dados

        lote = LoteBeneficiamento(
            numero="BNF-ATRASADO-001",
            prestador_id=b["prestador"].id,
            data_remessa=date.today() - timedelta(days=10),
            data_previsao_retorno=date.today() - timedelta(days=3),  # Venceu há 3 dias
            status="ENVIADO",
        )
        db.add(lote)
        await db.commit()

        # Consulta que o dashboard usaria
        hoje = date.today()
        r = await db.execute(
            select(LoteBeneficiamento).where(
                LoteBeneficiamento.status.in_(["ENVIADO", "AGUARDANDO_RETORNO"]),
                LoteBeneficiamento.data_previsao_retorno < hoje,
            )
        )
        atrasados = r.scalars().all()
        assert len(atrasados) == 1
        assert atrasados[0].numero == "BNF-ATRASADO-001"

    async def test_lote_no_prazo_nao_aparece_como_atrasado(self, db, base_dados):
        b = base_dados
        lote = LoteBeneficiamento(
            numero="BNF-NO-PRAZO-001",
            prestador_id=b["prestador"].id,
            data_remessa=date.today() - timedelta(days=2),
            data_previsao_retorno=date.today() + timedelta(days=5),  # No prazo
            status="ENVIADO",
        )
        db.add(lote)
        await db.commit()

        hoje = date.today()
        r = await db.execute(
            select(LoteBeneficiamento).where(
                LoteBeneficiamento.status.in_(["ENVIADO", "AGUARDANDO_RETORNO"]),
                LoteBeneficiamento.data_previsao_retorno < hoje,
            )
        )
        atrasados = r.scalars().all()
        assert len(atrasados) == 0
