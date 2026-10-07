"""Traducir una ventana a una búsqueda de verdad en el mercado.

Esto es la frontera con una API ajena, y tiene una regla que no está escrita en
ningún esquema: **el primer filtro de habilidad no admite un tramo de más de
cuatro niveles**. Se descubrió el 2026-10-05 probando contra el servidor, y se
descubrió TARDE porque el error no se veía: Hattrick contesta 200 con un
`chpperror`, el parser lo convertía en una búsqueda vacía, y cuatro escalones
pasaron por «aquí no hay nadie» cuando lo que había era un rechazo.

Las dos pruebas que importan son por tanto: que ninguna petición se pase del
tramo máximo, y que una búsqueda rechazada se note en vez de parecer vacía.
"""

from typing import Any

import pytest

from app.domain.engines.mercado_comparable import (
    ORDEN_DE_DESEMPATE,
    Franja,
    Objetivo,
    Ventana,
    objetivo_de,
    plan_de_busqueda,
)
from app.infrastructure.chpp.mercado import (
    ID_DE_HABILIDAD,
    PAGINA,
    TRAMO_MAXIMO_DEL_PRIMERO,
    BuscadorDeMercado,
    BusquedaRechazadaError,
    peticiones_de,
)

EDAD = 31


def _hab(**niveles: int) -> dict[str, int]:
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 0)
    base.update(niveles)
    return base


#: Alberto, el delantero con el que se probó todo contra el mercado real.
SKILLS = _hab(scoring=18, passing=13, playmaking=7)


def _objetivo() -> Objetivo:
    hecho = objetivo_de(1, EDAD, SKILLS)
    assert hecho is not None
    return hecho


def _primera() -> Ventana:
    return plan_de_busqueda(_objetivo())[0]


class _ClienteFalso:
    """Un CHPP de mentira que apunta lo que se le pidió."""

    def __init__(self, *respuestas: dict[str, Any]) -> None:
        self.respuestas = list(respuestas)
        self.pedidos: list[dict[str, Any]] = []

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        self.pedidos.append({"file": file, "version": version, **params})
        indice = len(self.pedidos) - 1
        if indice < len(self.respuestas):
            return self.respuestas[indice]
        return {"error": None, "item_count": 0, "page_size": PAGINA, "page_index": 0, "results": []}


def _pagina(item_count: int = 0, cuantos: int = 0) -> dict[str, Any]:
    return {
        "error": None,
        "item_count": item_count,
        "page_size": PAGINA,
        "page_index": 0,
        "results": [{"ht_player_id": n} for n in range(cuantos)],
    }


# --------------------------------------------------------------------------
# La regla del tramo máximo
# --------------------------------------------------------------------------


def test_ninguna_peticion_de_la_escalera_se_pasa_del_tramo_maximo() -> None:
    """LA prueba de este fichero.

    Hattrick rechaza con «No primary skill with min and max range has been
    specified» cualquier primer filtro de más de cuatro niveles, y el rechazo
    llega disfrazado de búsqueda vacía.
    """
    for ventana in plan_de_busqueda(_objetivo()):
        for pedido in peticiones_de(ventana):
            ancho = pedido["maxSkillValue1"] - pedido["minSkillValue1"] + 1
            assert ancho <= TRAMO_MAXIMO_DEL_PRIMERO, (ventana.peso, pedido)


def test_la_escalera_de_hoy_no_llega_a_trocear() -> None:
    """Lo más que se abre la primaria es un nivel a cada lado, o sea un tramo
    de tres, y el servidor admite hasta cuatro. El troceado se queda como red
    para cualquier escalera futura."""
    for ventana in plan_de_busqueda(_objetivo()):
        pedidos = peticiones_de(ventana)
        assert len(pedidos) == 1
        assert pedidos[0]["ageMin"] == pedidos[0]["ageMax"]


def test_un_tramo_ancho_se_trocearia_sin_dejar_huecos_ni_repetir() -> None:
    """Se trocea, no se recorta: recortarlo dejaría fuera a gente que el
    escalón sí admite."""
    ancho = Ventana(
        peso=50,
        edad_minima=EDAD,
        edad_maxima=EDAD,
        primaria=Franja("scoring", 10, 20),
        secundaria=Franja("passing", 5, 18),
        terciaria=Franja("playmaking", 2, 12),
    )
    pedidos = peticiones_de(ancho)
    assert len(pedidos) > 1
    cubierto: list[int] = []
    for pedido in pedidos:
        trozo = pedido["maxSkillValue1"] - pedido["minSkillValue1"] + 1
        assert trozo <= TRAMO_MAXIMO_DEL_PRIMERO
        cubierto.extend(range(pedido["minSkillValue1"], pedido["maxSkillValue1"] + 1))
    assert cubierto == list(range(10, 21))
    # Y los otros dos filtros no se trocean: la regla es sólo del primero.
    for pedido in pedidos:
        assert (pedido["minSkillValue2"], pedido["maxSkillValue2"]) == (5, 18)
        assert (pedido["minSkillValue3"], pedido["maxSkillValue3"]) == (2, 12)


# --------------------------------------------------------------------------
# Los parámetros
# --------------------------------------------------------------------------


def test_cada_habilidad_viaja_con_su_numero_de_hattrick() -> None:
    """Comprobado contra el servidor el 2026-10-04: skillType 5 es anotación."""
    assert ID_DE_HABILIDAD["scoring"] == 5
    assert ID_DE_HABILIDAD["passing"] == 7
    assert ID_DE_HABILIDAD["playmaking"] == 8
    pedido = peticiones_de(_primera())[0]
    assert pedido["skillType1"] == 5
    assert pedido["minSkillValue1"] == pedido["maxSkillValue1"] == 18
    assert pedido["skillType2"] == 7
    assert pedido["minSkillValue2"] == pedido["maxSkillValue2"] == 13


def test_la_terciaria_va_siempre_uno_arriba_y_dos_abajo() -> None:
    for ventana in plan_de_busqueda(_objetivo()):
        pedido = peticiones_de(ventana)[0]
        assert pedido["skillType3"] == ID_DE_HABILIDAD["playmaking"]
        assert (pedido["minSkillValue3"], pedido["maxSkillValue3"]) == (5, 8)


def test_queda_un_filtro_libre_de_los_cuatro() -> None:
    """Está ahí por si algún día hacen falta los topes que el buscador del
    propio Hattrick le pone a las habilidades que no son la terna."""
    for ventana in plan_de_busqueda(_objetivo()):
        for pedido in peticiones_de(ventana):
            assert "skillType4" not in pedido


def test_la_edad_viaja_en_anos_cumplidos_y_sin_dias() -> None:
    """Pedir días estrecharía la búsqueda por un criterio que el motor no
    aplica: compara años."""
    pedido = peticiones_de(_primera())[0]
    assert pedido["ageMin"] == pedido["ageMax"] == EDAD
    assert "ageDaysMin" not in pedido
    assert "ageDaysMax" not in pedido


def test_la_escalera_entera_traducida_a_lo_que_sale_por_el_cable() -> None:
    pedidos = [peticiones_de(v)[0] for v in plan_de_busqueda(_objetivo())]
    leido = [
        (
            p["ageMin"],
            p["minSkillValue1"],
            p["maxSkillValue1"],
            p["minSkillValue2"],
            p["maxSkillValue2"],
        )
        for p in pedidos
    ]
    assert leido == [
        (31, 18, 18, 13, 13),
        (31, 18, 18, 12, 14),
        (31, 17, 19, 12, 14),
        (32, 17, 19, 12, 14),
        (30, 17, 19, 12, 14),
    ]


# --------------------------------------------------------------------------
# El buscador
# --------------------------------------------------------------------------


async def test_una_busqueda_rechazada_no_pasa_por_una_busqueda_vacia() -> None:
    """El fallo que costó cuatro escalones: sin esto, un rechazo se cuenta
    como «aquí no hay nadie»."""
    cliente = _ClienteFalso({"error": "Invalid parameter specified (10)", "results": []})
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    with pytest.raises(BusquedaRechazadaError, match="Invalid parameter"):
        await buscador(_primera())


async def test_no_se_pide_una_segunda_pagina_si_ya_vinieron_todos() -> None:
    cliente = _ClienteFalso(_pagina(item_count=2, cuantos=2))
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    await buscador(_primera())
    assert buscador.peticiones == 1


async def test_el_menos_uno_del_recuento_no_se_lee_como_haber_terminado() -> None:
    """-1 es «más de 100». Tratarlo como un recuento dejaría fuera todo lo que
    no cupo en la primera página."""
    cliente = _ClienteFalso(_pagina(item_count=-1, cuantos=3), _pagina(item_count=-1, cuantos=3))
    buscador = BuscadorDeMercado(cliente, maximo_de_paginas=2)  # type: ignore[arg-type]
    filas = await buscador(_primera())
    assert buscador.peticiones == 2
    assert len(filas) == 6
    assert buscador.truncadas  # y queda constancia de que había más


async def test_una_pagina_vacia_corta_aunque_el_recuento_diga_muchos() -> None:
    cliente = _ClienteFalso(_pagina(item_count=-1, cuantos=0))
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    assert await buscador(_primera()) == []
    assert buscador.peticiones == 1
