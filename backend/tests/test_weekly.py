"""weekly.py — cierre semanal por ISO week y etiqueta "TT-ss".

`season_week_label`/`season_week_offset_for`: 2026-08-09, pedido
explícitamente — MatchRound de worlddetails.xml v2.0 ES la semana real de
temporada (1-16, confirmado por el usuario), no la jornada de liga. Se fija
esa versión explícita en sync_team.py (ver FILE_VERSIONS) para no depender
de que un cambio de versión por defecto de CHPP altere el significado en
silencio.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from app.application.queries.weekly import (
    changes_only,
    iso_week_key,
    latest_per_iso_week,
    season_week_label,
    season_week_offset_for,
    start_of_iso_week,
)


@dataclass
class FakeWorld:
    """Duck-types WorldContext para estos tests — solo los 3 campos que
    `season_week_*` realmente lee."""
    season: int
    match_round: int
    refreshed_at: datetime


NOW = datetime(2026, 8, 9, 13, 25, 12, tzinfo=UTC)
# Caso real verificado en vivo 2026-08-09: Colombia, temporada 83, semana 3.
WORLD = FakeWorld(season=83, match_round=3, refreshed_at=NOW)


def test_season_week_label_matches_the_live_verified_case() -> None:
    assert season_week_label(WORLD) == "83-03"


def test_season_week_label_is_none_without_a_world_context() -> None:
    assert season_week_label(None) is None


def test_season_week_offset_for_a_past_date_is_negative() -> None:
    two_weeks_ago = NOW.replace(day=26, month=7)  # 14 días antes
    offset = season_week_offset_for(WORLD, two_weeks_ago)
    assert offset == -2
    assert season_week_label(WORLD, weeks_offset=offset) == "83-01"


def test_season_week_offset_clamps_a_date_at_or_after_refreshed_at_to_zero() -> None:
    """Bug real encontrado y corregido en el backfill de Standing.season: un
    `when` a segundos de `refreshed_at` no debe redondear hacia -infinito y
    contar como "una semana adelantada"."""
    just_after = NOW.replace(minute=26)  # 48 segundos después de refreshed_at
    assert season_week_offset_for(WORLD, just_after) == 0
    assert season_week_label(WORLD, weeks_offset=0) == "83-03"


def test_season_week_offset_never_collapses_two_different_iso_weeks() -> None:
    """Caso real reportado por el usuario 2026-08-09: dos lecturas de dos
    semanas ISO DISTINTAS (2026-08-02 = semana ISO 31, 2026-08-09 = semana
    ISO 32 — domingo a domingo, exactamente 7 días de calendario, pero
    `latest_per_iso_week` ya las trata como cubos distintos) salían con la
    MISMA etiqueta "83-03" porque la cuenta original partía de AHORA en vez
    de anclar al lunes de cada semana ISO. Con el ancla correcta, dos
    semanas ISO distintas nunca pueden compartir offset."""
    reading_week_31 = datetime(2026, 8, 2, 0, 27, 54, tzinfo=UTC)
    reading_week_32 = datetime(2026, 8, 9, 14, 23, 34, tzinfo=UTC)  # la más reciente

    offset_31 = season_week_offset_for(WORLD, reading_week_31)
    offset_32 = season_week_offset_for(WORLD, reading_week_32)

    assert offset_31 != offset_32
    assert season_week_label(WORLD, weeks_offset=offset_31) != season_week_label(
        WORLD, weeks_offset=offset_32
    )
    assert season_week_label(WORLD, weeks_offset=offset_32) == "83-03"
    assert season_week_label(WORLD, weeks_offset=offset_31) == "83-02"


def test_season_week_label_rolls_over_into_the_previous_season() -> None:
    # 5 semanas antes de la semana 3 de la temporada 83 -> semana 14 de la 82.
    assert season_week_label(WORLD, weeks_offset=-5) == "82-14"


def test_season_week_label_rolls_over_into_the_next_season_for_forecasts() -> None:
    # La temporada 83 tiene 16 semanas: semana 3 + 13 = semana 16, todavía
    # dentro de la 83; una semana más ya cruza a la temporada 84, semana 1.
    assert season_week_label(WORLD, weeks_offset=13) == "83-16"
    assert season_week_label(WORLD, weeks_offset=14) == "84-01"


def test_changes_only_keeps_the_first_point_and_only_real_changes() -> None:
    """2026-08-12, pedido explícito para Espíritu/Confianza y Socios en
    Club: un punto por cambio real de valor, no uno por semana ni uno por
    sync — dos lecturas seguidas con el mismo valor no son un "snapshot
    nuevo", son la misma foto otra vez."""
    @dataclass
    class Reading:
        captured_at: datetime
        value: int

    readings = [
        Reading(datetime(2026, 8, 1, tzinfo=UTC), 5),
        Reading(datetime(2026, 8, 3, tzinfo=UTC), 5),   # sin cambio: se descarta
        Reading(datetime(2026, 8, 5, tzinfo=UTC), 7),   # cambió: se guarda
        Reading(datetime(2026, 8, 12, tzinfo=UTC), 7),  # sin cambio: se descarta
        Reading(datetime(2026, 8, 20, tzinfo=UTC), 6),  # cambió: se guarda
    ]
    kept = changes_only(readings, lambda r: r.captured_at, lambda r: r.value)
    assert [r.value for r in kept] == [5, 7, 6]
    assert [r.captured_at for r in kept] == [
        datetime(2026, 8, 1, tzinfo=UTC),
        datetime(2026, 8, 5, tzinfo=UTC),
        datetime(2026, 8, 20, tzinfo=UTC),
    ]


def test_changes_only_handles_a_single_reading() -> None:
    @dataclass
    class Reading:
        captured_at: datetime
        value: int

    only = [Reading(datetime(2026, 8, 1, tzinfo=UTC), 5)]
    assert changes_only(only, lambda r: r.captured_at, lambda r: r.value) == only


def test_changes_only_sorts_chronologically_before_deduping() -> None:
    @dataclass
    class Reading:
        captured_at: datetime
        value: int

    out_of_order = [
        Reading(datetime(2026, 8, 5, tzinfo=UTC), 7),
        Reading(datetime(2026, 8, 1, tzinfo=UTC), 5),
    ]
    kept = changes_only(out_of_order, lambda r: r.captured_at, lambda r: r.value)
    assert [r.value for r in kept] == [5, 7]


def test_iso_week_key_and_latest_per_iso_week_are_unaffected() -> None:
    """Regresión: el nuevo código no debe tocar el comportamiento ya
    existente de cierre semanal por ISO week."""
    a = datetime(2026, 8, 3, tzinfo=UTC)
    b = datetime(2026, 8, 5, tzinfo=UTC)
    assert iso_week_key(a) == iso_week_key(b)
    assert latest_per_iso_week([a, b], lambda d: d) == [b]
    assert start_of_iso_week(b).weekday() == 0
