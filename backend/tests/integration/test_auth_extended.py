"""
Testes de integração — Auth (complemento ao test_api_crud.py).

Cobre lacunas do módulo auth.py:
  - POST /api/v1/auth/usuarios  → criar usuário (admin-only)
  - Segurança de tokens: inválido, malformado
  - Usuário inativo não pode fazer login
"""
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.security import hash_password, create_access_token
from app.models.usuario import Usuario


# ---------------------------------------------------------------------------
# Gerenciamento de Usuários
# ---------------------------------------------------------------------------

class TestGerenciarUsuarios:
    async def test_admin_cria_usuario(self, client, auth_headers):
        """Admin pode criar usuário → 201 com dados corretos."""
        r = await client.post("/api/v1/auth/usuarios", json={
            "nome": "João Operador",
            "email": "joao@fabrica.com",
            "senha": "senha456",
            "perfil": "operador",
        }, headers=auth_headers)

        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "joao@fabrica.com"
        assert body["nome"] == "João Operador"
        assert body["perfil"] == "operador"
        assert "id" in body
        # Senha nunca deve ser exposta na resposta
        assert "senha" not in body
        assert "senha_hash" not in body

    async def test_criar_usuario_sem_auth_retorna_401(self, client):
        r = await client.post("/api/v1/auth/usuarios", json={
            "nome": "Teste",
            "email": "teste@teste.com",
            "senha": "senha123",
        })
        assert r.status_code == 401

    async def test_criar_usuario_com_perfil_operador_retorna_403(
        self, client, test_engine
    ):
        """Usuário com perfil 'operador' não pode criar outros usuários."""
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            operador = Usuario(
                nome="Operador Teste",
                email="operador@fabrica.com",
                senha_hash=hash_password("senha123"),
                perfil="operador",
                ativo=True,
            )
            session.add(operador)
            await session.commit()
            await session.refresh(operador)
            token = create_access_token({"sub": operador.id, "perfil": operador.perfil})

        headers_operador = {"Authorization": f"Bearer {token}"}

        r = await client.post("/api/v1/auth/usuarios", json={
            "nome": "Novo Usuário",
            "email": "novo@fabrica.com",
            "senha": "senha999",
        }, headers=headers_operador)
        assert r.status_code == 403

    async def test_usuario_criado_pode_fazer_login(self, client, auth_headers):
        """Usuário criado via API deve conseguir autenticar imediatamente."""
        await client.post("/api/v1/auth/usuarios", json={
            "nome": "Maria Vendas",
            "email": "maria@fabrica.com",
            "senha": "mariaSenha789",
            "perfil": "operador",
        }, headers=auth_headers)

        r = await client.post("/api/v1/auth/login", data={
            "username": "maria@fabrica.com",
            "password": "mariaSenha789",
        })
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_perfil_padrao_e_operador(self, client, auth_headers):
        """Sem informar perfil, o padrão deve ser 'operador'."""
        r = await client.post("/api/v1/auth/usuarios", json={
            "nome": "Sem Perfil",
            "email": "semperfil@fabrica.com",
            "senha": "senha321",
        }, headers=auth_headers)

        assert r.status_code == 201
        assert r.json()["perfil"] == "operador"


# ---------------------------------------------------------------------------
# Usuário Inativo
# ---------------------------------------------------------------------------

class TestUsuarioInativo:
    async def test_login_usuario_inativo_emite_token_mas_endpoints_rejeitam(
        self, client, test_engine
    ):
        """
        O endpoint de login não verifica ativo (verifica apenas senha).
        Porém, o token emitido é rejeitado em qualquer endpoint protegido por
        get_current_user, que checa user.ativo == True.
        """
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            inativo = Usuario(
                nome="Ex-Funcionário",
                email="inativo@fabrica.com",
                senha_hash=hash_password("senha123"),
                perfil="operador",
                ativo=False,
            )
            session.add(inativo)
            await session.commit()

        # Login retorna token mesmo para usuário inativo
        r_login = await client.post("/api/v1/auth/login", data={
            "username": "inativo@fabrica.com",
            "password": "senha123",
        })
        assert r_login.status_code == 200
        token = r_login.json()["access_token"]

        # Mas o token é rejeitado em endpoints protegidos
        r_prot = await client.get("/api/v1/dashboard/resumo", headers={
            "Authorization": f"Bearer {token}"
        })
        assert r_prot.status_code == 401

    async def test_token_de_usuario_inativado_retorna_401(self, client, test_engine):
        """Token de usuário que foi desativado depois de emitido deve ser rejeitado."""
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            usuario = Usuario(
                nome="Usuário Ativo",
                email="ativo@fabrica.com",
                senha_hash=hash_password("senha123"),
                perfil="operador",
                ativo=True,
            )
            session.add(usuario)
            await session.commit()
            await session.refresh(usuario)
            token = create_access_token({"sub": usuario.id, "perfil": usuario.perfil})

            # Inativa o usuário
            usuario.ativo = False
            await session.commit()

        headers = {"Authorization": f"Bearer {token}"}
        r = await client.get("/api/v1/dashboard/resumo", headers=headers)
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Segurança de Tokens
# ---------------------------------------------------------------------------

class TestTokenSeguranca:
    async def test_token_com_assinatura_invalida_retorna_401(self, client):
        """Token com assinatura manipulada deve ser rejeitado."""
        token = create_access_token({"sub": 1, "perfil": "admin"})
        # Manipula o último caractere da assinatura
        partes = token.split(".")
        assinatura_invalida = partes[2][:-1] + ("A" if partes[2][-1] != "A" else "B")
        token_invalido = ".".join(partes[:2] + [assinatura_invalida])

        r = await client.get("/api/v1/dashboard/resumo", headers={
            "Authorization": f"Bearer {token_invalido}"
        })
        assert r.status_code == 401

    async def test_token_malformado_retorna_401(self, client):
        """String aleatória no lugar do token deve retornar 401."""
        r = await client.get("/api/v1/dashboard/resumo", headers={
            "Authorization": "Bearer nao-sou-um-jwt-valido"
        })
        assert r.status_code == 401

    async def test_bearer_faltando_retorna_401(self, client):
        """Header sem o prefixo Bearer deve retornar 401."""
        token = create_access_token({"sub": 1, "perfil": "admin"})
        r = await client.get("/api/v1/dashboard/resumo", headers={
            "Authorization": token  # sem "Bearer "
        })
        assert r.status_code == 401
