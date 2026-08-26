"""SquadQueryService — plantilla con ratings de posición. HL-021 y HL-022."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.dto.squad import (
    PositionRatingDTO,
    SquadComparison,
    SquadHistoryEntry,
    SquadPlayer,
    SquadResponse,
    SquadTotals,
)
from app.application.queries.weekly import latest_per_iso_week, start_of_iso_week
from app.domain.engines import htms
from app.domain.engines.position_engine import (
    best_position,
    rate,
    rate_all,
)
from app.domain.engines.position_engine import (
    positions as engine_positions,
)
from app.domain.engines.position_engine import (
    special_roles as engine_special_roles,
)
from app.domain.value_objects.ht_constants import (
    PLAYER_AGGRESSIVENESS,
    PLAYER_AGREEABILITY,
    PLAYER_HONESTY,
    SPECIALTIES,
    match_role_short_label,
)
from app.infrastructure.db import models as m

SKILL_COLS = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")

# 2026-08-09, pedido explícitamente: "Último partido" solo debe mostrar
# dato si el partido de verdad fue reciente — caso real probado
# (Volodymyr Manakin): `LastMatch` de playerdetails.xml puede ser de hace
# más de un año, no "la semana pasada". La ventana se calcula contra AHORA
# en cada consulta (nunca una fecha fija guardada).
LAST_MATCH_RECENCY_WINDOW = timedelta(days=7)


class SquadQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        team_id: int,
        position: str | None = None,
        comparison_sync_id: int | None = None,
    ) -> SquadResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None
        # Capitán y lanzador de faltas no son posiciones en cancha, pero sí
        # son decisiones comparables de la plantilla y usan el mismo motor.
        if position is not None and position not in {
            *engine_positions(),
            *engine_special_roles(),
        }:
            raise KeyError(f"posición desconocida: {position}")

        rows = await self._latest(team_id)
        history = await self._history(team_id)

        baseline_at: datetime | None = None
        if comparison_sync_id is not None:
            chosen = next((item for item in history if item.sync_id == comparison_sync_id), None)
            if chosen is None:
                raise KeyError(f"snapshot {comparison_sync_id} desconocido para este equipo")
            baseline_at = datetime.fromisoformat(chosen.captured_at)
            baseline_by_player = await self._snapshots_as_of(team_id, baseline_at)
            comparison = SquadComparison(
                mode="snapshot",
                baseline_sync_id=comparison_sync_id,
                baseline_captured_at=chosen.captured_at,
            )
        else:
            baseline_by_player = {}
            comparison = SquadComparison(mode="previous_change")

        players: list[SquadPlayer] = []
        country_codes = {
            int(country_id): str(country_code).upper()
            for country_id, country_code in (
                await self._s.execute(
                    select(m.WorldContext.country_id, m.WorldContext.country_code).where(
                        m.WorldContext.country_code != ""
                    )
                )
            ).all()
        }
        for snap, ident in rows:
            previous = (
                baseline_by_player.get(snap.player_id)
                if baseline_at is not None
                else await self._previous_snapshot(snap)
            )
            skills = {c: getattr(snap, c) or 0 for c in SKILL_COLS}
            # HL-020: leadership real del jugador (players.xml), no la
            # constante 0 de antes — cierra el aporte al rating de capitán.
            # specialty: 2026-08-09, pedido explícitamente — el lanzador de
            # penaltis lleva un bono si el jugador es Técnico (código 1 en
            # SPECIALTIES), así que el motor de posiciones necesita el
            # código crudo, no solo la etiqueta ya traducida de abajo.
            # 2026-08-09: "loyalty" faltaba aquí — _loyalty_bonus() en
            # position_engine.py siempre devolvía 0 para TODA la app (ningún
            # llamador la pasaba), aunque positions.yaml ya declara la
            # fidelidad como un ajuste del Manual. Bug real, corregido de
            # paso: ahora aporta a cualquier posición de campo, no solo al
            # marcaje individual que la necesita explícitamente.
            player = {
                "skills": skills,
                "form": snap.form,
                "stamina": snap.stamina,
                "experience": snap.experience,
                "leadership": snap.leadership,
                "specialty": snap.specialty,
                "loyalty": snap.loyalty,
            }
            best = best_position(player)
            valor_htms = htms.de_habilidades(
                snap.age_years,
                snap.age_days,
                **{c: skills.get(c) for c in SKILL_COLS},
            )
            here = rate(player, position) if position else None
            # 2026-08-09: SQLite puede devolver el datetime sin tzinfo aunque
            # se guardara con `.replace(tzinfo=UTC)` (mismo patrón defensivo
            # que analysis.py) — sin esto, la resta con `datetime.now(UTC)`
            # lanza TypeError si el valor vuelve naive.
            last_match_is_recent = False
            if snap.last_match_played_at is not None:
                ref = (
                    snap.last_match_played_at
                    if snap.last_match_played_at.tzinfo
                    else snap.last_match_played_at.replace(tzinfo=UTC)
                )
                last_match_is_recent = datetime.now(UTC) - ref <= LAST_MATCH_RECENCY_WINDOW
            players.append(
                SquadPlayer(
                    ht_player_id=ident.ht_player_id,
                    name=f"{ident.first_name} {ident.last_name}",
                    age_years=snap.age_years,
                    age_days=snap.age_days,
                    tsi=snap.tsi,
                    form=snap.form,
                    stamina=snap.stamina,
                    experience=snap.experience,
                    salary=int(round(snap.salary / (team.currency_rate or 1.0))),
                    specialty=SPECIALTIES.get(snap.specialty, f"#{snap.specialty}"),
                    injury_level=snap.injury_level,
                    is_transfer_listed=snap.is_transfer_listed,
                    loyalty=snap.loyalty,
                    leadership=snap.leadership,
                    agreeability=snap.agreeability,
                    agreeability_label=PLAYER_AGREEABILITY.get(
                        snap.agreeability, f"#{snap.agreeability}"
                    ),
                    aggressiveness=snap.aggressiveness,
                    aggressiveness_label=PLAYER_AGGRESSIVENESS.get(
                        snap.aggressiveness, f"#{snap.aggressiveness}"
                    ),
                    honesty=snap.honesty,
                    honesty_label=PLAYER_HONESTY.get(snap.honesty, f"#{snap.honesty}"),
                    country_id=snap.country_id,
                    country_code=country_codes.get(snap.country_id),
                    league_goals=snap.league_goals,
                    cup_goals=snap.cup_goals,
                    friendlies_goals=snap.friendlies_goals,
                    career_goals=snap.career_goals,
                    career_hattricks=snap.career_hattricks,
                    career_assists=snap.career_assists,
                    player_trainer_skill_level=snap.player_trainer_skill_level,
                    player_trainer_type=snap.player_trainer_type,
                    mother_club_bonus=snap.mother_club_bonus,
                    mother_club_team_name=ident.mother_club_team_name,
                    native_league_name=ident.native_league_name,
                    confirmed_career_stage=ident.confirmed_career_stage,
                    confirmed_career_stage_at=(
                        ident.confirmed_career_stage_at.isoformat()
                        if ident.confirmed_career_stage_at is not None
                        else None
                    ),
                    purchase_price=(
                        int(round(ident.purchase_price / (team.currency_rate or 1.0)))
                        if ident.purchase_price is not None
                        else None
                    ),
                    purchased_at=(
                        ident.purchased_at.date().isoformat()
                        if ident.purchased_at is not None
                        else None
                    ),
                    last_match_position=(
                        match_role_short_label(
                            snap.last_match_position_code,
                            snap.last_match_behaviour_code,
                        )
                        if last_match_is_recent and snap.last_match_position_code is not None
                        else None
                    ),
                    last_match_rating=(snap.last_match_rating if last_match_is_recent else None),
                    last_match_played_minutes=(
                        snap.last_match_played_minutes if last_match_is_recent else None
                    ),
                    career_caps=snap.career_caps,
                    career_caps_u20=snap.career_caps_u20,
                    skills=skills,
                    htms=valor_htms.ability,
                    htms28=valor_htms.potential,
                    deltas=self._deltas(snap, previous, team.currency_rate or 1.0),
                    best_position=PositionRatingDTO(
                        position=best.position,
                        label=best.label,
                        rating=best.rating,
                        confidence="config",
                    ),
                    position_rating=(
                        PositionRatingDTO(
                            position=here.position,
                            label=here.label,
                            rating=here.rating,
                            confidence="config",
                        )
                        if here
                        else None
                    ),
                )
            )

        # HL-022: si se pidió una posición, la plantilla va ordenada por ella
        if position:
            players.sort(key=lambda p: -(p.position_rating.rating if p.position_rating else 0))
        else:
            players.sort(key=lambda p: -p.tsi)

        total_tsi = sum(player.tsi for player in players)
        total_salary = sum(player.salary for player in players)
        count = len(players)
        totals = SquadTotals(
            average_age=round(
                sum(player.age_years + player.age_days / 112 for player in players) / count, 1
            )
            if count
            else 0,
            average_form=round(sum(player.form for player in players) / count, 1) if count else 0,
            average_experience=round(sum(player.experience for player in players) / count, 1)
            if count
            else 0,
            average_tsi=round(total_tsi / count) if count else 0,
            total_tsi=total_tsi,
            average_salary=round(total_salary / count) if count else 0,
            total_salary=total_salary,
        )

        return SquadResponse(
            team_id=team_id,
            team_name=team.name,
            currency=team.currency_name or "",
            position=position,
            player_count=count,
            totals=totals,
            comparison=comparison,
            history=history,
            players=players,
        )

    async def player_positions(self, ht_player_id: int) -> list[PositionRatingDTO] | None:
        """Las 19 variantes de un jugador, ordenadas — el panel de HC."""
        stmt = (
            select(m.PlayerSnapshot, m.Player)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.ht_player_id == ht_player_id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).first()
        if row is None:
            return None
        snap = row[0]
        skills = {c: getattr(snap, c) or 0 for c in SKILL_COLS}
        player = {
            "skills": skills,
            "form": snap.form,
            "stamina": snap.stamina,
            "experience": snap.experience,
            "leadership": snap.leadership,
            "loyalty": snap.loyalty,
        }
        return [
            PositionRatingDTO(
                position=r.position, label=r.label, rating=r.rating, confidence="config"
            )
            for r in rate_all(player, include_special=True)
        ]

    async def _latest(self, team_id: int) -> list[tuple[m.PlayerSnapshot, m.Player]]:
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

    async def _previous_snapshot(self, current: m.PlayerSnapshot) -> m.PlayerSnapshot | None:
        """El último cierre semanal anterior del jugador.

        Un diff por cada Sync aparenta precisión diaria. La tabla compara
        contra la última lectura de una semana anterior; lo intra-semanal se
        conserva en BD, pero no se presenta como una nueva tendencia.
        """
        before_week = start_of_iso_week(current.captured_at)
        return await self._s.scalar(
            select(m.PlayerSnapshot)
            .where(
                m.PlayerSnapshot.player_id == current.player_id,
                m.PlayerSnapshot.captured_at < before_week,
            )
            .order_by(m.PlayerSnapshot.captured_at.desc(), m.PlayerSnapshot.id.desc())
            .limit(1)
        )

    async def _snapshots_as_of(
        self, team_id: int, captured_at: datetime
    ) -> dict[int, m.PlayerSnapshot]:
        """Último estado de cada jugador hasta un snapshot histórico elegido."""
        latest = (
            select(
                m.PlayerSnapshot.player_id.label("pid"),
                func.max(m.PlayerSnapshot.captured_at).label("mx"),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(
                m.Player.team_id == team_id,
                m.PlayerSnapshot.captured_at <= captured_at,
            )
            .group_by(m.PlayerSnapshot.player_id)
            .subquery()
        )
        rows = (
            (
                await self._s.execute(
                    select(m.PlayerSnapshot).join(
                        latest,
                        (m.PlayerSnapshot.player_id == latest.c.pid)
                        & (m.PlayerSnapshot.captured_at == latest.c.mx),
                    )
                )
            )
            .scalars()
            .all()
        )
        return {row.player_id: row for row in rows}

    async def _history(self, team_id: int) -> list[SquadHistoryEntry]:
        """Snapshots de equipo disponibles para una comparación explícita.

        Sólo exponemos syncs que realmente escribieron players.xml; una fila
        de playerdetails o un sync repetido sin cambios no es un punto nuevo
        que el usuario pueda comparar.
        """
        rows = await self._s.execute(
            select(
                m.Sync.id,
                func.max(m.PlayerSnapshot.captured_at),
                func.count(m.PlayerSnapshot.id),
            )
            .join(m.PlayerSnapshot, m.PlayerSnapshot.sync_id == m.Sync.id)
            .where(m.Sync.team_id == team_id, m.Sync.kind.contains("players"))
            .group_by(m.Sync.id)
            .order_by(func.max(m.PlayerSnapshot.captured_at))
        )
        all_entries = [
            SquadHistoryEntry(
                sync_id=int(sync_id), captured_at=captured.isoformat(), snapshots=int(count)
            )
            for sync_id, captured, count in rows.all()
            if captured is not None
        ]
        weekly = latest_per_iso_week(
            all_entries, lambda entry: datetime.fromisoformat(entry.captured_at)
        )
        return list(reversed(weekly))[:20]

    @staticmethod
    def _deltas(
        current: m.PlayerSnapshot, previous: m.PlayerSnapshot | None, currency_rate: float
    ) -> dict[str, int]:
        if previous is None:
            return {}

        fields = ("tsi", "form", "stamina", "experience", *SKILL_COLS)
        deltas: dict[str, int] = {}
        for field in fields:
            before, after = getattr(previous, field), getattr(current, field)
            if before is None or after is None:
                continue
            delta = int(after) - int(before)
            if delta:
                deltas[field] = delta

        salary_before = int(round(previous.salary / currency_rate))
        salary_after = int(round(current.salary / currency_rate))
        if salary_after != salary_before:
            deltas["salary"] = salary_after - salary_before
        if previous.is_transfer_listed != current.is_transfer_listed:
            deltas["market"] = 1 if current.is_transfer_listed else -1
        if previous.injury_level != current.injury_level:
            deltas["injury"] = current.injury_level - previous.injury_level
        return deltas
