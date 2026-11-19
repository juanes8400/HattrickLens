"""«Mejor alineación»: el once de la app, previsto por Hattrick sin enviarlo.

2026-11-19, pedido del usuario: poder ver la predicción con la mejor
alineación sin tener que enviarla. Es la opción de Rivales y Copa que va al
lado de «Alineación enviada».

QUÉ ES «LA MEJOR». La que propone la pantalla Alineación: el optimizador de
`lineup_optimizer`, con la matriz del Manual no Escrito y sus fórmulas de
forma, condición, experiencia y fidelidad. No mira al rival, ni la sede, ni la
táctica, ni si conviene rotar; por eso la pantalla avisa de que no es
necesariamente la más adecuada para ese partido (pedido del usuario).

DE DÓNDE SALEN LOS NÚMEROS. No los calculamos: se le pregunta a Hattrick con
`predictratings`, que devuelve los siete ratings de minuto 0 de una
alineación SIN guardarla. Así salen en la misma escala que los de la
alineación enviada y que los del rival. Comprobado en vivo el 2026-11-19: las
órdenes del partido se leyeron antes y después y no cambiaron.

La táctica que se manda es la Normal: la app no elige táctica para este once,
y el pronóstico del duelo aplica después la táctica habitual del equipo.
"""

from __future__ import annotations

from typing import Any

from app.domain.engines.lineup_optimizer import Lineup, best_formation
from app.domain.value_objects.alineacion_para_hattrick import alineacion_para_hattrick

#: Los siete sectores que Hattrick prevé. El balón parado no lo prevé.
SECTORES_PREVISTOS = (
    "midfield",
    "right_def",
    "central_def",
    "left_def",
    "right_att",
    "central_att",
    "left_att",
)

#: Los que hacen falta para que exista un once.
JUGADORES_DEL_ONCE = 11


def filas_del_once(lu: Lineup) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """El once y el banquillo del optimizador, en la forma del traductor."""
    once = [
        {
            "basePosition": a.base_position,
            "behaviour": a.behaviour,
            "htPlayerId": a.player["ht_player_id"],
        }
        for a in sorted(lu.assignments, key=lambda a: a.slot)
    ]
    banquillo = [{"slot": b.slot, "htPlayerId": b.player["ht_player_id"]} for b in lu.bench]
    return once, banquillo


def mejor_once(players: list[dict[str, Any]]) -> Lineup | None:
    """El once que propone Alineación sin ningún mando tocado, o nada si no
    hay gente para armarlo."""
    disponibles = [p for p in players if p.get("injury_level", -1) < 1]
    if len(disponibles) < JUGADORES_DEL_ONCE:
        return None
    try:
        lu, _ranking = best_formation(players)
    except ValueError:
        return None
    return lu


async def prevision_de_la_mejor(
    client: Any,
    players: list[dict[str, Any]],
    ht_match_id: int,
    ht_team_id: int,
    *,
    version: str,
    source_system: str = "hattrick",
) -> tuple[dict[str, int], str] | None:
    """Los siete ratings de minuto 0 de la mejor alineación, y su formación.

    `None` si no hay once, si Hattrick no la acepta o si falla: no tener la
    previsión no puede tumbar la pantalla, que cae a lo ya jugado y lo dice.
    """
    lu = mejor_once(players)
    if lu is None:
        return None
    once, banquillo = filas_del_once(lu)
    try:
        payload = alineacion_para_hattrick(once, banquillo, tactica=0)
        respuesta = await client.alineacion(
            ht_match_id,
            ht_team_id,
            payload,
            guardar=False,
            version=version,
            source_system=source_system,
        )
    except Exception:  # noqa: BLE001, sin previsión la ficha sigue (también AlineacionInvalidaError)
        return None
    prediccion = respuesta.get("prediction") if isinstance(respuesta, dict) else None
    if not isinstance(prediccion, dict):
        return None
    ratings = prediccion.get("ratings") or {}
    if any(not ratings.get(nombre) for nombre in SECTORES_PREVISTOS):
        return None
    return {nombre: int(ratings[nombre]) for nombre in SECTORES_PREVISTOS}, lu.formation
