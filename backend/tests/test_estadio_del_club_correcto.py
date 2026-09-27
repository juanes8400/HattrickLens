"""El estadio que se guarda es el del club que se pidio, o no se guarda.

2026-09-27, reporte de un usuario: «el Estadio saca los datos del club
principal, sea cual sea el club que estes mirando».

Es la misma forma del fallo que tuvo la cantera en septiembre: una cuenta de
Hattrick puede llevar varios clubes, y si el fichero que contesta no es el que
pediste, nadie se entera. Alli se arreglo comprobando que la academia devuelta
fuera la del club. El lector del estadio ya venia leyendo de que club es, pero
ese dato se tiraba sin mirarlo.
"""

import asyncio

from app.application.commands.sync_team import SyncResult, aforo_del_estadio

MIO = 537758
DEL_PRINCIPAL = 71743
AFORO = {"terraces": 6000, "basic": 4000, "roof": 2000, "vip": 500, "total": 12500}


class _CHPP:
    def __init__(self, de_quien: int | None) -> None:
        self.de_quien = de_quien

    async def fetch(self, file: str, **kw):
        assert file == "arenadetails"
        assert kw["teamID"] == MIO, "se pide el estadio DE ESTE club"
        payload = {"current_capacity": dict(AFORO)}
        if self.de_quien is not None:
            payload["ht_team_id"] = self.de_quien
        return payload


def _pedir(de_quien: int | None):
    informe = SyncResult(sync_id=0, status="completed")
    aforo = asyncio.run(aforo_del_estadio(_CHPP(de_quien), MIO, informe))
    return aforo, informe.errors


def test_el_estadio_propio_se_usa() -> None:
    aforo, errores = _pedir(MIO)
    assert aforo == AFORO
    assert errores == []


def test_el_estadio_de_otro_club_no_se_usa_y_se_dice() -> None:
    """Un aforo equivocado es peor que ninguno: de el salen todas las
    ocupaciones y la cuenta de si compensa ampliar."""
    aforo, errores = _pedir(DEL_PRINCIPAL)
    assert aforo is None
    assert len(errores) == 1
    assert str(DEL_PRINCIPAL) in errores[0]


def test_sin_ese_dato_no_se_bloquea_nada() -> None:
    """Una version del fichero que no lo traiga no puede dejar sin estadio a
    todo el mundo: se sigue como antes."""
    aforo, errores = _pedir(None)
    assert aforo == AFORO
    assert errores == []
