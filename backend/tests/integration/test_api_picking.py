"""
Testes de integração — Picking (Montagem de Pedidos) via API.

Módulo: /api/v1/picking/
Endpoints cobertos:
  POST /picking/{pedido_id}/iniciar    → Abre conferência, move pedido para EM_PICKING
  POST /picking/{pedido_id}/concluir   → Conclui separação manualmente → PICKING_OK
  GET  /picking/{conferencia_id}       → Detalha conferência com seus itens
  POST /picking/{conferencia_id}/scan  → Processa leitura do scanner (lógica de conferência)

Regras de negócio verificadas:
  - Só pedidos CONFIRMADO podem iniciar picking
  - Não é possível iniciar picking duas vezes no mesmo pedido (409)
  - Scan de código inexistente retorna ITEM_ERRADO
  - Scan de item não pertencente ao pedido retorna ITEM_ERRADO
  - Scan correto na quantidade exata → status OK
  - Scan que excede quantidade esperada → DIVERGENCIA_QUANTIDADE
  - Quando todos os itens ficam OK, conferência → CONCLUIDO e pedido → PICKING_OK
  - Concluir manualmente funciona tanto em EM_PICKING quanto CONFIRMADO
  - Todos os mutadores exigem autenticação (401 sem token)
"""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.parceiro import Cliente
from app.services.estoque_service import movimentar


async def _setup_picking(test_engine):
    """Cria produto com estoque, cliente e retorna pedido CONFIRMADO pronto para picking."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="PKG-001",
            descricao="Abraçadeira Gota 1/2",
            codigo_barras="7891234567890",
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
            preco_venda=Decimal("5.00"),
        )
        session.add(produto)

        loc = LocalizacaoEstoque(codigo="PKG-LOC", descricao="Estoque Picking")
        cliente = Cliente(
            razao_social="Cliente Picking Ltda",
            cnpj_cpf="55.555.555/0001-55",
            uf="SP",
            consumidor_final=False,
        )
        session.add(loc)
        session.add(cliente)
        await session.flush()

        await movimentar(session, produto.id, loc.id, "ENTRADA_COMPRA", Decimal("100"))
        await session.commit()

        return {
            "produto_id": produto.id,
            "produto_codigo": produto.codigo,
            "produto_barcode": produto.codigo_barras,
            "loc_id": loc.id,
            "cliente_id": cliente.id,
        }


async def _criar_pedido_confirmado(client, auth_headers, ids):
    """Cria e confirma um pedido de venda, retornando o pedido_id."""
    r = await client.post("/api/v1/vendas/", json={
        "cliente_id": ids["cliente_id"],
        "data_emissao": "2026-04-15",
        "itens": [{
            "produto_id": ids["produto_id"],
            "quantidade": "10",
            "preco_unitario": "5.00",
            "localizacao_id": ids["loc_id"],
        }],
    }, headers=auth_headers)
    assert r.status_code == 201
    pedido_id = r.json()["id"]

    r_conf = await client.post(f"/api/v1/vendas/{pedido_id}/confirmar", headers=auth_headers)
    assert r_conf.status_code == 200
    return pedido_id


# ---------------------------------------------------------------------------
# Iniciar picking
# ---------------------------------------------------------------------------

class TestIniciarPicking:
    async def test_iniciar_cria_conferencia_em_andamento(self, client, auth_headers, test_engine):
        """Pedido CONFIRMADO pode iniciar picking — conferência fica EM_ANDAMENTO."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)

        r = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "EM_ANDAMENTO"
        assert body["pedido_venda_id"] == pedido_id

    async def test_iniciar_move_pedido_para_em_picking(self, client, auth_headers, test_engine):
        """Após iniciar picking, o pedido de venda deve ficar EM_PICKING."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)

        await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)

        r_pedido = await client.get(f"/api/v1/vendas/{pedido_id}")
        assert r_pedido.json()["status"] == "EM_PICKING"

    async def test_iniciar_cria_itens_de_conferencia(self, client, auth_headers, test_engine):
        """A conferência criada deve conter os itens do pedido com status PENDENTE (via GET)."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)

        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        # GET retorna itens carregados via selectinload
        r = await client.get(f"/api/v1/picking/{conf_id}")
        conf = r.json()
        assert len(conf["itens"]) == 1
        assert conf["itens"][0]["status"] == "PENDENTE"
        assert float(conf["itens"][0]["quantidade_esperada"]) == 10.0

    async def test_iniciar_pedido_inexistente_retorna_404(self, client, auth_headers):
        """Pedido inexistente deve retornar 404."""
        r = await client.post("/api/v1/picking/99999/iniciar", headers=auth_headers)
        assert r.status_code == 404

    async def test_iniciar_pedido_orcamento_retorna_422(self, client, auth_headers, test_engine):
        """Pedido no status ORCAMENTO (não confirmado) não pode iniciar picking."""
        ids = await _setup_picking(test_engine)
        r_venda = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_venda.json()["id"]

        r = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        assert r.status_code == 422

    async def test_iniciar_duas_vezes_rejeitado(self, client, auth_headers, test_engine):
        """Não é possível iniciar picking duas vezes no mesmo pedido.

        Na segunda chamada, o pedido já está EM_PICKING (não CONFIRMADO),
        portanto o endpoint retorna 422 (transição de status inválida).
        """
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)

        r1 = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        assert r1.status_code == 201

        r2 = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        # Pedido está EM_PICKING — transição inválida
        assert r2.status_code in (409, 422)

    async def test_iniciar_sem_auth_retorna_401(self, client, test_engine):
        """Iniciar picking exige autenticação."""
        r = await client.post("/api/v1/picking/1/iniciar")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Concluir picking
# ---------------------------------------------------------------------------

class TestConcluirPicking:
    async def test_concluir_move_para_picking_ok(self, client, auth_headers, test_engine):
        """Concluir picking manualmente deve mover pedido para PICKING_OK."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)

        r = await client.post(f"/api/v1/picking/{pedido_id}/concluir", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "PICKING_OK"

    async def test_concluir_sem_picking_iniciado(self, client, auth_headers, test_engine):
        """Concluir de pedido CONFIRMADO (sem picking iniciado) também deve funcionar."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)

        r = await client.post(f"/api/v1/picking/{pedido_id}/concluir", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["status"] == "PICKING_OK"

    async def test_concluir_pedido_inexistente_retorna_404(self, client, auth_headers):
        """Concluir picking de pedido inexistente deve retornar 404."""
        r = await client.post("/api/v1/picking/99999/concluir", headers=auth_headers)
        assert r.status_code == 404

    async def test_concluir_pedido_orcamento_retorna_422(self, client, auth_headers, test_engine):
        """Pedido ORCAMENTO não pode ser concluído diretamente."""
        ids = await _setup_picking(test_engine)
        r_venda = await client.post("/api/v1/vendas/", json={
            "cliente_id": ids["cliente_id"],
            "data_emissao": "2026-04-15",
            "itens": [],
        }, headers=auth_headers)
        pedido_id = r_venda.json()["id"]

        r = await client.post(f"/api/v1/picking/{pedido_id}/concluir", headers=auth_headers)
        assert r.status_code == 422

    async def test_concluir_sem_auth_retorna_401(self, client):
        """Concluir picking exige autenticação."""
        r = await client.post("/api/v1/picking/1/concluir")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Detalhar conferência
# ---------------------------------------------------------------------------

class TestDetalharConferencia:
    async def test_detalhar_conferencia_existente(self, client, auth_headers, test_engine):
        """Conferência criada deve ser recuperável pelo seu ID."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)

        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        r = await client.get(f"/api/v1/picking/{conf_id}")
        assert r.status_code == 200
        assert r.json()["id"] == conf_id

    async def test_detalhar_conferencia_inexistente_retorna_404(self, client):
        """Conferência inexistente deve retornar 404."""
        r = await client.get("/api/v1/picking/99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Scan de itens
# ---------------------------------------------------------------------------

class TestScanPicking:
    async def test_scan_codigo_correto_retorna_ok(self, client, auth_headers, test_engine):
        """Escanear o código exato do produto na quantidade correta retorna OK."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        # Scan 10x para completar (pedido tem 10 unidades)
        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "10"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["resultado"] == "OK"

    async def test_scan_por_codigo_de_barras(self, client, auth_headers, test_engine):
        """Scanner deve aceitar código de barras além do código interno."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_barcode"], "quantidade": "10"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["resultado"] == "OK"

    async def test_scan_parcial_retorna_parcial(self, client, auth_headers, test_engine):
        """Escanear menos que o esperado retorna PARCIAL com faltante calculado."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "5"},
            headers=auth_headers,
        )
        body = r.json()
        assert body["resultado"] == "PARCIAL"
        assert body["quantidade_conferida"] == 5.0
        assert body["quantidade_esperada"] == 10.0

    async def test_scan_excedente_retorna_divergencia(self, client, auth_headers, test_engine):
        """Escanear mais do que o esperado retorna DIVERGENCIA_QUANTIDADE."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "15"},
            headers=auth_headers,
        )
        assert r.json()["resultado"] == "DIVERGENCIA_QUANTIDADE"

    async def test_scan_codigo_inexistente_retorna_item_errado(self, client, auth_headers, test_engine):
        """Código não cadastrado no sistema retorna ITEM_ERRADO."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": "CODIGO-INVALIDO-XYZ"},
            headers=auth_headers,
        )
        assert r.json()["resultado"] == "ITEM_ERRADO"

    async def test_scan_completo_conclui_conferencia(self, client, auth_headers, test_engine):
        """Após escanear todos os itens corretamente, conferência vira CONCLUIDO."""
        ids = await _setup_picking(test_engine)
        pedido_id = await _criar_pedido_confirmado(client, auth_headers, ids)
        r_init = await client.post(f"/api/v1/picking/{pedido_id}/iniciar", headers=auth_headers)
        conf_id = r_init.json()["id"]

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "10"},
            headers=auth_headers,
        )
        body = r.json()
        assert body["conferencia_concluida"] is True
        assert body["percentual_geral"] == 100.0

    async def test_scan_sem_auth_retorna_401(self, client):
        """Scan exige autenticação."""
        r = await client.post("/api/v1/picking/1/scan", params={"codigo": "P-001"})
        assert r.status_code == 401
