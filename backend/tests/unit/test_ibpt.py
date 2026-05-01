"""
TDD — Testes unitários da integração com IBPT (alíquotas por NCM).

Valida:
  - Token ausente → retorna None sem fazer request HTTP
  - Resposta 200 com dados completos → retorna AliquotasNCM preenchido
  - Resposta 4xx → retorna None
  - Qualquer exceção (timeout, JSON inválido) → retorna None sem propagar
  - UF não informada → usa settings.EMPRESA_UF como fallback
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.ibpt import buscar_aliquotas_ncm, AliquotasNCM


def _mock_response(status_code: int, json_data: dict = None):
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    return resp


# ---------------------------------------------------------------------------
# Token ausente
# ---------------------------------------------------------------------------

class TestTokenAusente:
    async def test_sem_token_retorna_none_sem_request(self):
        """Com IBPT_TOKEN vazio, nenhuma request deve ser feita."""
        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = ""
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient") as mock_client_cls:
                resultado = await buscar_aliquotas_ncm("73181500")

        assert resultado is None
        mock_client_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Resposta de sucesso
# ---------------------------------------------------------------------------

class TestRespostaSucesso:
    async def test_resposta_200_retorna_aliquotas_ncm(self):
        dados_api = {
            "Descricao": "Parafusos e porcas",
            "Nacional": 12.45,
            "Importado": 25.30,
            "Estadual": 12.0,
            "Municipal": 0.0,
        }

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, dados_api)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                resultado = await buscar_aliquotas_ncm("73181500", "SP")

        assert resultado is not None
        assert isinstance(resultado, AliquotasNCM)
        assert resultado.ncm == "73181500"
        assert resultado.descricao == "Parafusos e porcas"
        assert resultado.aliq_nacional == pytest.approx(12.45)
        assert resultado.aliq_importado == pytest.approx(25.30)
        assert resultado.aliq_estadual == pytest.approx(12.0)
        assert resultado.aliq_municipal == pytest.approx(0.0)

    async def test_campos_faltantes_usam_zero_como_padrao(self):
        """Se a API omitir campos, os valores devem ser 0."""
        dados_parciais = {"Descricao": "Produto sem alíquotas"}

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(200, dados_parciais)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                resultado = await buscar_aliquotas_ncm("00000000", "SP")

        assert resultado is not None
        assert resultado.aliq_nacional == 0.0
        assert resultado.aliq_estadual == 0.0


# ---------------------------------------------------------------------------
# Respostas de erro
# ---------------------------------------------------------------------------

class TestRespostaErro:
    async def test_resposta_404_retorna_none(self):
        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(404)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                resultado = await buscar_aliquotas_ncm("99999999")

        assert resultado is None

    async def test_resposta_500_retorna_none(self):
        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = _mock_response(500)
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                resultado = await buscar_aliquotas_ncm("73181500")

        assert resultado is None


# ---------------------------------------------------------------------------
# Falhas de rede e exceções
# ---------------------------------------------------------------------------

class TestFalhasRede:
    async def test_timeout_retorna_none_sem_propagar(self):
        """Timeout na request não deve propagar exceção, deve retornar None."""
        import httpx

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.side_effect = httpx.TimeoutException("timeout")
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                resultado = await buscar_aliquotas_ncm("73181500")

        assert resultado is None

    async def test_json_invalido_retorna_none(self):
        """Resposta que não é JSON válido deve retornar None."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("JSON inválido")

        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get.return_value = resp
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "SP"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                resultado = await buscar_aliquotas_ncm("73181500")

        assert resultado is None


# ---------------------------------------------------------------------------
# Fallback de UF
# ---------------------------------------------------------------------------

class TestFallbackUF:
    async def test_uf_nao_informada_usa_settings(self):
        """Quando UF não é passada, deve usar settings.EMPRESA_UF."""
        dados_api = {"Descricao": "Produto", "Nacional": 5.0, "Importado": 10.0, "Estadual": 7.0, "Municipal": 0.0}

        mock_get = AsyncMock(return_value=_mock_response(200, dados_api))
        mock_http = AsyncMock()
        mock_http.__aenter__.return_value.get = mock_get
        mock_http.__aexit__.return_value = False

        with patch("app.integrations.ibpt.settings") as mock_settings:
            mock_settings.IBPT_TOKEN = "token-valido"
            mock_settings.IBPT_CNPJ = "12345678000199"
            mock_settings.EMPRESA_UF = "MG"

            with patch("app.integrations.ibpt.httpx.AsyncClient", return_value=mock_http):
                await buscar_aliquotas_ncm("73181500")  # sem UF

        # Verifica que MG foi usado nos parâmetros
        call_kwargs = mock_get.call_args
        params = call_kwargs[1].get("params", {}) if call_kwargs[1] else {}
        if not params and call_kwargs[0]:
            params = call_kwargs[0][1] if len(call_kwargs[0]) > 1 else {}
        assert params.get("uf") == "MG"
