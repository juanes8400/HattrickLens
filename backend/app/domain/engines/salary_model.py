"""Estimar el sueldo de un jugador del que nadie lo anotó.

EL PROBLEMA
-----------
De los cinco componentes del saldo de una transferencia, Hattrick publica
cuatro para siempre --precio de compra, de venta, comisión del agente y coste
de los listados-- y el quinto sólo existe si alguien lo anotó mientras el
jugador estaba en el club. No hay ningún fichero que diga cuánto cobraba
alguien en 2018.

En Pulgas Arrechas eso son 515 etapas de 599 con el sueldo a cero por
ignorancia. Contarlo como cero es equivocarse el 100%: el saldo sale mejor de
lo que fue, y cuanto más tiempo estuvo el jugador, peor.

EL MÉTODO
---------
En Hattrick el sueldo sale de las habilidades, y el TSI también. Así que hay
una relación aprovechable, y se ajusta con las lecturas del PROPIO club --las
semanas en las que sí se anotaron TSI y sueldo a la vez-- en vez de con una
fórmula traída de fuera:

    log(sueldo) = a + b·log(TSI) + c·edad

Medido sobre las 1.134 lecturas de Pulgas Arrechas el 2026-09-04:

    curva sola ................ error mediano 28,7 %
    curva + ancla del jugador .. error mediano  5,9 %
    contarlo como cero ........ error          100 %

LA EDAD
-------
Sola no explica nada (R² 0,03): dos jugadores con las mismas habilidades
cobran igual tengan 18 o 30 años. Pero como corrección al TSI baja el error de
33,9 % a 28,7 %, porque a igual TSI un jugador mayor tiene otras habilidades.

EL ANCLA
--------
Cada jugador se sienta a una distancia ESTABLE de la curva: su sesgo personal
resultó ser 8,2 veces mayor que su propio ruido. La curva acierta la forma y
falla el nivel, y ese nivel no se mueve. Por eso una sola lectura suya --la
que rescata el relleno de fichas de ex-jugadores-- reconstruye su etapa entera
al 5,9 % en vez de al 28,7 %.

LO QUE NO SÉ
------------
La curva se ajusta con lecturas de la plantilla de HOY y se aplica a ventas de
hace once años. Dos riesgos, y sólo uno se pudo medir:

- El rango de TSI SÍ encaja: 483 de los 485 ex-jugadores caen dentro del rango
  con el que se ajustó la curva (medido 2026-09-04), así que se interpola, no
  se extrapola. Ese era el riesgo que más asustaba y resultó no serlo.
- Si Hattrick ha tocado la fórmula de sueldos desde 2015, no hay forma de
  saberlo desde aquí, y una venta de esa época se estimaría con la curva
  equivocada. Este sigue abierto.

El 28,7 % es el error DENTRO de los datos; fuera será peor y no sé cuánto. Por
eso cada cifra estimada viaja marcada y nunca se suma con las observadas sin
decirlo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Por debajo de esto no se ajusta nada. Con 26 lecturas el error ya es el
#: mismo que con 200 (30,4 % contra 29,1 %), así que el mínimo no busca
#: precisión sino evitar ajustar una recta a cuatro puntos: la primera
#: sincronización de cualquiera trae ya unas 25 lecturas de su plantilla.
MINIMO_DE_LECTURAS = 12

#: Sin variación de TSI la pendiente no se puede estimar y el ajuste
#: degeneraría en una constante disfrazada de modelo.
MINIMA_VARIACION_LOG_TSI = 0.05


@dataclass(frozen=True)
class LecturaDeSueldo:
    """Una semana en la que se conocen a la vez el TSI, la edad y el sueldo."""

    tsi: int
    edad: float
    salario: int


@dataclass(frozen=True)
class ModeloDeSueldo:
    """La curva ajustada, lista para estimar."""

    a: float
    b: float
    c: float
    lecturas: int

    def estimar(self, tsi: int | None, edad: float | None, ancla: float = 0.0) -> int | None:
        """El sueldo que le correspondería a ese TSI y esa edad.

        `ancla` es el sesgo personal del jugador en escala logarítmica, que
        sale de comparar una lectura suya con lo que la curva predecía. Sin
        ella la estimación es la de la curva.
        """
        if not tsi or tsi <= 0:
            return None
        exponente = self.a + self.b * math.log(tsi) + self.c * (edad or 0.0) + ancla
        # Un exponente disparado daría un sueldo absurdo antes que un error.
        if exponente > 30:
            return None
        return max(0, round(math.exp(exponente)))

    def ancla_de(self, lectura: LecturaDeSueldo) -> float | None:
        """Cuánto se separa este jugador de la curva, en logaritmo.

        Es la diferencia que se le suma a todas sus estimaciones. Constante a
        lo largo de su carrera, que es lo que la hace útil.
        """
        if lectura.tsi <= 0 or lectura.salario <= 0:
            return None
        predicho = self.a + self.b * math.log(lectura.tsi) + self.c * lectura.edad
        return math.log(lectura.salario) - predicho


def ajustar(lecturas: list[LecturaDeSueldo]) -> ModeloDeSueldo | None:
    """Mínimos cuadrados sobre log(sueldo) ~ 1 + log(TSI) + edad.

    Se resuelven las ecuaciones normales a mano --es una matriz 3x3-- para que
    el dominio no dependa de nadie. Devuelve `None` cuando no hay material
    suficiente, que es la respuesta honesta: mejor sin estimación que con una
    ajustada a cuatro puntos.
    """
    utiles = [x for x in lecturas if x.tsi > 0 and x.salario > 0]
    if len(utiles) < MINIMO_DE_LECTURAS:
        return None

    xs = [math.log(x.tsi) for x in utiles]
    media_x = sum(xs) / len(xs)
    if max(xs) - min(xs) < MINIMA_VARIACION_LOG_TSI:
        return None

    filas = [(1.0, x, u.edad, math.log(u.salario)) for x, u in zip(xs, utiles, strict=True)]
    # Normales: (XᵀX)·β = Xᵀy, con X = [1, log(tsi), edad].
    xtx = [[sum(f[i] * f[j] for f in filas) for j in range(3)] for i in range(3)]
    xty = [sum(f[i] * f[3] for f in filas) for i in range(3)]
    beta = _resolver(xtx, xty)
    if beta is None:
        # Sistema singular: pasa si todas las edades son idénticas. Se
        # reintenta sin el término de edad, que sigue valiendo (33,9 % de
        # error en vez de 28,7 %).
        xtx2 = [[sum(f[i] * f[j] for f in filas) for j in range(2)] for i in range(2)]
        xty2 = [sum(f[i] * f[3] for f in filas) for i in range(2)]
        beta2 = _resolver(xtx2, xty2)
        if beta2 is None:
            return None
        return ModeloDeSueldo(a=beta2[0], b=beta2[1], c=0.0, lecturas=len(utiles))
    _ = media_x
    return ModeloDeSueldo(a=beta[0], b=beta[1], c=beta[2], lecturas=len(utiles))


def _resolver(matriz: list[list[float]], vector: list[float]) -> list[float] | None:
    """Gauss con pivoteo parcial. `None` si el sistema es singular."""
    n = len(vector)
    m = [fila[:] + [vector[i]] for i, fila in enumerate(matriz)]
    for col in range(n):
        pivote = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivote][col]) < 1e-12:
            return None
        m[col], m[pivote] = m[pivote], m[col]
        for fila in range(col + 1, n):
            factor = m[fila][col] / m[col][col]
            for k in range(col, n + 1):
                m[fila][k] -= factor * m[col][k]
    sol = [0.0] * n
    for fila in range(n - 1, -1, -1):
        acumulado = m[fila][n] - sum(m[fila][k] * sol[k] for k in range(fila + 1, n))
        sol[fila] = acumulado / m[fila][fila]
    return sol
