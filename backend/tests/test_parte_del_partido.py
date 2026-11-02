"""El parte del partido en Cambios, y qué partido es «el último».

2026-11-01, dicho por un usuario: «el partido que aparece "Los Parquesitos"
no es de Liga, no debería aparecer». Era un torneo no oficial, jugado entre
semana, que tapaba el parte del último partido de verdad.
"""
import asyncio
from datetime import UTC, datetime, timedelta

from app.application.queries.parte_del_partido import build_parte_del_partido
from app.domain.value_objects.ht_constants import (
    MATCH_TYPE_FRIENDLY,
    MATCH_TYPE_LEAGUE,
    MATCH_TYPE_QUALIFICATION,
    MATCH_TYPE_TOURNAMENT_LEAGUE,
)
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

DOMINGO = datetime(2026, 10, 25, 21, 40, tzinfo=UTC)


async def _con_partidos(*tipos_y_dias: tuple[int, int, str]):
    """Siembra un partido jugado por cada `(match_type, días, rival)`."""
    factory, team_id = await seeded_session()
    async with factory() as s:
        for i, (tipo, dias, rival) in enumerate(tipos_y_dias):
            s.add(
                m.Match(
                    ht_match_id=772_000_000 + i,
                    played_at=DOMINGO + timedelta(days=dias),
                    match_type=tipo,
                    status="finished",
                    home_team_ht_id=HT_TEAM_ID,
                    away_team_ht_id=600_000 + i,
                    home_team_name="Pulgas Arrechas",
                    away_team_name=rival,
                    home_goals=2,
                    away_goals=1,
                )
            )
        await s.commit()
    return factory, team_id


def _parte(*tipos_y_dias: tuple[int, int, str]):
    async def go():
        factory, team_id = await _con_partidos(*tipos_y_dias)
        async with factory() as s:
            return await build_parte_del_partido(s, team_id)

    return asyncio.run(go())


def test_un_torneo_no_oficial_no_tapa_el_parte_del_partido() -> None:
    parte = _parte(
        (MATCH_TYPE_LEAGUE, 0, "Cauca CF"),
        (MATCH_TYPE_TOURNAMENT_LEAGUE, 3, "Los Parquesitos"),
    )
    assert parte is not None
    assert parte["away"] == "Cauca CF"
    assert parte["competition"] == "Liga"


def test_un_amistoso_sí_es_el_último_partido() -> None:
    """Los amistosos son partidos reales: no se calculan pronósticos para
    ellos, pero el parte los enseña --sin terna-- en vez de saltárselos."""
    parte = _parte(
        (MATCH_TYPE_LEAGUE, 0, "Cauca CF"),
        (MATCH_TYPE_FRIENDLY, 3, "Forever20"),
    )
    assert parte is not None
    assert parte["away"] == "Forever20"
    assert parte["prediction"] is None


def test_sin_partidos_oficiales_no_hay_parte_en_vez_de_un_torneo() -> None:
    assert _parte((MATCH_TYPE_TOURNAMENT_LEAGUE, 0, "Los Parquesitos")) is None


def test_la_promocion_se_compara_con_lo_que_dijimos() -> None:
    """2026-11-01, pedido del usuario: «quiero que los partidos de Promoción
    también tengan comparación entre predicción y resultado».

    El pronóstico lo guarda la ficha de rival --Liga no puede, el rival no
    está en tu serie-- y aquí se lee igual que el de un partido de liga.
    """

    async def go():
        factory, team_id = await _con_partidos((MATCH_TYPE_QUALIFICATION, 0, "Los de Arriba"))
        async with factory() as s:
            s.add(
                m.MatchPrediction(
                    ht_match_id=772_000_000,
                    team_id=team_id,
                    home_win=0.48,
                    draw=0.27,
                    away_win=0.25,
                    expected_home_goals=1.6,
                    expected_away_goals=1.2,
                    most_likely_score="2-1",
                    source="zonas",
                    engine="v1",
                    computed_at=DOMINGO,
                )
            )
            await s.commit()
            return await build_parte_del_partido(s, team_id)

    parte = asyncio.run(go())
    assert parte is not None
    assert parte["competition"] == "Promoción"
    assert parte["prediction"] is not None
    assert parte["prediction"]["homeWin"] == 0.48
    # Y el marcador cantado al lado del que cayó, que es de lo que va la pantalla.
    assert parte["prediction"]["mostLikelyScore"] == "2-1"
    assert (parte["homeGoals"], parte["awayGoals"]) == (2, 1)
