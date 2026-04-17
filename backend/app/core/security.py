"""
Utilitários de segurança: hashing de senhas e JWT HS256.

Implementação JWT usa apenas stdlib (hmac + hashlib) para evitar dependência
da biblioteca `cryptography` que pode ter incompatibilidades com extensões Rust.
"""
import hmac
import hashlib
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padding = (4 - len(s) % 4) % 4
    return base64.urlsafe_b64decode(s + "=" * padding)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria um token JWT assinado com HS256 usando apenas a stdlib."""
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = int(expire.timestamp())

    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}".encode()

    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        signing_input,
        hashlib.sha256,
    ).digest()

    return f"{header}.{body}.{_b64url_encode(sig)}"


def decode_token(token: str) -> Optional[dict]:
    """Verifica e decodifica um token JWT HS256."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b, body_b, sig_b = parts
        signing_input = f"{header_b}.{body_b}".encode()

        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            signing_input,
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(_b64url_decode(sig_b), expected_sig):
            return None

        payload = json.loads(_b64url_decode(body_b))

        # Verificar expiração
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            return None

        return payload
    except Exception:
        return None
