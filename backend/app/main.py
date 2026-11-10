from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.types import Scope

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.registro import configurar_registro
from app.i18n.middleware import TraducirRespuestas

# Antes de crear nada: lo que falle al arrancar también tiene derecho a
# contarse (2026-11-03).
configurar_registro()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # startup: warm caches, verify DB/Redis connectivity
    yield
    # shutdown: close pools


app = FastAPI(
    title="Hattrick Lens API",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+"
    if settings.environment == "local"
    else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Los textos de la API salen en el idioma que pide el navegador; en español
# no hace nada. Ver app/i18n/traductor.py.
app.add_middleware(TraducirRespuestas)

# Las respuestas viajan comprimidas (2026-09-20).
#
# MEDIDO: el listado de partidos pesaba 314.684 bytes y salía tal cual, sin una
# sola cabecera de compresión. Es JSON, o sea texto con las mismas veinte
# claves repetidas setecientas veces, que es el caso donde comprimir gana más:
# ese mismo cuerpo baja a unas decenas de kilobytes. No cambia una sola cuenta
# ni una sola respuesta, sólo lo que se manda por el cable.
#
# `minimum_size` deja en paz lo pequeño: comprimir dos kilobytes cuesta más
# procesador del que ahorra en red.
#
# SE PONE DESPUÉS DE LA TRADUCCIÓN a propósito. El orden de `add_middleware` es
# de dentro hacia fuera, así que ésta queda por FUERA y comprime el texto ya
# traducido; al revés comprimiría y la traducción recibiría un cuerpo binario.
#
# Lo que NO se comprime es el chorro de progreso de la sincronización: va
# marcado con `Content-Encoding: identity` en su propio endpoint, porque un
# flujo comprimido se queda atascado en el búfer y la barra no se movería.
#
# `compresslevel=6` y no el 9 de la casa. Medido con el listado de partidos,
# que es el cuerpo más gordo que sirve la aplicación: el 9 se lleva unos 100 ms
# de procesador por respuesta y sólo gana un puñado de kilobytes sobre el 6. El
# tiempo que el usuario espera es el de la cuenta MÁS el de comprimir, así que
# apretar hasta el último byte se paga en la pantalla.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=6)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── El frontend, servido por la misma aplicación ────────────────────────────
#
# Un solo proceso para API y pantalla: es lo que cabe en el plan gratuito de
# casi cualquier hosting, y de paso el navegador ve el mismo origen, así que la
# cookie de sesión viaja sin CORS ni dominios cruzados.
#
# Si la carpeta no existe (desarrollo, donde manda Vite), no se monta nada y la
# API funciona igual.
_FRONTEND = Path(__file__).resolve().parents[1] / "static"

# Lo que se guarda y lo que no (2026-11-10).
#
# MEDIDO en producción: `/assets/index-Da-mziAK.js` salía sin `Cache-Control`,
# el CDN contestaba `cf-cache-status: DYNAMIC` y pedirlo con `If-None-Match`
# igual a su etag devolvía un 200 con el fichero entero. O sea, cada visita
# volvía a bajarse la aplicación completa.
#
# Los nombres de `/assets/` llevan la huella que les pone Vite: si cambia un
# byte cambia el nombre, así que lo que hay detrás de un nombre no cambia
# nunca y se puede guardar un año sin preguntar (`immutable`).
#
# El `index.html` es justo lo contrario: se llama siempre igual y es quien dice
# qué bundles tocan. Con `no-cache` el navegador lo guarda pero pregunta antes
# de usarlo, y un despliegue nuevo se ve en la visita siguiente.
CACHE_CON_HUELLA = "public, max-age=31536000, immutable"
CACHE_DEL_INDEX = "no-cache"


class _AssetsConHuella(StaticFiles):
    """`StaticFiles` que marca como inmutable lo que sirve.

    Sólo lo que sirve: un nombre que no existe sale como 404 por excepción y no
    pasa por aquí, así que un fallo nunca se queda guardado un año.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        respuesta = await super().get_response(path, scope)
        respuesta.headers["Cache-Control"] = CACHE_CON_HUELLA
        return respuesta


def montar_frontend(app: FastAPI, carpeta: Path) -> None:
    """Sirve la pantalla ya compilada que hay en `carpeta`.

    Va lo último, detrás de la API y de `/health`: la ruta comodín se queda con
    todo lo que nadie haya reclamado antes.
    """
    carpeta = carpeta.resolve()

    # EL ORDEN IMPORTA. `/assets` se monta ANTES que la comodín: las rutas se
    # prueban por orden de registro y `/{ruta:path}` casa con todo, así que
    # cuando iba primero los bundles los servía ella con un `FileResponse`
    # pelado, que no sabe contestar 304, y este montaje no llegaba a usarse.
    app.mount("/assets", _AssetsConHuella(directory=carpeta / "assets"), name="assets")

    index = carpeta / "index.html"

    @app.get("/{ruta:path}", include_in_schema=False)
    async def spa(ruta: str) -> FileResponse:
        """Cualquier ruta que no sea la API devuelve el index.

        La navegación es del lado del cliente: recargar en /rivals/277186 tiene
        que servir la misma página, no un 404.
        """
        candidato = (carpeta / ruta).resolve()
        # `candidato != index`: pedir `/index.html` por su nombre es pedir el
        # index, y tiene que salir con su cabecera como por cualquier otra ruta.
        if ruta and candidato != index and candidato.is_file() and carpeta in candidato.parents:
            # Lo suelto de la raíz (favicon, escudo): son veinte kilobytes
            # entre todos y se quedan como estaban, sin cabecera.
            return FileResponse(candidato)
        return FileResponse(index, headers={"Cache-Control": CACHE_DEL_INDEX})


if (_FRONTEND / "index.html").exists():
    montar_frontend(app, _FRONTEND)
