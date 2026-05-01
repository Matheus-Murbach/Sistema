"""
Testes de integração — Pedidos de Compra via API.

Cobre os endpoints:
  - GET /compras/               → listar pedidos (com e sem filtro de status)
  - POST /compras/              → criar pedido com itens e cálculo de valor_total
  - PUT /compras/{id}/status    → atualizar status do pedido
"""
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.parceiro import Fornecedor
from app.models.produto import Produto, UnidadeMedida


async def _setup_compra(test_engine):
    """Cria fornecedor e produto mínimos para os testes de compra."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="KG", descricao="Quilograma")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="MP-ACO-01",
            descricao="Barra de Aço",
            tipo="MATERIA_PRIMA",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
        )
        session.add(produto)

        fornecedor = Fornecedor(
            razao_social="Siderúrgica São Paulo Ltda",
            cnpj_cpf="10.000.000/0001-00",
            uf="SP",
        )
        session.add(fornecedor)
        await session.commit()
        await session.refresh(produto)
        await session.refresh(fornecedor)
        return {"produto_id": produto.id, "fornecedor_id": fornecedor.id}


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

class TestListarPedidosCompra:
    async def test_listar_vazio(self, client):
        r = await client.get("/api/v1/compras/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_listar_com_filtro_status_vazio(self, client):
        r = await client.get("/api/v1/compras/?status=ABERTO")
        assert r.status_code == 200
        assert r.json() == []

    async def test_listar_apos_criacao(self, client, auth_headers, test_engine):
        ids = await _setup_compra(test_engine)

        await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [
                {"produto_id": ids["produto_id"], "quantidade": "10", "preco_unitario": "5.00"},
            ],
        }, headers=auth_headers)

        r = await client.get("/api/v1/compras/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_filtro_status_exclui_outros(self, client, auth_headers, test_engine):
        """Pedidos em ABERTO não aparecem quando filtro é RECEBIDO."""
        ids = await _setup_compra(test_engine)

        await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [],
        }, headers=auth_headers)

        r = await client.get("/api/v1/compras/?status=RECEBIDO")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------

class TestCriarPedidoCompra:
    async def test_criar_pedido_basico(self, client, auth_headers, test_engine):
        ids = await _setup_compra(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [
                {"produto_id": ids["produto_id"], "quantidade": "10", "preco_unitario": "5.00"},
            ],
        }, headers=auth_headers)

        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "ABERTO"
        assert body["numero"].startswith("PC-")
        assert float(body["valor_total"]) == pytest.approx(50.0)

    async def test_valor_total_e_soma_dos_itens(self, client, auth_headers, test_engine):
        """Dois itens com quantidades e preços diferentes — total deve ser a soma."""
        ids = await _setup_compra(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [
                {"produto_id": ids["produto_id"], "quantidade": "5", "preco_unitario": "10.00"},
                {"produto_id": ids["produto_id"], "quantidade": "3", "preco_unitario": "20.00"},
            ],
        }, headers=auth_headers)

        assert r.status_code == 201
        # 5×10 + 3×20 = 50 + 60 = 110
        assert float(r.json()["valor_total"]) == pytest.approx(110.0)

    async def test_criar_pedido_sem_itens(self, client, auth_headers, test_engine):
        """Lista vazia de itens deve criar pedido com total zero."""
        ids = await _setup_compra(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [],
        }, headers=auth_headers)

        assert r.status_code == 201
        assert float(r.json()["valor_total"]) == 0.0

    async def test_criar_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/compras/", json={})
        assert r.status_code == 401

    async def test_numero_sequencial_cresce(self, client, auth_headers, test_engine):
        """Dois pedidos devem ter números diferentes."""
        ids = await _setup_compra(test_engine)

        payload = {
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [],
        }
        r1 = await client.post("/api/v1/compras/", json=payload, headers=auth_headers)
        r2 = await client.post("/api/v1/compras/", json=payload, headers=auth_headers)

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["numero"] != r2.json()["numero"]

    async def test_campos_opcionais_preservados(self, client, auth_headers, test_engine):
        """Campos opcionais (condicao_pagamento, observacoes) devem ser persistidos."""
        ids = await _setup_compra(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "condicao_pagamento": "30/60 dias",
            "observacoes": "Pedido urgente",
            "itens": [],
        }, headers=auth_headers)

        assert r.status_code == 201
        body = r.json()
        assert body["condicao_pagamento"] == "30/60 dias"
        assert body["observacoes"] == "Pedido urgente"


# ---------------------------------------------------------------------------
# Atualização de Status
# ---------------------------------------------------------------------------

class TestStatusPedidoCompra:
    async def test_atualizar_status(self, client, auth_headers, test_engine):
        ids = await _setup_compra(test_engine)

        r_create = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_create.json()["id"]

        r = await client.put(
            f"/api/v1/compras/{pedido_id}/status?novo_status=ENVIADO",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ENVIADO"

    async def test_atualizar_status_pedido_inexistente(self, client, auth_headers):
        r = await client.put(
            "/api/v1/compras/99999/status?novo_status=CANCELADO",
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_atualizar_status_sem_auth(self, client):
        r = await client.put("/api/v1/compras/1/status?novo_status=CANCELADO")
        assert r.status_code == 401

    async def test_filtro_status_apos_atualizacao(self, client, auth_headers, test_engine):
        """Após atualizar para RECEBIDO, pedido aparece no filtro correspondente."""
        ids = await _setup_compra(test_engine)

        r_create = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": str(date.today()),
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_create.json()["id"]

        await client.put(
            f"/api/v1/compras/{pedido_id}/status?novo_status=RECEBIDO",
            headers=auth_headers,
        )

        r = await client.get("/api/v1/compras/?status=RECEBIDO")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["id"] == pedido_id
