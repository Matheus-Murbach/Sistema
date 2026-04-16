from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.compra import PedidoCompra, ItemPedidoCompra
from app.api.v1.auth import get_current_user

router = APIRouter()


class ItemCompraSchema(BaseModel):
    produto_id: int
    quantidade: Decimal
    preco_unitario: Decimal


class PedidoCompraCreate(BaseModel):
    fornecedor_id: int
    data_emissao: date
    data_previsao: Optional[date] = None
    condicao_pagamento: Optional[str] = None
    observacoes: Optional[str] = None
    itens: list[ItemCompraSchema]


@router.get("/")
async def listar_pedidos(status: Optional[str] = None, skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(PedidoCompra).order_by(PedidoCompra.criado_em.desc())
    if status:
        stmt = stmt.where(PedidoCompra.status == status)
    stmt = stmt.offset(skip).limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.post("/", status_code=201)
async def criar_pedido(
    data: PedidoCompraCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    count_r = await db.execute(select(func.count()).select_from(PedidoCompra))
    seq = (count_r.scalar() or 0) + 1
    numero = f"PC-{date.today().strftime('%Y%m%d')}-{seq}"

    pedido = PedidoCompra(
        numero=numero,
        fornecedor_id=data.fornecedor_id,
        data_emissao=data.data_emissao,
        data_previsao=data.data_previsao,
        condicao_pagamento=data.condicao_pagamento,
        observacoes=data.observacoes,
        status="ABERTO",
    )
    total = Decimal("0")
    for item_data in data.itens:
        vt = (item_data.quantidade * item_data.preco_unitario).quantize(Decimal("0.01"))
        item = ItemPedidoCompra(
            produto_id=item_data.produto_id,
            quantidade=item_data.quantidade,
            preco_unitario=item_data.preco_unitario,
            valor_total=vt,
        )
        pedido.itens.append(item)
        total += vt
    pedido.valor_total = total

    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return pedido


@router.put("/{pedido_id}/status")
async def atualizar_status(
    pedido_id: int,
    novo_status: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    r = await db.execute(select(PedidoCompra).where(PedidoCompra.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    pedido.status = novo_status
    await db.commit()
    return {"id": pedido.id, "status": pedido.status}
