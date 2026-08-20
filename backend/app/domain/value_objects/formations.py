"""Las formaciones de Hattrick y cómo se reparte cada línea.

Una formación tiene dos partes. El NOMBRE dice cuántos hay en cada línea
(4-4-2 = cuatro defensas, cuatro medios, dos delanteros) y el REPARTO dice
cuántos de esa línea juegan por dentro; el resto va a las bandas. El nombre
solo no basta: un 5-3-2 puede llevar tres mediocentros, o dos y un extremo, o
uno y dos extremos, y son onces distintos.

Hasta 2026-08-19 cada motor tenía su propia tabla, con un reparto fijo por
nombre y sin forma de moverlo. Aquí viven las dos, juntas, porque describen lo
mismo: si se separan, "5-3-2" acaba significando cosas distintas en Alineación
y en el once ideal de la liga.

Los máximos son del juego, confirmados por el usuario ese mismo día: 1 portero,
3 defensas centrales, 2 laterales (uno por banda), 3 mediocentros, 2 extremos
(uno por banda) y 3 delanteros. De ahí sale que ninguna línea pase de cinco.
"""

MAX_CENTRAL_DEFENDERS = 3
MAX_INNER_MIDFIELDERS = 3
MAX_FORWARDS = 3
MAX_FLANK_PER_LINE = 2   # una banda a cada lado

DEFAULT_FORMATION = "4-4-2"

# defensas-medios-delanteros. Las diez de Hattrick, de la más defensiva a la
# más ofensiva. El extremo cuenta en la línea del medio, igual que en el juego.
LINE_COUNTS: dict[str, tuple[int, int, int]] = {
    "5-5-0": (5, 5, 0),
    "5-4-1": (5, 4, 1),
    "5-3-2": (5, 3, 2),
    "5-2-3": (5, 2, 3),
    "4-5-1": (4, 5, 1),
    "4-4-2": (4, 4, 2),
    "4-3-3": (4, 3, 3),
    "3-5-2": (3, 5, 2),
    "3-4-3": (3, 4, 3),
    "2-5-3": (2, 5, 3),
}

# El reparto con el que arranca cada formación: (centrales, mediocentros).
DEFAULT_SPLIT: dict[str, tuple[int, int]] = {
    "5-5-0": (3, 3), "5-4-1": (3, 2), "5-3-2": (3, 1), "5-2-3": (3, 2),
    "4-5-1": (2, 3), "4-4-2": (2, 2), "4-3-3": (2, 1),
    "3-5-2": (3, 3), "3-4-3": (3, 2), "2-5-3": (2, 3),
}


def line_splits(total: int, max_inner: int) -> list[int]:
    """Cuántos pueden jugar por dentro en una línea de `total`.

    Son las opciones que ofrece el selector: el resto de la línea va a las
    bandas, y de esos caben dos como mucho. Una línea de cinco solo admite tres
    por dentro; una de tres admite uno, dos o tres.
    """
    return [
        inner
        for inner in range(0, min(max_inner, total) + 1)
        if 0 <= total - inner <= MAX_FLANK_PER_LINE
    ]


def central_defender_options(formation: str) -> list[int]:
    return line_splits(_lines(formation)[0], MAX_CENTRAL_DEFENDERS)


def inner_midfielder_options(formation: str) -> list[int]:
    return line_splits(_lines(formation)[1], MAX_INNER_MIDFIELDERS)


def _lines(formation: str) -> tuple[int, int, int]:
    return LINE_COUNTS.get(formation, LINE_COUNTS[DEFAULT_FORMATION])


def resolve_split(
    formation: str,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> tuple[int, int]:
    """El reparto pedido, o el de la formación si no se pide o no es legal.

    Un valor imposible cae al de por defecto en vez de reventar: el selector
    solo ofrece los legales, pero un número inventado en una URL no debe tumbar
    una pantalla.
    """
    por_defecto = DEFAULT_SPLIT.get(formation, DEFAULT_SPLIT[DEFAULT_FORMATION])
    centrales = (
        central_defenders
        if central_defenders in central_defender_options(formation)
        else por_defecto[0]
    )
    interiores = (
        inner_midfielders
        if inner_midfielders in inner_midfielder_options(formation)
        else por_defecto[1]
    )
    return centrales, interiores


def slots_for(
    formation: str,
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
) -> list[str]:
    """Los once puestos de un once concreto, del portero al delantero.

    Se construyen a partir del nombre y del reparto en vez de escribirse a
    mano, que es como una formación acabó armada con cinco medios llamándose
    4-3-3 (corregido el 2026-08-19).
    """
    defensas, medios, delanteros = _lines(formation)
    centrales, interiores = resolve_split(
        formation, central_defenders, inner_midfielders
    )
    return [
        "keeper",
        *["wingback"] * (defensas - centrales),
        *["central_defender"] * centrales,
        *["winger"] * (medios - interiores),
        *["inner_midfield"] * interiores,
        *["forward"] * delanteros,
    ]
