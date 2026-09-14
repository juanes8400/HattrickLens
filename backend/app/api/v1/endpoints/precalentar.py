"""Deja calculado lo que se va a ver, justo al terminar un sync (2026-09-14).

Con la caché por sync (`app/api/cache_por_sync.py`) la segunda visita es
instantánea, pero la primera después de sincronizar seguía pagando todos los
cálculos. Aquí se hacen en segundo plano en cuanto el sync termina, con las
mismas funciones y los mismos parámetros que piden las pantallas, así que
cuando el usuario abre el Dashboard ya está todo guardado.

NUNCA TUMBA NADA: corre aparte del sync, y si algo falla se anota y se sigue
con lo siguiente. Lo peor que puede pasar es que esa pantalla calcule al abrirla,
que es lo que pasaba siempre.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

#: Referencias a las tareas en marcha: sin ellas el recolector podría llevarse
#: una a medias.
_tareas: set[asyncio.Task[Any]] = set()


def lanzar_precalentado(team_id: int) -> None:
    try:
        tarea = asyncio.get_running_loop().create_task(precalentar(team_id))
    except RuntimeError:
        return
    _tareas.add(tarea)
    tarea.add_done_callback(_tareas.discard)


async def precalentar(team_id: int) -> None:
    # Imports aquí dentro: estos módulos importan `teams`, que importa este.
    from app.api.v1.endpoints.analysis import lineup
    from app.api.v1.endpoints.cup import cup
    from app.api.v1.endpoints.economy import economy
    from app.api.v1.endpoints.league import (
        league_comparison,
        league_sectores_recientes,
        liga_calculada,
        team_of_the_week,
    )
    from app.api.v1.endpoints.matches import matches
    from app.api.v1.endpoints.teams import changes_history
    from app.domain.engines.rival_scouting import PitchZoneMethod
    from app.infrastructure.db import models as m
    from app.infrastructure.db.session import SessionLocal

    async with SessionLocal() as session:
        team = await session.get(m.Team, team_id)
        if team is None:
            return
        usuario = await session.get(m.User, team.owner_user_id) if team.owner_user_id else None

        # Lo del Dashboard primero, que es lo que se abre al volver; después
        # lo de las pantallas que se suelen mirar tras sincronizar.
        pasos: list[tuple[str, Any]] = [
            ("liga (2.000)", lambda: liga_calculada(session, team_id, 2000)),
            ("sectores", lambda: league_sectores_recientes(team_id, session)),
            ("economía del Dashboard", lambda: economy(team_id, 52, False, session)),
            ("partidos", lambda: matches(team_id, False, None, session)),
            ("subidas", lambda: changes_history(team_id, None, 1, session)),
            (
                "mejor once",
                lambda: lineup(team_id, None, None, None, None, None, session),
            ),
            (
                "copa",
                lambda: cup(team_id, PitchZoneMethod.SUBMITTED, PitchZoneMethod.AVERAGE, session),
            ),
            ("liga (10.000)", lambda: liga_calculada(session, team_id, 10_000)),
            ("economía", lambda: economy(team_id, 52, True, session)),
        ]
        if usuario is not None:
            pasos.insert(
                2,
                (
                    "comparativa de liga",
                    lambda: league_comparison(team_id, False, True, session, usuario),
                ),
            )
            # Lo que pide la pestaña Comparativa de Liga al abrirse: la
            # comparativa en escala logarítmica y la mejor alineación de la
            # última jornada en 4-4-2 (2026-09-14).
            pasos += [
                (
                    "comparativa de Liga",
                    lambda: league_comparison(team_id, True, True, session, usuario),
                ),
                (
                    "mejor alineación de la jornada",
                    lambda: team_of_the_week(
                        team_id, "week", "4-4-2", None, None, None, session, usuario
                    ),
                ),
            ]

        for nombre, paso in pasos:
            try:
                await paso()
            except Exception as exc:  # noqa: BLE001, precalentar nunca tumba nada
                logger.info("precalentado de %s para el equipo %s: %s", nombre, team_id, exc)
                await session.rollback()
