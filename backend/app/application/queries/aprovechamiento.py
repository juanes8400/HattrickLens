"""A posteriori (2026-11-26): con lo que de verdad se jugó esta semana, qué
entrenamiento aprovechaba mejor.

Lee la semana de entrenamiento en curso --del corte anterior al siguiente,
liga más el partido entre semana-- y pasa a cada jugador por el motor puro de
`app.domain.engines.aprovechamiento`. Los minutos, los puestos, el cupo de 90′
y quién entrena en cada puesto son los mismos de `PostMatchTrainingService`:
se reutilizan, no se copian.

No llama a Hattrick: todo sale de lo sincronizado.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.post_match_training import (
    DEPRECATED_TRAINING_TYPES,
    DIAS_DEL_CICLO,
    TRAINING_POSITION_SHARES,
    PlayedSegment,
    PostMatchTrainingService,
)
from app.application.queries.training_context import TrainingContextService
from app.domain.engines import aprovechamiento as ap
from app.domain.engines.training_engine import TrainingSetup, default_setup
from app.domain.value_objects.ht_constants import (
    TRAINING_TARGET_SKILL,
    match_type_name,
    training_name,
    training_target,
)
from app.infrastructure.db import models as m


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AprovechamientoQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session
        self._pm = PostMatchTrainingService(session)

    async def get(self, team_id: int, ahora: datetime | None = None) -> dict[str, Any] | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        ahora = _aware(ahora or datetime.now(UTC))

        corte = await self._pm._training_deadline(team_id)
        desde = corte - timedelta(days=DIAS_DEL_CICLO)
        tramos, notas = await self._pm._played_segments(team_id, desde, corte)
        jugadores = await self._pm._players(team_id)
        entrenamiento = await self._pm._latest_training(team_id)
        ctx = await TrainingContextService(self._s).get(team_id)
        actual = entrenamiento.training_type if entrenamiento else None
        setup = ctx.setup if ctx is not None else default_setup("playmaking")
        # El jugador-entrenador no entrena (lo mismo que el A posteriori de antes).
        entrenador = entrenamiento.trainer_ht_id if entrenamiento else None

        por_jugador: dict[int, list[PlayedSegment]] = {}
        for t in tramos:
            if entrenador and t.ht_player_id == entrenador:
                continue
            por_jugador.setdefault(t.ht_player_id, []).append(t)

        opciones = [
            self._opcion(tipo, jugadores, por_jugador, setup)
            for tipo in sorted(TRAINING_TARGET_SKILL)
            if tipo not in DEPRECATED_TRAINING_TYPES and training_target(tipo) is not None
        ]
        opciones.sort(key=lambda o: o["aprovechado"], reverse=True)
        mejor = opciones[0] if opciones and opciones[0]["aprovechado"] > 0 else None
        de_actual = next((o for o in opciones if o["trainingType"] == actual), None)

        return {
            "corte": corte.isoformat(),
            "desde": desde.isoformat(),
            # Antes del corte todavía se puede cambiar; después, el corte que
            # guarda la base es el que acaba de pasar y la semana ya entrenó.
            "aunSePuedeCambiar": ahora < corte,
            "partidos": await self._partidos(team, {t.ht_match_id for t in tramos}),
            "actual": (
                {"trainingType": actual, "name": training_name(actual)}
                if actual is not None
                else None
            ),
            "mejor": mejor["trainingType"] if mejor else None,
            # Cuántas veces más aprovecha el mejor que el actual; None si no se
            # puede comparar (sin entrenamiento actual o el actual en cero).
            "veces": (
                mejor["aprovechado"] / de_actual["aprovechado"]
                if mejor and de_actual and de_actual["aprovechado"] > 0
                else None
            ),
            "opciones": opciones,
            "notas": notas,
        }

    def _opcion(
        self,
        tipo: int,
        jugadores: list[dict[str, Any]],
        por_jugador: dict[int, list[PlayedSegment]],
        setup: TrainingSetup,
    ) -> dict[str, Any]:
        skill = training_target(tipo) or setup.skill
        setup_del_tipo = TrainingSetup(
            skill=skill,
            training_type=tipo,
            intensity=setup.intensity,
            stamina_share=setup.stamina_share,
            coach_level=setup.coach_level,
            coach_is_excellent=setup.coach_is_excellent,
            assistant_level_sum=setup.assistant_level_sum,
        )
        entrenados = []
        for p in jugadores:
            suyos = por_jugador.get(p["ht_player_id"], [])
            m_ = self._pm._exposicion(tipo, suyos)
            if m_ <= 0:
                continue
            utiles = sum(
                max(t.played_minutes, 0) * self._pm._peso(tipo, t)
                for t in suyos
                if self._pm._peso(tipo, t) > 0
            )
            entrenados.append(
                ap.Entrenado(
                    ht_player_id=p["ht_player_id"],
                    name=p["name"],
                    exposicion=m_,
                    minutos_utiles=utiles,
                    ritmo=ap.ritmo(
                        skill,
                        p["skills"],
                        int(p["age_years"]),
                        int(p["age_days"]),
                        setup_del_tipo,
                    ),
                )
            )
        r = ap.aprovechamiento(
            tipo,
            entrenados,
            ap.casillas(TRAINING_POSITION_SHARES.get(tipo, {})),
            ap.ideal(skill, setup_del_tipo),
        )
        return {
            "trainingType": tipo,
            "name": training_name(tipo),
            "aprovechado": r.aprovechado,
            "aportePorCasilla": r.aporte_por_casilla,
            "semanasPorNivel": r.semanas_por_nivel,
            "casillas": r.casillas * ap.PARTIDOS_POR_SEMANA,
            "casillasQueEntrenan": r.casillas_que_entrenan,
            "jugadores": r.jugadores,
            "mejorJugador": (
                {"htPlayerId": r.mejor.ht_player_id, "name": r.mejor.name, "pct": r.mejor.pct}
                if r.mejor
                else None
            ),
            "minutosSinEntrenar": r.minutos_sin_entrenar,
        }

    async def _partidos(self, team: m.Team, ids: set[int | None]) -> list[dict[str, Any]]:
        """Los partidos de la semana que cuentan, con su rival, para el subtítulo."""
        reales = {i for i in ids if i}
        if not reales:
            return []
        filas = (
            await self._s.execute(
                select(m.Match).where(m.Match.ht_match_id.in_(reales)).order_by(m.Match.played_at)
            )
        ).scalars()
        out = []
        for p in filas:
            en_casa = p.home_team_ht_id == team.ht_team_id
            out.append(
                {
                    "htMatchId": p.ht_match_id,
                    "matchType": p.match_type,
                    "competicion": match_type_name(p.match_type),
                    "rival": p.away_team_name if en_casa else p.home_team_name,
                    "jugadoEl": _aware(p.played_at).isoformat() if p.played_at else None,
                }
            )
        return out
