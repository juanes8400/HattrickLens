"""Traduce el once que propone HT Lens al formato con el que Hattrick lo acepta.

2026-09-19, pedido del usuario: un botón de «Enviar alineación». Hattrick sí
deja escribirla (`matchorders`, `actionType=setmatchorder`, con permiso de
escritura), y lo que espera es un JSON con CATORCE ranuras fijas de campo, no
una lista de once. La ranura dice el puesto Y el lado:

    0 portero · 1 lateral derecho · 2 central derecho · 3 central ·
    4 central izquierdo · 5 lateral izquierdo · 6 extremo derecho ·
    7 interior derecho · 8 interior centro · 9 interior izquierdo ·
    10 extremo izquierdo · 11 delantero derecho · 12 delantero centro ·
    13 delantero izquierdo

Ese orden no es una suposición: es el mismo `RoleID` 100-113 que Hattrick
devuelve al leer las órdenes ya enviadas, menos cien. Las ranuras que no se
usan van con `id` 0, que es como el juego dice «vacía».

Lo que este módulo NO hace, a propósito: no DECIDE táctica, ni actitud, ni
capitán, ni lanzadores. Si el usuario los elige en Alineación (2026-11-19,
pedido suyo: táctica, capitán, tiro libre y penales), llegan como argumentos;
lo que no elija se devuelve tal y como vino de sus órdenes actuales. Enviarlo
con valores por defecto sería pisárselo sin que lo pidiera.

VUELVE EL 2026-11-19. Se retiró el 2026-09-20 con el envío entero y se
recupera del commit 2c07e14 para dos cosas: «Mejor alineación» en Rivales y
Copa (sólo `predictratings`, que no guarda nada) y el envío desde Alineación.
El formato se volvió a comprobar en vivo ese día: catorce posiciones,
catorce de banquillo, once lanzadores, `captain`, `setPieces`, `settings` y
`substitutions`, mandado como el campo `lineup` de un POST.
"""

from __future__ import annotations

from typing import Any

#: La orden individual, como la nombra el optimizador, en el código de
#: Hattrick (`MATCH_BEHAVIOUR` en ht_constants).
CODIGO_DE_ORDEN: dict[str, int] = {
    "normal": 0,
    "offensive": 1,
    "defensive": 2,
    "towards_middle": 3,
    "towards_wing": 4,
}

#: Cuántas ranuras de campo lleva el fichero.
RANURAS_DE_CAMPO = 14
#: Y cuántas de banquillo (7 suplentes + 7 reservas) y de lanzadores.
RANURAS_DE_BANQUILLO = 14
RANURAS_DE_LANZADORES = 11

#: Qué ranura ocupa cada puesto, según cuántos haya de ese puesto en el once.
#: El criterio es el del propio juego: con uno solo se juega por el centro
#: (o por la derecha donde no hay centro), y a partir de ahí se abre a los
#: lados. Escrito como tabla porque es una convención, no una fórmula.
RANURAS_POR_PUESTO: dict[str, dict[int, tuple[int, ...]]] = {
    "keeper": {1: (0,)},
    "wingback": {1: (1,), 2: (1, 5)},
    "central_defender": {1: (3,), 2: (2, 4), 3: (2, 3, 4)},
    "winger": {1: (6,), 2: (6, 10)},
    "inner_midfield": {1: (8,), 2: (7, 9), 3: (7, 8, 9)},
    "forward": {1: (12,), 2: (11, 13), 3: (11, 12, 13)},
}

#: El banquillo de Hattrick tiene su propio orden, que NO es el nuestro: el
#: delantero va antes que el extremo, y hay una plaza «extra» que HT Lens no
#: usa. Por eso se mapea por nombre y no por posición en la lista.
ORDEN_DEL_BANQUILLO: tuple[str, ...] = (
    "keeper",
    "central_defender",
    "wingback",
    "inner_midfield",
    "forward",
    "winger",
    "extra",
)


class AlineacionInvalidaError(ValueError):
    """El once no se puede escribir en el formato de Hattrick."""


def _ranura_vacia() -> dict[str, int]:
    return {"id": 0, "behaviour": 0}


def posiciones_de(once: list[dict[str, Any]]) -> list[dict[str, int]]:
    """Las catorce ranuras de campo a partir del once que propone la app.

    `once` son las filas de `/lineup`: cada una con `basePosition` (el puesto
    sin la orden), `behaviour` (la orden, con el nombre del optimizador) y
    `htPlayerId`.
    """
    ranuras = [_ranura_vacia() for _ in range(RANURAS_DE_CAMPO)]
    por_puesto: dict[str, list[dict[str, Any]]] = {}
    for fila in once:
        puesto = str(fila.get("basePosition") or fila.get("base_position") or "")
        if puesto not in RANURAS_POR_PUESTO:
            raise AlineacionInvalidaError(f"puesto desconocido: «{puesto}»")
        por_puesto.setdefault(puesto, []).append(fila)

    for puesto, filas in por_puesto.items():
        reparto = RANURAS_POR_PUESTO[puesto].get(len(filas))
        if reparto is None:
            raise AlineacionInvalidaError(
                f"{len(filas)} jugadores en «{puesto}» no caben en la cancha"
            )
        for indice, fila in zip(reparto, filas, strict=True):
            jugador = int(fila.get("htPlayerId") or fila.get("ht_player_id") or 0)
            if jugador <= 0:
                raise AlineacionInvalidaError(f"falta el jugador de «{puesto}»")
            orden = str(fila.get("behaviour") or "normal")
            if orden not in CODIGO_DE_ORDEN:
                raise AlineacionInvalidaError(f"orden desconocida: «{orden}»")
            ranuras[indice] = {"id": jugador, "behaviour": CODIGO_DE_ORDEN[orden]}
    return ranuras


def banquillo_de(banquillo: list[dict[str, Any]]) -> list[dict[str, int]]:
    """Las catorce ranuras de banquillo.

    HT Lens propone seis plazas (una por puesto) y Hattrick tiene siete más
    siete. Las que no se proponen se dejan vacías: son del usuario y no hay
    por qué rellenárselas.
    """
    por_puesto = {
        str(b.get("slot") or ""): int(b.get("htPlayerId") or b.get("ht_player_id") or 0)
        for b in banquillo
    }
    ranuras = [_ranura_vacia() for _ in range(RANURAS_DE_BANQUILLO)]
    for indice, puesto in enumerate(ORDEN_DEL_BANQUILLO):
        jugador = por_puesto.get(puesto, 0)
        if jugador > 0:
            ranuras[indice] = {"id": jugador, "behaviour": 0}
    return ranuras


def alineacion_para_hattrick(
    once: list[dict[str, Any]],
    banquillo: list[dict[str, Any]],
    *,
    actuales: dict[str, Any] | None = None,
    tactica: int | None = None,
    capitan: int | None = None,
    tiro_libre: int | None = None,
    penales: list[int] | None = None,
) -> dict[str, Any]:
    """El JSON completo que esperan `setmatchorder` y `predictratings`.

    `actuales` son las órdenes que el usuario ya tiene puestas en Hattrick.
    `tactica`, `capitan`, `tiro_libre` y `penales` son lo que eligió en
    Alineación; lo que llegue como `None` se toma de `actuales`. Lo demás
    --actitud, estilo del entrenador, marcaje y cambios programados-- se
    devuelve siempre tal cual venía: enviar la alineación no puede ser una
    excusa para borrarle el resto.
    """
    actuales = actuales or {}
    if penales is None:
        penales = [int(k or 0) for k in (actuales.get("kickers") or [])]
    lanzadores = [k for k in penales if k > 0][:RANURAS_DE_LANZADORES]
    if len(set(lanzadores)) != len(lanzadores):
        raise AlineacionInvalidaError("un jugador aparece dos veces entre los lanzadores")
    return {
        "positions": posiciones_de(once),
        "bench": banquillo_de(banquillo),
        "kickers": [{"id": k, "behaviour": 0} for k in lanzadores]
        + [_ranura_vacia() for _ in range(RANURAS_DE_LANZADORES - len(lanzadores))],
        "captain": int(capitan if capitan is not None else actuales.get("captain") or 0),
        "setPieces": int(tiro_libre if tiro_libre is not None else actuales.get("set_pieces") or 0),
        "settings": {
            "tactic": int(tactica if tactica is not None else actuales.get("tactic_type") or 0),
            "speechLevel": int(actuales.get("attitude") or 0),
            # `newLineup` sirve para guardar el once con nombre. No se usa:
            # sería crear entradas en la cuenta del usuario sin pedírselo.
            "newLineup": "",
            "coachModifier": int(actuales.get("coach_modifier") or 0),
            "manMarkerPlayerId": int(actuales.get("man_marker") or 0),
            "manMarkingPlayerId": int(actuales.get("man_marking") or 0),
        },
        "substitutions": list(actuales.get("substitutions") or []),
    }
