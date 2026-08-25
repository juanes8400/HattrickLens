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

2026-08-25, aportado por el usuario: hay un tercer final definitivo. Un
jugador que se convierte en ENTRENADOR de su equipo actual ya no puede
venderse nunca más, así que tampoco habrá reventa ni comisión. Cierra a
cualquiera de los dos, canterano incluido.
"""
from typing import Literal

Motivo = Literal["revendido", "despedido", "sin_comprador", "entrenador"]

# Hattrick contesta esto al pedir la ficha de alguien que ya no existe:
# despedido por su club o retirado por edad. Verificado en vivo con la cuenta
# del usuario (2026-08-21, jugador 400903807).
CODIGO_JUGADOR_INEXISTENTE = 56

#: Cuanto se espera antes de dar a alguien por "se fue sin que lo compraran".
#:
#: 2026-08-25, caso real: Enyo Kasaliyski se vendio por 4.880.000 y quedo
#: cerrado como `sin_comprador`. Hattrick lo saco de la plantilla, la
#: vigilancia lo miro, y el libro de compraventas todavia no reflejaba la
#: venta --llevaba cinco dias sin leerse por otro fallo--, asi que la unica
#: lectura posible era "se fue y nadie lo compro". Su comision no se habria
#: vigilado jamas.
#:
#: Con el libro leyendose en cada sincronizacion la ventana es de minutos,
#: pero existe. Esperar una semana no cuesta casi nada --sigue en la cola-- y
#: evita cerrar en falso un expediente que da dinero. Quien se fue hace meses
#: sin venta si es un cierre seguro.
DIAS_DE_GRACIA_SIN_COMPRADOR = 7


def es_canterano(mother_club_team_id: int | None, nuestro_ht_team_id: int) -> bool:
    """Canterano nuestro = su club de origen es este. Vale para cualquier
    jugador, también los que la app nunca vio en la plantilla."""
    return bool(mother_club_team_id) and mother_club_team_id == nuestro_ht_team_id


def desaparecio_de_hattrick(codigo_de_error: int | None) -> bool:
    """Despedido o retirado: su ficha ya no existe."""
    return codigo_de_error == CODIGO_JUGADOR_INEXISTENTE


def salio_hace_poco(
    left_at: object | None, ahora: object, dias: int = DIAS_DE_GRACIA_SIN_COMPRADOR
) -> bool:
    """¿Se fue tan hace poco que su venta podria no haberse leido aun?"""
    if left_at is None:
        return False
    return (ahora - left_at).days < dias   # type: ignore[operator]


def es_entrenador(ficha: dict | None) -> bool:
    """¿Se convirtió en entrenador de su equipo?

    Basta con que la ficha traiga el bloque `TrainerData`. Comprobado en vivo
    el 2026-08-25: de los veinticuatro jugadores del equipo lo trae uno solo
    —el entrenador— y la ficha individual de un jugador normal no lo trae en
    absoluto. Puede haber uno por equipo, no más.

    No se mira el nivel: un fixture guardado tenía un bloque con nivel 0 en
    alguien que no era entrenador, pero al pedir su ficha real Hattrick ya no
    devuelve el bloque. Era el fichero de pruebas el que estaba caducado.
    """
    return bool(ficha) and bool(ficha.get("is_player_trainer"))


def motivo_de_cierre(
    *,
    canterano: bool,
    revendido: bool,
    desaparecido: bool,
    salio_sin_comprador: bool,
    entrenador: bool = False,
    recien_salido: bool = False,
) -> Motivo | None:
    """Por qué dejar de vigilarlo, o `None` si hay que seguir mirándolo.

    El orden importa: desaparecer del juego cierra a cualquiera, incluido el
    canterano, y por eso se comprueba primero. Ser entrenador va justo
    después, por el mismo motivo: es definitivo para los dos.
    """
    if desaparecido:
        return "despedido"
    if entrenador:
        return "entrenador"
    if salio_sin_comprador:
        # Se fue sin que nadie lo comprara: no hubo club anterior al que
        # pagarle. Un canterano tampoco espera nada, porque ya no está en el
        # juego para que lo vendan.
        #
        # Salvo que ACABE de irse: la venta puede estar todavía en camino, y
        # cerrar aquí seria enterrar una comisión real. Ver
        # `DIAS_DE_GRACIA_SIN_COMPRADOR`.
        if recien_salido:
            return None
        return "sin_comprador"
    if revendido and not canterano:
        return "revendido"
    return None
