"""
Integração com a tabela IBPT para busca automática de alíquotas por NCM.
Retorna alíquotas de ICMS, IPI, PIS, COFINS para um dado NCM e UF.

API: https://apidoni.ibpt.org.br/api/v1/produtos
Documentação: https://ibpt.com.br/
"""
import httpx
from typing import Optional
from app.core.config import settings


IBPT_URL = "https://apidoni.ibpt.org.br/api/v1/produtos"


class AliquotasNCM:
    def __init__(
        self,
        ncm: str,
        descricao: str,
        aliq_nacional: float,
        aliq_importado: float,
        aliq_estadual: float,
        aliq_municipal: float,
    ):
        self.ncm = ncm
        self.descricao = descricao
        self.aliq_nacional = aliq_nacional        # % total federal (IRPJ, CSLL, PIS, COFINS, IPI...)
        self.aliq_importado = aliq_importado
        self.aliq_estadual = aliq_estadual         # ICMS médio no estado
        self.aliq_municipal = aliq_municipal       # ISS (se aplicável)


async def buscar_aliquotas_ncm(ncm: str, uf: str = None) -> Optional[AliquotasNCM]:
    """
    Busca alíquotas pelo NCM do produto na tabela IBPT.
    Retorna None se não encontrar ou se a API estiver indisponível.
    """
    uf = uf or settings.EMPRESA_UF
    if not settings.IBPT_TOKEN:
        return None

    params = {
        "token": settings.IBPT_TOKEN,
        "cnpj": settings.IBPT_CNPJ,
        "codigo": ncm,
        "uf": uf,
        "ex": "0",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(IBPT_URL, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
            return AliquotasNCM(
                ncm=ncm,
                descricao=data.get("Descricao", ""),
                aliq_nacional=float(data.get("Nacional", 0)),
                aliq_importado=float(data.get("Importado", 0)),
                aliq_estadual=float(data.get("Estadual", 0)),
                aliq_municipal=float(data.get("Municipal", 0)),
            )
    except Exception:
        return None
