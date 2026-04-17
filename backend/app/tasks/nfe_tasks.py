"""
Celery tasks para processamento assíncrono de NF-e.
Monitora status no SEFAZ e atualiza o banco quando autorizado/rejeitado.
"""
from app.core.celery_app import celery_app


@celery_app.task(
    bind=True,
    max_retries=20,
    default_retry_delay=15,
    queue="nfe",
    name="app.tasks.nfe_tasks.verificar_autorizacao_nfe",
)
def verificar_autorizacao_nfe(self, nf_id: int, pedido_id: int, referencia: str):
    """
    Verifica periodicamente se a NF-e foi autorizada pelo SEFAZ.
    Após autorização, baixa o estoque definitivamente.
    """
    import asyncio
    from app.core.database import AsyncSessionLocal
    from app.integrations.focus_nfe import focus_nfe
    from app.models.expedicao import NotaFiscalSaida
    from app.models.venda import PedidoVenda
    from app.services.estoque_service import liberar_reserva
    from sqlalchemy import select

    async def _run():
        resultado = await focus_nfe.consultar_nfe(referencia)
        data = resultado.get("data", {})
        status = data.get("status", "")

        async with AsyncSessionLocal() as db:
            r = await db.execute(select(NotaFiscalSaida).where(NotaFiscalSaida.id == nf_id))
            nf = r.scalar_one_or_none()
            if not nf:
                return "nf_nao_encontrada"

            if status == "autorizado":
                nf.status_sefaz = "AUTORIZADA"
                nf.numero = str(data.get("numero_nfe", ""))
                nf.chave_acesso = data.get("chave_nfe", "")
                nf.protocolo = data.get("numero_protocolo", "")
                await liberar_reserva(db, pedido_id, consumir=True)

                r2 = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
                pedido = r2.scalar_one_or_none()
                if pedido:
                    pedido.status = "EXPEDIDO"
                await db.commit()
                return "autorizado"

            elif status == "erro_autorizacao":
                nf.status_sefaz = "REJEITADA"
                nf.motivo_rejeicao = str(data.get("erros", ""))
                await db.commit()
                return "rejeitado"

            return "pendente"

    loop = asyncio.new_event_loop()
    try:
        resultado = loop.run_until_complete(_run())
        if resultado == "pendente":
            raise self.retry()
    finally:
        loop.close()
