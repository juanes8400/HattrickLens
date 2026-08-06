"""OAuth 1.0a dance con CHPP — la única forma de iniciar sesión en HT Lens.

No hay registro con email/contraseña: conectar con Hattrick.org ES la cuenta.
Ver docs/04-chpp-sync.md para el diagrama de secuencia completo, y
docs/spec/CORRECTIONS.md #1 para por qué es OAuth 1.0a y no OAuth2.
"""
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.sync_team import FILE_VERSIONS
from app.core.config import settings
from app.infrastructure.chpp.client import CHPPClient, CHPPOAuthDance
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.jwt import (
    COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    SessionTokenError,
    create_refresh_token,
    create_session_token,
    read_user_id,
)
from app.infrastructure.security.tokens import encrypt_token

router = APIRouter()
_pending: dict[str, str] = {}  # TODO producción: Redis con TTL, no memoria de proceso


def _set_session_cookies(response: Response, user_id: int) -> None:
    """Instala las dos cookies de sesión: acceso (corta) y refresco (larga).
    Se usa al conectar (dev-session, callback OAuth) y al renovar."""
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(user_id),
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_access_ttl_minutes * 60,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        create_refresh_token(user_id),
        httponly=True,
        samesite="lax",
        max_age=settings.jwt_refresh_ttl_days * 86400,
    )


@router.get("/connect")
async def connect() -> dict[str, str]:
    """Arranca el baile: pide un request token y devuelve la URL de Hattrick
    donde el usuario inicia sesión y autoriza HT Lens."""
    dance = CHPPOAuthDance()
    url, token, secret = await dance.get_authorize_url()
    _pending[token] = secret
    return {"authorizeUrl": url}


@router.get("/dev-session")
async def dev_session(user_id: int = 1, team_id: int | None = 1) -> RedirectResponse:
    """Instala una cookie de sesión para desarrollo local.

    Sirve para probar la UI en puertos nuevos sin repetir el OAuth dance.
    No crea tokens CHPP ni funciona fuera de `ENVIRONMENT=local`.
    """
    if settings.environment != "local":
        raise HTTPException(404, "no disponible")

    redirect_url = f"{settings.frontend_url}/connected"
    if team_id is not None:
        redirect_url += f"?teamId={team_id}"
    response = RedirectResponse(url=redirect_url)
    _set_session_cookies(response, user_id)
    return response


@router.post("/refresh")
async def refresh(
    session: AsyncSession = Depends(get_session),
    htlens_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
) -> Response:
    """Renueva la cookie de acceso (y rota la de refresco) sin repetir el
    baile OAuth. El frontend la llama sola cuando un request devuelve 401;
    el usuario nunca la ve — solo nota (o ya no nota) que dejó de tener que
    reconectar cada `jwt_access_ttl_minutes`."""
    if htlens_refresh is None:
        raise HTTPException(401, "no hay sesión para renovar — conecta con Hattrick")
    try:
        user_id = read_user_id(htlens_refresh, expected_type="refresh")
    except SessionTokenError as exc:
        raise HTTPException(401, str(exc)) from exc
    user = await session.get(m.User, user_id)
    if user is None:
        raise HTTPException(401, "la sesión no corresponde a ningún usuario")

    response = Response(status_code=204)
    _set_session_cookies(response, user.id)
    return response


@router.get("/callback")
async def callback(
    oauth_token: str,
    oauth_verifier: str,
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Hattrick redirige aquí tras la autorización. Cambia el verifier por el
    access token definitivo, identifica al usuario y sus equipos (teamdetails),
    los persiste, y deja al navegador con una cookie de sesión."""
    secret = _pending.pop(oauth_token, None)
    if secret is None:
        raise HTTPException(400, "oauth_token desconocido o ya usado")

    dance = CHPPOAuthDance()
    access_token, access_secret = await dance.exchange(oauth_token, secret, oauth_verifier)

    client = CHPPClient(access_token, access_secret)
    try:
        details = await client.fetch("teamdetails", version=FILE_VERSIONS["teamdetails"])
    finally:
        await client.aclose()

    ht_user_id = details.get("ht_user_id", 0)
    if not ht_user_id:
        raise HTTPException(502, "Hattrick no devolvió un UserID válido")

    user = await session.scalar(select(m.User).where(m.User.ht_user_id == ht_user_id))
    if user is None:
        user = m.User(
            ht_user_id=ht_user_id,
            login_name=details.get("login_name", ""),
            created_at=datetime.now(UTC),
        )
        session.add(user)
        await session.flush()  # asigna user.id
    else:
        user.login_name = details.get("login_name") or user.login_name

    token_row = await session.scalar(
        select(m.CHPPToken).where(m.CHPPToken.user_id == user.id)
    )
    if token_row is None:
        token_row = m.CHPPToken(user_id=user.id)
        session.add(token_row)
    token_row.oauth_token_enc = encrypt_token(access_token)
    token_row.oauth_secret_enc = encrypt_token(access_secret)
    token_row.status = "active"
    token_row.ht_user_id = ht_user_id

    first_team_id: int | None = None
    for t in details.get("teams", []):
        ht_team_id = t.get("ht_team_id", 0)
        if not ht_team_id:
            continue
        team = await session.scalar(select(m.Team).where(m.Team.ht_team_id == ht_team_id))
        if team is None:
            team = m.Team(ht_team_id=ht_team_id, name=t.get("name", ""))
            session.add(team)
            await session.flush()  # asigna team.id
        team.owner_user_id = user.id
        team.name = t.get("name") or team.name
        team.league_name = t.get("league_name") or team.league_name
        team.series_name = t.get("series_name") or team.series_name
        team.series_ht_id = t.get("series_ht_id") or team.series_ht_id
        if first_team_id is None:
            first_team_id = team.id

    await session.commit()

    redirect_url = f"{settings.frontend_url}/connected"
    if first_team_id is not None:
        redirect_url += f"?teamId={first_team_id}"
    response = RedirectResponse(url=redirect_url)
    _set_session_cookies(response, user.id)
    return response
