"""
Testes de integração — Recebimento de mercadorias.

Cobre:
  - GET /recebimento/ (lista NFs de entrada)
  - POST /recebimento/ (registra NF e dá entrada no estoque)
  - Cálculo de créditos fiscais na entrada (CRT 3 — Regime Normal)
  - Rejeição por QC: quantidade aprovada < quantidade total
"""
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.estoque import SaldoEstoque
from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.parceiro import Fornecedor


async def _criar_base(test_engine, auth_headers, client):
    """Cria produto, localização e fornecedor necessários para os testes de recebimento."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="MP-001",
            descricao="Chapa de Aço",
            tipo="MATERIA_PRIMA",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("5"),
            aliq_pis=Decimal("1.65"),
            aliq_cofins=Decimal("7.60"),
        )
        session.add(produto)

        loc = LocalizacaoEstoque(codigo="E-01", descricao="Estoque Matérias-Primas")
        session.add(loc)

        fornecedor = Fornecedor(
            razao_social="Siderúrgica Norte Ltda",
            cnpj_cpf="10.000.000/0001-00",
            uf="MG",
        )
        session.add(fornecedor)
        await session.commit()
        await session.refresh(produto)
        await session.refresh(loc)
        await session.refresh(fornecedor)
        return produto.id, loc.id, fornecedor.id


class TestListarEntradas:
    async def test_listar_entradas_vazio(self, client):
        r = await client.get("/api/v1/recebimento/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_detalhar_entrada_inexistente_404(self, client):
        r = await client.get("/api/v1/recebimento/99999")
        assert r.status_code == 404


class TestRegistrarEntrada:
    async def test_entrada_compra_mp_da_estoque(self, client, auth_headers, test_engine):
        produto_id, loc_id, forn_id = await _criar_base(test_engine, auth_headers, client)

        payload = {
            "tipo_entrada": "COMPRA_MP",
            "fornecedor_id": forn_id,
            "numero_nf": "NF-12345",
            "serie": "1",
            "data_emissao": "2026-04-15",
            "data_entrada": "2026-04-15",
            "cfop_entrada": "1101",
            "itens": [
                {
                    "produto_id": produto_id,
                    "localizacao_id": loc_id,
                    "quantidade": "100.0000",
                    "preco_unitario": "50.00",
                    "aliq_icms": "12.00",
                    "aliq_ipi": "5.00",
                    "aliq_pis": "1.65",
                    "aliq_cofins": "7.60",
                }
            ],
        }
        r = await client.post("/api/v1/recebimento/", json=payload, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["numero_nf"] == "NF-12345"
        assert body["status"] == "LANCADA"
        assert float(body["valor_produtos"]) == 5000.0

    async def test_entrada_calcula_credito_icms_regime_normal(
        self, client, auth_headers, test_engine
    ):
        """Regime Normal (CRT 3): compra de MP deve gerar crédito de ICMS."""
        produto_id, loc_id, forn_id = await _criar_base(test_engine, auth_headers, client)

        payload = {
            "tipo_entrada": "COMPRA_MP",
            "fornecedor_id": forn_id,
            "numero_nf": "NF-22222",
            "data_emissao": "2026-04-15",
            "data_entrada": "2026-04-15",
            "itens": [
                {
                    "produto_id": produto_id,
                    "localizacao_id": loc_id,
                    "quantidade": "100.0000",
                    "preco_unitario": "100.00",  # valor_total = R$ 10.000
                    "aliq_icms": "12.00",         # crédito_icms = R$ 1.200
                    "aliq_ipi": "5.00",            # crédito_ipi = R$ 500 (é MP)
                    "aliq_pis": "1.65",
                    "aliq_cofins": "7.60",
                }
            ],
        }
        r = await client.post("/api/v1/recebimento/", json=payload, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert float(body["credito_icms"]) == 1200.0
        assert float(body["credito_ipi"]) == 500.0

    async def test_entrada_com_qc_usa_quantidade_aprovada(
        self, client, auth_headers, test_engine
    ):
        """QC: apenas quantidade_aprovada deve entrar no estoque."""
        produto_id, loc_id, forn_id = await _criar_base(test_engine, auth_headers, client)

        payload = {
            "tipo_entrada": "COMPRA_MP",
            "fornecedor_id": forn_id,
            "numero_nf": "NF-33333",
            "data_emissao": "2026-04-15",
            "data_entrada": "2026-04-15",
            "itens": [
                {
                    "produto_id": produto_id,
                    "localizacao_id": loc_id,
                    "quantidade": "100.0000",
                    "preco_unitario": "10.00",
                    "aliq_icms": "0",
                    "aliq_ipi": "0",
                    "aliq_pis": "0",
                    "aliq_cofins": "0",
                    "aprovado_qc": True,
                    "quantidade_aprovada": "90.0000",  # 10 unidades rejeitadas
                    "observacao_qc": "10 unidades fora de especificação",
                }
            ],
        }
        r = await client.post("/api/v1/recebimento/", json=payload, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        # Valor deve ser calculado sobre 90, não 100
        assert float(body["valor_produtos"]) == 900.0

    async def test_entrada_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/recebimento/", json={})
        assert r.status_code == 401

    async def test_listar_entradas_apos_criacao(self, client, auth_headers, test_engine):
        produto_id, loc_id, forn_id = await _criar_base(test_engine, auth_headers, client)

        payload = {
            "tipo_entrada": "COMPRA_MP",
            "numero_nf": "NF-55555",
            "data_emissao": "2026-04-15",
            "data_entrada": "2026-04-15",
            "itens": [
                {
                    "produto_id": produto_id,
                    "localizacao_id": loc_id,
                    "quantidade": "10.0000",
                    "preco_unitario": "5.00",
                    "aliq_icms": "0",
                    "aliq_ipi": "0",
                    "aliq_pis": "0",
                    "aliq_cofins": "0",
                }
            ],
        }
        await client.post("/api/v1/recebimento/", json=payload, headers=auth_headers)

        r = await client.get("/api/v1/recebimento/")
        assert r.status_code == 200
        assert len(r.json()) >= 1
