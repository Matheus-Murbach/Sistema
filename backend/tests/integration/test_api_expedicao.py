"""
Testes de integração — Expedição de Saída (NF-e) via API.

Cobre os endpoints:
  - GET /expedicao/                      → lista NF-e de saída
  - GET /expedicao/{pedido_id}/preview   → preview fiscal por item (sem emitir)
  - POST /expedicao/{pedido_id}/emitir   → transmite NF-e ao SEFAZ (mock Focus)
  - POST /expedicao/{pedido_id}/expedir  → expede sem NF-e (baixa direta de estoque)
  - GET /expedicao/{nf_id}/status        → consulta status no SEFAZ (mock Focus)
  - GET /expedicao/{nf_id}/danfe         → download PDF DANFE (mock Focus)

Estratégia de mock: patch("app.api.v1.expedicao.focus_nfe") isola completamente
o Focus NF-e sem precisar de credenciais ou rede.
"""
import pytest
from decimal import Decimal
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.parceiro import Cliente
from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.venda import PedidoVenda, ItemPedidoVenda
from app.services.estoque_service import movimentar, reservar_estoque


async def _setup_expedicao(test_engine):
    """
    Cria a cadeia completa para teste de expedição:
    UnidadeMedida → Produto → Cliente → LocalizacaoEstoque → estoque → PedidoVenda CONFIRMADO.
    """
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="PC", descricao="Peça")
        session.add(un)
        await session.flush()

        produto = Produto(
            codigo="EXP-001",
            descricao="Parafuso Zincado M10",
            tipo="PRODUTO_BENEFICIADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            mva=Decimal("0"),
            preco_venda=Decimal("8.00"),
            cst_icms="00",
            cst_ipi="99",
            cst_pis="01",
            cst_cofins="01",
            ncm="73181500",
        )
        session.add(produto)

        # Cliente intraestadual (SP) — mesmo estado da empresa nos testes (EMPRESA_UF=SP)
        cliente = Cliente(
            razao_social="Distribuidora SP Ltda",
            cnpj_cpf="11.222.333/0001-44",
            uf="SP",
            consumidor_final=False,
            logradouro="Rua das Indústrias",
            numero="100",
            bairro="Centro",
            municipio="São Paulo",
            cep="01310-100",
        )
        session.add(cliente)

        loc = LocalizacaoEstoque(codigo="EXP-EST", descricao="Estoque Expedição")
        session.add(loc)
        await session.flush()

        # Coloca 500 unidades em estoque
        await movimentar(session, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("500"))
        await session.flush()

        # Cria pedido CONFIRMADO com reserva de estoque
        pedido = PedidoVenda(
            numero="PV-EXP-001",
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
            quantidade=Decimal("10"),
            preco_unitario=Decimal("8.00"),
            valor_total=Decimal("80.00"),
        )
        session.add(item)
        await session.flush()

        # Reserva estoque
        await reservar_estoque(session, produto.id, loc.id, Decimal("10"), pedido.id)
        await session.commit()

        await session.refresh(pedido)
        await session.refresh(produto)
        await session.refresh(cliente)
        await session.refresh(loc)

        return {
            "pedido_id": pedido.id,
            "produto_id": produto.id,
            "cliente_id": cliente.id,
            "loc_id": loc.id,
        }


# ---------------------------------------------------------------------------
# Listagem de NF-e
# ---------------------------------------------------------------------------

class TestListarNFsSaida:
    async def test_listar_vazio(self, client):
        r = await client.get("/api/v1/expedicao/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_listar_com_filtro_status_vazio(self, client):
        r = await client.get("/api/v1/expedicao/?status=AUTORIZADA")
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------------------
# Preview Fiscal
# ---------------------------------------------------------------------------

class TestPreviewFiscal:
    async def test_preview_retorna_itens_e_totais(self, client, auth_headers, test_engine):
        ids = await _setup_expedicao(test_engine)

        r = await client.get(
            f"/api/v1/expedicao/{ids['pedido_id']}/preview",
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["pedido_id"] == ids["pedido_id"]
        assert "itens" in body
        assert len(body["itens"]) == 1
        assert "totais" in body
        # Produto SP→SP com 12% ICMS, sem IPI: ICMS = 80 × 12% = 9.60
        assert body["totais"]["icms"] == pytest.approx(9.60, abs=0.01)
        assert body["totais"]["ipi"] == 0.0

    async def test_preview_pedido_inexistente_retorna_404(self, client, auth_headers):
        r = await client.get("/api/v1/expedicao/99999/preview", headers=auth_headers)
        assert r.status_code == 404

    async def test_preview_sem_auth_retorna_401(self, client, test_engine):
        ids = await _setup_expedicao(test_engine)
        r = await client.get(f"/api/v1/expedicao/{ids['pedido_id']}/preview")
        assert r.status_code == 401

    async def test_preview_cfop_intraestadual(self, client, auth_headers, test_engine):
        """Cliente SP e empresa SP → CFOP 5102."""
        ids = await _setup_expedicao(test_engine)
        r = await client.get(
            f"/api/v1/expedicao/{ids['pedido_id']}/preview",
            headers=auth_headers,
        )
        assert r.status_code == 200
        item = r.json()["itens"][0]
        assert item["cfop"] == "5102"


# ---------------------------------------------------------------------------
# Emissão de NF-e (com mock do Focus)
# ---------------------------------------------------------------------------

_BG_NOOP = "app.api.v1.expedicao._verificar_e_baixar_estoque"


class TestEmitirNFe:
    async def test_emitir_focus_aceita_retorna_aguardando(
        self, client, auth_headers, test_engine
    ):
        """Focus retorna 200 → NF criada com status AGUARDANDO."""
        ids = await _setup_expedicao(test_engine)

        mock_focus = AsyncMock()
        mock_focus.emitir_nfe.return_value = {"status_code": 200, "data": {"status": "processando"}}

        # A background task é substituída por um no-op — testada separadamente em test_nfe_tasks.py
        with patch("app.api.v1.expedicao.focus_nfe", mock_focus), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )

        assert r.status_code == 201
        body = r.json()
        assert body["status_sefaz"] == "AGUARDANDO"
        assert "focus_referencia" in body
        assert body["focus_referencia"].startswith("NF-")

    async def test_emitir_focus_rejeita_retorna_rejeitada(
        self, client, auth_headers, test_engine
    ):
        """Focus retorna 422 → NF criada com status REJEITADA."""
        ids = await _setup_expedicao(test_engine)

        mock_focus = AsyncMock()
        mock_focus.emitir_nfe.return_value = {
            "status_code": 422,
            "data": {"erros": [{"codigo": "539", "mensagem": "CNPJ inválido"}]},
        }

        with patch("app.api.v1.expedicao.focus_nfe", mock_focus), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )

        assert r.status_code == 201
        body = r.json()
        assert body["status_sefaz"] == "REJEITADA"

    async def test_emitir_pedido_inexistente_retorna_404(self, client, auth_headers):
        r = await client.post("/api/v1/expedicao/99999/emitir", headers=auth_headers)
        assert r.status_code == 404

    async def test_emitir_pedido_status_invalido_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Pedido em status ORCAMENTO não pode ser expedido."""
        ids = await _setup_expedicao(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        # Muda o pedido para ORCAMENTO antes do teste
        async with Session() as session:
            from sqlalchemy import select
            from app.models.venda import PedidoVenda as PV
            r = await session.execute(select(PV).where(PV.id == ids["pedido_id"]))
            pedido = r.scalar_one()
            pedido.status = "ORCAMENTO"
            await session.commit()

        mock_focus = AsyncMock()
        with patch("app.api.v1.expedicao.focus_nfe", mock_focus), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )
        assert r.status_code == 422

    async def test_emitir_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/expedicao/1/emitir")
        assert r.status_code == 401

    async def test_emitir_retorna_resumo_fiscal(self, client, auth_headers, test_engine):
        """Resposta deve incluir breakdown dos totais de impostos."""
        ids = await _setup_expedicao(test_engine)

        mock_focus = AsyncMock()
        mock_focus.emitir_nfe.return_value = {"status_code": 201, "data": {}}

        with patch("app.api.v1.expedicao.focus_nfe", mock_focus), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )

        assert r.status_code == 201
        body = r.json()
        assert "resumo_fiscal" in body
        resumo = body["resumo_fiscal"]
        assert "icms" in resumo
        assert "ipi" in resumo
        assert "pis" in resumo
        assert "cofins" in resumo


# ---------------------------------------------------------------------------
# Expedir sem NF-e
# ---------------------------------------------------------------------------

class TestExpedirSemNFe:
    async def test_expedir_muda_status_para_expedido(
        self, client, auth_headers, test_engine
    ):
        ids = await _setup_expedicao(test_engine)

        r = await client.post(
            f"/api/v1/expedicao/{ids['pedido_id']}/expedir",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "EXPEDIDO"
        assert body["pedido_id"] == ids["pedido_id"]

    async def test_expedir_com_transportadora(self, client, auth_headers, test_engine):
        ids = await _setup_expedicao(test_engine)

        r = await client.post(
            f"/api/v1/expedicao/{ids['pedido_id']}/expedir",
            json={"transportadora": "Transportes Rápidos Ltda"},
            headers=auth_headers,
        )
        assert r.status_code == 200

    async def test_expedir_pedido_inexistente_retorna_404(self, client, auth_headers):
        r = await client.post(
            "/api/v1/expedicao/99999/expedir",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 404

    async def test_expedir_pedido_status_invalido_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Pedido em ORCAMENTO não pode ser expedido."""
        ids = await _setup_expedicao(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            from sqlalchemy import select
            from app.models.venda import PedidoVenda as PV
            r = await session.execute(select(PV).where(PV.id == ids["pedido_id"]))
            pedido = r.scalar_one()
            pedido.status = "ORCAMENTO"
            await session.commit()

        r = await client.post(
            f"/api/v1/expedicao/{ids['pedido_id']}/expedir",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 422

    async def test_expedir_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/expedicao/1/expedir", json={})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Consultar Status da NF-e
# ---------------------------------------------------------------------------

class TestStatusNFe:
    async def _emitir_nf(self, client, auth_headers, ids):
        """Helper: emite uma NF com Focus mockado e retorna o nf_id."""
        mock_focus = AsyncMock()
        mock_focus.emitir_nfe.return_value = {"status_code": 200, "data": {}}
        with patch("app.api.v1.expedicao.focus_nfe", mock_focus), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )
        assert r.status_code == 201
        return r.json()["nf_id"]

    async def test_status_autorizado_atualiza_nf(self, client, auth_headers, test_engine):
        """Focus retorna 'autorizado' → NF deve virar AUTORIZADA com chave e número."""
        ids = await _setup_expedicao(test_engine)
        nf_id = await self._emitir_nf(client, auth_headers, ids)

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "status_code": 200,
            "data": {
                "status": "autorizado",
                "numero_nfe": "123456",
                "chave_nfe": "35240412345678000199550010000000011234567890",
                "numero_protocolo": "135240000000123",
            },
        }

        with patch("app.api.v1.expedicao.focus_nfe", mock_focus):
            r = await client.get(
                f"/api/v1/expedicao/{nf_id}/status",
                headers=auth_headers,
            )

        assert r.status_code == 200
        body = r.json()
        assert body["status_sefaz"] == "AUTORIZADA"
        assert body["chave"] == "35240412345678000199550010000000011234567890"

    async def test_status_pendente_mantem_aguardando(self, client, auth_headers, test_engine):
        """Focus retorna 'processando' → NF permanece AGUARDANDO."""
        ids = await _setup_expedicao(test_engine)
        nf_id = await self._emitir_nf(client, auth_headers, ids)

        mock_focus = AsyncMock()
        mock_focus.consultar_nfe.return_value = {
            "status_code": 200,
            "data": {"status": "processando"},
        }

        with patch("app.api.v1.expedicao.focus_nfe", mock_focus):
            r = await client.get(
                f"/api/v1/expedicao/{nf_id}/status",
                headers=auth_headers,
            )

        assert r.status_code == 200
        assert r.json()["status_sefaz"] == "AGUARDANDO"

    async def test_status_nf_inexistente_retorna_404(self, client, auth_headers):
        r = await client.get("/api/v1/expedicao/99999/status", headers=auth_headers)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Download DANFE
# ---------------------------------------------------------------------------

class TestDanfe:
    async def _emitir_e_autorizar(self, client, auth_headers, ids):
        """Helper: emite e autoriza uma NF-e, retorna nf_id."""
        mock_emit = AsyncMock()
        mock_emit.emitir_nfe.return_value = {"status_code": 200, "data": {}}
        with patch("app.api.v1.expedicao.focus_nfe", mock_emit), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )
        nf_id = r.json()["nf_id"]

        # Autoriza via endpoint de status
        mock_status = AsyncMock()
        mock_status.consultar_nfe.return_value = {
            "status_code": 200,
            "data": {
                "status": "autorizado",
                "numero_nfe": "1",
                "chave_nfe": "35240412345678000199550010000000011234567890",
                "numero_protocolo": "135240000000001",
            },
        }
        with patch("app.api.v1.expedicao.focus_nfe", mock_status):
            await client.get(f"/api/v1/expedicao/{nf_id}/status", headers=auth_headers)

        return nf_id

    async def test_danfe_nf_autorizada_retorna_pdf(self, client, auth_headers, test_engine):
        ids = await _setup_expedicao(test_engine)
        nf_id = await self._emitir_e_autorizar(client, auth_headers, ids)

        pdf_bytes = b"%PDF-1.4 fake pdf content"
        mock_focus = AsyncMock()
        mock_focus.download_danfe.return_value = pdf_bytes

        with patch("app.api.v1.expedicao.focus_nfe", mock_focus):
            r = await client.get(f"/api/v1/expedicao/{nf_id}/danfe")

        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content == pdf_bytes

    async def test_danfe_nf_nao_autorizada_retorna_404(self, client, auth_headers, test_engine):
        """NF em status AGUARDANDO não pode ter DANFE baixado."""
        ids = await _setup_expedicao(test_engine)

        mock_focus = AsyncMock()
        mock_focus.emitir_nfe.return_value = {"status_code": 200, "data": {}}
        with patch("app.api.v1.expedicao.focus_nfe", mock_focus), \
             patch(_BG_NOOP, AsyncMock()):
            r = await client.post(
                f"/api/v1/expedicao/{ids['pedido_id']}/emitir",
                headers=auth_headers,
            )
        nf_id = r.json()["nf_id"]

        r = await client.get(f"/api/v1/expedicao/{nf_id}/danfe")
        assert r.status_code == 404

    async def test_danfe_nf_inexistente_retorna_404(self, client):
        r = await client.get("/api/v1/expedicao/99999/danfe")
        assert r.status_code == 404

    async def test_danfe_focus_indisponivel_retorna_503(
        self, client, auth_headers, test_engine
    ):
        """Se Focus retornar None (PDF indisponível), deve retornar 503."""
        ids = await _setup_expedicao(test_engine)
        nf_id = await self._emitir_e_autorizar(client, auth_headers, ids)

        mock_focus = AsyncMock()
        mock_focus.download_danfe.return_value = None  # Focus indisponível

        with patch("app.api.v1.expedicao.focus_nfe", mock_focus):
            r = await client.get(f"/api/v1/expedicao/{nf_id}/danfe")

        assert r.status_code == 503
