"""En qué se puede convertir un canterano, en HTMS28, con lo que se sabe hoy.

2026-08-24, dictado por el usuario. Sustituye al «potencial» que se inventaba
esta herramienta —un índice con pesos 1 y 0,3 que, con el techo desconocido
puesto en 8, ordenaba por ignorancia— por dos números de la tabla real de
Hattrick (`docs/reference/htms_formulas_hattrick.html`).

Cada habilidad va DESDE DONDE ESTÁ HOY HASTA DONDE PUEDE LLEGAR, y cada
extremo se toma con la información que haya:

  * el suelo es el nivel actual si el ojeador lo dijo, y 0 si no lo dijo;
  * el techo es el techo si lo dijo, y 8 —el tope juvenil— si no.

Así, un «Defensa 5/?» va de `f_Def(5)` a `f_Def(8)`, y un «Lateral ?/7» va de
`f_Lat(0)` a `f_Lat(7)`: se sabe hasta dónde llega, pero no de dónde parte.
Una habilidad AL TOPE no tiene horquilla: el juego ha confirmado las dos
puntas.

Encima de esos dos extremos se aplica HTMS28 (§6 del documento), que suma un
término que sólo depende de la edad. Pesa mucho —a los 16 son casi mil
setecientos puntos— y eso es a propósito: esto no mide «qué sale de mi
academia» sino «en qué puede convertirse este chico», y ahí el tiempo que le
queda por delante ES el activo.

La horquilla mide lo que el ojeador NO ha dicho. Se estrecha sola según
habla, sin que haya que explicar nada.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.engines import htms

#: El tope de una habilidad juvenil, confirmado por el usuario el 2026-08-24:
#: es el mismo corte que manda en la clasificación («crack» a partir de 8).
TOPE_JUVENIL = 8

#: El orden en que `htms.ability` espera las siete habilidades.
SKILLS: tuple[str, ...] = (
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
)


@dataclass(frozen=True)
class Lectura:
    """Lo que el ojeador ha dicho de UNA habilidad."""

    current: int | None = None
    maximum: int | None = None
    max_reached: bool = False


@dataclass(frozen=True)
class Horquilla:
    """En qué se puede convertir, de lo peor a lo mejor."""

    minimo: int
    maximo: int
    ability_minima: int
    ability_maxima: int

    @property
    def anchura(self) -> int:
        """Lo que el ojeador todavía no ha dicho, en puntos."""
        return self.maximo - self.minimo


def niveles(lectura: Lectura) -> tuple[int, int]:
    """Entre qué dos niveles puede acabar esa habilidad."""
    suelo = lectura.current if lectura.current is not None else 0
    if lectura.maximum is not None:
        techo = lectura.maximum
    elif lectura.max_reached and lectura.current is not None:
        # Ya no sube: el techo es donde está.
        techo = lectura.current
    else:
        techo = TOPE_JUVENIL
    return suelo, max(suelo, techo)


def rango_htms28(lecturas: dict[str, Lectura], age_years: int, age_days: int) -> Horquilla:
    """La horquilla de HTMS28 de un canterano."""
    bajos: dict[str, int] = {}
    altos: dict[str, int] = {}
    for skill in SKILLS:
        suelo, techo = niveles(lecturas.get(skill) or Lectura())
        bajos[skill] = suelo
        altos[skill] = techo
    ability_min = htms.ability(**bajos)
    ability_max = htms.ability(**altos)
    return Horquilla(
        minimo=htms.potential(ability_min, age_years, age_days),
        maximo=htms.potential(ability_max, age_years, age_days),
        ability_minima=ability_min,
        ability_maxima=ability_max,
    )
