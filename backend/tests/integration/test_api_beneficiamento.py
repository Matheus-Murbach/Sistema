"""
Testes de integração — Beneficiamento Externo via API.

Cobre:
  - GET /beneficiamento/ (lista lotes)
  - GET /beneficiamento/em-transito
  - GET /beneficiamento/{id}
  - POST /beneficiamento/ (cria lote e movimenta estoque)
  - POST /beneficiamento/{id}/retorno
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.parceiro import PrestadorBeneficiamento
from app.services.estoque_service import movimentar, get_saldo


async def _setup_banho(test_engine):
    """Cria estrutura base para testes de beneficiamento."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.flush()

        bruto = Produto(
            codigo="BRUTO-M8",
            descricao="Parafuso Bruto M8",
            tipo="SEMI_ACABADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
        )
        acabado = Produto(
            codigo="ZINC-M8",
            descricao="Parafuso Zincado M8",
            tipo="PRODUTO_BENEFICIADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
        )
        session.add(bruto)
        session.add(acabado)

        loc = LocalizacaoEstoque(codigo="BNH-01", descricao="Estoque para Banho")
        session.add(loc)

        prestador = PrestadorBeneficiamento(
            razao_social="Zincagem Industrial Ltda",
            cnpj_cpf="55.666.777/0001-88",
            tipo_beneficiamento="Zincagem Eletrolítica",
            prazo_retorno_dias=5,
            percentual_perda_esperado=1.5,
        )
        session.add(prestador)
        await session.flush()

        # Coloca 300 unidades brutas em estoque disponível
        await movimentar(
            session, bruto.id, loc.id,
            tipo="ENTRADA_COMPRA",
            quantidade=Decimal("300"),
        )
        await session.commit()
        await session.refresh(bruto)
        await session.refresh(acabado)
        await session.refresh(loc)
        await session.refresh(prestador)

        return {
            "bruto_id": bruto.id,
            "acabado_id": acabado.id,
            "loc_id": loc.id,
            "prestador_id": prestador.id,
        }


class TestListarLotes:
    async def test_listar_lotes_vazio(self, client):
        r = await client.get("/api/v1/beneficiamento/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_em_transito_vazio(self, client):
        r = await client.get("/api/v1/beneficiamento/em-transito")
        assert r.status_code == 200
        assert r.json() == []

    async def test_detalhar_lote_inexistente_404(self, client):
        r = await client.get("/api/v1/beneficiamento/99999")
        assert r.status_code == 404


class TestCriarLote:
    async def test_criar_lote_baixa_estoque_disponivel(
        self, client, auth_headers, test_engine
    ):
        """Criar lote deve baixar do estoque DISPONIVEL e criar EM_BENEFICIAMENTO."""
        ids = await _setup_banho(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        payload = {
            "prestador_id": ids["prestador_id"],
            "tipo_beneficiamento": "Zincagem",
            "data_remessa": str(date.today()),
            "data_previsao_retorno": str(date.today() + timedelta(days=5)),
            "cfop_remessa": "5901",
            "cfop_retorno": "5902",
            "itens": [
                {
                    "produto_enviado_id": ids["bruto_id"],
                    "produto_retorno_id": ids["acabado_id"],
                    "localizacao_saida_id": ids["loc_id"],
                    "localizacao_retorno_id": ids["loc_id"],
                    "quantidade_enviada": "100",
                }
            ],
        }
        r = await client.post("/api/v1/beneficiamento/", json=payload, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "ENVIADO"
        assert body["prestador_id"] == ids["prestador_id"]

        # Verificar estoque: DISPONIVEL deve ter diminuído
        async with Session() as session:
            disponivel = await get_saldo(session, ids["bruto_id"], ids["loc_id"], "DISPONIVEL")
            em_banho = await get_saldo(session, ids["bruto_id"], ids["loc_id"], "EM_BENEFICIAMENTO")

        assert disponivel == Decimal("200")  # 300 - 100
        assert em_banho == Decimal("100")

    async def test_criar_lote_sem_estoque_suficiente_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Tentar enviar mais do que disponível deve retornar 422."""
        ids = await _setup_banho(test_engine)

        payload = {
            "prestador_id": ids["prestador_id"],
            "data_remessa": str(date.today()),
            "itens": [
                {
                    "produto_enviado_id": ids["bruto_id"],
                    "localizacao_saida_id": ids["loc_id"],
                    "quantidade_enviada": "999",  # Mais do que os 300 disponíveis
                }
            ],
        }
        r = await client.post("/api/v1/beneficiamento/", json=payload, headers=auth_headers)
        assert r.status_code == 422

    async def test_criar_lote_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/beneficiamento/", json={})
        assert r.status_code == 401

    async def test_listar_lotes_apos_criacao(self, client, auth_headers, test_engine):
        ids = await _setup_banho(test_engine)

        await client.post("/api/v1/beneficiamento/", json={
            "prestador_id": ids["prestador_id"],
            "data_remessa": str(date.today()),
            "itens": [
                {
                    "produto_enviado_id": ids["bruto_id"],
                    "localizacao_saida_id": ids["loc_id"],
                    "quantidade_enviada": "50",
                }
            ],
        }, headers=auth_headers)

        r = await client.get("/api/v1/beneficiamento/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_em_transito_mostra_lote_enviado(self, client, auth_headers, test_engine):
        ids = await _setup_banho(test_engine)

        await client.post("/api/v1/beneficiamento/", json={
            "prestador_id": ids["prestador_id"],
            "data_remessa": str(date.today()),
            "itens": [
                {
                    "produto_enviado_id": ids["bruto_id"],
                    "localizacao_saida_id": ids["loc_id"],
                    "quantidade_enviada": "30",
                }
            ],
        }, headers=auth_headers)

        r = await client.get("/api/v1/beneficiamento/em-transito")
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestRetornoLote:
    async def test_retorno_completo_atualiza_status(
        self, client, auth_headers, test_engine
    ):
        """Retorno completo deve mudar status do lote para RETORNADO."""
        from sqlalchemy import select
        from app.models.beneficiamento import ItemLoteBeneficiamento

        ids = await _setup_banho(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        # Criar lote
        r_lote = await client.post("/api/v1/beneficiamento/", json={
            "prestador_id": ids["prestador_id"],
            "data_remessa": str(date.today()),
            "itens": [
                {
                    "produto_enviado_id": ids["bruto_id"],
                    "produto_retorno_id": ids["acabado_id"],
                    "localizacao_saida_id": ids["loc_id"],
                    "localizacao_retorno_id": ids["loc_id"],
                    "quantidade_enviada": "100",
                }
            ],
        }, headers=auth_headers)
        assert r_lote.status_code == 201
        lote_id = r_lote.json()["id"]

        # Buscar o item_id diretamente no banco (a resposta da API não serializa relações)
        async with Session() as session:
            r = await session.execute(
                select(ItemLoteBeneficiamento).where(
                    ItemLoteBeneficiamento.lote_id == lote_id
                )
            )
            item = r.scalar_one()
            item_id = item.id

        # Registrar retorno completo
        r_retorno = await client.post(
            f"/api/v1/beneficiamento/{lote_id}/retorno",
            json={
                "data_retorno": str(date.today()),
                "nf_retorno_numero": "NF-99999",
                "valor_servico": "500.00",
                "itens": [
                    {
                        "item_id": item_id,
                        "quantidade_retornada": "99",  # 1% de perda → dentro do limite de 99%
                        "quantidade_rejeitada": "1",
                        "localizacao_retorno_id": ids["loc_id"],
                    }
                ],
            },
            headers=auth_headers,
        )
        assert r_retorno.status_code == 200
        body = r_retorno.json()
        assert body["status"] == "RETORNADO"
        assert float(body["total_retornado"]) == 99.0

    async def test_retorno_lote_inexistente_retorna_404(self, client, auth_headers):
        r = await client.post(
            "/api/v1/beneficiamento/99999/retorno",
            json={
                "data_retorno": str(date.today()),
                "itens": [],
            },
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_detalhar_lote_apos_criacao(self, client, auth_headers, test_engine):
        """Após criar o lote, detalhar deve retornar os dados corretos."""
        ids = await _setup_banho(test_engine)

        r_lote = await client.post("/api/v1/beneficiamento/", json={
            "prestador_id": ids["prestador_id"],
            "data_remessa": str(date.today()),
            "observacoes": "Lote de teste zincagem",
            "itens": [
                {
                    "produto_enviado_id": ids["bruto_id"],
                    "localizacao_saida_id": ids["loc_id"],
                    "quantidade_enviada": "25",
                }
            ],
        }, headers=auth_headers)
        lote_id = r_lote.json()["id"]

        r = await client.get(f"/api/v1/beneficiamento/{lote_id}")
        assert r.status_code == 200
        assert r.json()["id"] == lote_id
        assert r.json()["observacoes"] == "Lote de teste zincagem"
