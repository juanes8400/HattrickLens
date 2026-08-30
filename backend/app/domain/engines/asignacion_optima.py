"""Asignación óptima: repartir N sillas entre M candidatos, lo mejor posible.

2026-08-26. Hace falta para «Individual»: la ruleta de un canterano depende
del PUESTO, así que colocar el once no es ordenar una cola sino emparejar
jugadores con plazas, y el emparejamiento bueno no se obtiene eligiendo la
mejor pareja una y otra vez.

El contraejemplo que obliga a hacerlo bien:

    plaza:          portero   central
    Ana                  10         9
    Bruno                 8         0

Por turnos se coge lo mejor primero --Ana al portero, 10-- y a Bruno le queda
el central, 0. Total 10. El óptimo es Ana al central (9) y Bruno al portero
(8): total 17. Casi el doble, y con dos filas.

Implementa el método húngaro por caminos aumentantes con potenciales
(O(n²m)). Se escribe a mano a propósito: `scipy.optimize.linear_sum_assignment`
haría lo mismo, pero traer SciPy entero --y sus binarios-- para una matriz de
18×11 no sale a cuenta.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar

F = TypeVar("F")
C = TypeVar("C")

#: Nada que repartir vale un poco menos que cero para que el algoritmo no
#: prefiera una silla vacía a una que da cero: no cambia el total, pero deja
#: la asignación estable entre llamadas.
_SIN_VALOR = 0.0


# noqa en UP047: la sintaxis nueva de genericos (`def f[F, C]()`) NO resuelve
# con `get_type_hints` en Python 3.12, que es la version de CI y del
# despliegue. Ya rompio un despliegue el 2026-08-26; en local (3.14) pasa.
def asignacion_maxima(  # noqa: UP047
    filas: Sequence[F],
    columnas: Sequence[C],
    valor: Callable[[F, C], float],
) -> list[tuple[F, C]]:
    """Empareja cada columna con una fila distinta, maximizando la suma.

    `columnas` son las plazas a llenar y `filas` los candidatos; puede haber
    más candidatos que plazas --lo normal-- y entonces sobran los peores.

    Devuelve los pares en el orden de `columnas`. Las parejas de valor cero se
    incluyen igual: una plaza sin nadie no es lo mismo que una plaza con
    alguien que no aprovecha, y quien llama decide qué hacer con eso.

    El desempate es por el orden de entrada, así que dos llamadas con los
    mismos datos dan el mismo once --sin esto la pantalla bailaría entre
    recargas--.
    """
    n_filas, n_col = len(filas), len(columnas)
    if n_filas == 0 or n_col == 0:
        return []

    # TRASPUESTA A PROPOSITO. `_hungaro` exige que no haya mas filas que
    # columnas, y el caso real es justo el contrario: dieciocho canteranos
    # para once sillas. Pasandole las PLAZAS como filas y los CANDIDATOS como
    # columnas la condicion se cumple sola y sobran candidatos, que es lo que
    # queremos. Puesto al derecho se queda en BUCLE INFINITO --comprobado el
    # 2026-08-26: colgo la suite diez minutos--.
    #
    # Si aun asi faltan candidatos --menos chicos que sillas-- se rellena con
    # columnas de valor nulo, que al final se descartan y dejan la plaza vacia.
    ancho = max(n_filas, n_col)
    coste = [
        [(-float(valor(filas[i], c)) if i < n_filas else _SIN_VALOR) for i in range(ancho)]
        for c in columnas
    ]

    # `_hungaro` minimiza y contesta POR COLUMNA --candidato-> plaza--, asi que
    # se le da la vuelta al mapa.
    de_candidato = _hungaro(coste, n_col, ancho)

    de_plaza: dict[int, int] = {}
    for i, plaza in enumerate(de_candidato):
        if plaza is not None and i < n_filas:
            de_plaza[plaza] = i

    return [(filas[de_plaza[j]], c) for j, c in enumerate(columnas) if j in de_plaza]


def _hungaro(coste: list[list[float]], n: int, m: int) -> list[int | None]:
    """Húngaro clásico con potenciales. Devuelve, por columna, su fila.

    Es la versión de e-maxx: una columna ficticia hace de raíz y en cada
    ronda se añade una fila. `u` y `v` son los potenciales; `camino` guarda el
    árbol para poder deshacer el emparejamiento al aumentar.

    Los índices van desplazados en uno --el 0 es el centinela-- que es lo que
    hace la implementación corta y lo que la hace fácil de leer mal. No
    tocarla sin las pruebas delante.
    """
    infinito = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (m + 1)
    columna_de = [0] * (m + 1)  # columna -> fila (1-based, 0 = libre)
    camino = [0] * (m + 1)

    for fila in range(1, n + 1):
        columna_de[0] = fila
        j0 = 0
        mejor = [infinito] * (m + 1)
        usada = [False] * (m + 1)
        while True:
            usada[j0] = True
            i0 = columna_de[j0]
            delta = infinito
            j1 = 0
            for j in range(1, m + 1):
                if usada[j]:
                    continue
                actual = coste[i0 - 1][j - 1] - u[i0] - v[j]
                if actual < mejor[j]:
                    mejor[j] = actual
                    camino[j] = j0
                if mejor[j] < delta:
                    delta = mejor[j]
                    j1 = j
            for j in range(m + 1):
                if usada[j]:
                    u[columna_de[j]] += delta
                    v[j] -= delta
                else:
                    mejor[j] -= delta
            j0 = j1
            if columna_de[j0] == 0:
                break
        # Deshace la cadena: cada columna del camino se queda con la fila de
        # la anterior, y la ultima libera su hueco.
        while j0:
            j1 = camino[j0]
            columna_de[j0] = columna_de[j1]
            j0 = j1

    return [columna_de[j] - 1 if columna_de[j] else None for j in range(1, m + 1)]
