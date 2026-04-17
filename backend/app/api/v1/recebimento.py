"""
Expedição de Entrada - recebimento de mercadorias.
Processa NF de fornecedor, calcula créditos fiscais e dá entrada no estoque.
"""
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.recebimento import NotaFiscalEntrada, ItemNotaFiscalEntrada
from app.services.estoque_service import movimentar
from app.services.fiscal import calcular_creditos_entrada
from app.core.config import settings
from app.api.v1.auth import get_current_user

router = APIRouter()


class ItemEntradaSchema(BaseModel):
    produto_id: int
    localizacao_id: int
    cfop: Optional[str] = None
    ncm: Optional[str] = None
    quantidade: Decimal
    preco_unitario: Decimal
    aliq_icms: Decimal = Decimal("0")
    aliq_ipi: Decimal = Decimal("0")
    aliq_pis: Decimal = Decimal("0")
    aliq_cofins: Decimal = Decimal("0")
    aprovado_qc: Optional[bool] = None
    quantidade_aprovada: Optional[Decimal] = None
    observacao_qc: Optional[str] = None


class NFEntradaCreate(BaseModel):
    tipo_entrada: str  # COMPRA_MP | COMPRA_REVENDA | RETORNO_BANHO | DEVOLUCAO_VENDA
    fornecedor_id: Optional[int] = None
    numero_nf: str
    serie: Optional[str] = None
    chave_acesso: Optional[str] = None
    data_emissao: date
    data_entrada: date
    cfop_entrada: Optional[str] = None
    valor_frete: Decimal = Decimal("0")
    pedido_compra_id: Optional[int] = None
    lote_beneficiamento_id: Optional[int] = None
    observacoes: Optional[str] = None
    itens: list[ItemEntradaSchema]


@router.get("/")
async def listar_entradas(skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(NotaFiscalEntrada).order_by(NotaFiscalEntrada.criado_em.desc()).offset(skip).limit(limit)
    )
    return r.scalars().all()


@router.get("/{nf_id}")
async def detalhar_entrada(nf_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(NotaFiscalEntrada).where(NotaFiscalEntrada.id == nf_id))
    nf = r.scalar_one_or_none()
    if not nf:
        raise HTTPException(404, "NF não encontrada")
    return nf


@router.post("/", status_code=201)
async def registrar_entrada(
    data: NFEntradaCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Registra a entrada de uma NF e dá entrada no estoque.
    Calcula créditos fiscais automaticamente conforme regime.
    """
    nf = NotaFiscalEntrada(
        tipo_entrada=data.tipo_entrada,
        fornecedor_id=data.fornecedor_id,
        numero_nf=data.numero_nf,
        serie=data.serie,
        chave_acesso=data.chave_acesso,
        data_emissao=data.data_emissao,
        data_entrada=data.data_entrada,
        cfop_entrada=data.cfop_entrada,
        valor_frete=data.valor_frete,
        pedido_compra_id=data.pedido_compra_id,
        lote_beneficiamento_id=data.lote_beneficiamento_id,
        observacoes=data.observacoes,
        status="LANCADA",
    )

    total_produtos = Decimal("0")
    total_icms = Decimal("0")
    total_ipi = Decimal("0")
    total_pis = Decimal("0")
    total_cofins = Decimal("0")
    total_credito_icms = Decimal("0")
    total_credito_ipi = Decimal("0")
    total_credito_pis = Decimal("0")
    total_credito_cofins = Decimal("0")

    for item_data in data.itens:
        # Usa quantidade aprovada se informada (QC), senão usa total
        qtd_entrada = item_data.quantidade_aprovada or item_data.quantidade
        valor_total = (qtd_entrada * item_data.preco_unitario).quantize(Decimal("0.01"))

        # Calcular impostos do item
        valor_icms_item = (valor_total * item_data.aliq_icms / 100).quantize(Decimal("0.01"))
        valor_ipi_item = (valor_total * item_data.aliq_ipi / 100).quantize(Decimal("0.01"))
        valor_pis_item = (valor_total * item_data.aliq_pis / 100).quantize(Decimal("0.01"))
        valor_cofins_item = (valor_total * item_data.aliq_cofins / 100).quantize(Decimal("0.01"))

        # Calcular créditos
        creditos = calcular_creditos_entrada(
            valor_produto=valor_total,
            aliq_icms=item_data.aliq_icms,
            aliq_ipi=item_data.aliq_ipi,
            aliq_pis=item_data.aliq_pis,
            aliq_cofins=item_data.aliq_cofins,
            tipo_entrada=data.tipo_entrada,
            crt_empresa=settings.EMPRESA_CRT,
        )

        item = ItemNotaFiscalEntrada(
            produto_id=item_data.produto_id,
            localizacao_id=item_data.localizacao_id,
            cfop=item_data.cfop,
            ncm=item_data.ncm,
            quantidade=qtd_entrada,
            preco_unitario=item_data.preco_unitario,
            valor_total=valor_total,
            aliq_icms=item_data.aliq_icms,
            valor_icms=valor_icms_item,
            aliq_ipi=item_data.aliq_ipi,
            valor_ipi=valor_ipi_item,
            aliq_pis=item_data.aliq_pis,
            valor_pis=valor_pis_item,
            aliq_cofins=item_data.aliq_cofins,
            valor_cofins=valor_cofins_item,
            aprovado_qc=item_data.aprovado_qc,
            quantidade_aprovada=item_data.quantidade_aprovada,
            observacao_qc=item_data.observacao_qc,
        )
        nf.itens.append(item)

        total_produtos += valor_total
        total_icms += valor_icms_item
        total_ipi += valor_ipi_item
        total_pis += valor_pis_item
        total_cofins += valor_cofins_item
        total_credito_icms += creditos["credito_icms"]
        total_credito_ipi += creditos["credito_ipi"]
        total_credito_pis += creditos["credito_pis"]
        total_credito_cofins += creditos["credito_cofins"]

    nf.valor_produtos = total_produtos
    nf.valor_icms = total_icms
    nf.valor_ipi = total_ipi
    nf.valor_pis = total_pis
    nf.valor_cofins = total_cofins
    nf.valor_total = total_produtos + data.valor_frete + total_ipi
    nf.credito_icms = total_credito_icms
    nf.credito_ipi = total_credito_ipi
    nf.credito_pis = total_credito_pis
    nf.credito_cofins = total_credito_cofins

    db.add(nf)
    await db.flush()  # Gera ID antes de movimentar estoque

    # Dar entrada no estoque
    tipo_mov = "ENTRADA_COMPRA" if "COMPRA" in data.tipo_entrada else "ENTRADA_RETORNO_BANHO"
    for item in nf.itens:
        await movimentar(
            db,
            produto_id=item.produto_id,
            localizacao_id=item.localizacao_id,
            tipo=tipo_mov,
            quantidade=item.quantidade,
            documento_tipo="NF_ENTRADA",
            documento_id=nf.id,
            documento_numero=nf.numero_nf,
            usuario_id=current_user.id,
        )

    await db.commit()
    await db.refresh(nf)
    return nf
