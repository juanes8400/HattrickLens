"""A quién poner en cada plaza cuando se entrenan DOS cosas a la vez.

2026-08-23, modelo dictado por el usuario. Hattrick juvenil entrena una cosa
principal y otra secundaria, y cada entrenamiento llega a un conjunto de
puestos del campo. Puestos, no habilidades: por eso «Lateral» y «Pases» se
cruzan en los extremos, y por eso la misma habilidad puede entrenarse por dos
caminos distintos («Lateral» y «Lateral (extremos y delanteros)»).

Dibujado como un diagrama de Venn con las dos bolas:

    A ∩ B   los puestos que reciben LOS DOS entrenamientos
    A − B   solo el principal
    B − A   solo el secundario
    fuera   ni uno ni otro

Y se llena en ese orden, sin volver atrás:

1. La intersección primero, que es la plaza más valiosa: doble ración. Ahí van
   los mejores de la cola del PRINCIPAL.
2. `A − B` sigue bajando por esa misma cola: los que venían detrás y no
   cupieron arriba.
3. `B − A` cambia de criterio. Se mira a los que quedaron fuera de las dos
   regiones anteriores y se les ordena por la habilidad SECUNDARIA: gente que
   no valía para lo principal pero sí puede valer para lo otro.
4. Lo que sobre va a los puestos que no entrenan nada.

Los cupos a media ración cuentan como plazas normales; lo único que cambia es
que se llenan al final de su región.
"""
from dataclasses import dataclass, field

from app.domain.engines.youth_skill_score import (
    SLOT_CUPOS,
    PlayerNote,
)

#: Los once de una alineación juvenil. Ninguna región puede repartir más.
PLAZAS_DE_UNA_ALINEACION = 11

#: Cuántos caben de cada puesto, en el orden en que se rellenan las plazas que
#: ningún entrenamiento toca. El portero primero porque un once sin portero no
#: es un once; después el centro de la defensa, que es lo que suele quedar
#: fuera de los entrenamientos de banda.
PUESTOS_DE_UN_ONCE: tuple[tuple[str, int], ...] = (
    ("keeper", 1),
    ("central_defender", 3),
    ("inner_midfield", 3),
    ("forward", 3),
    ("wingback", 2),
    ("winger", 2),
)


#: Qué PUESTOS toca cada entrenamiento, y con cuánta ración. Los números salen
#: de `SLOT_CUPOS`; esto dice a qué puestos corresponden.
#:
#: 2026-08-23. Los dos casos con media ración están comprobados contra la wiki
#: de Hattrick: «Playmaking training trains the skill Playmaking for Inner
#: Midfielders and wingers (half rate)» y «Wing backs receive only half of the
#: training when trained in crossing». Los demás salen de que las cuentas del
#: usuario cuadran exactamente con este reparto: defensa 2 laterales + 3
#: centrales = 5, pases 3 medios + 2 extremos + 3 delanteros = 8, anotación 3
#: delanteros, balón parado los once.
#:
#: Si algún día uno resulta estar mal, se corrige AQUÍ y todo lo demás se
#: recalcula solo — es la única tabla del módulo con una opinión sobre las
#: reglas del juego.
#: Cada ENTRENAMIENTO --no cada habilidad-- con los puestos que toca. La
#: distincion importa: Hattrick entrena la misma habilidad por caminos
#: distintos, y cada camino llega a gente distinta. «Pases» no toca a ningun
#: defensa; «Pases (defensas y centro del campo completo)» si.
#:
#: 2026-08-23, dictado por el usuario. Los dos casos de media racion estan
#: comprobados contra la wiki de Hattrick (ver git). Si alguno cambia, se
#: corrige AQUI y todo lo demas se recalcula solo.
PORTERO = ("keeper",)
DEFENSAS = ("wingback", "wingback", "central_defender", "central_defender",
            "central_defender")
MEDIOS = ("inner_midfield", "inner_midfield", "inner_midfield")
EXTREMOS = ("winger", "winger")
DELANTEROS = ("forward", "forward", "forward")


@dataclass(frozen=True)
class Entrenamiento:
    """Un entrenamiento juvenil: que habilidad sube y a quien alcanza."""

    codigo: str
    skill: str
    label: str
    enteros: tuple[str, ...]
    medios: tuple[str, ...] = ()
    #: Hay un entrenamiento que sube DOS habilidades: «Anotación y balón
    #: parado». Se declara una vez, bajo la primera, y aparece como variante
    #: de las dos.
    tambien_sube: str | None = None


ENTRENAMIENTOS: dict[str, Entrenamiento] = {
    e.codigo: e for e in (
        Entrenamiento("keeper", "keeper", "Portería", PORTERO),
        Entrenamiento("defending", "defending", "Defensa", DEFENSAS),
        Entrenamiento(
            "defending_wide", "defending",
            "Defensa (porteros, defensas y centro del campo completo)",
            PORTERO + DEFENSAS + MEDIOS + EXTREMOS,
        ),
        Entrenamiento("playmaking", "playmaking", "Jugadas", MEDIOS, EXTREMOS),
        Entrenamiento("winger", "winger", "Lateral", EXTREMOS,
                      ("wingback", "wingback")),
        Entrenamiento("winger_forwards", "winger", "Lateral (extremos y delanteros)",
                      EXTREMOS + DELANTEROS),
        Entrenamiento("passing", "passing", "Pases", MEDIOS + EXTREMOS + DELANTEROS),
        Entrenamiento(
            "passing_defenders", "passing",
            "Pases (defensas y centro del campo completo)",
            DEFENSAS + MEDIOS + EXTREMOS,
        ),
        Entrenamiento("scoring", "scoring", "Anotación", DELANTEROS),
        # «Para todos, pero poquito», dicho asi por el usuario: llega a los
        # once y a media racion, que es lo que significa aqui «poquito».
        Entrenamiento(
            "scoring_set_pieces", "scoring", "Anotación y balón parado",
            (), PORTERO + DEFENSAS + MEDIOS + EXTREMOS + DELANTEROS,
            tambien_sube="set_pieces",
        ),
        Entrenamiento("set_pieces", "set_pieces", "Balón parado",
                      PORTERO + DEFENSAS + MEDIOS + EXTREMOS),
    )
}

#: Las variantes de cada habilidad, en el orden en que se declararon. La
#: primera es la forma "normal" y sirve de respaldo.
VARIANTES_POR_HABILIDAD: dict[str, list[str]] = {}
for _e in ENTRENAMIENTOS.values():
    VARIANTES_POR_HABILIDAD.setdefault(_e.skill, []).append(_e.codigo)
    if _e.tambien_sube:
        VARIANTES_POR_HABILIDAD.setdefault(_e.tambien_sube, []).append(_e.codigo)


def _entrenamiento(clave: str) -> Entrenamiento:
    """Acepta el codigo de un entrenamiento o el de una habilidad a secas."""
    if clave in ENTRENAMIENTOS:
        return ENTRENAMIENTOS[clave]
    variantes = VARIANTES_POR_HABILIDAD.get(clave)
    if variantes:
        return ENTRENAMIENTOS[variantes[0]]
    raise KeyError(clave)


@dataclass(frozen=True)
class Cupo:
    """Una plaza concreta que reparte entrenamiento.

    `racion` es la del entrenamiento al que pertenece la plaza: 100 o 50. Los
    de 50 van al final de su región, nunca a otra región. `racion_pareja` solo
    se usa en la intersección, donde la misma plaza recibe de los dos y cada
    uno puede darle una ración distinta.
    """

    puesto: str
    racion: int
    racion_pareja: int = 0


@dataclass(frozen=True)
class Asignacion:
    """Un canterano, su plaza y qué entrenamiento le llega ahí."""

    player: str
    puesto: str
    region: str
    racion_principal: int
    racion_secundaria: int
    #: En qué peldaño venía, y de qué cola salió. Sin esto la pantalla enseña
    #: un nombre en una plaza y no hay forma de saber por qué está ahí.
    peldano: int = 9
    #: La habilidad por la que se le eligió: la principal en las dos primeras
    #: regiones, la secundaria en la tercera. En las plazas que no entrenan se
    #: enseña igualmente la principal, para poder comparar con los demás.
    elegido_por: str = ""
    #: Su edad hoy y lo que el ojeador dijo de ESA habilidad. Es el motivo de
    #: que esté en esa plaza, y sin verlo la lista es una lista de nombres.
    age_days_total: int = 0
    current: int | None = None
    maximum: int | None = None
    max_reached: bool = False

    @property
    def recibe_doble(self) -> bool:
        return self.racion_principal > 0 and self.racion_secundaria > 0


@dataclass
class PlanDeEntrenamiento:
    principal: str
    secundaria: str
    asignaciones: list[Asignacion] = field(default_factory=list)
    #: Los que no entraron en los once, con lo mismo que llevan los de dentro:
    #: en el banquillo tambien hace falta saber quien es cada uno.
    fuera: list[Asignacion] = field(default_factory=list)

    @property
    def con_doble(self) -> int:
        return sum(1 for a in self.asignaciones if a.recibe_doble)


REGION_AMBOS = "ambos"
REGION_SOLO_PRINCIPAL = "solo_principal"
REGION_SOLO_SECUNDARIA = "solo_secundaria"
REGION_SIN_ENTRENAMIENTO = "sin_entrenamiento"


def cupos_de(clave: str) -> list[Cupo]:
    """Las plazas de un entrenamiento, enteras primero y medias despues."""
    e = _entrenamiento(clave)
    return [Cupo(p, 100) for p in e.enteros] + [Cupo(p, 50) for p in e.medios]


def mejor_variante(principal: str, skill_secundaria: str) -> str:
    """De todas las formas de entrenar esa habilidad, la que mas solapa.

    Es la pregunta que resuelve el ejemplo del usuario: con «Defensa» arriba,
    «Pases» a secas no toca a ningun defensa y la interseccion sale VACIA;
    «Pases (defensas y centro del campo completo)» la deja en cinco. Misma
    habilidad, mismo puesto en el ranking, y la diferencia entre cero y cinco.

    A igualdad de solape gana la forma normal, que es la primera declarada:
    sin motivo para complicarse, no se complica.
    """
    variantes = VARIANTES_POR_HABILIDAD.get(skill_secundaria)
    if not variantes:
        return skill_secundaria
    mejor, cuantos = variantes[0], -1
    for codigo in variantes:
        solape = len(_reparte_por_region(principal, codigo)[0])
        if solape > cuantos:
            mejor, cuantos = codigo, solape
    return mejor


def _reparte_por_region(
    principal: str, secundaria: str
) -> tuple[list[Cupo], list[Cupo], list[Cupo]]:
    """Las tres regiones del diagrama, cada una con sus plazas.

    Un puesto está en la intersección cuando los dos entrenamientos lo tocan.
    Se emparejan plaza a plaza: si «Pases» pone tres medios y «Jugadas» pone
    tres medios, son los mismos tres puestos y reciben doble. Y un puesto puede
    ser entero en un entrenamiento y medio en el otro, así que la plaza guarda
    las dos raciones.
    """
    de_a, de_b = cupos_de(principal), cupos_de(secundaria)
    sin_usar_b = list(de_b)

    ambos: list[Cupo] = []
    solo_a: list[Cupo] = []
    for cupo in de_a:
        pareja = next((c for c in sin_usar_b if c.puesto == cupo.puesto), None)
        if pareja is None:
            solo_a.append(cupo)
            continue
        sin_usar_b.remove(pareja)
        ambos.append(Cupo(cupo.puesto, cupo.racion, pareja.racion))
    return ambos, solo_a, sin_usar_b


def _orden_de_cola(jugadores: list[PlayerNote]) -> list[PlayerNote]:
    """La cola ya viene ordenada por los nueve peldaños; aquí solo se copia."""
    return list(jugadores)


def youth_training_plan(
    principal: str,
    secundaria: str,
    cola_principal: list[PlayerNote],
    cola_secundaria: list[PlayerNote],
    *,
    tope_principal: set[str] | None = None,
    tope_secundaria: set[str] | None = None,
    plazas: int = PLAZAS_DE_UNA_ALINEACION,
) -> PlanDeEntrenamiento:
    """El once propuesto: quién ocupa cada plaza y qué entrenamiento recibe.

    `cola_principal` y `cola_secundaria` son las listas que ya ordena
    `score_skills` por los nueve peldaños, cada una para SU habilidad. Aquí no
    se reordena nada: se van tomando por turnos.
    """
    ambos, solo_a, solo_b = _reparte_por_region(principal, secundaria)

    plan = PlanDeEntrenamiento(principal=principal, secundaria=secundaria)
    ya_puestos: set[str] = set()

    tope_a = tope_principal or set()
    tope_b = tope_secundaria or set()

    # Todos los canteranos conocidos, por si una cola se queda corta: una
    # plaza que entrena no puede quedarse vacia habiendo gente libre.
    todos = list(cola_principal) + [
        p for p in cola_secundaria
        if p.name not in {q.name for q in cola_principal}
    ]

    def vetados(region: str) -> set[str]:
        """Quien NO puede ocupar una plaza de esta region.

        El repuesto de arriba es lo que hacia falta vigilar: las colas ya
        vienen sin los que tocaron techo, pero al tirar de `todos` para no
        dejar una plaza vacia se podia colar alguien tapado justo en la
        habilidad que esa plaza entrena.
        """
        if region == REGION_AMBOS:
            return tope_a | tope_b
        if region == REGION_SOLO_PRINCIPAL:
            return tope_a
        if region == REGION_SOLO_SECUNDARIA:
            return tope_b
        return set()

    def siguiente(cola: list[PlayerNote], fuera: set[str]) -> PlayerNote | None:
        for p in cola:
            if p.name not in ya_puestos and p.name not in fuera:
                return p
        for p in todos:
            if p.name not in ya_puestos and p.name not in fuera:
                return p
        return None

    def coloca(cupos: list[Cupo], cola: list[PlayerNote], region: str) -> None:
        for cupo in cupos:
            if len(plan.asignaciones) >= plazas:
                return
            elegido = siguiente(cola, vetados(region))
            if elegido is None:
                return
            ya_puestos.add(elegido.name)
            if region == REGION_AMBOS:
                r_principal, r_secundaria = cupo.racion, cupo.racion_pareja
            elif region == REGION_SOLO_PRINCIPAL:
                r_principal, r_secundaria = cupo.racion, 0
            else:
                r_principal, r_secundaria = 0, cupo.racion
            plan.asignaciones.append(Asignacion(
                player=elegido.name, puesto=cupo.puesto, region=region,
                racion_principal=r_principal, racion_secundaria=r_secundaria,
                peldano=elegido.priority,
                elegido_por=(
                    secundaria if region == REGION_SOLO_SECUNDARIA else principal
                ),
                age_days_total=elegido.age_days_total,
                current=elegido.current,
                maximum=elegido.maximum,
                max_reached=elegido.max_reached,
            ))

    coloca(ambos, _orden_de_cola(cola_principal), REGION_AMBOS)
    coloca(solo_a, _orden_de_cola(cola_principal), REGION_SOLO_PRINCIPAL)
    coloca(solo_b, _orden_de_cola(cola_secundaria), REGION_SOLO_SECUNDARIA)

    # Las plazas que no entrena ninguno de los dos: se deducen de lo que las
    # regiones NO ocuparon. Sin esto, quien cae ahi se quedaba sin puesto y en
    # la cancha no habia donde dibujarlo.
    usados: dict[str, int] = {}
    for a in plan.asignaciones:
        usados[a.puesto] = usados.get(a.puesto, 0) + 1
    libres: list[str] = []
    for puesto, cabidas in PUESTOS_DE_UN_ONCE:
        faltan = cabidas - usados.get(puesto, 0)
        libres.extend([puesto] * max(0, faltan))

    # Lo que sobra: las plazas que no entrenan nada, con quien quede.
    restantes = [p for p in cola_principal if p.name not in ya_puestos]
    for jugador in restantes:
        if len(plan.asignaciones) >= plazas:
            break
        ya_puestos.add(jugador.name)
        plan.asignaciones.append(Asignacion(
            player=jugador.name,
            puesto=libres.pop(0) if libres else "",
            region=REGION_SIN_ENTRENAMIENTO,
            racion_principal=0, racion_secundaria=0,
            peldano=jugador.priority,
            # Sin entrenamiento no hay habilidad "suya", pero se enseña la
            # principal: es lo que permite compararlo con los que sí entrenan.
            elegido_por=principal,
            age_days_total=jugador.age_days_total,
            current=jugador.current,
            maximum=jugador.maximum,
            max_reached=jugador.max_reached,
        ))

    plan.fuera = [
        Asignacion(
            player=p.name, puesto="", region=REGION_SIN_ENTRENAMIENTO,
            racion_principal=0, racion_secundaria=0, peldano=p.priority,
            elegido_por=principal, age_days_total=p.age_days_total,
            current=p.current, maximum=p.maximum, max_reached=p.max_reached,
        )
        for p in cola_principal if p.name not in ya_puestos
    ]
    return plan
