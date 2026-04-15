"""Dashboard - visão geral operacional."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, timedelta

from app.core.database import get_db
from app.models.estoque import SaldoEstoque
from app.models.producao import OrdemProducao
from app.models.venda import PedidoVenda
from app.models.beneficiamento import LoteBeneficiamento
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.get("/resumo")
async def resumo_dashboard(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    hoje = date.today()
    inicio_mes = hoje.replace(day=1)

    # OPs abertas e em produção
    r1 = await db.execute(
        select(func.count()).where(OrdemProducao.status.in_(["ABERTA", "EM_PRODUCAO"]))
    )
    ops_abertas = r1.scalar()

    # Pedidos de venda pendentes de expedição
    r2 = await db.execute(
        select(func.count()).where(PedidoVenda.status.in_(["CONFIRMADO", "EM_PICKING", "PICKING_OK"]))
    )
    pedidos_pendentes = r2.scalar()

    # Lotes em beneficiamento (no banho)
    r3 = await db.execute(
        select(func.count()).where(
            LoteBeneficiamento.status.in_(["ENVIADO", "AGUARDANDO_RETORNO", "RETORNADO_PARCIAL"])
        )
    )
    lotes_banho = r3.scalar()

    # Lotes com prazo vencido
    r4 = await db.execute(
        select(func.count()).where(
            and_(
                LoteBeneficiamento.status.in_(["ENVIADO", "AGUARDANDO_RETORNO"]),
                LoteBeneficiamento.data_previsao_retorno < hoje,
            )
        )
    )
    lotes_atrasados = r4.scalar()

    # Vendas do mês
    r5 = await db.execute(
        select(func.sum(PedidoVenda.valor_total)).where(
            and_(
                PedidoVenda.status == "EXPEDIDO",
                PedidoVenda.data_emissao >= inicio_mes,
            )
        )
    )
    vendas_mes = r5.scalar() or 0

    return {
        "ops_abertas": ops_abertas,
        "pedidos_pendentes_expedicao": pedidos_pendentes,
        "lotes_no_banho": lotes_banho,
        "lotes_banho_atrasados": lotes_atrasados,
        "vendas_mes": float(vendas_mes),
        "data": str(hoje),
    }
