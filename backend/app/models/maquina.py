from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.base_model import TimestampMixin


class Maquina(Base, TimestampMixin):
    __tablename__ = "maquinas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    setor: Mapped[str | None] = mapped_column(String(60))
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    observacoes: Mapped[str | None] = mapped_column(Text)
