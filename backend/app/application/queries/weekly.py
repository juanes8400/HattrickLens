"""Regla temporal única para lecturas derivadas de snapshots.

Los snapshots crudos se conservan completos para auditoría. Las gráficas y los
diffs sólo pueden mostrar una lectura por semana ISO: la última que Lens vio
esa semana. Así varios syncs no fabrican una tendencia diaria.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import TypeVar


T = TypeVar("T")


def iso_week_key(value: datetime) -> tuple[int, int]:
    iso = value.isocalendar()
    return iso.year, iso.week


def latest_per_iso_week(items: Iterable[T], captured_at: Callable[[T], datetime]) -> list[T]:
    """Last observed item from each ISO week, ordered chronologically."""
    latest: dict[tuple[int, int], T] = {}
    for item in sorted(items, key=captured_at):
        latest[iso_week_key(captured_at(item))] = item
    return list(latest.values())


def start_of_iso_week(value: datetime) -> datetime:
    """Monday 00:00 in the timestamp's timezone, for prior-week queries."""
    return value - timedelta(
        days=value.weekday(), hours=value.hour, minutes=value.minute,
        seconds=value.second, microseconds=value.microsecond,
    )
