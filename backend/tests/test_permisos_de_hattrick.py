"""Qué permisos tiene un acceso, preguntado a Hattrick (`check_token`).

2026-11-19: tras reconectar, el envío seguía pidiendo el permiso de órdenes
de partido. Esto es lo que deja saber si el acceso lo tiene."""

import asyncio
from typing import Any

import httpx

from app.infrastructure.chpp.client import CHPPClient

RESPUESTA = b"""<?xml version="1.0" encoding="utf-8"?>
<HattrickData>
  <FileName>check_token</FileName>
  <Version>1.0</Version>
  <UserID>1</UserID>
  <Token>secreto</Token>
  <Created>2026-03-17 22:29:00</Created>
  <User>1</User>
  <Expires>9999-12-31 23:59:59</Expires>
  <ExtendedPermissions>manage_youthplayers,set_matchorder</ExtendedPermissions>
</HattrickData>"""


class _Falso:
    def __init__(self, estado: int, cuerpo: bytes | None = None, falla: bool = False) -> None:
        self.estado, self.cuerpo, self.falla = estado, cuerpo, falla

    async def get(self, url: str, **_: Any) -> httpx.Response:
        if self.falla:
            raise httpx.ConnectError("caído")
        assert url.endswith("/oauth/check_token.ashx")
        return httpx.Response(self.estado, content=self.cuerpo or b"")


def _con(falso: _Falso) -> list[str] | None:
    cli = CHPPClient("t", "s")
    cli._client = falso  # type: ignore[assignment]
    return asyncio.run(cli.permisos())


def test_lee_los_permisos_separados_por_comas() -> None:
    assert _con(_Falso(200, RESPUESTA)) == ["manage_youthplayers", "set_matchorder"]


def test_solo_lectura_es_una_lista_vacia() -> None:
    cuerpo = RESPUESTA.replace(b"manage_youthplayers,set_matchorder", b"")
    assert _con(_Falso(200, cuerpo)) == []


def test_si_hattrick_no_contesta_no_se_sabe() -> None:
    assert _con(_Falso(0, falla=True)) is None
    assert _con(_Falso(401)) is None
