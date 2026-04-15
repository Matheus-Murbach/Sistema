"""
Serviço de controle de estoque.
Todas as movimentações passam por aqui para garantir consistência.
"""
from decimal import Decimal
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.estoque import SaldoEstoque, MovimentacaoEstoque, ReservaEstoque
from fastapi import HTTPException


async def get_saldo(
    db: AsyncSession,
    produto_id: int,
    localizacao_id: int,
    status: str = "DISPONIVEL",
) -> Decimal:
    """Retorna saldo atual para produto + localização + status."""
    result = await db.execute(
        select(SaldoEstoque).where(
            SaldoEstoque.produto_id == produto_id,
            SaldoEstoque.localizacao_id == localizacao_id,
            SaldoEstoque.status == status,
        )
    )
    saldo = result.scalar_one_or_none()
    return saldo.quantidade if saldo else Decimal("0")


async def get_saldo_total_disponivel(db: AsyncSession, produto_id: int) -> Decimal:
    """Saldo disponível total em todas as localizações (descontando reservas)."""
    result = await db.execute(
        select(SaldoEstoque).where(
            SaldoEstoque.produto_id == produto_id,
            SaldoEstoque.status == "DISPONIVEL",
        )
    )
    saldos = result.scalars().all()
    return sum((s.quantidade for s in saldos), Decimal("0"))


async def movimentar(
    db: AsyncSession,
    produto_id: int,
    localizacao_id: int,
    tipo: str,
    quantidade: Decimal,
    status_estoque: str = "DISPONIVEL",
    documento_tipo: str | None = None,
    documento_id: int | None = None,
    documento_numero: str | None = None,
    usuario_id: int | None = None,
    observacao: str | None = None,
) -> MovimentacaoEstoque:
    """
    Registra uma movimentação e atualiza o saldo.
    quantidade positiva = entrada; negativa = saída.
    Levanta HTTPException se saída resultar em saldo negativo.
    """
    # Busca ou cria o saldo
    result = await db.execute(
        select(SaldoEstoque).where(
            SaldoEstoque.produto_id == produto_id,
            SaldoEstoque.localizacao_id == localizacao_id,
            SaldoEstoque.status == status_estoque,
        )
    )
    saldo_obj = result.scalar_one_or_none()

    if saldo_obj is None:
        saldo_obj = SaldoEstoque(
            produto_id=produto_id,
            localizacao_id=localizacao_id,
            status=status_estoque,
            quantidade=Decimal("0"),
        )
        db.add(saldo_obj)

    novo_saldo = saldo_obj.quantidade + quantidade

    if novo_saldo < 0:
        raise HTTPException(
            status_code=422,
            detail=f"Saldo insuficiente. Disponível: {saldo_obj.quantidade}, solicitado: {abs(quantidade)}",
        )

    saldo_obj.quantidade = novo_saldo

    mov = MovimentacaoEstoque(
        produto_id=produto_id,
        localizacao_id=localizacao_id,
        tipo=tipo,
        quantidade=quantidade,
        saldo_apos=novo_saldo,
        documento_tipo=documento_tipo,
        documento_id=documento_id,
        documento_numero=documento_numero,
        usuario_id=usuario_id,
        observacao=observacao,
    )
    db.add(mov)
    return mov


async def reservar_estoque(
    db: AsyncSession,
    produto_id: int,
    localizacao_id: int,
    quantidade: Decimal,
    pedido_venda_id: int,
) -> ReservaEstoque:
    """
    Move quantidade de DISPONIVEL → RESERVADO para um pedido de venda.
    Garante atomicidade: diminui DISPONIVEL e aumenta RESERVADO.
    """
    disponivel = await get_saldo(db, produto_id, localizacao_id, "DISPONIVEL")
    if disponivel < quantidade:
        raise HTTPException(
            status_code=422,
            detail=f"Estoque insuficiente para reserva. Disponível: {disponivel}, solicitado: {quantidade}",
        )

    # Diminui DISPONIVEL
    await movimentar(
        db, produto_id, localizacao_id,
        tipo="RESERVA",
        quantidade=-quantidade,
        status_estoque="DISPONIVEL",
        documento_tipo="PEDIDO_VENDA",
        documento_id=pedido_venda_id,
    )

    # Aumenta RESERVADO
    await movimentar(
        db, produto_id, localizacao_id,
        tipo="RESERVA",
        quantidade=quantidade,
        status_estoque="RESERVADO",
        documento_tipo="PEDIDO_VENDA",
        documento_id=pedido_venda_id,
    )

    reserva = ReservaEstoque(
        produto_id=produto_id,
        localizacao_id=localizacao_id,
        quantidade=quantidade,
        pedido_venda_id=pedido_venda_id,
        status="ATIVA",
    )
    db.add(reserva)
    return reserva


async def liberar_reserva(
    db: AsyncSession,
    pedido_venda_id: int,
    consumir: bool = False,
) -> None:
    """
    Libera ou consome reservas de um pedido.
    consumir=True → baixa do estoque RESERVADO (expedição realizada)
    consumir=False → devolve para DISPONIVEL (cancelamento do pedido)
    """
    result = await db.execute(
        select(ReservaEstoque).where(
            ReservaEstoque.pedido_venda_id == pedido_venda_id,
            ReservaEstoque.status == "ATIVA",
        )
    )
    reservas = result.scalars().all()

    for reserva in reservas:
        if consumir:
            # Baixa definitiva: sai do RESERVADO sem voltar ao DISPONIVEL
            await movimentar(
                db, reserva.produto_id, reserva.localizacao_id,
                tipo="SAIDA_VENDA",
                quantidade=-reserva.quantidade,
                status_estoque="RESERVADO",
                documento_tipo="PEDIDO_VENDA",
                documento_id=pedido_venda_id,
            )
            reserva.status = "CONSUMIDA"
        else:
            # Devolve para DISPONIVEL (cancelamento)
            await movimentar(
                db, reserva.produto_id, reserva.localizacao_id,
                tipo="CANCELAMENTO_RESERVA",
                quantidade=-reserva.quantidade,
                status_estoque="RESERVADO",
                documento_tipo="PEDIDO_VENDA",
                documento_id=pedido_venda_id,
            )
            await movimentar(
                db, reserva.produto_id, reserva.localizacao_id,
                tipo="CANCELAMENTO_RESERVA",
                quantidade=reserva.quantidade,
                status_estoque="DISPONIVEL",
                documento_tipo="PEDIDO_VENDA",
                documento_id=pedido_venda_id,
            )
            reserva.status = "LIBERADA"
