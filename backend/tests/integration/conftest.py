"""
Fixtures compartilhadas para testes de integração via API.

Usa httpx.AsyncClient + ASGITransport para testar os endpoints sem servidor HTTP real.
StaticPool garante que toda a suite usa a mesma conexão SQLite em memória,
permitindo que dados criados em fixtures sejam visíveis nas chamadas de API.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.usuario import Usuario
from app.models.produto import UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.core.security import hash_password, create_access_token

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Engine SQLite em memória com StaticPool — todos os acessos usam a mesma conexão."""
    eng = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(test_engine):
    """
    AsyncClient com get_db sobrescrito para usar o banco de testes.
    Garante que API e fixtures de dados usam o mesmo banco in-memory.
    """
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine):
    """Sessão direta para setup de dados de teste (sem passar pela API)."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_engine):
    """Cria usuário admin e retorna headers de autorização JWT."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        user = Usuario(
            nome="Admin Teste",
            email="admin@teste.com",
            senha_hash=hash_password("senha123"),
            perfil="admin",
            ativo=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        token = create_access_token({"sub": user.id, "perfil": user.perfil})

    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="function")
async def unidade_padrao(test_engine):
    """Cria unidade de medida 'UN' necessária para produtos."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.commit()
        await session.refresh(un)
        return un.id  # Retorna apenas o ID (suficiente para referenciar)


@pytest_asyncio.fixture(scope="function")
async def localizacao_padrao(test_engine):
    """Cria localização de estoque padrão."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        loc = LocalizacaoEstoque(codigo="A-01", descricao="Prateleira A-01")
        session.add(loc)
        await session.commit()
        await session.refresh(loc)
        return loc.id
