"""
Expedição de Saída - emissão de NF-e e baixa definitiva do estoque.

Fluxo:
  1. Picking concluído (status PICKING_OK)
  2. POST /expedicao/{pedido_id}/emitir → calcula impostos, monta NF, transmite SEFAZ
  3. Celery task monitora autorização e baixa estoque definitivamente
"""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.expedicao import NotaFiscalSaida, ItemNotaFiscalSaida
from app.models.venda import PedidoVenda, ItemPedidoVenda
from app.models.parceiro import Cliente
from app.models.produto import Produto
from app.services.fiscal import calcular_impostos_saida
from app.services.nfe_builder import build_payload_nfe
from app.services.estoque_service import liberar_reserva
from app.integrations.focus_nfe import focus_nfe
from app.core.config import settings
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.get("/")
async def listar_nfs_saida(
    status: Optional[str] = None,
    skip: int = 0, limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(NotaFiscalSaida).order_by(NotaFiscalSaida.criado_em.desc())
    if status:
        stmt = stmt.where(NotaFiscalSaida.status_sefaz == status)
    stmt = stmt.offset(skip).limit(limit)
    r = await db.execute(stmt)
    return r.scalars().all()


@router.get("/{pedido_id}/preview")
async def preview_fiscal(pedido_id: int, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    """Retorna o breakdown fiscal por item sem emitir a NF-e."""
    r = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")

    r2 = await db.execute(select(Cliente).where(Cliente.id == pedido.cliente_id))
    cliente = r2.scalar_one_or_none()

    r3 = await db.execute(select(ItemPedidoVenda).where(ItemPedidoVenda.pedido_id == pedido_id))
    itens_pv = r3.scalars().all()

    itens_preview = []
    totais = {"produtos": 0.0, "icms": 0.0, "ipi": 0.0, "pis": 0.0, "cofins": 0.0, "st": 0.0, "difal": 0.0}

    for item in itens_pv:
        r4 = await db.execute(select(Produto).where(Produto.id == item.produto_id))
        produto = r4.scalar_one_or_none()

        impostos = calcular_impostos_saida(
            valor_produto=item.valor_total,
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

        itens_preview.append({
            "produto_id": produto.id,
            "codigo": produto.codigo,
            "descricao": produto.descricao,
            "quantidade": float(item.quantidade),
            "preco_unitario": float(item.preco_unitario),
            "valor_bruto": float(item.valor_total),
            "cfop": impostos.cfop,
            "aliq_icms": float(impostos.aliq_icms),
            "valor_icms": float(impostos.valor_icms),
            "aliq_ipi": float(impostos.aliq_ipi),
            "valor_ipi": float(impostos.valor_ipi),
            "aliq_pis": float(impostos.aliq_pis),
            "valor_pis": float(impostos.valor_pis),
            "aliq_cofins": float(impostos.aliq_cofins),
            "valor_cofins": float(impostos.valor_cofins),
            "valor_icms_st": float(impostos.valor_icms_st),
            "valor_difal": float(impostos.valor_difal),
        })

        totais["produtos"] += float(item.valor_total)
        totais["icms"] += float(impostos.valor_icms)
        totais["ipi"] += float(impostos.valor_ipi)
        totais["pis"] += float(impostos.valor_pis)
        totais["cofins"] += float(impostos.valor_cofins)
        totais["st"] += float(impostos.valor_icms_st)
        totais["difal"] += float(impostos.valor_difal)

    totais["total_nf"] = totais["produtos"] + float(pedido.valor_frete) + totais["ipi"]

    return {"pedido_id": pedido_id, "numero": pedido.numero, "itens": itens_preview, "totais": totais}


@router.post("/{pedido_id}/emitir", status_code=201)
async def emitir_nfe_saida(
    pedido_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Emite a NF-e de saída para o pedido.
    Requer que o pedido esteja em status PICKING_OK.
    Transmite ao SEFAZ via Focus NF-e (async via background task).
    """
    r = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if pedido.status not in ("PICKING_OK", "CONFIRMADO"):
        raise HTTPException(422, f"Pedido no status '{pedido.status}' não pode ser expedido")

    r2 = await db.execute(select(Cliente).where(Cliente.id == pedido.cliente_id))
    cliente = r2.scalar_one_or_none()

    # Cria NF no banco em status RASCUNHO
    nf = NotaFiscalSaida(
        pedido_venda_id=pedido_id,
        cliente_id=pedido.cliente_id,
        natureza_operacao="VENDA DE MERCADORIA",
        finalidade="1",
        tipo_operacao="1",
        status_sefaz="RASCUNHO",
        data_emissao=datetime.now(timezone.utc),
        data_saida=datetime.now(timezone.utc),
        valor_frete=pedido.valor_frete,
    )

    r3 = await db.execute(select(ItemPedidoVenda).where(ItemPedidoVenda.pedido_id == pedido_id))
    itens_pedido = r3.scalars().all()

    itens_para_nfe = []
    total_produtos = Decimal("0")
    total_icms = Decimal("0")
    total_ipi = Decimal("0")
    total_pis = Decimal("0")
    total_cofins = Decimal("0")
    total_st = Decimal("0")
    total_difal = Decimal("0")

    for item_pv in itens_pedido:
        r4 = await db.execute(select(Produto).where(Produto.id == item_pv.produto_id))
        produto = r4.scalar_one_or_none()

        impostos = calcular_impostos_saida(
            valor_produto=item_pv.valor_total,
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

        item_nf = ItemNotaFiscalSaida(
            produto_id=produto.id,
            cfop=impostos.cfop,
            ncm=produto.ncm,
            cst_icms=impostos.cst_icms,
            cst_ipi=impostos.cst_ipi,
            cst_pis=impostos.cst_pis,
            cst_cofins=impostos.cst_cofins,
            quantidade=item_pv.quantidade,
            preco_unitario=item_pv.preco_unitario,
            valor_bruto=item_pv.valor_total,
            valor_desconto=Decimal("0"),
            base_icms=impostos.base_icms,
            aliq_icms=impostos.aliq_icms,
            valor_icms=impostos.valor_icms,
            valor_icms_st=impostos.valor_icms_st,
            base_ipi=impostos.base_ipi,
            aliq_ipi=impostos.aliq_ipi,
            valor_ipi=impostos.valor_ipi,
            base_pis=impostos.base_pis,
            aliq_pis=impostos.aliq_pis,
            valor_pis=impostos.valor_pis,
            base_cofins=impostos.base_cofins,
            aliq_cofins=impostos.aliq_cofins,
            valor_cofins=impostos.valor_cofins,
        )
        nf.itens.append(item_nf)

        itens_para_nfe.append({
            "produto": produto,
            "impostos": impostos,
            "quantidade": item_pv.quantidade,
            "preco_unitario": item_pv.preco_unitario,
            "valor_bruto": item_pv.valor_total,
            "unidade": "UN",
            "desconto": Decimal("0"),
        })

        total_produtos += item_pv.valor_total
        total_icms += impostos.valor_icms
        total_ipi += impostos.valor_ipi
        total_pis += impostos.valor_pis
        total_cofins += impostos.valor_cofins
        total_st += impostos.valor_icms_st
        total_difal += impostos.valor_difal

    nf.valor_produtos = total_produtos
    nf.valor_icms = total_icms
    nf.valor_ipi = total_ipi
    nf.valor_pis = total_pis
    nf.valor_cofins = total_cofins
    nf.valor_icms_st = total_st
    nf.valor_difal = total_difal
    nf.valor_total = total_produtos + pedido.valor_frete + total_ipi

    db.add(nf)
    await db.flush()

    # Referência para Focus NF-e
    referencia = f"NF-{pedido_id}-{nf.id}"
    nf.focus_referencia = referencia

    # Transmite para SEFAZ via Focus NF-e
    payload = build_payload_nfe(nf, pedido, cliente, itens_para_nfe)
    resultado = await focus_nfe.emitir_nfe(referencia, payload)

    if resultado["status_code"] in (200, 201):
        nf.status_sefaz = "AGUARDANDO"
    else:
        nf.status_sefaz = "REJEITADA"
        nf.motivo_rejeicao = str(resultado.get("data", {}))

    await db.commit()

    # Agenda verificação de status e baixa de estoque em background
    background_tasks.add_task(_verificar_e_baixar_estoque, pedido_id, nf.id, referencia)

    return {
        "nf_id": nf.id,
        "status_sefaz": nf.status_sefaz,
        "focus_referencia": referencia,
        "valor_total": float(nf.valor_total),
        "resumo_fiscal": {
            "icms": float(total_icms),
            "ipi": float(total_ipi),
            "pis": float(total_pis),
            "cofins": float(total_cofins),
            "icms_st": float(total_st),
            "difal": float(total_difal),
        },
    }


class ExpedirSchema(BaseModel):
    transportadora: Optional[str] = None
    numero_nf: Optional[str] = None
    observacoes: Optional[str] = None


@router.post("/{pedido_id}/expedir", status_code=200)
async def expedir_pedido(
    pedido_id: int,
    data: ExpedirSchema,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Expede o pedido sem emitir NF-e via SEFAZ. Baixa o estoque e marca como EXPEDIDO."""
    r = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if pedido.status not in ("PICKING_OK", "CONFIRMADO"):
        raise HTTPException(422, f"Pedido no status '{pedido.status}' não pode ser expedido")

    await liberar_reserva(db, pedido_id, consumir=True)

    if data.transportadora:
        pedido.transportadora = data.transportadora
    if data.observacoes:
        pedido.observacoes = (pedido.observacoes or "") + f"\nExpedição: {data.observacoes}"

    pedido.status = "EXPEDIDO"
    await db.commit()
    return {"pedido_id": pedido.id, "numero": pedido.numero, "status": "EXPEDIDO"}


@router.get("/{nf_id}/status")
async def consultar_status_nfe(
    nf_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Consulta o status atual da NF-e no SEFAZ via Focus NF-e."""
    r = await db.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf_id))
    nf = r.scalar_one_or_none()
    if not nf:
        raise HTTPException(404, "NF não encontrada")

    if nf.focus_referencia:
        resultado = await focus_nfe.consultar_nfe(nf.focus_referencia)
        data = resultado.get("data", {})
        status_focus = data.get("status", "")

        if status_focus == "autorizado":
            nf.status_sefaz = "AUTORIZADA"
            nf.numero = str(data.get("numero_nfe", ""))
            nf.chave_acesso = data.get("chave_nfe", "")
            nf.protocolo = data.get("numero_protocolo", "")
            await db.commit()

    return {"nf_id": nf.id, "status_sefaz": nf.status_sefaz, "chave": nf.chave_acesso}


@router.get("/{nf_id}/danfe")
async def download_danfe(nf_id: int, db: AsyncSession = Depends(get_db)):
    """Baixa o PDF do DANFE da NF-e autorizada."""
    from fastapi.responses import Response
    r = await db.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf_id))
    nf = r.scalar_one_or_none()
    if not nf or nf.status_sefaz != "AUTORIZADA":
        raise HTTPException(404, "NF-e não autorizada ou não encontrada")
    pdf = await focus_nfe.download_danfe(nf.focus_referencia)
    if not pdf:
        raise HTTPException(503, "DANFE indisponível")
    return Response(content=pdf, media_type="application/pdf")


async def _verificar_e_baixar_estoque(pedido_id: int, nf_id: int, referencia: str):
    """
    Background task: verifica autorização da NF-e e baixa estoque definitivamente.
    Em produção, substituir por Celery task com retry automático.
    """
    import asyncio
    from app.core.database import AsyncSessionLocal

    for tentativa in range(10):
        await asyncio.sleep(5 * (tentativa + 1))
        async with AsyncSessionLocal() as db:
            resultado = await focus_nfe.consultar_nfe(referencia)
            data = resultado.get("data", {})
            if data.get("status") == "autorizado":
                r = await db.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf_id))
                nf = r.scalar_one_or_none()
                if nf and nf.status_sefaz != "AUTORIZADA":
                    nf.status_sefaz = "AUTORIZADA"
                    nf.numero = str(data.get("numero_nfe", ""))
                    nf.chave_acesso = data.get("chave_nfe", "")
                    nf.protocolo = data.get("numero_protocolo", "")

                    # Baixa estoque definitivamente
                    await liberar_reserva(db, pedido_id, consumir=True)

                    # Atualiza status do pedido
                    r2 = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
                    pedido = r2.scalar_one_or_none()
                    if pedido:
                        pedido.status = "EXPEDIDO"

                    await db.commit()
                return
            elif data.get("status") == "erro_autorizacao":
                async with AsyncSessionLocal() as db:
                    r = await db.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf_id))
                    nf = r.scalar_one_or_none()
                    if nf:
                        nf.status_sefaz = "REJEITADA"
                        nf.motivo_rejeicao = data.get("erros", "")
                        await db.commit()
                return
