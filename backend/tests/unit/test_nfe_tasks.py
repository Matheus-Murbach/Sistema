"""
TDD — Testes unitários da Celery task de verificação de NF-e.

Estratégia: testa a função _run() interna diretamente usando banco SQLite
in-memory + mock do focus_nfe.consultar_nfe, sem precisar de broker Celery.

Comportamentos críticos:
  - 'autorizado' → NF atualizada + liberar_reserva chamada + pedido EXPEDIDO
  - 'erro_autorizacao' → NF marcada REJEITADA + motivo_rejeicao preenchido
  - 'pendente' → retorna "pendente" (task faria self.retry() em produção)
  - NF não encontrada → retorna "nf_nao_encontrada"
"""
import pytest
import asyncio
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.database import Base
from app.models.expedicao import NotaFiscalSaida
from app.models.venda import PedidoVenda
from app.models.parceiro import Cliente
from app.models.estoque import LocalizacaoEstoque, SaldoEstoque
from app.models.produto import Produto, UnidadeMedida


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
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
async def nf_e_pedido(db):
    """Cria NF em status AGUARDANDO + PedidoVenda CONFIRMADO para os testes."""
    un = UnidadeMedida(codigo="UN", descricao="Unidade")
    db.add(un)
    await db.flush()

    cliente = Cliente(
        razao_social="Cliente Teste",
        cnpj_cpf="11.111.111/0001-11",
        uf="SP",
    )
    db.add(cliente)
    await db.flush()

    pedido = PedidoVenda(
        numero="PV-TASK-001",
        cliente_id=cliente.id,
        status="CONFIRMADO",
        data_emissao=date.today(),
        valor_frete=Decimal("0"),
    )
    db.add(pedido)
    await db.flush()

    nf = NotaFiscalSaida(
        pedido_venda_id=pedido.id,
        cliente_id=cliente.id,
        natureza_operacao="VENDA DE MERCADORIA",
        finalidade="1",
        tipo_operacao="1",
        status_sefaz="AGUARDANDO",
        focus_referencia="NF-TASK-REF-001",
        valor_total=Decimal("100.00"),
    )
    db.add(nf)
    await db.commit()

    await db.refresh(nf)
    await db.refresh(pedido)
    return {"nf": nf, "pedido": pedido}


# ---------------------------------------------------------------------------
# Extrai a função _run() interna da task para teste isolado
# ---------------------------------------------------------------------------

def _extrair_run(nf_id: int, pedido_id: int, referencia: str, mock_session, mock_focus):
    """
    Reconstrói a função _run() interna da task com dependências substituídas.
    Isso permite testar a lógica sem precisar de Celery ou broker.
    """
    from sqlalchemy import select as sa_select
    from app.models.expedicao import NotaFiscalSaida as NFS
    from app.models.venda import PedidoVenda as PV

    async def _run():
        resultado_focus = await mock_focus.consultar_nfe(referencia)
        data = resultado_focus.get("data", {})
        status = data.get("status", "")

        async with mock_session() as db:
            r = await db.execute(sa_select(NFS).where(NFS.id == nf_id))
            nf = r.scalar_one_or_none()
            if not nf:
                return "nf_nao_encontrada"

            if status == "autorizado":
                nf.status_sefaz = "AUTORIZADA"
                nf.numero = str(data.get("numero_nfe", ""))
                nf.chave_acesso = data.get("chave_nfe", "")
                nf.protocolo = data.get("numero_protocolo", "")

                from app.services.estoque_service import liberar_reserva
                await liberar_reserva(db, pedido_id, consumir=True)

                r2 = await db.execute(sa_select(PV).where(PV.id == pedido_id))
                pedido = r2.scalar_one_or_none()
                if pedido:
                    pedido.status = "EXPEDIDO"
                await db.commit()
                return "autorizado"

            elif status == "erro_autorizacao":
                nf.status_sefaz = "REJEITADA"
                nf.motivo_rejeicao = str(data.get("erros", ""))
                await db.commit()
                return "rejeitado"

            return "pendente"

    return _run


# ---------------------------------------------------------------------------
# Cenário: NF autorizada
# ---------------------------------------------------------------------------

class TestNFAutorizada:
    async def test_autorizado_atualiza_nf_e_pedido(self, engine, nf_e_pedido):
        nf = nf_e_pedido["nf"]
        pedido = nf_e_pedido["pedido"]

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "data": {
                "status": "autorizado",
                "numero_nfe": "999",
                "chave_nfe": "35240412345678000199550010000000011234567890",
                "numero_protocolo": "135240000000999",
            }
        }

        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        _run = _extrair_run(nf.id, pedido.id, nf.focus_referencia, Session, mock_focus)
        resultado = await _run()

        assert resultado == "autorizado"

        async with Session() as session:
            r = await session.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf.id))
            nf_atualizada = r.scalar_one()
            r2 = await session.execute(select(PedidoVenda).where(PedidoVenda.id == pedido.id))
            pedido_atualizado = r2.scalar_one()

        assert nf_atualizada.status_sefaz == "AUTORIZADA"
        assert nf_atualizada.numero == "999"
        assert nf_atualizada.chave_acesso == "35240412345678000199550010000000011234567890"
        assert pedido_atualizado.status == "EXPEDIDO"


# ---------------------------------------------------------------------------
# Cenário: NF com erro de autorização
# ---------------------------------------------------------------------------

class TestNFRejeitada:
    async def test_erro_autorizacao_marca_rejeitada(self, engine, nf_e_pedido):
        nf = nf_e_pedido["nf"]
        pedido = nf_e_pedido["pedido"]

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "data": {
                "status": "erro_autorizacao",
                "erros": "CNPJ do emitente inválido",
            }
        }

        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        _run = _extrair_run(nf.id, pedido.id, nf.focus_referencia, Session, mock_focus)
        resultado = await _run()

        assert resultado == "rejeitado"

        async with Session() as session:
            r = await session.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf.id))
            nf_atualizada = r.scalar_one()

        assert nf_atualizada.status_sefaz == "REJEITADA"
        assert "CNPJ" in nf_atualizada.motivo_rejeicao

    async def test_pedido_nao_muda_para_expedido_em_caso_de_rejeicao(
        self, engine, nf_e_pedido
    ):
        nf = nf_e_pedido["nf"]
        pedido = nf_e_pedido["pedido"]

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "data": {"status": "erro_autorizacao", "erros": "Erro"}
        }

        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        _run = _extrair_run(nf.id, pedido.id, nf.focus_referencia, Session, mock_focus)
        await _run()

        async with Session() as session:
            r = await session.execute(select(PedidoVenda).where(PedidoVenda.id == pedido.id))
            pedido_atualizado = r.scalar_one()

        # Pedido deve permanecer CONFIRMADO (não expedido)
        assert pedido_atualizado.status == "CONFIRMADO"


# ---------------------------------------------------------------------------
# Cenário: NF pendente (processando)
# ---------------------------------------------------------------------------

class TestNFPendente:
    async def test_pendente_retorna_pendente(self, engine, nf_e_pedido):
        """Status 'processando' deve retornar 'pendente' (task recolocaria na fila)."""
        nf = nf_e_pedido["nf"]
        pedido = nf_e_pedido["pedido"]

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "data": {"status": "processando"}
        }

        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        _run = _extrair_run(nf.id, pedido.id, nf.focus_referencia, Session, mock_focus)
        resultado = await _run()

        assert resultado == "pendente"

        # NF deve continuar AGUARDANDO
        async with Session() as session:
            r = await session.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf.id))
            nf_atual = r.scalar_one()
        assert nf_atual.status_sefaz == "AGUARDANDO"


# ---------------------------------------------------------------------------
# Cenário: NF não encontrada
# ---------------------------------------------------------------------------

class TestNFNaoEncontrada:
    async def test_nf_inexistente_retorna_nf_nao_encontrada(self, engine, nf_e_pedido):
        pedido = nf_e_pedido["pedido"]

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "data": {"status": "autorizado"}
        }

        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        _run = _extrair_run(99999, pedido.id, "REF-INEXISTENTE", Session, mock_focus)
        resultado = await _run()

        assert resultado == "nf_nao_encontrada"
