"""Método 5: qué entrenar, mirando de qué está hecho cada puntaje.

2026-08-26, diseñado con el usuario. Sustituye a los dos umbrales sueltos de
`decision_individual` --la razón de 4× y la desviación de 0,25-- que
funcionaban pero que nadie podía defender: no salían de ningún sitio.

El problema que resuelve
------------------------
La pantalla puntúa las SIETE HABILIDADES y de ahí hay que sacar una PAREJA DE
ENTRENAMIENTOS, que es lo que de verdad se elige en Hattrick. En ese salto se
pierden dos cosas:

1. **Un puntaje puede ser puro «no sé».** La escalera de pesos da 27 a un
   canterano bueno y ⅓ a uno sin revelar, así que una habilidad de la que no
   se sabe nada saca un número pequeño pero NO nulo. Ordenar por ese número
   pone la ignorancia a competir con el conocimiento, y como la ignorancia
   abunda, gana el segundo puesto. Ejemplo real del 2026-08-26: seis
   habilidades entre 0,238 y 0,280, y las seis con 77-100 % de ignorancia
   dentro. Elegir la «segunda mejor» ahí era echarlo a suertes.

2. **«Individual» no es una habilidad**, así que no tiene fila en esa tabla y
   un ranking no puede proponerlo NUNCA. Lo detectó el usuario.

Cómo decide
-----------
Dos preguntas, y ninguna con un número inventado:

- **Niebla**: qué parte del puntaje viene de canteranos sin revelar. Un
  puntaje mayoritariamente de niebla no es una recomendación, es un hueco.
- **Cuántos valen**: cuántos canteranos están de verdad en un peldaño bueno.
  Es lo que separa «doblar» de «repartir»: doblar concentra la segunda dosis
  en los que ya destacan, y con uno solo esa dosis cae casi toda en gente de
  la que no se sabe nada --que es justo lo que Individual hace mejor--.

El paso 1 mira el PRIMERO; si ni él tiene respaldo, no hay nada que construir
y se descubre con los dos huecos. El paso 2 elige el segundo entre tres
candidatos, en orden de preferencia.

**Se apaga solo.** Cada techo revelado mueve gente de los cubos de ignorancia
(⅓, ¹⁄₂₇) a los de saber (9, 27): la niebla baja, «cuántos valen» sube, y
llega el día en que la segunda habilidad o el doblar pasan el filtro sin que
nadie toque un parámetro.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: No es una habilidad: es el entrenamiento que descubre. Vive aquí repetido
#: --y no importado de `decision_individual`-- para que este módulo no dependa
#: del que viene a sustituir.
INDIVIDUAL = "individual"

#: Por encima de esto, el puntaje es más ignorancia que información y no se
#: puede usar para recomendar. Elegido con el usuario el 2026-08-26: «si más
#: de la mitad del número no es información, no es una recomendación».
NIEBLA_MAXIMA = 0.50

#: Cuántos canteranos buenos hacen falta para que doblar la mejor habilidad
#: tenga sentido. Con menos, la segunda dosis se reparte entre desconocidos y
#: la hace mejor Individual. Elegido con el usuario: tres, que es cuando la
#: concentración alcanza a un grupo y no a un individuo.
MINIMO_PARA_DOBLAR = 3


@dataclass(frozen=True)
class Habilidad:
    """Una fila de la columna «Puntaje», ya desmenuzada."""

    skill: str
    label: str
    puntaje: float
    #: Lo que aportan los canteranos con nota conocida.
    de_saber: float
    #: Lo que aportan los que nadie ha revelado todavía.
    de_no_saber: float
    #: Cuántos están en un peldaño conocido Y bueno.
    cuantos_valen: int

    @property
    def niebla(self) -> float:
        """Qué parte del puntaje no es información. Entre 0 y 1."""
        total = self.de_saber + self.de_no_saber
        # Sin nada que repartir, todo es niebla: un puntaje de cero no
        # respalda ninguna recomendación.
        return 1.0 if total <= 0 else self.de_no_saber / total

    def respaldada(self, niebla_maxima: float = NIEBLA_MAXIMA) -> bool:
        return self.niebla <= niebla_maxima


#: Los tres caminos del segundo hueco, en orden de preferencia.
SEGUNDA_HABILIDAD = "segunda"
DOBLAR = "doblar"
DESCUBRIR = "descubrir"
TODO_NIEBLA = "todo_niebla"


@dataclass(frozen=True)
class Veredicto:
    """Qué entrenar, y por qué. `principal` y `secundario` son HABILIDADES
    --o `INDIVIDUAL`--; elegir la variante concreta del entrenamiento es otra
    decisión y vive en `mejor_variante`."""

    principal: str
    secundario: str
    #: Cuál de los tres caminos ganó. Es lo que la pantalla explica.
    camino: str
    motivo: str
    #: Lo que se midió para decidir, para poder enseñarlo sin recalcularlo.
    niebla_principal: float
    niebla_segunda: float | None
    valen_principal: int

    @property
    def descubre(self) -> bool:
        return INDIVIDUAL in (self.principal, self.secundario)


def _pct(x: float) -> int:
    return round(x * 100)


def decidir(
    habilidades: Sequence[Habilidad],
    *,
    niebla_maxima: float = NIEBLA_MAXIMA,
    minimo_para_doblar: int = MINIMO_PARA_DOBLAR,
) -> Veredicto | None:
    """Aplica el método 5. `None` si no hay con qué decidir.

    Los dos parámetros son opiniones del usuario, no hechos, y por eso entran
    por argumento: la pantalla los expone con una barrita para poder moverlos
    y ver el ranking recalcularse.
    """
    if not habilidades:
        return None

    orden = sorted(habilidades, key=lambda h: (-h.puntaje, h.skill))
    mejor = orden[0]
    # La MEJOR DE LAS RESPALDADAS, no la segunda del ranking. Son cosas
    # distintas y confundirlas costaba recomendaciones: el 2026-08-26 la
    # segunda era «Jugadas» (100 % de niebla) y detras venia «Pases» (77 %),
    # asi que mirar solo a la segunda tiraba la unica candidata con algo de
    # respaldo y saltaba directo a descubrir. Si no hay ninguna respaldada se
    # queda la segunda a secas, que es la que se enseña para explicar el no.
    respaldadas = [h for h in orden[1:] if h.respaldada(niebla_maxima)]
    segunda = respaldadas[0] if respaldadas else (orden[1] if len(orden) > 1 else None)

    # Paso 1. Si ni la mejor tiene respaldo, no hay nada que construir: todo
    # lo que se elija se estará eligiendo a ciegas. Se descubre con los dos
    # huecos, que es lo más rápido para salir de ahí.
    if not mejor.respaldada(niebla_maxima):
        return Veredicto(
            principal=INDIVIDUAL,
            secundario=INDIVIDUAL,
            camino=TODO_NIEBLA,
            motivo=(
                f"Ni «{mejor.label}», que es la mejor, tiene respaldo: "
                f"{_pct(mejor.niebla)} % de su puntaje es gente sin revelar. "
                "No hay nada que construir todavía, así que los dos huecos "
                "van a descubrir."
            ),
            niebla_principal=mejor.niebla,
            niebla_segunda=segunda.niebla if segunda else None,
            valen_principal=mejor.cuantos_valen,
        )

    # Paso 2, candidato 1: la segunda habilidad, si su numero significa algo.
    if segunda is not None and segunda.respaldada(niebla_maxima):
        return Veredicto(
            principal=mejor.skill,
            secundario=segunda.skill,
            camino=SEGUNDA_HABILIDAD,
            motivo=(
                f"«{segunda.label}» tiene respaldo ({_pct(segunda.niebla)} % de "
                "niebla), así que la segunda plaza compra rendimiento de verdad."
            ),
            niebla_principal=mejor.niebla,
            niebla_segunda=segunda.niebla,
            valen_principal=mejor.cuantos_valen,
        )

    # Candidato 2: doblar la mejor. Concentra, asi que solo vale la pena si
    # hay un grupo al que concentrar. Con uno o dos, la segunda dosis cae en
    # desconocidos --y eso lo hace mejor Individual, y mas ancho--.
    if mejor.cuantos_valen >= minimo_para_doblar:
        return Veredicto(
            principal=mejor.skill,
            secundario=mejor.skill,
            camino=DOBLAR,
            motivo=(
                f"Ninguna segunda habilidad tiene respaldo, pero «{mejor.label}» "
                + (
                    f"la tiene {mejor.cuantos_valen} canterano"
                    if mejor.cuantos_valen == 1
                    else f"la tienen {mejor.cuantos_valen} canteranos"
                )
                + ": doblarla concentra la segunda dosis en ellos."
            ),
            niebla_principal=mejor.niebla,
            niebla_segunda=segunda.niebla if segunda else None,
            valen_principal=mejor.cuantos_valen,
        )

    # Candidato 3: descubrir. Lo que queda cuando ni hay segunda de fiar ni
    # gente suficiente a la que concentrar.
    cuantos = mejor.cuantos_valen
    return Veredicto(
        principal=mejor.skill,
        secundario=INDIVIDUAL,
        camino=DESCUBRIR,
        motivo=(
            "Ninguna segunda habilidad tiene respaldo, y "
            + (
                f"«{mejor.label}» la tiene {cuantos} canterano"
                if cuantos == 1
                else f"«{mejor.label}» la tienen {cuantos} canteranos"
            )
            + ": muy poco para que doblar valga la pena. La segunda plaza va a "
            "descubrir."
        ),
        niebla_principal=mejor.niebla,
        niebla_segunda=segunda.niebla if segunda else None,
        valen_principal=cuantos,
    )
