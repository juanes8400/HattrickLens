"""Por qué se movió el espíritu y por qué se movió la confianza.

El manual de Hattrick nombra cuatro palancas para el espíritu —la actitud del
partido, las compras, las ventas y bajar el % de entrenamiento— y dice que
entre golpe y golpe el valor **tiende a un punto de equilibrio**. La confianza
va por otro camino: la mueven los resultados y los goles, y deriva hacia su
punto medio en cada actualización diaria.

De ahí sale la regla que gobierna este motor:

    UNA CAUSA SÓLO SE AFIRMA SI SE PUEDE COMPROBAR.

La actitud de cada partido está guardada y es comprobable, así que se afirma.
Una compra o una venta sólo *arriesgan* un bajón --el manual dice «corres el
riesgo»--, así que se cuentan y se enseñan al lado del tramo, pero nunca se
declaran causa de una caída que la deriva ya explica. La diferencia importa:
esta pantalla existe para que el usuario entienda su club, y una causa
inventada le enseña algo falso con la misma confianza que una verdadera.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.domain.value_objects.ht_constants import CONFIDENCE, TEAM_SPIRIT

#: El equilibrio base del espíritu para un club sin psicólogo deportivo.
#: Cada nivel de psicólogo lo sube una décima (manual de Hattrick).
#: OJO: es a donde TIENDE, no un suelo. Se puede bajar de aquí.
EQUILIBRIO_BASE = 4

#: Los tres valores de `TeamAttitude`. Se leen del detalle del partido, que
#: los trae para todos los partidos propios --también los viejos--, a
#: diferencia de las órdenes, que sólo existen antes de jugar.
PIC, NORMAL, MOTS = -1, 0, 1
ACTITUDES = {PIC: "PIC", NORMAL: "Normal", MOTS: "MOTS"}

#: Sólo estos tipos mueven el ánimo. Un torneo no lo toca, y en una temporada
#: real hay muchos más de torneo que de competición.
TIPOS_QUE_CUENTAN = (1, 3, 9)


@dataclass(frozen=True)
class Partido:
    played_at: datetime
    rival: str
    is_home: bool
    goals_for: int
    goals_against: int
    attitude: int | None

    @property
    def marcador(self) -> str:
        return f"{self.goals_for}-{self.goals_against}"

    @property
    def resultado(self) -> str:
        if self.goals_for > self.goals_against:
            return "win"
        return "loss" if self.goals_for < self.goals_against else "draw"


@dataclass(frozen=True)
class Lectura:
    at: datetime
    level: int


@dataclass
class Movimiento:
    """Un tramo entre dos lecturas, con lo que lo explica."""

    at: datetime
    desde: int
    hasta: int
    cause: str
    #: Contexto que NO se afirma como causa: cuántas operaciones de mercado
    #: cayeron dentro del tramo.
    buys: int = 0
    sales: int = 0
    matches: list[Partido] = field(default_factory=list)

    @property
    def delta(self) -> int:
        return self.hasta - self.desde


def _entre(partidos: list[Partido], a: datetime, b: datetime) -> list[Partido]:
    return [p for p in partidos if a < p.played_at <= b]


def movimientos_de_espiritu(
    lecturas: list[Lectura],
    partidos: list[Partido],
    compras: dict[str, int],
    ventas: dict[str, int],
    bajadas_de_intensidad: list[datetime],
) -> list[Movimiento]:
    """Qué explica cada tramo del espíritu.

    El orden en que se buscan las causas no es casual: primero lo que el
    manual describe como un golpe inmediato --la actitud, bajar la
    intensidad--, y sólo si no hubo ninguno se atribuye a la deriva. Al revés,
    la deriva se comería subidas que sí tienen dueño.
    """
    salida: list[Movimiento] = []
    for anterior, actual in zip(lecturas, lecturas[1:], strict=False):
        dentro = _entre(partidos, anterior.at, actual.at)
        bajo_intensidad = any(anterior.at < t <= actual.at for t in bajadas_de_intensidad)
        subio = actual.level > anterior.level

        if actual.level == anterior.level:
            # Un tramo plano no es una vuelta al equilibrio: es que no se
            # movió. Aparece desde que la serie llega hasta la última lectura
            # y no hasta el último cambio (2026-08-31).
            causa = "Sin cambios"
        elif subio and bajo_intensidad:
            causa = "Bajada del % de entrenamiento"
        elif subio:
            empuja = next((p for p in dentro if p.attitude == PIC), None)
            causa = f"PIC · {empuja.rival}" if empuja else "Subida sin causa registrada"
        else:
            hundio = next((p for p in dentro if p.attitude == MOTS), None)
            causa = f"MOTS · {hundio.rival}" if hundio else "Vuelta al equilibrio"

        salida.append(
            Movimiento(
                at=actual.at,
                desde=anterior.level,
                hasta=actual.level,
                cause=causa,
                buys=_cuantas(compras, anterior.at, actual.at),
                sales=_cuantas(ventas, anterior.at, actual.at),
                matches=dentro,
            )
        )
    return salida


def movimientos_de_confianza(lecturas: list[Lectura], partidos: list[Partido]) -> list[Movimiento]:
    """Qué explica cada tramo de la confianza: los resultados del tramo.

    No se mira la actitud: el manual la nombra sólo para el espíritu.
    """
    salida: list[Movimiento] = []
    for anterior, actual in zip(lecturas, lecturas[1:], strict=False):
        dentro = _entre(partidos, anterior.at, actual.at)
        if actual.level == anterior.level:
            causa = "Sin cambios"
        elif not dentro:
            causa = "Deriva hacia el punto medio"
        else:
            causa = ", ".join(f"{_como_acabo(p)} {p.marcador}" for p in dentro)
            causa = causa[:1].upper() + causa[1:]
        salida.append(
            Movimiento(
                at=actual.at,
                desde=anterior.level,
                hasta=actual.level,
                cause=causa,
                matches=dentro,
            )
        )
    return salida


def _como_acabo(p: Partido) -> str:
    return {"win": "victoria", "loss": "derrota"}.get(p.resultado, "empate")


def _cuantas(por_dia: dict[str, int], a: datetime, b: datetime) -> int:
    total = 0
    for dia, cuantas in por_dia.items():
        fecha = datetime.fromisoformat(dia)
        if a.date() <= fecha.date() <= b.date():
            total += cuantas
    return total


def escala(cual: str) -> list[dict[str, Any]]:
    """Los niveles ENTEROS de una escala, se hayan visto o no.

    2026-08-31, corregido a petición del usuario: recortar el eje a lo
    observado hacía parecer que el mínimo visto era un suelo del juego.
    """
    tabla = TEAM_SPIRIT if cual == "spirit" else CONFIDENCE
    return [{"level": k, "label": v} for k, v in sorted(tabla.items())]
