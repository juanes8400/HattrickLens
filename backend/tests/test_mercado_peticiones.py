"""Traducir una ventana a una búsqueda de verdad en el mercado.

Esto es la frontera con una API ajena, y tiene una regla que no está escrita
en ningún esquema: **el primer filtro de habilidad no admite un tramo de más
de cuatro niveles**. Se descubrió el 2026-10-05 probando contra el servidor,
y se descubrió TARDE porque el error no se veía: Hattrick contesta 200 con un
`chpperror`, el parser lo convertía en una búsqueda vacía, y cuatro escalones
de la escalera pasaron por «aquí no hay nadie» cuando lo que había era un
rechazo.

Las dos pruebas que importan son por tanto:

  · que NINGUNA petición de NINGÚN escalón se pase del tramo máximo, que es la
    que habría atrapado el fallo;
  · que una búsqueda rechazada se note, en vez de parecer una búsqueda vacía.
"""

from typing import Any

import pytest

from app.domain.engines.mercado_comparable import ESCALERA as ESCALERA_TRIO
from app.domain.engines.mercado_comparable import (
    ORDEN_DE_DESEMPATE,
    objetivo_de,
    plan_de_busqueda,
    ventana_de,
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
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 1)
    base.update(niveles)
    return base


#: Alberto, el delantero con el que se probó de verdad.
SKILLS = _hab(scoring=18, passing=13, playmaking=7)


def _objetivo(con_terciaria: bool = True):
    hecho = objetivo_de(1, EDAD, SKILLS, con_terciaria=con_terciaria)
    assert hecho is not None
    return hecho


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


def _vacia(item_count: int = 0, cuantos: int = 0) -> dict[str, Any]:
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


def test_ninguna_peticion_de_ninguna_escalera_se_pasa_del_tramo_maximo() -> None:
    """LA prueba de este fichero.

    Hattrick rechaza con «No primary skill with min and max range has been
    specified» cualquier primer filtro de más de cuatro niveles, y el rechazo
    llega disfrazado de búsqueda vacía. Esto recorre los dos modos enteros y
    comprueba cada petición que se enviaría.
    """
    for con_terciaria in (True, False):
        objetivo = _objetivo(con_terciaria)
        for ventana in plan_de_busqueda(objetivo):
            for pedido in peticiones_de(ventana):
                ancho = pedido["maxSkillValue1"] - pedido["minSkillValue1"] + 1
                assert ancho <= TRAMO_MAXIMO_DEL_PRIMERO, (ventana.peso, pedido)


def test_un_tramo_que_cabe_se_pide_de_una_sola_vez() -> None:
    ventana = ventana_de(_objetivo(), ESCALERA_TRIO[0])
    pedidos = peticiones_de(ventana)
    assert len(pedidos) == 1
    assert pedidos[0]["minSkillValue1"] == pedidos[0]["maxSkillValue1"] == 18


def test_un_tramo_que_no_cabe_se_trocea_sin_dejar_huecos_ni_repetir() -> None:
    """Se trocea, no se recorta: recortarlo sería mentir sobre lo que se
    buscó y dejaría fuera a gente que el escalón sí admite."""
    ancho = ventana_de(_objetivo(), ESCALERA_TRIO[-1])
    pedidos = peticiones_de(ancho)
    assert len(pedidos) > 1
    cubierto: list[int] = []
    for pedido in pedidos:
        cubierto.extend(range(pedido["minSkillValue1"], pedido["maxSkillValue1"] + 1))
    assert cubierto == sorted(cubierto)
    assert len(cubierto) == len(set(cubierto))
    assert cubierto == list(range(ancho.primaria.minimo, ancho.primaria.maximo + 1))


def test_los_filtros_segundo_y_tercero_no_se_trocean() -> None:
    """La regla es sólo del primero: en la prueba real, pases 11-15 y
    creación 3-11 pasaron tal cual."""
    ancho = ventana_de(_objetivo(), ESCALERA_TRIO[-1])
    for pedido in peticiones_de(ancho):
        assert pedido["minSkillValue2"] == ancho.secundaria.minimo
        assert pedido["maxSkillValue2"] == ancho.secundaria.maximo
        assert pedido["maxSkillValue3"] - pedido["minSkillValue3"] > TRAMO_MAXIMO_DEL_PRIMERO


# --------------------------------------------------------------------------
# Los parámetros
# --------------------------------------------------------------------------


def test_cada_habilidad_viaja_con_su_numero_de_hattrick() -> None:
    """Comprobado contra el servidor el 2026-10-04: skillType 5 es anotación."""
    assert ID_DE_HABILIDAD["scoring"] == 5
    assert ID_DE_HABILIDAD["passing"] == 7
    assert ID_DE_HABILIDAD["playmaking"] == 8
    pedido = peticiones_de(ventana_de(_objetivo(), ESCALERA_TRIO[0]))[0]
    assert pedido["skillType1"] == 5
    assert pedido["skillType2"] == 7
    assert pedido["skillType3"] == 8


def test_la_edad_viaja_en_anos_cumplidos_y_sin_dias() -> None:
    """Pedir días estrecharía la búsqueda por un criterio que el motor no
    aplica: compara años."""
    pedido = peticiones_de(ventana_de(_objetivo(), ESCALERA_TRIO[0]))[0]
    assert pedido["ageMin"] == pedido["ageMax"] == EDAD
    assert "ageDaysMin" not in pedido
    assert "ageDaysMax" not in pedido


def test_sin_terciaria_no_se_gasta_el_tercer_filtro() -> None:
    objetivo = _objetivo(con_terciaria=False)
    pedido = peticiones_de(plan_de_busqueda(objetivo)[0])[0]
    assert pedido["skillType1"] == 5
    assert pedido["skillType2"] == 7
    assert "skillType3" not in pedido


# --------------------------------------------------------------------------
# El buscador
# --------------------------------------------------------------------------


async def test_una_busqueda_rechazada_no_pasa_por_una_busqueda_vacia() -> None:
    """El fallo que costó cuatro escalones: sin esto, un rechazo se cuenta
    como «aquí no hay nadie» y el precio sale de menos gente de la que
    había."""
    cliente = _ClienteFalso({"error": "Invalid parameter specified (10)", "results": []})
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    with pytest.raises(BusquedaRechazadaError, match="Invalid parameter"):
        await buscador(ventana_de(_objetivo(), ESCALERA_TRIO[0]))


async def test_se_piden_todos_los_trozos_y_se_juntan_los_resultados() -> None:
    ancho = ventana_de(_objetivo(), ESCALERA_TRIO[-1])
    trozos = len(peticiones_de(ancho))
    cliente = _ClienteFalso(*[_vacia(item_count=1, cuantos=1) for _ in range(trozos)])
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    filas = await buscador(ancho)
    assert buscador.peticiones == trozos
    assert len(filas) == trozos


async def test_no_se_pide_una_segunda_pagina_si_ya_vinieron_todos() -> None:
    cliente = _ClienteFalso(_vacia(item_count=2, cuantos=2))
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    await buscador(ventana_de(_objetivo(), ESCALERA_TRIO[0]))
    assert buscador.peticiones == 1


async def test_el_menos_uno_del_recuento_no_se_lee_como_haber_terminado() -> None:
    """-1 es «más de 100». Tratarlo como un recuento dejaría fuera todo lo que
    no cupo en la primera página."""
    cliente = _ClienteFalso(_vacia(item_count=-1, cuantos=3), _vacia(item_count=-1, cuantos=3))
    buscador = BuscadorDeMercado(cliente, maximo_de_paginas=2)  # type: ignore[arg-type]
    filas = await buscador(ventana_de(_objetivo(), ESCALERA_TRIO[0]))
    assert buscador.peticiones == 2
    assert len(filas) == 6
    assert buscador.truncadas  # y queda constancia de que había más


async def test_una_pagina_vacia_corta_aunque_el_recuento_diga_muchos() -> None:
    cliente = _ClienteFalso(_vacia(item_count=-1, cuantos=0))
    buscador = BuscadorDeMercado(cliente)  # type: ignore[arg-type]
    assert await buscador(ventana_de(_objetivo(), ESCALERA_TRIO[0])) == []
    assert buscador.peticiones == 1
