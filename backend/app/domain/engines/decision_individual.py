"""Cuándo conviene entrenar «Individual», y en cuál de los dos huecos.

2026-08-26, reglas dictadas por el usuario. El puntaje de cada habilidad
(`youth_skill_score`) contesta «¿qué rinde más?». Ese es el problema
equivocado cuando la academia está a oscuras: con casi todos los techos sin
revelar, el puntaje de una habilidad se compone de pura ignorancia --el
peldaño del desconocido pesa ⅓, y el del bueno 27-- y el orden por debajo del
primero es ruido, no información.

«Individual» es el entrenamiento que descubre: cada puesto sube SU habilidad,
así que un once toca hasta cinco a la vez en vez de una. Es mucho más lento, y
por eso solo vale la pena donde no se sabe el nivel: un extremo con Lateral ya
revelado no descubre nada ahí.

Dos reglas, y solo dos:

    B. Si la DESVIACIÓN de los puntajes es pequeña, ninguna habilidad
       destaca y no hay nada que optimizar: Individual en los dos huecos.
    A. Si el primero saca MÁS DE CUATRO VECES al segundo, el segundo no vale
       la pena: el primero se queda e Individual entra de secundario.

**B manda sobre A.** Pueden dispararse las dos a la vez --pasa cuando hay
líder pero el conjunto entero es diminuto: con `0,9` y seis `0,2` la razón es
4,5 y la desviación 0,245-- y en ese caso el liderazgo es sobre nada.

La desviación es POBLACIONAL y sobre las siete habilidades que enseña la
columna «Puntaje», no sobre los entrenamientos (que son más: «Defensa» y
«Defensa (ancha)» son dos caminos a la misma habilidad).
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

#: El código que ocupa el hueco cuando la elección es descubrir. No es una
#: habilidad, así que no puede colisionar con ninguna de las siete.
INDIVIDUAL = "individual"

#: Regla A: cuántas veces tiene que sacarle el primero al segundo. Estricto:
#: «más de cuatro veces», no «cuatro o más».
RAZON_MINIMA = 4.0

#: Regla B: por debajo de esto, los puntajes no se separan lo suficiente como
#: para que elegir signifique algo.
DESVIACION_MAXIMA = 0.25


@dataclass(frozen=True)
class Decision:
    """Qué entrenar en cada hueco, y por qué."""

    principal: str
    secundario: str
    #: `"A"`, `"B"` o `None` cuando no entra Individual.
    regla: str | None
    #: Primero ÷ segundo. `None` si no hay dos puntajes que dividir; `inf`
    #: cuando el segundo es cero --el primero le saca infinito, y eso es un
    #: líder claro, no un fallo--.
    razon: float | None
    desviacion: float

    @property
    def descubre(self) -> bool:
        """Si algún hueco busca descubrir."""
        return INDIVIDUAL in (self.principal, self.secundario)


def _razon(mejor: float, segundo: float) -> float | None:
    if segundo > 0:
        return mejor / segundo
    return float("inf") if mejor > 0 else None


def decidir(puntajes: Sequence[tuple[str, float]]) -> Decision | None:
    """Las dos reglas, aplicadas a `(habilidad, puntaje)` de las siete.

    Devuelve `None` cuando no hay con qué decidir: sin al menos dos
    habilidades no existe «el segundo», y ninguna de las dos reglas significa
    nada. Callarse ahí es más honesto que inventar un veredicto.
    """
    if len(puntajes) < 2:
        return None

    orden = sorted(puntajes, key=lambda par: -par[1])
    mejor, segundo = orden[0], orden[1]
    desviacion = statistics.pstdev([p for _, p in puntajes])
    razon = _razon(mejor[1], segundo[1])

    # B primero: manda sobre A cuando ambas se disparan.
    if desviacion < DESVIACION_MAXIMA:
        return Decision(INDIVIDUAL, INDIVIDUAL, "B", razon, desviacion)

    if razon is not None and razon > RAZON_MINIMA:
        return Decision(mejor[0], INDIVIDUAL, "A", razon, desviacion)

    return Decision(mejor[0], segundo[0], None, razon, desviacion)


#: Las cinco habilidades que «Individual» puede descubrir: son las que algún
#: puesto entrena. Pases y Balón parado no son de ningún puesto, así que
#: quedan fuera —y por eso no cuentan para ordenar esta cola: incluirlas
#: pondría delante a quien tiene huecos que este entrenamiento no va a tapar.
HABILIDADES_DE_PUESTO = frozenset({"keeper", "defending", "playmaking", "winger", "scoring"})


def cola_de_descubrimiento(
    notas: Sequence[object],
    sin_revelar: dict[str, int],
) -> list[object]:
    """La cola de «Individual»: primero quien más ilumina.

    `youth_training_plan` no reordena nada —toma de la cola por turnos— así
    que hacer que Individual reparta por descubrimiento es exactamente esto:
    entregarle la misma lista de siempre, ordenada por otro criterio. No hace
    falta tocar el motor.

    El orden, y por qué:

    1. **Cuántas de las cinco no se saben**, de más a menos. Es la razón de
       ser del entrenamiento; quien ya está leído no descubre nada.
    2. **Quien se va pronto, antes.** A un canterano que sale en tres semanas
       o lo miras ahora o no lo miras: el que se queda tendrá su turno.
    3. **Más potencial primero.** Entre dos igual de tapados, importa más
       destapar al que puede llegar lejos.
    4. El nombre, para que dos empatados no bailen entre recargas.

    `notas` son `PlayerNote` —se tipan como `object` para no arrastrar aquí la
    dependencia de `youth_skill_score`, que ya importa bastante—.
    """
    return sorted(
        notas,
        key=lambda n: (
            -sin_revelar.get(getattr(n, "name", ""), 0),
            not getattr(n, "leaves_soon", False),
            -getattr(n, "htms28_max", 0),
            getattr(n, "name", ""),
        ),
    )
