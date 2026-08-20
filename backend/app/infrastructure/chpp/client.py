"""Adapter CHPP: OAuth 1.0a (HMAC-SHA1) + descarga de XML.

Endpoints oficiales:
  request_token: https://chpp.hattrick.org/oauth/request_token.ashx
  authorize:     https://chpp.hattrick.org/oauth/authorize.aspx
  access_token:  https://chpp.hattrick.org/oauth/access_token.ashx
  recursos:      https://chpp.hattrick.org/chppxml.ashx?file=<name>
"""
from typing import Any

import httpx
from authlib.integrations.httpx_client import AsyncOAuth1Client

from app.core.config import settings


class CHPPAuthError(Exception): ...
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

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        url = f"{settings.chpp_base_url}/chppxml.ashx"
        query = {"file": file, **({} if version == "latest" else {"version": version}), **params}
        try:
            resp = await self._client.get(url, params=query)
        except httpx.TransportError as exc:
            raise CHPPUnavailableError(str(exc)) from exc
        if resp.status_code == 401:
            raise CHPPAuthError("token revocado, requiere re-autorización")
        resp.raise_for_status()
        return self._parse(file, resp.content)  # bytes: el XML declara su encoding

    def _parse(self, file: str, xml: bytes) -> dict[str, Any]:
        from app.infrastructure.chpp.parsers import get_parser

        return get_parser(file)(xml)

    async def aclose(self) -> None:
        await self._client.aclose()


class CHPPOAuthDance:
    """Flujo de autorización de 3 patas."""

    async def get_authorize_url(self) -> tuple[str, str, str]:
        # timeout=30.0: httpx por defecto usa 5s, y `request_token.ashx` de
        # Hattrick puede tardar 12s+ en responder sin estar caído —
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
            url = f"{settings.chpp_base_url}/oauth/authorize.aspx?oauth_token={tok['oauth_token']}"
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
