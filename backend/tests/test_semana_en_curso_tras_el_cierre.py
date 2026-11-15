"""La semana en curso es la SIGUIENTE a la última cerrada.

2026-11-14, reportado por el usuario con una captura de Economía › Detalles:
«Dice 84-01 dos veces». Hattrick cerró la semana económica el sábado; la fila
cerrada se etiqueta con la semana en que cerró (84-01) y la fila «en curso»
tomaba la semana de la lectura, que hasta el lunes es la misma. La que corre
cierra el sábado siguiente: es la 84-02.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.economy import EconomyQueryService
from app.infrastructure.db import models as m
from tests.test_economy_query import _economy_row

# Miércoles 4 (83-16), jueves 12 (84-01, antes del cierre) y sábado 14 de
# noviembre (84-01, después del cierre). Cada lectura trae una semana cerrada
# distinta en sus `last_*`, salvo que se diga otra cosa.
MIERCOLES_83_16 = datetime(2026, 11, 4, 12, tzinfo=UTC)
JUEVES_84_01 = datetime(2026, 11, 12, 12, tzinfo=UTC)
SABADO_84_01 = datetime(2026, 11, 14, 22, tzinfo=UTC)


async def _economia(lecturas: list[tuple[datetime, int]]):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        team = m.Team(
            ht_team_id=1,
            name="Test FC",
            currency_rate=1.0,
            currency_name="US$",
            ht_league_id=19,
        )
        s.add(team)
        s.add(
            m.WorldContext(
                ht_league_id=19,
                country_name="Colombia",
                league_name="Colombia",
                season=84,
                season_offset=0,
                match_round=1,
                match_rounds_left=15,
                currency_name="US$",
                currency_rate=1.0,
                refreshed_at=lecturas[-1][0],
            )
        )
        await s.flush()
        s.add_all(
            _economy_row(i + 1, team.id, cuando, last_spectators=taquilla)
            for i, (cuando, taquilla) in enumerate(lecturas)
        )
        await s.commit()
        return await EconomyQueryService(s).get(team.id)


def test_tras_el_cierre_del_sabado_la_semana_en_curso_es_la_siguiente() -> None:
    d = asyncio.run(
        _economia([(MIERCOLES_83_16, 100), (JUEVES_84_01, 200), (SABADO_84_01, 300)])
    )
    assert d is not None
    etiquetas = [fila.season_week for fila in d.weekly_breakdown]
    assert etiquetas == ["84-02", "84-01", "83-16", "83-15"]
    assert d.weekly_breakdown[0].is_current is True
    # El punto de hoy en la gráfica y la proyección van detrás, sin repetir.
    assert d.current_week is not None
    assert d.current_week.season_week == "84-02"
    assert d.series[-1].season_week == "84-01"
    assert d.structural_forecast.week_labels[0] == "84-03"
    # Y la semana en curso suma en su temporada.
    assert [t.season for t in d.season_breakdown_totals] == [84, 83]


def test_antes_del_cierre_la_semana_en_curso_es_la_de_hoy() -> None:
    """El jueves todavía no cerró nada: la en curso es la de la lectura."""
    d = asyncio.run(_economia([(MIERCOLES_83_16, 100), (JUEVES_84_01, 200)]))
    assert d is not None
    etiquetas = [fila.season_week for fila in d.weekly_breakdown]
    assert etiquetas == ["84-01", "83-16", "83-15"]
    assert d.structural_forecast.week_labels[0] == "84-02"


def test_varias_lecturas_de_la_misma_semana_no_adelantan_nada() -> None:
    """Dos lecturas tras el cierre son la misma semana cerrada: no hay otra."""
    d = asyncio.run(
        _economia(
            [
                (MIERCOLES_83_16, 100),
                (JUEVES_84_01, 200),
                (SABADO_84_01, 300),
                (datetime(2026, 11, 15, 9, tzinfo=UTC), 300),
            ]
        )
    )
    assert d is not None
    etiquetas = [fila.season_week for fila in d.weekly_breakdown]
    assert etiquetas == ["84-02", "84-01", "83-16", "83-15"]
