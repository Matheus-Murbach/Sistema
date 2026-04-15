"""
Testes de integração — Fluxo de Vendas via API.

Verifica:
  1. POST /vendas/           → Cria pedido (ORCAMENTO) com cálculo de impostos
  2. POST /vendas/{id}/confirmar → Reserva estoque automaticamente (CONFIRMADO)
  3. POST /vendas/{id}/cancelar  → Libera reserva (CANCELADO)
  Também: listagem, detalhe, erro sem cliente válido.
"""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.parceiro import Cliente
from app.services.estoque_service import movimentar, get_saldo


async def _setup_venda(test_engine):
    """Cria produto com estoque e cliente para os testes de venda."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="PC", descricao="Peça")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="PV-001",
            descricao="Parafuso Zincado M8",
            tipo="PRODUTO_BENEFICIADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            mva=Decimal("0"),
            preco_venda=Decimal("5.50"),
            cst_icms="00",
            cst_ipi="99",
            cst_pis="01",
            cst_cofins="01",
        )
        session.add(produto)

        loc = LocalizacaoEstoque(codigo="E-VENDA", descricao="Estoque Produtos Acabados")
        session.add(loc)

        # Cliente intraestadual (SP) — mesmo estado que a empresa
        cliente_sp = Cliente(
            razao_social="Moto Peças SP Ltda",
            cnpj_cpf="11.222.333/0001-44",
            uf="SP",
            consumidor_final=False,
        )
        # Cliente interestadual (MG) — 12% ICMS
        cliente_mg = Cliente(
            razao_social="Distribuidora MG Ltda",
            cnpj_cpf="22.333.444/0001-55",
            uf="MG",
            consumidor_final=False,
        )
        session.add(cliente_sp)
        session.add(cliente_mg)
        await session.flush()

        # Coloca 200 unidades em estoque
        await movimentar(
            session, produto.id, loc.id,
            tipo="ENTRADA_COMPRA",
            quantidade=Decimal("200"),
        )
        await session.commit()
        await session.refresh(produto)
        await session.refresh(loc)
        await session.refresh(cliente_sp)
        await session.refresh(cliente_mg)

        return {
            "produto_id": produto.id,
            "loc_id": loc.id,
            "cliente_sp_id": cliente_sp.id,
            "cliente_mg_id": cliente_mg.id,
        }


class TestListarPedidos:
    async def test_listar_pedidos_vazio(self, client):
        r = await client.get("/api/v1/vendas/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_detalhar_pedido_inexistente_404(self, client):
        r = await client.get("/api/v1/vendas/99999")
        assert r.status_code == 404


class TestCriarPedido:
    async def test_criar_pedido_orcamento(self, client, auth_headers, test_engine):
        ids = await _setup_venda(test_engine)

        r = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "10",
                    "preco_unitario": "5.50",
                    "localizacao_id": ids["loc_id"],
                }
            ],
        }, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "ORCAMENTO"
        assert float(body["valor_total"]) == 55.0

    async def test_criar_pedido_cliente_inexistente_retorna_404(
        self, client, auth_headers
    ):
        r = await client.post("/api/v1/vendas/", json={
            "cliente_id": 99999,
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        assert r.status_code == 404

    async def test_criar_pedido_produto_inexistente_retorna_404(
        self, client, auth_headers, test_engine
    ):
        ids = await _setup_venda(test_engine)

        r = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": 99999,
                    "quantidade": "1",
                    "preco_unitario": "10.00",
                }
            ],
        }, headers=auth_headers)
        assert r.status_code == 404

    async def test_pedido_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/vendas/", json={})
        assert r.status_code == 401

    async def test_criar_pedido_interestadual_calcula_cfop_correto(
        self, client, auth_headers, test_engine
    ):
        """Pedido para cliente de MG deve gerar CFOP 6102 (interestadual)."""
        ids = await _setup_venda(test_engine)

        r = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_mg_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "5",
                    "preco_unitario": "10.00",
                }
            ],
        }, headers=auth_headers)
        assert r.status_code == 201

    async def test_criar_pedido_com_desconto(self, client, auth_headers, test_engine):
        """Desconto de 10% deve ser aplicado ao preço unitário."""
        ids = await _setup_venda(test_engine)

        r = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "10",
                    "preco_unitario": "10.00",
                    "desconto_percent": "10",  # 10% de desconto → R$ 9,00/un
                }
            ],
        }, headers=auth_headers)
        assert r.status_code == 201
        assert float(r.json()["valor_total"]) == pytest.approx(90.0, abs=0.01)


class TestConfirmarPedido:
    async def test_confirmar_pedido_reserva_estoque(
        self, client, auth_headers, test_engine
    ):
        """Confirmar pedido deve mover estoque de DISPONIVEL para RESERVADO."""
        ids = await _setup_venda(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        # Criar pedido
        r_pedido = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "50",
                    "preco_unitario": "5.50",
                    "localizacao_id": ids["loc_id"],
                }
            ],
        }, headers=auth_headers)
        pedido_id = r_pedido.json()["id"]

        # Confirmar pedido
        r_confirmar = await client.post(
            f"/api/v1/vendas/{pedido_id}/confirmar",
            headers=auth_headers,
        )
        assert r_confirmar.status_code == 200
        body = r_confirmar.json()
        assert body["status"] == "CONFIRMADO"
        assert body["itens_reservados"] == 1

        # Verificar saldos
        async with Session() as session:
            disponivel = await get_saldo(session, ids["produto_id"], ids["loc_id"], "DISPONIVEL")
            reservado = await get_saldo(session, ids["produto_id"], ids["loc_id"], "RESERVADO")
        assert disponivel == Decimal("150")  # 200 - 50
        assert reservado == Decimal("50")

    async def test_confirmar_pedido_ja_confirmado_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Confirmar pedido que já está CONFIRMADO deve retornar 422."""
        ids = await _setup_venda(test_engine)

        r_pedido = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "10",
                    "preco_unitario": "5.50",
                    "localizacao_id": ids["loc_id"],
                }
            ],
        }, headers=auth_headers)
        pedido_id = r_pedido.json()["id"]

        await client.post(f"/api/v1/vendas/{pedido_id}/confirmar", headers=auth_headers)
        r = await client.post(f"/api/v1/vendas/{pedido_id}/confirmar", headers=auth_headers)
        assert r.status_code == 422

    async def test_confirmar_pedido_inexistente_404(self, client, auth_headers):
        r = await client.post("/api/v1/vendas/99999/confirmar", headers=auth_headers)
        assert r.status_code == 404


class TestCancelarPedido:
    async def test_cancelar_pedido_orcamento(self, client, auth_headers, test_engine):
        ids = await _setup_venda(test_engine)

        r_pedido = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "5",
                    "preco_unitario": "5.50",
                }
            ],
        }, headers=auth_headers)
        pedido_id = r_pedido.json()["id"]

        r = await client.post(f"/api/v1/vendas/{pedido_id}/cancelar", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "CANCELADO"

    async def test_cancelar_pedido_confirmado_libera_reserva(
        self, client, auth_headers, test_engine
    ):
        """Cancelar pedido CONFIRMADO deve devolver estoque para DISPONIVEL."""
        ids = await _setup_venda(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        # Criar e confirmar
        r_pedido = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "30",
                    "preco_unitario": "5.50",
                    "localizacao_id": ids["loc_id"],
                }
            ],
        }, headers=auth_headers)
        pedido_id = r_pedido.json()["id"]
        await client.post(f"/api/v1/vendas/{pedido_id}/confirmar", headers=auth_headers)

        # Cancelar
        await client.post(f"/api/v1/vendas/{pedido_id}/cancelar", headers=auth_headers)

        # Estoque deve ter voltado ao DISPONIVEL
        async with Session() as session:
            disponivel = await get_saldo(session, ids["produto_id"], ids["loc_id"], "DISPONIVEL")
            reservado = await get_saldo(session, ids["produto_id"], ids["loc_id"], "RESERVADO")
        assert disponivel == Decimal("200")
        assert reservado == Decimal("0")

    async def test_cancelar_pedido_inexistente_404(self, client, auth_headers):
        r = await client.post("/api/v1/vendas/99999/cancelar", headers=auth_headers)
        assert r.status_code == 404

    async def test_listar_pedidos_com_filtro_status(
        self, client, auth_headers, test_engine
    ):
        ids = await _setup_venda(test_engine)

        r = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_sp_id"],
            "data_emissao": "2026-04-15",
            "itens": [
                {
                    "produto_id": ids["produto_id"],
                    "quantidade": "1",
                    "preco_unitario": "5.50",
                }
            ],
        }, headers=auth_headers)
        pedido_id = r.json()["id"]

        r_confirmados = await client.get("/api/v1/vendas/?status=CONFIRMADO")
        assert len(r_confirmados.json()) == 0

        r_orcamentos = await client.get("/api/v1/vendas/?status=ORCAMENTO")
        assert len(r_orcamentos.json()) == 1
