"""El once del ultimo partido sale del PARTIDO, no de la ficha de cada jugador.

2026-09-27, caso concreto del usuario: el partido 770393948 del FC Villainy
salia en Equipo con ocho jugadores y una formacion «3-5-0», que no existe.

La alineacion enviada (`submitted_lineup_json`) solo se captura mientras el
partido sigue PROXIMO y con ordenes dadas. Si nadie sincronizo en esa ventana
--lo normal en un segundo equipo-- ese partido se queda sin ella para siempre,
y el once salia de `player_snapshots.last_match_*`, que guarda el ULTIMO
partido de cada jugador y se pisa en cada sync. Basta un amistoso despues para
que media plantilla deje de apuntar al partido de liga.

`player_match_ratings` es la misma informacion guardada append-only, una fila
por (jugador, partido): lo capturado una vez ya no se pisa.
"""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import delete, select

from app.application.queries.habilidades import HabilidadesQueryService
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

LIGA = 1_000_001
AMISTOSO = 1_000_002
JUGADO = datetime(2026, 3, 1, 21, 40, tzinfo=UTC)

#: Un 5-4-1: portero, dos laterales, tres centrales, dos extremos, dos
#: mediocentros y un delantero.
PUESTOS = (100, 101, 105, 102, 103, 104, 106, 110, 107, 108, 111)


async def _escenario():
    """La liga jugada, sus fichas guardadas, y un amistoso despues encima."""
    factory, team_id = await seeded_session()
    async with factory() as s:
        s.add(
            m.Match(
                ht_match_id=LIGA,
                played_at=JUGADO,
                match_type=1,
                status="FINISHED",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=600001,
                home_team_name="Pulgas Arrechas",
                away_team_name="Deportivo Uno",
                home_goals=2,
                away_goals=1,
                match_round=5,
            )
        )
        s.add(
            m.Match(
                ht_match_id=AMISTOSO,
                played_at=datetime(2026, 3, 4, 21, 40, tzinfo=UTC),
                match_type=4,
                status="FINISHED",
                home_team_ht_id=HT_TEAM_ID,
                away_team_ht_id=600002,
                home_team_name="Pulgas Arrechas",
                away_team_name="Atletico Dos",
                home_goals=0,
                away_goals=0,
            )
        )
        jugadores = (await s.execute(select(m.Player).order_by(m.Player.id))).scalars().all()
        once = jugadores[: len(PUESTOS)]
        for jugador, puesto in zip(once, PUESTOS, strict=True):
            s.add(
                m.PlayerMatchRating(
                    player_id=jugador.id,
                    ht_match_id=LIGA,
                    position_code=puesto,
                    played_minutes=90,
                    rating=5.0,
                    captured_at=JUGADO,
                )
            )
        # Las fichas: solo tres siguen apuntando a la liga. Los otros ocho
        # jugaron el amistoso del sabado y sus `last_match_*` hablan de ese.
        for i, jugador in enumerate(once):
            foto = await s.scalar(
                select(m.PlayerSnapshot).where(m.PlayerSnapshot.player_id == jugador.id)
            )
            de_la_liga = i < 3
            foto.last_match_ht_id = LIGA if de_la_liga else AMISTOSO
            foto.last_match_position_code = PUESTOS[i] if de_la_liga else 114
            foto.last_match_played_minutes = 90
        await s.commit()
    return factory, team_id


async def _once_de(factory, team_id):
    async with factory() as s:
        return await HabilidadesQueryService(s).get(team_id)


def test_el_once_sobrevive_a_un_amistoso_posterior() -> None:
    async def caso():
        factory, team_id = await _escenario()
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.lineup_players == 11
    assert r.formation == "5-4-1"
    assert r.lineup_source == "partido"


def test_sin_las_fichas_del_partido_el_once_queda_corto_y_no_se_inventa_formacion() -> None:
    """El estado ANTERIOR al arreglo, para que se vea que no se tapa solo.

    Sin `player_match_ratings` no hay de donde sacar a los ocho que jugaron el
    amistoso, y el once se queda en tres. Lo que ya no pasa es que esos tres se
    presenten como una formacion.
    """

    async def caso():
        factory, team_id = await _escenario()
        async with factory() as s:
            await s.execute(delete(m.PlayerMatchRating).where(m.PlayerMatchRating.ht_match_id == LIGA))
            await s.commit()
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.lineup_players == 3
    assert r.formation is None
    assert r.lineup_source == "fichas"


def test_el_once_dice_de_que_partido_salio() -> None:
    """2026-09-27, pedido del usuario: la fecha sola no identifica el partido."""

    async def caso():
        factory, team_id = await _escenario()
        return await _once_de(factory, team_id)

    r = asyncio.run(caso())
    assert r.last_match_date == "2026-03-01"
    assert r.last_match_opponent == "Deportivo Uno"
    assert r.last_match_score == "2-1"
    assert r.last_match_is_home is True
    assert r.last_match_competition
