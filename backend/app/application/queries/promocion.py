"""El partido de Promoción y quién lo juega contra ti.

2026-11-01, pedido del usuario: «agregar el rival de Promoción a la lista de
Rivales de Liga» y «también quiero el rival de Promoción, desde que se conoce
hasta que ya se haya jugado, en la flor del dashboard».

POR QUÉ NO SALE SOLO. La Promoción es de liga --cuenta para subir, se juega en
tu sede o en la suya, el motor la trata como un partido de liga-- pero el rival
NO está en tu serie: viene de la de arriba. Así que no aparece en la
clasificación, de donde salen los siete rivales de siempre, y no estaba en
ninguna parte.

LO QUE YA ESTABA HECHO: el sync precarga sus últimos cinco oficiales igual que
los de tus contrincantes de liga y el de copa, porque el paso de «partidos de
rivales» ya incluía el tipo 2. Los datos estaban; lo que faltaba era
preguntar por ellos.

UNA POR TEMPORADA, Y LA ÚLTIMA. Un club con años de historia tiene varias
promociones en la base, así que se coge la más reciente por fecha. `pendiente`
dice si todavía no se ha jugado, que es la diferencia entre las dos cosas que
se pidieron: la flor sólo la quiere mientras esté por jugarse, y la lista de
rivales la quiere también después, que para eso se guarda la historia.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects.ht_constants import MATCH_TYPE_QUALIFICATION
from app.infrastructure.db import models as m


@dataclass(frozen=True)
class RivalDePromocion:
    ht_team_id: int
    nombre: str
    #: Tu sede o la suya. En Promoción la sede es segura, y el motor la usa.
    en_casa: bool
    cuando: datetime | None
    pendiente: bool


async def rival_de_promocion(
    session: AsyncSession, team: m.Team, *, solo_pendiente: bool = False
) -> RivalDePromocion | None:
    """Tu rival de Promoción, o nada si no juegas promoción.

    No jugar promoción es el caso NORMAL: sólo la juegan los que quedan en
    ciertos puestos. `None` no es un error ni un dato que falte.
    """
    condiciones = [
        or_(
            m.Match.home_team_ht_id == team.ht_team_id,
            m.Match.away_team_ht_id == team.ht_team_id,
        ),
        m.Match.match_type == MATCH_TYPE_QUALIFICATION,
    ]
    if solo_pendiente:
        condiciones.append(func.upper(m.Match.status) != "FINISHED")
    partido = await session.scalar(
        select(m.Match).where(*condiciones).order_by(m.Match.played_at.desc()).limit(1)
    )
    if partido is None:
        return None
    en_casa = partido.home_team_ht_id == team.ht_team_id
    rival_id = partido.away_team_ht_id if en_casa else partido.home_team_ht_id
    if not rival_id:
        return None
    return RivalDePromocion(
        ht_team_id=rival_id,
        nombre=(partido.away_team_name if en_casa else partido.home_team_name) or "",
        en_casa=en_casa,
        cuando=partido.played_at,
        pendiente=(partido.status or "").upper() != "FINISHED",
    )
