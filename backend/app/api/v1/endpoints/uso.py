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
from sqlalchemy import delete, func, select
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


#: Los nombres de pantalla que el frontend puede mandar. Sirve para saber cuáles
#: NO ha abierto nadie -- lo que ningún ranking enseña. Se escribe aquí y no se
#: deriva de los eventos por el mismo motivo: si se derivara, una pantalla sin
#: visitas no existiría y es justo la que hay que ver.
MODULOS_CONOCIDOS: frozenset[str] = frozenset(
    {
        "Dashboard",
        "Club y cuerpo técnico",
        "Equipo",
        "Jugadores",
        "Posiciones",
        "Alineación",
        "Entrenamiento",
        "Juveniles",
        "Transferencias",
        "Partidos",
        "Liga",
        "Copa",
        "Rivales",
        "Economía",
        "Estadio",
        "Sincronización",
        "Cambios",
        "Alertas",
        "Transparencia",
        "Uso",
        "Alta: bienvenida",
        "Alta: conectado",
        "Alta: importación",
    }
)


async def _nombres_de_usuario(session: AsyncSession) -> dict[int, str]:
    """El nombre de Hattrick de cada usuario, por su id de fila.

    Una tabla de números no se lee. El nombre de acceso ya es publico dentro
    del juego, y esta pantalla solo la ve el dueño de la instalacion.
    """
    filas = await session.execute(select(m.User.id, m.User.login_name))
    return {fila.id: (fila.login_name or f"usuario {fila.id}") for fila in filas}


#: Quitar al dueño de la instalación de sus propias estadísticas.
#:
#: Pedido el 2026-09-05. Mientras la aplicación tenga pocos usuarios, el que la
#: hizo es también el que más la usa: sus visitas ahogan las de todos los
#: demás y el resumen deja de contestar «qué usa la gente» para contestar «qué
#: uso yo». Con esto se puede mirar cualquiera de las dos cosas.
#:
#: Filtra por `user_id`, no por si es administrador: quita a QUIEN PREGUNTA. Si
#: mañana hay dos administradores, cada uno se quita a sí mismo y sigue viendo
#: al otro, que es lo que se quiere.
EXCLUIRME = Query(False, description="Dejar fuera los eventos de quien pregunta")


@router.get("/usage")
async def resumen(
    dias: int = Query(30, ge=1, le=365),
    excluirme: bool = EXCLUIRME,
    session: AsyncSession = Depends(get_session),
    admin: m.User = Depends(require_admin),
) -> dict[str, Any]:
    """El resumen de uso de los últimos `dias`."""
    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=dias)
    condiciones = [m.UiEvent.at >= desde]
    if excluirme:
        condiciones.append(m.UiEvent.user_id != admin.id)
    filas = (
        (await session.execute(select(m.UiEvent).where(*condiciones).order_by(m.UiEvent.at)))
        .scalars()
        .all()
    )
    nombres = await _nombres_de_usuario(session)
    eventos = [
        uso.Evento(
            sesion=f.session_id,
            tipo=f.kind,
            modulo=f.module,
            etiqueta=f.label,
            cuando=f.at,
            visible_ms=f.visible_ms or 0,
            usuario=f.user_id,
            nombre=nombres.get(f.user_id, f"usuario {f.user_id}"),
        )
        for f in filas
    ]
    t = uso.totales(eventos)
    ss = uso.sesiones(eventos)
    gente = uso.por_usuario(eventos)
    activos = len(gente)
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
        # ── Quién usa qué ────────────────────────────────────────────────────
        # Todo lo de arriba agrega a TODA la gente en un número. Con doce
        # registrados eso esconde lo que hay que saber: si una pantalla la usan
        # nueve personas o una sola muchas veces (2026-09-01).
        "byUser": [
            {
                "userId": u.usuario,
                "name": u.nombre,
                "sessions": u.sesiones,
                "pages": u.paginas,
                "clicks": u.clics,
                "minutes": u.minutos,
                "activeDays": u.dias_activos,
                "clicksPerPage": u.clics_por_pagina,
                "favouriteModule": u.modulo_favorito,
                "firstSeen": u.primera_vez.isoformat() if u.primera_vez else None,
                "lastSeen": u.ultima_vez.isoformat() if u.ultima_vez else None,
                # El desglose va anidado y no en una ruta aparte: son doce
                # personas por veintitantas pantallas, unos cientos de líneas,
                # y así la fila se despliega sin ir otra vez al servidor.
                "modules": [
                    {
                        "module": d.modulo,
                        "visits": d.visitas,
                        "clicks": d.clics,
                        "minutes": d.minutos,
                        "avgSecondsPerVisit": d.media_por_visita_s,
                        "lastSeen": d.ultima_vez.isoformat() if d.ultima_vez else None,
                    }
                    for d in uso.modulos_de(eventos, u.usuario)
                ],
            }
            for u in gente
        ],
        # Volumen y cariño no son lo mismo: se publican los dos por separado
        # para que la pantalla no tenga que elegir por su cuenta.
        "adoption": [
            {
                "module": a.modulo,
                "users": a.usuarios,
                "reach": a.alcance(activos),
                "days": a.dias,
                "visits": a.visitas,
                "clicks": a.clics,
                "minutes": a.minutos,
                "visitsPerUser": a.visitas_por_usuario,
                "clicksPerVisit": a.clics_por_visita,
            }
            for a in uso.adopcion(eventos)
        ],
        "insideEach": [
            {"module": mod, "controls": [{"label": e, "clicks": n} for e, n in top]}
            for mod, top in uso.dentro_de(eventos).items()
        ],
        "activeUsers": activos,
        "registeredUsers": len(nombres),
        # Lo que NADIE abrió. Un ranking por uso deja el cero fuera del final,
        # donde no se ve, y una pantalla que nadie abre es una decisión
        # pendiente.
        "untouched": uso.nunca_tocado(eventos, sorted(MODULOS_CONOCIDOS)),
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


@router.get("/usage/log")
async def registro(
    dias: int = Query(30, ge=1, le=365),
    usuario: int | None = Query(None, description="id de fila del usuario"),
    modulo: str | None = Query(None),
    tipo: str | None = Query(None, pattern="^(page|click)$"),
    buscar: str | None = Query(None, max_length=120),
    desde_fila: int = Query(0, ge=0),
    cuantas: int = Query(200, ge=1, le=1000),
    excluirme: bool = EXCLUIRME,
    session: AsyncSession = Depends(get_session),
    admin: m.User = Depends(require_admin),
) -> dict[str, Any]:
    """El registro crudo, uno por uno y del más reciente al más viejo.

    Los resúmenes contestan «qué se usa». Esto contesta la otra mitad: qué hizo
    UNA persona, en qué orden. Un promedio no enseña que alguien entró a
    Alineación, tocó cuatro cosas y se fue a Jugadores; la secuencia sí.

    Se pagina en el servidor porque noventa días de una instalación viva son
    decenas de miles de filas y el navegador no tiene por qué recibirlas todas
    para enseñar doscientas.
    """
    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=dias)
    condiciones = [m.UiEvent.at >= desde]
    if excluirme:
        condiciones.append(m.UiEvent.user_id != admin.id)
    if usuario is not None:
        condiciones.append(m.UiEvent.user_id == usuario)
    if modulo:
        condiciones.append(m.UiEvent.module == modulo)
    if tipo:
        condiciones.append(m.UiEvent.kind == tipo)
    if buscar:
        # Sobre la etiqueta del control, que es lo único con texto. Nunca sobre
        # lo que el usuario escribe, porque eso no se guarda.
        condiciones.append(m.UiEvent.label.ilike(f"%{buscar}%"))

    total = (
        await session.execute(select(func.count()).select_from(m.UiEvent).where(*condiciones))
    ).scalar_one()
    filas = (
        (
            await session.execute(
                select(m.UiEvent)
                .where(*condiciones)
                # El desempate por `id` no es adorno: varias filas comparten
                # el mismo instante --una vista y sus clics llegan juntos-- y
                # sin un segundo criterio el reparto entre páginas queda al
                # azar, así que una fila puede salir dos veces o ninguna.
                .order_by(m.UiEvent.at.desc(), m.UiEvent.id.desc())
                .offset(desde_fila)
                .limit(cuantas)
            )
        )
        .scalars()
        .all()
    )
    nombres = await _nombres_de_usuario(session)

    return {
        "total": total,
        "from": desde_fila,
        "rows": [
            {
                "id": f.id,
                "at": f.at.isoformat(),
                "userId": f.user_id,
                "name": nombres.get(f.user_id, f"usuario {f.user_id}"),
                "session": f.session_id,
                "kind": f.kind,
                "module": f.module,
                "label": f.label,
                "visibleMs": f.visible_ms or 0,
            }
            for f in filas
        ],
        # Para llenar los desplegables del filtro sin una ruta más.
        "users": [{"userId": i, "name": n} for i, n in sorted(nombres.items(), key=lambda x: x[1])],
        "modules": sorted(MODULOS_CONOCIDOS),
    }
