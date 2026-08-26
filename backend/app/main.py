from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings


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
if (_FRONTEND / "index.html").exists():

    @app.get("/{ruta:path}", include_in_schema=False)
    async def spa(ruta: str) -> FileResponse:
        """Cualquier ruta que no sea la API devuelve el index.

        La navegación es del lado del cliente: recargar en /rivals/277186 tiene
        que servir la misma página, no un 404.
        """
        candidato = (_FRONTEND / ruta).resolve()
        if ruta and candidato.is_file() and _FRONTEND in candidato.parents:
            return FileResponse(candidato)
        return FileResponse(_FRONTEND / "index.html")

    app.mount("/assets", StaticFiles(directory=_FRONTEND / "assets"), name="assets")
