"""La autopsia del último partido (2026-11-22, definida por el usuario).

Tres capas del mismo motor --lo que dijimos, con lo real tuyo y lo supuesto
del rival, con lo real de los dos--, un veredicto en claves y los jugadores
que jugaron por debajo de su media.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.queries.autopsia_del_partido import (
    _capa,
    autopsia_del_partido,
    duelo_decisivo,
    veredicto,
)
from app.application.queries.lo_dicho import lo_supuesto
from app.domain.value_objects.ht_constants import MATCH_TYPE_LEAGUE
from app.infrastructure.db import models as m
from tests.conftest import HT_TEAM_ID, seeded_session

#: Más tarde que cualquier partido de la base sembrada: es «el último».
PITIDO = datetime(2027, 3, 7, 21, 40, tzinfo=UTC)
PARTIDO = 880_000_001
RIVAL = 600_123

SECTORES = ("midfield", "left_def", "central_def", "right_def", "left_att", "central_att", "right_att")


def _todos(valor: float, **cambios: float) -> dict[str, float]:
    return {**dict.fromkeys(SECTORES, valor), "sp_def": valor, "sp_att": valor, **cambios}


def _fila(team_ht_id: int, en_casa: bool, r: dict[str, float]) -> m.MatchRating:
    return m.MatchRating(
        ht_match_id=PARTIDO,
        team_ht_id=team_ht_id,
        is_home=en_casa,
        midfield=int(r["midfield"]),
        left_def=int(r["left_def"]),
        central_def=int(r["central_def"]),
        right_def=int(r["right_def"]),
        left_att=int(r["left_att"]),
        central_att=int(r["central_att"]),
        right_att=int(r["right_att"]),
        set_pieces_def=int(r["sp_def"]),
        set_pieces_att=int(r["sp_att"]),
        tactic_type=0,
    )


def _autopsia(
    *,
    en_casa: bool = True,
    goles: tuple[int, int] = (1, 2),
    propio: dict[str, float] | None = None,
    rival: dict[str, float] | None = None,
    dicho: dict[str, Any] | None = None,
    supuesto: dict[str, Any] | None = None,
    con_valoraciones: bool = True,
    sembrar: Any = None,
) -> dict[str, Any] | None:
    async def go() -> dict[str, Any] | None:
        factory, team_id = await seeded_session()
        async with factory() as s:
            local, visita = (HT_TEAM_ID, RIVAL) if en_casa else (RIVAL, HT_TEAM_ID)
            s.add(
                m.Match(
                    ht_match_id=PARTIDO,
                    played_at=PITIDO,
                    match_type=MATCH_TYPE_LEAGUE,
                    status="finished",
                    home_team_ht_id=local,
                    away_team_ht_id=visita,
                    home_team_name="Local",
                    away_team_name="Visita",
                    home_goals=goles[0],
                    away_goals=goles[1],
                )
            )
            if con_valoraciones:
                s.add(_fila(HT_TEAM_ID, en_casa, propio or _todos(40)))
                s.add(_fila(RIVAL, not en_casa, rival or _todos(40)))
            if dicho is not None:
                s.add(
                    m.MatchPrediction(
                        ht_match_id=PARTIDO,
                        team_id=team_id,
                        source="zonas",
                        engine="x",
                        computed_at=PITIDO - timedelta(days=1),
                        supuesto_json=None if supuesto is None else json.dumps(supuesto),
                        **dicho,
                    )
                )
            if sembrar is not None:
                await sembrar(s, team_id)
            await s.commit()
        async with factory() as s:
            return await autopsia_del_partido(s, team_id)

    return asyncio.run(go())


def _dicho_desde_el_local(capa: dict[str, Any]) -> dict[str, Any]:
    return {
        "home_win": capa["gana"],
        "draw": capa["empate"],
        "away_win": capa["pierde"],
        "expected_home_goals": 1.5,
        "expected_away_goals": 1.0,
        "most_likely_score": capa["marcador"],
    }


def test_sin_valoraciones_lo_dice_en_vez_de_inventar() -> None:
    autopsia = _autopsia(con_valoraciones=False)
    assert autopsia == {"htMatchId": PARTIDO, "sinValoraciones": True}


def test_el_rival_vino_mas_fuerte_de_lo_supuesto() -> None:
    """Dijimos que ganábamos; el rival salió mucho más fuerte que lo que
    suponíamos --sobre todo en la defensa central-- y perdimos. Con lo real
    era lo más probable: el fallo fue de información, y del lado del rival."""
    supuesto_propio, supuesto_rival = _todos(40), _todos(30)
    rival_real = _todos(50, central_def=70)
    supuesto = lo_supuesto(supuesto_propio, supuesto_rival, 1.0, 1.0)
    dicho = _capa("dicho", supuesto_propio, supuesto_rival, 1.0, 1.0, False)
    autopsia = _autopsia(
        rival=rival_real, dicho=_dicho_desde_el_local(dicho), supuesto=supuesto
    )
    assert autopsia is not None
    assert autopsia["resultado"] == "pierde"
    capas = {c["clave"]: c for c in autopsia["capas"]}
    assert list(capas) == ["dicho", "realPropio", "real"]
    assert capas["dicho"]["gana"] > capas["dicho"]["pierde"]
    assert capas["real"]["pierde"] > capas["real"]["gana"]
    assert autopsia["veredicto"] == {
        "tipo": "informacion",
        "culpa": "rival",
        "sector": "central_def",
    }
    defensa = next(
        f
        for f in autopsia["supuestoVsReal"]
        if f["lado"] == "rival" and f["sector"] == "central_def"
    )
    assert (defensa["supuesto"], defensa["real"]) == (30, 70)


def test_de_visitante_lo_dicho_se_pone_del_lado_propio() -> None:
    dicho = {
        "home_win": 0.2,
        "draw": 0.2,
        "away_win": 0.6,
        "expected_home_goals": 0.8,
        "expected_away_goals": 1.7,
        "most_likely_score": "0-2",
    }
    autopsia = _autopsia(en_casa=False, goles=(0, 2), dicho=dicho)
    assert autopsia is not None
    primera = autopsia["capas"][0]
    assert (primera["gana"], primera["pierde"], primera["marcador"]) == (0.6, 0.2, "2-0")
    assert autopsia["resultado"] == "gana"
    # Sin lo supuesto no hay fila del medio ni tabla.
    assert [c["clave"] for c in autopsia["capas"]] == ["dicho", "real"]
    assert autopsia["supuestoVsReal"] == []


def test_sin_prediccion_queda_el_duelo_decisivo() -> None:
    autopsia = _autopsia(goles=(2, 0), propio=_todos(40, left_att=70))
    assert autopsia is not None
    assert autopsia["veredicto"] == {
        "tipo": "sinPrediccion",
        "culpa": None,
        "sector": "left_att",
    }


def test_esperado_y_azar() -> None:
    propio, rival = _todos(40), _todos(30)
    real = _capa("real", propio, rival, 1.0, 1.0, False)
    capas = {"dicho": real, "real": real}
    assert veredicto("gana", capas, propio, rival, None)["tipo"] == "esperado"
    assert veredicto("pierde", capas, propio, rival, None)["tipo"] == "azar"


def test_en_un_empate_no_hay_duelo_decisivo() -> None:
    assert duelo_decisivo(_todos(40), _todos(40), "empate") is None


def test_lo_supuesto_guarda_solo_los_campos_del_motor() -> None:
    lectura = {**_todos(40), "tactic_type": 3.0, "ht_match_id": 1.0, "en_casa": 1.0}
    supuesto = lo_supuesto(lectura, lectura, 1.1, 0.9)
    assert set(supuesto["propio"]) == {*SECTORES, "sp_def", "sp_att"}
    assert supuesto["factorPropio"] == 1.1


def test_por_debajo_de_su_media() -> None:
    """Una estrella o más por debajo de la media de sus partidos anteriores,
    con al menos tres; quien tiene dos partidos no tiene media todavía."""

    async def sembrar(s: Any, team_id: int) -> None:
        for ht_id, previas, hoy in ((990_001, [4.0, 4.5, 4.0], 2.5), (990_002, [5.0, 5.0], 2.0)):
            jugador = m.Player(
                ht_player_id=ht_id, team_id=team_id, first_name="Juan", last_name=str(ht_id)
            )
            s.add(jugador)
            await s.flush()
            for i, nota in enumerate(previas):
                s.add(
                    m.PlayerMatchRating(
                        player_id=jugador.id,
                        ht_match_id=870_000_000 + ht_id * 10 + i,
                        position_code=100,
                        played_minutes=90,
                        rating=nota,
                        captured_at=PITIDO - timedelta(days=7 * (i + 1)),
                    )
                )
            s.add(
                m.PlayerMatchRating(
                    player_id=jugador.id,
                    ht_match_id=PARTIDO,
                    position_code=100,
                    played_minutes=90,
                    rating=hoy,
                    captured_at=PITIDO,
                )
            )

    autopsia = _autopsia(sembrar=sembrar)
    assert autopsia is not None
    assert autopsia["porDebajoDeSuMedia"] == [
        {
            "htPlayerId": 990_001,
            "nombre": "Juan 990001",
            "estrellas": 2.5,
            "media": 4.2,
            "partidos": 3,
        }
    ]
