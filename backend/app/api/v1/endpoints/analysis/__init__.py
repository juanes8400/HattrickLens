"""`analysis`, repartido por funcionalidad.

Tenia 2309 lineas en un solo fichero y lo abren 9 de las 31
pantallas, asi que tocar una ruta obligaba a leerlas todas.

Los sub-routers se incluyen en el MISMO orden en que estaban sus rutas:
FastAPI resuelve por orden de registro, y una ruta con segmento literal
que conviva con otra con parametro cambiaria de significado si se
reordenaran.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.analysis import (
    alertas,
    alineacion,
    entrenamiento,
    jugadores,
    modelos,
    plantilla,
    resumen,
)

#: Lo que otros módulos le pedían a `analysis.py` cuando era un solo fichero:
#: `economy`, `league` y `rivals` cargan la plantilla con `roster`, y
#: `precalentar` calienta la alineación y las alertas guardadas. Se reexporta
#: para que el reparto no les obligue a cambiar su import.
from app.api.v1.endpoints.analysis.alertas import _insights_guardadas, _next_match_weather_insights
from app.api.v1.endpoints.analysis.alineacion import lineup
from app.api.v1.endpoints.analysis.plantilla import roster

__all__ = [
    "_insights_guardadas",
    "_next_match_weather_insights",
    "lineup",
    "roster",
    "router",
]

router = APIRouter()
router.include_router(plantilla.router)
router.include_router(jugadores.router)
router.include_router(alineacion.router)
router.include_router(entrenamiento.router)
router.include_router(alertas.router)
router.include_router(modelos.router)
router.include_router(resumen.router)
