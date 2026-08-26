"""Sesión de HT Lens tras conectar con Hattrick.

No hay contraseña propia que verificar (ver `models.User`): el JWT es la
prueba de que este navegador completó el baile OAuth con CHPP para un
`user_id` dado. Vive en una cookie httpOnly — nunca en localStorage, para que
JS de terceros no pueda leerlo.

Dos tokens, dos cookies: el de ACCESO (`COOKIE_NAME`, corto — minutos) es el
que se manda en cada request; el de REFRESCO (`REFRESH_COOKIE_NAME`, largo —
días) solo se manda al endpoint `/auth/refresh`, que emite un acceso nuevo
sin obligar a repetir el baile OAuth. Antes solo existía el de acceso — con
`jwt_refresh_ttl_days` declarado en `settings` pero sin ningún código que lo
usara, la sesión moría de verdad cada `jwt_access_ttl_minutes` sin ningún
renovado silencioso detrás. La claim `type` evita que un token sirva donde
no debería (un refresco no autentica un request normal, ni viceversa).
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt

from app.core.config import settings

COOKIE_NAME = "htlens_session"
REFRESH_COOKIE_NAME = "htlens_refresh"
ALGORITHM = "HS256"

TokenType = Literal["access", "refresh"]


class SessionTokenError(Exception):
    """El JWT de sesión falta, expiró, fue alterado, o es del tipo equivocado."""


def _create_token(user_id: int, token_type: TokenType, ttl: timedelta) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_session_token(user_id: int) -> str:
    return _create_token(user_id, "access", timedelta(minutes=settings.jwt_access_ttl_minutes))


def create_refresh_token(user_id: int) -> str:
    return _create_token(user_id, "refresh", timedelta(days=settings.jwt_refresh_ttl_days))


def read_user_id(token: str, expected_type: TokenType = "access") -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        # Tokens emitidos antes de esta claim no la traen — se tratan como
        # "access", el único tipo que existía entonces.
        if payload.get("type", "access") != expected_type:
            raise SessionTokenError(f"se esperaba un token de tipo {expected_type}")
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise SessionTokenError("sesión inválida o caducada") from exc
