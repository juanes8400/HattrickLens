"""Liga NO se cae cuando el equipo acaba de cambiar de serie.

2026-11-01, dicho por el usuario: «Cambié de Liga, aún tengo una especie de
ancla a la anterior, y hoy le doy en Liga y me sale 500».

El escenario que esto monta es el de la temporada nueva recién empezada: la
clasificación de la serie VIEJA sigue en la base --es historia, no basura--,
la de la serie NUEVA está capturada en la jornada 0, con los ocho equipos a
cero, y todavía no se ha jugado ni un partido de la serie nueva.
"""
import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.api.v1.endpoints.league import (
    _alineacion_enviada_propia,
    _lecturas_de_la_serie,
)
from app.application.queries.league import LeagueQueryService
from app.infrastructure.security.tokens import encrypt_token
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

VIEJA, NUEVA = 7777, 8888
ANTES = datetime(2026, 9, 1, tzinfo=UTC)
AHORA = datetime(2026, 11, 1, tzinfo=UTC)
RIVALES_VIEJOS = [(600001, "Deportivo Uno"), (600002, "Atlético Dos"), (600003, "Club Tres")]
RIVALES_NUEVOS = [(700001, "Nuevo Uno"), (700002, "Nuevo Dos"), (700003, "Nuevo Tres")]


async def _tras_el_ascenso():
    factory, team_id = await seeded_session()
    async with factory() as s:
        team = await s.get(m.Team, team_id)
        assert team is not None
        team.series_ht_id = NUEVA
        sync = m.Sync(user_id=1, team_id=team_id, kind="manual", status="completed", started_at=AHORA)
        s.add(sync)
        await s.flush()

        # La serie vieja, terminada: catorce jornadas y campeón.
        for i, (ht_id, nombre) in enumerate([(HT_TEAM_ID, "Pulgas Arrechas"), *RIVALES_VIEJOS]):
            s.add(
                m.Standing(
                    sync_id=sync.id, series_ht_id=VIEJA, season=83, match_round=14,
                    captured_at=ANTES, team_ht_id=ht_id, team_name=nombre, position=i + 1,
                    played=14, won=10 - i * 3, draws=2, lost=2 + i * 3,
                    goals_for=30 - i * 5, goals_against=10 + i * 5, points=32 - i * 9,
                )
            )
        for i in range(4):
            s.add(
                m.Match(
                    ht_match_id=800_000 + i, played_at=ANTES + timedelta(days=7 * i),
                    match_type=1, status="finished", series_ht_id=VIEJA,
                    home_team_ht_id=HT_TEAM_ID, away_team_ht_id=600001 + (i % 3),
                    home_team_name="Pulgas Arrechas", away_team_name="Deportivo Uno",
                    home_goals=2, away_goals=1, match_round=i + 1,
                )
            )

        # La serie nueva, sin empezar: jornada 0 y todos a cero.
        for i, (ht_id, nombre) in enumerate([(HT_TEAM_ID, "Pulgas Arrechas"), *RIVALES_NUEVOS]):
            s.add(
                m.Standing(
                    sync_id=sync.id, series_ht_id=NUEVA, season=84, match_round=0,
                    captured_at=AHORA, team_ht_id=ht_id, team_name=nombre, position=i + 1,
                    played=0, won=0, draws=0, lost=0, goals_for=0, goals_against=0, points=0,
                )
            )
        await s.commit()
    return factory, team_id


def test_liga_se_enseña_sin_haber_jugado_en_la_serie_nueva() -> None:
    async def go():
        factory, team_id = await _tras_el_ascenso()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id)

    resp = asyncio.run(go())
    assert resp is not None
    # Y es la serie NUEVA la que se enseña, no el ancla a la vieja.
    assert len(resp.standings) == 4
    assert {r.name for r in resp.standings} >= {"Nuevo Uno", "Nuevo Dos", "Nuevo Tres"}


async def _con_sesion_y_partido_pendiente():
    """El mismo escenario, con token activo y un partido de la serie nueva."""
    factory, team_id = await _tras_el_ascenso()
    async with factory() as s:
        team = await s.get(m.Team, team_id)
        assert team is not None
        usuario = m.User(email="dueño@ejemplo.com", ht_user_id=999)
        s.add(usuario)
        await s.flush()
        team.owner_user_id = usuario.id
        s.add(
            m.CHPPToken(
                user_id=usuario.id,
                oauth_token_enc=encrypt_token("tok"),
                oauth_secret_enc=encrypt_token("sec"),
                status="active",
                ht_user_id=999,
            )
        )
        s.add(
            m.Match(
                ht_match_id=772_208_117,
                played_at=AHORA + timedelta(days=2),
                match_type=1,
                status="UPCOMING",
                series_ht_id=NUEVA,
                match_round=1,
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=700_001,
                home_team_name="Pulgas Arrechas",
                away_team_name="Nuevo Uno",
                home_goals=-1,
                away_goals=-1,
            )
        )
        await s.commit()
    return factory, team_id


def test_si_matchorders_falla_liga_sigue_en_pie() -> None:
    """Las órdenes enviadas son un extra del Resumen, no la pantalla.

    Hasta el 2026-11-01 esto era un `try/finally` sin `except`, así que un
    `matchorders` que no contestara --el caso típico de un partido de una
    serie recién estrenada-- salía como 500 y Liga entera se quedaba en «No
    pudimos cargar estos datos» con la clasificación ya calculada al lado.
    """

    async def go():
        factory, team_id = await _con_sesion_y_partido_pendiente()
        async with factory() as s:
            with patch(
                "app.api.v1.endpoints.league.alineacion_enviada_de",
                side_effect=RuntimeError("Hattrick todavía no acepta órdenes de este partido"),
            ):
                return await _alineacion_enviada_propia(s, team_id)

    assert asyncio.run(go()) is None


def test_si_las_lecturas_de_la_serie_fallan_liga_sigue_en_pie() -> None:
    """Y lo mismo con los ratings en vivo: sin ellos queda la Poisson."""

    async def go():
        factory, team_id = await _con_sesion_y_partido_pendiente()
        async with factory() as s:
            # Un partido jugado en la serie nueva, que es lo que dispara las
            # llamadas en vivo.
            s.add(
                m.Match(
                    ht_match_id=772_208_118,
                    played_at=AHORA - timedelta(days=1),
                    match_type=1,
                    status="finished",
                    series_ht_id=NUEVA,
                    match_round=1,
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=700_002,
                    home_team_name="Pulgas Arrechas",
                    away_team_name="Nuevo Dos",
                    home_goals=1,
                    away_goals=1,
                )
            )
            await s.commit()
            with patch(
                "app.api.v1.endpoints.league.lecturas_de_la_serie",
                side_effect=ValueError("una respuesta que el parser no entiende"),
            ):
                return await _lecturas_de_la_serie(s, team_id)

    assert asyncio.run(go()) == {}


def test_la_serie_con_historia_ajena_no_tumba_liga() -> None:
    """El 500 de verdad: la jornada pasada de una serie en la que no estabas.

    2026-11-02, leído en el registro de producción --`RuntimeError: coroutine
    raised StopIteration`, cuarenta y dos veces en una hora, en
    `queries/league.py` dentro de `liga_calculada`--. La serie nueva trae sus
    partidos del año pasado, jugados entre los ocho equipos que estaban, y
    ninguno es tuyo. Así que apareces en la clasificación de HOY y no en la de
    la jornada anterior, que se arma con esos partidos; `next()` sin salida se
    iba a `StopIteration` y Liga y las alertas contestaban 500 enteras.
    """

    async def go():
        factory, team_id = await _tras_el_ascenso()
        async with factory() as s:
            # Doce jornadas de la serie nueva, del año pasado, entre los otros.
            for i in range(12):
                local, visita = RIVALES_NUEVOS[i % 3], RIVALES_NUEVOS[(i + 1) % 3]
                s.add(
                    m.Match(
                        ht_match_id=900_000 + i,
                        played_at=ANTES + timedelta(days=7 * i),
                        match_type=1,
                        status="finished",
                        series_ht_id=NUEVA,
                        match_round=i + 1,
                        home_team_ht_id=local[0],
                        away_team_ht_id=visita[0],
                        home_team_name=local[1],
                        away_team_name=visita[1],
                        home_goals=2,
                        away_goals=1,
                    )
                )
            await s.commit()
            return await LeagueQueryService(s).get(team_id)

    resp = asyncio.run(go())
    assert resp is not None
    # La pantalla entera sigue en pie; lo único que falta es el recuadro de
    # «cuánto movió la última jornada», que sin haber jugado no existe.
    assert resp.change is None
    assert len(resp.standings) == 4
