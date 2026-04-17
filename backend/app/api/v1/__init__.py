from fastapi import APIRouter
from app.api.v1 import (
    auth,
    produtos,
    parceiros,
    estoque,
    compras,
    recebimento,
    beneficiamento,
    producao,
    vendas,
    picking,
    expedicao,
    dashboard,
)

router = APIRouter()
router.include_router(auth.router,           prefix="/auth",           tags=["Autenticação"])
router.include_router(produtos.router,       prefix="/produtos",       tags=["Produtos"])
router.include_router(parceiros.router,      prefix="/parceiros",      tags=["Parceiros"])
router.include_router(estoque.router,        prefix="/estoque",        tags=["Estoque"])
router.include_router(compras.router,        prefix="/compras",        tags=["Compras"])
router.include_router(recebimento.router,    prefix="/recebimento",    tags=["Recebimento"])
router.include_router(beneficiamento.router, prefix="/beneficiamento", tags=["Beneficiamento"])
router.include_router(producao.router,       prefix="/producao",       tags=["PCP"])
router.include_router(vendas.router,         prefix="/vendas",         tags=["Vendas"])
router.include_router(picking.router,        prefix="/picking",        tags=["Picking"])
router.include_router(expedicao.router,      prefix="/expedicao",      tags=["Expedição"])
router.include_router(dashboard.router,      prefix="/dashboard",      tags=["Dashboard"])
