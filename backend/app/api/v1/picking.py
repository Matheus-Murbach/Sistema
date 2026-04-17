"""
Módulo de Picking - montagem e conferência de pedidos com leitor de barras.

Endpoint WebSocket /picking/{conferencia_id}/ws para leitura em tempo real.
Cada leitura do scanner é enviada como mensagem e o sistema responde com
o status: OK, DIVERGENCIA_QUANTIDADE, ITEM_ERRADO, JA_CONFERIDO.
"""
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import json

from app.core.database import get_db
from app.models.picking import ConferencePicking, ItemConferencePicking
from app.models.venda import PedidoVenda, ItemPedidoVenda
from app.models.produto import Produto
from app.api.v1.auth import get_current_user

router = APIRouter()


@router.post("/{pedido_id}/iniciar", status_code=201)
async def iniciar_picking(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cria a conferência de picking para um pedido confirmado."""
    r = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if pedido.status not in ("CONFIRMADO",):
        raise HTTPException(422, f"Pedido no status '{pedido.status}' não pode iniciar picking")

    # Verifica se já existe conferência
    r2 = await db.execute(select(ConferencePicking).where(ConferencePicking.pedido_venda_id == pedido_id))
    if r2.scalar_one_or_none():
        raise HTTPException(409, "Picking já iniciado para este pedido")

    conferencia = ConferencePicking(
        pedido_venda_id=pedido_id,
        operador_id=current_user.id,
        status="EM_ANDAMENTO",
        data_inicio=datetime.now(timezone.utc),
    )

    # Carrega itens do pedido
    r3 = await db.execute(select(ItemPedidoVenda).where(ItemPedidoVenda.pedido_id == pedido_id))
    itens_pedido = r3.scalars().all()
    for item in itens_pedido:
        conferencia.itens.append(ItemConferencePicking(
            item_pedido_id=item.id,
            produto_id=item.produto_id,
            quantidade_esperada=item.quantidade,
            status="PENDENTE",
        ))

    db.add(conferencia)
    pedido.status = "EM_PICKING"
    await db.commit()
    await db.refresh(conferencia)
    return conferencia


@router.post("/{pedido_id}/concluir")
async def concluir_picking(
    pedido_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Marca a separação como concluída manualmente → pedido vira PICKING_OK."""
    r = await db.execute(select(PedidoVenda).where(PedidoVenda.id == pedido_id))
    pedido = r.scalar_one_or_none()
    if not pedido:
        raise HTTPException(404, "Pedido não encontrado")
    if pedido.status not in ("EM_PICKING", "CONFIRMADO"):
        raise HTTPException(422, f"Pedido no status '{pedido.status}' não pode ser concluído")

    r2 = await db.execute(
        select(ConferencePicking).where(ConferencePicking.pedido_venda_id == pedido_id)
    )
    conf = r2.scalar_one_or_none()
    if conf and conf.status != "CONCLUIDO":
        conf.status = "CONCLUIDO"
        conf.data_conclusao = datetime.now(timezone.utc)

    pedido.status = "PICKING_OK"
    await db.commit()
    return {"pedido_id": pedido.id, "status": "PICKING_OK"}


@router.get("/{conferencia_id}")
async def detalhar_conferencia(conferencia_id: int, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(ConferencePicking).where(ConferencePicking.id == conferencia_id))
    c = r.scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Conferência não encontrada")
    return c


@router.post("/{conferencia_id}/scan")
async def registrar_leitura(
    conferencia_id: int,
    codigo: str,
    quantidade: Decimal = Decimal("1"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Processa uma leitura do scanner.
    Aceita código de barras do produto ou código interno.
    Retorna resultado da conferência para exibição na tela (verde/vermelho).
    """
    r = await db.execute(select(ConferencePicking).where(ConferencePicking.id == conferencia_id))
    conferencia = r.scalar_one_or_none()
    if not conferencia or conferencia.status != "EM_ANDAMENTO":
        raise HTTPException(404, "Conferência não encontrada ou já concluída")

    # Encontra produto pelo código de barras ou código
    r2 = await db.execute(
        select(Produto).where(
            (Produto.codigo_barras == codigo) | (Produto.codigo == codigo)
        )
    )
    produto = r2.scalar_one_or_none()
    if not produto:
        return {"resultado": "ITEM_ERRADO", "mensagem": f"Produto '{codigo}' não encontrado no sistema"}

    # Encontra o item da conferência
    r3 = await db.execute(
        select(ItemConferencePicking).where(
            ItemConferencePicking.conferencia_id == conferencia_id,
            ItemConferencePicking.produto_id == produto.id,
        )
    )
    item_conf = r3.scalar_one_or_none()

    if not item_conf:
        return {
            "resultado": "ITEM_ERRADO",
            "mensagem": f"Produto '{produto.descricao}' não está neste pedido",
        }

    # Atualiza quantidade conferida
    item_conf.quantidade_conferida += quantidade
    item_conf.ultima_leitura = datetime.now(timezone.utc)

    if item_conf.quantidade_conferida == item_conf.quantidade_esperada:
        item_conf.status = "OK"
        resultado = "OK"
        mensagem = f"{produto.descricao}: quantidade correta ({float(item_conf.quantidade_conferida)})"
    elif item_conf.quantidade_conferida > item_conf.quantidade_esperada:
        item_conf.status = "DIVERGENCIA_QUANTIDADE"
        resultado = "DIVERGENCIA_QUANTIDADE"
        mensagem = (
            f"{produto.descricao}: quantidade EXCEDIDA. "
            f"Esperado: {float(item_conf.quantidade_esperada)}, "
            f"Conferido: {float(item_conf.quantidade_conferida)}"
        )
    else:
        item_conf.status = "PENDENTE"
        resultado = "PARCIAL"
        falta = item_conf.quantidade_esperada - item_conf.quantidade_conferida
        mensagem = f"{produto.descricao}: faltam {float(falta)} unidades"

    # Recalcula percentual de conclusão
    r4 = await db.execute(
        select(ItemConferencePicking).where(ItemConferencePicking.conferencia_id == conferencia_id)
    )
    todos = r4.scalars().all()
    ok_count = sum(1 for i in todos if i.status == "OK")
    conferencia.percentual_concluido = Decimal(str(round(ok_count / len(todos) * 100, 2))) if todos else Decimal("0")

    # Verifica se concluiu tudo
    if all(i.status == "OK" for i in todos):
        conferencia.status = "CONCLUIDO"
        conferencia.data_conclusao = datetime.now(timezone.utc)

        # Atualiza pedido
        r5 = await db.execute(select(PedidoVenda).where(PedidoVenda.id == conferencia.pedido_venda_id))
        pedido = r5.scalar_one_or_none()
        if pedido:
            pedido.status = "PICKING_OK"

    await db.commit()
    return {
        "resultado": resultado,
        "mensagem": mensagem,
        "produto_id": produto.id,
        "produto_descricao": produto.descricao,
        "quantidade_esperada": float(item_conf.quantidade_esperada),
        "quantidade_conferida": float(item_conf.quantidade_conferida),
        "percentual_geral": float(conferencia.percentual_concluido),
        "conferencia_concluida": conferencia.status == "CONCLUIDO",
    }


@router.websocket("/{conferencia_id}/ws")
async def picking_websocket(
    conferencia_id: int,
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket para leitura em tempo real do scanner.
    O cliente envia: {"codigo": "7891234567890", "quantidade": 1}
    O servidor responde com o resultado imediatamente.
    """
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                codigo = payload.get("codigo", "")
                quantidade = Decimal(str(payload.get("quantidade", 1)))

                # Reutiliza a lógica do endpoint REST
                r = await db.execute(select(ConferencePicking).where(ConferencePicking.id == conferencia_id))
                conferencia = r.scalar_one_or_none()
                if not conferencia:
                    await websocket.send_text(json.dumps({"resultado": "ERRO", "mensagem": "Conferência não encontrada"}))
                    continue

                r2 = await db.execute(
                    select(Produto).where((Produto.codigo_barras == codigo) | (Produto.codigo == codigo))
                )
                produto = r2.scalar_one_or_none()
                if not produto:
                    await websocket.send_text(json.dumps({
                        "resultado": "ITEM_ERRADO",
                        "mensagem": f"Código '{codigo}' não encontrado",
                        "cor": "vermelho",
                    }))
                    continue

                r3 = await db.execute(
                    select(ItemConferencePicking).where(
                        ItemConferencePicking.conferencia_id == conferencia_id,
                        ItemConferencePicking.produto_id == produto.id,
                    )
                )
                item_conf = r3.scalar_one_or_none()
                if not item_conf:
                    await websocket.send_text(json.dumps({
                        "resultado": "ITEM_ERRADO",
                        "mensagem": f"'{produto.descricao}' não está no pedido",
                        "cor": "vermelho",
                    }))
                    continue

                item_conf.quantidade_conferida += quantidade
                item_conf.ultima_leitura = datetime.now(timezone.utc)

                if item_conf.quantidade_conferida >= item_conf.quantidade_esperada:
                    item_conf.status = "OK"
                    cor = "verde"
                    resultado = "OK"
                else:
                    cor = "amarelo"
                    resultado = "PARCIAL"

                r4 = await db.execute(
                    select(ItemConferencePicking).where(ItemConferencePicking.conferencia_id == conferencia_id)
                )
                todos = r4.scalars().all()
                ok_count = sum(1 for i in todos if i.status == "OK")
                pct = round(ok_count / len(todos) * 100, 1) if todos else 0
                conferencia.percentual_concluido = Decimal(str(pct))

                if all(i.status == "OK" for i in todos):
                    conferencia.status = "CONCLUIDO"
                    resultado = "CONCLUIDO"
                    cor = "verde"

                await db.commit()
                await websocket.send_text(json.dumps({
                    "resultado": resultado,
                    "produto": produto.descricao,
                    "esperado": float(item_conf.quantidade_esperada),
                    "conferido": float(item_conf.quantidade_conferida),
                    "percentual": pct,
                    "cor": cor,
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({"resultado": "ERRO", "mensagem": str(e)}))
    except WebSocketDisconnect:
        pass
