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


#: El banquillo juvenil: un suplente por puesto, mas uno suelto. Se llena con
#: el MISMO criterio que el once --primero los puestos que reciben los dos
#: entrenamientos, luego los del principal, luego los del secundario, y al
#: final los que no reciben nada-- porque un suplente que entra recibe lo que
#: toque su puesto, y elegirlos por otro orden desperdicia esa entrada.
#:
#: 2026-08-24, pedido asi por el usuario.
#: Uno por puesto y nada mas: un suplente "extra" sin puesto no esta en
#: ninguna region, asi que no recibiria nada, y ocuparlo seria fingir una
#: plaza. Quien no cabe aqui se queda fuera, que es lo mismo pero dicho.
PUESTOS_DE_UN_BANQUILLO: tuple[str, ...] = (
    "keeper", "central_defender", "wingback", "inner_midfield", "winger",
    "forward",
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
#: Los seis puestos, para escribir la tabla de abajo sin repetirse.
POR = "keeper"
DFC = "central_defender"
LAT = "wingback"
MED = "inner_midfield"
EXT = "winger"
DEL = "forward"

#: Cuanto de un entrenamiento le llega a cada puesto, en porcentaje.
#:
#: 2026-08-24, dictada por el usuario. Es la unica tabla del modulo con una
#: opinion sobre las reglas del juego: si algo cambia se corrige AQUI y todo
#: lo demas se recalcula solo.
#:
#: Los valores no se quedan en 100: Balon Parado da 125 al portero. La barra
#: de la pantalla se topea, el numero no.
TODOS = (POR, DFC, LAT, MED, EXT, DEL)


def _mismo(puestos: tuple[str, ...], cuanto: int) -> dict[str, int]:
    return {p: cuanto for p in puestos}


@dataclass(frozen=True)
class Entrenamiento:
    """Un entrenamiento juvenil: que sube, a quien llega y cuanto le da."""

    codigo: str
    skill: str
    label: str
    #: Puesto -> porcentaje. Un puesto que no aparece no recibe nada.
    ritmos: dict[str, int]
    #: Hay un entrenamiento que sube DOS habilidades a ritmos distintos:
    #: «Anotación y balón parado» da 60 de Anotación y 40 de Balón parado.
    #: Se declara una vez, bajo la primera, y aparece como variante de las dos.
    tambien_sube: str | None = None
    ritmos_de_la_otra: dict[str, int] | None = None

    def ritmo(self, puesto: str, skill: str | None = None) -> int:
        """Lo que recibe ese puesto. `skill` elige cual de las dos, si sube dos."""
        if skill is not None and skill == self.tambien_sube:
            return (self.ritmos_de_la_otra or {}).get(puesto, 0)
        return self.ritmos.get(puesto, 0)


ENTRENAMIENTOS: dict[str, Entrenamiento] = {
    e.codigo: e for e in (
        Entrenamiento("keeper", "keeper", "Portería", {POR: 100}),
        Entrenamiento("defending", "defending", "Defensa", {DFC: 100, LAT: 100}),
        Entrenamiento(
            "defending_wide", "defending",
            "Defensa (porteros, defensas y centro del campo completo)",
            _mismo((POR, DFC, LAT, MED, EXT), 80),
        ),
        Entrenamiento("playmaking", "playmaking", "Jugadas", {MED: 100, EXT: 50}),
        Entrenamiento("winger", "winger", "Lateral", {EXT: 100, LAT: 50}),
        Entrenamiento("winger_forwards", "winger", "Lateral (extremos y delanteros)",
                      {EXT: 60, DEL: 60}),
        Entrenamiento("passing", "passing", "Pases",
                      _mismo((MED, EXT, DEL), 100)),
        Entrenamiento(
            "passing_defenders", "passing",
            "Pases (defensas y centro del campo completo)",
            _mismo((DFC, LAT, MED, EXT), 80),
        ),
        Entrenamiento("scoring", "scoring", "Anotación", {DEL: 100}),
        Entrenamiento(
            "scoring_set_pieces", "scoring", "Anotación y balón parado",
            _mismo(TODOS, 60),
            tambien_sube="set_pieces", ritmos_de_la_otra=_mismo(TODOS, 40),
        ),
        Entrenamiento("set_pieces", "set_pieces", "Balón parado",
                      {POR: 125, DFC: 100, LAT: 100, MED: 100, EXT: 100, DEL: 100}),
    )
}

#: El hueco secundario rinde dos tercios de lo que rendiria ese mismo
#: entrenamiento puesto de principal. Baja a la mitad si repites EL MISMO
#: entrenamiento en los dos huecos --el error que Hattrick castiga--; dos
#: entrenamientos distintos que suben la misma habilidad no cuentan como
#: repetir. 2026-08-24, dictado por el usuario.
SECUNDARIO_NORMAL = 2 / 3
SECUNDARIO_DUPLICADO = 1 / 2


def factor_secundario(principal: str, secundaria: str) -> float:
    return (
        SECUNDARIO_DUPLICADO if principal == secundaria else SECUNDARIO_NORMAL
    )


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
    #: Lo que de verdad recibe, ya con el castigo del hueco secundario
    #: aplicado: la celda ensena el producto, no la casilla de la tabla.
    racion_principal: float
    racion_secundaria: float
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
    #: En que se puede convertir, en HTMS28. Es lo que la tabla enseña en vez
    #: de la edad --que va dentro de este numero-- desde el 2026-08-24.
    htms28_min: int = 0
    htms28_max: int = 0
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

    @property
    def doble_a_ciegas(self) -> int:
        """De los que reciben doble racion, a cuantos no se les sabe nada.

        No es un defecto del reparto: la cola los pone ahi a proposito, porque
        entrenar a un desconocido es lo que hace que se revele. Pero quien
        mira la cancha tiene derecho a saber cuanta de esa apuesta es a
        ciegas, que aqui suele ser casi toda.
        """
        return sum(
            1 for a in self.asignaciones
            if a.recibe_doble
            and a.current is None and a.maximum is None and not a.max_reached
        )


REGION_AMBOS = "ambos"
REGION_SOLO_PRINCIPAL = "solo_principal"
REGION_SOLO_SECUNDARIA = "solo_secundaria"
REGION_SIN_ENTRENAMIENTO = "sin_entrenamiento"


#: Cuantas plazas hay de cada puesto en un once juvenil.
CUANTOS_DE_CADA: dict[str, int] = dict(PUESTOS_DE_UN_ONCE)


def cupos_de(clave: str) -> list[Cupo]:
    """Las plazas de un entrenamiento, de mas racion a menos.

    El orden importa: dentro de una region se reparten en este orden, asi que
    quien va primero en la cola cae en la plaza que mas recibe.
    """
    e = _entrenamiento(clave)
    plazas = [
        Cupo(puesto, e.ritmos[puesto])
        for puesto, _ in PUESTOS_DE_UN_ONCE
        for _ in range(CUANTOS_DE_CADA[puesto])
        if e.ritmos.get(puesto, 0) > 0
    ]
    # No se puede entrenar a mas de once: `PUESTOS_DE_UN_ONCE` enumera los
    # puestos POSIBLES --catorce entre todos-- y una alineacion elige once.
    # Sin este tope, «Balón parado», que llega a los seis puestos, repartiria
    # catorce plazas y dejaria de cuadrar con las cuentas de la hoja.
    return sorted(plazas, key=lambda c: -c.racion)[:PLAZAS_DE_UNA_ALINEACION]


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

    # El hueco secundario rinde menos, y lo que se ensena es lo que recibe.
    factor = factor_secundario(principal, secundaria)

    def _rebajado(racion: int) -> float:
        return round(racion * factor, 1)

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
                r_principal, r_secundaria = cupo.racion, _rebajado(cupo.racion_pareja)
            elif region == REGION_SOLO_PRINCIPAL:
                r_principal, r_secundaria = cupo.racion, 0.0
            else:
                r_principal, r_secundaria = 0.0, _rebajado(cupo.racion)
            plan.asignaciones.append(Asignacion(
                player=elegido.name, puesto=cupo.puesto, region=region,
                racion_principal=r_principal, racion_secundaria=r_secundaria,
                peldano=elegido.priority,
                elegido_por=(
                    secundaria if region == REGION_SOLO_SECUNDARIA else principal
                ),
                age_days_total=elegido.age_days_total,
                htms28_min=elegido.htms28_min,
                htms28_max=elegido.htms28_max,
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
            racion_principal=0.0, racion_secundaria=0.0,
            peldano=jugador.priority,
            # Sin entrenamiento no hay habilidad "suya", pero se enseña la
            # principal: es lo que permite compararlo con los que sí entrenan.
            elegido_por=principal,
            age_days_total=jugador.age_days_total,
                htms28_min=jugador.htms28_min,
                htms28_max=jugador.htms28_max,
            current=jugador.current,
            maximum=jugador.maximum,
            max_reached=jugador.max_reached,
        ))

    # El banquillo, con el MISMO criterio que el once: primero los puestos que
    # reciben los dos entrenamientos, luego los del principal, luego los del
    # secundario, y al final los que no reciben nada. Un suplente que entra
    # recibe lo que toque su puesto, asi que el orden importa igual.
    racion_de: dict[str, tuple[str, float, float]] = {}
    for cupo in ambos:
        racion_de.setdefault(
            cupo.puesto,
            (REGION_AMBOS, cupo.racion, _rebajado(cupo.racion_pareja)))
    for cupo in solo_a:
        racion_de.setdefault(
            cupo.puesto, (REGION_SOLO_PRINCIPAL, cupo.racion, 0.0))
    for cupo in solo_b:
        racion_de.setdefault(
            cupo.puesto, (REGION_SOLO_SECUNDARIA, 0.0, _rebajado(cupo.racion)))

    ORDEN = (
        REGION_AMBOS, REGION_SOLO_PRINCIPAL, REGION_SOLO_SECUNDARIA,
        REGION_SIN_ENTRENAMIENTO,
    )
    banquillo = sorted(
        PUESTOS_DE_UN_BANQUILLO,
        key=lambda puesto: ORDEN.index(
            racion_de.get(puesto, (REGION_SIN_ENTRENAMIENTO, 0, 0))[0]
        ),
    )

    for puesto in banquillo:
        region, r_a, r_b = racion_de.get(
            puesto, (REGION_SIN_ENTRENAMIENTO, 0.0, 0.0))
        cola = (
            cola_secundaria if region == REGION_SOLO_SECUNDARIA
            else cola_principal
        )
        elegido = siguiente(_orden_de_cola(cola), vetados(region))
        if elegido is None:
            break
        ya_puestos.add(elegido.name)
        plan.fuera.append(Asignacion(
            player=elegido.name, puesto=puesto, region=region,
            racion_principal=r_a, racion_secundaria=r_b,
            peldano=elegido.priority,
            elegido_por=(
                secundaria if region == REGION_SOLO_SECUNDARIA else principal
            ),
            age_days_total=elegido.age_days_total,
                htms28_min=elegido.htms28_min,
                htms28_max=elegido.htms28_max,
            current=elegido.current, maximum=elegido.maximum,
            max_reached=elegido.max_reached,
        ))

    # Y los que no caben ni en el banquillo: sin puesto ni racion, pero en la
    # lista, que sigue siendo gente de la academia.
    plan.fuera.extend(
        Asignacion(
            player=p.name, puesto="", region=REGION_SIN_ENTRENAMIENTO,
            racion_principal=0.0, racion_secundaria=0.0, peldano=p.priority,
            elegido_por=principal, age_days_total=p.age_days_total,
                htms28_min=p.htms28_min,
                htms28_max=p.htms28_max,
            current=p.current, maximum=p.maximum, max_reached=p.max_reached,
        )
        for p in cola_principal if p.name not in ya_puestos
    )
    return plan
