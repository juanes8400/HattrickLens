"""Minutos de un jugador en un partido, a partir de la alineación.

Hattrick no publica los minutos jugados en ningún sitio: `matchlineup.xml` da
el once inicial, la alineación final con estrellas y la lista de cambios, cada
uno con su minuto. Con esas tres cosas los minutos salen exactos, sin estimar
nada.

La dirección del cambio está verificada en vivo contra un partido real de
selección (matchID 41943634, Rwanda, 2026-08-21): `SubjectPlayerID` es quien
SALE --siempre uno del once inicial-- y `ObjectPlayerID` quien ENTRA. Cuando
los dos son el mismo jugador no es un cambio, es una orden de cambiar de
posición o de comportamiento: ahí no sale nadie.

Se cuenta sobre 90 minutos. El descuento existe (`AddedMinutes` en la ficha
del partido) pero no cambia nada aquí: la experiencia pesa los minutos sobre
90 y ese peso ya está topado en 1.
"""
from dataclasses import dataclass

#: Un partido dura esto. Lo que se juegue de más no suma peso.
MINUTOS_DE_UN_PARTIDO = 90


@dataclass(frozen=True)
class Cambio:
    """Un cambio del partido: quién sale, quién entra y en qué minuto."""

    sale: int
    entra: int
    minuto: int

    @property
    def es_cambio_de_verdad(self) -> bool:
        """Mismo jugador a los dos lados = cambio de posición, no de gente."""
        return self.sale != self.entra


def minutos_jugados(
    titulares: set[int] | frozenset[int],
    cambios: list[Cambio],
    ht_player_id: int,
) -> int:
    """Cuántos minutos jugó este jugador. Cero si no llegó a entrar.

    - Titular al que nadie sustituye: los 90.
    - Titular sustituido en el 60: 60.
    - Suplente que entra en el 60: 30.
    - Suplente que nunca entra: 0.

    Un jugador puede entrar y volver a salir (lesión, doble cambio): se cuenta
    desde que entró hasta que salió.
    """
    reales = [c for c in cambios if c.es_cambio_de_verdad]

    entrada = 0 if ht_player_id in titulares else None
    for c in reales:
        if c.entra == ht_player_id and entrada is None:
            entrada = _acotado(c.minuto)
    if entrada is None:
        return 0

    salida = MINUTOS_DE_UN_PARTIDO
    for c in reales:
        if c.sale == ht_player_id:
            minuto = _acotado(c.minuto)
            # Solo cuenta la salida posterior a su entrada: si entró en el 60
            # tras salir otro, una salida anterior no es suya.
            if minuto >= entrada:
                salida = min(salida, minuto)

    return max(0, salida - entrada)


def _acotado(minuto: int) -> int:
    return max(0, min(MINUTOS_DE_UN_PARTIDO, minuto))
