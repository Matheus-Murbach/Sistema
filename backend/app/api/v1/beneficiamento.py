"""
Módulo de Beneficiamento Externo (Banho).

Fluxo:
  1. Criar lote → selecionar itens do estoque a enviar
  2. Emitir NF de Remessa (CFOP 5901/6901) via Focus NF-e
  3. Baixar do estoque DISPONIVEL → criar saldo EM_BENEFICIAMENTO
  4. No retorno: registrar quantidades retornadas e rejeitadas
  5. Entrada do produto beneficiado no estoque DISPONIVEL
"""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.beneficiamento import LoteBeneficiamento, ItemLoteBeneficiamento
from app.services.estoque_service import movimentar
from app.api.v1.auth import get_current_user

router = APIRouter()


class ItemLoteSchema(BaseModel):
    produto_enviado_id: int
    produto_retorno_id: Optional[int] = None
    localizacao_saida_id: int
    localizacao_retorno_id: Optional[int] = None
    quantidade_enviada: Decimal


class LoteCreate(BaseModel):
    prestador_id: int
    tipo_beneficiamento: Optional[str] = None
    data_remessa: date
    data_previsao_retorno: Optional[date] = None
    cfop_remessa: str = "5901"
    cfop_retorno: str = "5902"
    observacoes: Optional[str] = None
    itens: list[ItemLoteSchema]


class RetornoItemSchema(BaseModel):
    item_id: int
    quantidade_retornada: Decimal
    quantidade_rejeitada: Decimal = Decimal("0")
    localizacao_retorno_id: Optional[int] = None
    observacao: Optional[str] = None


class RetornoLoteSchema(BaseModel):
    data_retorno: date
    nf_retorno_numero: Optional[str] = None
    nf_retorno_chave: Optional[str] = None
    valor_servico: Decimal = Decimal("0")
    valor_insumos: Decimal = Decimal("0")
    itens: list[RetornoItemSchema]


@router.get("/")
async def listar_lotes(status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(LoteBeneficiamento).order_by(LoteBeneficiamento.data_remessa.desc())
    if status:
        stmt = stmt.where(LoteBeneficiamento.status == status)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.get("/em-transito")
async def lotes_em_transito(db: AsyncSession = Depends(get_db)):
    """Lotes enviados para banho que ainda não retornaram."""
    r = await db.execute(
        select(LoteBeneficiamento).where(
            LoteBeneficiamento.status.in_(["ENVIADO", "AGUARDANDO_RETORNO", "RETORNADO_PARCIAL"])
        )
    )
    return r.scalars().all()


@router.get("/{lote_id}")
async def detalhar_lote(lote_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(LoteBeneficiamento).where(LoteBeneficiamento.id == lote_id))
    lote = r.scalar_one_or_none()
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    return lote


@router.post("/", status_code=201)
async def criar_lote(
    data: LoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cria lote e baixa itens do estoque DISPONIVEL para EM_BENEFICIAMENTO."""
    from app.core.config import settings
    import datetime

    # Gera número do lote
    hoje = datetime.date.today()
    numero = f"BNF-{hoje.strftime('%Y%m%d')}-{data.prestador_id}"

    lote = LoteBeneficiamento(
        numero=numero,
        prestador_id=data.prestador_id,
        tipo_beneficiamento=data.tipo_beneficiamento,
        data_remessa=data.data_remessa,
        data_previsao_retorno=data.data_previsao_retorno,
        cfop_remessa=data.cfop_remessa,
        cfop_retorno=data.cfop_retorno,
        status="ABERTO",
        observacoes=data.observacoes,
    )

    for item_data in data.itens:
        item = ItemLoteBeneficiamento(
            produto_enviado_id=item_data.produto_enviado_id,
            produto_retorno_id=item_data.produto_retorno_id,
            localizacao_saida_id=item_data.localizacao_saida_id,
            localizacao_retorno_id=item_data.localizacao_retorno_id,
            quantidade_enviada=item_data.quantidade_enviada,
        )
        lote.itens.append(item)

    db.add(lote)
    await db.flush()

    # Movimenta estoque: DISPONIVEL → EM_BENEFICIAMENTO
    for item in lote.itens:
        # Sai do DISPONIVEL
        await movimentar(
            db, item.produto_enviado_id, item.localizacao_saida_id,
            tipo="SAIDA_REMESSA_BANHO",
            quantidade=-item.quantidade_enviada,
            status_estoque="DISPONIVEL",
            documento_tipo="LOTE_BENEFICIAMENTO",
            documento_id=lote.id,
            documento_numero=lote.numero,
            usuario_id=current_user.id,
        )
        # Entra em EM_BENEFICIAMENTO
        await movimentar(
            db, item.produto_enviado_id, item.localizacao_saida_id,
            tipo="ENTRADA_EM_BENEFICIAMENTO",
            quantidade=item.quantidade_enviada,
            status_estoque="EM_BENEFICIAMENTO",
            documento_tipo="LOTE_BENEFICIAMENTO",
            documento_id=lote.id,
            documento_numero=lote.numero,
        )

    lote.status = "ENVIADO"
    await db.commit()
    await db.refresh(lote)
    return lote


@router.post("/{lote_id}/retorno", status_code=200)
async def registrar_retorno(
    lote_id: int,
    data: RetornoLoteSchema,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Registra o retorno do beneficiamento.
    - Baixa EM_BENEFICIAMENTO
    - Dá entrada do produto beneficiado em DISPONIVEL
    - Registra perdas/rejeições
    """
    r = await db.execute(
        select(LoteBeneficiamento)
        .options(selectinload(LoteBeneficiamento.itens))
        .where(LoteBeneficiamento.id == lote_id)
    )
    lote = r.scalar_one_or_none()
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    if lote.status not in ("ENVIADO", "AGUARDANDO_RETORNO", "RETORNADO_PARCIAL"):
        raise HTTPException(422, f"Lote não pode receber retorno no status '{lote.status}'")

    lote.data_retorno_real = data.data_retorno
    lote.nf_retorno_numero = data.nf_retorno_numero
    lote.nf_retorno_chave = data.nf_retorno_chave
    lote.valor_servico = data.valor_servico
    lote.valor_insumos = data.valor_insumos

    for retorno in data.itens:
        r2 = await db.execute(
            select(ItemLoteBeneficiamento).where(ItemLoteBeneficiamento.id == retorno.item_id)
        )
        item = r2.scalar_one_or_none()
        if not item or item.lote_id != lote_id:
            raise HTTPException(404, f"Item {retorno.item_id} não encontrado no lote")

        item.quantidade_retornada = retorno.quantidade_retornada
        item.quantidade_rejeitada = retorno.quantidade_rejeitada
        item.retornado = True
        if retorno.observacao:
            item.observacao = retorno.observacao

        loc_retorno = retorno.localizacao_retorno_id or item.localizacao_retorno_id or item.localizacao_saida_id
        produto_retorno = item.produto_retorno_id or item.produto_enviado_id

        # Baixa EM_BENEFICIAMENTO (quantidade enviada total)
        await movimentar(
            db, item.produto_enviado_id, item.localizacao_saida_id,
            tipo="SAIDA_RETORNO_BANHO",
            quantidade=-item.quantidade_enviada,
            status_estoque="EM_BENEFICIAMENTO",
            documento_tipo="LOTE_BENEFICIAMENTO",
            documento_id=lote.id,
            documento_numero=lote.numero,
            usuario_id=current_user.id,
        )

        # Entra produto beneficiado no DISPONIVEL (apenas quantidade aprovada)
        if retorno.quantidade_retornada > 0:
            await movimentar(
                db, produto_retorno, loc_retorno,
                tipo="ENTRADA_RETORNO_BANHO",
                quantidade=retorno.quantidade_retornada,
                status_estoque="DISPONIVEL",
                documento_tipo="LOTE_BENEFICIAMENTO",
                documento_id=lote.id,
                documento_numero=lote.numero,
                usuario_id=current_user.id,
            )

    # Verifica se todos os itens foram retornados
    total_enviado = sum(i.quantidade_enviada for i in lote.itens)
    total_retornado = sum(i.quantidade_retornada for i in lote.itens if i.retornado)
    lote.status = "RETORNADO" if total_retornado >= total_enviado * Decimal("0.99") else "RETORNADO_PARCIAL"

    await db.commit()
    await db.refresh(lote)
    return {"lote_id": lote.id, "status": lote.status, "total_retornado": float(total_retornado)}
