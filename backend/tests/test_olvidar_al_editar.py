"""Lo editable de la caché por sync se olvida al editar (2026-11-21).

Pedido del usuario: que las páginas carguen más rápido. La plantilla, el
balance, la ficha y compañía se guardan, y como el usuario puede cambiarlos a
mano sin sincronizar --precios, etapas, grupos--, cualquier edición del equipo
que salga bien los olvida. Lo que no es editable se queda: archivar una alerta
no debe obligar a recalcular el Dashboard.
"""

import asyncio
from collections.abc import Iterator

import pytest
from starlette.requests import Request

from app.api import cache_por_sync as cps


def _guardar(team_id: int, nombre: str) -> None:
    cps._memoria[(0, nombre, team_id, 1, (), "es")] = (0.0, {"x": 1})


def _peticion(metodo: str, ruta: str) -> Request:
    return Request({"type": "http", "method": metodo, "path": ruta, "headers": []})


def _correr(metodo: str, ruta: str, fallar: bool = False) -> None:
    async def go() -> None:
        gen = cps.olvidar_al_editar(_peticion(metodo, ruta))
        await gen.__anext__()
        if fallar:
            with pytest.raises(RuntimeError):
                await gen.athrow(RuntimeError("la edición falló"))
            return
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    asyncio.run(go())


@pytest.fixture(autouse=True)
def _limpio() -> Iterator[None]:
    cps.limpiar()
    yield
    cps.limpiar()


def _nombres(team_id: int) -> set[str]:
    return {k[1] for k in cps._memoria if k[2] == team_id}


def test_una_edicion_olvida_lo_editable_y_nada_mas() -> None:
    for nombre in ("plantilla", "balance", "ficha", "dashboard"):
        _guardar(7, nombre)
    _guardar(8, "plantilla")
    _correr("PATCH", "/api/v1/teams/7/stints/3")
    assert _nombres(7) == {"dashboard"}, "lo no editable se queda"
    assert _nombres(8) == {"plantilla"}, "otro equipo no se toca"


def test_leer_no_olvida_nada() -> None:
    _guardar(7, "plantilla")
    _correr("GET", "/api/v1/teams/7/squad")
    assert _nombres(7) == {"plantilla"}


def test_una_ruta_que_no_es_de_un_equipo_no_olvida_nada() -> None:
    _guardar(7, "plantilla")
    _correr("POST", "/api/v1/feedback")
    assert _nombres(7) == {"plantilla"}


def test_si_alguien_guarda_a_mitad_de_la_edicion_se_olvida_igual() -> None:
    """El segundo olvido, al terminar: lo guardado durante la edición puede
    ser lo de antes de ella."""

    async def go() -> None:
        gen = cps.olvidar_al_editar(_peticion("PUT", "/api/v1/teams/7/player-groups/members/1"))
        await gen.__anext__()
        _guardar(7, "clases-de-jugador")
        with pytest.raises(StopAsyncIteration):
            await gen.__anext__()

    asyncio.run(go())
    assert _nombres(7) == set()
