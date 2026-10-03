"""`teams`, repartido por funcionalidad.

Tenia 1179 lineas en un solo fichero y lo abren 9 de las 31
pantallas, asi que tocar una ruta obligaba a leerlas todas.

Los sub-routers se incluyen en el MISMO orden en que estaban sus rutas:
FastAPI resuelve por orden de registro, y una ruta con segmento literal
que conviva con otra con parametro cambiaria de significado si se
reordenaran.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.teams import (
    cambios,
    club,
    dashboard,
    jugadores,
    modelos,
    partidos,
    plantilla,
    relleno,
    sincronizacion,
)

#: Lo que `precalentar` le pedía a `teams.py` cuando era un solo fichero: va
#: calentando el panel y el historial de cambios en segundo plano. Se reexporta
#: para que el reparto no le obligue a cambiar su import.
from app.api.v1.endpoints.teams.cambios import changes_history
from app.api.v1.endpoints.teams.dashboard import dashboard_guardado

__all__ = ["changes_history", "dashboard_guardado", "router"]

router = APIRouter()
router.include_router(club.router)
router.include_router(sincronizacion.router)
router.include_router(jugadores.router)
router.include_router(cambios.router)
router.include_router(partidos.router)
router.include_router(dashboard.router)
router.include_router(plantilla.router)
router.include_router(modelos.router)
router.include_router(relleno.router)
