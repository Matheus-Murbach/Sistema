"""
Nota Fiscal de Saída (NF-e de venda).

Emitida após picking 100% conferido.
Transmitida ao SEFAZ via Focus NF-e API.
Baixa o estoque reservado definitivamente.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base
from app.models.base_model import TimestampMixin


class NotaFiscalSaida(Base, TimestampMixin):
    __tablename__ = "notas_fiscais_saida"

    id: Mapped[int] = mapped_column(primary_key=True)

    pedido_venda_id: Mapped[int] = mapped_column(ForeignKey("pedidos_venda.id"), nullable=False)
    pedido_venda: Mapped["PedidoVenda"] = relationship()  # type: ignore[name-defined]

    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)

    # Dados da NF-e
    numero: Mapped[str | None] = mapped_column(String(15))
    serie: Mapped[str] = mapped_column(String(3), default="1")
    chave_acesso: Mapped[str | None] = mapped_column(String(44), unique=True)
    protocolo: Mapped[str | None] = mapped_column(String(20))

    data_emissao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_saida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    natureza_operacao: Mapped[str] = mapped_column(String(60), default="VENDA DE MERCADORIA")
    finalidade: Mapped[str] = mapped_column(String(1), default="1")  # 1=Normal, 2=Complementar, 3=Ajuste, 4=Devolução
    tipo_operacao: Mapped[str] = mapped_column(String(1), default="1")  # 1=Saída

    # Totais fiscais
    valor_produtos: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_frete: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_desconto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_icms_st: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_difal: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Status de transmissão SEFAZ
    # RASCUNHO | AGUARDANDO | AUTORIZADA | REJEITADA | CANCELADA | DENEGADA
    status_sefaz: Mapped[str] = mapped_column(String(15), default="RASCUNHO")
    motivo_rejeicao: Mapped[str | None] = mapped_column(Text)

    # Referência ao XML armazenado
    xml_path: Mapped[str | None] = mapped_column(String(255))
    danfe_path: Mapped[str | None] = mapped_column(String(255))

    # ID da requisição no Focus NF-e (para consultar status)
    focus_referencia: Mapped[str | None] = mapped_column(String(100))

    itens: Mapped[list["ItemNotaFiscalSaida"]] = relationship(
        back_populates="nota", cascade="all, delete-orphan"
    )


class ItemNotaFiscalSaida(Base):
    __tablename__ = "itens_nf_saida"

    id: Mapped[int] = mapped_column(primary_key=True)
    nota_id: Mapped[int] = mapped_column(ForeignKey("notas_fiscais_saida.id"), nullable=False)
    nota: Mapped["NotaFiscalSaida"] = relationship(back_populates="itens")

    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    produto: Mapped["Produto"] = relationship()  # type: ignore[name-defined]

    cfop: Mapped[str] = mapped_column(String(5), nullable=False)
    ncm: Mapped[str | None] = mapped_column(String(10))
    cst_icms: Mapped[str | None] = mapped_column(String(3))
    cst_ipi: Mapped[str | None] = mapped_column(String(2))
    cst_pis: Mapped[str | None] = mapped_column(String(2))
    cst_cofins: Mapped[str | None] = mapped_column(String(2))

    quantidade: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    valor_bruto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    valor_desconto: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    # Impostos do item
    base_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_icms: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_icms: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    valor_icms_st: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    base_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_ipi: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_ipi: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    base_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_pis: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_pis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    base_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    aliq_cofins: Mapped[Decimal] = mapped_column(Numeric(7, 4), default=0)
    valor_cofins: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
