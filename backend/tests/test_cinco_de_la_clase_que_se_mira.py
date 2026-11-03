"""La ficha de rival enseña cinco DE LO QUE SE ESTÁ MIRANDO.

2026-11-02/03. El usuario: «sigo viendo 2 en Rivales» para Angkor FC. No era
que faltaran partidos --Hattrick tenía dieciocho oficiales suyos en dieciséis
semanas-- ni que fallara la llamada al archivo. Era que la ventana se recortaba
a cinco MEZCLANDO clases y el selector filtraba después: contra un rival sin
cruce oficial pendiente --cualquiera, con la liga terminada-- esos cinco eran
dos de liga y tres amistosos, y cada botón enseñaba su mitad.

Reproducido contra Hattrick de verdad antes de arreglarlo: Angkor 2,
Calduteros 2, Casiba 5, exactamente los números de producción. Casiba era el
único con cinco oficiales en el calendario del último mes.
"""

import asyncio
from typing import Any

from app.api.v1.endpoints.rivals import fetch_rival_matches_and_lineups

RIVAL = 2230608
#: Dos de liga y tres amistosos, que es lo que tenía Angkor en el calendario.
CALENDARIO = [
    (900_001, 1, "2026-10-18 20:00:00"),
    (900_002, 1, "2026-10-25 20:00:00"),
    (900_003, 4, "2026-10-21 20:00:00"),
    (900_004, 4, "2026-10-28 20:00:00"),
    (900_005, 5, "2026-10-14 20:00:00"),
]
#: Y en el archivo, los oficiales de antes que el calendario ya no alcanza.
ARCHIVO = [(900_010 + i, 1, f"2026-09-{13 + i * 7:02d} 20:00:00") for i in range(4)]


def _partido(ht_match_id: int, tipo: int, cuando: str) -> dict[str, Any]:
    return {
        "ht_match_id": ht_match_id,
        "match_type": tipo,
        "match_date": cuando,
        "status": "FINISHED",
        "home_team_id": RIVAL,
        "away_team_id": 999,
        "home_team_name": "Angkor FC",
        "away_team_name": "Otro",
        "home_goals": 1,
        "away_goals": 0,
    }


class CHPPFalso:
    def __init__(self) -> None:
        self.llamadas: list[str] = []

    async def fetch(self, file: str, version: str = "", **params: Any) -> dict[str, Any]:
        self.llamadas.append(file)
        if file == "players":
            return {"players": [], "team_name": "Angkor FC"}
        if file == "matches":
            return {"matches": [_partido(*p) for p in CALENDARIO]}
        if file == "matchesarchive":
            return {"matches": [_partido(*p) for p in ARCHIVO]}
        if file == "matchdetails":
            return {"home": {}, "away": {}}
        if file == "matchlineup":
            return {"players": []}
        return {}


def _ficha(*, oficiales: bool, amistosos: bool):
    from datetime import UTC, datetime, timedelta

    chpp = CHPPFalso()

    async def go():
        return await fetch_rival_matches_and_lineups(
            chpp,  # type: ignore[arg-type]
            RIVAL,
            include_competitive=oficiales,
            include_friendlies=amistosos,
            # SIN cruce oficial pendiente, que es el caso que fallaba: con la
            # liga terminada ningún rival tiene uno.
            solo_oficiales=False,
            desde=datetime(2026, 7, 13, tzinfo=UTC) - timedelta(0),
        )

    return asyncio.run(go()), chpp


def test_con_el_selector_en_oficiales_salen_cinco_oficiales() -> None:
    ficha, chpp = _ficha(oficiales=True, amistosos=False)
    tipos = [mt["match_type"] for mt in ficha.matches]
    assert len(ficha.matches) == 5, tipos
    assert all(t == 1 for t in tipos), tipos
    # Y para conseguirlos hubo que ir al archivo: el calendario sólo tenía dos.
    assert "matchesarchive" in chpp.llamadas


def test_con_el_selector_en_amistosos_salen_los_amistosos() -> None:
    ficha, _ = _ficha(oficiales=False, amistosos=True)
    tipos = [mt["match_type"] for mt in ficha.matches]
    assert tipos and all(t in (4, 5) for t in tipos), tipos
