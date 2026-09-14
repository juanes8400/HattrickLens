"""La alineación que ya mandaste para un partido que aún no se juega.

Vivía dentro de la ficha de rival hasta el 2026-09-09, cuando la pantalla de
Copa pasó a ofrecer el mismo resumen «Alineación enviada». Se saca aquí porque
copiarlo habría dejado dos versiones de la misma regla, y la regla tiene
esquinas: qué hacer si faltan sectores, qué sistema de origen pedir, y que la
predicción se pide EN VIVO y no se fía del último sync.

QUÉ NO ESTÁ AQUÍ: los dos ratings de acciones indirectas a balón parado.
Hattrick prevé siete sectores para unas órdenes enviadas y no prevé esos dos
(comprobado el 2026-09-05 y otra vez el 2026-09-09). Quien use esto tiene que
completarlos con lo ya jugado, y decirlo en pantalla.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.commands.sync_team import FILE_VERSIONS
from app.infrastructure.db import models as m

#: Los siete sectores que Hattrick sí prevé para unas órdenes ya enviadas.
SECTORES_PREVISTOS: tuple[str, ...] = (
    "midfield",
    "right_def",
    "central_def",
    "left_def",
    "right_att",
    "central_att",
    "left_att",
)


@dataclass(frozen=True)
class AlineacionEnviada:
    """Unas órdenes ya mandadas para UN partido concreto.

    Viaja con el `ht_match_id` pegado a propósito: quien la reciba tiene que
    poder comprobar que es la del partido que está pronosticando, y no la de
    otro cruce pendiente.
    """

    ht_match_id: int
    #: Los siete sectores que Hattrick prevé. Nunca las indirectas.
    ratings: dict[str, int]
    #: La táctica de ESAS MISMAS órdenes, o `None` si no se pudo leer.
    tactica: int | None


def once_enviado(
    match: m.Match | None,
    players: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resuelve el once enviado contra el roster actual conservando el orden.

    Nueve es el mínimo legal para iniciar. Si faltan más jugadores en el
    roster actual (por venta, migración incompleta o JSON corrupto), se descarta
    la referencia completa en vez de presentar un promedio parcial engañoso.
    """
    if match is None or not match.submitted_lineup_json:
        return []
    try:
        rows = json.loads(match.submitted_lineup_json)
        player_ids = [
            int(row["ht_player_id"])
            for row in rows
            if isinstance(row, dict) and row.get("ht_player_id")
        ]
    except (TypeError, ValueError, KeyError):
        return []
    by_id = {int(player["ht_player_id"]): player for player in players}
    resolved = [by_id[player_id] for player_id in player_ids if player_id in by_id]
    return resolved if 9 <= len(resolved) <= 11 else []


def prediccion_guardada(match: m.Match | None) -> dict[str, int] | None:
    """Los siete ratings de minuto 0 ya sincronizados, o nada si falta uno.

    «O nada si falta uno» y no «los que haya»: seis sectores de una alineación
    y uno en blanco no describen ninguna alineación, y el hueco se acabaría
    leyendo como un cero, que es un rating pésimo y no un «no sé».
    """
    if match is None:
        return None
    values = {
        "midfield": match.submitted_rating_midfield,
        "right_def": match.submitted_rating_right_def,
        "central_def": match.submitted_rating_central_def,
        "left_def": match.submitted_rating_left_def,
        "right_att": match.submitted_rating_right_att,
        "central_att": match.submitted_rating_central_att,
        "left_att": match.submitted_rating_left_att,
    }
    if any(value is None for value in values.values()):
        return None
    return {key: int(value) for key, value in values.items() if value is not None}


async def orden_en_vivo(client: Any, match: m.Match) -> tuple[dict[str, int], int | None] | None:
    """La predicción de minuto 0 de las órdenes ya enviadas, y su táctica.

    `actionType=predictratings` es de solo lectura: Hattrick calcula los siete
    ratings para la alineación que YA está guardada, no envía ni modifica
    nada. Devuelve `None` si todavía no hay órdenes, y también si falla: no
    tener predicción no puede tumbar la pantalla.
    """
    sistema = (match.source_system or "hattrick").strip().lower()
    if sistema not in {"hattrick", "youth", "htointegrated"}:
        sistema = "hattrick"
    try:
        payload = await client.fetch(
            "matchorders",
            version=FILE_VERSIONS["matchorders"],
            matchID=match.ht_match_id,
            sourceSystem=sistema,
            actionType="predictratings",
        )
    except Exception:  # noqa: BLE001, sin predicción, la pantalla sigue entera
        return None
    prediccion = payload.get("prediction")
    if not isinstance(prediccion, dict):
        return None
    ratings = prediccion.get("ratings") or {}
    if any(ratings.get(nombre) is None for nombre in SECTORES_PREVISTOS):
        return None
    tactica = prediccion.get("tactic_type")
    return (
        {nombre: int(ratings[nombre]) for nombre in SECTORES_PREVISTOS},
        int(tactica) if tactica is not None else None,
    )


async def prediccion_en_vivo(client: Any, match: m.Match) -> dict[str, int] | None:
    """Sólo los siete ratings de `orden_en_vivo`, sin la táctica.

    Es lo que usan Copa y la ficha de rival, que pegan el resultado encima de
    un diccionario de ratings: devolverles también la táctica colaría una
    clave que no es un rating.
    """
    orden = await orden_en_vivo(client, match)
    return orden[0] if orden is not None else None


async def alineacion_enviada_de(client: Any | None, match: m.Match) -> AlineacionEnviada | None:
    """Tus órdenes para ese partido: las sincronizadas, o si no, en vivo.

    La MISMA regla que Copa --la guardada primero, la de en vivo si no hay--
    con una diferencia que importa: la táctica viaja EMPAREJADA con sus
    ratings. La sincronizada va con la táctica sincronizada; la de en vivo, con
    la que Hattrick devuelve en esa misma respuesta. Cruzarlas pegaría una
    táctica vieja a unas órdenes nuevas.

    `client` puede ser `None`, sin sesión: entonces sólo vale la sincronizada.
    """
    guardada = prediccion_guardada(match)
    if guardada is not None:
        return AlineacionEnviada(match.ht_match_id, guardada, match.submitted_tactic_type)
    if client is None:
        return None
    orden = await orden_en_vivo(client, match)
    if orden is None:
        return None
    return AlineacionEnviada(match.ht_match_id, orden[0], orden[1])


async def partido_pendiente_contra(
    session: AsyncSession,
    own_ht_team_id: int,
    rival_ht_team_id: int,
) -> m.Match | None:
    """El próximo partido contra ese rival, haya o no órdenes sincronizadas.

    Hasta 2026-08-19 exigía `orders_given=True`, que es un dato del ÚLTIMO
    sync: si mandabas la alineación después de sincronizar, la pantalla no se
    enteraba hasta el siguiente sync. La predicción se pide ahora en vivo con
    `actionType=predictratings`, y esa llamada ya responde por sí sola si hay
    órdenes o no.
    """
    return await session.scalar(  # type: ignore[no-any-return]
        select(m.Match)
        .where(
            or_(
                and_(
                    m.Match.home_team_ht_id == own_ht_team_id,
                    m.Match.away_team_ht_id == rival_ht_team_id,
                ),
                and_(
                    m.Match.away_team_ht_id == own_ht_team_id,
                    m.Match.home_team_ht_id == rival_ht_team_id,
                ),
            ),
            ~m.Match.status.ilike("finished"),
        )
        .order_by(m.Match.played_at.asc())
        .limit(1)
    )
