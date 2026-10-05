"""Recorrer la escalera de comparables gastando las menos búsquedas posibles.

El motor (`app.domain.engines.mercado_comparable`) sabe quién se parece a
quién y cuánto vale cada parecido. Lo que falta es el recorrido, y el recorrido
tiene un coste: cada escalón es una llamada al mercado, la escalera entera son
catorce, y multiplicado por una plantilla de veinticinco se va a varios
cientos a la semana.

De ahí las dos economías de este módulo:

1. **Lo ya traído se mira primero.** Las filas que la búsqueda devolvió esta
   semana, para éste o para cualquier otro jugador, se filtran en local antes
   de pedir nada. Lo que de verdad ahorra esto es REPETIR al mismo jugador en
   la misma semana, no compartir entre jugadores distintos: medido sobre la
   plantilla real el 2026-10-05, las 351 peticiones que necesitan veinticuatro
   jugadores sólo bajan a 346 al compartirlas, un 1,4%. Con escalones de nivel
   EXACTO dos jugadores tuyos piden la misma búsqueda sólo si coinciden en
   habilidad, nivel y edad, y eso casi nunca pasa. (Con las ventanas anchas
   del diseño anterior el solape era otra cosa; se midió y no lo era tanto.)
2. **Se para en cuanto hay seis.** No se recorre la escalera entera por
   gusto: se abandona en el escalón que reúne el mínimo, y sólo se llega al
   suelo cuando de verdad no hay con quién comparar.

El corte es SIEMPRE al final de un escalón, nunca a mitad de página: si el
sexto y el séptimo se parecen igual, dejar fuera al séptimo por orden de
llegada sería arbitrario.

Qué filtros acepta de verdad la búsqueda del juego es cosa de quien
implemente `Buscador`, y da igual que acepte menos de los que se le piden: la
ventana se vuelve a aplicar en local sobre cada fila, así que una búsqueda que
devuelva de más no mete a nadie que no se parezca.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.engines.mercado_comparable import (
    Estimacion,
    Objetivo,
    Ventana,
    estimar,
    plan_de_busqueda,
    recolectar,
)

#: Lo que tiene que saber hacer quien llame al mercado: recibir una ventana y
#: devolver filas con la forma del parser. Las páginas, los reintentos y el
#: límite de llamadas son suyos.
Buscador = Callable[[Ventana], Awaitable[Sequence[Mapping[str, Any]]]]


@dataclass(frozen=True, slots=True)
class Resultado:
    """El precio y lo que costó sacarlo."""

    estimacion: Estimacion
    #: Cuántas búsquedas se gastaron. Cero significa que lo guardado bastó.
    busquedas: int
    #: Si se llegó al final de la escalera sin reunir el mínimo.
    agotada: bool


async def buscar_comparables(
    objetivo: Objetivo,
    buscar: Buscador,
    *,
    guardadas: Iterable[Mapping[str, Any]] = (),
    ahora: datetime | None = None,
) -> Resultado:
    """Reúne comparables hasta tener suficientes, y devuelve el precio.

    `ahora` decide qué subastas están lo bastante cerca de cerrar como para
    que su puja cuente, y se puede fijar desde fuera; sin él es la hora de
    verdad.

    Si una búsqueda falla, la excepción sube: media escalera recorrida daría
    un precio peor que el que tocaba, y dar un precio peor sin avisar es justo
    lo que este módulo no debe hacer. Quien llame decide si reintenta o si
    deja al jugador sin precio esta semana.
    """
    reunidos = recolectar(objetivo, guardadas, ahora=ahora)
    estimacion = estimar(reunidos)
    busquedas = 0
    agotada = False
    if not estimacion.suficiente:
        plan = plan_de_busqueda(objetivo)
        for ventana in plan:
            filas = await buscar(ventana)
            busquedas += 1
            reunidos = recolectar(objetivo, filas, reunidos, ahora=ahora)
            estimacion = estimar(reunidos)
            if estimacion.suficiente:
                break
        else:
            agotada = True
    return Resultado(estimacion=estimacion, busquedas=busquedas, agotada=agotada)
