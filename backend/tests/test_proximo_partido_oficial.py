"""El próximo partido OFICIAL para el Dashboard (2026-11-18): no el de liga."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.proximo_partido_oficial import proximo_partido_oficial
from app.domain.value_objects.ht_constants import (
    MATCH_TYPE_CUP,
    MATCH_TYPE_FRIENDLY,
    MATCH_TYPE_LEAGUE,
)
from app.infrastructure.db import models as m

AHORA = datetime(2026, 11, 18, 12, tzinfo=UTC)
NOSOTROS = 537758


def _partido(mid: int, tipo: int, horas: float, *, en_casa: bool = True) -> m.Match:
    return m.Match(
        ht_match_id=mid,
        played_at=AHORA + timedelta(hours=horas),
        match_type=tipo,
        status="UPCOMING" if horas > 0 else "FINISHED",
        home_team_ht_id=NOSOTROS if en_casa else 999,
        away_team_ht_id=999 if en_casa else NOSOTROS,
        home_team_name="Pulgas" if en_casa else "Rival",
        away_team_name="Rival" if en_casa else "Pulgas",
        orders_given=True,
    )


def _con(partidos: list[m.Match]) -> object:
    async def correr() -> object:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as s:
            team = m.Team(ht_team_id=NOSOTROS, name="Pulgas")
            s.add(team)
            s.add_all(partidos)
            await s.commit()
            team_id = team.id
        async with AsyncSession(engine) as s:
            resultado = await proximo_partido_oficial(s, team_id, AHORA)
        await engine.dispose()
        return resultado

    return asyncio.run(correr())


def test_el_de_copa_de_hoy_va_antes_que_el_de_liga_del_domingo() -> None:
    p = _con(
        [
            _partido(1, MATCH_TYPE_LEAGUE, 24 * 4),
            _partido(2, MATCH_TYPE_CUP, 10, en_casa=False),
        ]
    )
    assert p is not None
    assert p.ht_match_id == 2  # type: ignore[attr-defined]
    assert p.is_home is False  # type: ignore[attr-defined]
    assert p.rival_ht_id == 999  # type: ignore[attr-defined]


def test_un_amistoso_no_cuenta_ni_un_partido_ya_jugado() -> None:
    p = _con(
        [
            _partido(1, MATCH_TYPE_CUP, -5),
            _partido(2, MATCH_TYPE_FRIENDLY, 3),
            _partido(3, MATCH_TYPE_LEAGUE, 48),
        ]
    )
    assert p is not None and p.ht_match_id == 3  # type: ignore[attr-defined]


def test_sin_oficiales_pendientes_no_hay_nada() -> None:
    assert _con([_partido(1, MATCH_TYPE_FRIENDLY, 3)]) is None
