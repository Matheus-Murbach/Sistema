"""
Lote de Beneficiamento - controle de itens enviados para tratamento externo (banho).

Fluxo fiscal:
  Saída: NF de Remessa para Industrialização  (CFOP 5901 intra / 6901 inter)
  Retorno: NF de Retorno de Industrialização   (CFOP 5902 intra / 6902 inter)

O prestador emite NF de serviço (mão de obra + insumos) sobre o valor agregado.
Itens saem como brutos/semi-acabados e voltam como produto acabado/beneficiado.
"""
from datetime import date
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, Date, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class LoteBeneficiamento(Base, TimestampMixin):
    __tablename__ = "lotes_beneficiamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    prestador_id: Mapped[int] = mapped_column(ForeignKey("prestadores_beneficiamento.id"), nullable=False)
    prestador: Mapped["PrestadorBeneficiamento"] = relationship()  # type: ignore[name-defined]

    tipo_beneficiamento: Mapped[str | None] = mapped_column(String(60))  # Zincagem, Niquelação, etc.

    data_remessa: Mapped[date] = mapped_column(Date, nullable=False)
    data_previsao_retorno: Mapped[date | None] = mapped_column(Date)
    data_retorno_real: Mapped[date | None] = mapped_column(Date)

    # NF de Remessa emitida pela empresa
    nf_remessa_chave: Mapped[str | None] = mapped_column(String(44))
    nf_remessa_numero: Mapped[str | None] = mapped_column(String(15))
    cfop_remessa: Mapped[str] = mapped_column(String(5), default="5901")

    # NF de Retorno recebida do prestador
    nf_retorno_chave: Mapped[str | None] = mapped_column(String(44))
    nf_retorno_numero: Mapped[str | None] = mapped_column(String(15))
    cfop_retorno: Mapped[str] = mapped_column(String(5), default="5902")

    # Valor do serviço cobrado pelo prestador
    valor_servico: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_insumos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # ABERTO | ENVIADO | AGUARDANDO_RETORNO | RETORNADO_PARCIAL | RETORNADO | CANCELADO
    status: Mapped[str] = mapped_column(String(25), default="ABERTO")

    observacoes: Mapped[str | None] = mapped_column(Text)

    itens: Mapped[list["ItemLoteBeneficiamento"]] = relationship(
        back_populates="lote", cascade="all, delete-orphan"
    )


class ItemLoteBeneficiamento(Base):
    __tablename__ = "itens_lote_beneficiamento"

    id: Mapped[int] = mapped_column(primary_key=True)
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes_beneficiamento.id"), nullable=False)
    lote: Mapped["LoteBeneficiamento"] = relationship(back_populates="itens")

    # Produto que saiu (bruto/semi-acabado)
    produto_enviado_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto_enviado: Mapped["Produto"] = relationship(  # type: ignore[name-defined]
        "Produto", foreign_keys="[ItemLoteBeneficiamento.produto_enviado_id]"
    )

    # Produto que volta (acabado/beneficiado) — pode ser o mesmo ou diferente
    produto_retorno_id: Mapped[int | None] = mapped_column(ForeignKey("produtos.id"))
    produto_retorno: Mapped["Produto"] = relationship(  # type: ignore[name-defined]
        "Produto", foreign_keys="[ItemLoteBeneficiamento.produto_retorno_id]"
    )

    localizacao_saida_id: Mapped[int | None] = mapped_column(ForeignKey("localizacoes_estoque.id"))
    localizacao_retorno_id: Mapped[int | None] = mapped_column(ForeignKey("localizacoes_estoque.id"))

    quantidade_enviada: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    quantidade_retornada: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)
    quantidade_rejeitada: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)

    # Custo unitário do serviço rateado
    custo_servico_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=0)

    retornado: Mapped[bool] = mapped_column(Boolean, default=False)
    observacao: Mapped[str | None] = mapped_column(String(255))
