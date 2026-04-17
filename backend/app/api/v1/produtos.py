from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

from app.core.database import get_db
from app.models.produto import Produto, UnidadeMedida
from app.integrations.ibpt import buscar_aliquotas_ncm
from app.api.v1.auth import get_current_user

router = APIRouter()


class ProdutoCreate(BaseModel):
    codigo: str
    codigo_barras: Optional[str] = None
    descricao: str
    tipo: str = "MATERIA_PRIMA"
    unidade_id: int
    ncm: Optional[str] = None
    cest: Optional[str] = None
    origem: str = "0"
    cst_icms: Optional[str] = None
    csosn: Optional[str] = None
    aliq_icms: Decimal = Decimal("0")
    cst_ipi: Optional[str] = None
    aliq_ipi: Decimal = Decimal("0")
    cst_pis: Optional[str] = None
    aliq_pis: Decimal = Decimal("0.65")
    cst_cofins: Optional[str] = None
    aliq_cofins: Decimal = Decimal("3.00")
    mva: Decimal = Decimal("0")
    preco_custo: Decimal = Decimal("0")
    preco_venda: Decimal = Decimal("0")
    estoque_minimo: Decimal = Decimal("0")
    estoque_maximo: Decimal = Decimal("0")
    observacoes: Optional[str] = None


class ProdutoUpdate(ProdutoCreate):
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    unidade_id: Optional[int] = None


@router.get("/unidades-medida")
async def listar_unidades(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UnidadeMedida).order_by(UnidadeMedida.codigo))
    return result.scalars().all()


@router.get("/")
async def listar_produtos(
    q: Optional[str] = Query(None, description="Busca por código, barras ou descrição"),
    tipo: Optional[str] = None,
    ativo: bool = True,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Produto).where(Produto.ativo == ativo)
    if tipo:
        stmt = stmt.where(Produto.tipo == tipo)
    if q:
        stmt = stmt.where(
            or_(
                Produto.codigo.ilike(f"%{q}%"),
                Produto.descricao.ilike(f"%{q}%"),
                Produto.codigo_barras == q,
            )
        )
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    produtos = result.scalars().all()
    return produtos


@router.get("/{produto_id}")
async def detalhar_produto(produto_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise HTTPException(404, "Produto não encontrado")
    return produto


@router.post("/", status_code=201)
async def criar_produto(
    data: ProdutoCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    produto = Produto(**data.model_dump())
    db.add(produto)
    await db.commit()
    await db.refresh(produto)
    return produto


@router.put("/{produto_id}")
async def atualizar_produto(
    produto_id: int,
    data: ProdutoUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise HTTPException(404, "Produto não encontrado")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(produto, k, v)
    await db.commit()
    await db.refresh(produto)
    return produto


@router.get("/{produto_id}/aliquotas-ncm")
async def buscar_aliquotas(produto_id: int, uf: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Busca alíquotas IBPT para o NCM do produto."""
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise HTTPException(404, "Produto não encontrado")
    if not produto.ncm:
        raise HTTPException(400, "Produto sem NCM cadastrado")
    aliquotas = await buscar_aliquotas_ncm(produto.ncm, uf)
    if not aliquotas:
        raise HTTPException(503, "Serviço IBPT indisponível ou token não configurado")
    return {
        "ncm": aliquotas.ncm,
        "descricao": aliquotas.descricao,
        "aliq_nacional": aliquotas.aliq_nacional,
        "aliq_importado": aliquotas.aliq_importado,
        "aliq_estadual": aliquotas.aliq_estadual,
        "aliq_municipal": aliquotas.aliq_municipal,
    }
