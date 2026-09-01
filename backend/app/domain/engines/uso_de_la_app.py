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
    tipo: str  # "page" | "click"
    modulo: str
    etiqueta: str | None
    cuando: datetime
    visible_ms: int = 0
    #: Quién. Faltaba hasta el 2026-09-01: el endpoint leía la columna y la
    #: tiraba al construir el evento, así que TODO salía agregado y no había
    #: forma de ver a quién le sirve cada pantalla. Con doce usuarios
    #: registrados, un total dice muy poco.
    usuario: int = 0
    #: Su nombre en Hattrick, para no leer una tabla de números.
    nombre: str = ""


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


# ── Quién usa qué ────────────────────────────────────────────────────────────
#
# Todo lo de arriba agrega a TODOS los usuarios en un número. Con doce
# registrados eso esconde justo lo que hay que saber: si una pantalla la usan
# nueve personas o la usa una sola muchas veces (2026-09-01).


@dataclass
class UsoDeUsuario:
    """Un renglón por persona."""

    usuario: int
    nombre: str
    sesiones: int = 0
    paginas: int = 0
    clics: int = 0
    visible_ms: int = 0
    primera_vez: datetime | None = None
    ultima_vez: datetime | None = None
    dias_activos: int = 0
    #: Dónde pasa más tiempo. Es su respuesta a «¿para qué usas esto?».
    modulo_favorito: str = ""

    @property
    def minutos(self) -> float:
        return round(self.visible_ms / 60_000, 1)

    @property
    def clics_por_pagina(self) -> float:
        """Si mira o toca. Cero clics en muchas páginas es una pantalla que se
        consulta; muchos, una con la que se trabaja."""
        return round(self.clics / self.paginas, 2) if self.paginas else 0.0


def por_usuario(eventos: list[Evento]) -> list[UsoDeUsuario]:
    """Un renglón por persona, del que más tiempo echa al que menos."""
    gente: dict[int, UsoDeUsuario] = {}
    sesiones_de: dict[int, set[str]] = defaultdict(set)
    dias_de: dict[int, set[str]] = defaultdict(set)
    tiempo_por_modulo: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for e in eventos:
        u = gente.setdefault(
            e.usuario, UsoDeUsuario(usuario=e.usuario, nombre=e.nombre or str(e.usuario))
        )
        if e.nombre:
            u.nombre = e.nombre
        sesiones_de[e.usuario].add(e.sesion)
        dias_de[e.usuario].add(e.cuando.date().isoformat())
        if e.tipo == "page":
            u.paginas += 1
            u.visible_ms += max(0, e.visible_ms)
            tiempo_por_modulo[e.usuario][e.modulo] += max(0, e.visible_ms)
        elif e.tipo == "click":
            u.clics += 1
        u.primera_vez = e.cuando if u.primera_vez is None else min(u.primera_vez, e.cuando)
        u.ultima_vez = e.cuando if u.ultima_vez is None else max(u.ultima_vez, e.cuando)

    for uid, u in gente.items():
        u.sesiones = len(sesiones_de[uid])
        u.dias_activos = len(dias_de[uid])
        suyo = tiempo_por_modulo[uid]
        if suyo:
            u.modulo_favorito = max(suyo.items(), key=lambda x: x[1])[0]
    return sorted(gente.values(), key=lambda u: (u.visible_ms, u.paginas), reverse=True)


def modulos_de(eventos: list[Evento], usuario: int) -> list[UsoDeModulo]:
    """Lo mismo que `modulos`, pero de una sola persona."""
    return modulos([e for e in eventos if e.usuario == usuario])


@dataclass
class Adopcion:
    """Cuánto se usa una pantalla Y cuánto se vuelve a ella.

    Volumen y cariño no son lo mismo. Una pantalla puede acumular horas porque
    una persona la dejó abierta, y otra tener pocas visitas pero de nueve
    personas distintas, semana tras semana. La segunda es la que importa.
    """

    modulo: str
    usuarios: int
    dias: int
    visitas: int
    clics: int
    visible_ms: int

    @property
    def minutos(self) -> float:
        return round(self.visible_ms / 60_000, 1)

    @property
    def visitas_por_usuario(self) -> float:
        """Cuánto VUELVE cada uno. Uno es «la abrió y ya»."""
        return round(self.visitas / self.usuarios, 1) if self.usuarios else 0.0

    @property
    def clics_por_visita(self) -> float:
        """Si se trabaja con ella o sólo se mira."""
        return round(self.clics / self.visitas, 2) if self.visitas else 0.0

    def alcance(self, activos: int) -> float:
        """Qué parte de la gente activa la ha tocado, en tanto por ciento."""
        return round(self.usuarios / activos * 100, 1) if activos else 0.0


def adopcion(eventos: list[Evento]) -> list[Adopcion]:
    """Por módulo: a cuánta gente llega, cuántos días y cuánto se vuelve.

    Ordenado por número de personas y luego por visitas por persona: primero lo
    que usa MUCHA gente, y entre dos iguales, aquello a lo que más se vuelve.
    """
    usuarios: dict[str, set[int]] = defaultdict(set)
    dias: dict[str, set[str]] = defaultdict(set)
    crudo: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])  # visitas, clics, ms

    for e in eventos:
        usuarios[e.modulo].add(e.usuario)
        dias[e.modulo].add(e.cuando.date().isoformat())
        if e.tipo == "page":
            crudo[e.modulo][0] += 1
            crudo[e.modulo][2] += max(0, e.visible_ms)
        elif e.tipo == "click":
            crudo[e.modulo][1] += 1

    salida = [
        Adopcion(
            modulo=mod,
            usuarios=len(usuarios[mod]),
            dias=len(dias[mod]),
            visitas=crudo[mod][0],
            clics=crudo[mod][1],
            visible_ms=crudo[mod][2],
        )
        for mod in usuarios
    ]
    return sorted(salida, key=lambda a: (a.usuarios, a.visitas_por_usuario), reverse=True)


def dentro_de(eventos: list[Evento], cuantos: int = 8) -> dict[str, list[tuple[str, int]]]:
    """Qué se pulsa DENTRO de cada pantalla, no en toda la aplicación.

    `mas_pulsado` da un ranking global y lo copan siempre las dos o tres
    pantallas grandes. Esto contesta la otra pregunta, que es la que sirve para
    decidir qué mantener: de los que entran AQUÍ, ¿qué tocan?
    """
    por_modulo: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in eventos:
        if e.tipo == "click" and e.etiqueta:
            por_modulo[e.modulo][e.etiqueta] += 1
    return {
        mod: sorted(etiquetas.items(), key=lambda x: -x[1])[:cuantos]
        for mod, etiquetas in sorted(por_modulo.items(), key=lambda x: -sum(x[1].values()))
    }


def nunca_tocado(eventos: list[Evento], todos_los_modulos: list[str]) -> list[str]:
    """Las pantallas por las que NO ha pasado nadie.

    Es la mitad que ningún ranking enseña: una lista ordenada por uso deja lo
    de cero fuera del final, donde no se ve. Y una pantalla que nadie abre es
    una decisión pendiente.
    """
    vistos = {e.modulo for e in eventos}
    return sorted(m for m in todos_los_modulos if m not in vistos)
