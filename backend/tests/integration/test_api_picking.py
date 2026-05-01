"""
Testes de integração — Picking (Conferência de Pedidos) via API.

Cobre os endpoints:
  - POST /picking/{pedido_id}/iniciar    → cria conferência para pedido CONFIRMADO
  - POST /picking/{pedido_id}/concluir   → conclui picking manualmente → PICKING_OK
  - GET  /picking/{conferencia_id}       → detalha conferência com itens
  - POST /picking/{conferencia_id}/scan  → processa leitura do scanner

WebSocket (/{conferencia_id}/ws) não é testado aqui — complexidade de
simulação de cliente WS não justifica neste momento.
"""
import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.models.parceiro import Cliente
from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.venda import PedidoVenda, ItemPedidoVenda
from app.services.estoque_service import movimentar, reservar_estoque
from app.models.picking import ConferencePicking


async def _setup_picking(test_engine):
    """
    Cria cadeia completa: produto → cliente → estoque reservado → pedido CONFIRMADO.
    Retorna IDs para uso nos testes.
    """
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="PICK-001",
            descricao="Parafuso M8 Zincado",
            tipo="PRODUTO_BENEFICIADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            codigo_barras="7890000001234",
        )
        session.add(produto)

        cliente = Cliente(
            razao_social="Cliente Picking Ltda",
            cnpj_cpf="22.333.444/0001-55",
            uf="SP",
        )
        session.add(cliente)

        loc = LocalizacaoEstoque(codigo="PK-01", descricao="Estoque Picking")
        session.add(loc)
        await session.flush()

        # Estoque inicial: 200 unidades
        await movimentar(session, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("200"))
        await session.flush()

        # Pedido CONFIRMADO com 5 unidades reservadas
        pedido = PedidoVenda(
            numero="PV-PICK-001",
            cliente_id=cliente.id,
            status="CONFIRMADO",
            data_emissao=date.today(),
            valor_frete=Decimal("0"),
        )
        session.add(pedido)
        await session.flush()

        item = ItemPedidoVenda(
            pedido_id=pedido.id,
            produto_id=produto.id,
            quantidade=Decimal("5"),
            preco_unitario=Decimal("10.00"),
            valor_total=Decimal("50.00"),
        )
        session.add(item)
        await session.flush()

        await reservar_estoque(session, produto.id, loc.id, Decimal("5"), pedido.id)
        await session.commit()

        await session.refresh(pedido)
        await session.refresh(produto)
        await session.refresh(loc)

        return {
            "pedido_id": pedido.id,
            "produto_id": produto.id,
            "produto_codigo": produto.codigo,
            "produto_codigo_barras": produto.codigo_barras,
            "loc_id": loc.id,
        }


# ---------------------------------------------------------------------------
# Iniciar Picking
# ---------------------------------------------------------------------------

class TestIniciarPicking:
    async def test_iniciar_pedido_confirmado(self, client, auth_headers, test_engine):
        """Pedido CONFIRMADO → conferência criada + pedido vira EM_PICKING."""
        ids = await _setup_picking(test_engine)

        r = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )
        assert r.status_code == 201
        body = r.json()
        assert body["pedido_venda_id"] == ids["pedido_id"]
        assert body["status"] == "EM_ANDAMENTO"
        assert "id" in body

    async def test_iniciar_muda_status_pedido_para_em_picking(
        self, client, auth_headers, test_engine
    ):
        ids = await _setup_picking(test_engine)

        await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )

        # Verifica diretamente no banco
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            r = await session.execute(
                select(PedidoVenda).where(PedidoVenda.id == ids["pedido_id"])
            )
            pedido = r.scalar_one()
        assert pedido.status == "EM_PICKING"

    async def test_iniciar_pedido_ja_em_picking_retorna_erro(
        self, client, auth_headers, test_engine
    ):
        """Após iniciar, pedido vira EM_PICKING; nova tentativa deve falhar (422)."""
        ids = await _setup_picking(test_engine)

        await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )
        r = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )
        # Pedido está EM_PICKING, que não é CONFIRMADO → 422
        assert r.status_code in (409, 422)

    async def test_iniciar_pedido_com_status_errado_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Pedido em ORCAMENTO não pode iniciar picking."""
        ids = await _setup_picking(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            r = await session.execute(
                select(PedidoVenda).where(PedidoVenda.id == ids["pedido_id"])
            )
            pedido = r.scalar_one()
            pedido.status = "ORCAMENTO"
            await session.commit()

        r = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_iniciar_pedido_inexistente_retorna_404(self, client, auth_headers):
        r = await client.post("/api/v1/picking/99999/iniciar", headers=auth_headers)
        assert r.status_code == 404

    async def test_iniciar_sem_auth_retorna_401(self, client, test_engine):
        ids = await _setup_picking(test_engine)
        r = await client.post(f"/api/v1/picking/{ids['pedido_id']}/iniciar")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Detalhar Conferência
# ---------------------------------------------------------------------------

class TestDetalharConferencia:
    async def test_detalhar_conferencia_existente(self, client, auth_headers, test_engine):
        ids = await _setup_picking(test_engine)

        r_init = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )
        conf_id = r_init.json()["id"]

        r = await client.get(f"/api/v1/picking/{conf_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == conf_id
        assert "itens" in body
        assert len(body["itens"]) == 1

    async def test_detalhar_conferencia_inexistente_retorna_404(self, client):
        r = await client.get("/api/v1/picking/99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Scan de Itens
# ---------------------------------------------------------------------------

class TestRegistrarScan:
    async def _iniciar(self, client, auth_headers, ids):
        r = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )
        assert r.status_code == 201
        return r.json()["id"]

    async def test_scan_quantidade_correta_retorna_ok(self, client, auth_headers, test_engine):
        """Escanear exatamente a quantidade esperada → resultado OK."""
        ids = await _setup_picking(test_engine)
        conf_id = await self._iniciar(client, auth_headers, ids)

        # A quantidade esperada é 5, escaneia 5 de uma vez
        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "5"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["resultado"] == "OK"
        assert float(body["quantidade_conferida"]) == 5.0

    async def test_scan_quantidade_parcial_retorna_parcial(
        self, client, auth_headers, test_engine
    ):
        """Escanear menos que o esperado → resultado PARCIAL."""
        ids = await _setup_picking(test_engine)
        conf_id = await self._iniciar(client, auth_headers, ids)

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "2"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["resultado"] == "PARCIAL"

    async def test_scan_quantidade_excedida_retorna_divergencia(
        self, client, auth_headers, test_engine
    ):
        """Escanear mais que o esperado → DIVERGENCIA_QUANTIDADE."""
        ids = await _setup_picking(test_engine)
        conf_id = await self._iniciar(client, auth_headers, ids)

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "99"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["resultado"] == "DIVERGENCIA_QUANTIDADE"

    async def test_scan_codigo_desconhecido_retorna_item_errado(
        self, client, auth_headers, test_engine
    ):
        """Código não existente no sistema → ITEM_ERRADO."""
        ids = await _setup_picking(test_engine)
        conf_id = await self._iniciar(client, auth_headers, ids)

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": "CODIGO-INVALIDO-XYZ", "quantidade": "1"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["resultado"] == "ITEM_ERRADO"

    async def test_scan_via_codigo_barras(self, client, auth_headers, test_engine):
        """Scan pelo código de barras também deve funcionar."""
        ids = await _setup_picking(test_engine)
        conf_id = await self._iniciar(client, auth_headers, ids)

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo_barras"], "quantidade": "5"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["resultado"] == "OK"

    async def test_scan_completo_conclui_conferencia_automaticamente(
        self, client, auth_headers, test_engine
    ):
        """Quando todos os itens ficam OK, a conferência deve virar CONCLUIDO."""
        ids = await _setup_picking(test_engine)
        conf_id = await self._iniciar(client, auth_headers, ids)

        r = await client.post(
            f"/api/v1/picking/{conf_id}/scan",
            params={"codigo": ids["produto_codigo"], "quantidade": "5"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["conferencia_concluida"] is True
        assert float(body["percentual_geral"]) == 100.0

    async def test_scan_sem_auth_retorna_401(self, client, test_engine):
        ids = await _setup_picking(test_engine)
        r = await client.post(
            f"/api/v1/picking/1/scan",
            params={"codigo": "PROD-001", "quantidade": "1"},
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Concluir Picking Manualmente
# ---------------------------------------------------------------------------

class TestConcluirPicking:
    async def test_concluir_picking_muda_status_para_picking_ok(
        self, client, auth_headers, test_engine
    ):
        ids = await _setup_picking(test_engine)

        # Inicia picking
        await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/iniciar",
            headers=auth_headers,
        )

        r = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/concluir",
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "PICKING_OK"

    async def test_concluir_pedido_status_invalido_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Pedido já expedido não pode ser concluído novamente."""
        ids = await _setup_picking(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            r = await session.execute(
                select(PedidoVenda).where(PedidoVenda.id == ids["pedido_id"])
            )
            pedido = r.scalar_one()
            pedido.status = "EXPEDIDO"
            await session.commit()

        r = await client.post(
            f"/api/v1/picking/{ids['pedido_id']}/concluir",
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_concluir_pedido_inexistente_retorna_404(self, client, auth_headers):
        r = await client.post("/api/v1/picking/99999/concluir", headers=auth_headers)
        assert r.status_code == 404

    async def test_concluir_sem_auth_retorna_401(self, client, test_engine):
        ids = await _setup_picking(test_engine)
        r = await client.post(f"/api/v1/picking/{ids['pedido_id']}/concluir")
        assert r.status_code == 401
