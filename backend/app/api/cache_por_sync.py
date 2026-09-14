"""Caché en memoria que dura hasta el próximo sync (2026-09-14).

Casi todo lo que enseña la app sale de datos que sólo cambian al sincronizar,
y aun así cada visita lo recalculaba: el Dashboard tardaba cinco segundos la
primera vez y otros cinco la segunda. Aquí se guarda cada resultado con el
último sync TERMINADO del equipo en la clave, así que un sync nuevo lo invalida
solo y nunca se enseña nada viejo.

Tres detalles que importan:

  · Cuenta sólo syncs terminados (`completed` o `partial`). Un sync a medias
    ya tiene fila, y guardar un cálculo hecho con datos a medio escribir bajo
    esa clave dejaría la pantalla con datos incompletos hasta el siguiente.
  · Si llegan dos peticiones iguales a la vez --el Dashboard y las alertas
    piden la misma Liga--, se calcula UNA vez y la segunda espera.
  · La base de datos va en la clave. En producción hay una sola; en las
    pruebas cada una crea la suya con los mismos ids, y sin esto se pisarían.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import models as m

#: Tope de vida aunque no llegue un sync nuevo: lo que dependa de la fecha de
#: hoy (una proyección, un plazo) no debe quedarse congelado para siempre.
TTL_MAXIMO = 6 * 3600

_memoria: dict[tuple[Any, ...], tuple[float, Any]] = {}
_en_curso: dict[tuple[Any, ...], asyncio.Future[Any]] = {}


async def ultimo_sync_terminado(session: AsyncSession, team_id: int) -> int | None:
    return await session.scalar(
        select(func.max(m.Sync.id)).where(
            m.Sync.team_id == team_id,
            m.Sync.status.in_(("completed", "partial")),
        )
    )


async def por_sync(
    session: AsyncSession,
    team_id: int,
    nombre: str,
    parametros: tuple[Any, ...],
    calcular: Callable[[], Awaitable[Any]],
    ttl: float = TTL_MAXIMO,
) -> Any:
    """Lo guardado para (equipo, último sync, `nombre`, `parametros`), o se calcula.

    Lo devuelto se comparte entre peticiones: quien lo reciba no debe
    modificarlo."""
    # Sin sesión --una prueba que llama al endpoint a pelo, con la plantilla
    # simulada-- no hay sync que mirar ni base con la que separar: se calcula.
    if session is None:
        return await calcular()
    base = id(getattr(session, "bind", None))
    clave = (base, nombre, team_id, await ultimo_sync_terminado(session, team_id), parametros)
    guardado = _memoria.get(clave)
    if guardado is not None and time.monotonic() - guardado[0] < ttl:
        return guardado[1]

    pendiente = _en_curso.get(clave)
    if pendiente is not None:
        return await asyncio.shield(pendiente)

    futuro: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    _en_curso[clave] = futuro
    try:
        valor = await calcular()
    except Exception as exc:
        futuro.set_exception(exc)
        futuro.exception()  # recogida: si nadie esperaba, no avisa de «nunca leída»
        raise
    except BaseException:
        futuro.cancel()
        raise
    finally:
        _en_curso.pop(clave, None)
    futuro.set_result(valor)

    ahora = time.monotonic()
    # Sin crecer para siempre: fuera lo caducado y lo de syncs anteriores de
    # este mismo cálculo.
    for k in [
        k
        for k, (t, _) in _memoria.items()
        if ahora - t >= TTL_MAXIMO or (k[:3] == clave[:3] and k[3] != clave[3])
    ]:
        del _memoria[k]
    _memoria[clave] = (ahora, valor)
    return valor


def limpiar() -> None:
    """Para las pruebas."""
    _memoria.clear()
    _en_curso.clear()
