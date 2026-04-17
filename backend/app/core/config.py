from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "Sistema ERP Industrial"
    DEBUG: bool = False

    # Banco de dados
    DATABASE_URL: str = "postgresql+asyncpg://sistema:sistema_dev@localhost:5432/sistema"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # Segurança
    SECRET_KEY: str = "dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Focus NF-e
    FOCUS_NFE_TOKEN: str = ""
    FOCUS_NFE_URL: str = "https://homologacao.focusnfe.com.br"

    # IBPT (tabela de impostos)
    IBPT_TOKEN: str = ""
    IBPT_CNPJ: str = ""

    # Dados da Empresa
    EMPRESA_CNPJ: str = ""
    EMPRESA_IE: str = ""
    EMPRESA_IM: str = ""
    EMPRESA_RAZAO_SOCIAL: str = ""
    EMPRESA_NOME_FANTASIA: str = ""
    EMPRESA_LOGRADOURO: str = ""
    EMPRESA_NUMERO: str = ""
    EMPRESA_BAIRRO: str = ""
    EMPRESA_MUNICIPIO: str = ""
    EMPRESA_UF: str = "SP"
    EMPRESA_CEP: str = ""
    EMPRESA_TELEFONE: str = ""
    EMPRESA_EMAIL: str = ""

    # CRT: 1=Simples Nacional, 2=Simples Nacional Excesso, 3=Regime Normal (Lucro Presumido/Real)
    EMPRESA_CRT: Literal["1", "2", "3"] = "3"

    # Certificado Digital
    CERTIFICADO_TIPO: Literal["A1", "A3"] = "A1"
    CERTIFICADO_PATH: str = "/app/certificados/certificado.pfx"
    CERTIFICADO_SENHA: str = ""


settings = Settings()
