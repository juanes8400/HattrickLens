"""Método 7: qué entrenar, mirando de qué está hecho cada puntaje.

Firmado por el usuario el 2026-08-26. Sustituye al método 5 --dos umbrales
sueltos, la razón de 4× y la desviación de 0,25-- que funcionaban pero que
nadie podía defender, y al 6, que medía parejas y acababa comparando puntos
con probabilidades: dos monedas distintas en columnas contiguas.

El problema que resuelve
------------------------
La pantalla puntúa las SIETE HABILIDADES y hay que elegir una PAREJA DE
ENTRENAMIENTOS. En ese salto se pierden dos cosas:

1. **Un puntaje puede no ser información.** La escalera de pesos da 27 a un
   canterano bueno y ⅓ a uno sin revelar, así que la ignorancia saca número y
   compite. Y el Bonus Personalizado suma también, aunque no diga nada de los
   chicos: es una preferencia del usuario. Un puntaje hecho de esas dos cosas
   te devuelve tu propia opinión disfrazada de dato. El 2026-08-26 «Balón
   parado» era segunda del ranking con un 21 % de su puntaje puesto a mano.

2. **«Individual» no es una habilidad**, no tiene fila en esa tabla, y por eso
   un ranking NO PUEDE proponerlo nunca. Lo detectó el usuario.

Cómo decide
-----------
Cada hueco mira SU posición del ranking y solo esa:

    principal   = la 1.ª, salvo que esté descartada -> Individual
    secundaria  = la 2.ª, salvo que esté descartada -> Individual

Y descartada significa que el 90 % o más de su puntaje no es respaldo.

**No se baja por el ranking**, a propósito y dicho así por el usuario: si la
2.ª está descartada entra Individual aunque la 3.ª esté viva. La 2.ª es la que
el ranking propone para ese hueco; si no vale, lo que falta no es otra
habilidad, es información.

**Se apaga solo.** Cada techo revelado mueve gente de los cubos de ignorancia
(⅓, ¹⁄₂₇) a los de saber (9, 27): el no-respaldo baja y llega el día en que la
2.ª pasa el filtro sin que nadie toque nada.

El 0,90 NO es un parámetro de pantalla. Con los datos del usuario la
separación real es 14 % · 81 % · y cinco al 100 %: cualquier corte entre 82 y
100 da lo mismo, así que ajustarlo sería fingir una precisión que no existe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

#: No es una habilidad: es el entrenamiento que descubre.
INDIVIDUAL = "individual"

#: Por encima de esto, el puntaje es ignorancia y preferencia, no evidencia.
UMBRAL_DE_DESCARTE = 0.90


@dataclass(frozen=True)
class Habilidad:
    """Una fila de la columna «Puntaje», partida en sus tres sumandos."""

    skill: str
    label: str
    #: Lo que aportan los canteranos en un peldaño conocido Y bueno.
    respaldo: float
    #: Lo que aportan los que nadie ha revelado todavía.
    desconocido: float
    #: El Bonus Personalizado. Cuenta como NO respaldo: es una preferencia del
    #: usuario, no evidencia sobre los chicos.
    bonus: float

    @property
    def puntaje(self) -> float:
        return self.respaldo + self.desconocido + self.bonus

    @property
    def no_respaldo(self) -> float:
        """Qué parte del puntaje no es evidencia. Entre 0 y 1.

        Un puntaje de cero no respalda nada, así que vale 1 --y de paso evita
        la división por cero--.
        """
        total = self.puntaje
        return 1.0 if total <= 0 else (self.desconocido + self.bonus) / total

    @property
    def descartada(self) -> bool:
        return self.no_respaldo >= UMBRAL_DE_DESCARTE


@dataclass(frozen=True)
class Veredicto:
    """Qué entrenar en cada hueco, y por qué."""

    principal: str
    secundaria: str
    motivo: str
    #: Lo que se midió, para que la pantalla lo enseñe sin recalcularlo.
    no_respaldo_principal: float
    no_respaldo_secundaria: float | None

    @property
    def descubre(self) -> bool:
        return INDIVIDUAL in (self.principal, self.secundaria)


def _pct(x: float) -> int:
    return round(x * 100)


def decidir(habilidades: Sequence[Habilidad]) -> Veredicto | None:
    """Aplica el método 7. `None` si no hay ni una habilidad que mirar.

    Sin parámetros: los que la pantalla ofrece --el corte del plazo, la
    separación entre peldaños, el peso del bonus-- ya han hecho su trabajo
    antes, produciendo los puntajes que llegan aquí.
    """
    if not habilidades:
        return None

    orden = sorted(habilidades, key=lambda h: (-h.puntaje, h.skill))
    primera = orden[0]
    segunda = orden[1] if len(orden) > 1 else None

    principal = INDIVIDUAL if primera.descartada else primera.skill
    if segunda is None:
        secundaria = INDIVIDUAL
    else:
        secundaria = INDIVIDUAL if segunda.descartada else segunda.skill

    return Veredicto(
        principal=principal,
        secundaria=secundaria,
        motivo=_motivo(primera, segunda),
        no_respaldo_principal=primera.no_respaldo,
        no_respaldo_secundaria=segunda.no_respaldo if segunda else None,
    )


def _motivo(primera: Habilidad, segunda: Habilidad | None) -> str:
    """La frase que explica el veredicto. Sin esto la recomendación es un
    oráculo: dice qué, nunca por qué, y no se puede discutir con ella."""
    if primera.descartada and (segunda is None or segunda.descartada):
        return (
            f"Ni «{primera.label}», que es la mejor, tiene respaldo: "
            f"{_pct(primera.no_respaldo)} % de su puntaje son canteranos sin revelar y "
            "bonus puesto a mano. No hay nada que construir todavía, así que los dos "
            "huecos van a descubrir."
        )
    if primera.descartada:
        assert segunda is not None
        return (
            f"«{primera.label}» encabeza el ranking pero {_pct(primera.no_respaldo)} % de "
            f"su puntaje no es respaldo, así que el hueco principal va a descubrir. "
            f"«{segunda.label}» sí lo tiene y se queda con el secundario."
        )
    if segunda is None:
        return (
            f"Solo «{primera.label}» tiene puntaje, y con respaldo "
            f"({_pct(primera.no_respaldo)} % de no-respaldo). El segundo hueco va a descubrir."
        )
    if segunda.descartada:
        return (
            f"«{segunda.label}» es la segunda del ranking, pero "
            f"{_pct(segunda.no_respaldo)} % de su puntaje son canteranos sin revelar y "
            "bonus puesto a mano: no hay a quién entrenar ahí. El segundo hueco va a "
            "descubrir."
        )
    return (
        f"«{primera.label}» y «{segunda.label}» tienen respaldo "
        f"({_pct(primera.no_respaldo)} % y {_pct(segunda.no_respaldo)} % de no-respaldo), "
        "así que las dos plazas compran rendimiento de verdad."
    )
