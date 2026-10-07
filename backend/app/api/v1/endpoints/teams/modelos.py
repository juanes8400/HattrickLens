"""Calibraciones que la aplicacion ensena por transparencia.

Sale de partir `teams.py`, que tenia 1179 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter

from app.application.queries.transparencia import como_json as catalogo_de_calculos
from app.domain.engines.position_engine import model_info

router = APIRouter()


@router.get("/calculos", summary="Catálogo de cálculos con su formulación y sus constantes")
async def calculos() -> list[dict[str, Any]]:
    """Qué calcula la herramienta, con qué fórmula y con qué constantes.

    No lleva `team_id`: describe los MOTORES, que son los mismos para todos.
    Los valores del club de cada uno llegan por los endpoints que ya existen
    --la fórmula de entrenamiento, la matriz de posiciones-- y la pantalla los
    engancha bajo su cálculo.
    """
    return catalogo_de_calculos()


@router.get("/positions/model", summary="Modelo de posiciones basado en el Manual no Escrito")
async def positions_model() -> dict[str, Any]:
    """Procedencia, matriz y factores del motor de posiciones."""
    return model_info()
