"""
Testes de integração — CRUD de cadastros via API.

Cobre os endpoints de:
  - /health (main.py)
  - /auth/login
  - /produtos/ (CRUD)
  - /parceiros/fornecedores/ (CRUD)
  - /parceiros/clientes/ (CRUD)
  - /estoque/localizacoes e saldos
  - /dashboard/resumo
"""
import pytest
from decimal import Decimal


# ---------------------------------------------------------------------------
# Health check (main.py)
# ---------------------------------------------------------------------------

class TestHealthCheck:
    async def test_health_retorna_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Auth — login
# ---------------------------------------------------------------------------

class TestAuth:
    async def test_login_invalido_retorna_401(self, client):
        r = await client.post("/api/v1/auth/login", data={
            "username": "nao_existe@teste.com",
            "password": "senhaerrada",
        })
        assert r.status_code == 401

    async def test_login_valido_retorna_token(self, client, auth_headers):
        """Usando a fixture auth_headers, o usuário admin foi criado.
        Agora testa o endpoint de login diretamente."""
        r = await client.post("/api/v1/auth/login", data={
            "username": "admin@teste.com",
            "password": "senha123",
        })
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["perfil"] == "admin"

    async def test_endpoint_autenticado_sem_token_retorna_401(self, client):
        r = await client.post("/api/v1/produtos/", json={
            "codigo": "P-001",
            "descricao": "Produto",
            "unidade_id": 1,
        })
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------

class TestProdutosCRUD:
    async def test_listar_produtos_vazio(self, client):
        r = await client.get("/api/v1/produtos/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_criar_produto(self, client, auth_headers, unidade_padrao):
        r = await client.post("/api/v1/produtos/", json={
            "codigo": "PROD-001",
            "descricao": "Parafuso M8",
            "tipo": "PRODUTO_BENEFICIADO",
            "unidade_id": unidade_padrao,
            "ncm": "73181500",
            "aliq_icms": "12.00",
            "aliq_pis": "0.65",
            "aliq_cofins": "3.00",
            "preco_venda": "5.50",
        }, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["codigo"] == "PROD-001"
        assert body["descricao"] == "Parafuso M8"
        assert body["tipo"] == "PRODUTO_BENEFICIADO"

    async def test_listar_produtos_apos_criacao(self, client, auth_headers, unidade_padrao):
        await client.post("/api/v1/produtos/", json={
            "codigo": "PROD-002",
            "descricao": "Arruela",
            "unidade_id": unidade_padrao,
        }, headers=auth_headers)

        r = await client.get("/api/v1/produtos/")
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_detalhar_produto(self, client, auth_headers, unidade_padrao):
        r_create = await client.post("/api/v1/produtos/", json={
            "codigo": "PROD-003",
            "descricao": "Porca M6",
            "unidade_id": unidade_padrao,
        }, headers=auth_headers)
        produto_id = r_create.json()["id"]

        r = await client.get(f"/api/v1/produtos/{produto_id}")
        assert r.status_code == 200
        assert r.json()["id"] == produto_id

    async def test_detalhar_produto_inexistente_retorna_404(self, client):
        r = await client.get("/api/v1/produtos/99999")
        assert r.status_code == 404

    async def test_atualizar_produto(self, client, auth_headers, unidade_padrao):
        r_create = await client.post("/api/v1/produtos/", json={
            "codigo": "PROD-004",
            "descricao": "Antes",
            "unidade_id": unidade_padrao,
        }, headers=auth_headers)
        produto_id = r_create.json()["id"]

        r = await client.put(f"/api/v1/produtos/{produto_id}", json={
            "descricao": "Depois",
            "unidade_id": unidade_padrao,
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["descricao"] == "Depois"

    async def test_buscar_produto_por_descricao(self, client, auth_headers, unidade_padrao):
        await client.post("/api/v1/produtos/", json={
            "codigo": "PROD-005",
            "descricao": "Parafuso Especial",
            "unidade_id": unidade_padrao,
        }, headers=auth_headers)

        r = await client.get("/api/v1/produtos/?q=especial")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["descricao"] == "Parafuso Especial"

    async def test_buscar_produto_sem_resultado(self, client, auth_headers, unidade_padrao):
        r = await client.get("/api/v1/produtos/?q=produto_inexistente_xyz")
        assert r.status_code == 200
        assert r.json() == []

    async def test_produto_sem_ncm_nao_tem_aliquotas_ibpt(self, client, auth_headers, unidade_padrao):
        """Produto sem NCM deve retornar 400 ao buscar alíquotas IBPT."""
        r_create = await client.post("/api/v1/produtos/", json={
            "codigo": "PROD-SEM-NCM",
            "descricao": "Produto sem NCM",
            "unidade_id": unidade_padrao,
        }, headers=auth_headers)
        produto_id = r_create.json()["id"]

        r = await client.get(f"/api/v1/produtos/{produto_id}/aliquotas-ncm")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Parceiros — Fornecedores
# ---------------------------------------------------------------------------

class TestFornecedoresCRUD:
    async def test_listar_fornecedores_vazio(self, client):
        r = await client.get("/api/v1/parceiros/fornecedores/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_criar_fornecedor(self, client, auth_headers):
        r = await client.post("/api/v1/parceiros/fornecedores/", json={
            "razao_social": "Aços São Paulo Ltda",
            "cnpj_cpf": "12.345.678/0001-99",
            "uf": "SP",
            "prazo_entrega_dias": 5,
        }, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["razao_social"] == "Aços São Paulo Ltda"
        assert body["cnpj_cpf"] == "12.345.678/0001-99"

    async def test_detalhar_fornecedor(self, client, auth_headers):
        r_create = await client.post("/api/v1/parceiros/fornecedores/", json={
            "razao_social": "Fornecedor Teste",
            "cnpj_cpf": "98.765.432/0001-10",
        }, headers=auth_headers)
        forn_id = r_create.json()["id"]

        r = await client.get(f"/api/v1/parceiros/fornecedores/{forn_id}")
        assert r.status_code == 200
        assert r.json()["id"] == forn_id

    async def test_fornecedor_inexistente_retorna_404(self, client):
        r = await client.get("/api/v1/parceiros/fornecedores/99999")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Parceiros — Clientes
# ---------------------------------------------------------------------------

class TestClientesCRUD:
    async def test_criar_cliente(self, client, auth_headers):
        r = await client.post("/api/v1/parceiros/clientes/", json={
            "razao_social": "Comprador Industrial Ltda",
            "cnpj_cpf": "11.222.333/0001-44",
            "uf": "RJ",
            "consumidor_final": False,
        }, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["razao_social"] == "Comprador Industrial Ltda"
        assert body["uf"] == "RJ"

    async def test_listar_clientes(self, client, auth_headers):
        await client.post("/api/v1/parceiros/clientes/", json={
            "razao_social": "Cliente A",
            "cnpj_cpf": "11.111.111/0001-11",
        }, headers=auth_headers)
        await client.post("/api/v1/parceiros/clientes/", json={
            "razao_social": "Cliente B",
            "cnpj_cpf": "22.222.222/0001-22",
        }, headers=auth_headers)

        r = await client.get("/api/v1/parceiros/clientes/")
        assert r.status_code == 200
        assert len(r.json()) == 2

    async def test_atualizar_cliente(self, client, auth_headers):
        r_create = await client.post("/api/v1/parceiros/clientes/", json={
            "razao_social": "Cliente Original",
            "cnpj_cpf": "33.333.333/0001-33",
        }, headers=auth_headers)
        cli_id = r_create.json()["id"]

        r = await client.put(f"/api/v1/parceiros/clientes/{cli_id}", json={
            "razao_social": "Cliente Atualizado",
            "cnpj_cpf": "33.333.333/0001-33",
        }, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["razao_social"] == "Cliente Atualizado"


# ---------------------------------------------------------------------------
# Estoque — Localizações e Saldos
# ---------------------------------------------------------------------------

class TestEstoqueCRUD:
    async def test_listar_localizacoes_vazio(self, client):
        r = await client.get("/api/v1/estoque/localizacoes")
        assert r.status_code == 200
        assert r.json() == []

    async def test_criar_localizacao(self, client, auth_headers):
        r = await client.post("/api/v1/estoque/localizacoes", json={
            "codigo": "A-01",
            "descricao": "Prateleira A-01",
            "corredor": "A",
            "prateleira": "01",
        }, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["codigo"] == "A-01"

    async def test_listar_saldos_vazio(self, client):
        r = await client.get("/api/v1/estoque/saldos")
        assert r.status_code == 200
        assert r.json() == []

    async def test_pronta_entrega_retorna_lista(self, client):
        """Endpoint pronta-entrega deve funcionar mesmo sem saldo."""
        r = await client.get("/api/v1/estoque/pronta-entrega")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_alertas_estoque_minimo_retorna_lista(self, client):
        """Endpoint de alertas deve funcionar mesmo sem produtos."""
        r = await client.get("/api/v1/estoque/alertas-estoque-minimo")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_listar_movimentacoes(self, client):
        r = await client.get("/api/v1/estoque/movimentacoes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class TestDashboard:
    async def test_resumo_dashboard(self, client, auth_headers):
        r = await client.get("/api/v1/dashboard/resumo", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "ops_abertas" in body
        assert "pedidos_pendentes_expedicao" in body
        assert "lotes_no_banho" in body
        assert "lotes_banho_atrasados" in body
        assert "vendas_mes" in body
        assert "data" in body

    async def test_dashboard_sem_auth_retorna_401(self, client):
        r = await client.get("/api/v1/dashboard/resumo")
        assert r.status_code == 401

    async def test_dashboard_valores_zerados_sem_dados(self, client, auth_headers):
        """Com banco vazio, todos os contadores devem ser zero."""
        r = await client.get("/api/v1/dashboard/resumo", headers=auth_headers)
        body = r.json()
        assert body["ops_abertas"] == 0
        assert body["pedidos_pendentes_expedicao"] == 0
        assert body["lotes_no_banho"] == 0
        assert body["lotes_banho_atrasados"] == 0
        assert body["vendas_mes"] == 0.0
