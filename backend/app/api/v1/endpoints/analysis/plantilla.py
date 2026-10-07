"""La plantilla.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SKILL_COLS, SquadQueryService
from app.infrastructure.db import models as m

router = APIRouter()


async def roster(session: AsyncSession, team_id: int) -> tuple[list[dict[str, Any]], m.Team]:
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    rows = await SquadQueryService(session)._latest(team_id)
    players = [
        {
            "ht_player_id": ident.ht_player_id,
            "first_name": ident.first_name,
            "last_name": ident.last_name,
            "name": f"{ident.first_name} {ident.last_name}",
            "age_years": snap.age_years,
            "age_days": snap.age_days,
            "tsi": snap.tsi,
            "form": snap.form,
            "stamina": snap.stamina,
            "experience": snap.experience,
            "salary": snap.salary,
            # HL-15x: specialty/leadership ya vienen reales de players.xml
            # antes se ponían a 0 a mano porque no se persistían todavía.
            "specialty": snap.specialty,
            "leadership": snap.leadership,
            # 2026-08-09: bug real corregido de paso, sin esto,
            # _loyalty_bonus() en position_engine.py siempre daba 0 (ningún
            # llamador pasaba "loyalty"), pese a que positions.yaml ya
            # declara la fidelidad como ajuste del Manual.
            "loyalty": snap.loyalty,
            "injury_level": snap.injury_level,
            "is_transfer_listed": snap.is_transfer_listed,
            "skills": {c: getattr(snap, c) or 0 for c in SKILL_COLS},
            # Cuándo jugó por última vez. Lo usa la alerta de forma para no
            # avisar de quien no juega (ver `_quienes_juegan`).
            "last_match_played_at": snap.last_match_played_at,
        }
        for snap, ident in rows
    ]
    return players, team
