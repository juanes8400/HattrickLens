"""Traducir una ventana del motor de comparables a una búsqueda de verdad.

DE DÓNDE SALEN ESTOS NOMBRES. El esquema que hay en `docs/chpp-reference`
describe la RESPUESTA del fichero del mercado, no la petición, así que los
nombres de los parámetros no estaban en el repo. Salen de la librería pública
`pychpp` y se comprobaron contra el servidor el 2026-10-04 con una llamada
hecha a propósito para que delatara un error: se pidió anotación 18 exacta en
jugadores de 31 años y volvieron seis, los seis con anotación 18. Si
`skillType` hubiera usado otra numeración, el 18 habría caído en otra
habilidad. Los números son LOS MISMOS que los de `trainingevents`, que el repo
ya tenía mapeados en `app/config/training.yaml`.

LA REGLA QUE NO ESTABA ESCRITA EN NINGUNA PARTE, y que se descubrió probando
contra el mercado real el 2026-10-05: **el primer filtro de habilidad no
admite un tramo de más de cuatro niveles**. Pedir anotación 16-19 funciona;
pedir 16-20 o 15-19 devuelve

    Invalid parameter specified (10) Additional Info: No primary skill with
    min and max range has been specified

Los otros filtros (`skillType2`, `skillType3`) sí aceptan tramos anchos: en la
misma prueba, pases 11-15 y creación 3-11 pasaron sin problema. Hattrick
quiere una habilidad «principal» acotada que haga barata la búsqueda, y el
resto son refinamientos.

El troceado que hay más abajo existe por esa regla. Con la escalera actual no
llega a saltar nunca, porque lo más que se abre la primaria es un nivel a cada
lado, o sea un tramo de tres; se queda como red, para que ninguna escalera
futura pueda pedir un tramo que el servidor rechace sin que nadie se entere.

Se gastan TRES de los cuatro filtros: la primaria, la secundaria y la
terciaria. Queda uno libre por si algún día hacen falta los topes que el
buscador del propio Hattrick le pone a las habilidades que no son la terna.

LO QUE LA BÚSQUEDA SIGUE SIN SABER HACER, y por eso se filtra en casa:

· No se puede pedir «sólo los que tienen puja». Vienen todos, y los que nadie
  quiso se descartan después. En la prueba real fue el filtro más sangriento,
  con diferencia: de 52 resultados, 4 tenían puja.
· No se puede pedir una TERNA. Se piden habilidades con sus tramos, pero un
  jugador que tenga esos niveles y un cuarto más alto encaja en la búsqueda y
  no se parece en nada; de eso se encarga `peso_de`.
"""

from __future__ import annotations

from typing import Any

from app.domain.engines.mercado_comparable import Franja, Ventana
from app.infrastructure.chpp.client import CHPPClient

#: Los mismos números que `skill_id_map` de `app/config/training.yaml`, que
#: vienen de `trainingevents` y están contrastados con la tabla oficial de
#: traducciones. Se repiten aquí en vez de leer el YAML porque esto es la
#: frontera con una API externa: si algún día uno de los dos usos cambiara,
#: tienen que poder divergir sin arrastrarse.
ID_DE_HABILIDAD: dict[str, int] = {
    "keeper": 1,
    "stamina": 2,
    "set_pieces": 3,
    "defending": 4,
    "scoring": 5,
    "winger": 6,
    "passing": 7,
    "playmaking": 8,
}

#: La versión del fichero que trae la puja más alta y el equipo pujador.
VERSION = "1.1"

#: Niveles que admite como mucho el PRIMER filtro. Cuatro, comprobado contra
#: el servidor: 16-19 pasa y 16-20 no.
TRAMO_MAXIMO_DEL_PRIMERO = 4

#: Resultados por página. El fichero dice -1 cuando hay más de 100, así que
#: por encima de cien ya no se sabe cuántos faltan.
PAGINA = 100


class BusquedaRechazadaError(RuntimeError):
    """Hattrick contestó, pero diciendo que no.

    Tiene clase propia porque el daño de confundirlo con «no hay nadie» es
    justo el que este módulo existe para evitar.
    """


def _trozos(franja: Franja) -> list[tuple[int, int]]:
    """Parte un tramo en pedazos que quepan en el primer filtro."""
    pedazos = []
    desde = franja.minimo
    while desde <= franja.maximo:
        hasta = min(desde + TRAMO_MAXIMO_DEL_PRIMERO - 1, franja.maximo)
        pedazos.append((desde, hasta))
        desde = hasta + 1
    return pedazos


def peticiones_de(ventana: Ventana, *, pagina: int = 0) -> list[dict[str, int]]:
    """Las peticiones que hacen falta para cubrir una ventana entera.

    Suele ser una. Son varias cuando la primaria se abrió más de lo que cabe
    en un solo filtro. La edad va en años cumplidos, sin días: el motor
    compara años, y pedir días estrecharía la búsqueda por un criterio que
    luego nadie aplica.
    """
    comunes: dict[str, int] = {
        "ageMin": ventana.edad_minima,
        "ageMax": ventana.edad_maxima,
        "pageIndex": pagina,
        "pageSize": PAGINA,
        "skillType1": ID_DE_HABILIDAD[ventana.primaria.habilidad],
    }
    for numero, franja in enumerate((ventana.secundaria, ventana.terciaria), start=2):
        comunes[f"skillType{numero}"] = ID_DE_HABILIDAD[franja.habilidad]
        comunes[f"minSkillValue{numero}"] = franja.minimo
        comunes[f"maxSkillValue{numero}"] = franja.maximo

    return [
        {**comunes, "minSkillValue1": desde, "maxSkillValue1": hasta}
        for desde, hasta in _trozos(ventana.primaria)
    ]


class BuscadorDeMercado:
    """Un `Buscador` de verdad, con sus trozos y sus páginas.

    Se le pasa a `buscar_comparables`. Lleva la cuenta de lo que gasta, que es
    lo que de verdad hay que vigilar: la cuota de CHPP es de la aplicación
    entera, no de cada manager.
    """

    def __init__(self, cliente: CHPPClient, *, maximo_de_paginas: int = 2) -> None:
        self._cliente = cliente
        self._maximo_de_paginas = maximo_de_paginas
        #: Peticiones hechas, trozos y páginas incluidos.
        self.peticiones = 0
        #: Ventanas en las que había más resultados de los que se trajeron.
        self.truncadas: list[Ventana] = []

    async def __call__(self, ventana: Ventana) -> list[dict[str, Any]]:
        filas: list[dict[str, Any]] = []
        for base in peticiones_de(ventana):
            filas.extend(await self._un_trozo(ventana, base))
        return filas

    async def _un_trozo(self, ventana: Ventana, base: dict[str, int]) -> list[dict[str, Any]]:
        filas: list[dict[str, Any]] = []
        for pagina in range(self._maximo_de_paginas):
            datos = await self._cliente.fetch(
                "transfersearch", version=VERSION, **{**base, "pageIndex": pagina}
            )
            self.peticiones += 1
            if datos.get("error"):
                raise BusquedaRechazadaError(f"{datos['error']} | pedido: {base}")
            filas.extend(datos["results"])
            total = int(datos.get("item_count", 0))
            # -1 es «más de 100»: nunca es una señal de haber acabado.
            if not datos["results"] or (0 <= total <= (pagina + 1) * PAGINA):
                return filas
        self.truncadas.append(ventana)
        return filas
