"""El recorrido de la escalera, que es donde se gastan las llamadas.

Cada escalón es una llamada al mercado y la escalera son catorce, así que lo
que se vigila aquí es el GASTO, no el precio: que no se llame si lo guardado
bastaba, que se pare en cuanto hay seis, que se pare al final de un escalón y
no a mitad de página, y que un mercado que devuelve siempre lo mismo no se
quede dando vueltas.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from app.application.queries.mercado_comparable import buscar_comparables
from app.domain.engines.mercado_comparable import (
    ESCALERA,
    MINIMO_DE_COMPARABLES,
    ORDEN_DE_DESEMPATE,
    Objetivo,
    Ventana,
    objetivo_de,
)

#: Un instante fijo y un plazo que cierra dentro: las pruebas de aqui miden el
#: GASTO del recorrido, no la regla de las 24 horas, que tiene las suyas.
AHORA = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
CIERRA_YA = "2026-10-05 20:00:00"

EDAD = 24


def _hab(**niveles: int) -> dict[str, int]:
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 1)
    base.update(niveles)
    return base


SKILLS = _hab(scoring=18, passing=13, playmaking=7)


def _objetivo() -> Objetivo:
    hecho = objetivo_de(777, EDAD, SKILLS)
    assert hecho is not None
    return hecho


def _fila(
    ident: int, *, puja: int = 4_000_000, passing: int = 13, scoring: int = 18
) -> dict[str, Any]:
    return {
        "ht_player_id": ident,
        "first_name": "Jugador",
        "last_name": str(ident),
        "age_years": EDAD,
        "asking_price": puja,
        "highest_bid": puja,
        "has_bids": puja > 0,
        "injury_level": -1,
        "deadline": CIERRA_YA,
        "tsi": 150_000,
        "specialty": 0,
        "seller_team_name": "Equipo Ajeno",
        "seller_league_id": 92,
        "skills": _hab(scoring=scoring, passing=passing, playmaking=7),
    }


def _seis(desde: int = 1) -> list[dict[str, Any]]:
    return [_fila(ident) for ident in range(desde, desde + MINIMO_DE_COMPARABLES)]


class _Mercado:
    """Un mercado de mentira que apunta qué se le pidió y en qué orden."""

    def __init__(self, *paginas: list[dict[str, Any]]) -> None:
        self.paginas = list(paginas)
        self.pedidas: list[Ventana] = []

    async def __call__(self, ventana: Ventana) -> list[dict[str, Any]]:
        self.pedidas.append(ventana)
        indice = len(self.pedidas) - 1
        return self.paginas[indice] if indice < len(self.paginas) else []


async def test_si_lo_guardado_ya_basta_no_se_llama_al_mercado() -> None:
    """La economía que importa: con la plantilla entera, los mercados de
    jugadores parecidos se solapan y la mayoría de las semanas no hace falta
    pedir nada nuevo."""
    mercado = _Mercado()
    resultado = await buscar_comparables(_objetivo(), mercado, guardadas=_seis(), ahora=AHORA)
    assert resultado.busquedas == 0
    assert mercado.pedidas == []
    assert resultado.estimacion.suficiente is True
    assert resultado.estimacion.precio == 4_000_000
    assert resultado.agotada is False


async def test_con_seis_en_el_primer_escalon_se_gasta_una_sola_llamada() -> None:
    mercado = _Mercado(_seis())
    resultado = await buscar_comparables(_objetivo(), mercado, ahora=AHORA)
    assert resultado.busquedas == 1
    assert resultado.estimacion.peso_minimo == 100
    assert [c.peso for c in resultado.estimacion.comparables] == [100] * 6


async def test_se_para_en_el_escalon_que_reune_el_minimo() -> None:
    """Dos en el exacto, tres en el de 95 y el sexto en el de 90: tres
    llamadas y ni una más, aunque la escalera tenga quince escalones."""
    mercado = _Mercado(
        [_fila(1), _fila(2)],
        [_fila(3, passing=12), _fila(4, passing=12), _fila(5, passing=12)],
        [_fila(6, scoring=17)],
        _seis(100),  # este escalón no debería pedirse nunca
    )
    resultado = await buscar_comparables(_objetivo(), mercado, ahora=AHORA)
    assert resultado.busquedas == 3
    assert resultado.estimacion.n == MINIMO_DE_COMPARABLES
    assert [c.peso for c in resultado.estimacion.comparables] == [100, 100, 95, 95, 95, 90]
    assert resultado.agotada is False


async def test_las_ventanas_se_piden_en_el_orden_de_la_escalera() -> None:
    """Y cada una pide niveles EXACTOS, un escalón por eje."""
    mercado = _Mercado([_fila(1)], [_fila(2)], _seis(10))
    await buscar_comparables(_objetivo(), mercado, ahora=AHORA)
    assert [ventana.peso for ventana in mercado.pedidas] == [100, 95, 90]
    exacta, secundaria_abajo, primaria_abajo = mercado.pedidas
    assert (exacta.primaria.minimo, exacta.secundaria.minimo) == (18, 13)
    assert (secundaria_abajo.primaria.minimo, secundaria_abajo.secundaria.minimo) == (18, 12)
    assert (primaria_abajo.primaria.minimo, primaria_abajo.secundaria.minimo) == (17, 13)
    assert exacta.edad_minima == exacta.edad_maxima == EDAD


async def test_el_escalon_entero_entra_aunque_pase_del_minimo() -> None:
    """Nadie se queda fuera por orden de llegada: si el escalón que cierra la
    cuenta trae ocho, entran los ocho."""
    mercado = _Mercado([_fila(ident) for ident in range(1, 9)])
    resultado = await buscar_comparables(_objetivo(), mercado, ahora=AHORA)
    assert resultado.busquedas == 1
    assert resultado.estimacion.n == 8


async def test_un_mercado_vacio_agota_la_escalera_y_no_da_precio() -> None:
    """La pantalla dirá «no hay mercado comparable esta semana»: eso no es un
    error, es la respuesta."""
    mercado = _Mercado()
    resultado = await buscar_comparables(_objetivo(), mercado, ahora=AHORA)
    assert resultado.busquedas == len(ESCALERA)
    assert resultado.agotada is True
    assert resultado.estimacion.suficiente is False
    assert resultado.estimacion.precio is None
    assert resultado.estimacion.n == 0


async def test_un_mercado_que_devuelve_siempre_lo_mismo_no_se_queda_dando_vueltas() -> None:
    """Catorce escalones devolviendo al mismo jugador no son catorce
    comparables: se gasta la escalera, se cuenta uno y se dice que no hay
    precio."""
    repetido = [_fila(1)]
    mercado = _Mercado(*([repetido] * len(ESCALERA)))
    resultado = await buscar_comparables(_objetivo(), mercado, ahora=AHORA)
    assert resultado.busquedas == len(ESCALERA)
    assert resultado.estimacion.n == 1
    assert resultado.estimacion.suficiente is False


async def test_lo_guardado_cuenta_y_ahorra_escalones() -> None:
    """Cinco guardados y uno nuevo: una sola llamada en vez de tres."""
    mercado = _Mercado([_fila(99)])
    resultado = await buscar_comparables(
        _objetivo(), mercado, guardadas=_seis()[: MINIMO_DE_COMPARABLES - 1], ahora=AHORA
    )
    assert resultado.busquedas == 1
    assert resultado.estimacion.n == MINIMO_DE_COMPARABLES


async def test_lo_guardado_que_no_se_parece_no_ahorra_nada() -> None:
    """Las filas guardadas son de la semana entera, no de este jugador: la
    mayoría serán de otros y hay que filtrarlas igual."""
    ajenos = [
        {
            "ht_player_id": 500 + i,
            "age_years": EDAD,
            "highest_bid": 1_000_000,
            "has_bids": True,
            "injury_level": -1,
            "skills": _hab(keeper=15, defending=9),
        }
        for i in range(20)
    ]
    mercado = _Mercado(_seis())
    resultado = await buscar_comparables(_objetivo(), mercado, guardadas=ajenos, ahora=AHORA)
    assert resultado.busquedas == 1
    assert resultado.estimacion.n == MINIMO_DE_COMPARABLES


async def test_si_el_mercado_falla_la_excepcion_sube() -> None:
    """Media escalera recorrida daría un precio peor que el que toca, y darlo
    sin avisar es lo que este módulo no debe hacer."""

    async def roto(ventana: Ventana) -> list[dict[str, Any]]:
        raise TimeoutError("el mercado no contesta")

    with pytest.raises(TimeoutError):
        await buscar_comparables(_objetivo(), roto, ahora=AHORA)
