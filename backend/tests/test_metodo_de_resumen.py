"""Un solo resumen manda en Liga, y dos en Copa.

2026-09-09, pedido del usuario: Liga ofrece los mismos resúmenes que la ficha
de rival, con UN selector para toda la pantalla; Copa hereda los dos selectores
de la ficha --uno por lado--, y del lado propio además la alineación enviada.

2026-09-13, pedido del usuario: la mediana se retira porque enredaba, y el
promedio la absorbe. Quedan cuatro resúmenes, y quien pida "median" en una URL
vieja recibe el promedio en vez de un error.

Lo que se prueba aquí es la plomería, no el motor: que lo elegido llega hasta
el número, que lo imposible se normaliza en vez de reventar, y que la respuesta
dice cuál se usó de verdad. Que cada método calcule lo suyo ya lo prueba
`test_prediccion_engine.py`.
"""

from __future__ import annotations

import asyncio

import pytest

from app.api.v1.endpoints.cup import _metodo_de_copa
from app.api.v1.endpoints.league import _metodo_de_la_pantalla
from app.application.queries.league import LeagueQueryService
from tests.conftest import HT_TEAM_ID
from tests.test_league_matches_academy_queries import _with_league

LOS_CUATRO = ("average", "max", "max_parallel", "last")


@pytest.mark.parametrize("metodo", LOS_CUATRO)
def test_liga_acepta_los_cuatro_resumenes(metodo: str) -> None:
    assert _metodo_de_la_pantalla(metodo) == metodo


@pytest.mark.parametrize("pedido", ["median", "submitted", "mediana", "", "MEDIAN"])
def test_liga_cae_en_el_promedio_ante_cualquier_otra_cosa(pedido: str) -> None:
    """Ni 422 ni pantalla en blanco.

    «median» va primero en la lista y no es un descuido: es la mediana
    retirada el 2026-09-13, y una URL guardada de antes tiene que abrir en
    promedio. «submitted» tampoco es un resumen de esta pantalla: en Liga se
    describen ocho equipos y de siete no se pueden ver las órdenes.
    """
    assert _metodo_de_la_pantalla(pedido) == "average"


@pytest.mark.parametrize("metodo", LOS_CUATRO)
def test_copa_acepta_los_mismos_cuatro(metodo: str) -> None:
    assert _metodo_de_copa(metodo) == metodo


def test_copa_resuelve_la_alineacion_enviada_como_promedio_de_lo_jugado() -> None:
    """En Copa «Alineación enviada» SÍ es una opción, pero no un resumen.

    Es un vector que da Hattrick y que se pega encima de los siete sectores que
    prevé. Los otros dos --las acciones indirectas a balón parado, que Hattrick
    no prevé-- y el caso de que no haya órdenes mandadas se sostienen con el
    promedio de lo ya jugado. Por eso `_metodo_de_copa` la traduce a promedio
    en vez de rechazarla. Y la mediana retirada, igual.
    """
    assert _metodo_de_copa("submitted") == "average"
    assert _metodo_de_copa("median") == "average"


def _lecturas_que_suben() -> dict[int, list[dict[str, float]]]:
    """Un partido flojo, uno normal y uno brillante para cada equipo.

    El equipo propio sube más fuerte que los otros, así que «máximo» tiene que
    subirle la probabilidad de título respecto al promedio, y no sólo moverla.

    CERCA A PROPÓSITO. Con la mediana los tres partidos se leían como el
    flojo y los equipos salían iguales; con el promedio el techo cuenta, y
    un propio de 20-20-90 ya salía campeón al 100 % con los dos resúmenes,
    así que el máximo no tenía por dónde subirlo. Con estos: 95 % contra 97 %.
    """
    campos = (
        "midfield",
        "left_def",
        "central_def",
        "right_def",
        "left_att",
        "central_att",
        "right_att",
        "sp_def",
        "sp_att",
    )

    def tres(base: float, techo: float) -> list[dict[str, float]]:
        return [dict.fromkeys(campos, v) for v in (base, base, techo)]

    return {
        HT_TEAM_ID: tres(20, 24),
        600001: tres(20, 22),
        600002: tres(20, 22),
        600003: tres(20, 22),
    }


def test_el_metodo_llega_hasta_las_predicciones_de_liga() -> None:
    """El selector mueve la Proyección, y el próximo partido del Resumen no.

    Se comprueba con el título --que sale de la simulación-- y con el próximo
    partido, porque desde el 2026-09-12 son dos preguntas distintas: la
    Proyección resume ocho equipos con un solo criterio, y el Resumen
    pronostica UN partido con una alineación concreta por lado.
    """

    async def go(metodo: str):
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(
                team_id, runs=4000, lecturas=_lecturas_que_suben(), metodo=metodo
            )

    con_promedio = asyncio.run(go("average"))
    con_maximo = asyncio.run(go("max"))
    assert con_promedio is not None and con_maximo is not None

    # La respuesta dice con qué salió, para que el selector marque lo real.
    assert con_promedio.pitch_zone_method == "average"
    assert con_maximo.pitch_zone_method == "max"

    propio_promedio = next(o for o in con_promedio.outlook if o.is_own_team)
    propio_maximo = next(o for o in con_maximo.outlook if o.is_own_team)
    # Con el máximo, el equipo propio juega con su mejor registro (24) contra
    # el de unos rivales que apenas mejoran: tiene que salir mejor parado.
    assert propio_maximo.title_probability > propio_promedio.title_probability

    # Y el próximo partido del Resumen NO se mueve con él. Si un día volviera a
    # colgar del selector, esto lo cazaría.
    assert con_promedio.next_match is not None
    assert con_maximo.next_match is not None
    assert con_maximo.next_match == con_promedio.next_match
    assert con_promedio.next_match["sources"]["own"]["kind"] == "last"


def test_liga_abre_en_promedio_si_no_se_pide_nada() -> None:
    """El defecto de la consulta es el promedio, no un resumen retirado."""

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=1000)

    d = asyncio.run(go())
    assert d is not None
    assert d.pitch_zone_method == "average"


def test_liga_sin_lecturas_sigue_saliendo_con_cualquier_metodo() -> None:
    """Sin ratings no hay modelo de zonas, y eso no es un error.

    Es lo que pasa la primera vez que alguien abre Liga sin haber
    sincronizado. El selector no puede convertir esa pantalla en un fallo.
    """

    async def go():
        factory, team_id = await _with_league()
        async with factory() as s:
            return await LeagueQueryService(s).get(team_id, runs=1000, metodo="max_parallel")

    d = asyncio.run(go())
    assert d is not None
    assert d.pitch_zone_method == "max_parallel"
    assert d.standings
