"""El parte del último entrenamiento (2026-09-19, pedido del usuario).

La pregunta es «¿qué pasó en la última actualización de entrenamiento?», y lo
primero que hay que saber es CUÁNDO fue. No se adivina: Hattrick publica la
hora de la actualización semanal de cada liga y ya la guardamos
(`WorldContext.training_date`). Desde ese instante se retrocede de siete en
siete hasta el último que ya pasó, que es el mismo mecanismo con el que se
reconstruye el diario semanal de entrenamiento.

Las subidas no se deducen comparando fotos: son las que Hattrick confirma una
por una (`skill_ups`), con su temporada y su semana. Si en la última
actualización no subió nadie, eso se dice tal cual y se apunta cuál fue la
última que sí movió algo, en vez de enseñar subidas viejas como si fueran de
ahora.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import season_week_for_datetime
from app.domain.engines import training_engine as te
from app.domain.value_objects.ht_constants import SKILL_LABELS, training_name
from app.infrastructure.db import models as m


@dataclass
class SubidaConfirmada:
    ht_player_id: int
    name: str
    skill: str
    skill_label: str
    from_level: int
    to_level: int


@dataclass
class ParteDeEntrenamiento:
    #: Instante oficial de la actualización, en UTC.
    at: datetime | None
    season_week: str | None
    training_type: str | None
    intensity: int | None
    stamina_share: int | None
    trainer_name: str | None
    ups: list[SubidaConfirmada]
    #: La actualización anterior, para tener con qué comparar.
    previous_at: datetime | None
    previous_season_week: str | None
    previous_ups: int
    #: Cuando en la última no subió nadie, la última que sí.
    last_with_ups: str | None
    #: Hasta cuándo llegan los datos guardados. Si esa marca es ANTERIOR al
    #: entrenamiento, «no subió nadie» sería mentira: es que todavía no se ha
    #: mirado. La pantalla necesita poder decir esa diferencia.
    data_at: datetime | None
    pending_sync: bool


def _utc(valor: datetime) -> datetime:
    return valor if valor.tzinfo else valor.replace(tzinfo=UTC)


def momento_de_la_ultima(ancla: datetime | None, ahora: datetime | None = None) -> datetime | None:
    """El último instante de entrenamiento que YA pasó.

    `ancla` es la hora oficial que publica Hattrick para esta liga. Puede venir
    en el futuro (es la próxima), así que se retrocede semana a semana.
    """
    if ancla is None:
        return None
    ahora = ahora or datetime.now(UTC)
    instante = _utc(ancla)
    while instante > ahora:
        instante -= timedelta(days=7)
    return instante


class UltimoEntrenamientoQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int) -> ParteDeEntrenamiento | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        # El mundo de ESTA liga: la hora de la actualizacion es de la liga,
        # no de la cuenta. Misma lectura que el diario semanal.
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None
            else None
        )
        ultima = momento_de_la_ultima(world.training_date if world else None)
        anterior = ultima - timedelta(days=7) if ultima is not None else None

        etiqueta = (
            season_week_for_datetime(world, ultima)
            if world is not None and ultima is not None
            else None
        )
        etiqueta_anterior = (
            season_week_for_datetime(world, anterior)
            if world is not None and anterior is not None
            else None
        )

        # La configuración que estaba puesta en ese momento, no la de hoy:
        # cambiar de entrenamiento el jueves no reescribe lo que paso el martes.
        vigente = None
        if ultima is not None:
            vigente = await self._s.scalar(
                select(m.TrainingSnapshot)
                .where(
                    m.TrainingSnapshot.team_id == team_id,
                    m.TrainingSnapshot.captured_at <= ultima.replace(tzinfo=None),
                )
                .order_by(m.TrainingSnapshot.captured_at.desc())
                .limit(1)
            )

        filas = list(
            (
                await self._s.execute(
                    select(m.SkillUp, m.Player)
                    .join(m.Player, m.Player.ht_player_id == m.SkillUp.ht_player_id)
                    .where(m.SkillUp.team_id == team_id)
                    .order_by(
                        m.SkillUp.season.desc(),
                        m.SkillUp.match_round.desc(),
                    )
                )
            ).all()
        )

        cfg = te._config()
        mapa = {int(sid): str(nombre) for sid, nombre in cfg["skill_id_map"].items()}
        etiquetas = SKILL_LABELS

        def como_subida(fila: tuple[m.SkillUp, m.Player]) -> SubidaConfirmada:
            up, jugador = fila
            clave = mapa.get(up.skill_id, str(up.skill_id))
            return SubidaConfirmada(
                ht_player_id=up.ht_player_id,
                name=f"{jugador.first_name or ''} {jugador.last_name or ''}".strip(),
                skill=clave,
                skill_label=etiquetas.get(clave, clave),
                from_level=up.old_level,
                to_level=up.new_level,
            )

        def de_la_semana(semana: str | None) -> list[tuple[m.SkillUp, m.Player]]:
            if semana is None:
                return []
            return [f for f in filas if f"{f[0].season:02d}-{f[0].match_round:02d}" == semana]

        ups = [como_subida(f) for f in de_la_semana(etiqueta)]
        # Primero quien más subió, y a igualdad por nombre: una lista estable.
        ups.sort(key=lambda s: (-(s.to_level - s.from_level), s.name))

        # Hasta cuando llegan los datos: la ultima foto guardada de la
        # plantilla.
        data_at = await self._s.scalar(
            select(func.max(m.PlayerSnapshot.captured_at))
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id)
        )
        if data_at is not None:
            data_at = _utc(data_at)

        ultima_con_subidas = None
        if not ups and filas:
            primera = filas[0][0]
            ultima_con_subidas = f"{primera.season:02d}-{primera.match_round:02d}"

        return ParteDeEntrenamiento(
            at=ultima,
            season_week=etiqueta,
            training_type=training_name(vigente.training_type) if vigente else None,
            intensity=vigente.training_level if vigente else None,
            stamina_share=vigente.stamina_part if vigente else None,
            trainer_name=vigente.trainer_name if vigente else None,
            ups=ups,
            previous_at=anterior,
            previous_season_week=etiqueta_anterior,
            previous_ups=len(de_la_semana(etiqueta_anterior)),
            last_with_ups=ultima_con_subidas,
            data_at=data_at,
            pending_sync=(
                ultima is not None and (data_at is None or data_at < ultima)
            ),
        )


def como_json(parte: ParteDeEntrenamiento) -> dict[str, Any]:
    return {
        "at": parte.at.isoformat() if parte.at else None,
        "seasonWeek": parte.season_week,
        "trainingType": parte.training_type,
        "intensity": parte.intensity,
        "staminaShare": parte.stamina_share,
        "trainerName": parte.trainer_name,
        "ups": [
            {
                "htPlayerId": s.ht_player_id,
                "name": s.name,
                "skill": s.skill,
                "skillLabel": s.skill_label,
                "fromLevel": s.from_level,
                "toLevel": s.to_level,
            }
            for s in parte.ups
        ],
        "previousAt": parte.previous_at.isoformat() if parte.previous_at else None,
        "previousSeasonWeek": parte.previous_season_week,
        "previousUps": parte.previous_ups,
        "lastWithUps": parte.last_with_ups,
        "dataAt": parte.data_at.isoformat() if parte.data_at else None,
        "pendingSync": parte.pending_sync,
    }
