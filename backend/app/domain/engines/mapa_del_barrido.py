"""El mapa de un barrido de comisiones: qué se ha hecho y hasta dónde llega.

2026-08-25. La barra del botón de Transferencias dejó de ser un porcentaje
para ser un mapa: de izquierda a derecha van los ex-jugadores vigilados, del
más reciente al más antiguo, el frente avanza por la izquierda y cada turno al
azar enciende una marca allí donde cayó.

Vive aquí, y no en el navegador, por una razón que costó tres intentos: **el
eje hay que congelarlo al empezar el barrido**. Recalculándolo en cada
pulsación contra la tabla viva, cada expediente que se cierra borra una
casilla, todas las posiciones se corren y las marcas ya pintadas saltan de
sitio o desaparecen. Congelado, la casilla de un jugador es suya hasta que el
barrido termina, se cierre su expediente o no.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Balance:
    """Cómo queda la vigilancia cuando el barrido para.

    Pedido el 2026-08-25, tanto al pulsar «Parar» como al terminar del todo:
    lo que importa no es cuántos se miraron, sino **cuántos siguen pudiendo
    darte dinero** y **cuántos quedan por mirar otro día**.
    """

    abiertos: int
    """Expedientes que siguen vivos: pueden dar comisión en el futuro."""

    por_mirar: int
    """De este barrido, los que se quedaron sin revisar."""

    cerrados: dict[str, int]
    """Los que este barrido dio por zanjados, DESGLOSADOS POR MOTIVO.

    El total no basta: "12 cerrados" puede ser una buena noticia --doce
    revendidos ya cobrados-- o la senal de que algo esta roto, como los 121
    "entrenador" de golpe que delataron el fallo de `TrainerData`.
    """

    comisiones: int
    """Comisiones atribuidas durante este barrido."""

    @property
    def total_cerrados(self) -> int:
        return sum(self.cerrados.values())


@dataclass(frozen=True)
class Mapa:
    """Lo que la barra necesita saber, y nada más."""

    total: int
    """Casillas del eje: el ancho de la barra."""

    hechas: list[int]
    """Posiciones ya atendidas, en orden. Se pintan como marcas."""

    frente: int
    """Cuántas casillas lleva el bloque sólido desde la izquierda."""


def frente_de(hechas: set[int]) -> int:
    """El tramo SEGUIDO desde la izquierda, no el total de atendidos.

    Es lo que distingue el avance del picoteo: una marca suelta a mitad del
    eje no empuja el frente, y por eso se ve de un vistazo que la mitad
    aleatoria está explorando lejos.
    """
    seguidas = 0
    while seguidas in hechas:
        seguidas += 1
    return seguidas


def mapa_de(eje: list[int], atendidos: set[int]) -> Mapa:
    """Traduce el barrido congelado a lo que se pinta.

    `eje` es la cola tal como estaba al empezar, del movimiento más reciente
    al más antiguo. `atendidos` son los ht_player_id ya revisados en ESTE
    barrido —se deduce de la base, no de un contador, para que recargar la
    página no borre lo andado.
    """
    hechas = {i for i, pid in enumerate(eje) if pid in atendidos}
    return Mapa(
        total=len(eje),
        hechas=sorted(hechas),
        frente=frente_de(hechas),
    )


def balance_de(
    mapa: Mapa,
    abiertos: int,
    cerrados: dict[str, int],
    comisiones: int,
) -> Balance:
    """El resumen del barrido, sin volver a preguntarle nada a la base.

    `por_mirar` sale del eje congelado y no de la cola viva: la cola encoge
    también por los cierres, y decir "quedan 12" cuando ocho de esos doce ya
    están zanjados sería mentir sobre el trabajo que falta.
    """
    return Balance(
        abiertos=abiertos,
        por_mirar=max(0, mapa.total - len(mapa.hechas)),
        cerrados=dict(cerrados),
        comisiones=comisiones,
    )
