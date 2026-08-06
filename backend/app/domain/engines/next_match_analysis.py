"""Hechos y proyecciones mínimos para preparar el próximo partido.

No intenta reconstruir las habilidades privadas del rival ni sustituir el
simulador de Hattrick.  La resistencia, forma y experiencia vienen tal cual
de ``players.xml``; solamente el once probable se proyecta a partir de las
alineaciones públicas de partidos ya terminados.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any


FIELD_POSITION_CODES = frozenset(range(1, 15))


def line_for_position(position_code: int | None) -> str:
    """Agrupa los 14 slots de cancha en líneas legibles para el informe."""
    if position_code == 1:
        return "Portería"
    if position_code in {2, 3, 4, 5, 6}:
        return "Defensa"
    if position_code in {7, 11}:
        return "Bandas"
    if position_code in {8, 9, 10}:
        return "Mediocampo"
    if position_code in {12, 13, 14}:
        return "Delantera"
    return "Sin posición observada"


def probable_starters(
    players: list[dict[str, Any]],
    appearances: list[dict[str, Any]],
    limit: int = 11,
) -> list[dict[str, Any]]:
    """Forma un once probable sin afirmar que sea la alineación real.

    ``appearances`` contiene una fila por jugador y partido, ordenada de más
    antiguo a más reciente. Se priorizan presencia como titular, recurrencia,
    y finalmente recencia; el TSI solo rompe empates. Si no hay alineaciones
    públicas, se devuelve una muestra por TSI con posición desconocida.
    """
    by_id = {int(p["ht_player_id"]): p for p in players}
    counts: dict[int, int] = defaultdict(int)
    latest: dict[int, dict[str, Any]] = {}

    for index, appearance in enumerate(appearances, start=1):
        player_id = int(appearance["ht_player_id"])
        if player_id not in by_id or appearance.get("position_code") not in FIELD_POSITION_CODES:
            continue
        counts[player_id] += 1
        latest[player_id] = {**appearance, "recency": index}

    eligible = list(by_id)
    eligible.sort(
        key=lambda player_id: (
            -counts.get(player_id, 0),
            -int(latest.get(player_id, {}).get("recency", 0)),
            -int(by_id[player_id].get("tsi", 0)),
        )
    )

    rows: list[dict[str, Any]] = []
    for player_id in eligible[:limit]:
        player = by_id[player_id]
        seen = latest.get(player_id, {})
        position_code = seen.get("position_code")
        name = seen.get("name") or player.get("name") or f"Jugador {player_id}"
        stars = seen.get("rating_stars")
        end_stars = seen.get("rating_stars_end")
        star_drop = (
            round(float(stars) - float(end_stars), 2)
            if isinstance(stars, (int, float)) and isinstance(end_stars, (int, float))
            and stars > 0 and end_stars > 0
            else None
        )
        rows.append({
            "ht_player_id": player_id,
            "name": name,
            "position_code": position_code,
            "line": line_for_position(position_code),
            "starts_in_sample": counts.get(player_id, 0),
            "sample_size": len({a.get("match_id") for a in appearances if a.get("match_id")}),
            "tsi": int(player.get("tsi", 0)),
            "stamina": (
                int(player.get("stamina", 0)) if player.get("stamina_is_read", True) else None
            ),
            "form": int(player.get("form", 0)) if player.get("form_is_read", True) else None,
            "experience": (
                int(player.get("experience", 0)) if player.get("experience_is_read", True) else None
            ),
            "rating_stars": stars if isinstance(stars, (int, float)) and stars > 0 else None,
            "rating_stars_end": end_stars if isinstance(end_stars, (int, float)) and end_stars > 0 else None,
            "rating_star_drop": star_drop,
        })
    return rows


def direct_condition_summary(players: list[dict[str, Any]]) -> dict[str, Any]:
    """Resume lecturas actuales; no estima una resistencia futura.

    En Hattrick, 0 también es un nivel válido. Por eso no se interpreta un
    cero individual como "dato ausente" ni se reemplaza por un supuesto.
    """
    if not players:
        return {
            "players": 0,
            "stamina_available": False,
            "form_available": False,
            "experience_available": False,
            "stamina_avg": None,
            "stamina_median": None,
            "form_avg": None,
            "experience_avg": None,
            "low_stamina_count": 0,
            "by_line": [],
        }

    def average(rows: list[dict[str, Any]], key: str) -> float | None:
        values = [float(row[key]) for row in rows if row.get(key) is not None]
        return round(sum(values) / len(values), 1) if values else None

    def metric_available(key: str) -> bool:
        return any(player.get(key) is not None for player in players)

    by_line: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in players:
        by_line[str(player["line"])].append(player)
    line_order = ("Portería", "Defensa", "Bandas", "Mediocampo", "Delantera", "Sin posición observada")

    return {
        "players": len(players),
        "stamina_available": metric_available("stamina"),
        "form_available": metric_available("form"),
        "experience_available": metric_available("experience"),
        "stamina_avg": average(players, "stamina"),
        "stamina_median": (
            float(median(row["stamina"] for row in players if row.get("stamina") is not None))
            if metric_available("stamina") else None
        ),
        "form_avg": average(players, "form"),
        "experience_avg": average(players, "experience"),
        "low_stamina_count": sum(
            1 for row in players if row.get("stamina") is not None and row["stamina"] <= 5
        ),
        "by_line": [
            {
                "line": line,
                "players": len(by_line[line]),
                "stamina_avg": average(by_line[line], "stamina"),
                "form_avg": average(by_line[line], "form"),
                "experience_avg": average(by_line[line], "experience"),
            }
            for line in line_order
            if by_line.get(line)
        ],
    }
