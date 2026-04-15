"""
Integração com Focus NF-e para emissão e consulta de NF-e.

Documentação: https://focusnfe.com.br/doc/
Endpoints principais:
  POST /v2/nfe          - Emitir NF-e
  GET  /v2/nfe/{ref}    - Consultar status
  DELETE /v2/nfe/{ref}  - Cancelar NF-e

A referência (ref) é gerada pelo nosso sistema para identificar a nota.
"""
import httpx
from typing import Optional
from app.core.config import settings


class FocusNFeClient:
    def __init__(self):
        self.base_url = settings.FOCUS_NFE_URL
        self.token = settings.FOCUS_NFE_TOKEN
        self._auth = (self.token, "")

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    async def emitir_nfe(self, referencia: str, dados_nfe: dict) -> dict:
        """
        Emite uma NF-e.
        referencia: identificador único da nota no nosso sistema (ex: "NF-2024-001234")
        dados_nfe: payload no formato Focus NF-e
        Retorna dict com status e dados da NF-e.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.base_url}/v2/nfe?ref={referencia}",
                json=dados_nfe,
                auth=self._auth,
                headers=self._headers(),
            )
            return {"status_code": resp.status_code, "data": resp.json()}

    async def consultar_nfe(self, referencia: str) -> dict:
        """Consulta o status de uma NF-e pelo identificador."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/v2/nfe/{referencia}",
                auth=self._auth,
            )
            return {"status_code": resp.status_code, "data": resp.json()}

    async def cancelar_nfe(self, referencia: str, justificativa: str) -> dict:
        """Cancela uma NF-e autorizada (mínimo 15 caracteres na justificativa)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{self.base_url}/v2/nfe/{referencia}",
                json={"justificativa": justificativa},
                auth=self._auth,
                headers=self._headers(),
            )
            return {"status_code": resp.status_code, "data": resp.json()}

    async def download_danfe(self, referencia: str) -> Optional[bytes]:
        """Baixa o PDF do DANFE."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v2/nfe/{referencia}/danfe",
                auth=self._auth,
            )
            if resp.status_code == 200:
                return resp.content
            return None

    async def download_xml(self, referencia: str) -> Optional[bytes]:
        """Baixa o XML da NF-e autorizada."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/v2/nfe/{referencia}/xml",
                auth=self._auth,
            )
            if resp.status_code == 200:
                return resp.content
            return None


focus_nfe = FocusNFeClient()
