"""Los carriles centrales tienen lado, y el lado decide las ordenes.

Con tres en linea hay uno izquierdo, uno central y uno derecho. El lado no
cambia lo que aporta el jugador: decide si puede salir «hacia el lateral».
El del medio no tiene lado al que salir, asi que no puede.
"""
import pytest

from app.domain.engines.lineup_optimizer import (
    ORDER_VARIANTS,
    best_lineup,
    variantes_de_casilla,
)
from app.domain.value_objects.formations import slots_for


def _jugadores(n: int = 14) -> list[dict]:
    return [
        {
            "ht_player_id": i, "name": f"J{i}", "tsi": 10000,
            "ratings": {}, "form": 7, "stamina": 8,
        }
        for i in range(1, n + 1)
    ]


@pytest.mark.parametrize("carril", ["central_defender", "inner_midfield", "forward"])
def test_el_del_medio_no_puede_salir_hacia_el_lateral(carril: str) -> None:
    slots = [carril, carril, carril]
    izquierda = variantes_de_casilla(slots, 0)
    medio = variantes_de_casilla(slots, 1)
    derecha = variantes_de_casilla(slots, 2)

    hacia_lateral = [v for v in ORDER_VARIANTS[carril] if v.endswith("_towards_wing")]
    assert hacia_lateral, "este carril deberia tener esa orden"
    for v in hacia_lateral:
        assert v in izquierda
        assert v in derecha
        assert v not in medio, "el del medio no tiene lado al que salir"


@pytest.mark.parametrize("carril", ["central_defender", "inner_midfield", "forward"])
def test_con_dos_en_linea_los_dos_son_de_lado(carril: str) -> None:
    slots = [carril, carril]
    for i in (0, 1):
        assert variantes_de_casilla(slots, i) == ORDER_VARIANTS[carril]


def test_las_demas_ordenes_siguen_en_el_medio() -> None:
    """Solo se pierde «hacia el lateral». Ofensiva y defensiva se quedan."""
    medio = variantes_de_casilla(["inner_midfield"] * 3, 1)
    assert "inner_midfield" in medio
    assert "inner_midfield_offensive" in medio
    assert "inner_midfield_defensive" in medio


def test_un_carril_no_contamina_al_de_al_lado() -> None:
    """Tres centrales y dos delanteros: los delanteros conservan la suya."""
    slots = slots_for("3-5-2")
    delanteros = [i for i, s in enumerate(slots) if s == "forward"]
    assert len(delanteros) == 2
    for i in delanteros:
        assert "forward_towards_wing" in variantes_de_casilla(slots, i)


def test_no_se_puede_fijar_esa_orden_en_el_medio() -> None:
    slots = slots_for("3-5-2")
    medio = [i for i, s in enumerate(slots) if s == "central_defender"][1]
    with pytest.raises(ValueError, match="no es una orden"):
        best_lineup(_jugadores(), "3-5-2", orders={medio: "central_defender_towards_wing"})


def test_en_los_lados_si_se_puede_fijar() -> None:
    slots = slots_for("3-5-2")
    lado = [i for i, s in enumerate(slots) if s == "central_defender"][0]
    once = best_lineup(_jugadores(), "3-5-2", orders={lado: "central_defender_towards_wing"})
    puesto = next(a.position for a in once.assignments if a.slot == lado)
    assert puesto == "central_defender_towards_wing"


def test_el_optimizador_no_propone_lo_imposible() -> None:
    once = best_lineup(_jugadores(), "3-5-2")
    slots = slots_for("3-5-2")
    for a in once.assignments:
        assert a.position in variantes_de_casilla(slots, a.slot), (
            f"casilla {a.slot}: {a.position} no cabe ahi"
        )
