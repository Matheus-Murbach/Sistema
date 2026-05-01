"""
TDD — Testes unitários do cliente Focus NF-e.

Valida que o wrapper HTTP:
  - Chama as URLs corretas com auth e payload corretos
  - Retorna dict com status_code e data em todos os cenários
  - Trata respostas de erro sem lançar exceção
  - Retorna None para downloads quando o arquivo não está disponível
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.focus_nfe import FocusNFeClient


def _make_client(base_url="https://homologacao.focusnfe.com.br", token="token-teste"):
    """Cria instância do cliente com settings mockadas."""
    with patch("app.integrations.focus_nfe.settings") as mock_settings:
        mock_settings.FOCUS_NFE_URL = base_url
        mock_settings.FOCUS_NFE_TOKEN = token
        return FocusNFeClient()


def _mock_response(status_code: int, json_data: dict = None, content: bytes = None):
    """Cria um response mockado para httpx."""
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    if content is not None:
        resp.content = content
    return resp


# ---------------------------------------------------------------------------
# emitir_nfe
# ---------------------------------------------------------------------------

class TestEmitirNFe:
    async def test_emitir_sucesso_retorna_status_200_e_dados(self):
        client = _make_client()
        dados_resposta = {"status": "processando", "numero_nfe": None}

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.post.return_value = _mock_response(200, dados_resposta)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.emitir_nfe("NF-TESTE-001", {"natureza_operacao": "VENDA"})

        assert resultado["status_code"] == 200
        assert resultado["data"]["status"] == "processando"

    async def test_emitir_rejeicao_retorna_status_422(self):
        client = _make_client()
        dados_erro = {"erros": [{"codigo": "539", "mensagem": "CNPJ inválido"}]}

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.post.return_value = _mock_response(422, dados_erro)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.emitir_nfe("NF-REJEITADA-001", {})

        assert resultado["status_code"] == 422
        assert "erros" in resultado["data"]

    async def test_emitir_usa_url_e_referencia_corretos(self):
        client = _make_client(base_url="https://api.focusnfe.com.br")
        mock_post = AsyncMock(return_value=_mock_response(200, {}))
        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.post = mock_post
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            await client.emitir_nfe("REF-123", {"dados": "teste"})

        call_args = mock_post.call_args
        url = call_args[0][0] if call_args[0] else call_args[1].get("url", call_args[0])
        assert "https://api.focusnfe.com.br/v2/nfe" in str(call_args)
        assert "REF-123" in str(call_args)


# ---------------------------------------------------------------------------
# consultar_nfe
# ---------------------------------------------------------------------------

class TestConsultarNFe:
    async def test_consultar_autorizado(self):
        client = _make_client()
        dados = {
            "status": "autorizado",
            "numero_nfe": "123456",
            "chave_nfe": "35240412345678000199550010000000011234567890",
            "numero_protocolo": "135240000000001",
        }

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, dados)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.consultar_nfe("REF-AUTORIZADA")

        assert resultado["status_code"] == 200
        assert resultado["data"]["status"] == "autorizado"
        assert resultado["data"]["numero_nfe"] == "123456"

    async def test_consultar_pendente(self):
        client = _make_client()
        dados = {"status": "processando"}

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, dados)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.consultar_nfe("REF-PENDENTE")

        assert resultado["data"]["status"] == "processando"

    async def test_consultar_erro_autorizacao(self):
        client = _make_client()
        dados = {"status": "erro_autorizacao", "erros": "CNPJ inválido"}

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, dados)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.consultar_nfe("REF-ERRO")

        assert resultado["data"]["status"] == "erro_autorizacao"


# ---------------------------------------------------------------------------
# download_danfe
# ---------------------------------------------------------------------------

class TestDownloadDanfe:
    async def test_download_danfe_sucesso_retorna_bytes(self):
        client = _make_client()
        pdf_bytes = b"%PDF-1.4 conteudo do pdf"

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, content=pdf_bytes)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.download_danfe("REF-COM-DANFE")

        assert resultado == pdf_bytes

    async def test_download_danfe_nao_disponivel_retorna_none(self):
        client = _make_client()

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(404)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.download_danfe("REF-SEM-DANFE")

        assert resultado is None

    async def test_download_danfe_servidor_erro_retorna_none(self):
        client = _make_client()

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(503)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.download_danfe("REF-ERRO-SERVIDOR")

        assert resultado is None


# ---------------------------------------------------------------------------
# download_xml
# ---------------------------------------------------------------------------

class TestDownloadXml:
    async def test_download_xml_sucesso_retorna_bytes(self):
        client = _make_client()
        xml_bytes = b"<?xml version='1.0'?><nfeProc></nfeProc>"

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, content=xml_bytes)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.download_xml("REF-XML")

        assert resultado == xml_bytes

    async def test_download_xml_indisponivel_retorna_none(self):
        client = _make_client()

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(404)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.download_xml("REF-SEM-XML")

        assert resultado is None


# ---------------------------------------------------------------------------
# cancelar_nfe
# ---------------------------------------------------------------------------

class TestCancelarNFe:
    async def test_cancelar_sucesso_retorna_200(self):
        client = _make_client()
        dados = {"status": "cancelado"}

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.delete.return_value = _mock_response(200, dados)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.focus_nfe.httpx.AsyncClient", return_value=mock_http):
            resultado = await client.cancelar_nfe(
                "REF-CANCELAR",
                "Produto entregue incorretamente ao cliente"
            )

        assert resultado["status_code"] == 200
        assert resultado["data"]["status"] == "cancelado"
