"""Regla temporal única para lecturas derivadas de snapshots.

Los snapshots crudos se conservan completos para auditoría. Las gráficas y los
diffs sólo pueden mostrar una lectura por semana ISO: la última que Lens vio
esa semana. Así varios syncs no fabrican una tendencia diaria.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from app.domain.engines.economy_engine import SEASON_WEEKS

# `models` se importa de VERDAD, no solo para el analizador: hay anotaciones que
# lo nombran y con `TYPE_CHECKING` no resuelven al evaluarlas en ejecucion.
from app.infrastructure.db import models as m

# `TypeVar` y no la sintaxis `def f[T]()` de Python 3.12: esa forma no resuelve
# con `get_type_hints` en 3.12, que es la version con la que se despliega. Aqui
# se corre 3.14 y por eso el fallo solo aparecia en CI.
T = TypeVar("T")


def iso_week_key(value: datetime) -> tuple[int, int]:
    iso = value.isocalendar()
    return iso.year, iso.week


def latest_per_iso_week[T](items: Iterable[T], captured_at: Callable[[T], datetime]) -> list[T]:
    """Last observed item from each ISO week, ordered chronologically."""
    latest: dict[tuple[int, int], T] = {}
    for item in sorted(items, key=captured_at):
        latest[iso_week_key(captured_at(item))] = item
    return list(latest.values())


def changes_only(  # noqa: UP047
    items: Iterable[T],
    captured_at: Callable[[T], datetime],
    value: Callable[[T], Any],
) -> list[T]:
    """Un punto por cambio REAL de valor, no uno por semana ISO ni uno por
    sync — 2026-08-12, pedido explícito para Espíritu/Confianza y Socios en
    Club: si dos syncs seguidos leen el mismo número, el segundo no es un
    "snapshot nuevo", es la misma foto otra vez. Se queda siempre el primer
    dato visto y, después, sólo los que de verdad cambiaron — a diferencia de
    `latest_per_iso_week`, que colapsa por semana sin mirar si el valor
    cambió y puede meter puntos idénticos seguidos si el valor real tardó
    varias semanas en moverse."""
    ordered = sorted(items, key=captured_at)
    kept: list[T] = []
    last_value: Any = object()  # centinela: nunca igual a un valor real
    for item in ordered:
        v = value(item)
        if v != last_value:
            kept.append(item)
            last_value = v
    return kept


def start_of_iso_week(value: datetime) -> datetime:
    """Monday 00:00 in the timestamp's timezone, for prior-week queries."""
    return value - timedelta(
        days=value.weekday(),
        hours=value.hour,
        minutes=value.minute,
        seconds=value.second,
        microseconds=value.microsecond,
    )


# ── Etiqueta temporada-semana ("TT-ss") ──────────────────────────────────
#
# 2026-08-09, confirmado por el usuario: `MatchRound` de worlddetails.xml
# v2.0 ES la semana real de temporada (1-16, el mismo ciclo semanal de
# economía/entrenamiento) — no la jornada de liga (eso es un concepto
# distinto, de leaguedetails.xml/Standing, con su propio -1 de ajuste). Se
# fija esa versión explícita en sync_team.py para no depender de que un
# cambio de versión por defecto de CHPP altere el significado en silencio.
#
# CHPP no expone un campo aparte de "semana de temporada" fuera de
# MatchRound, así que WorldContext (con su season/match_round YA fijos al
# instante `refreshed_at`) es la única ancla real disponible — sin ella no
# hay forma honesta de etiquetar una fecha con su temporada-semana; se
# devuelve `None` antes que inventar un ancla.
def _week_index(world: m.WorldContext) -> int:
    """Índice absoluto de semana: temporada × 16 + (semana − 1), 0-index."""
    return world.season * SEASON_WEEKS + (world.match_round - 1)


def season_week_offset_for(world: m.WorldContext | None, when: datetime) -> int:
    """Semanas ISO transcurridas entre `when` y AHORA (`world.refreshed_at`)
    — negativo si `when` es pasado, listo para `season_week_label`.

    2026-08-09, bug real encontrado en vivo: la primera versión contaba
    `(refreshed_at - when).days // 7` a partir de AHORA sin más — dos
    lecturas de dos semanas ISO DISTINTAS pero separadas por menos de 7 días
    de esa cuenta (p. ej. una capturada un domingo, la otra el domingo
    siguiente) caían en el mismo cociente entero y salían con la MISMA
    etiqueta "TT-ss", pese a que el propio gráfico ya las trata como semanas
    distintas (`latest_per_iso_week`). Ancla ambos extremos al lunes de su
    semana ISO (`start_of_iso_week`, la MISMA frontera que usa el resto de
    este módulo) antes de restar: la diferencia entre dos lunes es siempre
    un múltiplo exacto de 7 días, así que dos semanas ISO distintas NUNCA
    pueden dar el mismo cociente — coincide uno a uno con los cubos que ya
    arma `latest_per_iso_week`, sin ambigüedad de redondeo.

    SQLite/aiosqlite puede devolver un datetime sin tzinfo aunque se haya
    guardado en UTC (mismo gotcha ya documentado en squad.py/analysis.py) —
    sin este resguardo, restar un naive contra un aware lanza `TypeError`."""
    if world is None or world.refreshed_at is None:
        return 0
    refreshed_at = (
        world.refreshed_at if world.refreshed_at.tzinfo else world.refreshed_at.replace(tzinfo=UTC)
    )
    when_aware = when if when.tzinfo else when.replace(tzinfo=UTC)
    elapsed_days = (start_of_iso_week(refreshed_at) - start_of_iso_week(when_aware)).days
    return -(elapsed_days // 7)


def season_week_label(world: m.WorldContext | None, *, weeks_offset: int = 0) -> str | None:
    """ "TT-ss" (temporada-semana, p. ej. "83-03") para el `WorldContext`
    dado, desplazado `weeks_offset` semanas respecto a AHORA (negativo =
    pasado, positivo = futuro — para semanas de una proyección). `None` si
    no hay `WorldContext` propio sincronizado todavía."""
    if world is None or world.season is None or world.match_round is None:
        return None
    idx = _week_index(world) + weeks_offset
    season, week = divmod(idx, SEASON_WEEKS)
    return f"{season:02d}-{week + 1:02d}"


def season_at_offset(world: m.WorldContext | None, *, weeks_offset: int = 0) -> int | None:
    """Solo el número de temporada (sin la semana) en `weeks_offset` — para
    agrupar filas de una tabla por temporada (ver Detalles, 2026-08-09,
    pedido explícito: totales acumulados "83"/"82" al estilo Hattrick
    Control). Misma ancla y mismas reglas que `season_week_label`."""
    if world is None or world.season is None or world.match_round is None:
        return None
    idx = _week_index(world) + weeks_offset
    season, _week = divmod(idx, SEASON_WEEKS)
    return season


def season_week_for_datetime(
    world: m.WorldContext | None,
    when: datetime,
) -> str | None:
    """Temporada-semana exacta de una fecha pasada, presente o futura.

    Esta es la entrada canónica para fechas reales. Mantiene juntas las dos
    partes que no deben volver a implementarse por separado: convertir la
    fecha a un desplazamiento de semanas ISO y aplicar ese desplazamiento al
    ancla ``Season``/``MatchRound`` entregada por ``worlddetails.xml``.
    """
    return season_week_label(
        world,
        weeks_offset=season_week_offset_for(world, when),
    )


def season_for_datetime(
    world: m.WorldContext | None,
    when: datetime,
) -> int | None:
    """Número de temporada exacto para una fecha pasada, presente o futura."""
    return season_at_offset(
        world,
        weeks_offset=season_week_offset_for(world, when),
    )


def backfill_leading_gaps(values: list[float | None]) -> list[float | None]:
    """Rellena SOLO el hueco inicial de una serie con su primer valor conocido.

    2026-08-16, pedido explícito y con la advertencia de que **es un cambio
    puramente estético**: los primeros snapshots de esta cuenta se guardaron
    antes de que existieran algunas columnas (fidelidad, rasgos), así que su
    serie arranca con un tramo vacío que en la gráfica se ve como un salto
    feo desde la nada.

    Por eso esta función vive en la capa de presentación y NO debe usarse para
    calcular nada: el valor que estira hacia atrás no es una medición, es la
    primera lectura repetida. Los huecos INTERIORES se respetan tal cual —
    esos sí significan "esa semana no se leyó" y taparlos escondería una
    laguna real en medio de la serie.
    """
    first = next((i for i, value in enumerate(values) if value is not None), None)
    if first is None or first == 0:
        return values
    return [values[first]] * first + values[first:]
