"""
Script de seed inicial do banco de dados.

Cria:
  - Usuário administrador padrão
  - Unidades de medida básicas
  - Localizações de estoque padrão
  - Máquinas padrão

Uso:
  cd backend
  python scripts/seed.py

  ou via Docker:
  docker compose exec backend python scripts/seed.py

Variáveis de ambiente opcionais:
  ADMIN_EMAIL    (padrão: admin@sistema.local)
  ADMIN_SENHA    (padrão: admin123)
  DATABASE_URL   (padrão: lido do .env)
"""
import asyncio
import os
import sys

# Garante que o diretório pai está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings

DATABASE_URL = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@sistema.local")
ADMIN_SENHA = os.environ.get("ADMIN_SENHA", "admin123")


async def seed():
    from app.models.usuario import Usuario
    from app.models.produto import UnidadeMedida
    from app.models.estoque import LocalizacaoEstoque
    from app.models.maquina import Maquina

    async with AsyncSessionLocal() as db:
        # Admin
        r = await db.execute(select(Usuario).where(Usuario.email == ADMIN_EMAIL))
        if not r.scalar_one_or_none():
            db.add(Usuario(
                nome="Administrador",
                email=ADMIN_EMAIL,
                senha_hash=pwd_context.hash(ADMIN_SENHA),
                perfil="admin",
                ativo=True,
            ))
            print(f"  ✓ Admin criado: {ADMIN_EMAIL} / {ADMIN_SENHA}")
        else:
            print(f"  - Admin já existe: {ADMIN_EMAIL}")

        # Unidades de medida
        for codigo, descricao in [
            ("UN", "Unidade"),
            ("KG", "Quilograma"),
            ("MT", "Metro"),
            ("CX", "Caixa"),
            ("PC", "Peça"),
            ("M2", "Metro Quadrado"),
            ("LT", "Litro"),
        ]:
            r = await db.execute(select(UnidadeMedida).where(UnidadeMedida.codigo == codigo))
            if not r.scalar_one_or_none():
                db.add(UnidadeMedida(codigo=codigo, descricao=descricao))

        print("  ✓ Unidades de medida: UN, KG, MT, CX, PC, M2, LT")

        # Localizações padrão
        for codigo, descricao, corredor, prateleira, bin_ in [
            ("A-01-01", "Corredor A, Prateleira 01, Bin 01", "A", "01", "01"),
            ("A-01-02", "Corredor A, Prateleira 01, Bin 02", "A", "01", "02"),
            ("A-02-01", "Corredor A, Prateleira 02, Bin 01", "A", "02", "01"),
            ("B-01-01", "Corredor B, Prateleira 01, Bin 01", "B", "01", "01"),
            ("B-01-02", "Corredor B, Prateleira 01, Bin 02", "B", "01", "02"),
        ]:
            r = await db.execute(select(LocalizacaoEstoque).where(LocalizacaoEstoque.codigo == codigo))
            if not r.scalar_one_or_none():
                db.add(LocalizacaoEstoque(codigo=codigo, descricao=descricao, corredor=corredor, prateleira=prateleira, bin=bin_))

        for codigo, descricao in [
            ("RECEB", "Área de Recebimento"),
            ("EXPEDICAO", "Área de Expedição"),
            ("PRODUCAO", "Chão de Fábrica / Produção"),
        ]:
            r = await db.execute(select(LocalizacaoEstoque).where(LocalizacaoEstoque.codigo == codigo))
            if not r.scalar_one_or_none():
                db.add(LocalizacaoEstoque(codigo=codigo, descricao=descricao))

        print("  ✓ Localizações: A-01-01..B-01-02, RECEB, EXPEDICAO, PRODUCAO")

        # Máquinas
        for i in range(1, 4):
            codigo = f"MAQ-0{i}"
            r = await db.execute(select(Maquina).where(Maquina.codigo == codigo))
            if not r.scalar_one_or_none():
                db.add(Maquina(codigo=codigo, nome=f"Máquina {i}", ativa=True))

        print("  ✓ Máquinas: MAQ-01, MAQ-02, MAQ-03")

        await db.commit()
        print("\nSeed concluído com sucesso!")


if __name__ == "__main__":
    print("Executando seed do banco de dados...")
    asyncio.run(seed())
