from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db
from app.models.parceiro import Fornecedor, Cliente, PrestadorBeneficiamento
from app.api.v1.auth import get_current_user

router = APIRouter()


class ParceiroBase(BaseModel):
    razao_social: str
    nome_fantasia: Optional[str] = None
    cnpj_cpf: str
    ie: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    bairro: Optional[str] = None
    municipio: Optional[str] = None
    uf: Optional[str] = None
    cep: Optional[str] = None
    codigo_municipio_ibge: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    crt: str = "3"
    observacoes: Optional[str] = None


class FornecedorCreate(ParceiroBase):
    prazo_entrega_dias: int = 0
    condicao_pagamento: Optional[str] = None


class ClienteCreate(ParceiroBase):
    consumidor_final: bool = False
    limite_credito: float = 0.0
    condicao_pagamento: Optional[str] = None


class PrestadorCreate(ParceiroBase):
    tipo_beneficiamento: Optional[str] = None
    prazo_retorno_dias: int = 7
    percentual_perda_esperado: float = 0.0


def _build_router(Model, CreateSchema, prefix):
    sub = APIRouter()

    @sub.get("/")
    async def listar(
        q: Optional[str] = Query(None),
        skip: int = 0, limit: int = 50,
        db: AsyncSession = Depends(get_db),
    ):
        stmt = select(Model).where(Model.ativo == True)
        if q:
            stmt = stmt.where(or_(
                Model.razao_social.ilike(f"%{q}%"),
                Model.cnpj_cpf.ilike(f"%{q}%"),
            ))
        stmt = stmt.offset(skip).limit(limit)
        r = await db.execute(stmt)
        return r.scalars().all()

    @sub.get("/{id}")
    async def detalhar(id: int, db: AsyncSession = Depends(get_db)):
        r = await db.execute(select(Model).where(Model.id == id))
        obj = r.scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Não encontrado")
        return obj

    @sub.post("/", status_code=201)
    async def criar(data: CreateSchema, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
        obj = Model(**data.model_dump())
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return obj

    @sub.put("/{id}")
    async def atualizar(id: int, data: CreateSchema, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
        r = await db.execute(select(Model).where(Model.id == id))
        obj = r.scalar_one_or_none()
        if not obj:
            raise HTTPException(404, "Não encontrado")
        for k, v in data.model_dump(exclude_none=True).items():
            setattr(obj, k, v)
        await db.commit()
        await db.refresh(obj)
        return obj

    return sub


router.include_router(_build_router(Fornecedor, FornecedorCreate, "fornecedores"), prefix="/fornecedores", tags=["Fornecedores"])
router.include_router(_build_router(Cliente, ClienteCreate, "clientes"), prefix="/clientes", tags=["Clientes"])
router.include_router(_build_router(PrestadorBeneficiamento, PrestadorCreate, "prestadores"), prefix="/prestadores", tags=["Prestadores de Beneficiamento"])
