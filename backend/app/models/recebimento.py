"""
Nota Fiscal de Entrada (NF do fornecedor ao receber mercadorias).

Tipos de entrada:
  COMPRA_MP       - Compra de matéria-prima
  COMPRA_REVENDA  - Compra de item para revenda
  RETORNO_BANHO   - Retorno de beneficiamento externo (CFOP 5902/6902)
  DEVOLUCAO_VENDA - Devolução de cliente
"""
from datetime import date
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Date, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class NotaFiscalEntrada(Base, TimestampMixin):
    __tablename__ = "notas_fiscais_entrada"

    id: Mapped[int] = mapped_column(primary_key=True)

    tipo_entrada: Mapped[str] = mapped_column(String(20), nullable=False)  # COMPRA_MP | COMPRA_REVENDA | RETORNO_BANHO | DEVOLUCAO_VENDA

    fornecedor_id: Mapped[int | None] = mapped_column(ForeignKey("fornecedores.id"))
    fornecedor: Mapped["Fornecedor"] = relationship()  # type: ignore[name-defined]

    # Dados da NF do fornecedor
    numero_nf: Mapped[str] = mapped_column(String(15), nullable=False)
    serie: Mapped[str | None] = mapped_column(String(5))
    chave_acesso: Mapped[str | None] = mapped_column(String(44), unique=True)  # Chave NF-e
    data_emissao: Mapped[date] = mapped_column(Date, nullable=False)
    data_entrada: Mapped[date] = mapped_column(Date, nullable=False)

    cfop_entrada: Mapped[str | None] = mapped_column(String(5))   # Ex: 1101, 2101, 1949

    # Totais
    valor_produtos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_frete: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Créditos apurados (conforme regime tributário)
    credito_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    credito_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    credito_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    credito_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Vinculação com pedido de compra (opcional)
    pedido_compra_id: Mapped[int | None] = mapped_column(ForeignKey("pedidos_compra.id"))

    # Vinculação com lote de beneficiamento (para retorno do banho)
    lote_beneficiamento_id: Mapped[int | None] = mapped_column(ForeignKey("lotes_beneficiamento.id"))

    # PENDENTE | CONFERIDA | LANCADA | DIVERGENCIA
    status: Mapped[str] = mapped_column(String(20), default="PENDENTE")

    observacoes: Mapped[str | None] = mapped_column(Text)

    itens: Mapped[list["ItemNotaFiscalEntrada"]] = relationship(back_populates="nota", cascade="all, delete-orphan")


class ItemNotaFiscalEntrada(Base):
    __tablename__ = "itens_nf_entrada"

    id: Mapped[int] = mapped_column(primary_key=True)
    nota_id: Mapped[int] = mapped_column(ForeignKey("notas_fiscais_entrada.id"), nullable=False)
    nota: Mapped["NotaFiscalEntrada"] = relationship(back_populates="itens")

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    localizacao_id: Mapped[int | None] = mapped_column(ForeignKey("localizacoes_estoque.id"))

    cfop: Mapped[str | None] = mapped_column(String(5))
    ncm: Mapped[str | None] = mapped_column(String(10))

    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # Impostos do item
    aliq_icms: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_ipi: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_pis: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_cofins: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Controle de qualidade na entrada
    aprovado_qc: Mapped[bool | None] = mapped_column(Boolean)
    quantidade_aprovada: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    observacao_qc: Mapped[str | None] = mapped_column(String(255))
