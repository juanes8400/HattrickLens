"""Cuándo buscar una reventa, y en qué orden mirar.

2026-08-24, diseñado con el usuario. La vigilancia de reventas es cara —una
llamada a CHPP por ex-jugador— y estaba ciega: 218 en cola y casi todas las
llamadas gastadas en semanas donde no había nada que encontrar.

Dos ideas, y las dos vienen de él:

1. **El dinero dice cuándo.** `IncomeSoldPlayersCommission` viene en línea
   propia en `economy.xml`, separada de las ventas del club, y ya se
   descarga en cada sync. Si sube, alguien revendió a un ex-jugador nuestro.
   No dice quién, pero convierte una patrulla en una persecución.

2. **La alternancia dice en qué orden.** Uno reciente, uno al azar, otro
   reciente, otro al azar… Lo reciente rinde más —quien lleva cuatro años en
   la cola sin que lo revendan lleva cuatro años demostrando que su
   probabilidad semanal es baja— pero el azar impide que la cola larga muera
   de hambre.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Comisiones:
    """Las dos cifras de comisión que trae `economy.xml`."""

    en_curso: int
    semana_cerrada: int


@dataclass(frozen=True)
class Vigilancia:
    """Lo que sabíamos la última vez que se miró."""

    vista_en_curso: int
    vista_cerrada: int
    cazando: bool


@dataclass(frozen=True)
class Decision:
    cazando: bool
    vista_en_curso: int
    vista_cerrada: int
    #: Sólo cierto cuando la cacería ARRANCA en esta pasada: es la señal para
    #: vaciar la lista de a quién ya se probó.
    empieza: bool


def revisar_el_dinero(antes: Vigilancia, ahora: Comisiones) -> Decision:
    """¿Ha entrado comisión nueva desde la última vez?

    El caso que obliga a mirar las dos cifras: si no sincronizas durante una
    semana entera, la de «en curso» ya se reinició a cero y el dinero sólo
    queda en la de «semana cerrada». Mirando sólo la primera, esa comisión no
    se vería nunca.
    """
    vista_en_curso = antes.vista_en_curso
    vista_cerrada = antes.vista_cerrada
    empieza = False

    if ahora.semana_cerrada != vista_cerrada:
        # Cambió la semana. Si lo que se cerró es más de lo que llegamos a
        # ver mientras corría, hubo dinero que se nos escapó.
        if ahora.semana_cerrada > vista_en_curso:
            empieza = True
        vista_cerrada = ahora.semana_cerrada
        # La cifra en curso vuelve a empezar; si no se reinicia aquí, la
        # comisión de la semana siguiente tendría que superar a la de ésta
        # para notarse.
        vista_en_curso = 0

    if ahora.en_curso > vista_en_curso:
        empieza = True
        vista_en_curso = ahora.en_curso

    return Decision(
        cazando=antes.cazando or empieza,
        vista_en_curso=vista_en_curso,
        vista_cerrada=vista_cerrada,
        empieza=empieza,
    )


def orden_de_busqueda(
    por_recencia: list[int],
    ya_probados: set[int],
    cuantos: int,
    *,
    azar: random.Random | None = None,
    empezar_por_reciente: bool = True,
) -> list[int]:
    """Uno reciente, uno al azar, otro reciente, otro al azar…

    `por_recencia` viene ordenada del movimiento más reciente al más
    antiguo. Los ya probados EN ESTA CACERÍA no se repiten; la lista se vacía
    al abrir una nueva, porque si no la mitad aleatoria se agotaría tras el
    primer barrido y no volvería a mirar a nadie.

    `empezar_por_reciente` existe porque el botón trabaja de a un jugador por
    pulsación: si cada llamada empezara siempre por la cabeza, nunca le
    tocaría el turno al azar. Quien llama lo deduce de cuántos lleva
    probados —par, toca reciente; impar, toca azar— y así la alternancia
    sobrevive entre pulsaciones sin guardar nada más.
    """
    # `random` a secas y no `secrets`: esto reparte turnos de busqueda, no
    # protege nada. Que sea predecible no le da ventaja a nadie.
    rnd = azar or random.Random()  # noqa: S311
    quedan = [x for x in por_recencia if x not in ya_probados]
    if not quedan:
        return []

    elegidos: list[int] = []
    # La cola de recientes se consume por la cabeza; el azar, de lo que
    # quede una vez descontado lo ya elegido en esta misma tanda.
    pendientes = list(quedan)
    toca_reciente = empezar_por_reciente
    while pendientes and len(elegidos) < cuantos:
        elegido = pendientes[0] if toca_reciente else rnd.choice(pendientes)
        pendientes.remove(elegido)
        elegidos.append(elegido)
        toca_reciente = not toca_reciente
    return elegidos
