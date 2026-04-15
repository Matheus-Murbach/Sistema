"""
PCP - Planejamento e Controle da Produção.

Fluxo de alta rotatividade:
  1. POST /producao/           → Cria OP (ABERTA)
  2. POST /producao/{id}/iniciar → Consome MP imediatamente do estoque (EM_PRODUCAO)
  3. POST /producao/{id}/concluir → Registra produzido + refugo, entra no estoque (CONCLUIDA)
"""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import re

from app.core.database import get_db
from app.models.producao import OrdemProducao, ItemOrdemProducao, ConsumoMaterial
from app.services.estoque_service import movimentar
from app.api.v1.auth import get_current_user

router = APIRouter()


class ItemBOMSchema(BaseModel):
    produto_id: int
    quantidade_necessaria: Decimal


class OPCreate(BaseModel):
    produto_id: int
    maquina_id: Optional[int] = None
    quantidade_planejada: Decimal
    data_planejada: Optional[datetime] = None
    localizacao_saida_id: Optional[int] = None
    pedido_venda_id: Optional[int] = None
    observacoes: Optional[str] = None
    materiais: list[ItemBOMSchema]


class ConsumoSchema(BaseModel):
    produto_id: int
    localizacao_id: int
    quantidade: Decimal


class ConcluirOPSchema(BaseModel):
    quantidade_produzida: Decimal
    quantidade_refugo: Decimal = Decimal("0")
    localizacao_saida_id: Optional[int] = None


@router.get("/")
async def listar_ops(
    status: Optional[str] = None,
    maquina_id: Optional[int] = None,
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(OrdemProducao).order_by(OrdemProducao.criado_em.desc())
    if status:
        stmt = stmt.where(OrdemProducao.status == status)
    if maquina_id:
        stmt = stmt.where(OrdemProducao.maquina_id == maquina_id)
    stmt = stmt.offset(skip).limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.get("/{op_id}")
async def detalhar_op(op_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(OrdemProducao).where(OrdemProducao.id == op_id))
    op = r.scalar_one_or_none()
    if not op:
        raise HTTPException(404, "OP não encontrada")
    return op


@router.post("/", status_code=201)
async def criar_op(
    data: OPCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from datetime import date
    numero = f"OP-{date.today().strftime('%Y%m%d')}-{data.produto_id}"

    op = OrdemProducao(
        numero=numero,
        produto_id=data.produto_id,
        maquina_id=data.maquina_id,
        quantidade_planejada=data.quantidade_planejada,
        data_planejada=data.data_planejada,
        localizacao_saida_id=data.localizacao_saida_id,
        pedido_venda_id=data.pedido_venda_id,
        observacoes=data.observacoes,
        status="ABERTA",
    )
    for m in data.materiais:
        op.itens.append(ItemOrdemProducao(
            produto_id=m.produto_id,
            quantidade_necessaria=m.quantidade_necessaria,
        ))
    db.add(op)
    await db.commit()
    await db.refresh(op)
    return op


@router.post("/{op_id}/iniciar")
async def iniciar_op(
    op_id: int,
    consumos: list[ConsumoSchema],
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Inicia a OP e consome a matéria-prima do estoque imediatamente.
    Esta é a operação de 'alta rotatividade': assim que o operador
    pega o material, o sistema já registra o consumo.
    """
    r = await db.execute(select(OrdemProducao).where(OrdemProducao.id == op_id))
    op = r.scalar_one_or_none()
    if not op:
        raise HTTPException(404, "OP não encontrada")
    if op.status != "ABERTA":
        raise HTTPException(422, f"OP não pode ser iniciada no status '{op.status}'")

    op.status = "EM_PRODUCAO"
    op.data_inicio = datetime.now(timezone.utc)

    for c in consumos:
        await movimentar(
            db, c.produto_id, c.localizacao_id,
            tipo="SAIDA_PRODUCAO",
            quantidade=-c.quantidade,
            status_estoque="DISPONIVEL",
            documento_tipo="ORDEM_PRODUCAO",
            documento_id=op.id,
            documento_numero=op.numero,
            usuario_id=current_user.id,
        )
        consumo = ConsumoMaterial(
            op_id=op.id,
            produto_id=c.produto_id,
            localizacao_id=c.localizacao_id,
            quantidade=c.quantidade,
            usuario_id=current_user.id,
        )
        db.add(consumo)

        # Atualiza quantidade consumida no BOM
        r2 = await db.execute(
            select(ItemOrdemProducao).where(
                ItemOrdemProducao.op_id == op.id,
                ItemOrdemProducao.produto_id == c.produto_id,
            )
        )
        bom_item = r2.scalar_one_or_none()
        if bom_item:
            bom_item.quantidade_consumida += c.quantidade

    await db.commit()
    return {"op_id": op.id, "status": op.status, "mensagem": "OP iniciada, materiais consumidos do estoque"}


@router.post("/{op_id}/concluir")
async def concluir_op(
    op_id: int,
    data: ConcluirOPSchema,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Conclui a OP registrando quantidade produzida e refugo.
    Dá entrada do produto acabado no estoque.
    """
    r = await db.execute(select(OrdemProducao).where(OrdemProducao.id == op_id))
    op = r.scalar_one_or_none()
    if not op:
        raise HTTPException(404, "OP não encontrada")
    if op.status != "EM_PRODUCAO":
        raise HTTPException(422, f"OP não pode ser concluída no status '{op.status}'")

    op.quantidade_produzida = data.quantidade_produzida
    op.quantidade_refugo = data.quantidade_refugo
    op.status = "CONCLUIDA"
    op.data_conclusao = datetime.now(timezone.utc)

    loc_saida = data.localizacao_saida_id or op.localizacao_saida_id
    if not loc_saida:
        raise HTTPException(422, "Localização de saída não informada")

    # Entrada do produto acabado no estoque
    if data.quantidade_produzida > 0:
        await movimentar(
            db, op.produto_id, loc_saida,
            tipo="ENTRADA_PRODUCAO",
            quantidade=data.quantidade_produzida,
            status_estoque="DISPONIVEL",
            documento_tipo="ORDEM_PRODUCAO",
            documento_id=op.id,
            documento_numero=op.numero,
            usuario_id=current_user.id,
        )

    yield_real = (data.quantidade_produzida / op.quantidade_planejada * 100) if op.quantidade_planejada > 0 else 0

    await db.commit()
    return {
        "op_id": op.id,
        "status": op.status,
        "quantidade_produzida": float(data.quantidade_produzida),
        "quantidade_refugo": float(data.quantidade_refugo),
        "yield_percent": round(float(yield_real), 2),
    }
