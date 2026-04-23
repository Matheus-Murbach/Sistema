"""
Testes de integração — Importação em Lote e Busca de NCM via API.

Módulo: /api/v1/produtos/
Endpoints cobertos:
  POST /produtos/importar          → Importa lista de produtos em JSON; ignora duplicados
  GET  /produtos/ncm/{ncm}         → Consulta descrição do NCM via BrasilAPI (mockado)
  GET  /produtos/unidades-medida   → Lista unidades de medida cadastradas

Regras de negócio verificadas (importar):
  - Produtos novos são criados e contados em 'criados'
  - Produtos com código já existente são ignorados e contados em 'duplicados'
  - Unidade desconhecida usa fallback para 'UN' quando disponível
  - Campo ncm vazio ou None é aceito (NCM é opcional)
  - Todos os campos opcionais têm defaults válidos (alíquotas, preços, estoque)
  - Importação sem autenticação retorna 401

Regras de negócio verificadas (ncm):
  - NCM com exatamente 8 dígitos aciona a BrasilAPI (mockado)
  - NCM com formato inválido retorna 400 antes de chamar a API externa
  - NCM não encontrado na tabela TIPI retorna 404
  - Falha no serviço externo retorna 503
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida


async def _criar_unidade(test_engine, codigo="UN", descricao="Unidade"):
    """Cria uma unidade de medida diretamente no banco."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo=codigo, descricao=descricao)
        session.add(un)
        await session.commit()
        await session.refresh(un)
        return un.id


# ---------------------------------------------------------------------------
# POST /produtos/importar
# ---------------------------------------------------------------------------

class TestImportarProdutos:
    async def test_importar_lista_simples_cria_produtos(self, client, auth_headers, test_engine):
        """Importar lista com 3 produtos novos deve criar todos e retornar criados=3."""
        await _criar_unidade(test_engine)

        r = await client.post("/api/v1/produtos/importar", json={
            "produtos": [
                {"codigo": "IMP-001", "descricao": "Produto Um",   "unidade": "UN"},
                {"codigo": "IMP-002", "descricao": "Produto Dois",  "unidade": "UN"},
                {"codigo": "IMP-003", "descricao": "Produto Tres",  "unidade": "UN"},
            ]
        }, headers=auth_headers)

        assert r.status_code == 200
        body = r.json()
        assert body["criados"] == 3
        assert body["duplicados"] == 0
        assert body["erros"] == []

    async def test_importar_produto_aparece_na_listagem(self, client, auth_headers, test_engine):
        """Produto importado deve aparecer na listagem normal de produtos."""
        await _criar_unidade(test_engine)

        await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "VISIVEL-001", "descricao": "Produto Visível", "unidade": "UN"}]
        }, headers=auth_headers)

        r = await client.get("/api/v1/produtos/?q=Visível")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["codigo"] == "VISIVEL-001"

    async def test_importar_duplicado_e_ignorado(self, client, auth_headers, test_engine):
        """Produto com código já existente é ignorado (não sobrescreve) e conta como duplicado."""
        await _criar_unidade(test_engine)

        # Primeira importação
        await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "DUP-001", "descricao": "Original", "unidade": "UN"}]
        }, headers=auth_headers)

        # Segunda importação com mesmo código
        r = await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "DUP-001", "descricao": "Tentativa de sobrescrever", "unidade": "UN"}]
        }, headers=auth_headers)

        assert r.status_code == 200
        body = r.json()
        assert body["criados"] == 0
        assert body["duplicados"] == 1

        # Descrição original não foi alterada
        r_lista = await client.get("/api/v1/produtos/?q=DUP-001")
        assert r_lista.json()[0]["descricao"] == "Original"

    async def test_importar_mistura_novos_e_duplicados(self, client, auth_headers, test_engine):
        """Lista com produtos novos e duplicados deve separar os contadores corretamente."""
        await _criar_unidade(test_engine)

        await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "EXIST-001", "descricao": "Existente", "unidade": "UN"}]
        }, headers=auth_headers)

        r = await client.post("/api/v1/produtos/importar", json={
            "produtos": [
                {"codigo": "EXIST-001", "descricao": "Existente",  "unidade": "UN"},
                {"codigo": "NOVO-001",  "descricao": "Novo A",     "unidade": "UN"},
                {"codigo": "NOVO-002",  "descricao": "Novo B",     "unidade": "UN"},
            ]
        }, headers=auth_headers)

        body = r.json()
        assert body["criados"] == 2
        assert body["duplicados"] == 1

    async def test_importar_com_aliquotas_persiste_valores_fiscais(self, client, auth_headers, test_engine):
        """Alíquotas informadas no import devem ser salvas no produto."""
        await _criar_unidade(test_engine)

        await client.post("/api/v1/produtos/importar", json={
            "produtos": [{
                "codigo": "FISCAL-001",
                "descricao": "Produto com fiscal",
                "unidade": "UN",
                "aliq_icms": "12",
                "aliq_ipi": "5",
                "aliq_pis": "0.65",
                "aliq_cofins": "3.00",
            }]
        }, headers=auth_headers)

        # Busca o produto e verifica os campos fiscais
        r = await client.get("/api/v1/produtos/?q=FISCAL-001")
        assert r.status_code == 200
        p = r.json()[0]
        produto_id = p["id"]

        r_det = await client.get(f"/api/v1/produtos/{produto_id}")
        det = r_det.json()
        assert float(det["aliq_icms"]) == pytest.approx(12.0)
        assert float(det["aliq_ipi"]) == pytest.approx(5.0)

    async def test_importar_unidade_desconhecida_usa_fallback_un(self, client, auth_headers, test_engine):
        """Se a unidade informada não existe no banco, usa UN como fallback."""
        await _criar_unidade(test_engine, "UN", "Unidade")

        r = await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "FALLBACK-001", "descricao": "Produto", "unidade": "INEXISTENTE"}]
        }, headers=auth_headers)

        assert r.status_code == 200
        assert r.json()["criados"] == 1
        assert r.json()["erros"] == []

    async def test_importar_ncm_vazio_aceito(self, client, auth_headers, test_engine):
        """NCM vazio ou ausente deve ser aceito — campo é opcional."""
        await _criar_unidade(test_engine)

        r = await client.post("/api/v1/produtos/importar", json={
            "produtos": [
                {"codigo": "NCM-VAZIO-001", "descricao": "Sem NCM", "unidade": "UN", "ncm": ""},
                {"codigo": "NCM-NULL-001",  "descricao": "NCM null", "unidade": "UN", "ncm": None},
            ]
        }, headers=auth_headers)

        assert r.json()["criados"] == 2
        assert r.json()["erros"] == []

    async def test_importar_campos_opcionais_com_defaults(self, client, auth_headers, test_engine):
        """Importação sem preços ou estoque deve usar defaults (0) sem erros."""
        await _criar_unidade(test_engine)

        r = await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "DEFAULT-001", "descricao": "Produto default", "unidade": "UN"}]
        }, headers=auth_headers)

        assert r.status_code == 200
        assert r.json()["criados"] == 1

    async def test_importar_lista_vazia_retorna_zero(self, client, auth_headers):
        """Lista vazia deve ser aceita e retornar criados=0."""
        r = await client.post("/api/v1/produtos/importar", json={"produtos": []},
                               headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["criados"] == 0

    async def test_importar_sem_auth_retorna_401(self, client):
        """Importação exige autenticação."""
        r = await client.post("/api/v1/produtos/importar", json={"produtos": []})
        assert r.status_code == 401

    async def test_importar_preserva_tipo_correto(self, client, auth_headers, test_engine):
        """Tipo informado no import deve ser salvo (não forçado para MATERIA_PRIMA)."""
        await _criar_unidade(test_engine)

        await client.post("/api/v1/produtos/importar", json={
            "produtos": [{"codigo": "TIPO-001", "descricao": "PA", "unidade": "UN", "tipo": "PRODUTO_ACABADO"}]
        }, headers=auth_headers)

        r = await client.get("/api/v1/produtos/?q=TIPO-001")
        assert r.json()[0]["tipo"] == "PRODUTO_ACABADO"


# ---------------------------------------------------------------------------
# GET /produtos/ncm/{ncm}  (com mock da BrasilAPI)
# ---------------------------------------------------------------------------

class TestConsultarNcm:
    async def test_ncm_valido_retorna_descricao(self, client):
        """NCM de 8 dígitos encontrado retorna descrição e aviso sobre alíquotas."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"descricao": "Parafusos de ferro ou aço"}

        with patch("app.api.v1.produtos.httpx.AsyncClient") as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_ctx

            r = await client.get("/api/v1/produtos/ncm/73181600")

        assert r.status_code == 200
        body = r.json()
        assert body["ncm"] == "73181600"
        assert body["descricao"] == "Parafusos de ferro ou aço"
        assert "aviso" in body

    async def test_ncm_com_menos_de_8_digitos_retorna_400(self, client):
        """NCM com menos de 8 dígitos deve retornar 400 sem chamar a API externa."""
        r = await client.get("/api/v1/produtos/ncm/7318")
        assert r.status_code == 400

    async def test_ncm_com_mais_de_8_digitos_retorna_400(self, client):
        """NCM com mais de 8 dígitos deve retornar 400."""
        r = await client.get("/api/v1/produtos/ncm/731816001")
        assert r.status_code == 400

    async def test_ncm_com_letras_retorna_400(self, client):
        """NCM não numérico deve retornar 400."""
        r = await client.get("/api/v1/produtos/ncm/7318ABCD")
        assert r.status_code == 400

    async def test_ncm_nao_encontrado_retorna_404(self, client):
        """BrasilAPI retornando 404 deve ser propagado como 404."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404

        with patch("app.api.v1.produtos.httpx.AsyncClient") as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_ctx

            r = await client.get("/api/v1/produtos/ncm/99999999")

        assert r.status_code == 404

    async def test_ncm_servico_indisponivel_retorna_503(self, client):
        """Falha na chamada à BrasilAPI deve retornar 503."""
        with patch("app.api.v1.produtos.httpx.AsyncClient") as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.get = AsyncMock(side_effect=Exception("timeout"))
            mock_cls.return_value = mock_ctx

            r = await client.get("/api/v1/produtos/ncm/73181600")

        assert r.status_code == 503

    async def test_ncm_remove_pontos_e_tracos(self, client):
        """NCM formatado como '7318.16.00' deve ser normalizado para '73181600'."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"descricao": "Parafusos"}

        with patch("app.api.v1.produtos.httpx.AsyncClient") as mock_cls:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_ctx.__aexit__ = AsyncMock(return_value=False)
            mock_ctx.get = AsyncMock(return_value=mock_resp)
            mock_cls.return_value = mock_ctx

            r = await client.get("/api/v1/produtos/ncm/7318.16.00")

        assert r.status_code == 200
        assert r.json()["ncm"] == "73181600"


# ---------------------------------------------------------------------------
# GET /produtos/unidades-medida
# ---------------------------------------------------------------------------

class TestListarUnidades:
    async def test_listar_vazio(self, client):
        """Com banco zerado, retorna lista vazia."""
        r = await client.get("/api/v1/produtos/unidades-medida")
        assert r.status_code == 200
        assert r.json() == []

    async def test_listar_com_unidades(self, client, test_engine):
        """Unidades cadastradas devem aparecer ordenadas por código."""
        await _criar_unidade(test_engine, "UN", "Unidade")
        await _criar_unidade(test_engine, "KG", "Quilograma")
        await _criar_unidade(test_engine, "MT", "Metro")

        r = await client.get("/api/v1/produtos/unidades-medida")
        assert r.status_code == 200
        codigos = [u["codigo"] for u in r.json()]
        assert codigos == sorted(codigos)  # Verifica ordenação alfabética
        assert "UN" in codigos
        assert "KG" in codigos
