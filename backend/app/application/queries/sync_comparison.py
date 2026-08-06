"""Structured comparison for the Changes screen.

Hattrick Control's useful idea is not the notification text itself.  It keeps
the last meaningful comparison visible and aggregates positive, negative and
net movement.  This query builds that report from our append-only snapshots;
no value is inferred from presentation strings and no synthetic data is used.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import start_of_iso_week
from app.domain.value_objects.ht_constants import CONFIDENCE, TEAM_SPIRIT
from app.infrastructure.db import models as m


PLAYER_METRICS: tuple[tuple[str, str, str], ...] = (
    ("tsi", "TSI", "TSI"),
    ("salary", "Salario", "SAL"),
    ("form", "Forma", "FO"),
    ("stamina", "Resistencia", "CO"),
    ("experience", "Experiencia", "EX"),
    ("keeper", "Portería", "PO"),
    ("defending", "Defensa", "DE"),
    ("playmaking", "Jugadas", "JU"),
    ("winger", "Lateral", "LA"),
    ("passing", "Pases", "PA"),
    ("scoring", "Anotación", "AN"),
    ("set_pieces", "Balón parado", "BP"),
)

POPULARITY: dict[int, str] = {
    0: "Sanguinarios",
    1: "Furiosos",
    2: "Irritados",
    3: "Tranquilos",
    4: "Contentos",
    5: "Satisfechos",
    6: "Delirantes",
    7: "Eufóricos",
    8: "Bailando en las calles",
    9: "Escribiendo poemas de amor",
}

MEANINGFUL_CATEGORIES = ("jugadores", "entrenamiento", "economía", "economia")


def _iso(sync: m.Sync | None) -> str | None:
    if sync is None:
        return None
    return (sync.finished_at or sync.started_at).isoformat()


def _metric_summary() -> dict[str, dict[str, Any]]:
    return {
        key: {
            "key": key,
            "label": label,
            "abbreviation": abbreviation,
            "upCount": 0,
            "upTotal": 0,
            "downCount": 0,
            "downTotal": 0,
            "net": 0,
        }
        for key, label, abbreviation in PLAYER_METRICS
    }


def _record_delta(summary: dict[str, dict[str, Any]], key: str, delta: int) -> None:
    metric = summary[key]
    metric["net"] += delta
    if delta > 0:
        metric["upCount"] += 1
        metric["upTotal"] += delta
    elif delta < 0:
        metric["downCount"] += 1
        metric["downTotal"] += delta


async def _previous_player_snapshot(
    session: AsyncSession, current: m.PlayerSnapshot
) -> m.PlayerSnapshot | None:
    return await session.scalar(
        select(m.PlayerSnapshot)
        .where(
            m.PlayerSnapshot.player_id == current.player_id,
            m.PlayerSnapshot.captured_at < start_of_iso_week(current.captured_at),
        )
        .order_by(m.PlayerSnapshot.captured_at.desc(), m.PlayerSnapshot.id.desc())
        .limit(1)
    )


async def _player_report(
    session: AsyncSession, team_id: int, sync_id: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = await session.execute(
        select(m.PlayerSnapshot, m.Player)
        .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        .where(m.PlayerSnapshot.sync_id == sync_id, m.Player.team_id == team_id)
        .order_by(m.Player.last_name, m.Player.first_name)
    )
    summary = _metric_summary()
    rows: list[dict[str, Any]] = []

    for current, player in result.all():
        previous = await _previous_player_snapshot(session, current)
        if previous is None:
            rows.append(
                {
                    "htPlayerId": player.ht_player_id,
                    "name": f"{player.first_name} {player.last_name}".strip(),
                    "tsi": current.tsi,
                    "tsiDelta": None,
                    "salary": current.salary,
                    "salaryDelta": None,
                    "isNew": True,
                    "changes": [
                        {
                            "key": "arrival",
                            "label": "Alta en la plantilla",
                            "abbreviation": "ALTA",
                            "before": None,
                            "current": True,
                            "delta": None,
                            "direction": "up",
                        }
                    ],
                }
            )
            continue

        changes: list[dict[str, Any]] = []
        for key, label, abbreviation in PLAYER_METRICS:
            before = getattr(previous, key)
            after = getattr(current, key)
            if before is None or after is None or before == after:
                continue
            delta = int(after) - int(before)
            _record_delta(summary, key, delta)
            if key not in {"tsi", "salary"}:
                changes.append(
                    {
                        "key": key,
                        "label": label,
                        "abbreviation": abbreviation,
                        "before": before,
                        "current": after,
                        "delta": delta,
                        "direction": "up" if delta > 0 else "down",
                    }
                )

        if previous.injury_level != current.injury_level:
            changes.append(
                {
                    "key": "injury",
                    "label": "Lesión",
                    "abbreviation": "LES",
                    "before": previous.injury_level,
                    "current": current.injury_level,
                    "delta": current.injury_level - previous.injury_level,
                    "direction": "up" if current.injury_level < previous.injury_level else "down",
                }
            )

        if previous.is_transfer_listed != current.is_transfer_listed:
            changes.append(
                {
                    "key": "market",
                    "label": "Mercado",
                    "abbreviation": "MER",
                    "before": previous.is_transfer_listed,
                    "current": current.is_transfer_listed,
                    "delta": None,
                    "direction": "neutral",
                }
            )

        tsi_delta = current.tsi - previous.tsi
        salary_delta = current.salary - previous.salary
        if changes or tsi_delta or salary_delta:
            rows.append(
                {
                    "htPlayerId": player.ht_player_id,
                    "name": f"{player.first_name} {player.last_name}".strip(),
                    "tsi": current.tsi,
                    "tsiDelta": tsi_delta,
                    "salary": current.salary,
                    "salaryDelta": salary_delta,
                    "isNew": False,
                    "changes": changes,
                }
            )

    return rows, list(summary.values())


async def _snapshot_for_sync_or_before(
    session: AsyncSession,
    model: type[m.TrainingSnapshot] | type[m.EconomySnapshot],
    team_id: int,
    sync: m.Sync,
) -> tuple[Any | None, Any | None, bool]:
    current = await session.scalar(
        select(model)
        .where(model.team_id == team_id, model.sync_id == sync.id)
        .order_by(model.id.desc())
        .limit(1)
    )
    exact = current is not None
    if current is None:
        current = await session.scalar(
            select(model)
            .where(model.team_id == team_id, model.captured_at <= (sync.finished_at or sync.started_at))
            .order_by(model.id.desc())
            .limit(1)
        )
    if current is None:
        return None, None, False
    previous = await session.scalar(
        select(model)
        .where(
            model.team_id == team_id,
            model.captured_at < start_of_iso_week(current.captured_at),
        )
        .order_by(model.captured_at.desc(), model.id.desc())
        .limit(1)
    )
    if not exact:
        previous = current
    return current, previous, exact


def _club_item(
    key: str,
    label: str,
    before: int | None,
    current: int | None,
    names: dict[int, str] | None = None,
) -> dict[str, Any]:
    def display(value: int | None) -> str | None:
        if value is None:
            return None
        if names is None:
            return f"{value:,}".replace(",", ".")
        return f"{names.get(value, 'Nivel')} ({value})"

    return {
        "key": key,
        "label": label,
        "before": before,
        "current": current,
        "beforeDisplay": display(before),
        "currentDisplay": display(current),
        "delta": None if before is None or current is None else current - before,
        "changed": before is not None and current is not None and before != current,
    }


async def _club_report(
    session: AsyncSession, team_id: int, sync: m.Sync
) -> list[dict[str, Any]]:
    training, old_training, _ = await _snapshot_for_sync_or_before(
        session, m.TrainingSnapshot, team_id, sync
    )
    economy, old_economy, _ = await _snapshot_for_sync_or_before(
        session, m.EconomySnapshot, team_id, sync
    )
    items: list[dict[str, Any]] = []
    if training is not None:
        items.extend(
            (
                _club_item(
                    "team_spirit",
                    "Espíritu del equipo",
                    old_training.morale if old_training else None,
                    training.morale,
                    TEAM_SPIRIT,
                ),
                _club_item(
                    "self_confidence",
                    "Confianza",
                    old_training.self_confidence if old_training else None,
                    training.self_confidence,
                    CONFIDENCE,
                ),
            )
        )
    if economy is not None:
        items.extend(
            (
                _club_item(
                    "fan_club_size",
                    "Número de socios",
                    old_economy.fan_club_size if old_economy else None,
                    economy.fan_club_size,
                ),
                _club_item(
                    "supporters_popularity",
                    "Aficionados",
                    old_economy.supporters_popularity if old_economy else None,
                    economy.supporters_popularity,
                    POPULARITY,
                ),
                _club_item(
                    "sponsors_popularity",
                    "Patrocinadores",
                    old_economy.sponsors_popularity if old_economy else None,
                    economy.sponsors_popularity,
                    POPULARITY,
                ),
            )
        )
    return items


async def _changes_for_sync(
    session: AsyncSession, sync_id: int | None
) -> list[dict[str, str]]:
    if sync_id is None:
        return []
    rows = (
        await session.execute(
            select(m.SyncChange)
            .where(m.SyncChange.sync_id == sync_id)
            .order_by(m.SyncChange.id)
        )
    ).scalars().all()
    return [{"category": row.category, "summary": row.summary} for row in rows]


async def build_sync_comparison(session: AsyncSession, team_id: int) -> dict[str, Any]:
    """Return the latest sync plus the most recent meaningful comparison.

    Detail syncs (one row per player/match) must not hide the full team sync.
    An empty repeated sync also must not erase the last useful comparison: the
    UI reports both timestamps and says explicitly when the report is older.
    """

    normal_sync_filter: Iterable[Any] = (
        m.Sync.team_id == team_id,
        m.Sync.kind.contains("players"),
    )
    latest = await session.scalar(
        select(m.Sync).where(*normal_sync_filter).order_by(m.Sync.started_at.desc()).limit(1)
    )
    if latest is None:
        return {
            "syncId": None,
            "syncedAt": None,
            "changes": [],
            "reportSyncId": None,
            "reportSyncedAt": None,
            "reportIsLatest": True,
            "reportChanges": [],
            "playerRows": [],
            "summary": list(_metric_summary().values()),
            "clubChanges": [],
        }

    meaningful_ids = (
        select(m.SyncChange.sync_id)
        .where(
            m.SyncChange.team_id == team_id,
            m.SyncChange.category.in_(MEANINGFUL_CATEGORIES),
        )
        .distinct()
    )
    report_sync = await session.scalar(
        select(m.Sync)
        .where(*normal_sync_filter, m.Sync.id.in_(meaningful_ids))
        .order_by(m.Sync.started_at.desc())
        .limit(1)
    )
    report_sync = report_sync or latest

    latest_changes = await _changes_for_sync(session, latest.id)
    report_changes = await _changes_for_sync(session, report_sync.id)
    player_rows, summary = await _player_report(session, team_id, report_sync.id)
    club_changes = await _club_report(session, team_id, report_sync)

    return {
        "syncId": latest.id,
        "syncedAt": _iso(latest),
        "changes": latest_changes,
        "reportSyncId": report_sync.id,
        "reportSyncedAt": _iso(report_sync),
        "reportIsLatest": report_sync.id == latest.id,
        "reportChanges": report_changes,
        "playerRows": player_rows,
        "summary": summary,
        "clubChanges": club_changes,
    }
