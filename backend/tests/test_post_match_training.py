import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from app.application.queries.post_match_training import (
    PlayedSegment,
    PostMatchTrainingService,
    _repartidos_por_puesto,
    position_name,
)
from app.domain.engines.training_engine import training_exposure
from app.domain.value_objects.ht_constants import training_name
from app.infrastructure.db import models as m

from .conftest import seeded_session


@pytest.mark.parametrize("position_code", [102, 105, 109, 110])
def test_long_passing_trains_all_defenders_and_midfielders(position_code: int) -> None:
    """Centrales, laterales, medios interiores y extremos reciben el tipo 10."""
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    assert service._position_share(10, position_code) == "full"


def test_long_passing_does_not_train_forwards() -> None:
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    assert service._position_share(10, 113) == "none"


@pytest.mark.asyncio
async def test_post_match_training_counts_real_forward_minutes() -> None:
    factory, team_id = await seeded_session()
    now = datetime.now(UTC)

    async with factory() as s:
        player = (
            await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .limit(1)
            )
        ).scalar_one()
        team = await s.get(m.Team, team_id)
        assert team is not None

        world = (await s.execute(select(m.WorldContext).limit(1))).scalar_one()
        world.training_date = now + timedelta(days=1)
        world.refreshed_at = now

        s.add(
            m.Match(
                ht_match_id=900001,
                played_at=now,
                match_type=1,
                status="Finished",
                home_team_ht_id=team.ht_team_id,
                away_team_ht_id=123,
                home_team_name=team.name,
                away_team_name="Rival",
                home_goals=2,
                away_goals=0,
            )
        )
        s.add(
            m.PlayerMatchRating(
                player_id=player.id,
                ht_match_id=900001,
                position_code=13,
                played_minutes=90,
                rating=7.0,
                captured_at=now,
            )
        )
        await s.commit()

    result = await PostMatchTrainingService(s).get(team_id)

    assert result is not None
    assert result["recommendation"]["recommendable"] is True
    assert result["recommendation"]["trainingType"] != 1
    scoring = next(o for o in result["options"] if o["trainingType"] == 4)
    keeper = next(o for o in result["options"] if o["trainingType"] == 9)
    # Los que Hattrick ya retiró no salen, ni como referencia (2026-11-23).
    assert not any(o["trainingType"] in (0, 1) for o in result["options"])
    assert scoring["equivalentMinutes"] == 90
    assert keeper["equivalentMinutes"] == 0

    # 2026-09-13: se ordena por el aporte posicional ganado, no por subidas.
    # Un delantero que juega 90 minutos gana aporte entrenando Anotación, y
    # nada entrenando Balón parado, que sube rápido pero no mejora ningún puesto.
    set_pieces = next(o for o in result["options"] if o["trainingType"] == 2)
    assert scoring["value"] > set_pieces["value"]
    values = [o["value"] for o in result["options"] if o["recommendable"]]
    assert values == sorted(values, reverse=True)
    assert result["recommendation"]["trainingType"] != 2

    row = next(p for p in result["players"] if p["htPlayerId"] == player.ht_player_id)
    assert row["exposureByTrainingType"]["4"] == 1.0
    assert "9" not in row["exposureByTrainingType"]
    assert row["segments"][0]["position"] == "Delantero medio"


#: La tabla ENTERA, dictada por el usuario el 2026-10-09 leyéndola del juego,
#: entrenamiento por entrenamiento. Filas: el tipo de CHPP. Columnas: el
#: porcentaje que recibe un jugador por cada minuto en ese puesto.
#:
#: Se escribe aquí y no se deriva de `TRAINING_POSITION_SHARES`: una prueba que
#: lee la misma tabla que prueba no comprueba nada. Esta es la fuente, y el
#: código tiene que coincidir con ella.
TABLA_DICTADA: dict[int, dict[int, int]] = {
    # portero, central, lateral, medio interior, extremo, delantero
    2: {100: 100, 103: 100, 101: 100, 108: 100, 106: 100, 112: 100},
    3: {100: 0, 103: 100, 101: 100, 108: 0, 106: 0, 112: 0},
    4: {100: 0, 103: 0, 101: 0, 108: 0, 106: 0, 112: 100},
    5: {100: 0, 103: 0, 101: 50, 108: 0, 106: 100, 112: 0},
    6: {100: 100, 103: 100, 101: 100, 108: 100, 106: 100, 112: 100},
    7: {100: 0, 103: 0, 101: 0, 108: 100, 106: 100, 112: 100},
    8: {100: 0, 103: 0, 101: 0, 108: 100, 106: 50, 112: 0},
    9: {100: 100, 103: 0, 101: 0, 108: 0, 106: 0, 112: 0},
    10: {100: 0, 103: 100, 101: 100, 108: 100, 106: 100, 112: 0},
    11: {100: 100, 103: 100, 101: 100, 108: 100, 106: 100, 112: 0},
    12: {100: 0, 103: 0, 101: 0, 108: 0, 106: 100, 112: 100},
}


@pytest.mark.parametrize("training_type", sorted(TABLA_DICTADA))
def test_cada_puesto_recibe_lo_que_dicta_la_tabla_oficial(training_type: int) -> None:
    """El reparto por puestos, contra la tabla que dio el usuario.

    2026-10-09. Un usuario reportó que un jugador suyo con 87′ de lateral y 3′
    de extremo recibía la semana entera de «Lateral». Al revisar el reparto
    para contestarle salieron tres casillas mal, que esta tabla fija:

    · «Defensa» no entrenaba al LATERAL. Noventa minutos y 0 %.
    · «Defensa (porteros, defensas y centro del campo completo)» no entrenaba
      al PORTERO, al que su propio nombre nombra.
    · «Anotación y balón parado» daba 50 % a todo el que no fuera delantero,
      duplicando la lentitud que ya cobra el coeficiente del entrenamiento.

    Falta una, a propósito: en «Balón parado» el portero y el cobrador de
    tiros libres reciben el 125 %, y el motor todavía no sabe expresar un peso
    por encima del completo. Aquí van al 100 %, que es lo que hace hoy, y el
    día que se represente esta tabla tiene que cambiar con el código.
    """
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    for position_code, esperado in TABLA_DICTADA[training_type].items():
        share = service._position_share(training_type, position_code)
        recibido = round(training_exposure(90, share) * 100)
        assert recibido == esperado, (
            f"entrenamiento {training_name(training_type)}, "
            f"{position_name(position_code)}: {recibido} % y debería ser {esperado} %"
        )


def _fila(ht_player_id: int, position_code: int, minutos: int) -> PlayedSegment:
    return PlayedSegment(
        ht_player_id=ht_player_id,
        player_name="Un Jugador",
        ht_match_id=771779994,
        position_code=position_code,
        played_minutes=minutos,
        rating=None,
        played_at=None,
        match_type=1,
        source="playerdetails-history",
    )


def test_el_caso_del_usuario_de_punta_a_punta() -> None:
    """87′ de lateral y 3′ de extremo, con entrenamiento de Lateral.

    2026-10-08, reportado por un usuario con su jugador 513909842. Hattrick
    publica una sola fila por partido --«extremo, 90 minutos», el puesto en el
    que acabó-- y de ahí salía el 100 % de semana. Con el once inicial y el
    cambio, que vienen en `matchlineup.xml`, se reparte: el extremo cobra el
    100 % y el lateral el 50 %, así que son 87×0,5 + 3×1,0 = 46,5 minutos
    equivalentes, el 51,7 % de la semana.
    """
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    una_fila = [_fila(513909842, 110, 90)]

    # Como estaba: una fila, el puesto en el que acabó, la semana entera.
    assert round(service._exposicion(5, una_fila), 4) == 1.0

    once = json.dumps([{"ht_player_id": 513909842, "role_id": 105, "behaviour": 0}])
    eventos = json.dumps(
        {
            "cambios": [
                {
                    "minuto": 87,
                    "sale": 513909842,
                    "entra": 513909842,
                    "nuevo_puesto": 110,
                    "order_type": 3,
                }
            ],
            "cobrador": 0,
        }
    )
    tramos = _repartidos_por_puesto(una_fila, {771779994: (once, eventos)})

    assert sorted((t.position_code, t.played_minutes) for t in tramos) == [(105, 87), (110, 3)]
    assert round(service._exposicion(5, tramos), 4) == 0.5167


def test_sin_alineacion_guardada_el_partido_se_queda_como_estaba() -> None:
    """Los partidos viejos y los que la sincronización no ha alcanzado.

    Baja tres alineaciones por vez, así que durante un tiempo convivirán las
    dos formas. El que no tiene alineación no se inventa: conserva su fila.
    """
    una_fila = [_fila(513909842, 110, 90)]
    assert _repartidos_por_puesto(una_fila, {}) == una_fila
    assert _repartidos_por_puesto(una_fila, {771779994: (None, None)}) == una_fila
    assert _repartidos_por_puesto(una_fila, {771779994: ("{roto", "{roto")}) == una_fila


def test_el_cobrador_de_tiros_libres_entrena_al_125() -> None:
    """Regla del usuario, 2026-10-09, en Balón parado y juegue donde juegue.

    Un delantero que cobra las faltas recibe el 125 %, no el 100 %. Antes esto
    no se podía ni representar: la exposición estaba topada en 1,0.
    """
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    once = json.dumps([{"ht_player_id": 7, "role_id": 112, "behaviour": 0}])
    con_cobrador = json.dumps({"cambios": [], "cobrador": 7})
    sin_cobrador = json.dumps({"cambios": [], "cobrador": 0})

    cobra = _repartidos_por_puesto([_fila(7, 112, 90)], {771779994: (once, con_cobrador)})
    no_cobra = _repartidos_por_puesto([_fila(7, 112, 90)], {771779994: (once, sin_cobrador)})

    assert round(service._exposicion(2, cobra), 4) == 1.25
    assert round(service._exposicion(2, no_cobra), 4) == 1.0
    # Y sólo en Balón parado: en cualquier otro entrenamiento es uno más.
    assert round(service._exposicion(4, cobra), 4) == 1.0


@pytest.mark.asyncio
async def test_el_partido_de_su_club_anterior_NO_entrena_aqui() -> None:
    """2026-11-14, pedido del usuario: a un recién llegado sólo se le cuentan
    los partidos jugados con ESTE equipo. Su último partido con el club
    anterior está en la base (de un rival estudiado, por ejemplo) y entraba en
    sus minutos de entrenamiento."""
    factory, team_id = await seeded_session()
    now = datetime.now(UTC)

    async with factory() as s:
        player = (
            await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .limit(1)
            )
        ).scalar_one()
        world = (await s.execute(select(m.WorldContext).limit(1))).scalar_one()
        world.training_date = now + timedelta(days=1)
        world.refreshed_at = now
        s.add(
            m.Match(
                ht_match_id=900002,
                played_at=now,
                match_type=1,
                status="Finished",
                home_team_ht_id=555,
                away_team_ht_id=666,
                home_team_name="Su club anterior",
                away_team_name="Otro",
                home_goals=1,
                away_goals=1,
            )
        )
        s.add(
            m.PlayerMatchRating(
                player_id=player.id,
                ht_match_id=900002,
                position_code=13,
                played_minutes=90,
                rating=7.0,
                captured_at=now,
            )
        )
        await s.commit()

    segmentos, _ = await PostMatchTrainingService(s)._played_segments(
        team_id, now - timedelta(days=7), now + timedelta(days=1)
    )
    assert all(seg.ht_match_id != 900002 for seg in segmentos)


def test_los_mejores_90_de_la_semana_y_nada_mas() -> None:
    """Regla del usuario, 2026-11-25, con su ejemplo: 90 minutos de delantero
    el miércoles y 45 de portero el domingo. Hattrick coge los mejores 90
    minutos entrenables de la semana para cada entrenamiento: con Anotación
    cuentan los 90 de delantero, y con Portería, los 45 de portero."""
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    miercoles = replace(_fila(1, 112, 90), ht_match_id=1)
    domingo = replace(_fila(1, 100, 45), ht_match_id=2)
    semana = [miercoles, domingo]

    assert service._exposicion(4, semana) == 1.0
    assert service._exposicion(9, semana) == 0.5
    # Balón parado lo reciben los dos puestos: aun así el tope es de 90.
    assert service._exposicion(2, semana) == 1.0


async def _sembrar_copa_y_liga(*, con_ficha_de_copa: bool) -> tuple[Any, int, list[int]]:
    """Copa el miércoles y liga el domingo, con dos jugadores de la plantilla.

    De la copa queda la alineación entera. Las fichas sólo recuerdan el último
    partido de cada uno: la liga. Es lo que pasa cuando no se sincroniza entre
    los dos partidos.
    """
    factory, team_id = await seeded_session()
    now = datetime.now(UTC)
    async with factory() as s:
        team = await s.get(m.Team, team_id)
        assert team is not None
        jugadores = (
            (
                await s.execute(
                    select(m.Player)
                    .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                    .limit(2)
                )
            )
            .scalars()
            .all()
        )
        uno, otro = jugadores
        world = (await s.execute(select(m.WorldContext).limit(1))).scalar_one()
        world.training_date = now + timedelta(days=1)
        world.refreshed_at = now
        for ht_match_id, cuando, tipo in (
            (910001, now - timedelta(days=4), 3),
            (910002, now - timedelta(days=1), 1),
        ):
            s.add(
                m.Match(
                    ht_match_id=ht_match_id,
                    played_at=cuando,
                    match_type=tipo,
                    status="FINISHED",
                    home_team_ht_id=team.ht_team_id,
                    away_team_ht_id=123,
                    home_team_name=team.name,
                    away_team_name="Rival",
                    home_goals=1,
                    away_goals=0,
                    played_lineup_json=json.dumps(
                        [
                            {"ht_player_id": uno.ht_player_id, "role_id": 112, "behaviour": 0},
                            {"ht_player_id": otro.ht_player_id, "role_id": 103, "behaviour": 0},
                        ]
                        if tipo == 3
                        else [
                            {"ht_player_id": uno.ht_player_id, "role_id": 100, "behaviour": 0},
                            {"ht_player_id": otro.ht_player_id, "role_id": 103, "behaviour": 0},
                        ]
                    ),
                    # En la copa, el central se va en el 60 y no vuelve.
                    played_events_json=json.dumps(
                        {
                            "cambios": (
                                [
                                    {
                                        "minuto": 60,
                                        "sale": otro.ht_player_id,
                                        "entra": 999999999,
                                        "nuevo_puesto": 103,
                                        "order_type": 1,
                                    }
                                ]
                                if tipo == 3
                                else []
                            ),
                            "cobrador": 0,
                        }
                    ),
                )
            )
        # La liga, en la ficha de los dos: su último partido.
        for jugador, puesto, minutos in ((uno, 100, 45), (otro, 103, 90)):
            s.add(
                m.PlayerMatchRating(
                    player_id=jugador.id,
                    ht_match_id=910002,
                    position_code=puesto,
                    played_minutes=minutos,
                    rating=6.0,
                    captured_at=now,
                )
            )
        if con_ficha_de_copa:
            s.add(
                m.PlayerMatchRating(
                    player_id=uno.id,
                    ht_match_id=910001,
                    position_code=112,
                    played_minutes=90,
                    rating=7.0,
                    captured_at=now - timedelta(days=3),
                )
            )
        await s.commit()
    return factory, team_id, [uno.ht_player_id, otro.ht_player_id]


@pytest.mark.asyncio
async def test_la_copa_no_se_pierde_aunque_no_se_sincronice_entre_partidos() -> None:
    """2026-11-25, la copa del 18-nov: entre ella y la liga no hubo
    sincronización y de once jugadores sólo uno conservaba la copa en su ficha.
    La alineación guardada la reconstruye: el delantero de la copa cobra sus 90
    minutos de Anotación aunque su ficha sólo diga «portero, 45»."""
    factory, team_id, (delantero, central) = await _sembrar_copa_y_liga(con_ficha_de_copa=False)
    now = datetime.now(UTC)
    async with factory() as s:
        service = PostMatchTrainingService(s)
        segmentos, _ = await service._played_segments(
            team_id, now - timedelta(days=7), now + timedelta(days=1)
        )

    suyos = [seg for seg in segmentos if seg.ht_player_id == delantero]
    assert sorted((seg.ht_match_id, seg.position_code, seg.played_minutes) for seg in suyos) == [
        (910001, 112, 90),
        (910002, 100, 45),
    ]
    assert service._exposicion(4, suyos) == 1.0
    assert service._exposicion(9, suyos) == 0.5
    # El central se fue en el 60 de la copa: la alineación lo dice, sin ficha.
    del_central = sorted(
        (seg.ht_match_id, seg.played_minutes) for seg in segmentos if seg.ht_player_id == central
    )
    assert del_central == [(910001, 60), (910002, 90)]
    # Y el que entró por él no es de la plantilla: no se le inventa nada.
    assert all(seg.ht_player_id != 999999999 for seg in segmentos)


@pytest.mark.asyncio
async def test_con_ficha_de_copa_no_se_cuenta_dos_veces() -> None:
    factory, team_id, (delantero, _) = await _sembrar_copa_y_liga(con_ficha_de_copa=True)
    now = datetime.now(UTC)
    async with factory() as s:
        segmentos, _ = await PostMatchTrainingService(s)._played_segments(
            team_id, now - timedelta(days=7), now + timedelta(days=1)
        )
    de_copa = [s for s in segmentos if s.ht_player_id == delantero and s.ht_match_id == 910001]
    assert [(s.position_code, s.played_minutes) for s in de_copa] == [(112, 90)]


@pytest.mark.asyncio
async def test_la_ventana_es_un_ciclo_de_siete_dias() -> None:
    """Domingo de liga + partido entre semana, y al corte vuelve a empezar
    (regla del usuario, 2026-11-25). Un partido de hace siete días y medio ya
    se entrenó en el ciclo anterior y no entra."""
    factory, team_id = await seeded_session()
    now = datetime.now(UTC)
    async with factory() as s:
        team = await s.get(m.Team, team_id)
        assert team is not None
        player = (
            await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .limit(1)
            )
        ).scalar_one()
        world = (await s.execute(select(m.WorldContext).limit(1))).scalar_one()
        world.training_date = now
        world.refreshed_at = now
        s.add(
            m.Match(
                ht_match_id=920001,
                played_at=now - timedelta(days=7, hours=12),
                match_type=1,
                status="FINISHED",
                home_team_ht_id=team.ht_team_id,
                away_team_ht_id=123,
                home_team_name=team.name,
                away_team_name="Rival",
                home_goals=0,
                away_goals=0,
                played_lineup_json=json.dumps(
                    [{"ht_player_id": player.ht_player_id, "role_id": 112, "behaviour": 0}]
                ),
                played_events_json=json.dumps({"cambios": [], "cobrador": 0}),
            )
        )
        await s.commit()
        result = await PostMatchTrainingService(s).get(team_id)

    assert result is not None
    row = next(p for p in result["players"] if p["htPlayerId"] == player.ht_player_id)
    assert all(seg["matchId"] != 920001 for seg in row["segments"])
