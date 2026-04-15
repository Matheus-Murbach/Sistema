"""
Cadastro de produtos com dados fiscais completos.

Tipos de produto:
  MATERIA_PRIMA     - Insumo comprado para produção (gera crédito IPI/ICMS)
  REVENDA           - Item comprado pronto para revender
  SEMI_ACABADO      - Produzido internamente, ainda não acabado
  PRODUTO_ACABADO   - Produção interna finalizada
  PRODUTO_BENEFICIADO - Voltou do banho, pronto para venda

Origem (campo orig da NF-e):
  0 - Nacional
  1 - Estrangeira importação direta
  2 - Estrangeira adquirida no mercado interno
  ...etc (tabela ICMS)
"""

from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class UnidadeMedida(Base):
    __tablename__ = "unidades_medida"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)  # UN, KG, MT, CX...
    descricao: Mapped[str] = mapped_column(String(60), nullable=False)


class Produto(Base, TimestampMixin):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    codigo_barras: Mapped[str | None] = mapped_column(String(50), unique=True)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao_complementar: Mapped[str | None] = mapped_column(Text)

    tipo: Mapped[str] = mapped_column(
        String(30),
        default="MATERIA_PRIMA",
        # MATERIA_PRIMA | REVENDA | SEMI_ACABADO | PRODUTO_ACABADO | PRODUTO_BENEFICIADO
    )

    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    unidade: Mapped["UnidadeMedida"] = relationship()

    # Estoque
    estoque_minimo: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    estoque_maximo: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    peso_liquido: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    peso_bruto: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))

    # Dados fiscais
    ncm: Mapped[str | None] = mapped_column(String(10))      # Ex: 73181500
    cest: Mapped[str | None] = mapped_column(String(9))       # Para ICMS-ST
    origem: Mapped[str] = mapped_column(String(1), default="0")  # 0=Nacional

    # ICMS
    cst_icms: Mapped[str | None] = mapped_column(String(3))   # 000, 010, 020, 041, 060...
    csosn: Mapped[str | None] = mapped_column(String(3))       # Para Simples Nacional: 101, 102, 400...
    aliq_icms: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    aliq_icms_st: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    mva: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)  # Margem de Valor Agregado (ST)

    # IPI
    cst_ipi: Mapped[str | None] = mapped_column(String(2))    # 00, 49, 50, 99...
    aliq_ipi: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    codigo_enquadramento_ipi: Mapped[str | None] = mapped_column(String(3))

    # PIS / COFINS
    cst_pis: Mapped[str | None] = mapped_column(String(2))    # 01, 02, 07, 49, 50, 99...
    aliq_pis: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("0.65"))
    cst_cofins: Mapped[str | None] = mapped_column(String(2))
    aliq_cofins: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=Decimal("3.00"))

    # Preço de custo e venda
    preco_custo: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Observações internas
    observacoes: Mapped[str | None] = mapped_column(Text)
