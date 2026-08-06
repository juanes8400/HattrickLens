"""Dependency injection para la capa HTTP."""
from collections.abc import AsyncGenerator

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.dashboard import DashboardQueryService
from app.application.queries.squad import SquadQueryService
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.jwt import COOKIE_NAME, SessionTokenError, read_user_id


async def get_dashboard_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[DashboardQueryService, None]:
    yield DashboardQueryService(session)


async def get_squad_service(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[SquadQueryService, None]:
    yield SquadQueryService(session)


async def get_current_user(
    session: AsyncSession = Depends(get_session),
    htlens_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> m.User:
    """El usuario de la cookie de sesión. 401 si falta, caducó o fue alterada
    — nunca un usuario por defecto: `trigger_sync` actuaba antes como `user_id=0`
    para cualquiera, que es exactamente el agujero que esta dependencia cierra."""
    if htlens_session is None:
        raise HTTPException(401, "no hay sesión — conecta con Hattrick primero")
    try:
        user_id = read_user_id(htlens_session)
    except SessionTokenError as exc:
        raise HTTPException(401, str(exc)) from exc
    user = await session.get(m.User, user_id)
    if user is None:
        raise HTTPException(401, "la sesión no corresponde a ningún usuario")
    return user
