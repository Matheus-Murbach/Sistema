from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional, List
import httpx

from app.core.database import get_db
from app.models.produto import Produto, UnidadeMedida
from app.integrations.ibpt import buscar_aliquotas_ncm
from app.api.v1.auth import get_current_user

router = APIRouter()


class ProdutoCreate(BaseModel):
    codigo: str
    codigo_barras: Optional[str] = None
    descricao: str
    tipo: str = "MATERIA_PRIMA"
    unidade_id: int
    ncm: Optional[str] = None
    cest: Optional[str] = None
    origem: str = "0"
    cst_icms: Optional[str] = None
    csosn: Optional[str] = None
    aliq_icms: Decimal = Decimal("0")
    cst_ipi: Optional[str] = None
    aliq_ipi: Decimal = Decimal("0")
    cst_pis: Optional[str] = None
    aliq_pis: Decimal = Decimal("0.65")
    cst_cofins: Optional[str] = None
    aliq_cofins: Decimal = Decimal("3.00")
    mva: Decimal = Decimal("0")
    preco_custo: Decimal = Decimal("0")
    preco_venda: Decimal = Decimal("0")
    estoque_minimo: Decimal = Decimal("0")
    estoque_maximo: Decimal = Decimal("0")
    observacoes: Optional[str] = None


class ProdutoUpdate(ProdutoCreate):
    codigo: Optional[str] = None
    descricao: Optional[str] = None
    unidade_id: Optional[int] = None


class ProdutoImportItem(BaseModel):
    codigo: str
    descricao: str
    tipo: str = "MATERIA_PRIMA"
    unidade: str = "UN"
    preco_custo: Decimal = Decimal("0")
    preco_venda: Decimal = Decimal("0")
    estoque_minimo: Decimal = Decimal("0")
    aliq_icms: Decimal = Decimal("0")
    aliq_ipi: Decimal = Decimal("0")
    aliq_pis: Decimal = Decimal("0.65")
    aliq_cofins: Decimal = Decimal("3.00")
    ncm: Optional[str] = None


class ImportacaoRequest(BaseModel):
    produtos: List[ProdutoImportItem]


@router.get("/unidades-medida")
async def listar_unidades(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(UnidadeMedida).order_by(UnidadeMedida.codigo))
    return result.scalars().all()


@router.get("/")
async def listar_produtos(
    q: Optional[str] = Query(None, description="Busca por código, barras ou descrição"),
    tipo: Optional[str] = None,
    ativo: bool = True,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Produto).where(Produto.ativo == ativo)
    if tipo:
        stmt = stmt.where(Produto.tipo == tipo)
    if q:
        stmt = stmt.where(
            or_(
                Produto.codigo.ilike(f"%{q}%"),
                Produto.descricao.ilike(f"%{q}%"),
                Produto.codigo_barras == q,
            )
        )
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    produtos = result.scalars().all()
    return produtos


@router.get("/ncm/{ncm}")
async def consultar_ncm(ncm: str):
    """Consulta descrição do NCM via BrasilAPI (gratuita, sem token)."""
    ncm_clean = ncm.strip().replace(".", "").replace("-", "").replace("/", "")
    if len(ncm_clean) != 8 or not ncm_clean.isdigit():
        raise HTTPException(400, "NCM deve ter exatamente 8 dígitos numéricos")
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"https://brasilapi.com.br/api/ncm/v1/{ncm_clean}")
            if resp.status_code == 404:
                raise HTTPException(404, f"NCM {ncm_clean} não encontrado na tabela TIPI")
            if resp.status_code != 200:
                raise HTTPException(503, "Serviço de consulta NCM indisponível no momento")
            data = resp.json()
            return {
                "ncm": ncm_clean,
                "descricao": data.get("descricao", ""),
                "aviso": "Alíquotas (ICMS, IPI, PIS, COFINS) devem ser confirmadas com seu contador",
            }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Erro ao consultar serviço de NCM")


@router.post("/importar")
async def importar_produtos(
    data: ImportacaoRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """Importa produtos em lote a partir de uma lista JSON. Ignora códigos já existentes."""
    unidades_result = await db.execute(select(UnidadeMedida))
    unidades: dict[str, int] = {u.codigo.upper(): u.id for u in unidades_result.scalars().all()}
    fallback_id = unidades.get("UN") or (list(unidades.values())[0] if unidades else None)

    criados = 0
    duplicados = 0
    erros: list[dict] = []

    for item in data.produtos:
        existing = await db.execute(select(Produto.id).where(Produto.codigo == item.codigo))
        if existing.scalar_one_or_none():
            duplicados += 1
            continue

        unidade_id = unidades.get(item.unidade.upper()) or fallback_id
        if not unidade_id:
            erros.append({"codigo": item.codigo, "erro": "Nenhuma unidade de medida cadastrada no sistema"})
            continue

        produto = Produto(
            codigo=item.codigo,
            descricao=item.descricao,
            tipo=item.tipo,
            unidade_id=unidade_id,
            preco_custo=item.preco_custo,
            preco_venda=item.preco_venda,
            estoque_minimo=item.estoque_minimo,
            aliq_icms=item.aliq_icms,
            aliq_ipi=item.aliq_ipi,
            aliq_pis=item.aliq_pis,
            aliq_cofins=item.aliq_cofins,
            ncm=item.ncm if item.ncm else None,
        )
        db.add(produto)
        criados += 1

    await db.commit()
    return {"criados": criados, "duplicados": duplicados, "erros": erros}


@router.get("/{produto_id}")
async def detalhar_produto(produto_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise HTTPException(404, "Produto não encontrado")
    return produto


@router.post("/", status_code=201)
async def criar_produto(
    data: ProdutoCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    produto = Produto(**data.model_dump())
    db.add(produto)
    await db.commit()
    await db.refresh(produto)
    return produto


@router.put("/{produto_id}")
async def atualizar_produto(
    produto_id: int,
    data: ProdutoUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise HTTPException(404, "Produto não encontrado")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(produto, k, v)
    await db.commit()
    await db.refresh(produto)
    return produto


@router.get("/{produto_id}/aliquotas-ncm")
async def buscar_aliquotas(produto_id: int, uf: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Busca alíquotas IBPT para o NCM do produto."""
    result = await db.execute(select(Produto).where(Produto.id == produto_id))
    produto = result.scalar_one_or_none()
    if not produto:
        raise HTTPException(404, "Produto não encontrado")
    if not produto.ncm:
        raise HTTPException(400, "Produto sem NCM cadastrado")
    aliquotas = await buscar_aliquotas_ncm(produto.ncm, uf)
    if not aliquotas:
        raise HTTPException(503, "Serviço IBPT indisponível ou token não configurado")
    return {
        "ncm": aliquotas.ncm,
        "descricao": aliquotas.descricao,
        "aliq_nacional": aliquotas.aliq_nacional,
        "aliq_importado": aliquotas.aliq_importado,
        "aliq_estadual": aliquotas.aliq_estadual,
        "aliq_municipal": aliquotas.aliq_municipal,
    }
