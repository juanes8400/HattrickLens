"""Clases de Jugador: cuatro formas de partir la plantilla.

REGLAS DEL USUARIO, 2026-11-16. Ninguna es una fórmula ajustada a sus datos:
son repartos y cortes que él dictó, sobre motores que ya existen.

TITULARIDAD (Titular / Suplencia / Reserva).

1. Se toman las tres formaciones con más experiencia del equipo (la que da
   el juego, de 0 a 10 por formación).
2. Para cada una se busca el mejor once con el mismo motor de Alineación.
   Quien entre en cualquiera de esos onces es Titular.
3. Suplencia: lo mismo, con todos los titulares fuera de la plantilla. Si no
   llegan a once, «los pone en sus mejores puestos y deja huecos».
4. Reserva: los demás.

Empate en el corte: si la tercera empata con la cuarta, se usan sólo dos
(«Si hay empate entre la 3ra y la 4ta, usar solo 2»). Generalizado: entran
sólo las formaciones con más experiencia que la primera que se queda fuera,
así ninguna se elige por el orden de una lista. Si el empate se las lleva
todas, se usa el 4-4-2 («Si todas están igual de empatadas, usar 4-4-2»,
2026-11-17): en 8 de 328 plantillas el reparto salía vacío, todos en Reserva.
Sin lectura de experiencia no hay nada que desempatar y no se inventa ninguna:
la pantalla pide sincronizar. Los lesionados cuentan como
sanos («Como si estuviera sano»): una lesión dice quién no juega este sábado,
no a qué grupo pertenece.

RENTABILIDAD DEPORTIVA (HTMS a los 28 × sueldo). Sustituye el 2026-11-17 a
«Potencial» (HTMS hoy × HTMS28): con su plantilla, sueldo y HTMS de hoy caían
del mismo lado de la mediana en 17 de 19, así que las dos repartían casi igual,
y el usuario se quedó con la que habla de lo que cuesta. Cortes en la mediana
de la plantilla entera, con los veteranos de HTMS28 negativo dentro («Si»).
Quien cae justo en una mediana cuenta arriba («Arriba»): en HTMS28, alto; en
sueldo, caro. Estrellas: futuro alto, sueldo alto. Gangas: futuro alto, sueldo
bajo. Caros: futuro bajo, sueldo alto. Económicos: futuro bajo, sueldo bajo.

ETAPA DE CARRERA. La de la ficha de cada jugador (`career_stage_engine`); la
que el usuario confirme a mano allí manda. Cualquier etapa puede partirse en
titulares y suplentes, pero sólo si tiene más de 11 jugadores, y no se parte
si uno de los dos lados quedaría vacío («No se parte»).
"""

import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.engines.lineup_optimizer import Lineup, best_lineup
from app.domain.value_objects.formations import LINE_COUNTS

CUANTAS_FORMACIONES = 3
#: La formación cuando el empate no deja ninguna (regla del usuario, 2026-11-17).
SI_TODAS_EMPATAN = "4-4-2"
#: Una etapa con más jugadores que esto se parte en titulares y suplentes.
TOPE_DE_UNA_ETAPA = 11

TITULAR = "titular"
SUPLENCIA = "suplencia"
RESERVA = "reserva"

ESTRELLAS = "estrellas"
GANGAS = "gangas"
CAROS = "caros"
ECONOMICOS = "economicos"

#: Los dos lados de una etapa partida.
LADO_TITULAR = "titular"
LADO_SUPLENTE = "suplente"


@dataclass(frozen=True)
class Casilla:
    """Una casilla de un once. Sin jugador (`ht_player_id` None) es un hueco."""

    slot: int
    #: La casilla sin orden: «wingback», «central_defender»…
    base: str
    #: La posición con su orden («wingback_defensive»); None en un hueco.
    position: str | None = None
    ht_player_id: int | None = None
    rating: float | None = None


@dataclass(frozen=True)
class Once:
    formation: str
    casillas: tuple[Casilla, ...]


@dataclass(frozen=True)
class Reparto:
    formations: tuple[str, ...]
    #: ht_player_id → TITULAR, SUPLENCIA o RESERVA, para toda la plantilla.
    titularidad: Mapping[int, str]
    onces_titular: tuple[Once, ...]
    onces_suplencia: tuple[Once, ...]


@dataclass(frozen=True)
class CorteDeRentabilidad:
    mediana_htms28: float
    mediana_sueldo: float
    #: ht_player_id → ESTRELLAS, GANGAS, CAROS o ECONOMICOS.
    grupos: Mapping[int, str]


def _con_guiones(clave: str) -> str:
    """«550» → «5-5-0», el nombre con el que la conoce Alineación."""
    return "-".join(clave) if "-" not in clave else clave


def formaciones_mas_entrenadas(
    experiencia: Mapping[str, int], cuantas: int = CUANTAS_FORMACIONES
) -> tuple[str, ...]:
    """Las `cuantas` con más experiencia, sin ninguna que entre por empate.

    Si la última que cabe empata con la primera que se queda fuera, se quitan
    todas las de ese nivel: elegir entre ellas sería elegir al azar. Si eso
    las quita todas, el 4-4-2.
    """
    conocidas = [(_con_guiones(k), v) for k, v in experiencia.items()]
    ordenadas = sorted(((f, v) for f, v in conocidas if f in LINE_COUNTS), key=lambda fv: -fv[1])
    if len(ordenadas) <= cuantas:
        return tuple(f for f, _ in ordenadas)
    corte = ordenadas[cuantas][1]
    elegidas = tuple(f for f, v in ordenadas[:cuantas] if v > corte)
    return elegidas or (SI_TODAS_EMPATAN,)


def _sanos(jugadores: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**j, "injury_level": -1} for j in jugadores]


MotorDeOnces = Callable[[list[dict[str, Any]], str], Lineup]


def _con_huecos(jugadores: list[dict[str, Any]], formacion: str) -> Lineup:
    return best_lineup(jugadores, formacion, con_huecos=True)


def _onces(
    jugadores: list[dict[str, Any]], formaciones: Sequence[str], once: MotorDeOnces
) -> tuple[tuple[Once, ...], set[int]]:
    """El mejor once de cada formación (con huecos si no llegan) y quién entra."""
    if not jugadores:
        return (), set()
    onces: list[Once] = []
    dentro: set[int] = set()
    for formacion in formaciones:
        alineacion = once(jugadores, formacion)
        casillas = [
            Casilla(
                slot=a.slot,
                base=a.base_position,
                position=a.position,
                ht_player_id=int(a.player["ht_player_id"]),
                rating=a.rating,
            )
            for a in alineacion.assignments
        ]
        casillas += [Casilla(slot=j, base=base) for j, base in alineacion.holes]
        onces.append(
            Once(formation=formacion, casillas=tuple(sorted(casillas, key=lambda c: c.slot)))
        )
        dentro |= {c.ht_player_id for c in casillas if c.ht_player_id is not None}
    return tuple(onces), dentro


def repartir(
    jugadores: Sequence[dict[str, Any]],
    experiencia: Mapping[str, int],
    once: MotorDeOnces = _con_huecos,
) -> Reparto:
    formaciones = formaciones_mas_entrenadas(experiencia)
    todos = _sanos(jugadores)

    onces_t, titulares = _onces(todos, formaciones, once)
    sin_titulares = [j for j in todos if int(j["ht_player_id"]) not in titulares]
    onces_s, suplencia = _onces(sin_titulares, formaciones, once)

    titularidad = {
        int(j["ht_player_id"]): (
            TITULAR
            if int(j["ht_player_id"]) in titulares
            else SUPLENCIA
            if int(j["ht_player_id"]) in suplencia
            else RESERVA
        )
        for j in todos
    }
    return Reparto(
        formations=formaciones,
        titularidad=titularidad,
        onces_titular=onces_t,
        onces_suplencia=onces_s,
    )


def rentabilidad(valores: Mapping[int, tuple[int, int]]) -> CorteDeRentabilidad | None:
    """`valores`: ht_player_id → (HTMS28, sueldo semanal). None sin jugadores.

    El sueldo puede ir en cualquier moneda: la mediana y el corte no cambian
    al dividirlo por una tasa."""
    if not valores:
        return None
    mf = float(statistics.median(f for f, _ in valores.values()))
    ms = float(statistics.median(s for _, s in valores.values()))

    def grupo(f: int, s: int) -> str:
        alto_28, caro = f >= mf, s >= ms
        if alto_28 and caro:
            return ESTRELLAS
        if alto_28:
            return GANGAS
        if caro:
            return CAROS
        return ECONOMICOS

    return CorteDeRentabilidad(
        mediana_htms28=mf,
        mediana_sueldo=ms,
        grupos={pid: grupo(f, s) for pid, (f, s) in valores.items()},
    )


def partir_etapas(
    etapas: Mapping[int, str], titulares: set[int], tope: int = TOPE_DE_UNA_ETAPA
) -> dict[int, str | None]:
    """ht_player_id → LADO_TITULAR, LADO_SUPLENTE o None (etapa sin partir)."""
    por_etapa: dict[str, list[int]] = {}
    for pid, etapa in etapas.items():
        por_etapa.setdefault(etapa, []).append(pid)
    lados: dict[int, str | None] = dict.fromkeys(etapas)
    for miembros in por_etapa.values():
        if len(miembros) <= tope:
            continue
        dentro = [pid for pid in miembros if pid in titulares]
        if not dentro or len(dentro) == len(miembros):
            continue
        for pid in miembros:
            lados[pid] = LADO_TITULAR if pid in titulares else LADO_SUPLENTE
    return lados
