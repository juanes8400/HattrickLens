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
siempre avisa, se pierde la conexión, se apaga el portátil, el móvil mata la
pestaña, así que esperar el aviso de cierre dejaría sesiones abiertas para
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


# ── De dónde es la gente ─────────────────────────────────────────────────────


@dataclass
class UsoDePais:
    """Un renglón por país, para el mapa.

    2026-09-28, pedido del usuario. HT Lens se anuncia en foros de países muy
    distintos y hasta ahora no había forma de saber a cuáles llegó: la tabla de
    personas da nombres, no procedencias. El país no se pregunta ni se deduce de
    la conexión, sale de la liga del club, que es un dato que Hattrick ya da.
    """

    codigo: str
    nombre: str
    usuarios: int = 0
    sesiones: int = 0
    paginas: int = 0
    clics: int = 0
    visible_ms: int = 0

    @property
    def minutos(self) -> float:
        return round(self.visible_ms / 60_000, 1)


def por_pais(eventos: list[Evento], pais_de: dict[int, tuple[str, str]]) -> list[UsoDePais]:
    """Agrupa por país de origen, del que más clics acumula al que menos.

    `pais_de` lleva el país de cada persona; quien no tenga --un club en una
    liga internacional, o alguien que se registró y nunca sincronizó-- cae en
    una fila de código vacío en vez de desaparecer. Sumar mal es peor que decir
    «de éstos no se sabe».
    """
    paises: dict[str, UsoDePais] = {}
    gente: dict[str, set[int]] = defaultdict(set)
    sesiones_de: dict[str, set[str]] = defaultdict(set)

    for e in eventos:
        codigo, nombre = pais_de.get(e.usuario, ("", ""))
        p = paises.setdefault(codigo, UsoDePais(codigo=codigo, nombre=nombre))
        if nombre:
            p.nombre = nombre
        gente[codigo].add(e.usuario)
        sesiones_de[codigo].add(e.sesion)
        if e.tipo == "page":
            p.paginas += 1
            p.visible_ms += max(0, e.visible_ms)
        elif e.tipo == "click":
            p.clics += 1

    for codigo, p in paises.items():
        p.usuarios = len(gente[codigo])
        p.sesiones = len(sesiones_de[codigo])
    # Por clics, que es lo que colorea el mapa; a igualdad, por gente.
    return sorted(paises.values(), key=lambda p: (p.clics, p.usuarios), reverse=True)


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


# ── En el tiempo ─────────────────────────────────────────────────────────────
#
# 2026-10-23, pedido del usuario: «número de usuarios en el tiempo (personas
# activas vs tiempo)». Todo lo de arriba contesta cuánto se usa y quién; nada
# contestaba si eso CRECE. Con un solo número por plazo, doce personas estables
# y doce que llegaron la semana pasada se leen igual.
#
# LA GENTE NO SE SUMA. Es la trampa de esta tabla y la razón de que el grano lo
# calcule el servidor y no la pantalla: quien entra lunes y martes son dos
# renglones diarios y UNA persona en la semana. Agrupar sumando los días daría
# siempre más gente de la que hay, y el error crece justo cuando alguien usa la
# aplicación todos los días, que es el caso que se quiere ver.

#: Los tres granos, con cuánto dura cada uno.
GRANOS = ("day", "week", "month")


def _cubo(cuando: datetime, grano: str) -> str:
    """En qué casilla cae un instante. La clave es la fecha de su comienzo."""
    d = cuando.date()
    if grano == "month":
        return d.replace(day=1).isoformat()
    if grano == "week":
        return (d - timedelta(days=d.weekday())).isoformat()
    return d.isoformat()


def _siguiente(clave: str, grano: str) -> str:
    """La casilla de después, para rellenar los huecos."""
    d = datetime.fromisoformat(clave).date()
    if grano == "month":
        return (d.replace(day=28) + timedelta(days=7)).replace(day=1).isoformat()
    if grano == "week":
        return (d + timedelta(days=7)).isoformat()
    return (d + timedelta(days=1)).isoformat()


@dataclass
class Tramo:
    """Una casilla de la serie: un día, una semana o un mes."""

    #: La fecha de comienzo, en ISO. Es la etiqueta y la clave de orden.
    desde: str
    #: Personas DISTINTAS con actividad. Lo que se pidió.
    usuarios: int = 0
    #: De ésas, las que aparecen por primera vez.
    nuevos: int = 0
    sesiones: int = 0
    paginas: int = 0
    clics: int = 0
    visible_ms: int = 0

    @property
    def minutos(self) -> float:
        return round(self.visible_ms / 60_000, 1)


def en_el_tiempo(
    eventos: list[Evento],
    grano: str = "day",
    estreno_de: dict[int, datetime] | None = None,
) -> list[Tramo]:
    """La serie de personas activas, del tramo más viejo al más nuevo.

    LOS HUECOS SE RELLENAN CON CEROS. Un fin de semana sin nadie no es un tramo
    que no exista: es un cero, y tiene que ocupar su sitio. Sin rellenar, una
    serie de barras a paso fijo pinta tres días sueltos de un mes como si
    fueran tres días seguidos, y eso no es un gráfico incompleto sino uno que
    dice algo falso.

    `estreno_de` lleva la PRIMERA VEZ DE SIEMPRE de cada persona, no la primera
    dentro de estos eventos. Es lo que hace que «nuevos» signifique lo mismo
    mirando siete días o mirando todo: con el primer evento de la lista
    filtrada, un plazo de treinta días estrenaría de golpe a todo el mundo.
    Sin ese dato la columna se queda en cero antes que mentir.
    """
    if grano not in GRANOS:
        grano = "day"
    tramos: dict[str, Tramo] = {}
    gente: dict[str, set[int]] = defaultdict(set)
    sesiones_de: dict[str, set[str]] = defaultdict(set)

    for e in eventos:
        clave = _cubo(e.cuando, grano)
        t = tramos.setdefault(clave, Tramo(desde=clave))
        gente[clave].add(e.usuario)
        sesiones_de[clave].add(e.sesion)
        if e.tipo == "page":
            t.paginas += 1
            t.visible_ms += max(0, e.visible_ms)
        elif e.tipo == "click":
            t.clics += 1

    for clave, t in tramos.items():
        t.usuarios = len(gente[clave])
        t.sesiones = len(sesiones_de[clave])

    if estreno_de:
        for usuario, cuando in estreno_de.items():
            clave = _cubo(cuando, grano)
            if clave in tramos and usuario in gente[clave]:
                tramos[clave].nuevos += 1

    if not tramos:
        return []

    salida: list[Tramo] = []
    clave = min(tramos)
    ultima = max(tramos)
    # Un tope por si acaso: la serie sale de lo que hay guardado, y lo guardado
    # se poda, pero un dato con la fecha torcida no debe poder pedir un millón
    # de casillas vacías.
    while clave <= ultima and len(salida) < 1200:
        salida.append(tramos.get(clave) or Tramo(desde=clave))
        clave = _siguiente(clave, grano)
    return salida
