from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.venda import PedidoVenda, ItemPedidoVenda
from app.models.produto import Produto
from app.models.parceiro import Cliente
from app.services.estoque_service import get_saldo_total_disponivel, reservar_estoque
from app.services.fiscal import calcular_impostos_saida
from app.core.config import settings
from app.api.v1.auth import get_current_user

router = APIRouter()


class ItemVendaSchema(BaseModel):
    produto_id: int
    quantidade: Decimal
    preco_unitario: Decimal
    desconto_percent: Decimal = Decimal("0")
    localizacao_id: Optional[int] = None


class PedidoVendaCreate(BaseModel):
    cliente_id: int
    data_emissao: date
    data_previsao_entrega: Optional[date] = None
    condicao_pagamento: Optional[str] = None
    transportadora: Optional[str] = None
    frete_por_conta: str = "0"
    valor_frete: Decimal = Decimal("0")
    observacoes: Optional[str] = None
    itens: list[ItemVendaSchema]


@router.get("/")
async def listar_pedidos(
    status: Optional[str] = None,
    cliente_id: Optional[int] = None,
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PedidoVenda).order_by(PedidoVenda.criado_em.desc())
    if status:
        stmt = stmt.where(PedidoVenda.status == status)
    if cliente_id:
        stmt = stmt.where(PedidoVenda.cliente_id == cliente_id)
    stmt = stmt.offset(skip).limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.get("/{pedido_id}")
async def detalhar_pedido(pedido_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(PedidoVenda)
        .options(selectinload(PedidoVenda.itens))
        .where(PedidoVenda.id == pedido_id)
    )
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    return pedido


@router.post("/", status_code=201)
async def criar_pedido(
    data: PedidoVendaCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from sqlalchemy import func
    count_r = await db.execute(select(func.count()).select_from(PedidoVenda))
    seq = (count_r.scalar() or 0) + 1
    numero = f"PV-{date.today().strftime('%Y%m%d')}-{seq}"

    # Busca cliente para dados fiscais
    r = await db.execute(select(Cliente).where(Cliente.id == data.cliente_id))
    cliente = r.scalar_one_or_none()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")

    pedido = PedidoVenda(
        numero=numero,
        cliente_id=data.cliente_id,
        status="ORCAMENTO",
        data_emissao=data.data_emissao,
        data_previsao_entrega=data.data_previsao_entrega,
        condicao_pagamento=data.condicao_pagamento,
        transportadora=data.transportadora,
        frete_por_conta=data.frete_por_conta,
        valor_frete=data.valor_frete,
        observacoes=data.observacoes,
    )

    total_produtos = Decimal("0")
    for item_data in data.itens:
        r2 = await db.execute(select(Produto).where(Produto.id == item_data.produto_id))
        produto = r2.scalar_one_or_none()
        if not produto:
            raise HTTPException(404, f"Produto {item_data.produto_id} não encontrado")

        desconto_valor = item_data.preco_unitario * item_data.desconto_percent / 100
        preco_liquido = item_data.preco_unitario - desconto_valor
        valor_total = (preco_liquido * item_data.quantidade).quantize(Decimal("0.01"))

        # Calcular impostos de saída
        impostos = calcular_impostos_saida(
            valor_produto=valor_total,
            aliq_icms=produto.aliq_icms,
            aliq_ipi=produto.aliq_ipi,
            aliq_pis=produto.aliq_pis,
            aliq_cofins=produto.aliq_cofins,
            mva=produto.mva,
            uf_destino=cliente.uf or settings.EMPRESA_UF,
            consumidor_final=cliente.consumidor_final,
            crt_empresa=settings.EMPRESA_CRT,
            cst_icms=produto.cst_icms or "00",
            csosn=produto.csosn,
            cst_ipi=produto.cst_ipi or "99",
            cst_pis=produto.cst_pis or "01",
            cst_cofins=produto.cst_cofins or "01",
        )

        # Verifica disponibilidade
        disponivel = await get_saldo_total_disponivel(db, item_data.produto_id)

        item = ItemPedidoVenda(
            produto_id=item_data.produto_id,
            quantidade=item_data.quantidade,
            preco_unitario=item_data.preco_unitario,
            desconto_percent=item_data.desconto_percent,
            valor_total=valor_total,
            aliq_icms=impostos.aliq_icms,
            valor_icms=impostos.valor_icms,
            aliq_ipi=impostos.aliq_ipi,
            valor_ipi=impostos.valor_ipi,
            aliq_pis=impostos.aliq_pis,
            valor_pis=impostos.valor_pis,
            aliq_cofins=impostos.aliq_cofins,
            valor_cofins=impostos.valor_cofins,
            valor_icms_st=impostos.valor_icms_st,
            valor_difal=impostos.valor_difal,
            disponivel=disponivel >= item_data.quantidade,
        )
        pedido.itens.append(item)
        total_produtos += valor_total

    pedido.valor_produtos = total_produtos
    pedido.valor_total = total_produtos + data.valor_frete

    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return pedido


@router.post("/{pedido_id}/confirmar")
async def confirmar_pedido(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Confirma o pedido de orçamento → CONFIRMADO.
    Reserva automaticamente o estoque disponível para cada item.
    """
    r = await db.execute(
        select(PedidoVenda)
        .options(selectinload(PedidoVenda.itens))
        .where(PedidoVenda.id == pedido_id)
    )
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if pedido.status != "ORCAMENTO":
        raise HTTPException(422, f"Pedido já está '{pedido.status}', não pode ser confirmado novamente")

    # Reserva estoque para cada item com localização definida
    reservas = []
    for item in pedido.itens:
        # Busca primeiro saldo disponível para o produto
        from app.models.estoque import SaldoEstoque
        r2 = await db.execute(
            select(SaldoEstoque).where(
                SaldoEstoque.produto_id == item.produto_id,
                SaldoEstoque.status == "DISPONIVEL",
                SaldoEstoque.quantidade >= item.quantidade,
            ).limit(1)
        )
        saldo = r2.scalar_one_or_none()
        if saldo:
            await reservar_estoque(db, item.produto_id, saldo.localizacao_id, item.quantidade, pedido_id)
            reservas.append(item.produto_id)

    pedido.status = "CONFIRMADO"
    await db.commit()
    return {
        "pedido_id": pedido.id,
        "status": pedido.status,
        "itens_reservados": len(reservas),
    }


@router.post("/{pedido_id}/cancelar")
async def cancelar_pedido(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.estoque_service import liberar_reserva
    r = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if pedido.status in ("EXPEDIDO",):
        raise HTTPException(422, "Pedido expedido não pode ser cancelado diretamente")

    await liberar_reserva(db, pedido_id, consumir=False)
    pedido.status = "CANCELADO"
    await db.commit()
    return {"pedido_id": pedido.id, "status": pedido.status}
