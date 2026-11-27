"""Cuánto se aprovecha un entrenamiento con lo que de verdad se jugó (A posteriori).

Definido con el usuario entre el 2026-11-23 y el 2026-11-26, regla a regla.
Ningún número sale de ajustar sus datos (AGENTS.md): la tabla HTMS y las
semanas por nivel son las fórmulas que ya usa la app, y lo demás --la edad en
que un jugador deja de servir, el ideal, los dos partidos por semana-- son
reglas que dictó él.

Para cada jugador que jugó en un puesto que entrena:

    aporte = m · ΔHTMS / T · w

* ``m``: la fracción de semana que entrena (minutos con su peso, hasta 90′ por
  semana; ver ``PostMatchTrainingService._exposicion``).
* ``ΔHTMS``: lo que sube su HTMS al subir un nivel esa habilidad.
* ``T``: las semanas que tarda en subirlo con la configuración del equipo.
* ``w``: el peso por edad, ``máx(0, 1 + (HTMS28 − HTMS) / 746)``. Cuanto más
  joven, más vale cada subida; a los 34 años deja de contar (regla del
  usuario, 2026-11-25: «A_fin = 34»). El 746 sale de esa regla: es lo que
  vale ``HTMS − HTMS28`` justo a los 34, y así ``w`` llega a 0 ahí.

Y para el entrenamiento entero:

    aprovechado = Σ aporte ÷ (casillas × 2 partidos × G_ideal)

``G_ideal`` es el aporte de un jugador de 17 años con nivel 8 (excelente) en
la habilidad, jugando 90′ en su casilla: el 100 %. Se comprobó que es el
óptimo, o está a menos de un 3,4 % de él, siguiendo la trayectoria de un
jugador que empieza a los 17 con nivel 8 y envejece con las semanas
(2026-11-26). Las casillas vacías y los minutos que se repiten cuando el
jugador ya cumplió sus 90′ son desperdicio por construcción: el denominador
cuenta todas las casillas de los dos partidos.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import product

from app.domain.engines import htms
from app.domain.engines.training_engine import TrainingSetup, weeks_to_next_level

#: El ideal: 17 años y 0 días, nivel 8 (excelente) en la habilidad.
EDAD_DEL_IDEAL = 17
NIVEL_DEL_IDEAL = 8
#: La edad en que un jugador deja de servir (regla del usuario, 2026-11-25).
EDAD_EN_QUE_DEJA_DE_SERVIR = 34
#: −(HTMS28 − HTMS) a los 34 años y 0 días: con él, ``w`` vale 0 justo ahí.
K_EDAD = 746
#: Liga + el partido entre semana (copa, copa desafío o amistoso).
PARTIDOS_POR_SEMANA = 2
#: Para nombrar al «jugador que mejor lo aprovecha» hay que haber jugado al
#: menos esto en un puesto que entrena: sin el mínimo ganaba un juvenil con
#: 2′ y un 70 % (Homeag, semana del 22-nov).
MINUTOS_PARA_DESTACAR = 45

#: Los topes de cada línea en una alineación de Hattrick: un portero y diez de
#: campo, con hasta 3 centrales, 2 laterales, 3 interiores, 2 extremos y 3
#: delanteros.
_TOPES: dict[str, int] = {
    "defender": 3,
    "wingback": 2,
    "inner_mid": 3,
    "winger": 2,
    "forward": 3,
}
_DE_CAMPO = 10
_PESOS = {"full": 1.0, "partial": 0.5, "none": 0.0}
_HABILIDADES = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")
#: Divino: más arriba no se entrena.
NIVEL_MAXIMO = 20


def peso_por_edad(age_years: int, age_days: int) -> float:
    """``w = máx(0, 1 + (HTMS28 − HTMS) / 746)``.

    ``HTMS28 − HTMS`` sólo depende de la edad (es lo que se suma o se resta
    por las semanas que faltan o sobran hasta los 28), así que se calcula con
    un jugador vacío: a los 17 vale 1641 y ``w`` ≈ 3,2; a los 28, 0 y ``w`` = 1.
    """
    margen = htms.potential(0, age_years, age_days)
    return max(0.0, 1 + margen / K_EDAD)


def casillas(shares: Mapping[str, str]) -> float:
    """Las casillas que puede llenar un entrenamiento en un partido.

    Es la suma de pesos más alta que cabe en una alineación válida: Defensa
    llena 5 (3 centrales y 2 laterales), Lateral 3 (2 extremos completos y 2
    laterales a medias), Portería 1. Se busca entre todas las alineaciones
    posibles en vez de escribirla a mano, para que no pueda desacompasarse de
    la tabla de quién entrena qué.
    """

    def peso(rol: str) -> float:
        return _PESOS[shares.get(rol) or shares.get("all") or "none"]

    roles = list(_TOPES)
    mejor = 0.0
    for reparto in product(*(range(_TOPES[r] + 1) for r in roles)):
        if sum(reparto) != _DE_CAMPO:
            continue
        mejor = max(mejor, sum(n * peso(r) for n, r in zip(reparto, roles, strict=True)))
    return peso("keeper") + mejor


@dataclass(frozen=True)
class Ritmo:
    """Lo que rinde una semana de entrenamiento para un jugador concreto."""

    semanas: float  # T
    delta_htms: int  # ΔHTMS
    peso_edad: float  # w

    @property
    def por_semana(self) -> float:
        """ΔHTMS / T · w: el aporte de una semana completa."""
        return self.delta_htms / self.semanas * self.peso_edad if self.semanas > 0 else 0.0


def ritmo(
    skill: str,
    skills: Mapping[str, int],
    age_years: int,
    age_days: int,
    setup: TrainingSetup,
) -> Ritmo:
    nivel = int(skills.get(skill, 0) or 0)
    w = peso_por_edad(age_years, age_days)
    if nivel >= NIVEL_MAXIMO:
        return Ritmo(semanas=0.0, delta_htms=0, peso_edad=w)
    t = weeks_to_next_level(skill, nivel, age_years, age_days, setup=setup).weeks_to_next_level
    antes = htms.ability(**{k: skills.get(k) for k in _HABILIDADES})
    despues = htms.ability(
        **{k: (nivel + 1 if k == skill else skills.get(k)) for k in _HABILIDADES}
    )
    return Ritmo(semanas=t, delta_htms=despues - antes, peso_edad=w)


def ideal(skill: str, setup: TrainingSetup) -> float:
    """``G_ideal``: 17 años y 0 días, nivel 8 en la habilidad, una semana completa."""
    return ritmo(skill, {skill: NIVEL_DEL_IDEAL}, EDAD_DEL_IDEAL, 0, setup).por_semana


@dataclass(frozen=True)
class Entrenado:
    """Un jugador que jugó esta semana en un puesto que entrena."""

    ht_player_id: int
    name: str
    exposicion: float  # m
    #: Minutos jugados en puestos que entrenan, con su peso: lo que habría
    #: entrenado sin el cupo de 90′.
    minutos_utiles: float
    ritmo: Ritmo

    @property
    def aporte(self) -> float:
        return self.exposicion * self.ritmo.por_semana


@dataclass(frozen=True)
class Mejor:
    ht_player_id: int
    name: str
    #: Su ritmo en % del ideal: lo que aprovecha él, con una semana completa.
    pct: float


@dataclass(frozen=True)
class Aprovechamiento:
    training_type: int
    #: Σ aporte ÷ (casillas · 2 · G_ideal). El número de la pantalla.
    aprovechado: float
    #: Σ m·w·ΔHTMS ÷ (casillas · 2 · G_ideal): la altura del punto en la
    #: gráfica. ``aporte_por_casilla / semanas_por_nivel = aprovechado``.
    aporte_por_casilla: float
    #: T media, ponderada por lo que aporta cada uno. ``None`` si nadie entrenó.
    semanas_por_nivel: float | None
    casillas: float  # por partido
    casillas_que_entrenan: float  # Σ m, de casillas × 2
    jugadores: int
    mejor: Mejor | None
    minutos_sin_entrenar: float  # por el cupo de 90′


def aprovechamiento(
    training_type: int,
    entrenados: Iterable[Entrenado],
    casillas_por_partido: float,
    g_ideal: float,
    partidos: int = PARTIDOS_POR_SEMANA,
) -> Aprovechamiento:
    """Junta a todos los que entrenaron en un número, más los datos de su fila.

    ``partidos`` es SIEMPRE 2 en la pantalla (regla del usuario: sin amistoso,
    la casilla del segundo partido cuenta como desperdicio). Es parámetro sólo
    para las pruebas.
    """
    lista = [e for e in entrenados if e.exposicion > 0]
    denominador = casillas_por_partido * partidos * g_ideal
    suma_aporte = sum(e.aporte for e in lista)
    suma_altura = sum(e.exposicion * e.ritmo.peso_edad * e.ritmo.delta_htms for e in lista)
    aprovechado = suma_aporte / denominador if denominador > 0 else 0.0
    altura = suma_altura / denominador if denominador > 0 else 0.0
    candidatos = [e for e in lista if e.exposicion * 90 >= MINUTOS_PARA_DESTACAR and g_ideal > 0]
    destacado = max(candidatos, key=lambda e: e.ritmo.por_semana, default=None)
    return Aprovechamiento(
        training_type=training_type,
        aprovechado=aprovechado,
        aporte_por_casilla=altura,
        semanas_por_nivel=(altura / aprovechado) if aprovechado > 0 else None,
        casillas=casillas_por_partido,
        casillas_que_entrenan=sum(e.exposicion for e in lista),
        jugadores=len(lista),
        mejor=(
            Mejor(
                ht_player_id=destacado.ht_player_id,
                name=destacado.name,
                pct=destacado.ritmo.por_semana / g_ideal,
            )
            if destacado is not None
            else None
        ),
        minutos_sin_entrenar=sum(max(0.0, e.minutos_utiles - e.exposicion * 90) for e in lista),
    )
