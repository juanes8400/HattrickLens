"""Cuándo un precio cruza el precio de equilibrio de un jugador.

2026-11-21, pedido y definido por el usuario. El aviso del ±5 % dice cuánto se
movió un valor; esto dice algo distinto y más útil para vender: si ese valor
pasó de un lado al otro del precio de equilibrio, lo mínimo por lo que habría
que vender al jugador para no perder dinero.

TRES SEÑALES, cada una frente al mismo umbral:

· el precio por comparables del jugador, que avisa al subir y al bajar;
· lo máximo pagado por un parecido (idéntico o equivalente), igual;
· la puja más alta de un anuncio con pujas en «Esperando su precio», que avisa
  SÓLO AL SUBIR. Una puja no baja nunca: para que la máxima baje, el anuncio
  tiene que cerrarse, y eso se ve después en lo pagado por los parecidos.

CUENTA CUALQUIER CRUCE, también el que provoca el umbral al moverse solo
(decisión del usuario): cada semana el sueldo sube los gastos, y la comisión
del agente baja con los días en el club. Lo que importa es si hoy venderías con
o sin pérdida, mueva lo que mueva.

Funciones puras: lo que se lee de la base llega ya leído.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

Senal = Literal["precio", "maximo", "puja"]
Sentido = Literal["sube", "baja"]


@dataclass(frozen=True, slots=True)
class Cruce:
    ht_player_id: int
    nombre: str
    senal: Senal
    sentido: Sentido
    antes: int
    ahora: int
    equilibrio_antes: int
    equilibrio_ahora: int
    #: Sólo para la puja: cuándo cierra el anuncio que la lleva.
    cierra: datetime | None = None


def sentido_del_cruce(
    antes: int | None,
    equilibrio_antes: int | None,
    ahora: int | None,
    equilibrio_ahora: int | None,
    *,
    solo_subida: bool = False,
) -> Sentido | None:
    """Hacia dónde cruzó, o `None` si sigue del mismo lado o falta un dato.

    Llegar justo al equilibrio cuenta como estar encima: a ese precio no se
    pierde, que es lo que el número promete.
    """
    if antes is None or equilibrio_antes is None or ahora is None or equilibrio_ahora is None:
        return None
    estaba = antes >= equilibrio_antes
    esta = ahora >= equilibrio_ahora
    if esta and not estaba:
        return "sube"
    if estaba and not esta and not solo_subida:
        return "baja"
    return None


# ── La historia de las pujas ────────────────────────────────────────────────


def _utc(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


def _leer(historia: str | None) -> list[list[object]]:
    try:
        datos = json.loads(historia or "[]")
    except ValueError:
        return []
    if not isinstance(datos, list):
        return []
    return [e for e in datos if isinstance(e, list) and len(e) == 2]


def historia_de_pujas(
    historia: str | None,
    *,
    puja_anterior: int | None,
    visto_antes: datetime | None,
    puja: int,
    ahora: datetime,
) -> str:
    """Añade la puja de hoy a la historia del anuncio si cambió.

    Un anuncio guardado antes de que existiera la historia (0118) llega con
    ella vacía: se arranca con lo último que se supo de él y cuándo, que es
    mejor punto de partida que un cero que haría saltar el aviso sin motivo.
    """
    entradas = _leer(historia)
    if not entradas and puja_anterior is not None and visto_antes is not None:
        entradas.append([_utc(visto_antes).isoformat(), int(puja_anterior)])
    if not entradas or entradas[-1][1] != puja:
        entradas.append([_utc(ahora).isoformat(), int(puja)])
    return json.dumps(entradas)


def puja_en(historia: str | None, momento: datetime) -> int | None:
    """La puja que llevaba el anuncio en `momento`, o `None` si todavía no se
    había visto."""
    limite = _utc(momento)
    ultima: int | None = None
    for cuando, puja in _leer(historia):
        try:
            if _utc(datetime.fromisoformat(str(cuando))) > limite:
                break
        except ValueError:
            continue
        ultima = int(puja)  # type: ignore[call-overload]
    return ultima
