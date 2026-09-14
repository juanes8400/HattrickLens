"""El torneo de un partido en palabras, con la copa por su nombre.

«Copa» a secas no dice cuál: el equipo que cae de la Copa Colombia sigue en la
Copa Cocuy Rubí o en la de Consuelo, y son torneos distintos (2026-09-14,
pedido del usuario). Estadio y Partidos lo dicen igual porque salen de aquí.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects.ht_constants import MATCH_TYPE_CUP, MATCH_TYPE_NAMES
from app.infrastructure.db import models as m


async def nombres_de_copa(session: AsyncSession, team: m.Team) -> dict[tuple[int, int], str]:
    """Nombre de cada copa del país del equipo, por su nivel e índice."""
    if team.ht_league_id is None:
        return {}
    consulta = select(m.WorldCup).where(m.WorldCup.ht_league_id == team.ht_league_id)
    copas = (await session.execute(consulta)).scalars()
    # Las copas nacionales tienen nivel de liga 0; las divisionales, el de la
    # división (sólo por debajo de la sexta). Se prefiere la que corresponde al
    # equipo y, si no hay, cualquiera del mismo nivel.
    nivel_esperado = team.league_level if (team.league_level or 0) > 6 else 0
    nombres: dict[tuple[int, int], str] = {}
    for copa in sorted(copas, key=lambda c: c.cup_league_level != nivel_esperado):
        nombres.setdefault((copa.cup_level, copa.cup_level_index), copa.cup_name)
    return nombres


def nombre_del_torneo(
    match_type: int,
    cup_level: int | None,
    cup_level_index: int | None,
    nombres: dict[tuple[int, int], str],
) -> str:
    """«Liga», «Hattrick Masters»... y en copa, cuál: «Copa Cocuy Rubí»."""
    if match_type == MATCH_TYPE_CUP and cup_level is not None and cup_level_index is not None:
        nombre = nombres.get((cup_level, cup_level_index))
        if nombre:
            return nombre
    return MATCH_TYPE_NAMES.get(match_type, "Partido")
