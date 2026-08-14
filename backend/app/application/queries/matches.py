"""MatchesQueryService — HL-071, HL-072, HL-073, HL-075, HL-076.

Un resultado dice quién ganó; no dice por qué. La diferencia entre «hemos
perdido 1-2» y «hemos generado nueve ocasiones y convertido una mientras el
rival convertía dos de tres» es la diferencia entre lamentar un partido y
cambiar algo la semana siguiente.

Así que este servicio separa deliberadamente **generación** de **definición**.
Son problemas distintos con soluciones distintas: la primera se arregla con
mediocampo y táctica, la segunda con anotación y suerte. Confundirlas lleva a
fichar delanteros cuando el problema es que la pelota no llega.

Sobre la muestra: las tasas de conversión son ruidosas. Con menos de una
docena de ocasiones la diferencia entre 20% y 40% es azar. El servicio
devuelve el tamaño de muestra junto a la tasa para que la cifra no se lea
sola.

2026-08-12, pedido explícito: los partidos NO oficiales (Escaleras/Duelos/
Torneos/Preparación) se excluyen SIEMPRE, sin botón que los reactive — ver
`NON_OFFICIAL_MATCH_TYPES`. El botón que existía para eso ahora controla los
Amistosos (`FRIENDLY_MATCH_TYPES`), que sí son partidos reales, solo que no
cuentan para el historial competitivo por defecto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import (
    season_at_offset,
    season_week_label,
    season_week_offset_for,
)
from app.domain.engines.match_analysis import (
    CHANCE_ZONE_LABELS,
    CHANCE_ZONES,
    SECTORS,
    ChanceTally,
    analyse,
    hatstats,
    loddar_stats,
)
from app.domain.value_objects.ht_constants import (
    NON_OFFICIAL_MATCH_TYPES,
    is_friendly_match_type,
)
from app.infrastructure.db import models as m

# Por debajo de esto una tasa de conversión es una anécdota, no una medida.
MIN_CHANCES_FOR_A_RATE = 12

_BEST_METRICS = (
    ("hatstats", "Valoración"),
    ("midfield", "Mediocampo"),
    ("right_def", "Defensa derecha"),
    ("central_def", "Defensa central"),
    ("left_def", "Defensa izquierda"),
    ("right_att", "Ataque derecha"),
    ("central_att", "Ataque central"),
    ("left_att", "Ataque izquierda"),
)


@dataclass
class SectorRow:
    sector: str
    label: str
    own: int
    opponent: int
    delta: int
    dominance: float


@dataclass
class MatchRow:
    ht_match_id: int
    date: str
    match_type: int
    opponent: str
    is_home: bool
    goals_for: int
    goals_against: int
    result: str
    hatstats: int | None
    hatstats_opponent: int | None
    loddar: float | None
    midfield: int | None


@dataclass
class ZoneChances:
    zone: str
    label: str
    own: int
    opponent: int


@dataclass
class ConversionSummary:
    own_chances: int
    own_goals: int
    own_conversion: float
    opponent_chances: int
    opponent_goals: int
    opponent_conversion: float
    is_reliable: bool
    zones: list[ZoneChances]


@dataclass
class RatingSeriesPoint:
    ht_match_id: int
    date: str
    season_week: str | None
    opponent: str
    result: str
    goals_for: int
    goals_against: int
    midfield: int
    defence: int
    attack: int
    hatstats: int


@dataclass
class MatchDetail:
    ht_match_id: int
    date: str
    opponent: str
    is_home: bool
    score: str
    sectors: list[SectorRow]
    possession: tuple[int, int]
    hatstats: int
    hatstats_opponent: int
    loddar: float
    loddar_opponent: float
    verdict: str
    strengths: list[str]
    weaknesses: list[str]
    own_chances: dict[str, int | float]
    opponent_chances: dict[str, int | float]


@dataclass
class HomeAwayRow:
    scope: str
    label: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int


@dataclass
class BestRating:
    metric: str
    label: str
    value: int
    date: str
    opponent: str
    ht_match_id: int


@dataclass
class MatchesResponse:
    team_name: str
    matches_played: int
    record: str
    goals_for: int
    goals_against: int
    matches: list[MatchRow]
    rating_series: list[RatingSeriesPoint]
    conversion: ConversionSummary
    avg_hatstats: float | None
    best_match: MatchRow | None
    worst_match: MatchRow | None
    available_seasons: list[int]
    current_season: int | None
    selected_season: int | None
    season_label: str
    include_friendlies: bool
    home_away: list[HomeAwayRow]
    results_pie: dict[str, int]
    best_ratings: list[BestRating]
    notes: list[str] = field(default_factory=list)


class MatchesQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _team(self, team_id: int) -> m.Team | None:
        return await self._s.get(m.Team, team_id)

    async def _world(self, team: m.Team) -> m.WorldContext | None:
        if team.ht_league_id is None:
            return None
        return await self._s.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )

    async def _played(self, ht_team_id: int) -> list[m.Match]:
        """Partidos oficiales de ESTE equipo. Los no-oficiales (Escaleras,
        Duelos, Torneos, Preparación) se excluyen aquí siempre — no hay
        override en ningún punto de la herramienta (pedido explícito
        2026-08-12). Los Amistosos SÍ se incluyen: el filtro de amistosos se
        aplica después, sobre esta misma lista, para que el selector de
        temporadas no dependa de si están visibles o no."""
        query = (
            select(m.Match)
            .where(
                (m.Match.home_team_ht_id == ht_team_id)
                | (m.Match.away_team_ht_id == ht_team_id)
            )
            .where(m.Match.home_goals >= 0)
            .where(m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES))
        )
        rows = await self._s.execute(query.order_by(m.Match.played_at))
        return list(rows.scalars())

    async def _ratings(self, ht_match_ids: list[int]) -> dict[tuple[int, bool], m.MatchRating]:
        """Se indexa por (ht_match_id, is_home), no por team_ht_id: en
        Escaleras/Duelos (MatchType 50/62) `team_ht_id` es un ID efímero que
        no coincide con ningún ht_team_id real, ni siquiera el del equipo
        propio (verificado con datos reales de la cuenta) — la posición
        home/away es la única señal fiable para saber de quién es cada fila."""
        if not ht_match_ids:
            return {}
        rows = await self._s.execute(
            select(m.MatchRating).where(m.MatchRating.ht_match_id.in_(ht_match_ids))
        )
        return {(r.ht_match_id, r.is_home): r for r in rows.scalars()}

    async def overview(
        self, team_id: int, *, include_friendlies: bool = False, season: int | None = None
    ) -> MatchesResponse | None:
        """Nombrado `overview` y no `list` a propósito: un método `list` en el
        cuerpo de la clase tapa el builtin, y las anotaciones `list[...]` de los
        métodos siguientes dejan de compilar."""
        team = await self._team(team_id)
        if team is None:
            return None
        all_played = await self._played(team.ht_team_id)
        if not all_played:
            return None

        world = await self._world(team)
        current_season = world.season if world is not None else None

        match_season: dict[int, int | None] = {}
        seasons_seen: set[int] = set()
        for match in all_played:
            offset = season_week_offset_for(world, match.played_at)
            s = season_at_offset(world, weeks_offset=offset)
            match_season[match.ht_match_id] = s
            if s is not None:
                seasons_seen.add(s)
        available_seasons = sorted(seasons_seen, reverse=True)

        played = [
            p for p in all_played
            if (include_friendlies or not is_friendly_match_type(p.match_type))
            and (season is None or match_season.get(p.ht_match_id) == season)
        ]

        if season is None:
            season_label = "Todas las temporadas"
        elif current_season is not None and season == current_season:
            season_label = f"Temporada actual ({season})"
        else:
            season_label = f"Temporada {season}"

        if not played:
            return MatchesResponse(
                team_name=team.name,
                matches_played=0, record="0-0-0", goals_for=0, goals_against=0,
                matches=[], rating_series=[],
                conversion=ConversionSummary(
                    own_chances=0, own_goals=0, own_conversion=0.0,
                    opponent_chances=0, opponent_goals=0, opponent_conversion=0.0,
                    is_reliable=False, zones=[],
                ),
                avg_hatstats=None, best_match=None, worst_match=None,
                available_seasons=available_seasons, current_season=current_season,
                selected_season=season, season_label=season_label,
                include_friendlies=include_friendlies,
                home_away=[], results_pie={"won": 0, "drawn": 0, "lost": 0},
                best_ratings=[],
                notes=["No hay partidos con estos filtros."],
            )

        ratings = await self._ratings([p.ht_match_id for p in played])
        rows: list[MatchRow] = []
        series: list[RatingSeriesPoint] = []
        won = drawn = lost = 0
        gf = ga = 0
        home_played = home_won = home_drawn = home_lost = home_gf = home_ga = 0
        away_played = away_won = away_drawn = away_lost = away_gf = away_ga = 0
        own_tally = ChanceTally()
        opp_tally = ChanceTally()
        best: dict[str, BestRating] = {}

        for match in played:
            is_home = match.home_team_ht_id == team.ht_team_id
            own_goals = match.home_goals if is_home else match.away_goals
            opp_goals = match.away_goals if is_home else match.home_goals
            opponent = match.away_team_name if is_home else match.home_team_name
            date = _iso(match.played_at)
            gf += own_goals
            ga += opp_goals
            if own_goals > opp_goals:
                won += 1
                result = "V"
            elif own_goals == opp_goals:
                drawn += 1
                result = "E"
            else:
                lost += 1
                result = "D"

            if is_home:
                home_played += 1
                home_gf += own_goals
                home_ga += opp_goals
                home_won += result == "V"
                home_drawn += result == "E"
                home_lost += result == "D"
            else:
                away_played += 1
                away_gf += own_goals
                away_ga += opp_goals
                away_won += result == "V"
                away_drawn += result == "E"
                away_lost += result == "D"

            own_r = ratings.get((match.ht_match_id, is_home))
            opp_r = ratings.get((match.ht_match_id, not is_home))
            own_dict = _rating_dict(own_r)
            hs = hatstats(own_dict) if own_r else None

            rows.append(
                MatchRow(
                    ht_match_id=match.ht_match_id,
                    date=date,
                    match_type=match.match_type,
                    opponent=opponent,
                    is_home=is_home,
                    goals_for=own_goals,
                    goals_against=opp_goals,
                    result=result,
                    hatstats=hs,
                    hatstats_opponent=hatstats(_rating_dict(opp_r)) if opp_r else None,
                    loddar=loddar_stats(own_dict) if own_r else None,
                    midfield=own_r.midfield if own_r else None,
                )
            )
            if own_r:
                own_tally.left += own_r.chances_left
                own_tally.center += own_r.chances_center
                own_tally.right += own_r.chances_right
                own_tally.special += own_r.chances_special
                own_tally.other += own_r.chances_other
                own_tally.goals += own_goals

                series.append(
                    RatingSeriesPoint(
                        ht_match_id=match.ht_match_id,
                        date=date,
                        season_week=season_week_label(
                            world, weeks_offset=season_week_offset_for(world, match.played_at)
                        ),
                        opponent=opponent,
                        result=result,
                        goals_for=own_goals,
                        goals_against=opp_goals,
                        midfield=own_r.midfield,
                        defence=own_r.right_def + own_r.central_def + own_r.left_def,
                        attack=own_r.right_att + own_r.central_att + own_r.left_att,
                        hatstats=hs or 0,
                    )
                )

                candidates = {
                    "hatstats": hs or 0,
                    "midfield": own_r.midfield,
                    "right_def": own_r.right_def,
                    "central_def": own_r.central_def,
                    "left_def": own_r.left_def,
                    "right_att": own_r.right_att,
                    "central_att": own_r.central_att,
                    "left_att": own_r.left_att,
                }
                for metric, label in _BEST_METRICS:
                    value = candidates[metric]
                    current_best = best.get(metric)
                    if current_best is None or value > current_best.value:
                        best[metric] = BestRating(
                            metric=metric, label=label, value=value, date=date,
                            opponent=opponent, ht_match_id=match.ht_match_id,
                        )
            if opp_r:
                opp_tally.left += opp_r.chances_left
                opp_tally.center += opp_r.chances_center
                opp_tally.right += opp_r.chances_right
                opp_tally.special += opp_r.chances_special
                opp_tally.other += opp_r.chances_other
                opp_tally.goals += opp_goals

        conversion = ConversionSummary(
            own_chances=own_tally.total, own_goals=own_tally.goals,
            own_conversion=round(own_tally.conversion, 4),
            opponent_chances=opp_tally.total, opponent_goals=opp_tally.goals,
            opponent_conversion=round(opp_tally.conversion, 4),
            is_reliable=own_tally.total >= MIN_CHANCES_FOR_A_RATE
            and opp_tally.total >= MIN_CHANCES_FOR_A_RATE,
            zones=[
                ZoneChances(
                    zone=z, label=CHANCE_ZONE_LABELS[z],
                    own=getattr(own_tally, z), opponent=getattr(opp_tally, z),
                )
                for z in CHANCE_ZONES
            ],
        )

        rated = [r for r in rows if r.hatstats is not None]
        hs_values = [r.hatstats for r in rated if r.hatstats is not None]
        avg_hs = round(sum(hs_values) / len(hs_values), 1) if hs_values else None

        notes: list[str] = []
        if not rated:
            notes.append(
                "Todavía no hay ratings por sector sincronizados, así que los "
                "índices HatStats y LoddarStats están vacíos. Llegan con el "
                "detalle de partido."
            )
        if rated and not conversion.is_reliable and conversion.own_chances:
            notes.append(
                f"Muestra corta: por debajo de {MIN_CHANCES_FOR_A_RATE} "
                "ocasiones la tasa de conversión es ruido, no señal. Se "
                "muestra igualmente, marcada."
            )

        home_away = [
            HomeAwayRow(
                scope="home", label="Local", played=home_played, won=home_won,
                drawn=home_drawn, lost=home_lost, goals_for=home_gf, goals_against=home_ga,
            ),
            HomeAwayRow(
                scope="away", label="Visitante", played=away_played, won=away_won,
                drawn=away_drawn, lost=away_lost, goals_for=away_gf, goals_against=away_ga,
            ),
        ]

        return MatchesResponse(
            team_name=team.name,
            matches_played=len(rows),
            record=f"{won}-{drawn}-{lost}",
            goals_for=gf,
            goals_against=ga,
            matches=list(reversed(rows)),
            rating_series=series,
            conversion=conversion,
            avg_hatstats=avg_hs,
            best_match=max(rated, key=lambda r: r.hatstats or 0) if rated else None,
            worst_match=min(rated, key=lambda r: r.hatstats or 0) if rated else None,
            available_seasons=available_seasons,
            current_season=current_season,
            selected_season=season,
            season_label=season_label,
            include_friendlies=include_friendlies,
            home_away=home_away,
            results_pie={"won": won, "drawn": drawn, "lost": lost},
            best_ratings=sorted(best.values(), key=lambda b: [m[0] for m in _BEST_METRICS].index(b.metric)),
            notes=notes,
        )

    async def detail(self, team_id: int, ht_match_id: int) -> MatchDetail | None:
        team = await self._team(team_id)
        if team is None:
            return None
        match = await self._s.scalar(
            select(m.Match).where(m.Match.ht_match_id == ht_match_id)
        )
        if match is None:
            return None

        is_home = match.home_team_ht_id == team.ht_team_id
        ratings = await self._ratings([ht_match_id])
        own_r = ratings.get((ht_match_id, is_home))
        opp_r = ratings.get((ht_match_id, not is_home))
        if own_r is None:
            return None

        own_goals = match.home_goals if is_home else match.away_goals
        opp_goals = match.away_goals if is_home else match.home_goals
        own_chances = _side_tally(own_r, own_goals)
        opp_chances = _side_tally(opp_r, opp_goals)
        possession = (own_r.possession_first_half, own_r.possession_second_half)
        result = analyse(
            own_ratings=_rating_dict(own_r),
            opponent_ratings=_rating_dict(opp_r),
            own_chances=own_chances,
            opponent_chances=opp_chances,
            possession=possession,
        )

        return MatchDetail(
            ht_match_id=ht_match_id,
            date=_iso(match.played_at),
            opponent=match.away_team_name if is_home else match.home_team_name,
            is_home=is_home,
            score=f"{own_goals}-{opp_goals}",
            sectors=[
                SectorRow(
                    sector=s.sector, label=s.label, own=s.own,
                    opponent=s.opponent, delta=s.delta, dominance=round(s.dominance, 3),
                )
                for s in result.sectors
            ],
            possession=possession,
            hatstats=result.hatstats_own,
            hatstats_opponent=result.hatstats_opponent,
            loddar=result.loddar_own,
            loddar_opponent=result.loddar_opponent,
            verdict=result.verdict,
            strengths=result.strengths,
            weaknesses=result.weaknesses,
            own_chances=_tally_dict(own_chances),
            opponent_chances=_tally_dict(opp_chances),
        )


def _side_tally(r: m.MatchRating | None, goals: int) -> ChanceTally:
    if r is None:
        return ChanceTally(goals=goals)
    return ChanceTally(
        left=r.chances_left, center=r.chances_center, right=r.chances_right,
        special=r.chances_special, other=r.chances_other, goals=goals,
    )


def _rating_dict(r: m.MatchRating | None) -> dict[str, int]:
    if r is None:
        return dict.fromkeys(SECTORS, 0)
    return {
        "midfield": r.midfield,
        "right_def": r.right_def, "central_def": r.central_def, "left_def": r.left_def,
        "right_att": r.right_att, "central_att": r.central_att, "left_att": r.left_att,
    }


def _tally_dict(t: ChanceTally) -> dict[str, int | float]:
    return {
        "left": t.left, "center": t.center, "right": t.right,
        "special": t.special, "other": t.other,
        "total": t.total, "goals": t.goals,
        "conversion": round(t.conversion, 4),
    }


def _iso(dt: datetime) -> str:
    return dt.date().isoformat()
