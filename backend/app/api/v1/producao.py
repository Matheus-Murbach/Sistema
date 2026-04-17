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
from sqlalchemy import select, func
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


class ConversaoRapidaSchema(BaseModel):
    produto_mp_id: int
    localizacao_mp_id: Optional[int] = None
    quantidade_mp: Decimal
    produto_pa_id: int
    localizacao_pa_id: Optional[int] = None
    quantidade_pa: Decimal
    observacao: Optional[str] = None


@router.post("/conversao-rapida", status_code=201)
async def conversao_rapida(
    data: ConversaoRapidaSchema,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Conversão instantânea MP → PA.
    Consome a MP e registra o PA no estoque em uma única operação.
    """
    from app.models.estoque import SaldoEstoque
    from datetime import date

    # Resolve localização da MP: usa a informada ou a 1ª disponível
    loc_mp = data.localizacao_mp_id
    if not loc_mp:
        r = await db.execute(
            select(SaldoEstoque).where(
                SaldoEstoque.produto_id == data.produto_mp_id,
                SaldoEstoque.status == "DISPONIVEL",
                SaldoEstoque.quantidade >= data.quantidade_mp,
            ).limit(1)
        )
        s = r.scalar_one_or_none()
        if not s:
            raise HTTPException(422, "Estoque insuficiente de matéria-prima")
        loc_mp = s.localizacao_id

    # Resolve localização do PA: usa a informada ou a mesma da MP
    loc_pa = data.localizacao_pa_id or loc_mp

    # Gera número único da OP
    count_r = await db.execute(select(func.count()).select_from(OrdemProducao))
    seq = (count_r.scalar() or 0) + 1
    numero = f"OP-{date.today().strftime('%Y%m%d')}-{seq}"

    # Cria OP já concluída para rastreabilidade
    op = OrdemProducao(
        numero=numero,
        produto_id=data.produto_pa_id,
        quantidade_planejada=data.quantidade_pa,
        quantidade_produzida=data.quantidade_pa,
        quantidade_refugo=Decimal("0"),
        localizacao_saida_id=loc_pa,
        status="CONCLUIDA",
        data_inicio=datetime.now(timezone.utc),
        data_conclusao=datetime.now(timezone.utc),
        observacoes=data.observacao,
    )
    op.itens.append(ItemOrdemProducao(
        produto_id=data.produto_mp_id,
        quantidade_necessaria=data.quantidade_mp,
        quantidade_consumida=data.quantidade_mp,
    ))
    db.add(op)
    await db.flush()

    # Consome MP
    await movimentar(
        db, data.produto_mp_id, loc_mp,
        tipo="SAIDA_PRODUCAO",
        quantidade=-data.quantidade_mp,
        status_estoque="DISPONIVEL",
        documento_tipo="ORDEM_PRODUCAO",
        documento_id=op.id,
        documento_numero=op.numero,
        usuario_id=current_user.id,
        observacao=data.observacao,
    )

    # Entrada do PA
    await movimentar(
        db, data.produto_pa_id, loc_pa,
        tipo="ENTRADA_PRODUCAO",
        quantidade=data.quantidade_pa,
        status_estoque="DISPONIVEL",
        documento_tipo="ORDEM_PRODUCAO",
        documento_id=op.id,
        documento_numero=op.numero,
        usuario_id=current_user.id,
        observacao=data.observacao,
    )

    await db.commit()
    return {
        "op_numero": op.numero,
        "produto_mp_id": data.produto_mp_id,
        "quantidade_mp_consumida": float(data.quantidade_mp),
        "produto_pa_id": data.produto_pa_id,
        "quantidade_pa_produzida": float(data.quantidade_pa),
    }


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
    count_r = await db.execute(select(func.count()).select_from(OrdemProducao))
    seq = (count_r.scalar() or 0) + 1
    numero = f"OP-{date.today().strftime('%Y%m%d')}-{seq}"

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
