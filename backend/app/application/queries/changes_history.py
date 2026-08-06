"""Historical player changes for the Hattrick-Control-style Changes screen.

Unlike the last-sync report, this query walks the append-only player snapshots
and compares weekly closes. It never tries to reconstruct a skill pop from TSI
or presentation text: each before/after pair comes from CHPP values that were
actually saved for the player.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import latest_per_iso_week
from app.infrastructure.db import models as m

# 2026-08-05, pedido explícitamente: "los cambios de la página de cambios
# deben ser efímeros, máximo verse los de la última semana, nada más
# antiguo" — se sigue guardando todo (append-only, la tabla cruda no se
# toca), solo se DEJA DE MOSTRAR lo que ya pasó de una semana. El "antes" de
# un cambio dentro de la ventana puede venir de un snapshot más viejo (hace
# falta para calcular el delta) — el filtro va sobre `capturedAt` del
# cambio, no sobre qué snapshots se leen.
CHANGES_VISIBILITY_WINDOW = timedelta(days=7)

METRICS: tuple[tuple[str, str, str], ...] = (
    ("keeper", "Portería", "skill"),
    ("defending", "Defensa", "skill"),
    ("playmaking", "Jugadas", "skill"),
    ("winger", "Lateral", "skill"),
    ("passing", "Pases", "skill"),
    ("scoring", "Anotación", "skill"),
    ("set_pieces", "Balón parado", "skill"),
    ("stamina", "Condición", "skill"),
    ("experience", "Experiencia", "experience"),
    ("form", "Forma", "form"),
)


def _name(player: m.Player) -> str:
    return f"{player.first_name} {player.last_name}".strip()


def _event(
    current: m.PlayerSnapshot,
    player: m.Player,
    key: str,
    label: str,
    before: int,
    value: int,
) -> dict[str, Any]:
    return {
        "capturedAt": current.captured_at.isoformat(),
        "htPlayerId": player.ht_player_id,
        "name": _name(player),
        "key": key,
        "label": label,
        "before": before,
        "current": value,
        "delta": value - before,
    }


async def build_changes_history(
    session: AsyncSession,
    team_id: int,
    player_ht_id: int | None = None,
) -> dict[str, Any]:
    """Return every saved player delta plus one player's chronological series."""
    rows = (
        await session.execute(
            select(m.PlayerSnapshot, m.Player)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id)
            .order_by(m.PlayerSnapshot.captured_at, m.PlayerSnapshot.id)
        )
    ).all()

    snapshots: dict[int, list[tuple[m.PlayerSnapshot, m.Player]]] = defaultdict(list)
    for snapshot, player in rows:
        snapshots[player.ht_player_id].append((snapshot, player))

    # La misma regla de las gráficas: un cierre semanal, no un diff por cada
    # vez que se pulsó Sync. Los datos crudos quedan guardados en la tabla.
    snapshots = {
        player_id: latest_per_iso_week(entries, lambda item: item[0].captured_at)
        for player_id, entries in snapshots.items()
    }

    players = [
        {"htPlayerId": ht_player_id, "name": _name(items[-1][1])}
        for ht_player_id, items in snapshots.items()
    ]
    players.sort(key=lambda p: p["name"].casefold())

    latest_player = max(
        snapshots,
        key=lambda ht_player_id: snapshots[ht_player_id][-1][0].captured_at,
        default=None,
    )
    selected_player = player_ht_id if player_ht_id in snapshots else latest_player

    # `captured_at` de SQLite llega naive aunque la columna sea aware (mismo
    # caso que `sold_at` en sync_team.py) — el cutoff se calcula naive para
    # comparar contra el mismo tipo.
    cutoff = (datetime.now(UTC) - CHANGES_VISIBILITY_WINDOW).replace(tzinfo=None)

    grouped: dict[str, list[dict[str, Any]]] = {"skill": [], "experience": [], "form": []}
    for entries in snapshots.values():
        for (previous, _), (current, player) in zip(entries, entries[1:]):
            captured_at = current.captured_at
            if captured_at.tzinfo is not None:
                captured_at = captured_at.replace(tzinfo=None)
            if captured_at < cutoff:
                continue
            for key, label, group in METRICS:
                before = getattr(previous, key)
                value = getattr(current, key)
                if before is None or value is None or before == value:
                    continue
                grouped[group].append(_event(current, player, key, label, int(before), int(value)))

    for group in grouped.values():
        group.sort(key=lambda event: event["capturedAt"], reverse=True)

    series: list[dict[str, Any]] = []
    if selected_player is not None:
        for snapshot, _ in snapshots[selected_player]:
            series.append(
                {
                    "capturedAt": snapshot.captured_at.isoformat(),
                    "tsi": snapshot.tsi,
                    "salary": snapshot.salary,
                    "form": snapshot.form,
                    "experience": snapshot.experience,
                    "stamina": snapshot.stamina,
                }
            )

    return {
        "players": players,
        "selectedPlayerId": selected_player,
        "skillChanges": grouped["skill"],
        "experienceChanges": grouped["experience"],
        "formChanges": grouped["form"],
        "series": series,
    }
