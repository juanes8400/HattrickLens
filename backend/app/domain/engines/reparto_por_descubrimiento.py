"""Colocar el once cuando «Individual» ocupa un hueco.

2026-08-26, dictado por el usuario. Con cualquier otro entrenamiento el once
se llena ordenando una cola: la habilidad que sube es la misma en todas las
plazas, así que solo importa a quién pones, no dónde. Con «Individual» no:
**la ruleta depende del puesto**, y entonces colocar el once es emparejar
jugadores con plazas, no ordenar una lista.

Dos reglas, y la segunda es la que el usuario subrayó:

1. **El compañero manda primero.** Con «Lateral + Individual», las plazas que
   Lateral entrena se llenan con su cola de siempre y no se negocian. Solo lo
   que sobra se reparte para descubrir.

2. **La habilidad del compañero NO cuenta como descubrimiento.** Si a un chico
   le sale Lateral en la ruleta de Individual, eso no aporta nada nuevo: esa
   habilidad ya la está trabajando el otro hueco. La plaza se juzga por lo que
   puede iluminar que el compañero no vaya a iluminar ya.

   Si el compañero sube DOS --«Anotación y balón parado»-- se descuentan las
   dos, por el mismo motivo.

Y una tercera que no es opinión sino aritmética: una habilidad que ya tocó
techo tampoco se puede descubrir, así que no suma.

El emparejamiento se resuelve con el óptimo real (`asignacion_optima`), no
por turnos. Elegir la mejor pareja una y otra vez puede salir casi la mitad de
bueno --el contraejemplo está allí documentado-- y aquí las plazas escasean:
quitarle el portero a quien más lo aprovecha puede costar más de lo que gana
quien se lo queda.
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass

from app.domain.engines.asignacion_optima import asignacion_maxima


@dataclass(frozen=True)
class Candidato:
    """Un canterano disponible, con lo que aún no se sabe de él."""

    nombre: str
    #: Las habilidades cuyo nivel no se conoce Y que todavía pueden subir. Un
    #: techo ya alcanzado no está aquí: entrenarlo no lo va a revelar.
    sin_revelar: frozenset[str]


def probabilidad_de_descubrir(
    reparto: dict[str, int],
    sin_revelar: Container[str],
    excluidas: Container[str] = frozenset(),
) -> int:
    """Qué posibilidad hay de que esa plaza destape algo nuevo, en porcentaje.

    Es la suma de las casillas de la ruleta que caen en habilidades que no se
    saben Y que el compañero no está entrenando ya. Un chico con todo revelado
    da 0 --la plaza se desperdicia en él--; uno del que no se sabe nada y cuyo
    puesto no comparte habilidad con el compañero, 100.
    """
    return sum(p for skill, p in reparto.items() if skill in sin_revelar and skill not in excluidas)


def reparte(
    plazas: Sequence[str],
    candidatos: Iterable[Candidato],
    reparto_de: dict[str, dict[str, int]],
    excluidas: Container[str] = frozenset(),
) -> list[tuple[str, str]]:
    """Quién ocupa cada plaza para destapar lo máximo posible.

    `plazas` son los puestos libres --repetidos si hay varios del mismo--,
    `reparto_de` es la ruleta de cada puesto (`puesto -> habilidad -> %`), y
    `excluidas` las habilidades que el compañero ya entrena.

    Devuelve `(nombre, puesto)` en el orden de `plazas`. Una plaza sin
    candidato no aparece.
    """
    gente = list(candidatos)
    if not gente or not plazas:
        return []

    def vale(c: Candidato, plaza: tuple[int, str]) -> float:
        _, puesto = plaza
        return probabilidad_de_descubrir(reparto_de.get(puesto, {}), c.sin_revelar, excluidas)

    # Las plazas van numeradas porque puede haber tres centrales y son sillas
    # distintas: sin el indice el emparejamiento las trataria como una sola.
    numeradas = list(enumerate(plazas))
    pares = asignacion_maxima(gente, numeradas, vale)

    por_indice = {plaza[0]: c.nombre for c, plaza in pares}
    return [(por_indice[i], puesto) for i, puesto in numeradas if i in por_indice]
