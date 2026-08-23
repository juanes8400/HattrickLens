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
PUESTOS_ENTEROS: dict[str, tuple[str, ...]] = {
    "keeper": ("keeper",),
    "defending": ("wingback", "wingback", "central_defender",
                  "central_defender", "central_defender"),
    "playmaking": ("inner_midfield", "inner_midfield", "inner_midfield"),
    "winger": ("winger", "winger"),
    "passing": ("inner_midfield", "inner_midfield", "inner_midfield",
                "winger", "winger", "forward", "forward", "forward"),
    "scoring": ("forward", "forward", "forward"),
    "set_pieces": ("keeper", "wingback", "wingback", "central_defender",
                   "central_defender", "central_defender", "winger", "winger",
                   "inner_midfield", "inner_midfield", "inner_midfield"),
}
PUESTOS_MEDIOS: dict[str, tuple[str, ...]] = {
    "playmaking": ("winger", "winger"),
    "winger": ("wingback", "wingback"),
}


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
    #: regiones, la secundaria en la tercera.
    elegido_por: str = ""

    @property
    def recibe_doble(self) -> bool:
        return self.racion_principal > 0 and self.racion_secundaria > 0


@dataclass
class PlanDeEntrenamiento:
    principal: str
    secundaria: str
    asignaciones: list[Asignacion] = field(default_factory=list)
    #: Los que no entraron en los once.
    fuera: list[str] = field(default_factory=list)

    @property
    def con_doble(self) -> int:
        return sum(1 for a in self.asignaciones if a.recibe_doble)


REGION_AMBOS = "ambos"
REGION_SOLO_PRINCIPAL = "solo_principal"
REGION_SOLO_SECUNDARIA = "solo_secundaria"
REGION_SIN_ENTRENAMIENTO = "sin_entrenamiento"


def cupos_de(skill: str) -> list[Cupo]:
    """Las plazas de un entrenamiento, enteras primero y medias después."""
    enteros = [Cupo(p, 100) for p in PUESTOS_ENTEROS.get(skill, ())]
    medios = [Cupo(p, 50) for p in PUESTOS_MEDIOS.get(skill, ())]
    esperados = SLOT_CUPOS.get(skill)
    if esperados is not None:
        # La tabla de puestos y la de cuentas tienen que decir lo mismo. Si un
        # dia se toca una y no la otra, que salte aqui y no en la pantalla.
        assert (len(enteros), len(medios)) == esperados, (
            f"{skill}: {len(enteros)}+{len(medios)} contra {esperados[0]}+{esperados[1]}"
        )
    return enteros + medios


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
            ))

    coloca(ambos, _orden_de_cola(cola_principal), REGION_AMBOS)
    coloca(solo_a, _orden_de_cola(cola_principal), REGION_SOLO_PRINCIPAL)
    coloca(solo_b, _orden_de_cola(cola_secundaria), REGION_SOLO_SECUNDARIA)

    # Lo que sobra: las plazas que no entrenan nada, con quien quede.
    restantes = [p for p in cola_principal if p.name not in ya_puestos]
    for jugador in restantes:
        if len(plan.asignaciones) >= plazas:
            break
        ya_puestos.add(jugador.name)
        plan.asignaciones.append(Asignacion(
            player=jugador.name, puesto="", region=REGION_SIN_ENTRENAMIENTO,
            racion_principal=0, racion_secundaria=0,
            peldano=jugador.priority, elegido_por="",
        ))

    plan.fuera = [p.name for p in cola_principal if p.name not in ya_puestos]
    return plan
