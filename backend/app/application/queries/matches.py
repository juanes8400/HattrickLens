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
docena de ocasiones de un tipo, la diferencia entre 20% y 40% es azar. El
servicio devuelve el tamaño de muestra junto a cada tasa para que la cifra no
se lea sola.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.match_analysis import (
    SECTORS,
    ChanceTally,
    analyse,
    hatstats,
    loddar_stats,
)
from app.domain.value_objects.ht_constants import NON_OFFICIAL_MATCH_TYPES
from app.infrastructure.db import models as m

# Por debajo de esto una tasa de conversión es una anécdota, no una medida.
MIN_CHANCES_FOR_A_RATE = 12

# Identificadores de evento de Hattrick agrupados por tipo de ocasión.
# Mapa parcial y declarado como tal: se completa al sincronizar matchdetails.
GOAL_EVENTS = range(100, 200)
CHANCE_EVENTS = range(200, 400)


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
class ConversionRate:
    kind: str
    label: str
    chances: int
    goals: int
    rate: float
    is_reliable: bool


@dataclass
class RatingSeriesPoint:
    date: str
    opponent: str
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
    own_chances: dict[str, int]
    opponent_chances: dict[str, int]


@dataclass
class MatchesResponse:
    team_name: str
    matches_played: int
    record: str
    goals_for: int
    goals_against: int
    matches: list[MatchRow]
    rating_series: list[RatingSeriesPoint]
    conversion: list[ConversionRate]
    avg_hatstats: float | None
    best_match: MatchRow | None
    worst_match: MatchRow | None
    notes: list[str] = field(default_factory=list)


class MatchesQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _team(self, team_id: int) -> m.Team | None:
        return await self._s.get(m.Team, team_id)

    async def _played(self, ht_team_id: int, include_non_official: bool = False) -> list[m.Match]:
        query = (
            select(m.Match)
            .where(
                (m.Match.home_team_ht_id == ht_team_id)
                | (m.Match.away_team_ht_id == ht_team_id)
            )
            .where(m.Match.home_goals >= 0)
        )
        if not include_non_official:
            query = query.where(m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES))
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
        self, team_id: int, include_non_official: bool = False
    ) -> MatchesResponse | None:
        """Nombrado `overview` y no `list` a propósito: un método `list` en el
        cuerpo de la clase tapa el builtin, y las anotaciones `list[...]` de los
        métodos siguientes dejan de compilar."""
        team = await self._team(team_id)
        if team is None:
            return None
        played = await self._played(team.ht_team_id, include_non_official)
        if not played:
            return None

        ratings = await self._ratings([p.ht_match_id for p in played])
        rows: list[MatchRow] = []
        series: list[RatingSeriesPoint] = []
        won = drawn = lost = 0
        gf = ga = 0

        for match in played:
            is_home = match.home_team_ht_id == team.ht_team_id
            own_goals = match.home_goals if is_home else match.away_goals
            opp_goals = match.away_goals if is_home else match.home_goals
            opponent = match.away_team_name if is_home else match.home_team_name
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

            own_r = ratings.get((match.ht_match_id, is_home))
            opp_r = ratings.get((match.ht_match_id, not is_home))
            own_dict = _rating_dict(own_r)
            hs = hatstats(own_dict) if own_r else None

            rows.append(
                MatchRow(
                    ht_match_id=match.ht_match_id,
                    date=_iso(match.played_at),
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
                series.append(
                    RatingSeriesPoint(
                        date=_iso(match.played_at),
                        opponent=opponent,
                        midfield=own_r.midfield,
                        defence=own_r.right_def + own_r.central_def + own_r.left_def,
                        attack=own_r.right_att + own_r.central_att + own_r.left_att,
                        hatstats=hs or 0,
                    )
                )

        tallies = await self._tallies(team.ht_team_id, [p.ht_match_id for p in played])
        conversion = _conversion_rates(tallies)

        rated = [r for r in rows if r.hatstats is not None]
        hs_values = [r.hatstats for r in rated if r.hatstats is not None]
        avg_hs = round(sum(hs_values) / len(hs_values), 1) if hs_values else None

        notes: list[str] = []
        if not include_non_official:
            notes.append(
                "Escaleras y Duelos no se muestran (no son partidos oficiales): "
                "actívalos con el botón de arriba si quieres verlos."
            )
        if not rated:
            notes.append(
                "Todavía no hay ratings por sector sincronizados, así que los "
                "índices HatStats y LoddarStats están vacíos. Llegan con el "
                "detalle de partido."
            )
        weak = [c.label for c in conversion if not c.is_reliable and c.chances]
        if weak:
            notes.append(
                f"Muestra corta en {', '.join(weak)}: por debajo de "
                f"{MIN_CHANCES_FOR_A_RATE} ocasiones la tasa de conversión es "
                "ruido, no señal. Se muestra igualmente, marcada."
            )

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

        own_chances, opp_chances = await self._match_tallies(ht_match_id, team.ht_team_id)
        possession = (own_r.possession_first_half, own_r.possession_second_half)
        result = analyse(
            own_ratings=_rating_dict(own_r),
            opponent_ratings=_rating_dict(opp_r),
            own_chances=own_chances,
            opponent_chances=opp_chances,
            possession=possession,
        )

        own_goals = match.home_goals if is_home else match.away_goals
        opp_goals = match.away_goals if is_home else match.home_goals
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

    async def _events(self, ht_match_ids: list[int]) -> list[m.MatchEvent]:
        if not ht_match_ids:
            return []
        rows = await self._s.execute(
            select(m.MatchEvent).where(m.MatchEvent.ht_match_id.in_(ht_match_ids))
        )
        return list(rows.scalars())

    async def _match_tallies(
        self, ht_match_id: int, ht_team_id: int
    ) -> tuple[ChanceTally, ChanceTally]:
        events = await self._events([ht_match_id])
        own = _tally([e for e in events if e.subject_team_ht_id == ht_team_id])
        opp = _tally([e for e in events if e.subject_team_ht_id not in (ht_team_id, 0)])
        return own, opp

    async def _tallies(self, ht_team_id: int, ht_match_ids: list[int]) -> ChanceTally:
        events = await self._events(ht_match_ids)
        return _tally([e for e in events if e.subject_team_ht_id == ht_team_id])


def _tally(events: list[m.MatchEvent]) -> ChanceTally:
    """Cuenta ocasiones y goles. Sin eventos devuelve ceros, y las tasas que
    salen de ahí se marcan como no fiables aguas arriba."""
    t = ChanceTally()
    for e in events:
        is_goal = e.event_type_id in GOAL_EVENTS
        is_chance = is_goal or e.event_type_id in CHANCE_EVENTS
        if not is_chance:
            continue
        t.normal += 1
        if is_goal:
            t.normal_goals += 1
    return t


def _conversion_rates(t: ChanceTally) -> list[ConversionRate]:
    out = []
    for kind, label, chances, goals in [
        ("normal", "Ocasiones normales", t.normal, t.normal_goals),
        ("special", "Eventos especiales", t.special, t.special_goals),
        ("counter", "Contraataques", t.counter, t.counter_goals),
        ("total", "Total", t.total, t.goals),
    ]:
        out.append(
            ConversionRate(
                kind=kind, label=label, chances=chances, goals=goals,
                rate=round(goals / chances, 4) if chances else 0.0,
                is_reliable=chances >= MIN_CHANCES_FOR_A_RATE,
            )
        )
    return out


def _rating_dict(r: m.MatchRating | None) -> dict[str, int]:
    if r is None:
        return dict.fromkeys(SECTORS, 0)
    return {
        "midfield": r.midfield,
        "right_def": r.right_def, "central_def": r.central_def, "left_def": r.left_def,
        "right_att": r.right_att, "central_att": r.central_att, "left_att": r.left_att,
    }


def _tally_dict(t: ChanceTally) -> dict[str, int]:
    return {
        "normal": t.normal, "normalGoals": t.normal_goals,
        "special": t.special, "specialGoals": t.special_goals,
        "counter": t.counter, "counterGoals": t.counter_goals,
        "total": t.total, "goals": t.goals,
    }


def _iso(dt: datetime) -> str:
    return dt.date().isoformat()
