"""
Configuração global de testes.

Importa todos os modelos para garantir que Base.metadata tenha
todos os schemas registrados antes do create_all nos testes.
"""

# Importa todos os models para popular Base.metadata
import app.models  # noqa: F401 — garante que todas as tabelas estão registradas

# Configura a UF da empresa para SP em todos os testes
# (evita que .env local mude o comportamento dos testes)
import os
os.environ.setdefault("EMPRESA_UF", "SP")
os.environ.setdefault("EMPRESA_CRT", "3")
os.environ.setdefault("SECRET_KEY", "test-secret-key-nao-usar-em-producao")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
