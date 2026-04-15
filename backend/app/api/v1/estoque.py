from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

from app.core.database import get_db
from app.models.estoque import LocalizacaoEstoque, SaldoEstoque, MovimentacaoEstoque
from app.models.produto import Produto
from app.api.v1.auth import get_current_user

router = APIRouter()


# --- Localizações ---

class LocalizacaoCreate(BaseModel):
    codigo: str
    descricao: Optional[str] = None
    corredor: Optional[str] = None
    prateleira: Optional[str] = None
    bin: Optional[str] = None


@router.get("/localizacoes")
async def listar_localizacoes(db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(LocalizacaoEstoque).where(LocalizacaoEstoque.ativa == True))
    return r.scalars().all()


@router.post("/localizacoes", status_code=201)
async def criar_localizacao(data: LocalizacaoCreate, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    loc = LocalizacaoEstoque(**data.model_dump())
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


# --- Saldos ---

@router.get("/saldos")
async def listar_saldos(
    produto_id: Optional[int] = None,
    localizacao_id: Optional[int] = None,
    status: Optional[str] = None,
    apenas_positivos: bool = True,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SaldoEstoque)
    if produto_id:
        stmt = stmt.where(SaldoEstoque.produto_id == produto_id)
    if localizacao_id:
        stmt = stmt.where(SaldoEstoque.localizacao_id == localizacao_id)
    if status:
        stmt = stmt.where(SaldoEstoque.status == status)
    if apenas_positivos:
        stmt = stmt.where(SaldoEstoque.quantidade > 0)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.get("/pronta-entrega")
async def pronta_entrega(
    q: Optional[str] = Query(None, description="Filtrar por código/descrição"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retorna produtos com estoque DISPONÍVEL (sem reservas).
    Usado pela equipe de vendas para saber o que pode ser entregue imediatamente.
    """
    stmt = (
        select(
            Produto.id,
            Produto.codigo,
            Produto.descricao,
            func.sum(SaldoEstoque.quantidade).label("quantidade_disponivel"),
        )
        .join(SaldoEstoque, SaldoEstoque.produto_id == Produto.id)
        .where(
            SaldoEstoque.status == "DISPONIVEL",
            SaldoEstoque.quantidade > 0,
            Produto.ativo == True,
        )
        .group_by(Produto.id, Produto.codigo, Produto.descricao)
    )
    if q:
        stmt = stmt.where(
            (Produto.codigo.ilike(f"%{q}%")) | (Produto.descricao.ilike(f"%{q}%"))
        )
    r = await db.execute(stmt)
    return [
        {
            "produto_id": row.id,
            "codigo": row.codigo,
            "descricao": row.descricao,
            "quantidade_disponivel": row.quantidade_disponivel,
        }
        for row in r.all()
    ]


@router.get("/alertas-estoque-minimo")
async def alertas_estoque_minimo(db: AsyncSession = Depends(get_db)):
    """
    Retorna produtos cujo saldo disponível total está abaixo do estoque mínimo.
    """
    subq = (
        select(
            SaldoEstoque.produto_id,
            func.sum(SaldoEstoque.quantidade).label("total_disponivel"),
        )
        .where(SaldoEstoque.status == "DISPONIVEL")
        .group_by(SaldoEstoque.produto_id)
        .subquery()
    )
    stmt = (
        select(Produto, subq.c.total_disponivel)
        .outerjoin(subq, subq.c.produto_id == Produto.id)
        .where(
            Produto.ativo == True,
            Produto.estoque_minimo > 0,
            (subq.c.total_disponivel == None) | (subq.c.total_disponivel < Produto.estoque_minimo),
        )
    )
    r = await db.execute(stmt)
    rows = r.all()
    return [
        {
            "produto_id": row.Produto.id,
            "codigo": row.Produto.codigo,
            "descricao": row.Produto.descricao,
            "estoque_minimo": float(row.Produto.estoque_minimo),
            "estoque_atual": float(row.total_disponivel or 0),
            "deficit": float(row.Produto.estoque_minimo - (row.total_disponivel or 0)),
        }
        for row in rows
    ]


@router.get("/movimentacoes")
async def listar_movimentacoes(
    produto_id: Optional[int] = None,
    tipo: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(MovimentacaoEstoque).order_by(MovimentacaoEstoque.criado_em.desc())
    if produto_id:
        stmt = stmt.where(MovimentacaoEstoque.produto_id == produto_id)
    if tipo:
        stmt = stmt.where(MovimentacaoEstoque.tipo == tipo)
    stmt = stmt.offset(skip).limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()
