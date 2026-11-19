"""«Mejor alineación» (2026-11-19): el once de la app, previsto por Hattrick
sin enviarlo. Lo que se vigila es que se PREVÉ y nunca se guarda, y que un
fallo de Hattrick no tumba la ficha."""

import asyncio
from pathlib import Path
from typing import Any

from app.application.queries.mejor_alineacion import (
    SECTORES_PREVISTOS,
    filas_del_once,
    mejor_once,
    prevision_de_la_mejor,
)
from app.infrastructure.chpp.parsers import parse_matchorders, parse_players

FIXTURES = Path(__file__).parent / "fixtures"
ROSTER = parse_players((FIXTURES / "players.xml").read_bytes())["players"]


class HattrickDePrueba:
    def __init__(self, respuesta: dict[str, Any] | Exception) -> None:
        self.respuesta = respuesta
        self.llamadas: list[dict[str, Any]] = []

    async def alineacion(self, ht_match_id: int, team_id: int, payload: dict, **kw: Any) -> dict:
        self.llamadas.append({"match": ht_match_id, "team": team_id, "payload": payload, **kw})
        if isinstance(self.respuesta, Exception):
            raise self.respuesta
        return self.respuesta


PREVISION = parse_matchorders((FIXTURES / "matchorders_predictratings.xml").read_bytes())


def test_se_preve_y_nunca_se_guarda() -> None:
    hattrick = HattrickDePrueba(PREVISION)
    out = asyncio.run(prevision_de_la_mejor(hattrick, ROSTER, 775653933, 537758, version="3.0"))
    assert out is not None
    ratings, formacion = out
    assert set(ratings) == set(SECTORES_PREVISTOS)
    assert formacion
    [llamada] = hattrick.llamadas
    assert llamada["guardar"] is False
    assert llamada["match"] == 775653933 and llamada["team"] == 537758
    # El once entero va en las catorce ranuras, con la táctica Normal.
    payload = llamada["payload"]
    assert sum(1 for r in payload["positions"] if r["id"]) == 11
    assert payload["settings"]["tactic"] == 0


def test_el_once_es_el_de_alineacion() -> None:
    lu = mejor_once(ROSTER)
    assert lu is not None
    once, banquillo = filas_del_once(lu)
    assert [f["htPlayerId"] for f in once] == [
        a.player["ht_player_id"] for a in sorted(lu.assignments, key=lambda a: a.slot)
    ]
    assert len(banquillo) == len(lu.bench)


def test_si_hattrick_falla_no_hay_prevision_y_no_revienta() -> None:
    hattrick = HattrickDePrueba(RuntimeError("Hattrick caído"))
    assert asyncio.run(prevision_de_la_mejor(hattrick, ROSTER, 1, 2, version="3.0")) is None


def test_una_respuesta_sin_ratings_no_vale() -> None:
    hattrick = HattrickDePrueba({"prediction": None, "chpp_error": "Index was out of range"})
    assert asyncio.run(prevision_de_la_mejor(hattrick, ROSTER, 1, 2, version="3.0")) is None


def test_sin_once_no_se_le_pregunta_a_hattrick() -> None:
    hattrick = HattrickDePrueba(PREVISION)
    assert asyncio.run(prevision_de_la_mejor(hattrick, ROSTER[:5], 1, 2, version="3.0")) is None
    assert hattrick.llamadas == []
