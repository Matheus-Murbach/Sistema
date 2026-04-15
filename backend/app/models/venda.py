"""
Pedidos de Venda.

Status do pedido:
  ORCAMENTO       - Ainda não confirmado, sem reserva de estoque
  CONFIRMADO      - Confirmado, estoque reservado automaticamente
  EM_PICKING      - Na montagem/conferência
  PICKING_OK      - Conferência concluída, aguarda expedição
  EXPEDIDO        - NF emitida, entregue para transporte
  CANCELADO       - Cancelado, reservas liberadas
  DEVOLVIDO       - Retornou (devolução total)
"""
from datetime import date
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Date, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class PedidoVenda(Base, TimestampMixin):
    __tablename__ = "pedidos_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    cliente: Mapped["Cliente"] = relationship()  # type: ignore[name-defined]

    status: Mapped[str] = mapped_column(String(20), default="ORCAMENTO")

    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    data_previsao_entrega: Mapped[date | None] = mapped_column(Date)

    condicao_pagamento: Mapped[str | None] = mapped_column(String(60))
    transportadora: Mapped[str | None] = mapped_column(String(100))
    frete_por_conta: Mapped[str] = mapped_column(String(1), default="0")  # 0=Emitente, 1=Destinatário

    # Totais
    valor_produtos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_frete: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_desconto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    observacoes: Mapped[str | None] = mapped_column(Text)
    observacoes_internas: Mapped[str | None] = mapped_column(Text)

    itens: Mapped[list["ItemPedidoVenda"]] = relationship(back_populates="pedido", cascade="all, delete-orphan")


class ItemPedidoVenda(Base):
    __tablename__ = "itens_pedido_venda"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[int] = mapped_column(ForeignKey("pedidos_venda.id"), nullable=False)
    pedido: Mapped["PedidoVenda"] = relationship(back_populates="itens")

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    desconto_percent: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Impostos calculados para a venda
    aliq_icms: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_ipi: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_pis: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_cofins: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_icms_st: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_difal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Status de disponibilidade
    disponivel: Mapped[bool] = mapped_column(Boolean, default=False)
    previsao_entrega: Mapped[date | None] = mapped_column(Date)
