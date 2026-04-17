"""
Ordens de Produção (OP) - PCP.

Fluxo de alta rotatividade:
  1. Criar OP (produto a fabricar, máquina, quantidade)
  2. "Iniciar OP" → consome MP do estoque imediatamente (via ConsumoMaterial)
  3. "Concluir OP" → registra quantidade produzida + refugo → entrada no estoque de acabados

Isso mantém a agilidade para alta rotatividade mas garante rastreabilidade.
A BOM (Bill of Materials) lista os insumos necessários por unidade produzida.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class OrdemProducao(Base, TimestampMixin):
    __tablename__ = "ordens_producao"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    maquina_id: Mapped[int | None] = mapped_column(ForeignKey("maquinas.id"))
    maquina: Mapped["Maquina"] = relationship()  # type: ignore[name-defined]

    quantidade_planejada: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_produzida: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    quantidade_refugo: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)

    # ABERTA | EM_PRODUCAO | CONCLUIDA | CANCELADA
    status: Mapped[str] = mapped_column(String(20), default="ABERTA")

    data_planejada: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_conclusao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Localização de saída dos produtos acabados
    localizacao_saida_id: Mapped[int | None] = mapped_column(ForeignKey("localizacoes_estoque.id"))

    # Vínculo com pedido de venda que gerou a OP (opcional)
    pedido_venda_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos_venda.id"))

    observacoes: Mapped[str | None] = mapped_column(Text)

    itens: Mapped[list["ItemOrdemProducao"]] = relationship(back_populates="op", cascade="all, delete-orphan")
    consumos: Mapped[list["ConsumoMaterial"]] = relationship(back_populates="op", cascade="all, delete-orphan")


class ItemOrdemProducao(Base):
    """BOM - Bill of Materials: lista de materiais necessários para a OP."""
    __tablename__ = "itens_ordem_producao"

    id: Mapped[int] = mapped_column(primary_key=True)
    op_id: Mapped[int] = mapped_column(ForeignKey("ordens_producao.id"), nullable=False)
    op: Mapped["OrdemProducao"] = relationship(back_populates="itens")

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    quantidade_necessaria: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_consumida: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)


class ConsumoMaterial(Base, TimestampMixin):
    """Registro efetivo de consumo de MP quando operador pega o material."""
    __tablename__ = "consumos_material"

    id: Mapped[int] = mapped_column(primary_key=True)
    op_id: Mapped[int] = mapped_column(ForeignKey("ordens_producao.id"), nullable=False)
    op: Mapped["OrdemProducao"] = relationship(back_populates="consumos")

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    localizacao_id: Mapped[int | None] = mapped_column(ForeignKey("localizacoes_estoque.id"))
    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
