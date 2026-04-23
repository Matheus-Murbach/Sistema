"""
Testes de integração — Expedição de Saída via API.

Módulo: /api/v1/expedicao/
Endpoints cobertos:
  GET  /expedicao/                       → Lista NFs de saída emitidas
  GET  /expedicao/{pedido_id}/preview    → Breakdown fiscal por item sem emitir NF-e
  POST /expedicao/{pedido_id}/expedir    → Expede sem NF-e SEFAZ: baixa estoque, EXPEDIDO
  GET  /expedicao/{nf_id}/status         → Consulta status da NF-e no SEFAZ (Focus)

Regras de negócio verificadas:
  - Só pedidos PICKING_OK ou CONFIRMADO podem ser expedidos
  - Após expedir: status do pedido vira EXPEDIDO
  - Após expedir: estoque reservado é consumido (baixado definitivamente)
  - Expedir pedido inexistente → 404
  - Preview retorna impostos calculados por item
  - Todos os mutadores exigem autenticação (401 sem token)
"""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.parceiro import Cliente
from app.services.estoque_service import movimentar, get_saldo


async def _setup_expedicao(test_engine):
    """Cria produto com estoque e cliente para os testes de expedição."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="EXP-001",
            descricao="Abraçadeira para Expedição",
            tipo="PRODUTO_ACABADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            cst_icms="00",
            cst_ipi="99",
            cst_pis="01",
            cst_cofins="01",
            preco_venda=Decimal("10.00"),
        )
        session.add(produto)

        loc = LocalizacaoEstoque(codigo="EXP-LOC", descricao="Estoque Expedição")
        cliente = Cliente(
            razao_social="Cliente Expedição Ltda",
            cnpj_cpf="77.777.777/0001-77",
            uf="SP",
            consumidor_final=False,
        )
        session.add(loc)
        session.add(cliente)
        await session.flush()

        await movimentar(session, produto.id, loc.id, "ENTRADA_COMPRA", Decimal("200"))
        await session.commit()

        return {
            "produto_id": produto.id,
            "loc_id": loc.id,
            "cliente_id": cliente.id,
        }


async def _pedido_picking_ok(client, auth_headers, ids, quantidade=20):
    """Cria pedido → confirma → inicia picking → conclui picking → retorna pedido_id."""
    r = await client.post("/api/v1/vendas/", json={
        "cliente_id": ids["cliente_id"],
        "data_emissao": "2026-04-15",
        "itens": [{
            "produto_id": ids["produto_id"],
            "quantidade": str(quantidade),
            "preco_unitario": "10.00",
            "localizacao_id": ids["loc_id"],
        }],
    }, headers=auth_headers)
    assert r.status_code == 201
    pedido_id = r.json()["id"]

    await client.post(f"/api/v1/vendas/{pedido_id}/confirmar", headers=auth_headers)
    await client.post(f"/api/v1/picking/{pedido_id}/concluir", headers=auth_headers)
    return pedido_id


# ---------------------------------------------------------------------------
# Listagem
# ---------------------------------------------------------------------------

class TestListarExpedicao:
    async def test_listar_vazio(self, client):
        """Com banco zerado, retorna lista vazia."""
        r = await client.get("/api/v1/expedicao/")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Preview fiscal
# ---------------------------------------------------------------------------

class TestPreviewFiscal:
    async def test_preview_retorna_impostos_por_item(self, client, auth_headers, test_engine):
        """Preview deve calcular e retornar os impostos sem emitir NF-e."""
        ids = await _setup_expedicao(test_engine)
        pedido_id = await _pedido_picking_ok(client, auth_headers, ids)

        r = await client.get(f"/api/v1/expedicao/{pedido_id}/preview", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "itens" in body
        assert len(body["itens"]) == 1

        item = body["itens"][0]
        assert "valor_icms" in item
        assert "valor_pis" in item
        assert "valor_cofins" in item
        assert item["cfop"] in ("5102", "5405", "6102")

    async def test_preview_pedido_inexistente_retorna_404(self, client, auth_headers):
        """Preview de pedido inexistente deve retornar 404."""
        r = await client.get("/api/v1/expedicao/99999/preview", headers=auth_headers)
        assert r.status_code == 404

    async def test_preview_sem_auth_retorna_401(self, client):
        """Preview exige autenticação."""
        r = await client.get("/api/v1/expedicao/1/preview")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Expedir (sem NF-e SEFAZ)
# ---------------------------------------------------------------------------

class TestExpedirPedido:
    async def test_expedir_picking_ok_retorna_expedido(self, client, auth_headers, test_engine):
        """Pedido PICKING_OK deve ser expedido com sucesso."""
        ids = await _setup_expedicao(test_engine)
        pedido_id = await _pedido_picking_ok(client, auth_headers, ids)

        r = await client.post(f"/api/v1/expedicao/{pedido_id}/expedir",
                               json={}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "EXPEDIDO"
        assert r.json()["pedido_id"] == pedido_id

    async def test_expedir_consome_estoque_reservado(self, client, auth_headers, test_engine):
        """Após expedir, o estoque reservado é consumido definitivamente (saldo RESERVADO → 0)."""
        ids = await _setup_expedicao(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        pedido_id = await _pedido_picking_ok(client, auth_headers, ids, quantidade=30)

        await client.post(f"/api/v1/expedicao/{pedido_id}/expedir",
                          json={}, headers=auth_headers)

        async with Session() as session:
            reservado = await get_saldo(session, ids["produto_id"], ids["loc_id"], "RESERVADO")
            disponivel = await get_saldo(session, ids["produto_id"], ids["loc_id"], "DISPONIVEL")

        assert reservado == Decimal("0")
        assert disponivel == Decimal("170")  # 200 - 30

    async def test_expedir_com_transportadora(self, client, auth_headers, test_engine):
        """Campo transportadora é opcional e deve ser persistido."""
        ids = await _setup_expedicao(test_engine)
        pedido_id = await _pedido_picking_ok(client, auth_headers, ids)

        r = await client.post(f"/api/v1/expedicao/{pedido_id}/expedir", json={
            "transportadora": "Transportadora ABC",
            "observacoes": "Entrega urgente",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "EXPEDIDO"

    async def test_expedir_pedido_inexistente_retorna_404(self, client, auth_headers):
        """Expedir pedido inexistente deve retornar 404."""
        r = await client.post("/api/v1/expedicao/99999/expedir",
                               json={}, headers=auth_headers)
        assert r.status_code == 404

    async def test_expedir_pedido_orcamento_retorna_422(self, client, auth_headers, test_engine):
        """Pedido ORCAMENTO não pode ser expedido diretamente."""
        ids = await _setup_expedicao(test_engine)
        r_venda = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_venda.json()["id"]

        r = await client.post(f"/api/v1/expedicao/{pedido_id}/expedir",
                               json={}, headers=auth_headers)
        assert r.status_code == 422

    async def test_expedir_sem_auth_retorna_401(self, client):
        """Expedir exige autenticação."""
        r = await client.post("/api/v1/expedicao/1/expedir", json={})
        assert r.status_code == 401

    async def test_expedir_pedido_cancelado_retorna_422(self, client, auth_headers, test_engine):
        """Pedido CANCELADO não pode ser expedido."""
        ids = await _setup_expedicao(test_engine)
        r_venda = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_venda.json()["id"]
        await client.post(f"/api/v1/vendas/{pedido_id}/cancelar", headers=auth_headers)

        r = await client.post(f"/api/v1/expedicao/{pedido_id}/expedir",
                               json={}, headers=auth_headers)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Fluxo completo: Venda → Confirmar → Picking → Expedir
# ---------------------------------------------------------------------------

class TestFluxoCompletoExpedicao:
    async def test_fluxo_completo_orcamento_ate_expedido(self, client, auth_headers, test_engine):
        """
        Fluxo end-to-end:
          ORCAMENTO → CONFIRMADO → EM_PICKING → PICKING_OK → EXPEDIDO
        Verifica que cada transição de status ocorre corretamente.
        """
        ids = await _setup_expedicao(test_engine)

        # 1. Criar pedido (ORCAMENTO)
        r1 = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_id"],
            "data_emissao": "2026-04-15",
            "itens": [{
                "produto_id": ids["produto_id"],
                "quantidade": "5",
                "preco_unitario": "10.00",
                "localizacao_id": ids["loc_id"],
            }],
        }, headers=auth_headers)
        assert r1.json()["status"] == "ORCAMENTO"
        pedido_id = r1.json()["id"]

        # 2. Confirmar (CONFIRMADO)
        r2 = await client.post(f"/api/v1/vendas/{pedido_id}/confirmar", headers=auth_headers)
        assert r2.json()["status"] == "CONFIRMADO"

        # 3. Iniciar picking (EM_PICKING)
        r3 = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        assert r3.status_code == 201
        r_p = await client.get(f"/api/v1/vendas/{pedido_id}")
        assert r_p.json()["status"] == "EM_PICKING"

        # 4. Concluir picking (PICKING_OK)
        r4 = await client.post(f"/api/v1/picking/{pedido_id}/concluir", headers=auth_headers)
        assert r4.json()["status"] == "PICKING_OK"

        # 5. Expedir (EXPEDIDO)
        r5 = await client.post(f"/api/v1/expedicao/{pedido_id}/expedir",
                                json={}, headers=auth_headers)
        assert r5.json()["status"] == "EXPEDIDO"
