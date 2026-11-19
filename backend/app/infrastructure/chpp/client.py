"""Adapter CHPP: OAuth 1.0a (HMAC-SHA1) + descarga de XML.

Endpoints oficiales:
  request_token: https://chpp.hattrick.org/oauth/request_token.ashx
  authorize:     https://chpp.hattrick.org/oauth/authorize.aspx
  access_token:  https://chpp.hattrick.org/oauth/access_token.ashx
  recursos:      https://chpp.hattrick.org/chppxml.ashx?file=<name>
"""

import asyncio
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth1Client

from app.core.config import settings

#: Cuántas veces se pide un fichero antes de darlo por perdido, y cuánto se
#: espera entre intentos (se dobla cada vez: 0,5s y 1s).
REINTENTOS = 3
ESPERA_BASE = 0.5


class CHPPAuthError(Exception):
    """El token está muerto: hay que volver a autorizar la aplicación.

    Sólo se levanta cuando se ha COMPROBADO que lo está. Marcar un token como
    revocado desconecta al usuario y le obliga a rehacer el baile de OAuth, y
    hasta el 2026-09-04 bastaba un 401 cualquiera de Hattrick para hacerlo:
    un permiso que faltaba para esa llamada concreta, un límite de peticiones
    o un mal rato del servidor tiraban la sesión entera.
    """


class CHPPDeniedError(Exception):
    """Hattrick dijo 401 pero el token sigue vivo.

    Es lo que contesta una llamada que pide algo para lo que el token no tiene
    permiso. No se arregla reconectando ni esperando: se arregla no haciendo
    esa llamada, así que quien la haga decide qué contar. Lo que NO puede
    hacer es dar la sesión por perdida.
    """


class CHPPUnavailableError(Exception): ...


class CHPPClient:
    def __init__(self, token: str, token_secret: str) -> None:
        self._client = AsyncOAuth1Client(
            client_id=settings.chpp_consumer_key,
            client_secret=settings.chpp_consumer_secret,
            token=token,
            token_secret=token_secret,
            signature_method="HMAC-SHA1",
            headers={"User-Agent": settings.chpp_user_agent},
            timeout=15.0,
        )

    async def fetch(
        self,
        file: str,
        version: str = "latest",
        *,
        parse_as: str | None = None,
        **params: Any,
    ) -> dict[str, Any]:
        """Pide un fichero a CHPP y lo lee.

        `parse_as` existe para `actionType=viewOldies`: se pide `players.xml`
        pero se lee con un lector propio. Ampliar el de `players` cambiaria
        `content_hash` y reescribiria una foto de cada jugador del equipo sin
        que hubiera cambiado nada.
        """
        url = f"{settings.chpp_base_url}/chppxml.ashx"
        query = {"file": file, **({} if version == "latest" else {"version": version}), **params}
        resp = await self._get_con_reintentos(url, query)
        if resp.status_code == 401:
            # Un 401 NO significa por sí solo que el token esté revocado, y
            # tratarlo así desconectaba al usuario cada dos por tres. Se
            # comprueba preguntando por la ficha del propio equipo, que no
            # necesita ningún permiso especial: si eso responde, el token vive
            # y el 401 era de esta llamada concreta (2026-09-04).
            if await self._token_sigue_vivo():
                raise CHPPDeniedError(f"Hattrick negó «{file}» con este token")
            raise CHPPAuthError("token revocado, requiere re-autorización")
        resp.raise_for_status()
        return self._parse(parse_as or file, resp.content)  # bytes: el XML declara su encoding

    async def _get_con_reintentos(self, url: str, query: dict[str, Any]) -> httpx.Response:
        """Lo pasajero se reintenta antes de darlo por un fallo.

        El contrato del puerto (`app/domain/ports/chpp_gateway.py`) ya pedía
        «retries con backoff» desde el principio; no estaban escritos. Un
        corte de red de un segundo o un 502 de Hattrick llegaban arriba como
        un error de verdad y, con la plantilla a medio sincronizar, dejaban al
        usuario mirando una pantalla rota.
        """
        ultimo: Exception | None = None
        for intento in range(REINTENTOS):
            try:
                resp = await self._client.get(url, params=query)
            except httpx.TransportError as exc:
                ultimo = exc
            else:
                # 401 y 4xx no se reintentan: repetir lo mismo da lo mismo.
                if resp.status_code < 500:
                    return resp
                ultimo = httpx.HTTPStatusError(
                    f"Hattrick devolvió {resp.status_code}", request=resp.request, response=resp
                )
            if intento < REINTENTOS - 1:
                await asyncio.sleep(ESPERA_BASE * 2**intento)
        raise CHPPUnavailableError(str(ultimo))

    async def _token_sigue_vivo(self) -> bool:
        """Una sola llamada barata para separar «no puedes» de «ya no eres».

        `teamdetails` es lo primero que se pide al conectar y no necesita
        ningún permiso extra: si contesta, el token es válido. Ante la duda
        --la comprobación falla, Hattrick no responde-- se devuelve `True`,
        que es el lado prudente: mejor un error pasajero que desconectar a
        alguien cuya sesión estaba bien.
        """
        try:
            resp = await self._client.get(
                f"{settings.chpp_base_url}/chppxml.ashx", params={"file": "teamdetails"}
            )
        except httpx.TransportError:
            return True
        return resp.status_code != 401

    async def permisos(self) -> list[str] | None:
        """Los permisos extra que Hattrick dice que tiene este acceso.

        2026-11-19: tras reconectar, el envío de la alineación seguía diciendo
        que faltaba el permiso, y desde la app no había forma de saber si el
        acceso lo tenía o no. `oauth/check_token.ashx` lo dice: trae
        `ExtendedPermissions` con los permisos separados por comas
        («manage_youthplayers,set_matchorder»). Sólo lectura.

        `None` si Hattrick no contesta: no saberlo no es lo mismo que no tenerlo.
        """
        from xml.etree.ElementTree import ParseError  # noqa: S405, sólo la excepción

        from defusedxml import ElementTree

        try:
            resp = await self._client.get(f"{settings.chpp_base_url}/oauth/check_token.ashx")
        except httpx.TransportError:
            return None
        if resp.status_code != 200:
            return None
        try:
            raiz = ElementTree.fromstring(resp.content)
        except ParseError:
            return None
        texto = raiz.findtext("ExtendedPermissions") or ""
        return [p.strip() for p in texto.replace(";", ",").split(",") if p.strip()]

    async def alineacion(
        self,
        ht_match_id: int,
        team_id: int,
        alineacion: dict[str, Any],
        *,
        guardar: bool,
        version: str = "3.0",
        source_system: str = "hattrick",
    ) -> dict[str, Any]:
        """Prevé una alineación en Hattrick o, con `guardar=True`, la envía.

        Vuelve el 2026-11-19 desde el commit 2c07e14, con el formato que se
        comprobó en vivo ese día: la alineación viaja como el campo `lineup`
        de un POST a `matchorders`.

        * `guardar=False` usa `predictratings`: Hattrick devuelve los siete
          ratings de esa alineación y NO la guarda. Comprobado leyendo las
          órdenes antes y después. No necesita ningún permiso extra.
        * `guardar=True` usa `setmatchorder` y sustituye las órdenes del
          partido. Necesita el permiso `set_matchorder`; sin él Hattrick
          contesta 401 y sale como `CHPPDeniedError`, que se arregla
          reconectando UNA vez, no reintentando.

        No se reintenta nunca: reintentar una escritura que quizá sí llegó es
        arriesgar un doble envío.
        """
        import json as _json

        url = f"{settings.chpp_base_url}/chppxml.ashx"
        query = {
            "file": "matchorders",
            "version": version,
            "actionType": "setmatchorder" if guardar else "predictratings",
            "matchID": ht_match_id,
            "teamId": team_id,
            "sourceSystem": source_system,
        }
        try:
            resp = await self._client.post(
                url, params=query, data={"lineup": _json.dumps(alineacion)}
            )
        except httpx.TransportError as exc:
            raise CHPPUnavailableError(str(exc)) from exc
        if resp.status_code == 401:
            if await self._token_sigue_vivo():
                raise CHPPDeniedError(
                    "Hattrick no deja enviar la alineación con este acceso: falta el "
                    "permiso de órdenes de partido, y se concede al reconectar"
                )
            raise CHPPAuthError("token revocado, requiere re-autorización")
        if resp.status_code >= 500:
            raise CHPPUnavailableError(f"Hattrick devolvió {resp.status_code}")
        resp.raise_for_status()
        return self._parse("matchorders", resp.content)

    def _parse(self, file: str, xml: bytes) -> dict[str, Any]:
        from app.infrastructure.chpp.parsers import get_parser

        return get_parser(file)(xml)

    async def aclose(self) -> None:
        await self._client.aclose()


class CHPPOAuthDance:
    """Flujo de autorización de 3 patas."""

    async def get_authorize_url(self) -> tuple[str, str, str]:
        # timeout=30.0: httpx por defecto usa 5s, y `request_token.ashx` de
        # Hattrick puede tardar 12s+ en responder sin estar caído
        # verificado en vivo 2026-08-04 con una llamada directa (12.5s,
        # respuesta válida). Antes bloqueaba "Conectar con Hattrick" con
        # `httpx.ReadTimeout` incluso con 15s.
        async with AsyncOAuth1Client(
            client_id=settings.chpp_consumer_key,
            client_secret=settings.chpp_consumer_secret,
            redirect_uri=settings.chpp_callback_url,
            headers={"User-Agent": settings.chpp_user_agent},
            timeout=30.0,
        ) as client:
            tok = await client.fetch_request_token(
                f"{settings.chpp_base_url}/oauth/request_token.ashx"
            )
            # `scope` va en la URL de AUTORIZACION, no en la de request_token.
            # Comprobado en vivo el 2026-08-26 leyendo la propia pagina de
            # Hattrick: puesto en `request_token.ashx` se ignora en silencio
            # --la peticion no falla, pero la pantalla sigue ofreciendo solo
            # «Acceso de lectura»-- y puesto aqui aparece «Administra tus
            # juveniles». Sin el, el token no puede con `unlockskills`, que
            # escribe, y contesta 401 con una pagina de IIS.
            url = f"{settings.chpp_base_url}/oauth/authorize.aspx?oauth_token={tok['oauth_token']}"
            if settings.chpp_scope:
                url = f"{url}&scope={settings.chpp_scope}"
            return url, tok["oauth_token"], tok["oauth_token_secret"]

    async def exchange(self, token: str, secret: str, verifier: str) -> tuple[str, str]:
        async with AsyncOAuth1Client(
            client_id=settings.chpp_consumer_key,
            client_secret=settings.chpp_consumer_secret,
            token=token,
            token_secret=secret,
            headers={"User-Agent": settings.chpp_user_agent},
            timeout=30.0,
        ) as client:
            access = await client.fetch_access_token(
                f"{settings.chpp_base_url}/oauth/access_token.ashx", verifier=verifier
            )
            return access["oauth_token"], access["oauth_token_secret"]
