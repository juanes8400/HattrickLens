"""DashboardQueryService — lado de lectura (CQRS).

No pasa por el dominio ni por repositorios de escritura: lee directamente los
snapshots más recientes. En PostgreSQL esto se sustituirá por la vista
materializada `mv_team_dashboard` (docs/02) sin cambiar este contrato.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.dashboard import (
    Alert,
    DashboardResponse,
    FinanceSummary,
    PlayerRow,
    SquadSummary,
    TrainingSummary,
)
from app.application.queries.training_context import TrainingContextService
from app.application.queries.training_squad import TrainingSquadQueryService
from app.domain.engines import training_engine as te
from app.domain.engines.economy_engine import structural_balance, total_sponsor_income
from app.domain.value_objects.ht_constants import (
    CONFIDENCE,
    TEAM_SPIRIT,
    training_name,
)
from app.infrastructure.db import models as m

# La temporada de Hattrick dura 112 días: 27 años y 56 días son 27,5.
DAYS_PER_HT_YEAR = 112

STALE_AFTER = timedelta(hours=12)
# columna en DB → clave camelCase en la API (consistencia de contrato)
SKILL_COLS = {
    "keeper": "keeper",
    "defending": "defending",
    "playmaking": "playmaking",
    "winger": "winger",
    "passing": "passing",
    "scoring": "scoring",
    "set_pieces": "setPieces",
}


class DashboardQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int, now: datetime | None = None) -> DashboardResponse | None:
        now = now or datetime.now(UTC)
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        # CHPP entrega importes en la moneda base del juego: hay que dividir
        # por la tasa del país o se muestran inflados (Colombia = 10).
        rate = team.currency_rate or 1.0

        last_sync = await self._s.scalar(
            select(m.Sync)
            .where(m.Sync.team_id == team_id, m.Sync.status.in_(("completed", "partial")))
            .order_by(m.Sync.started_at.desc())
            .limit(1)
        )
        synced_at = last_sync.finished_at or last_sync.started_at if last_sync else None
        stale = True
        if synced_at is not None:
            ref = synced_at if synced_at.tzinfo else synced_at.replace(tzinfo=UTC)
            stale = (now - ref) > STALE_AFTER

        resp = DashboardResponse(
            team_id=team_id,
            team_name=team.name,
            league_name=team.league_name,
            series_name=team.series_name,
            synced_at=synced_at,
            sync_id=last_sync.id if last_sync else None,
            stale=stale,
        )

        rows = await self._latest_players(team_id)
        players = [snap for snap, _ in rows]
        if rows:
            resp.squad = self._squad(players, rate)
            top = sorted(rows, key=lambda r: -r[0].salary)[:5]
            resp.top_salaries = [self._row(snap, ident, rate) for snap, ident in top]

        econ = await self._s.scalar(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at.desc())
            .limit(1)
        )
        if econ:

            def local(v: int) -> int:
                return int(round(v / rate))

            # Las dos semanas ya cerradas que guarda Hattrick: la ultima y la
            # de antes (`last_*`). Los ingresos llevan las ventas dentro, que
            # es como se pidio: el porcentaje de salarios se mueve con ellas y
            # eso es parte de la respuesta, no ruido.
            ingresos_dos_semanas = econ.income_sum + econ.last_income_sum
            gastos_dos_semanas = econ.costs_sum + econ.last_costs_sum
            salarios_dos_semanas = econ.costs_players + econ.last_costs_players

            resp.finance = FinanceSummary(
                cash=local(econ.cash),
                expected_cash=local(econ.expected_cash),
                weekly_delta=local(econ.expected_weeks_total),
                income_sum=local(econ.income_sum),
                costs_sum=local(econ.costs_sum),
                costs_players=local(econ.costs_players),
                fan_club_size=econ.fan_club_size,  # no es dinero
                last_weeks_total=local(econ.last_weeks_total),
                structural_balance=local(
                    structural_balance(
                        total_sponsor_income(econ.income_sponsors, econ.income_sponsor_bonuses),
                        econ.income_spectators,
                        econ.costs_players,
                        econ.costs_staff,
                        econ.costs_arena,
                    )
                ),
                biweekly_balance=local(ingresos_dos_semanas - gastos_dos_semanas),
                biweekly_income=local(ingresos_dos_semanas),
                biweekly_salaries=local(salarios_dos_semanas),
                salary_share_pct=(
                    round(salarios_dos_semanas / ingresos_dos_semanas * 100, 1)
                    if ingresos_dos_semanas > 0
                    else 0.0
                ),
                currency=team.currency_name or "",
            )

        tr = await self._s.scalar(
            select(m.TrainingSnapshot)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        )
        if tr:
            # El porcentaje y la edad media salen del MISMO contexto que usa la
            # proyección de entrenamiento, no de una regla aparte: entrenador,
            # asistentes e intensidad ya están resueltos ahí con su
            # procedencia (dato real o supuesto).
            ctx = await TrainingContextService(self._s).get(team_id)
            eficiencia = (
                te.training_efficiency_pct(
                    ctx.setup.coach_level,
                    ctx.setup.assistant_level_sum,
                    ctx.setup.intensity,
                    ctx.setup.stamina_share,
                )
                if ctx is not None
                else 0.0
            )
            # Edad media de quienes de VERDAD recibieron entrenamiento esta
            # semana (minutos jugados en la posición que entrena), no de toda
            # la plantilla: entrenar Anotación no le llega al portero.
            entrenados = await self._trained_ages(team_id, ctx.trained_skill if ctx else None)
            resp.training = TrainingSummary(
                type_id=tr.training_type,
                type_name=training_name(tr.training_type),
                level=tr.training_level,
                stamina_part=tr.stamina_part,
                trainer_name=tr.trainer_name,
                morale=tr.morale,
                morale_name=TEAM_SPIRIT.get(tr.morale, "?"),
                confidence=tr.self_confidence,
                confidence_name=CONFIDENCE.get(tr.self_confidence, "?"),
                efficiency_pct=eficiencia,
                coach_level=ctx.setup.coach_level if ctx else 0,
                assistant_level_sum=int(ctx.setup.assistant_level_sum) if ctx else 0,
                trained_avg_age=round(sum(entrenados) / len(entrenados), 1) if entrenados else None,
                trained_players=len(entrenados),
            )

        resp.alerts = self._alerts(resp, players)
        return resp

    async def _trained_ages(self, team_id: int, skill: str | None) -> list[float]:
        """Edades, en años con decimales, de los jugadores que recibieron el
        entrenamiento de esta semana. Lista vacía si todavía no se ha jugado
        ningún partido de la semana: ahí no hay a quién medir."""
        if skill is None:
            return []
        vista = await TrainingSquadQueryService(self._s).squad_view(team_id, skill)
        if vista is None:
            return []
        return [
            fila.age_years + fila.age_days / DAYS_PER_HT_YEAR
            for fila in vista.rows
            if fila.current_week_exposure > 0
        ]

    async def _latest_players(self, team_id: int) -> list[tuple[m.PlayerSnapshot, m.Player]]:
        """Último snapshot por jugador (equivalente al DISTINCT ON de PostgreSQL)."""
        latest = (
            select(
                m.PlayerSnapshot.player_id.label("pid"),
                func.max(m.PlayerSnapshot.captured_at).label("mx"),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
            .group_by(m.PlayerSnapshot.player_id)
            .subquery()
        )
        stmt = (
            select(m.PlayerSnapshot, m.Player)
            .join(
                latest,
                (m.PlayerSnapshot.player_id == latest.c.pid)
                & (m.PlayerSnapshot.captured_at == latest.c.mx),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        )
        return [(r[0], r[1]) for r in (await self._s.execute(stmt)).all()]

    def _squad(self, players: list[m.PlayerSnapshot], rate: float) -> SquadSummary:
        n = len(players)
        avg_age = sum(p.age_years + p.age_days / 112 for p in players) / n
        return SquadSummary(
            player_count=n,
            avg_age=round(avg_age, 1),
            total_tsi=sum(p.tsi for p in players),
            top11_tsi=sum(sorted((p.tsi for p in players), reverse=True)[:11]),
            total_salary=int(round(sum(p.salary for p in players) / rate)),
            # Solo bajas reales: el nivel 0 es magullado y puede jugar, así
            # que contarlo inflaba el marcador de lesionados del Dashboard.
            injured_count=sum(1 for p in players if p.injury_level >= 1),
        )

    def _row(self, p: m.PlayerSnapshot, ident: m.Player, rate: float) -> PlayerRow:
        return PlayerRow(
            ht_player_id=ident.ht_player_id,
            name=f"{ident.first_name} {ident.last_name}",
            age_years=p.age_years,
            age_days=p.age_days,
            tsi=p.tsi,
            form=p.form,
            stamina=p.stamina,
            salary=int(round(p.salary / rate)),
            injury_level=p.injury_level,
            skills={alias: getattr(p, col) or 0 for col, alias in SKILL_COLS.items()},
        )

    def _alerts(self, resp: DashboardResponse, players: list[m.PlayerSnapshot]) -> list[Alert]:
        out: list[Alert] = []
        if resp.stale:
            out.append(
                Alert(
                    kind="sync",
                    severity="info",
                    message="Los datos no se sincronizan hace más de 12 horas.",
                )
            )
        if resp.squad and resp.squad.injured_count:
            out.append(
                Alert(
                    kind="injury",
                    severity="warning",
                    message=f"{resp.squad.injured_count} jugador(es) lesionado(s).",
                )
            )
        if resp.finance and resp.squad:
            weeks = (
                resp.finance.cash // abs(resp.finance.weekly_delta)
                if resp.finance.weekly_delta < 0
                else None
            )
            if weeks is not None and weeks < 8:
                out.append(
                    Alert(
                        kind="finance",
                        severity="danger",
                        message=f"Con el balance actual la caja aguanta ~{weeks} semanas.",
                    )
                )
        if players:
            veterans = [p for p in players if p.age_years >= 33]
            if veterans:
                out.append(
                    Alert(
                        kind="squad",
                        severity="info",
                        message=f"{len(veterans)} jugador(es) de 33+ años en plantilla.",
                    )
                )
        return out
