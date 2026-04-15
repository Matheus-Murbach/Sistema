from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.database import engine, Base
from app.api.v1 import router as api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Cria tabelas se não existirem (usar Alembic em produção)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Sistema ERP Industrial",
    description=(
        "ERP completo para controle de expedição, PCP, estoque, vendas, "
        "picking e fiscal (NF-e integrado)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sistema-erp"}
