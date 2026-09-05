from fastapi import APIRouter

from app.api.v1.endpoints import (
    academy,
    analysis,
    arena,
    auth_chpp,
    cup,
    economy,
    league,
    libro,
    matches,
    player_balance,
    rivals,
    sync,
    teams,
    uso,
)

api_router = APIRouter()
api_router.include_router(auth_chpp.router, prefix="/auth/chpp", tags=["auth"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(sync.router, prefix="/syncs", tags=["sync"])
api_router.include_router(analysis.router, tags=["análisis"])
api_router.include_router(economy.router, tags=["economía"])
api_router.include_router(arena.router, tags=["estadio"])
api_router.include_router(matches.router, tags=["partidos"])
api_router.include_router(league.router, tags=["liga y predicciones"])
api_router.include_router(academy.router, tags=["juveniles"])
api_router.include_router(rivals.router, tags=["scouting de rivales"])
api_router.include_router(cup.router, tags=["copa"])
api_router.include_router(player_balance.router, tags=["saldo neto por jugador"])
api_router.include_router(uso.router, tags=["uso de la app"])
api_router.include_router(libro.router, tags=["libro de visitas"])
