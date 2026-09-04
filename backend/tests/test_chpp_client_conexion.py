"""Que un mal rato de Hattrick no desconecte al usuario.

2026-09-04, reportado en producción: «se desconecta a cada rato». La causa
eran dos fallos que se sumaban. En el backend, CUALQUIER 401 de Hattrick
marcaba el token como revocado para siempre; en el frontend, cualquier 401 se
leía como «tu sesión caducó» y echaba al usuario a /welcome. Entre los dos,
un permiso que faltaba para una sola llamada, un límite de peticiones o un
502 pasajero tiraban la sesión entera.

Aquí se vigila la mitad del backend: cuándo se puede decir que un token está
muerto, y qué se hace mientras tanto.
"""

import asyncio

import httpx
import pytest

from app.infrastructure.chpp import client as mod
from app.infrastructure.chpp.client import (
    CHPPAuthError,
    CHPPClient,
    CHPPDeniedError,
    CHPPUnavailableError,
)


def run(coro):
    return asyncio.run(coro)


class _Respuesta:
    """Lo mínimo de httpx.Response que mira el cliente."""

    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content
        self.request = httpx.Request("GET", "https://chpp.hattrick.org/chppxml.ashx")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=self.request, response=None)  # type: ignore[arg-type]


def _cliente(respuestas, monkeypatch):
    """Un CHPPClient cuyo GET devuelve lo que le digamos, en orden.

    `respuestas` es una lista de respuestas o de excepciones a levantar. Se
    guarda además la lista de ficheros pedidos, que es lo que permite ver si
    hubo comprobación del token o reintentos.

    Las credenciales se ponen a mano porque `authlib` exige un `client_id` no
    vacío al construir el cliente. En una máquina con `.env` la de verdad
    estaba ahí y estas pruebas pasaban; en CI no existe y las seis reventaban
    con `Missing "client_id"`. Green en local no probaba nada (2026-09-04).
    """
    monkeypatch.setattr(mod.settings, "chpp_consumer_key", "clave-de-prueba")
    monkeypatch.setattr(mod.settings, "chpp_consumer_secret", "secreto-de-prueba")
    c = CHPPClient("t", "s")
    pedidos: list[str] = []
    cola = list(respuestas)

    async def get(url, params=None, **kw):
        pedidos.append((params or {}).get("file", "?"))
        siguiente = cola.pop(0) if cola else _Respuesta(200, b"<x/>")
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    monkeypatch.setattr(c._client, "get", get)
    monkeypatch.setattr(c, "_parse", lambda file, xml: {"ok": True})
    return c, pedidos


def test_un_401_con_el_token_vivo_no_revoca_la_sesion(monkeypatch) -> None:
    """El caso que desconectaba a la gente.

    Una llamada da 401 porque el token no tiene permiso para ESE fichero. La
    comprobación contra `teamdetails` responde, así que el token está sano y
    lo que procede es negar la operación, no la sesión.
    """
    c, pedidos = _cliente([_Respuesta(401), _Respuesta(200)], monkeypatch)
    with pytest.raises(CHPPDeniedError):
        run(c.fetch("youthplayerlist"))
    # La segunda llamada es la comprobación: se preguntó por el propio equipo.
    assert pedidos == ["youthplayerlist", "teamdetails"]


def test_un_401_con_el_token_muerto_si_revoca(monkeypatch) -> None:
    """Cuando ni siquiera la ficha del propio equipo responde, el token está
    de verdad muerto y hay que volver a autorizar."""
    c, pedidos = _cliente([_Respuesta(401), _Respuesta(401)], monkeypatch)
    with pytest.raises(CHPPAuthError):
        run(c.fetch("players"))
    assert pedidos == ["players", "teamdetails"]


def test_si_la_comprobacion_no_responde_se_supone_que_el_token_vive(monkeypatch) -> None:
    """Ante la duda, el lado prudente.

    Desconectar a alguien cuya sesión estaba bien cuesta rehacer el baile de
    OAuth entero; un error pasajero de más no cuesta nada.
    """
    c, _ = _cliente([_Respuesta(401), httpx.ConnectError("sin red")], monkeypatch)
    with pytest.raises(CHPPDeniedError):
        run(c.fetch("players"))


def test_un_502_se_reintenta_antes_de_darlo_por_perdido(monkeypatch) -> None:
    """El contrato del puerto pedía reintentos con backoff desde el principio
    y no estaban escritos: un 502 llegaba arriba como un fallo de verdad."""
    monkeypatch.setattr(mod, "ESPERA_BASE", 0)
    c, pedidos = _cliente([_Respuesta(502), _Respuesta(200)], monkeypatch)
    assert run(c.fetch("players")) == {"ok": True}
    assert len(pedidos) == 2


def test_un_corte_de_red_se_reintenta_y_al_final_se_rinde(monkeypatch) -> None:
    monkeypatch.setattr(mod, "ESPERA_BASE", 0)
    fallos = [httpx.ConnectError("sin red")] * mod.REINTENTOS
    c, pedidos = _cliente(fallos, monkeypatch)
    with pytest.raises(CHPPUnavailableError):
        run(c.fetch("players"))
    assert len(pedidos) == mod.REINTENTOS


def test_un_404_no_se_reintenta(monkeypatch) -> None:
    """Repetir una petición mal formada da lo mismo tres veces."""
    monkeypatch.setattr(mod, "ESPERA_BASE", 0)
    c, pedidos = _cliente([_Respuesta(404)], monkeypatch)
    with pytest.raises(httpx.HTTPStatusError):
        run(c.fetch("players"))
    assert len(pedidos) == 1
