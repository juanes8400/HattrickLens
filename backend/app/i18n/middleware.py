"""Middleware que traduce las respuestas JSON de la API (2026-09-15).

ASGI puro y no ``BaseHTTPMiddleware``: este último se lleva mal con las
respuestas en streaming, y la sincronización en vivo es una. Lo que no es
JSON (el streaming, los ficheros) pasa sin tocar; el JSON se junta entero,
se traduce con ``traductor`` y se reenvía con su nueva longitud.

En español no hace nada: ni junta el cuerpo ni lo vuelve a serializar.
"""

from __future__ import annotations

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.i18n.traductor import idioma_de, traductor


class TraducirRespuestas:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        cabeceras = dict(scope.get("headers") or [])
        idioma = idioma_de(cabeceras.get(b"accept-language", b"").decode("latin-1"))
        tr = traductor(idioma)
        if tr is None:
            # También en español se declara que la respuesta depende del
            # idioma: el panel se guarda 30 s en la caché del navegador, y sin
            # esto, al cambiar a inglés, se servía la copia en español.
            async def marcar(mensaje: Message) -> None:
                if mensaje["type"] == "http.response.start":
                    mensaje = {**mensaje, "headers": _con_vary(mensaje.get("headers", []))}
                await send(mensaje)

            await self.app(scope, receive, marcar)
            return

        inicio: dict[str, Any] | None = None
        pasar_de_largo = False
        trozos: list[bytes] = []

        async def enviar(mensaje: Message) -> None:
            nonlocal inicio, pasar_de_largo
            if mensaje["type"] == "http.response.start":
                tipo = next(
                    (v for k, v in mensaje.get("headers", []) if k.lower() == b"content-type"),
                    b"",
                )
                if not tipo.startswith(b"application/json"):
                    pasar_de_largo = True
                    await send(mensaje)
                    return
                inicio = dict(mensaje)
                return
            if mensaje["type"] != "http.response.body" or pasar_de_largo or inicio is None:
                await send(mensaje)
                return
            trozos.append(mensaje.get("body", b""))
            if mensaje.get("more_body"):
                return
            cuerpo = b"".join(trozos)
            try:
                traducido = tr.json(json.loads(cuerpo))
                cuerpo = json.dumps(traducido, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            except ValueError:
                pass
            nuevas = [
                (k, v) for k, v in inicio.get("headers", []) if k.lower() != b"content-length"
            ]
            nuevas.append((b"content-length", str(len(cuerpo)).encode("latin-1")))
            await send({**inicio, "headers": _con_vary(nuevas)})
            await send({"type": "http.response.body", "body": cuerpo})

        await self.app(scope, receive, enviar)


def _con_vary(cabeceras: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """Añade ``Accept-Language`` a ``Vary`` sin perder lo que ya traía (``Origin``)."""
    valores = [v.decode("latin-1") for k, v in cabeceras if k.lower() == b"vary"]
    partes = [p.strip() for v in valores for p in v.split(",") if p.strip()]
    if not any(p.lower() == "accept-language" for p in partes):
        partes.append("Accept-Language")
    resto = [(k, v) for k, v in cabeceras if k.lower() != b"vary"]
    return [*resto, (b"vary", ", ".join(partes).encode("latin-1"))]
