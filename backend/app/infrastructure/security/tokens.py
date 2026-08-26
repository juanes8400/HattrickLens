"""Cifrado en reposo de los tokens OAuth de CHPP.

`chpp_tokens.oauth_token_enc`/`oauth_secret_enc` nunca guardan el token en
claro: son la credencial con la que HT Lens actúa contra Hattrick.org en
nombre del usuario, así que una fuga de la base de datos no debe filtrarlas.
Fernet (AES-128-CBC + HMAC) es simétrico y suficiente aquí — no hace falta
un KMS para una sola clave que ya vive fuera del repo (`.env`).
"""

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class TokenDecryptionError(Exception):
    """La clave de cifrado no coincide con la que cifró el token."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    return Fernet(settings.token_encryption_key.encode())


def encrypt_token(value: str) -> bytes:
    return _fernet().encrypt(value.encode())


def decrypt_token(value: bytes) -> str:
    try:
        return _fernet().decrypt(value).decode()
    except InvalidToken as exc:
        raise TokenDecryptionError(
            "no se pudo descifrar el token, TOKEN_ENCRYPTION_KEY no coincide con la que lo cifró"
        ) from exc
