"""
Conferência de Picking - montagem de pedidos com leitor de código de barras.

O operador escaneia cada item e o sistema valida:
  - Item correto (código bate com o pedido)
  - Quantidade correta
Alertas visuais (verde/vermelho) em tempo real.
O pedido só avança para expedição quando status = CONCLUIDO (100% conferido).
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class ConferencePicking(Base, TimestampMixin):
    __tablename__ = "conferencias_picking"

    id: Mapped[int] = mapped_column(primary_key=True)

    pedido_venda_id: Mapped[int] = mapped_column(ForeignKey("pedidos_venda.id"), nullable=False, unique=True)
    pedido_venda: Mapped["PedidoVenda"] = relationship()  # type: ignore[name-defined]

    operador_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    # EM_ANDAMENTO | CONCLUIDO | DIVERGENCIA
    status: Mapped[str] = mapped_column(String(20), default="EM_ANDAMENTO")

    data_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_conclusao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Percentual de conclusão (0-100)
    percentual_concluido: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)

    itens: Mapped[list["ItemConferencePicking"]] = relationship(
        back_populates="conferencia", cascade="all, delete-orphan"
    )


class ItemConferencePicking(Base):
    __tablename__ = "itens_conferencia_picking"

    id: Mapped[int] = mapped_column(primary_key=True)
    conferencia_id: Mapped[int] = mapped_column(ForeignKey("conferencias_picking.id"), nullable=False)
    conferencia: Mapped["ConferencePicking"] = relationship(back_populates="itens")

    item_pedido_id: Mapped[int] = mapped_column(ForeignKey("itens_pedido_venda.id"), nullable=False)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    quantidade_esperada: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_conferida: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)

    # PENDENTE | OK | DIVERGENCIA_QUANTIDADE | ITEM_ERRADO
    status: Mapped[str] = mapped_column(String(25), default="PENDENTE")

    # Cada leitura do scanner registra aqui
    ultima_leitura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
