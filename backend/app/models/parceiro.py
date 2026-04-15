"""
Fornecedores, Clientes e Prestadores de Beneficiamento (ex: galvanizadores).
"""
from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base_model import TimestampMixin


class _ParceiroBase(Base, TimestampMixin):
    """Classe base abstrata para todos os parceiros comerciais."""
    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True)
    razao_social: Mapped[str] = mapped_column(String(150), nullable=False)
    nome_fantasia: Mapped[str | None] = mapped_column(String(150))
    cnpj_cpf: Mapped[str] = mapped_column(String(18), unique=True, nullable=False)
    ie: Mapped[str | None] = mapped_column(String(30))   # Inscrição Estadual
    im: Mapped[str | None] = mapped_column(String(30))   # Inscrição Municipal

    # Endereço
    logradouro: Mapped[str | None] = mapped_column(String(100))
    numero: Mapped[str | None] = mapped_column(String(10))
    complemento: Mapped[str | None] = mapped_column(String(60))
    bairro: Mapped[str | None] = mapped_column(String(60))
    municipio: Mapped[str | None] = mapped_column(String(60))
    uf: Mapped[str | None] = mapped_column(String(2))
    cep: Mapped[str | None] = mapped_column(String(9))
    codigo_municipio_ibge: Mapped[str | None] = mapped_column(String(7))

    # Contato
    telefone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(100))

    # Regime tributário do parceiro (importante para ICMS e NF-e)
    # 1=Simples Nacional, 2=Simples Nacional Excesso, 3=Regime Normal
    crt: Mapped[str] = mapped_column(String(1), default="3")

    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    observacoes: Mapped[str | None] = mapped_column(Text)


class Fornecedor(_ParceiroBase):
    __tablename__ = "fornecedores"

    # Condições comerciais
    prazo_entrega_dias: Mapped[int] = mapped_column(default=0)
    condicao_pagamento: Mapped[str | None] = mapped_column(String(60))


class Cliente(_ParceiroBase):
    __tablename__ = "clientes"

    # Indica se é consumidor final (afeta DIFAL e ICMS)
    consumidor_final: Mapped[bool] = mapped_column(Boolean, default=False)
    limite_credito: Mapped[float] = mapped_column(default=0.0)
    condicao_pagamento: Mapped[str | None] = mapped_column(String(60))


class PrestadorBeneficiamento(_ParceiroBase):
    """Empresa que realiza o banho (galvanização, niquelação, etc.)."""
    __tablename__ = "prestadores_beneficiamento"

    tipo_beneficiamento: Mapped[str | None] = mapped_column(String(60))  # Ex: Zincagem, Niquelação
    prazo_retorno_dias: Mapped[int] = mapped_column(default=7)
    percentual_perda_esperado: Mapped[float] = mapped_column(default=0.0)  # % histórico de perda
