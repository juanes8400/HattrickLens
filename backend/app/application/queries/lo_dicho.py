"""Lo que dijimos de un partido antes de jugarlo, guardado.

Vivía dentro de la consulta de Liga, que es quien lo estrenó. Se saca aquí el
2026-11-01, cuando la ficha de rival pasó a guardar lo que dice del partido de
PROMOCIÓN: ese cruce no lo pronostica Liga --el rival no está en tu serie, así
que la Poisson de la serie no lo alcanza-- y copiar la función habría dejado
dos sitios escribiendo la misma tabla con reglas que podrían divergir.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.domain.engines.prediccion import VERSION_DEL_MOTOR
from app.infrastructure.db import models as m

_log = logging.getLogger(__name__)


async def guardar_lo_dicho(
    ht_match_id: int | None,
    team_id: int,
    pronostico: dict[str, Any],
    fuente: str,
) -> None:
    """Deja escrito lo que acabamos de decir de un partido por jugarse.

    2026-09-26, pedido del usuario. Las predicciones se calculaban y se
    tiraban, así que después del partido no había forma honesta de decir
    «esto es lo que te dijimos»: recalcularlo hacia atrás da lo que diríamos
    HOY con los datos de entonces, que no es lo mismo.

    UNA FILA POR PARTIDO **Y CLUB**: los dos lados de un partido pueden estar
    conectados --la misma cuenta con sus dos clubes, o dos managers-- y el
    pronóstico no es el mismo para los dos, porque el motor usa la alineación
    que ESE manager envió. Sin el club en la clave, el segundo en abrir Liga
    pisaba la fila del primero y después del partido le enseñaba una terna que
    nunca vio.

    SE REESCRIBE MIENTRAS EL PARTIDO SIGA PENDIENTE, a propósito: lo que vale
    es lo último que el usuario llegó a ver antes del pitido, no lo primero.
    En cuanto se juega deja de ser un cruce pendiente y esto no se vuelve a
    llamar, así que la fila queda congelada sola.

    EN SU PROPIA SESIÓN, no en la de la petición. Es la única escritura de
    una petición de lectura, y un `commit` en medio caduca los objetos que el
    lector todavía está usando: la primera versión de esto tumbaba la pantalla
    entera al leer `team.name` después de guardar. Aparte, si la escritura
    falla no deja la transacción del lector envenenada, que es justo el error
    que reportan los usuarios al importar clubes viejos.

    Y no se hace notar: si falla, la pantalla sale igual. Guardar lo que
    dijimos no puede ser motivo para no poder decirlo.
    """
    if ht_match_id is None:
        return
    valores = {
        "home_win": round(float(pronostico["homeWin"]), 4),
        "draw": round(float(pronostico["draw"]), 4),
        "away_win": round(float(pronostico["awayWin"]), 4),
        "expected_home_goals": round(float(pronostico["expectedHomeGoals"]), 2),
        "expected_away_goals": round(float(pronostico["expectedAwayGoals"]), 2),
        "most_likely_score": str(pronostico["mostLikelyScore"])[:16],
        "source": fuente,
        "engine": VERSION_DEL_MOTOR,
        "computed_at": datetime.now(UTC),
    }
    from app.infrastructure.db.session import SessionLocal

    try:
        async with SessionLocal() as propia:
            fila = await propia.scalar(
                select(m.MatchPrediction).where(
                    m.MatchPrediction.ht_match_id == ht_match_id,
                    m.MatchPrediction.team_id == team_id,
                )
            )
            if fila is None:
                propia.add(m.MatchPrediction(ht_match_id=ht_match_id, team_id=team_id, **valores))
            else:
                for campo, valor in valores.items():
                    setattr(fila, campo, valor)
            await propia.commit()
    except Exception:  # noqa: BLE001, guardar lo dicho nunca tumba la pantalla
        # PERO SE DEJA DICHO. La primera version se lo callaba, y una clave
        # primaria mal declarada en la migracion (`BIGINT` en vez de
        # `PKBigInt`, que sqlite no autonumera) estuvo tirando cada INSERT
        # sin que se notara: la pantalla salia bien y la tabla seguia vacia.
        _log.warning("no se pudo guardar el pronostico del partido %s", ht_match_id, exc_info=True)
