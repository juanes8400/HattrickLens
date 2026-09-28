"""La taquilla de UN partido, a partir de las entradas de cada sector.

2026-09-28, decision del usuario: «guarda el desglose, calcula con el, y no lo
enseñes nunca». Este modulo es el «calcula con el», y es el unico sitio donde
el desglose se convierte en dinero.

POR QUE HACE FALTA. Hattrick no publica la taquilla partido a partido: la
publica por semana, sumada, en las finanzas. Con un partido en casa por semana
se podria atribuir --es la tecnica que resolvio la comision del agente-- pero
los partidos de Copa comparten semana con los de liga casi siempre, y con los
datos reales del usuario solo una de nueve semanas cerradas tenia un unico
partido en casa, y no era de Copa.

LOS PRECIOS estan verificados y viven en `arena_engine`: Tribunas se derivo de
forma exacta con un partido en el que tres sectores se llenaron, y los otros
tres los confirmo el usuario «para toda la herramienta» el 2026-08-13.

NO REDONDEA A LA BAJA NI INVENTA. Si falta el desglose de un partido devuelve
`None`, no un cero: un cero diria «no entro nadie», que es otra cosa. Esos
partidos se quedan fuera del total hasta que su detalle se vuelva a pedir.
"""

from typing import Any

from app.domain.engines.arena_engine import TICKET_PRICES

#: Cada sector con el nombre que lleva en la foto del partido y el que lleva
#: en la tabla de precios. Son dos vocabularios distintos y esto los junta.
SECTORES: tuple[tuple[str, str], ...] = (
    ("sold_terraces", "general"),
    ("sold_basic", "preferentes"),
    ("sold_roof", "tribunas"),
    ("sold_vip", "palcos"),
)


def taquilla_del_partido(foto: Any, precios: dict[str, float] | None = None) -> int | None:
    """Lo que se recaudo en ese partido, o `None` si falta el desglose.

    `foto` es una fila de `stadium_history`; se leen sus cuatro sectores.
    """
    p = precios or TICKET_PRICES
    total = 0.0
    for columna, sector in SECTORES:
        entradas = getattr(foto, columna, None)
        if entradas is None:
            return None
        total += int(entradas) * p[sector]
    return int(round(total))


def taquilla_de_varios(fotos: list[Any], precios: dict[str, float] | None = None) -> list[int]:
    """Las taquillas que SI se pueden calcular, en el orden de entrada."""
    calculadas = (taquilla_del_partido(f, precios) for f in fotos)
    return [t for t in calculadas if t is not None]
