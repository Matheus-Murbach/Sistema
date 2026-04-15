"""
Controle de estoque por localização física.

Status de saldo:
  DISPONIVEL       - Livre para venda/produção
  RESERVADO        - Reservado para pedido de venda confirmado
  EM_PRODUCAO      - Alocado em Ordem de Produção aberta
  EM_BENEFICIAMENTO - Saiu para banho externo, aguardando retorno
  BLOQUEADO_QC     - Aguardando liberação do controle de qualidade
  INATIVO          - Desativado (ajuste de inventário, etc.)

Tipos de movimentação:
  ENTRADA_COMPRA, ENTRADA_RETORNO_BANHO, ENTRADA_PRODUCAO, ENTRADA_AJUSTE,
  SAIDA_PRODUCAO, SAIDA_REMESSA_BANHO, SAIDA_VENDA, SAIDA_AJUSTE, SAIDA_REFUGO
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class LocalizacaoEstoque(Base):
    __tablename__ = "localizacoes_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)  # Ex: A-01-02
    descricao: Mapped[str | None] = mapped_column(String(100))
    # corredor / prateleira / bin (para futuro WMS)
    corredor: Mapped[str | None] = mapped_column(String(10))
    prateleira: Mapped[str | None] = mapped_column(String(10))
    bin: Mapped[str | None] = mapped_column(String(10))
    ativa: Mapped[bool] = mapped_column(default=True)


class SaldoEstoque(Base):
    """Saldo atual por produto + localização + status."""
    __tablename__ = "saldos_estoque"
    __table_args__ = (
        UniqueConstraint("produto_id", "localizacao_id", "status", name="uq_saldo_produto_loc_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]
    localizacao_id: Mapped[int] = mapped_column(ForeignKey("localizacoes_estoque.id"), nullable=False)
    localizacao: Mapped["LocalizacaoEstoque"] = relationship()
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(25), default="DISPONIVEL")


class MovimentacaoEstoque(Base, TimestampMixin):
    """Registro imutável de cada entrada/saída do estoque."""
    __tablename__ = "movimentacoes_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]
    localizacao_id: Mapped[int] = mapped_column(ForeignKey("localizacoes_estoque.id"))
    localizacao: Mapped["LocalizacaoEstoque"] = relationship()

    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)  # + entrada / - saída
    saldo_apos: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    # Documento de origem
    documento_tipo: Mapped[str | None] = mapped_column(String(30))  # NF_ENTRADA, OP, PEDIDO_VENDA...
    documento_id: Mapped[int | None] = mapped_column()
    documento_numero: Mapped[str | None] = mapped_column(String(50))

    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observacao: Mapped[str | None] = mapped_column(Text)


class ReservaEstoque(Base, TimestampMixin):
    """Reserva de estoque para pedido de venda confirmado."""
    __tablename__ = "reservas_estoque"

    id: Mapped[int] = mapped_column(primary_key=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]
    localizacao_id: Mapped[int] = mapped_column(ForeignKey("localizacoes_estoque.id"))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    # Origem da reserva
    pedido_venda_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos_venda.id"))
    status: Mapped[str] = mapped_column(String(20), default="ATIVA")  # ATIVA | LIBERADA | CONSUMIDA
