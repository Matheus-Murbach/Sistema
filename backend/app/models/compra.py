"""
Pedidos de Compra para fornecedores.
Gerados manualmente ou automaticamente quando estoque cai abaixo do mínimo.
"""
from datetime import date
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class PedidoCompra(Base, TimestampMixin):
    __tablename__ = "pedidos_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    fornecedor_id: Mapped[int] = mapped_column(ForeignKey("fornecedores.id"), nullable=False)
    fornecedor: Mapped["Fornecedor"] = relationship()  # type: ignore[name-defined]

    # ABERTO | ENVIADO | PARCIALMENTE_RECEBIDO | RECEBIDO | CANCELADO
    status: Mapped[str] = mapped_column(String(30), default="ABERTO")

    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    data_previsao: Mapped[date | None] = mapped_column(Date)

    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    condicao_pagamento: Mapped[str | None] = mapped_column(String(60))
    observacoes: Mapped[str | None] = mapped_column(Text)

    itens: Mapped[list["ItemPedidoCompra"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")


class ItemPedidoCompra(Base):
    __tablename__ = "itens_pedido_compra"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos_compra.id"), nullable=False)
    pedido: Mapped["PedidoCompra"] = relationship(back_populates="itens")

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_recebida: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
