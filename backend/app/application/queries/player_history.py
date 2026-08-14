"""Historia real de un jugador + su posición dentro de la distribución de la
plantilla — HL-15x, ficha de jugador ampliada.

Todo lo de aquí es append-only (`player_snapshots`, `player_match_ratings`):
no hay nada calculado/proyectado, es lo que realmente se ha sincronizado.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SKILL_COLS
from app.application.queries.weekly import latest_per_iso_week
from app.domain.engines import experience_engine as exp
from app.domain.engines.stats import gaussian_kde, kde_grid, percentile_rank
from app.domain.value_objects.ht_constants import (
    MATCH_TYPE_CUP,
    MATCH_TYPE_FRIENDLY,
    MATCH_TYPE_FRIENDLY_CUP_RULES,
    MATCH_TYPE_INTERNATIONAL_FRIENDLY,
    MATCH_TYPE_INTERNATIONAL_FRIENDLY_CUP_RULES,
    MATCH_TYPE_LEAGUE,
    MATCH_TYPE_MASTERS,
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE,
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES,
    MATCH_TYPE_NATIONAL_TEAM_FRIENDLY,
    MATCH_TYPE_QUALIFICATION,
    MATCH_TYPE_YOUTH_FRIENDLY,
    MATCH_TYPE_YOUTH_FRIENDLY_CUP_RULES,
    MATCH_TYPE_YOUTH_LEAGUE,
    NON_OFFICIAL_MATCH_TYPES,
)
from app.infrastructure.db import models as m

# match_type real (Match.match_type) → categoría de experience_engine.
# Cotejado 2026-08-05 contra docs/reference/tabla_experiencia.html: Masters,
# amistoso de selección y liga/amistoso juvenil SÍ tienen un valor real y
# corresponden 1:1 a un match_type, así que ya puntúan. La selección nacional
# COMPETITIVA (10/11) sigue fuera de `MATCH_TYPE_TO_EXPERIENCE_CATEGORY` a
# propósito: ese código no distingue Mundial/Copa continental/Copa de
# Naciones ni sus rondas de eliminatoria (7 a 70 puntos según la tabla real),
# así que asignarle un valor sería inventarlo — se cuenta aparte, sin
# puntuar, en `MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_TYPES` (ver
# `experience_progress`). Es preferible una observación descartada a
# contaminar la media.
#
# 2026-08-11, pedido explícito: Torneo liga/playoff (además de Escalera,
# Duelo y Preparación, que ya estaban fuera) tampoco cuenta — son partidos
# de mentiras, así que quedan fuera de `NON_OFFICIAL_MATCH_TYPES` y de aquí.
MATCH_TYPE_TO_EXPERIENCE_CATEGORY = {
    MATCH_TYPE_LEAGUE: "league",
    MATCH_TYPE_QUALIFICATION: "qualification",
    MATCH_TYPE_CUP: "cup",
    MATCH_TYPE_FRIENDLY: "friendly",
    MATCH_TYPE_FRIENDLY_CUP_RULES: "friendly",
    MATCH_TYPE_INTERNATIONAL_FRIENDLY: "friendly_international",
    MATCH_TYPE_INTERNATIONAL_FRIENDLY_CUP_RULES: "friendly_international",
    MATCH_TYPE_MASTERS: "masters",
    MATCH_TYPE_NATIONAL_TEAM_FRIENDLY: "national_team_friendly",
    MATCH_TYPE_YOUTH_LEAGUE: "youth_league",
    MATCH_TYPE_YOUTH_FRIENDLY: "youth_friendly",
    MATCH_TYPE_YOUTH_FRIENDLY_CUP_RULES: "youth_friendly",
}

# Partidos de selección detectados pero deliberadamente sin puntaje — ver el
# comentario de arriba y el campo `unscored_national_matches` en
# `ExperienceProgress`.
MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_TYPES = frozenset({
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE,
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES,
})


def experience_category(match_type: int, cup_level: int = -1) -> str | None:
    """Resolve the exact experience bucket exposed by CHPP.

    MatchType 3 identifies every official cup match, while CupLevel separates
    the main cup (1) from Challenger (2) and Consolation (3). Those secondary
    cups award one quarter of the main-cup experience, so treating all three
    as ``cup`` would overstate both player progress and calibration intervals.
    """
    if match_type == MATCH_TYPE_CUP and cup_level in {2, 3}:
        return "cup_secondary"
    return MATCH_TYPE_TO_EXPERIENCE_CATEGORY.get(match_type)

# Las 11 variables del timeline/radar: los 7 skills + experiencia, fidelidad,
# forma y condición (stamina) — HL-15x #5, ampliado a pedido del usuario para
# que el radar "Base del jugador" tenga más de 2 ejes. `form`/`stamina` son
# columnas propias de PlayerSnapshot (no parte de SKILL_COLS), pero
# `getattr` las lee igual.
HISTORY_SKILL_COLS = (*SKILL_COLS, "experience", "loyalty", "form", "stamina")

# HL-15x #99: el usuario pidió excluir Balón Parado del top-3 de habilidades
# (histograma de percentil) — se entrena aparte y no define el "perfil"
# principal del jugador de la misma forma que las otras 6.
SKILL_COLS_FOR_TOP3 = tuple(c for c in SKILL_COLS if c != "set_pieces")


@dataclass
class SnapshotPoint:
    captured_at: str
    age_years: int
    age_days: int
    tsi: int
    salary: int
    skills: dict[str, int]


@dataclass
class MatchRatingPoint:
    ht_match_id: int
    captured_at: str
    position_code: int
    played_minutes: int
    rating: float


@dataclass
class Distribution:
    grid: list[float]
    density: list[float]
    values: list[float]
    own_value: float


class PlayerHistoryQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def snapshot_history(self, ht_player_id: int) -> list[SnapshotPoint]:
        """Todo el historial real de snapshots del jugador, ordenado. Hoy
        puede ser muy corto (cuenta nueva) — se devuelve tal cual, sin
        rellenar puntos que no existen."""
        stmt = (
            select(m.PlayerSnapshot)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.ht_player_id == ht_player_id)
            .order_by(m.PlayerSnapshot.captured_at.asc())
        )
        rows = latest_per_iso_week(
            (await self._s.execute(stmt)).scalars().all(), lambda row: row.captured_at
        )
        return [
            SnapshotPoint(
                captured_at=snap.captured_at.isoformat(),
                age_years=snap.age_years, age_days=snap.age_days,
                tsi=snap.tsi, salary=snap.salary,
                skills={c: getattr(snap, c) or 0 for c in HISTORY_SKILL_COLS},
            )
            for snap in rows
        ]

    async def match_rating_history(self, ht_player_id: int) -> list[MatchRatingPoint]:
        # Escaleras, Duelos, Torneos y Preparación no son partidos reales —
        # pedido explícito 2026-08-11: fuera del historial de ratings. Un
        # `outerjoin` (no inner) porque un rating sin fila `Match` todavía
        # (orden de sync) no es un partido de mentiras confirmado — se
        # mantiene en vez de descartarlo por una duda.
        stmt = (
            select(m.PlayerMatchRating, m.Match)
            .join(m.Player, m.Player.id == m.PlayerMatchRating.player_id)
            .outerjoin(m.Match, m.Match.ht_match_id == m.PlayerMatchRating.ht_match_id)
            .where(m.Player.ht_player_id == ht_player_id)
            .order_by(m.PlayerMatchRating.captured_at.asc())
        )
        rows = (await self._s.execute(stmt)).all()
        return [
            MatchRatingPoint(
                ht_match_id=r.ht_match_id, captured_at=r.captured_at.isoformat(),
                position_code=r.position_code, played_minutes=r.played_minutes,
                rating=r.rating,
            )
            for r, match in rows
            if match is None or match.match_type not in NON_OFFICIAL_MATCH_TYPES
        ]

    async def squad_distributions(
        self, team_id: int, ht_player_id: int, currency_rate: float
    ) -> dict[str, Distribution] | None:
        """KDE de TSI, Salario y $/TSI sobre la plantilla activa, con el
        valor de este jugador para resaltar — HL-15x #8. `None` si el
        jugador no está en la plantilla (ya no está en el club)."""
        latest = await self._latest_snapshots_by_ht_id(team_id)
        own_snap = latest.get(ht_player_id)
        if own_snap is None:
            return None

        snaps = list(latest.values())
        tsi_values = [float(s.tsi) for s in snaps]
        salary_values = [float(s.salary) / max(currency_rate, 1.0) for s in snaps]
        ratio_values = [
            (float(s.salary) / max(currency_rate, 1.0)) / s.tsi if s.tsi > 0 else 0.0
            for s in snaps
        ]

        own_tsi = float(own_snap.tsi)
        own_salary = float(own_snap.salary) / max(currency_rate, 1.0)
        own_ratio = own_salary / own_tsi if own_tsi > 0 else 0.0

        def build(values: list[float], own_value: float) -> Distribution:
            grid = kde_grid(values)
            return Distribution(
                grid=grid, density=gaussian_kde(values, grid),
                values=values, own_value=own_value,
            )

        return {
            "tsi": build(tsi_values, own_tsi),
            "salary": build(salary_values, own_salary),
            "salaryPerTsi": build(ratio_values, own_ratio),
        }

    async def top_skill_distributions(
        self, team_id: int, ht_player_id: int, top_n: int = 3
    ) -> dict[str, Distribution] | None:
        """KDE de las top-N habilidades del jugador (excluye Balón Parado)
        sobre la plantilla activa, cada una con su valor propio resaltado —
        HL-15x #99, reemplaza el gauge de percentil de una sola habilidad."""
        latest = await self._latest_snapshots_by_ht_id(team_id)
        own_snap = latest.get(ht_player_id)
        if own_snap is None:
            return None
        own_skills = {c: getattr(own_snap, c) or 0 for c in SKILL_COLS_FOR_TOP3}
        top_skills = sorted(own_skills, key=lambda s: -own_skills[s])[:top_n]
        snaps = list(latest.values())

        out: dict[str, Distribution] = {}
        for skill in top_skills:
            values = [float(getattr(s, skill) or 0) for s in snaps]
            own_value = float(own_skills[skill])
            grid = kde_grid(values)
            out[skill] = Distribution(
                grid=grid, density=gaussian_kde(values, grid),
                values=values, own_value=own_value,
            )
        return out

    async def dominant_skill_percentile(
        self, team_id: int, ht_player_id: int
    ) -> dict[str, Any] | None:
        """Percentil del jugador dentro de la plantilla activa en SU skill
        dominante (la más alta entre las 7) — HL-15x #23."""
        latest = await self._latest_snapshots_by_ht_id(team_id)
        own_snap = latest.get(ht_player_id)
        if own_snap is None:
            return None
        own_skills = {c: getattr(own_snap, c) or 0 for c in SKILL_COLS}
        dominant = max(own_skills, key=lambda s: own_skills[s])
        own_value = float(own_skills[dominant])
        peers = [float(getattr(s, dominant) or 0) for s in latest.values()]
        return {
            "skill": dominant,
            "value": own_value,
            "percentile": round(percentile_rank(peers, own_value), 1),
            "squadSize": len(peers),
        }

    async def experience_progress(self, ht_player_id: int) -> exp.ExperienceProgress | None:
        """% real hacia la próxima subida de experiencia — HL-15x #11, fórmula
        del Manual No Escrito (`experience_engine`, ya verificada contra
        Hattrick Control para liga y amistoso internacional).

        Cuenta partidos REALES jugados por este jugador (de
        `player_match_ratings`, cruzado con `matches` por `match_type`)
        desde el snapshot más antiguo con el mismo nivel de experiencia que
        tiene hoy — es decir, desde que EMPEZAMOS a verlo en ese nivel, no
        desde que realmente subió (eso puede haber sido antes de que esta
        cuenta empezara a sincronizar). El resultado puede subestimar el
        progreso real para un nivel que llevaba tiempo, pero nunca inventa
        partidos que no hemos visto.

        2026-08-05, pedido explícitamente: cada partido puntúa proporcional
        a los minutos jugados sobre 90 (jugar 70 = 70/90 de los puntos de esa
        competencia; 90 o más = el 100%, nunca más) — `player_match_ratings`
        ya trae `played_minutes` por partido, así que es un peso, no un
        fichero nuevo.

        También cierra el punto ciego de selección nacional: `Caps` (carry-
        forward en cada snapshot, ver `repositories.append_snapshot`) es un
        contador de carrera independiente de si `LastMatch` alcanzó a
        capturar ESE partido concreto — si Caps subió más de lo que
        `player_match_ratings` puede explicar, hay partido(s) de selección
        que Hattrick confirma pero de los que nunca vimos el detalle (el
        club jugó después y LastMatch quedó sobrescrito antes del siguiente
        sync). Esos entran también en `unscored_national_matches`.
        """
        snap_stmt = (
            select(
                m.PlayerSnapshot.captured_at, m.PlayerSnapshot.experience,
                m.PlayerSnapshot.career_caps,
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.ht_player_id == ht_player_id)
            .order_by(m.PlayerSnapshot.captured_at.asc())
        )
        snaps = latest_per_iso_week(
            (await self._s.execute(snap_stmt)).all(), lambda row: row.captured_at
        )
        if not snaps:
            return None
        current_level = snaps[-1].experience
        since_date = snaps[-1].captured_at
        caps_at_since_date = snaps[-1].career_caps
        for row in reversed(snaps):
            if row.experience == current_level:
                since_date = row.captured_at
                caps_at_since_date = row.career_caps
            else:
                break
        caps_now = snaps[-1].career_caps

        stmt = (
            select(
                m.Match.match_type,
                m.Match.cup_level,
                m.PlayerMatchRating.played_minutes,
            )
            .select_from(m.PlayerMatchRating)
            .join(m.Player, m.Player.id == m.PlayerMatchRating.player_id)
            .join(m.Match, m.Match.ht_match_id == m.PlayerMatchRating.ht_match_id)
            .where(
                m.Player.ht_player_id == ht_player_id,
                m.PlayerMatchRating.captured_at >= since_date,
            )
        )
        rows = (await self._s.execute(stmt)).all()
        counts: dict[str, float] = {"league": 0.0, "cup": 0.0, "friendly": 0.0}
        national_friendly_seen = 0
        national_competitive_seen = 0
        for mt, cup_level, played_minutes in rows:
            weight = min(played_minutes / 90.0, 1.0) if played_minutes > 0 else 0.0
            category = experience_category(mt, cup_level)
            if category:
                counts[category] = counts.get(category, 0.0) + weight
                if category == "national_team_friendly":
                    national_friendly_seen += 1
            elif mt in MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_TYPES:
                national_competitive_seen += 1

        caps_gained = (
            caps_now - caps_at_since_date
            if caps_now is not None and caps_at_since_date is not None
            else None
        )
        seen_national = national_friendly_seen + national_competitive_seen
        blind_spot = max(caps_gained - seen_national, 0) if caps_gained is not None else 0
        unscored_national_matches = national_competitive_seen + blind_spot

        return exp.progress(counts, unscored_national_matches=unscored_national_matches)

    async def experience_level_up_observations(
        self, team_id: int
    ) -> tuple[list[exp.LevelUp], int]:
        """Build calibration samples from real, fully observed intervals.

        An experience snapshot only exposes an integer level.  A first sighting
        at a level could have happened anywhere within that level, so it must
        never become a calibration sample.  We start an interval only after a
        previous level-up was seen, then add the points from matches the player
        actually played until the next observed level-up.

        The returned crossing count includes discarded intervals.  It tells the
        UI why a team can have seen level changes but still lack calibration
        evidence.
        """
        snapshot_rows = (
            await self._s.execute(
                select(
                    m.Player.id,
                    m.Player.first_name,
                    m.Player.last_name,
                    m.PlayerSnapshot.captured_at,
                    m.PlayerSnapshot.experience,
                )
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                .where(m.Player.team_id == team_id)
                .order_by(m.Player.id, m.PlayerSnapshot.captured_at)
            )
        ).all()

        # Match.played_at, rather than the later CHPP capture timestamp, keeps
        # an interval tied to the actual match that awarded experience.
        # played_minutes viaja también: 2026-08-05, cada partido pesa
        # proporcional a los minutos jugados sobre 90 (ver experience_progress).
        match_rows = (
            await self._s.execute(
                select(
                    m.PlayerMatchRating.player_id,
                    m.Match.played_at,
                    m.Match.match_type,
                    m.Match.cup_level,
                    m.PlayerMatchRating.played_minutes,
                )
                .select_from(m.PlayerMatchRating)
                .join(m.Player, m.Player.id == m.PlayerMatchRating.player_id)
                .join(m.Match, m.Match.ht_match_id == m.PlayerMatchRating.ht_match_id)
                .where(
                    m.Player.team_id == team_id,
                    m.PlayerMatchRating.played_minutes > 0,
                )
                .order_by(m.PlayerMatchRating.player_id, m.Match.played_at)
            )
        ).all()

        snapshots_by_player: dict[int, list[tuple[str, datetime, int]]] = {}
        for player_id, first, last, captured_at, level in snapshot_rows:
            name = f"{first} {last}".strip()
            snapshots_by_player.setdefault(int(player_id), []).append(
                (name, captured_at, int(level))
            )

        matches_by_player: dict[int, list[tuple[datetime, int, int, int]]] = {}
        for player_id, played_at, match_type, cup_level, played_minutes in match_rows:
            matches_by_player.setdefault(int(player_id), []).append(
                (played_at, int(match_type), int(cup_level), int(played_minutes))
            )

        observations: list[exp.LevelUp] = []
        crossings_seen = 0
        for player_id, snapshots in snapshots_by_player.items():
            snapshots = latest_per_iso_week(snapshots, lambda item: item[1])
            if not snapshots:
                continue

            name, _, previous_level = snapshots[0]
            # A player's first sighting might be mid-level. It is not an anchor.
            level_started_at: datetime | None = None
            player_matches = matches_by_player.get(player_id, [])

            for _, captured_at, level in snapshots[1:]:
                if level == previous_level:
                    continue

                if level < previous_level:
                    # A malformed/out-of-order history must not manufacture an
                    # interval. Reset the anchor and wait for a clean pop.
                    previous_level = level
                    level_started_at = None
                    continue

                crossings_seen += 1
                is_single_level_pop = level == previous_level + 1
                if is_single_level_pop and level_started_at is not None:
                    counts: dict[str, float] = {}
                    for played_at, match_type, cup_level, played_minutes in player_matches:
                        if level_started_at < played_at <= captured_at:
                            category = experience_category(match_type, cup_level)
                            if category is not None:
                                weight = min(played_minutes / 90.0, 1.0)
                                counts[category] = counts.get(category, 0.0) + weight
                    accumulated = exp.points(counts)
                    if accumulated > 0:
                        observations.append(
                            exp.LevelUp(
                                player=name,
                                from_level=previous_level,
                                to_level=level,
                                points_accumulated=accumulated,
                            )
                        )

                # The snapshot that exposes the new level is the only safe
                # beginning of the next interval. A multi-level jump has no
                # reliable boundary for either individual level.
                level_started_at = captured_at if is_single_level_pop else None
                previous_level = level

        return observations, crossings_seen

    async def _latest_snapshots_by_ht_id(self, team_id: int) -> dict[int, m.PlayerSnapshot]:
        """Último snapshot real de cada jugador activo de la plantilla,
        indexado por `ht_player_id` — base compartida de distribuciones y
        percentil, ambos sobre "la plantilla tal como está ahora"."""
        stmt = (
            select(m.PlayerSnapshot, m.Player)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
        )
        rows = (await self._s.execute(stmt)).all()
        latest: dict[int, m.PlayerSnapshot] = {}
        for snap, player in rows:
            prev = latest.get(player.ht_player_id)
            if prev is None or snap.captured_at > prev.captured_at:
                latest[player.ht_player_id] = snap
        return latest
