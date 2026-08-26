"""Qué usa la gente, y cuánto: el resumen que alimenta la pantalla de uso.

2026-08-26, pedido por el usuario: además de qué módulos se visitan, quería el
instante exacto, los clics, el tiempo dentro de cada pantalla y lo que dura una
sesión entera.

Aquí no hay base de datos ni HTTP: sólo la aritmética, que es la parte donde se
puede mentir sin que se note. Dos decisiones que la sostienen:

**El tiempo se mide con la pestaña VISIBLE.** Es el navegador quien descuenta
lo que pasa en segundo plano y manda ya sólo el tiempo visible. Sin eso, una
pestaña olvidada toda la noche diría "ocho horas en Juveniles" y el número
dejaría de servir para nada.

**Una sesión se corta por inactividad, no al cerrar el navegador.** Cerrar no
siempre avisa —se pierde la conexión, se apaga el portátil, el móvil mata la
pestaña— así que esperar el aviso de cierre dejaría sesiones abiertas para
siempre. Con un corte por silencio, la peor consecuencia de un cierre brusco es
partir una sesión en dos.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

#: Silencio a partir del cual se considera que empezó otra sesión.
CORTE_POR_SILENCIO = timedelta(minutes=30)


@dataclass(frozen=True)
class Evento:
    """Lo que manda el navegador, ya limpio."""

    sesion: str
    tipo: str          # "page" | "click"
    modulo: str
    etiqueta: str | None
    cuando: datetime
    visible_ms: int = 0


@dataclass
class UsoDeModulo:
    modulo: str
    visitas: int = 0
    clics: int = 0
    visible_ms: int = 0
    ultima_vez: datetime | None = None

    @property
    def minutos(self) -> float:
        return round(self.visible_ms / 60_000, 1)

    @property
    def media_por_visita_s(self) -> float:
        """Cuánto se queda la gente, de media, cada vez que entra."""
        return round(self.visible_ms / self.visitas / 1000, 1) if self.visitas else 0.0


@dataclass
class Sesion:
    sesion: str
    empezo: datetime
    termino: datetime
    paginas: int = 0
    clics: int = 0
    modulos: set[str] = field(default_factory=set)

    @property
    def duracion_s(self) -> int:
        return int((self.termino - self.empezo).total_seconds())


def modulos(eventos: list[Evento]) -> list[UsoDeModulo]:
    """Un renglón por módulo, del más usado al menos."""
    por_modulo: dict[str, UsoDeModulo] = {}
    for e in eventos:
        u = por_modulo.setdefault(e.modulo, UsoDeModulo(modulo=e.modulo))
        if e.tipo == "page":
            u.visitas += 1
            u.visible_ms += max(0, e.visible_ms)
        elif e.tipo == "click":
            u.clics += 1
        if u.ultima_vez is None or e.cuando > u.ultima_vez:
            u.ultima_vez = e.cuando
    return sorted(
        por_modulo.values(),
        key=lambda u: (u.visible_ms, u.visitas, u.clics),
        reverse=True,
    )


def sesiones(eventos: list[Evento]) -> list[Sesion]:
    """Agrupa por identificador de sesión y la acota con sus propios eventos.

    La duración es del PRIMER al ÚLTIMO evento. Un solo evento da cero, que es
    lo honesto: no se sabe cuánto se quedó, sólo que pasó por ahí.
    """
    por_sesion: dict[str, Sesion] = {}
    for e in sorted(eventos, key=lambda x: x.cuando):
        s = por_sesion.get(e.sesion)
        if s is None:
            s = Sesion(sesion=e.sesion, empezo=e.cuando, termino=e.cuando)
            por_sesion[e.sesion] = s
        s.termino = max(s.termino, e.cuando)
        s.empezo = min(s.empezo, e.cuando)
        s.modulos.add(e.modulo)
        if e.tipo == "page":
            s.paginas += 1
        elif e.tipo == "click":
            s.clics += 1
    return sorted(por_sesion.values(), key=lambda s: s.empezo, reverse=True)


@dataclass(frozen=True)
class Totales:
    sesiones: int
    paginas: int
    clics: int
    minutos: float
    duracion_media_s: int
    clics_por_sesion: float


def totales(eventos: list[Evento]) -> Totales:
    ss = sesiones(eventos)
    duraciones = [s.duracion_s for s in ss]
    paginas = sum(1 for e in eventos if e.tipo == "page")
    clics = sum(1 for e in eventos if e.tipo == "click")
    visible = sum(max(0, e.visible_ms) for e in eventos if e.tipo == "page")
    return Totales(
        sesiones=len(ss),
        paginas=paginas,
        clics=clics,
        minutos=round(visible / 60_000, 1),
        # La MEDIANA, no la media: una sola pestaña olvidada dispara la media y
        # deja de describir a nadie.
        duracion_media_s=_mediana(duraciones),
        clics_por_sesion=round(clics / len(ss), 1) if ss else 0.0,
    )


def _mediana(nums: list[int]) -> int:
    if not nums:
        return 0
    ordenados = sorted(nums)
    medio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[medio]
    return (ordenados[medio - 1] + ordenados[medio]) // 2


def por_hora(eventos: list[Evento]) -> dict[int, int]:
    """A qué horas se usa. Contesta si conviene desplegar de madrugada."""
    reloj: dict[int, int] = defaultdict(int)
    for e in eventos:
        reloj[e.cuando.hour] += 1
    return dict(reloj)


def mas_pulsado(eventos: list[Evento], cuantos: int = 12) -> list[tuple[str, int]]:
    """Los controles más usados, por su etiqueta.

    Es lo que dice si una función se usa o sólo se mira: "Juveniles" puede
    tener muchas visitas y ni un clic en «Qué entrenar».
    """
    cuenta: dict[str, int] = defaultdict(int)
    for e in eventos:
        if e.tipo == "click" and e.etiqueta:
            cuenta[f"{e.modulo} · {e.etiqueta}"] += 1
    return sorted(cuenta.items(), key=lambda x: -x[1])[:cuantos]
