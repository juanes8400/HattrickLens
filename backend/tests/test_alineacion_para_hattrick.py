"""El once de HT Lens escrito como lo quiere Hattrick (2026-09-19).

Lo que se vigila aquí es lo único que puede salir caro de verdad: que un
jugador acabe en la ranura equivocada. Una ranura mal puesta no da error, da
un partido jugado con la alineación cambiada, así que las catorce posiciones
se comprueban una por una contra el mismo orden que Hattrick usa al DEVOLVER
las órdenes (`RoleID` 100-113).
"""

import pytest

from app.domain.value_objects.alineacion_para_hattrick import (
    AlineacionInvalidaError,
    alineacion_para_hattrick,
    banquillo_de,
    posiciones_de,
)


def once(*filas: tuple[str, str, int]) -> list[dict]:
    return [
        {"basePosition": puesto, "behaviour": orden, "htPlayerId": jugador}
        for puesto, orden, jugador in filas
    ]


ONCE_442 = once(
    ("keeper", "normal", 1),
    ("wingback", "offensive", 2),
    ("wingback", "normal", 3),
    ("central_defender", "normal", 4),
    ("central_defender", "towards_wing", 5),
    ("winger", "defensive", 6),
    ("winger", "normal", 7),
    ("inner_midfield", "offensive", 8),
    ("inner_midfield", "towards_middle", 9),
    ("forward", "normal", 10),
    ("forward", "defensive", 11),
)


def test_cada_puesto_cae_en_su_ranura() -> None:
    ranuras = posiciones_de(ONCE_442)
    ids = [r["id"] for r in ranuras]
    # portero, lateral D, central D, centro, central I, lateral I,
    # extremo D, interior D, interior centro, interior I, extremo I,
    # delantero D, delantero centro, delantero I
    assert ids == [1, 2, 4, 0, 5, 3, 6, 8, 0, 9, 7, 10, 0, 11]


def test_la_orden_individual_viaja_con_su_codigo() -> None:
    ranuras = posiciones_de(ONCE_442)
    assert ranuras[1]["behaviour"] == 1  # lateral ofensivo
    assert ranuras[4]["behaviour"] == 4  # central hacia el lateral
    assert ranuras[6]["behaviour"] == 2  # extremo defensivo
    assert ranuras[9]["behaviour"] == 3  # interior hacia el centro
    assert ranuras[0]["behaviour"] == 0  # portero, normal


def test_un_solo_central_juega_por_el_centro() -> None:
    ranuras = posiciones_de(
        once(
            ("keeper", "normal", 1),
            ("central_defender", "normal", 2),
            ("wingback", "normal", 3),
            ("wingback", "normal", 4),
            ("inner_midfield", "normal", 5),
            ("inner_midfield", "normal", 6),
            ("inner_midfield", "normal", 7),
            ("winger", "normal", 8),
            ("winger", "normal", 9),
            ("forward", "normal", 10),
            ("forward", "normal", 11),
        )
    )
    assert ranuras[3]["id"] == 2
    assert ranuras[2]["id"] == 0 and ranuras[4]["id"] == 0


def test_tres_de_una_linea_llenan_las_tres_ranuras() -> None:
    ranuras = posiciones_de(
        once(
            ("keeper", "normal", 1),
            ("central_defender", "normal", 2),
            ("central_defender", "normal", 3),
            ("central_defender", "normal", 4),
            ("wingback", "normal", 5),
            ("wingback", "normal", 6),
            ("inner_midfield", "normal", 7),
            ("inner_midfield", "normal", 8),
            ("inner_midfield", "normal", 9),
            ("forward", "normal", 10),
            ("forward", "normal", 11),
        )
    )
    assert [ranuras[i]["id"] for i in (2, 3, 4)] == [2, 3, 4]
    assert [ranuras[i]["id"] for i in (7, 8, 9)] == [7, 8, 9]


def test_un_puesto_que_no_cabe_se_rechaza_antes_de_enviar() -> None:
    """Cuatro centrales no existen en Hattrick. Vale mucho más un error aquí
    que un fichero aceptado a medias."""
    with pytest.raises(AlineacionInvalidaError):
        posiciones_de(once(*[("central_defender", "normal", i) for i in range(1, 5)]))


def test_el_banquillo_va_en_el_orden_de_hattrick() -> None:
    """El delantero suplente va ANTES que el extremo, al revés que en la app."""
    ranuras = banquillo_de(
        [
            {"slot": "keeper", "htPlayerId": 21},
            {"slot": "central_defender", "htPlayerId": 22},
            {"slot": "wingback", "htPlayerId": 23},
            {"slot": "inner_midfield", "htPlayerId": 24},
            {"slot": "winger", "htPlayerId": 25},
            {"slot": "forward", "htPlayerId": 26},
        ]
    )
    assert [r["id"] for r in ranuras] == [21, 22, 23, 24, 26, 25, 0, 0, 0, 0, 0, 0, 0, 0]


def test_lo_que_no_proponemos_se_devuelve_tal_cual() -> None:
    """Enviar el once no puede borrar la táctica ni el capitán del usuario."""
    actuales = {
        "tactic_type": 2,
        "attitude": 1,
        "coach_modifier": -1,
        "captain": 444,
        "set_pieces": 555,
        "kickers": [10, 11],
        "substitutions": [{"playerIn": "1", "playerOut": "2"}],
    }
    payload = alineacion_para_hattrick(ONCE_442, [], actuales=actuales)
    assert payload["settings"]["tactic"] == "2"
    assert payload["settings"]["speechLevel"] == "1"
    assert payload["settings"]["coachModifier"] == "-1"
    assert payload["captain"] == "444"
    assert payload["setPieces"] == "555"
    assert payload["substitutions"] == [{"playerIn": "1", "playerOut": "2"}]
    assert [k["id"] for k in payload["kickers"][:2]] == [10, 11]
    assert len(payload["kickers"]) == 11
    assert len(payload["positions"]) == 14
    assert len(payload["bench"]) == 14
