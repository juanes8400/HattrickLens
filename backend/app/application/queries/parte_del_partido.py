"""El parte del último partido, contrastado con lo que habíamos dicho.

2026-09-26, pedido del usuario: «un parte del partido más grande en Cambios,
comparado contra las probabilidades». La gracia no es repetir el resultado,
que ya se ve en Partidos, sino ponerlo al lado de la terna que dábamos ANTES
de jugarlo, que es lo único que permite decir si acertamos o no.

DE AQUÍ SALEN NÚMEROS Y CLAVES, NUNCA FRASES. La pantalla escribe la frase
juntando una clave con esos números, porque una frase pegada aquí con un
f-string («ganaste 3-1, le dábamos un 48%») no se puede traducir: el traductor
recibiría una cadena distinta por cada resultado posible del mundo.

Tampoco se deriva aquí lo que la pantalla puede derivar sola (quién era el
favorito, si el marcador cantado fue el que cayó, cómo le fue al equipo
propio): con los goles y las tres probabilidades ya lo tiene todo, y cada
campo de más es un campo más que mantener y que traducir mal.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.domain.value_objects.ht_constants import match_type_name
from app.infrastructure.db import models as m


async def build_parte_del_partido(session: AsyncSession, team_id: int) -> dict[str, Any] | None:
    """El último partido jugado del equipo, con lo que dijimos de él si lo hay.

    Devuelve `None` si el equipo no existe o todavía no tiene ningún partido
    jugado: es un estado normal de una cuenta recién conectada, no un error.

    `prediction` a `None` es el otro estado que la pantalla tiene que saber
    pintar, y es el caso NORMAL de todo partido anterior al 2026-09-26: antes
    de esa fecha las predicciones se calculaban y se tiraban. No se rellena
    recalculándolo hacia atrás porque eso sería lo que diríamos hoy, no lo
    que dijimos.
    """
    team = await session.scalar(
        select(m.Team)
        .options(load_only(m.Team.id, m.Team.ht_team_id, raiseload=True))
        .where(m.Team.id == team_id)
    )
    if team is None:
        return None

    partido = await session.scalar(
        select(m.Match)
        .options(
            load_only(
                m.Match.ht_match_id,
                m.Match.played_at,
                m.Match.match_type,
                m.Match.match_round,
                m.Match.home_team_ht_id,
                m.Match.home_team_name,
                m.Match.away_team_name,
                m.Match.home_goals,
                m.Match.away_goals,
                raiseload=True,
            )
        )
        .where(
            (m.Match.home_team_ht_id == team.ht_team_id)
            | (m.Match.away_team_ht_id == team.ht_team_id),
            m.Match.home_goals >= 0,
        )
        .order_by(m.Match.played_at.desc())
        .limit(1)
    )
    if partido is None:
        return None

    # El pronóstico DE ESTE CLUB. Un partido tiene dos lados y los dos pueden
    # estar conectados, con pronósticos distintos: el de enfrente no es «lo que
    # te dijimos», y esta pantalla no sirve para otra cosa.
    dicho = await session.scalar(
        select(m.MatchPrediction).where(
            m.MatchPrediction.ht_match_id == partido.ht_match_id,
            m.MatchPrediction.team_id == team_id,
        )
    )

    return {
        "htMatchId": partido.ht_match_id,
        "playedAt": _iso(partido.played_at),
        "competition": match_type_name(partido.match_type),
        "round": partido.match_round,
        "home": partido.home_team_name,
        "away": partido.away_team_name,
        "homeGoals": partido.home_goals,
        "awayGoals": partido.away_goals,
        "isHome": partido.home_team_ht_id == team.ht_team_id,
        "prediction": None
        if dicho is None
        else {
            "homeWin": dicho.home_win,
            "draw": dicho.draw,
            "awayWin": dicho.away_win,
            "expectedHomeGoals": dicho.expected_home_goals,
            "expectedAwayGoals": dicho.expected_away_goals,
            "mostLikelyScore": dicho.most_likely_score,
            # «zonas» o «goles»: no es un detalle interno. El respaldo de goles
            # agregados ignora alineaciones y tácticas, y a un pronóstico así
            # no se le puede pedir cuentas igual que al motor de zonas.
            "source": dicho.source,
            "engine": dicho.engine,
            "computedAt": _iso(dicho.computed_at),
        },
    }


def _iso(cuando: datetime | None) -> str | None:
    return cuando.isoformat() if cuando is not None else None
