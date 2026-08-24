"""Qué habilidad conviene entrenar en la academia.

2026-08-17: portado de la hoja de cálculo del usuario (`JUvens.xlsx`, hojas
`Juveniles` y `AuxiJuveniles`), que es la especificación. Aquí no se inventa
nada: cada constante y cada corte sale de una fórmula de esa hoja, y los
comentarios dicen de cuál.

La idea del método: en la academia no se entrena a un jugador, se entrena una
HABILIDAD, y la reciben todos a la vez. Así que la pregunta no es "quién es mi
mejor canterano" sino "en qué habilidad tengo más que ganar" — y eso depende de
cuántos chicos prometen en ella y de cuánto tiempo les queda antes de que se
les acabe el plazo.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.engines import youth_htms as yh

# Las siete habilidades juveniles, en el orden de la hoja.
SKILLS: tuple[str, ...] = (
    "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces",
)

# `AuxiJuveniles!B2` y siguientes: los cortes de calidad sobre la nota por
# habilidad. Son cerrados por abajo y abiertos por arriba (">=7" y "<8").
EXCELLENT_FROM = 8
GOOD_FROM = 7
ACCEPTABLE_FROM = 6

#: El orden en que conviene dar los minutos de UNA habilidad, pedido asi el
#: 2026-08-23. Es una decision distinta de "que habilidad entreno": el puntaje
#: de arriba elige la habilidad, y esto elige a quien se le dan los puestos que
#: reciben ese entrenamiento.
#:
#: Antes esta lista se ordenaba solo por nota, de mayor a menor, con los
#: desconocidos al final. Eso ignoraba el plazo, que es justo lo que decide:
#: entre dos "buenos" iguales, el que se va en cinco semanas necesita los
#: minutos AHORA; el otro los tendra igual mas adelante.
PRIORIDAD_EXCELENTE = 1
PRIORIDAD_BUENO_PRONTO = 2
PRIORIDAD_BUENO_TARDE = 3
PRIORIDAD_ACEPTABLE_PRONTO = 4
PRIORIDAD_ACEPTABLE_TARDE = 5
PRIORIDAD_SIN_DESCUBRIR_PRONTO = 6
PRIORIDAD_SIN_DESCUBRIR_TARDE = 7
PRIORIDAD_INSUFICIENTE = 8
PRIORIDAD_EL_RESTO = 9

INSUFICIENTE = 5


def training_priority(
    note: int | None, *, leaves_soon: bool, max_reached: bool = False
) -> int:
    """A quien darle los minutos de esta habilidad, del primero al ultimo.

    Un techo ya alcanzado NO es "sin descubrir": no es que no se sepa, es que
    se sabe que no va a subir. Entrenarlo es tiempo tirado, asi que va al
    final con el resto, no al cubo de la apuesta.
    """
    if max_reached:
        return PRIORIDAD_EL_RESTO
    if note is None:
        return (
            PRIORIDAD_SIN_DESCUBRIR_PRONTO if leaves_soon
            else PRIORIDAD_SIN_DESCUBRIR_TARDE
        )
    if note >= EXCELLENT_FROM:
        return PRIORIDAD_EXCELENTE
    if note >= GOOD_FROM:
        return PRIORIDAD_BUENO_PRONTO if leaves_soon else PRIORIDAD_BUENO_TARDE
    if note >= ACCEPTABLE_FROM:
        return (
            PRIORIDAD_ACEPTABLE_PRONTO if leaves_soon
            else PRIORIDAD_ACEPTABLE_TARDE
        )
    if note >= INSUFICIENTE:
        return PRIORIDAD_INSUFICIENTE
    return PRIORIDAD_EL_RESTO

# `Juveniles!F3` y `G3`: la edad que TENDRÁ el chico el día que se le acabe el
# plazo, en años y días. El corte de 38 días parte a los que se van pronto de
# los que aún tienen margen — un canterano prometedor al que le quedan tres
# semanas no da tiempo a entrenarlo.
#: El año del corte: sale del juvenil con 17 y pico. `SOON_MAX_DAYS` son los
#: días de ese corte, así que el umbral entero es 17;038 y la comparación es
#: estricta — «menos de 17;038».
#: Un año de Hattrick.
DAYS_PER_HT_YEAR = 112

LEAVE_AGE_YEARS = 17
SOON_MAX_DAYS = 38

# Para quien no se sabe cuándo se podrá promocionar. Tiene que quedar FUERA
# del alcance del mando (0–112 días) a propósito: con el respaldo anterior
# —"un día más que el umbral por defecto"— todos los canteranos sin dato
# volteaban de cubo a la vez justo al pasar de 38 a 39, y la pantalla entera
# daba un salto que parecía un cálculo y era un artefacto del respaldo.
UNKNOWN_DEADLINE_DAYS = 999

# Denominador de `AuxiJuveniles!B11` (`=B2/16`): los conteos se normalizan
# contra el tamaño máximo de una academia, no contra los que hay hoy. Así el
# puntaje no sube sólo por tener pocos canteranos.
SQUAD_NORMALISER = 16


class Bucket(StrEnum):
    """Los siete cubos de `AuxiJuveniles`, del que más pesa al que menos."""

    EXCELLENT = "excelente"
    GOOD_SOON = "bueno_pronto"
    GOOD_LATER = "bueno_tarde"
    ACCEPTABLE_SOON = "aceptable_pronto"
    ACCEPTABLE_LATER = "aceptable_tarde"
    UNKNOWN_SOON = "desconocido_pronto"
    UNKNOWN_LATER = "desconocido_tarde"
    #: Ya llegó a su techo. No es «no se sabe»: se sabe, y se sabe que no
    #: sube. Tiene grupo propio porque compartirlo con los desconocidos hacía
    #: que un canterano tapado EMPUJARA la habilidad hacia arriba en el
    #: ranking, que es exactamente lo contrario de lo que toca.
    AT_MAX = "al_tope"


# Los pesos de `AuxiJuveniles!O11` no son siete números sueltos: son una
# ESCALERA de potencias de una misma base. Escritos como exponentes se ve la
# intención — cada peldaño vale la base entera más que el de abajo, así que un
# solo canterano excelente pesa más que todos los "buenos" juntos. No es una
# media ponderada: es un desempate por niveles escrito como suma.
#
# Con base 3 salen exactamente los 81 / 27 / 9 / 3 / 1 / ⅓ / 1/27 de la hoja,
# y "entrenables" en 1/9 — el peldaño -2, entre los dos desconocidos.
EXPONENTS: dict[str, int] = {
    Bucket.EXCELLENT: 4,
    Bucket.GOOD_SOON: 3,
    Bucket.GOOD_LATER: 2,
    Bucket.ACCEPTABLE_SOON: 1,
    Bucket.ACCEPTABLE_LATER: 0,
    Bucket.UNKNOWN_SOON: -1,
    Bucket.UNKNOWN_LATER: -3,
}
TRAINABLE_EXPONENT = -2

DEFAULT_WEIGHT_BASE = 3.0
# Rango en el que la escalera sigue significando algo. En 1 todos los peldaños
# valen lo mismo: es dejar de priorizar y contar cabezas, que es una postura
# legítima y por eso el mando llega hasta ahí. Por DEBAJO de 1 el orden se
# invertiría —lo malo pesaría más que lo bueno— y eso no significa nada, así
# que ahí se corta. Por arriba, donde la diferencia ya es tan bestia que sólo
# cuenta el primer cubo con algo.
MIN_WEIGHT_BASE = 1.0
MAX_WEIGHT_BASE = 4.0


def weights_for(base: float = DEFAULT_WEIGHT_BASE) -> dict[str, float]:
    """La escalera de pesos para una base dada.

    El grupo de los que ya tocaron techo pesa CERO y no está en la escalera:
    no es un peldaño más bajo, es que no cuenta. Entrenar algo que ya no sube
    no vale nada, y ninguna base debería poder darle valor.
    """
    return {
        **{bucket: base ** exp for bucket, exp in EXPONENTS.items()},
        Bucket.AT_MAX: 0.0,
    }


def trainable_weight_for(base: float = DEFAULT_WEIGHT_BASE) -> float:
    return base ** TRAINABLE_EXPONENT


# Se conservan los valores por defecto como constantes porque hay código y
# pruebas que los leen directamente.
WEIGHTS: dict[str, float] = weights_for()
TRAINABLE_WEIGHT = trainable_weight_for()

@dataclass(frozen=True)
class YouthSkillReading:
    """Lo que se sabe de UNA habilidad de UN canterano."""

    current: int | None
    maximum: int | None
    max_reached: bool = False


@dataclass(frozen=True)
class YouthCandidate:
    name: str
    #  Edad que tendrá al agotarse el plazo (`Juveniles!F` y `G`).
    age_years_at_deadline: int
    age_days_at_deadline: int
    skills: dict[str, YouthSkillReading]
    #  Su edad HOY. Sigue haciendo falta para pintar la ficha.
    age_years: int = 0
    age_days: int = 0

    @property
    def horquilla_htms28(self) -> yh.Horquilla:
        """En que se puede convertir, con lo que se sabe hoy.

        Se deriva de sus habilidades y su edad, que es todo lo que hace falta:
        asi ningun sitio que construya un candidato puede olvidarse de pasarla.

        Sustituye al desempate por edad desde el 2026-08-24. `maximo` lleva la
        edad dentro --pesa casi mil setecientos puntos a los 16-- asi que
        sigue premiando al mas joven, pero ademas descuenta a quien tiene un
        techo bajo confirmado, cosa que la edad sola no sabia hacer.
        """
        return yh.rango_htms28(
            {
                skill: yh.Lectura(
                    current=r.current, maximum=r.maximum,
                    max_reached=r.max_reached,
                )
                for skill, r in self.skills.items()
            },
            self.age_years, self.age_days,
        )

    @property
    def edad_en_dias(self) -> int:
        return self.age_years * DAYS_PER_HT_YEAR + self.age_days


@dataclass(frozen=True)
class PlayerNote:
    """Qué saca UN canterano en UNA habilidad, para decidir a quién dar minutos.

    `note` es `None` cuando el ojeador aún no ha revelado nada de esa
    habilidad — y ese caso importa tanto como los buenos: darle minutos a un
    desconocido es lo que hace que se revele.
    """

    name: str
    note: int | None
    bucket: str
    leaves_soon: bool
    max_reached: bool
    #: Su edad hoy, en días. Se enseña; ya no desempata.
    age_days_total: int = 0
    #: En que se puede convertir, en HTMS28. Desempata dentro del peldaño.
    htms28_min: int = 0
    htms28_max: int = 0
    #: El nivel que tiene en esa habilidad, se entrene o no. `note` vale None
    #: cuando la habilidad ya tocó techo --no hay nada que entrenar-- pero el
    #: número sí se sabe, y es lo que Hattrick enseña junto al candado.
    level: int | None = None
    #: Lo que el ojeador dijo, tal cual: a qué nivel juega hoy y hasta dónde
    #: puede llegar. Se revelan por separado y cualquiera puede faltar. Es lo
    #: que necesita la pantalla para pintar la barra igual en todas partes.
    current: int | None = None
    maximum: int | None = None
    #: Su puesto en la cola de esta habilidad, de 1 a 9. Ver
    #: `training_priority`.
    priority: int = PRIORIDAD_EL_RESTO


@dataclass
class SkillScore:
    skill: str
    counts: dict[str, int]
    score: float
    #  `AuxiJuveniles!M`: cuántos canteranos reciben de verdad este
    #  entrenamiento. En la hoja se teclea a mano; aquí es un dato de entrada,
    #  0 mientras nadie lo aporte — nunca un número inventado.
    trainable_count: float = 0.0
    #  Los canteranos que PUEDEN mejorar en esta habilidad, ordenados por lo
    #  que sacan. No sólo los buenos: incluye a quien todavía no se sabe qué
    #  da, porque darle minutos es lo único que lo revela.
    players: list[PlayerNote] = field(default_factory=list)
    #  Los que ya tocaron techo. No están en `players` --no compiten por unos
    #  minutos que no les servirían de nada-- pero se cuentan para decirlo.
    at_max: list[PlayerNote] = field(default_factory=list)


def skill_note(reading: YouthSkillReading) -> int | None:
    """Nota de una habilidad: SU TECHO, y nada más.

    2026-08-24, corregido a peticion del usuario. Antes era el mayor entre el
    nivel actual y el techo --`MAX(max, actual)` de `Juveniles!AF3`-- y eso
    juntaba dos cosas que no son la misma:

      * a quien juega a 7 con techo 7 --ya llego, no hay nada que ganar-- le
        daba la misma nota que a quien juega a 3 con techo 7, al que le
        quedan cuatro niveles;
      * y hundia a quien tiene el nivel revelado bajo y el techo SIN revelar.
        Caso real: Fabian Ochoa, Pases nivel 2 y techo desconocido, caia al
        ultimo peldaño como si el 2 fuera su limite. Nadie dijo eso: un 2 solo
        fija un suelo, su techo puede ser 8.

    Lo que decide cuanto vale desarrollar a alguien es hasta donde puede
    llegar. `None` es "no se sabe", que NO es lo mismo que un techo bajo y
    tiene su propio cubo, entre "aceptable" e "insuficiente".

    Un techo ya alcanzado tambien anula la nota: entrenar algo que no va a
    subir es tiempo tirado, por alto que este.
    """
    if reading.max_reached:
        return None
    return reading.maximum or None


def bucket_of(
    note: int | None, *, leaves_soon: bool, max_reached: bool = False
) -> str:
    """El cubo de `AuxiJuveniles` al que cae una nota."""
    if max_reached:
        return Bucket.AT_MAX
    if note is None:
        return Bucket.UNKNOWN_SOON if leaves_soon else Bucket.UNKNOWN_LATER
    if note >= EXCELLENT_FROM:
        # El excelente NO se parte por plazo: `AuxiJuveniles!B2` es un COUNTIF
        # sin filtro de edad, a diferencia del resto que son COUNTIFS. Un
        # crack se aprovecha aunque quede poco.
        return Bucket.EXCELLENT
    if note >= GOOD_FROM:
        return Bucket.GOOD_SOON if leaves_soon else Bucket.GOOD_LATER
    if note >= ACCEPTABLE_FROM:
        return Bucket.ACCEPTABLE_SOON if leaves_soon else Bucket.ACCEPTABLE_LATER
    # Por debajo de "aceptable" la hoja no cuenta nada: ni siquiera entra como
    # desconocido, porque no lo es — se sabe, y se sabe que no sirve.
    return ""


def leaves_soon(
    candidate: YouthCandidate, *, soon_max_days: int = SOON_MAX_DAYS
) -> bool:
    """¿Sale con menos de 17;038?

    2026-08-23, corregido: lo que importa no es «se va pronto» sino la EDAD a
    la que sale, y la edad son dos números. Antes se miraba solo el de los
    días --`age_days_at_deadline <= 38`-- así que alguien que saliera con
    18;010 contaba igual que uno de 17;010: diez es menos que treinta y ocho.
    En esta academia todos salen con 17;xxx y por eso no se veía.

    El corte es estricto, como se dijo: «menos de 17;038».
    """
    return (candidate.age_years_at_deadline, candidate.age_days_at_deadline) < (
        LEAVE_AGE_YEARS, soon_max_days
    )


def score_skills(
    candidates: list[YouthCandidate],
    trainable: dict[str, float] | None = None,
    *,
    soon_max_days: int = SOON_MAX_DAYS,
    weight_base: float = DEFAULT_WEIGHT_BASE,
    trainable_weight: float | None = None,
) -> list[SkillScore]:
    """Una nota por habilidad, de la que más conviene entrenar a la que menos.

    `trainable` es el conteo de `AuxiJuveniles!M` — cuántos canteranos reciben
    realmente ese entrenamiento. Si no se aporta vale 0 y ese sumando no
    participa; el resto del puntaje es idéntico.

    `soon_max_days` y `weight_base` son los dos números que el usuario puede
    mover. El MÉTODO no cambia —la escalera de potencias, los cubos, la nota
    por habilidad— pero dónde se pone el corte del plazo y cuánto separa un
    peldaño del siguiente es una opinión, y cada uno tiene la suya.
    """
    trainable = trainable or {}
    weights = weights_for(weight_base)
    # El peso del bonus lo SUGIERE la escalera (peldaño -2), pero se puede
    # mover aparte: es el único sumando que no describe a la cantera sino a
    # cuánto quiere pesar el usuario ese criterio.
    peso_bonus = (
        trainable_weight_for(weight_base) if trainable_weight is None else trainable_weight
    )
    out: list[SkillScore] = []
    for skill in SKILLS:
        counts = {b.value: 0 for b in Bucket}
        names: list[PlayerNote] = []
        tapados: list[PlayerNote] = []
        for candidate in candidates:
            horquilla = candidate.horquilla_htms28
            reading = candidate.skills.get(skill)
            if reading is None:
                continue
            note = skill_note(reading)
            pronto = leaves_soon(candidate, soon_max_days=soon_max_days)
            bucket = bucket_of(
                note, leaves_soon=pronto, max_reached=reading.max_reached
            )
            # Quien ya toco techo no compite por estos minutos: no le
            # servirian de nada. Se aparta, no se pone el ultimo.
            destino = tapados if reading.max_reached else names
            destino.append(
                PlayerNote(
                    name=candidate.name,
                    note=note,
                    bucket=bucket,
                    leaves_soon=pronto,
                    max_reached=reading.max_reached,
                    age_days_total=candidate.edad_en_dias,
                    htms28_min=horquilla.minimo,
                    htms28_max=horquilla.maximo,
                    level=max(reading.current or 0, reading.maximum or 0) or None,
                    current=reading.current,
                    maximum=reading.maximum,
                    priority=training_priority(
                        note, leaves_soon=pronto, max_reached=reading.max_reached
                    ),
                )
            )
            if bucket:
                counts[bucket] += 1

        trainable_count = float(trainable.get(skill, 0.0))
        score = sum(
            weights[bucket] * counts[bucket] / SQUAD_NORMALISER for bucket in counts
        ) + peso_bonus * trainable_count / SQUAD_NORMALISER
        out.append(
            SkillScore(
                skill=skill,
                counts=counts,
                # Sin redondear: el dominio calcula y la capa que lo pinta
                # decide cuántos decimales enseñar. Redondear aquí a seis
                # cifras rompía la comparación contra la hoja, que trabaja en
                # doble precisión.
                score=score,
                trainable_count=trainable_count,
                # Por la cola de `training_priority`, dentro de cada peldaño
                # por nota, y a igualdad de nota POR EDAD: primero el más
                # joven, que es al que le queda más por crecer. El nombre solo
                # decide entre dos que nacieron el mismo día.
                #
                # 2026-08-23: el desempate por edad faltaba y el orden acababa
                # siendo alfabético. Gustavo Obregón, el más joven de la
                # cantera, salía quinto detrás de Antonio, Carlos y Fabián.
                # Peldaño, techo, HTMS28 maximo, y por ultimo el nivel
                # actual --el mas cerca del techo primero: entre dos que van a
                # acabar en el mismo sitio, entra el que esta a punto de
                # rematarlo--.
                #
                # 2026-08-24: el tercer criterio era la edad de hoy. Ahora es
                # el HTMS28 maximo, que la lleva dentro --y pesa mas que nada
                # a estas edades-- pero ademas descuenta a quien tiene un
                # techo bajo confirmado, cosa que la edad sola no sabia hacer.
                players=sorted(
                    names,
                    key=lambda p: (
                        p.priority,
                        -(p.note or 0),
                        -p.htms28_max,
                        -(p.current or 0),
                        p.name,
                    ),
                ),
                at_max=sorted(tapados, key=lambda p: p.name),
            )
        )
    # De mayor a menor. El desempate es el orden de `SKILLS`, no un `RAND()`
    # como en la hoja: una lista que se reordena sola en cada recarga sería
    # imposible de leer.
    return sorted(out, key=lambda s: -s.score)


# ── De dónde sale el número de "entrenables" ────────────────────────────────
#
# 2026-08-17, pedido explícito: ese conteo deja de ser un número tecleado y
# pasa a elegirse con un método. Todos devuelven un valor por habilidad en la
# MISMA escala 0–`SQUAD_NORMALISER`, para que cambiar de método cambie el
# criterio y no las unidades — si uno devolviera decenas y otro unidades, el
# sumando pesaría distinto por accidente y no por decisión.

class TrainableMethod(StrEnum):
    # 1 (RECEIVERS) y 2 (RIVALS) están definidos pero aún no se pueden
    # calcular: el primero necesita la alineación juvenil —CHPP no la manda en
    # youthplayerlist— y el segundo unas estadísticas que el usuario aportará.
    # No se listan como opción hasta que devuelvan un número real: una opción
    # que siempre da 0 no es una opción, es una trampa.
    SLOTS = "slots"          # 1b: plazas que entrena cada entrenamiento
    ATTACK = "attack"        # 3: aporte de esa habilidad al ataque
    MIDFIELD = "midfield"    # 4: al mediocampo
    DEFENCE = "defence"      # 5: a la defensa
    SENIOR = "senior"        # 6: lo que entrena el primer equipo
    EDIT = "edit"            # 7: a mano


# Cuántos jugadores de una alineación reciben de verdad cada entrenamiento.
# No sale de la cantera de nadie: es cómo reparte Hattrick el entrenamiento por
# puesto —el portero entrena solo él, el balón parado les llega a los once— así
# que son números fijos y no dependen del equipo.
#: A cuantas plazas llega cada entrenamiento, en el formato X+Y del usuario:
#: X son los cupos que entrenan al 100% y Y los que entrenan a media racion.
#: Los medios CUENTAN como plazas --por eso se suman aqui-- y lo unico que los
#: distingue es que se llenan al final de su cola (ver `youth_training_plan`).
#:
#: 2026-08-23, corregido por el usuario: Lateral pasa de 3 a 2+2, o sea 4.
SLOT_CUPOS: dict[str, tuple[int, int]] = {
    "keeper": (1, 0),
    "defending": (5, 0),
    "playmaking": (3, 2),
    "winger": (2, 2),
    "passing": (8, 0),
    "scoring": (3, 0),
    "set_pieces": (11, 0),
}

SLOT_TRAINABLES: dict[str, float] = {
    skill: float(enteros + medios) for skill, (enteros, medios) in SLOT_CUPOS.items()
}


def slot_trainable() -> dict[str, float]:
    """Método 1b: a cuántas plazas de la alineación le llega cada entrenamiento.

    La versión fija del método 1. El de verdad —cuántos de MIS canteranos lo
    reciben— necesita la alineación juvenil, que CHPP no manda; éste responde a
    la misma pregunta con el reparto del juego, que no cambia de equipo a
    equipo.
    """
    return dict(SLOT_TRAINABLES)


def senior_trainable(skill: str | None) -> dict[str, float]:
    """Método 6: todo el peso a lo que entrena el primer equipo.

    16 contra 0, sin medias tintas — es la opción de quien quiere que la
    cantera vaya en la misma dirección que el equipo grande y no se plantea
    matices. Si no se sabe qué entrena el primer equipo, no se empuja nada.
    """
    return {s: (float(SQUAD_NORMALISER) if s == skill else 0.0) for s in SKILLS}


# Qué sectores del motor de posiciones componen cada bloque del campo.
SECTORS_BY_BLOCK: dict[str, tuple[str, ...]] = {
    TrainableMethod.ATTACK: ("central_attack", "side_attack"),
    TrainableMethod.MIDFIELD: ("midfield",),
    TrainableMethod.DEFENCE: ("central_defence", "side_defence"),
}


def block_trainable(
    block: str, positions: dict[str, dict[str, dict[str, float]]]
) -> dict[str, float]:
    """Cuánto pesa cada habilidad en un bloque del campo, en escala 0–16.

    `positions` es posición -> sector -> habilidad -> coeficiente, tal cual lo
    declara la matriz del Manual.

    Se toma el MÁXIMO entre posiciones, no la suma. La pregunta que responde
    es "¿cuán determinante es esta habilidad ALLÍ DONDE SE USA?", no "¿cuánto
    pesa en el conjunto del catálogo de posiciones?".

    2026-08-17, elegido tras comparar los dos criterios con datos reales: la
    suma premiaba a las habilidades repartidas entre muchas posiciones y
    castigaba a las concentradas en una. La portería salía 2 sobre 16 —sólo un
    puesto la usa— y con eso entrenar portería no se recomendaría JAMÁS, que
    es un artefacto del criterio y no una verdad del juego. Con el máximo sale
    16, que es lo que de verdad vale en un portero. En ataque también cambia el
    orden: anotación pasa por delante de lateral, porque en un delantero es lo
    más determinante mientras lateral se reparte entre cuatro puestos.

    Dentro de UNA MISMA posición sí se suman los sectores del bloque: un
    interior aporta a ataque central y a ataque lateral, y las dos cosas son
    ataque suyo.

    Una habilidad que no aparece en ninguna posición da 0, y eso es un dato: el
    balón parado no contribuye a ningún sector del campo, así que bajo estos
    métodos no puntúa por ahí — puntúa por lo que ya tienen los canteranos.
    """
    sectors = SECTORS_BY_BLOCK.get(block, ())
    totals = {
        skill: max(
            (
                sum(spec.get(sector, {}).get(skill, 0.0) for sector in sectors)
                for spec in positions.values()
            ),
            default=0.0,
        )
        for skill in SKILLS
    }
    top = max(totals.values(), default=0.0)
    if top <= 0:
        return {skill: 0.0 for skill in SKILLS}
    # Sin redondear: el aporte de una habilidad a un bloque es una proporción,
    # y truncarla a entero perdía la diferencia entre habilidades vecinas —
    # 10,7 y 10,4 no son "11 y 10", son casi lo mismo.
    return {
        skill: value / top * SQUAD_NORMALISER for skill, value in totals.items()
    }
