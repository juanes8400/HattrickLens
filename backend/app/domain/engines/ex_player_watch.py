"""Cuándo un ex-jugador deja de poder darnos dinero.

Diseñado con el usuario el 2026-08-21. Vigilar a un ex-jugador cuesta una
llamada a Hattrick cada vez, así que lo que de verdad importa es saber cuándo
dejar de mirarlo — y eso depende de una sola cosa: si salió de nuestra cantera
o no.

- **Uno cualquiera** nos paga comisión de "club anterior" solo en la
  SIGUIENTE venta, la del club al que se lo vendimos. Ocurrida esa venta, ya
  no hay nada más que esperar de él.
- **Un canterano** nos paga en CADA venta futura, sin límite. No hay una
  última: solo deja de cobrarse cuando el jugador desaparece del juego.

De ahí que el despido (o el retiro, que para el bolsillo es lo mismo) cierre a
cualquiera de los dos, y la reventa cierre solo al primero.
"""
from typing import Literal

Motivo = Literal["revendido", "despedido", "sin_comprador"]

# Hattrick contesta esto al pedir la ficha de alguien que ya no existe:
# despedido por su club o retirado por edad. Verificado en vivo con la cuenta
# del usuario (2026-08-21, jugador 400903807).
CODIGO_JUGADOR_INEXISTENTE = 56


def es_canterano(mother_club_team_id: int | None, nuestro_ht_team_id: int) -> bool:
    """Canterano nuestro = su club de origen es este. Vale para cualquier
    jugador, también los que la app nunca vio en la plantilla."""
    return bool(mother_club_team_id) and mother_club_team_id == nuestro_ht_team_id


def desaparecio_de_hattrick(codigo_de_error: int | None) -> bool:
    """Despedido o retirado: su ficha ya no existe."""
    return codigo_de_error == CODIGO_JUGADOR_INEXISTENTE


def motivo_de_cierre(
    *,
    canterano: bool,
    revendido: bool,
    desaparecido: bool,
    salio_sin_comprador: bool,
) -> Motivo | None:
    """Por qué dejar de vigilarlo, o `None` si hay que seguir mirándolo.

    El orden importa: desaparecer del juego cierra a cualquiera, incluido el
    canterano, y por eso se comprueba primero.
    """
    if desaparecido:
        return "despedido"
    if salio_sin_comprador:
        # Se fue sin que nadie lo comprara: no hubo club anterior al que
        # pagarle. Un canterano tampoco espera nada, porque ya no está en el
        # juego para que lo vendan.
        return "sin_comprador"
    if revendido and not canterano:
        return "revendido"
    return None
