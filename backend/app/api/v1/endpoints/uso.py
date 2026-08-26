"""Qué funcionalidad usa la gente.

2026-08-26, pedido por el usuario. Dos rutas: una donde el navegador deja lo
que ha hecho, y otra que devuelve el resumen ya masticado.

Lo que se guarda y lo que NO:

- Sí: el módulo, la etiqueta del control pulsado, el instante exacto, la
  sesión y el tiempo con la pestaña visible.
- No: nada que el usuario escriba. Ni el contenido de un campo, ni una
  búsqueda, ni un nombre de jugador. La etiqueta llega recortada a 120
  caracteres y quien la elige es el frontend, no un volcado del DOM.

El identificador de sesión lo pone el navegador y no identifica a nadie por sí
solo; el usuario sale de la sesión de la propia aplicación, que ya existía.
"""

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin
from app.domain.engines import uso_de_la_app as uso
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

#: Cuántos días se conserva el detalle. Pasado ese plazo la fila se borra: es
#: dato de comportamiento y no hace falta guardarlo para siempre.
DIAS_QUE_SE_GUARDA = 90

#: Tope por envío. El navegador manda en tandas; sin tope, una pestaña con un
#: fallo podría mandar un millón de filas de una vez.
MAXIMO_POR_TANDA = 50


class EventoEntrante(BaseModel):
    # Los nombres van en camelCase porque son EXACTAMENTE los que manda el
    # navegador; renombrarlos a snake_case rompe el contrato con el recolector
    # sin ganar nada. De ahi los `noqa: N815`.
    sessionId: str = Field(max_length=36)  # noqa: N815
    kind: str = Field(pattern="^(page|click)$")
    module: str = Field(max_length=64)
    label: str | None = Field(default=None, max_length=120)
    at: datetime
    visibleMs: int = Field(  # noqa: N815
        default=0, ge=0, le=24 * 60 * 60 * 1000
    )


class Tanda(BaseModel):
    events: list[EventoEntrante] = Field(max_length=MAXIMO_POR_TANDA)


@router.post("/usage/events", status_code=204)
async def recoger(
    tanda: Tanda,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> None:
    """Recoge una tanda de eventos del navegador.

    Devuelve 204 y nada más: el navegador manda esto en segundo plano --a veces
    con `sendBeacon`, que no espera respuesta-- así que cualquier cuerpo sería
    trabajo tirado.
    """
    ahora = datetime.now(UTC).replace(tzinfo=None)
    for e in tanda.events:
        cuando = e.at.replace(tzinfo=None) if e.at.tzinfo else e.at
        # El reloj del navegador no es de fiar --puede ir adelantado, o saltar
        # con un cambio de hora-- y una fecha futura ensuciaria todo lo que se
        # ordene o agrupe por tiempo.
        if cuando > ahora:
            cuando = ahora
        session.add(
            m.UiEvent(
                user_id=user.id,
                session_id=e.sessionId,
                kind=e.kind,
                module=e.module,
                label=e.label,
                at=cuando,
                visible_ms=e.visibleMs,
            )
        )
    await session.commit()


@router.get("/usage")
async def resumen(
    dias: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_session),
    _: m.User = Depends(require_admin),
) -> dict[str, Any]:
    """El resumen de uso de los últimos `dias`."""
    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=dias)
    filas = (
        (
            await session.execute(
                select(m.UiEvent).where(m.UiEvent.at >= desde).order_by(m.UiEvent.at)
            )
        )
        .scalars()
        .all()
    )
    eventos = [
        uso.Evento(
            sesion=f.session_id,
            tipo=f.kind,
            modulo=f.module,
            etiqueta=f.label,
            cuando=f.at,
            visible_ms=f.visible_ms or 0,
        )
        for f in filas
    ]
    t = uso.totales(eventos)
    ss = uso.sesiones(eventos)
    return {
        "days": dias,
        "totals": {
            "sessions": t.sesiones,
            "pages": t.paginas,
            "clicks": t.clics,
            "minutes": t.minutos,
            "medianSessionSeconds": t.duracion_media_s,
            "clicksPerSession": t.clics_por_sesion,
        },
        "modules": [
            {
                "module": u.modulo,
                "visits": u.visitas,
                "clicks": u.clics,
                "minutes": u.minutos,
                "avgSecondsPerVisit": u.media_por_visita_s,
                "lastSeen": u.ultima_vez.isoformat() if u.ultima_vez else None,
            }
            for u in uso.modulos(eventos)
        ],
        "topControls": [
            {"label": etiqueta, "clicks": n} for etiqueta, n in uso.mas_pulsado(eventos)
        ],
        "byHour": uso.por_hora(eventos),
        "recentSessions": [
            {
                "id": s.sesion,
                "startedAt": s.empezo.isoformat(),
                "seconds": s.duracion_s,
                "pages": s.paginas,
                "clicks": s.clics,
                "modules": sorted(s.modulos),
            }
            for s in ss[:25]
        ],
    }


async def podar_eventos_viejos(session: AsyncSession) -> int:
    """Borra el detalle que ya pasó del plazo.

    Sin esto la tabla crece sin fin: con cien usuarios activos son millones de
    filas al año, y el plan gratuito de la base ronda 1 GB.
    """
    corte = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=DIAS_QUE_SE_GUARDA)
    resultado = await session.execute(delete(m.UiEvent).where(m.UiEvent.at < corte))
    await session.commit()
    return resultado.rowcount or 0


@router.get("/usage/export.csv")
async def exportar(
    dias: int = Query(365, ge=1, le=3650),
    session: AsyncSession = Depends(get_session),
    _: m.User = Depends(require_admin),
) -> StreamingResponse:
    """El detalle en crudo, para guardarlo fuera.

    2026-08-26, y no es un adorno: la base del plan gratuito no tiene copias y
    en varios proveedores caduca. Todo lo demás de HT Lens se reconstruye
    sincronizando otra vez; esto no, porque no existe en Hattrick. Si se pierde
    la base sin haber exportado, el historial de uso se perdió.

    Se arma en memoria a propósito: con la poda a noventa días son unas pocas
    decenas de miles de filas, y montar un volcado por trozos para eso sería
    complicar el código sin ganar nada.
    """
    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=dias)
    filas = (
        (
            await session.execute(
                select(m.UiEvent).where(m.UiEvent.at >= desde).order_by(m.UiEvent.at)
            )
        )
        .scalars()
        .all()
    )

    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";")
    # Punto y coma y BOM: con coma y sin BOM, Excel en español mete la fila
    # entera en una sola columna y destroza los acentos.
    escritor.writerow(["cuando", "sesion", "usuario", "tipo", "modulo", "etiqueta", "visible_ms"])
    for f in filas:
        escritor.writerow(
            [
                f.at.isoformat(sep=" ", timespec="seconds"),
                f.session_id,
                f.user_id,
                f.kind,
                f.module,
                f.label or "",
                f.visible_ms or 0,
            ]
        )

    contenido = "﻿" + buffer.getvalue()
    hoy = datetime.now(UTC).strftime("%Y%m%d")
    return StreamingResponse(
        iter([contenido.encode("utf-8")]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="uso-htlens-{hoy}.csv"'},
    )
