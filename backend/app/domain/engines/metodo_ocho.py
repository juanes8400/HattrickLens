"""Método 8: qué entrenar, y por qué.

Firmado por el usuario el 2026-08-30. Es la quinta forma de esta decisión y
las cuatro anteriores están retiradas; el historial vive aquí porque cada
descarte enseña algo que no hay que repetir:

- **Ranking puro.** «Individual» no es una habilidad, no tiene fila en la tabla
  de puntajes, y por eso un ranking NO PUEDE proponerlo nunca. Lo detectó el
  usuario y es el defecto que originó todo lo demás.
- **Método 5** (razón de 4× y desviación de 0,25): funcionaba, pero esos dos
  números no salían de ningún sitio.
- **Método 6** (medir cada pareja sobre el once): acababa comparando puntos de
  entrenamiento con probabilidades de descubrir, que son dos monedas
  distintas puestas en columnas contiguas.
- **Método 7**: se quedó sin forma de proponer «doblar» —repetir la habilidad
  por otro camino— y con cinco buenos en una habilidad daba un 40 % menos de
  entrenamiento a los mejores, porque la forma pura solo alcanza cuatro sillas
  y el quinto se quedaba fuera.

Las tres ideas que sobreviven
-----------------------------
1. **No todo puntaje es información.** La escalera da 27 a un canterano bueno
   y ⅓ a uno sin revelar, así que la ignorancia saca número y compite. Y el
   Bonus Personalizado suma sin decir nada de los chicos: es una preferencia
   del usuario. Un puntaje hecho de esas dos cosas te devuelve tu propia
   opinión disfrazada de dato.

2. **Un puntaje alto puede ser una sola persona.** Por eso doblar no se decide
   por el tamaño del número sino quitándole a la habilidad su mejor canterano
   y viendo si aguanta en cabeza. Un excelente solitario da 5,33 de puntaje
   --casi el triple de lo normal-- y no debe doblar: concentraría dos
   entrenamientos en un chico mientras diecisiete siguen a oscuras.

3. **Hay un suelo por debajo del cual no merece la pena entrenar nada.** Sin
   él, una habilidad con un canterano mediano se recomienda igual: su
   no-respaldo se queda en el 82 %, no llega al 90 %, y el descarte no la mata.

No hay ninguna comparación de parejas ni ningún valor esperado: todo sale de
la tabla de puntajes que el usuario ya está viendo.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

#: No es una habilidad: es el entrenamiento que descubre.
INDIVIDUAL = "individual"

#: Los siete peldaños, de mejor a peor. Es el mismo orden que usa la cola de
#: `youth_skill_score`; se repite aquí como lista para poder recorrerla.
ESCALERA: tuple[str, ...] = (
    "excelente",
    "bueno_pronto",
    "bueno_tarde",
    "aceptable_pronto",
    "aceptable_tarde",
    "desconocido_pronto",
    "desconocido_tarde",
)

#: Peldaño 4 o mejor. Es el suelo: por debajo de un «aceptable joven» no hay
#: nada que valga la pena entrenar, y el hueco se cede a Individual.
#:
#: Se lee como SUELO DE LA ESCALERA, no como el cubo exacto: un «bueno» está
#: por encima de un «aceptable joven», así que sería absurdo que lo
#: descalificara.
PELDANOS_APTOS: frozenset[str] = frozenset(ESCALERA[:4])

#: Los cubos que NO son respaldo. Los dos de ignorancia y el de los que ya
#: tocaron techo --que no es que no se sepa, es que se sabe que no sube--.
PELDANOS_SIN_RESPALDO: frozenset[str] = frozenset(
    {"desconocido_pronto", "desconocido_tarde", "al_tope"}
)

#: Por encima de esto, el puntaje es ignorancia y preferencia, no evidencia.
#: No sale a pantalla: con los datos reales la separación es 14 % · 81 % · y
#: cinco al 100 %, así que ajustarlo sería fingir una precisión que no existe.
UMBRAL_DE_DESCARTE = 0.90


@dataclass(frozen=True)
class Habilidad:
    """Una fila de la columna «Puntaje», con sus cubos y su bonus."""

    skill: str
    label: str
    #: Peldaño -> cuántos canteranos. Las claves son las de `Bucket`.
    cubos: Mapping[str, int]
    #: El peso de cada peldaño, ya normalizado igual que en el ranking.
    pesos: Mapping[str, float] = field(repr=False)
    #: Lo que aporta el Bonus Personalizado, ya en unidades de puntaje.
    bonus: float = 0.0

    def puntaje(self, sin_peldano: str | None = None) -> float:
        """El puntaje. `sin_peldano` descuenta UN canterano de ese peldaño.

        Es lo que necesita la prueba de robustez: no hace falta reconstruir la
        academia entera, basta con restar el peso de uno.
        """
        total = self.bonus
        for peldano, cuantos in self.cubos.items():
            n = cuantos - 1 if peldano == sin_peldano else cuantos
            if n > 0:
                total += n * self.pesos.get(peldano, 0.0)
        return total

    @property
    def no_respaldo(self) -> float:
        """Qué parte del puntaje no es evidencia sobre los chicos. De 0 a 1."""
        total = self.puntaje()
        if total <= 0:
            return 1.0
        sin_valor = self.bonus + sum(
            n * self.pesos.get(p, 0.0) for p, n in self.cubos.items() if p in PELDANOS_SIN_RESPALDO
        )
        return sin_valor / total

    @property
    def descartada(self) -> bool:
        return self.no_respaldo >= UMBRAL_DE_DESCARTE

    @property
    def respaldados(self) -> int:
        """Cuántos canteranos tiene en el peldaño 4 o mejor."""
        return sum(n for p, n in self.cubos.items() if p in PELDANOS_APTOS)

    @property
    def apta(self) -> bool:
        return self.respaldados >= 1

    @property
    def mejor_peldano(self) -> str | None:
        """El peldaño más alto que ocupa. `None` si no tiene a nadie."""
        return next((p for p in ESCALERA if self.cubos.get(p, 0) > 0), None)

    @property
    def sirve(self) -> bool:
        """Si puede ocupar un hueco. Si no, lo cede a Individual."""
        return self.apta and not self.descartada


#: Los tres caminos del hueco secundario.
DOBLAR = "doblar"
SEGUNDA = "segunda"
DESCUBRIR = "descubrir"


@dataclass(frozen=True)
class Veredicto:
    principal: str
    secundaria: str
    camino: str
    motivo: str
    #: Los numeritos que lo explican, para que la pantalla no rehaga la cuenta.
    puntaje_principal: float
    no_respaldo_principal: float
    respaldados_principal: int
    #: La prueba de robustez: qué se quitó, cuánto quedó, y quién adelantó.
    peldano_quitado: str | None
    puntaje_sin_el: float
    robusta: bool
    quien_adelanta: str | None
    #: La segunda del ranking, si la hay.
    label_segunda: str | None
    no_respaldo_segunda: float | None
    respaldados_segunda: int | None

    @property
    def descubre(self) -> bool:
        return INDIVIDUAL in (self.principal, self.secundaria)


def decidir(habilidades: Sequence[Habilidad]) -> Veredicto | None:
    """Aplica el método 8. `None` si no hay ni una habilidad que mirar.

    Sin parámetros: los tres que la pantalla ofrece --el corte del plazo, la
    separación entre peldaños y el peso del bonus-- ya hicieron su trabajo
    antes, produciendo los puntajes que llegan aquí.
    """
    if not habilidades:
        return None

    orden = sorted(habilidades, key=lambda h: (-h.puntaje(), h.skill))
    primera = orden[0]
    segunda = orden[1] if len(orden) > 1 else None

    # --- El principal.
    principal = primera.skill if primera.sirve else INDIVIDUAL

    # --- La prueba de robustez: quitarle su mejor canterano y volver a
    # ordenar. Si aguanta en cabeza, su fuerza es un GRUPO y merece doblarse;
    # si se cae, era UN CHICO y no hay nada que concentrar.
    quitado = primera.mejor_peldano
    sin_el = primera.puntaje(quitado)
    rival = max(
        (h for h in habilidades if h is not primera),
        key=lambda h: (h.puntaje(), h.skill),
        default=None,
    )
    robusta = rival is None or sin_el >= rival.puntaje()
    quien = rival.label if (rival is not None and not robusta) else None

    # --- El secundario.
    if robusta and principal != INDIVIDUAL:
        secundaria, camino = primera.skill, DOBLAR
    elif segunda is not None and segunda.sirve:
        secundaria, camino = segunda.skill, SEGUNDA
    else:
        secundaria, camino = INDIVIDUAL, DESCUBRIR

    return Veredicto(
        principal=principal,
        secundaria=secundaria,
        camino=camino,
        motivo=_motivo(primera, segunda, camino, robusta, quien),
        puntaje_principal=primera.puntaje(),
        no_respaldo_principal=primera.no_respaldo,
        respaldados_principal=primera.respaldados,
        peldano_quitado=quitado,
        puntaje_sin_el=sin_el,
        robusta=robusta,
        quien_adelanta=quien,
        label_segunda=segunda.label if segunda else None,
        no_respaldo_segunda=segunda.no_respaldo if segunda else None,
        respaldados_segunda=segunda.respaldados if segunda else None,
    )


def _pct(x: float) -> int:
    return round(x * 100)


def _cuantos(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular}" if n == 1 else f"{n} {plural}"


def _motivo(
    primera: Habilidad,
    segunda: Habilidad | None,
    camino: str,
    robusta: bool,
    quien: str | None,
) -> str:
    """La frase que lo explica. Sin esto la recomendación es un oráculo: dice
    qué, nunca por qué, y no se puede discutir con ella."""
    if not primera.apta:
        return (
            f"«{primera.label}» encabeza el ranking pero no tiene ni un canterano "
            "decente: nadie llega a «aceptable joven». No hay a quién entrenar, "
            "así que los dos huecos van a descubrir."
        )
    if primera.descartada:
        return (
            f"«{primera.label}» encabeza el ranking pero {_pct(primera.no_respaldo)} % de "
            "su puntaje son canteranos sin revelar y bonus puesto a mano. El hueco "
            "principal va a descubrir."
        )
    if camino == DOBLAR:
        return (
            f"«{primera.label}» aguanta en cabeza aunque le quites su mejor canterano "
            f"({primera.puntaje():.2f} → {primera.puntaje(primera.mejor_peldano):.2f}): su "
            f"fuerza es un grupo de {_cuantos(primera.respaldados, 'canterano', 'canteranos')}, "
            "no una persona. Se repite por otro camino para que les alcance a todos."
        )
    if camino == SEGUNDA:
        assert segunda is not None
        return (
            f"«{primera.label}» se cae del primer puesto sin su mejor canterano, así que "
            f"doblarla concentraría en uno solo. «{segunda.label}» tiene respaldo "
            f"({_cuantos(segunda.respaldados, 'canterano', 'canteranos')} en peldaño alto) "
            "y se queda con el secundario."
        )
    # DESCUBRIR
    caida = (
        f"se cae por detrás de «{quien}» si le quitas su mejor canterano"
        if quien
        else "no aguanta sin su mejor canterano"
    )
    if segunda is None:
        return f"Solo «{primera.label}» tiene puntaje, y {caida}. El segundo hueco descubre."
    if not segunda.apta:
        return (
            f"«{primera.label}» {caida}, así que doblarla concentraría en uno solo. Y "
            f"«{segunda.label}», la segunda del ranking, no tiene ni un canterano que "
            "llegue a «aceptable joven». El segundo hueco va a descubrir."
        )
    return (
        f"«{primera.label}» {caida}. Y «{segunda.label}», la segunda del ranking, es "
        f"{_pct(segunda.no_respaldo)} % canteranos sin revelar y bonus. El segundo hueco "
        "va a descubrir."
    )
