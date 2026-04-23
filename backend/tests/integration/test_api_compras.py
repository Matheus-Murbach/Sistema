"""
Testes de integração — Pedidos de Compra via API.

Módulo: /api/v1/compras/
Endpoints cobertos:
  GET  /compras/                       → Lista pedidos, filtra por status
  POST /compras/                       → Cria pedido com itens e calcula valor_total
  PUT  /compras/{id}/status            → Atualiza status do pedido

Regras de negócio verificadas:
  - Números de pedido únicos (PC-YYYYMMDD-N) mesmo para o mesmo fornecedor
  - valor_total = soma de (qtd × preco_unit) por item
  - Status inicia como ABERTO; pode ser atualizado para ENVIADO, RECEBIDO etc.
  - Todos os endpoints de escrita exigem autenticação (401 sem token)
"""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida
from app.models.parceiro import Fornecedor


async def _setup_compras(test_engine):
    """Cria fornecedor e produto de matéria-prima para uso nos testes."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="KG", descricao="Quilograma")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="MP-ACO-001",
            descricao="Aço 1020 Barra",
            tipo="MATERIA_PRIMA",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
        )
        session.add(produto)

        fornecedor = Fornecedor(
            razao_social="Aços Brasil Ltda",
            cnpj_cpf="12.345.678/0001-99",
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
        """Com banco zerado, retorna lista vazia."""
        r = await client.get("/api/v1/compras/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_listar_apos_criacao(self, client, auth_headers, test_engine):
        """Pedido criado aparece na listagem geral."""
        ids = await _setup_compras(test_engine)

        await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)

        r = await client.get("/api/v1/compras/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_filtro_por_status_aberto(self, client, auth_headers, test_engine):
        """Filtro status=ABERTO retorna apenas pedidos nesse estado."""
        ids = await _setup_compras(test_engine)

        await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)

        r_aberto = await client.get("/api/v1/compras/?status=ABERTO")
        assert r_aberto.status_code == 200
        assert len(r_aberto.json()) == 1

        r_enviado = await client.get("/api/v1/compras/?status=ENVIADO")
        assert r_enviado.status_code == 200
        assert len(r_enviado.json()) == 0


# ---------------------------------------------------------------------------
# Criação
# ---------------------------------------------------------------------------

class TestCriarPedidoCompra:
    async def test_criar_basico_retorna_201(self, client, auth_headers, test_engine):
        """Criar pedido com um item retorna 201 com status ABERTO."""
        ids = await _setup_compras(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {"produto_id": ids["produto_id"], "quantidade": "50", "preco_unitario": "8.00"},
            ],
        }, headers=auth_headers)

        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "ABERTO"
        assert float(body["valor_total"]) == pytest.approx(400.0)
        assert body["numero"].startswith("PC-")

    async def test_numero_unico_dois_pedidos_mesmo_fornecedor(self, client, auth_headers, test_engine):
        """Dois pedidos para o mesmo fornecedor devem ter números distintos (evita duplicate key)."""
        ids = await _setup_compras(test_engine)

        r1 = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        r2 = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)

        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["numero"] != r2.json()["numero"]

    async def test_valor_total_multiplos_itens(self, client, auth_headers, test_engine):
        """valor_total deve ser a soma de todos os itens do pedido."""
        ids = await _setup_compras(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            from sqlalchemy import select
            r = await session.execute(select(UnidadeMedida).where(UnidadeMedida.codigo == "KG"))
            un = r.scalar_one()
            p2 = Produto(codigo="MP-ACO-002", descricao="Aço 1045", tipo="MATERIA_PRIMA", unidade_id=un.id)
            session.add(p2)
            await session.commit()
            await session.refresh(p2)
            p2_id = p2.id

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {"produto_id": ids["produto_id"], "quantidade": "10", "preco_unitario": "5.00"},
                {"produto_id": p2_id,             "quantidade": "20", "preco_unitario": "3.00"},
            ],
        }, headers=auth_headers)

        assert r.status_code == 201
        assert float(r.json()["valor_total"]) == pytest.approx(110.0)

    async def test_pedido_sem_itens_valor_zero(self, client, auth_headers, test_engine):
        """Pedido sem itens deve ser aceito com valor_total zero."""
        ids = await _setup_compras(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)

        assert r.status_code == 201
        assert float(r.json()["valor_total"]) == 0.0

    async def test_criar_sem_auth_retorna_401(self, client):
        """Endpoint de criação exige autenticação."""
        r = await client.post("/api/v1/compras/", json={})
        assert r.status_code == 401

    async def test_criar_com_condicao_pagamento(self, client, auth_headers, test_engine):
        """Campos opcionais (condicao_pagamento, observacoes) são persistidos."""
        ids = await _setup_compras(test_engine)

        r = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "condicao_pagamento": "30/60/90 dias",
            "observacoes": "Frete CIF",
            "itens": [],
        }, headers=auth_headers)

        assert r.status_code == 201
        body = r.json()
        assert body["condicao_pagamento"] == "30/60/90 dias"
        assert body["observacoes"] == "Frete CIF"


# ---------------------------------------------------------------------------
# Atualização de status
# ---------------------------------------------------------------------------

class TestAtualizarStatusCompra:
    async def test_atualizar_para_enviado(self, client, auth_headers, test_engine):
        """Status ABERTO → ENVIADO deve funcionar normalmente."""
        ids = await _setup_compras(test_engine)

        r_create = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_create.json()["id"]

        r = await client.put(
            f"/api/v1/compras/{pedido_id}/status?novo_status=ENVIADO",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ENVIADO"

    async def test_atualizar_para_recebido(self, client, auth_headers, test_engine):
        """Status pode avançar até RECEBIDO."""
        ids = await _setup_compras(test_engine)

        r_create = await client.post("/api/v1/compras/", json={
            "fornecedor_id": ids["fornecedor_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_create.json()["id"]

        r = await client.put(
            f"/api/v1/compras/{pedido_id}/status?novo_status=RECEBIDO",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "RECEBIDO"

    async def test_pedido_inexistente_retorna_404(self, client, auth_headers):
        """Atualizar status de pedido que não existe deve retornar 404."""
        r = await client.put(
            "/api/v1/compras/99999/status?novo_status=ENVIADO",
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_atualizar_sem_auth_retorna_401(self, client):
        """Endpoint de atualização exige autenticação."""
        r = await client.put("/api/v1/compras/1/status?novo_status=ENVIADO")
        assert r.status_code == 401
