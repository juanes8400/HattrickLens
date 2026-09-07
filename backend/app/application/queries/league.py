"""LeagueQueryService — HL-080, HL-083, HL-090, HL-091, HL-094.

Clasificación, calendario y la simulación de temporada que los convierte en
probabilidades.

Una nota sobre las reglas de CHPP que da forma a este módulo: está permitido
mostrar los datos actuales de otros equipos, pero no llevar un histórico de la
evolución de sus jugadores. Por eso aquí se trabaja con **resultados y
clasificación** — que son públicos y colectivos — y nunca con la ficha
individual de los jugadores rivales.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.season_simulator import (
    Fixture,
    TeamRecord,
    best_worst_case,
    forecast_match,
    model_info,
    simulate,
)
from app.infrastructure.db import models as m

LEAGUE_MATCH_TYPE = 1


@dataclass
class StandingRow:
    position: int
    ht_team_id: int
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    is_own_team: bool


@dataclass
class TeamHistoryRow:
    ht_team_id: int
    name: str
    is_own_team: bool
    # Alineados con LeagueHistory.rounds — None donde esa jornada no se ha
    # sincronizado todavía (no se rellena hacia adelante ni se inventa).
    positions: list[int | None]
    points: list[int | None]


@dataclass
class LeagueHistory:
    rounds: list[int]
    teams: list[TeamHistoryRow]


@dataclass
class BestWorstRow:
    ht_team_id: int
    name: str
    remaining_matches: int
    current_points: int
    current_position: int
    best_case_position_distribution: dict[int, float]
    best_case_expected_points: float
    worst_case_position_distribution: dict[int, float]
    worst_case_expected_points: float


@dataclass
class FixtureRow:
    date: str
    match_round: int
    home: str
    away: str
    played: bool
    score: str | None


@dataclass
class OutlookRow:
    ht_team_id: int
    name: str
    is_own_team: bool
    current_position: int
    current_points: int
    expected_points: float
    expected_position: float
    most_likely_position: int
    title_probability: float
    promotion_probability: float
    second_to_fourth_probability: float
    relegation_playoff_probability: float
    relegation_probability: float
    attack_strength: float
    defence_strength: float
    position_distribution: dict[int, float]


@dataclass
class LeagueResponse:
    team_name: str
    series_name: str | None
    season: int | None
    rounds_played: int
    rounds_remaining: int
    standings: list[StandingRow]
    # Clasificación Local/Visitante — pedido explícitamente 2026-08-08,
    # calculadas desde los resultados reales (ver `_standings_from_matches`);
    # `standings` (arriba) sigue siendo la combinada oficial de CHPP.
    standings_home: list[StandingRow]
    standings_away: list[StandingRow]
    history: LeagueHistory
    fixtures: list[FixtureRow]
    outlook: list[OutlookRow]
    own_outlook: OutlookRow | None
    best_worst: BestWorstRow | None
    next_match: dict[str, Any] | None
    simulation_runs: int
    league_avg_goals: float
    model: dict[str, Any]
    is_top_division: bool = False
    is_bottom_division: bool = False
    caveats: list[str] = field(default_factory=list)


def _history_from_matches(
    matches: list[m.Match],
    rows: list[m.Standing],
    team_ht_id: int,
) -> LeagueHistory:
    """Posición/puntos reales de cada equipo después de cada jornada,
    calculados a partir de los resultados de partidos ya conocidos —
    `leaguefixtures.xml` trae el calendario COMPLETO de la serie, cruces
    entre dos rivales incluidos, así que el resultado de una jornada ya
    jugada se conoce aunque nunca se haya sincronizado una foto de
    `leaguedetails.xml` justo en ese momento. Antes, el historial dependía
    de que el usuario sincronizara exactamente en cada jornada — con un
    solo sync a mitad de temporada, jornadas enteras (p. ej. la 1) se
    quedaban sin fila aunque sus resultados fueran perfectamente
    conocidos. 2026-08-08, pedido explícitamente tras comparar con
    Hattrick Control.

    Una jornada solo cuenta como fila del historial cuando TODOS sus
    partidos están resueltos — un resultado suelto de una jornada en
    curso no es una tabla comparable entre los n equipos."""
    teams = {r.team_ht_id: r.team_name for r in rows}
    n = len(teams)
    if n == 0:
        return LeagueHistory(rounds=[], teams=[])

    by_round: dict[int, list[m.Match]] = {}
    for mt in matches:
        if mt.match_round is None or mt.home_goals < 0 or mt.away_goals < 0:
            continue
        if mt.home_team_ht_id not in teams or mt.away_team_ht_id not in teams:
            continue
        by_round.setdefault(mt.match_round, []).append(mt)

    cum = {tid: {"points": 0, "gf": 0, "ga": 0} for tid in teams}
    real_rounds: list[int] = []
    positions_by_round: dict[int, dict[int, int]] = {}
    points_by_round: dict[int, dict[int, int]] = {}
    for rnd in sorted(by_round):
        round_matches = by_round[rnd]
        for mt in round_matches:
            h, a = mt.home_team_ht_id, mt.away_team_ht_id
            cum[h]["gf"] += mt.home_goals
            cum[h]["ga"] += mt.away_goals
            cum[a]["gf"] += mt.away_goals
            cum[a]["ga"] += mt.home_goals
            if mt.home_goals > mt.away_goals:
                cum[h]["points"] += 3
            elif mt.home_goals < mt.away_goals:
                cum[a]["points"] += 3
            else:
                cum[h]["points"] += 1
                cum[a]["points"] += 1
        if len(round_matches) < n // 2:
            continue  # jornada incompleta: ya sumada a `cum`, pero no es fila comparable
        ranked = sorted(
            teams,
            key=lambda tid: (
                -cum[tid]["points"],
                -(cum[tid]["gf"] - cum[tid]["ga"]),
                -cum[tid]["gf"],
            ),
        )
        positions_by_round[rnd] = {tid: i + 1 for i, tid in enumerate(ranked)}
        points_by_round[rnd] = {tid: cum[tid]["points"] for tid in teams}
        real_rounds.append(rnd)

    # Jornada 0 simbólica: 0 puntos es un HECHO para todos antes de jugar
    # nada, no un dato inventado — se antepone sin necesitar ningún partido
    # jugado. El puesto no tiene un valor real ahí (empate a 0 entre los n
    # equipos, sin desempate posible), así que queda None.
    history_rounds = [0, *real_rounds] if real_rounds else []
    return LeagueHistory(
        rounds=history_rounds,
        teams=[
            TeamHistoryRow(
                ht_team_id=tid,
                name=name,
                is_own_team=tid == team_ht_id,
                positions=[
                    None if rnd == 0 else positions_by_round[rnd].get(tid) for rnd in history_rounds
                ],
                points=[0 if rnd == 0 else points_by_round[rnd].get(tid) for rnd in history_rounds],
            )
            for tid, name in teams.items()
        ],
    )


def _merge_standing_snapshots(
    history: LeagueHistory,
    standing_snapshots: list[m.Standing],
) -> LeagueHistory:
    """Complementa el historial calculado desde partidos con cualquier foto
    real de `leaguedetails.xml` para una jornada que `leaguefixtures.xml`
    todavía no refleja completa — CHPP a veces tarda en actualizar el
    marcador de ese fichero aunque `leaguedetails.xml` ya sepa que la
    jornada terminó (visto en vivo 2026-08-08: jornada 2 con Standing real,
    pero solo 1 de 4 partidos con marcador en Match). Si los partidos YA
    cubren esa jornada completa, esa fuente manda — nunca se pisa."""
    by_round_team: dict[int, dict[int, m.Standing]] = {}
    for s in standing_snapshots:
        if s.played <= 0:
            continue
        by_round_team.setdefault(s.match_round, {})[s.team_ht_id] = s

    real_history_rounds = [r for r in history.rounds if r != 0]
    extra_rounds = sorted(r for r in by_round_team if r not in real_history_rounds)
    if not extra_rounds:
        return history

    real_rounds = sorted({*real_history_rounds, *extra_rounds})
    all_rounds = [0, *real_rounds]
    index_in_history = {rnd: i for i, rnd in enumerate(history.rounds)}

    return LeagueHistory(
        rounds=all_rounds,
        teams=[
            TeamHistoryRow(
                ht_team_id=t.ht_team_id,
                name=t.name,
                is_own_team=t.is_own_team,
                positions=[
                    t.positions[index_in_history[rnd]]
                    if rnd in index_in_history
                    else None
                    if rnd == 0
                    else (
                        snap.position
                        if (snap := by_round_team.get(rnd, {}).get(t.ht_team_id))
                        else None
                    )
                    for rnd in all_rounds
                ],
                points=[
                    t.points[index_in_history[rnd]]
                    if rnd in index_in_history
                    else 0
                    if rnd == 0
                    else (
                        snap.points
                        if (snap := by_round_team.get(rnd, {}).get(t.ht_team_id))
                        else None
                    )
                    for rnd in all_rounds
                ],
            )
            for t in history.teams
        ],
    )


def _standings_from_matches(
    matches: list[m.Match],
    rows: list[m.Standing],
    own_team_ht_id: int,
    side: Literal["home", "away"],
) -> list[StandingRow]:
    """Clasificación Local o Visitante — pedido explícitamente 2026-08-08.
    `leaguedetails.xml` solo da la tabla combinada; esto se calcula desde
    los resultados reales de `leaguefixtures.xml`/`matches.xml` (los mismos
    partidos que ya alimentan `_history_from_matches`), filtrando solo a
    los partidos jugados como local o como visitante según `side`."""
    teams = {r.team_ht_id: r.team_name for r in rows}
    stats = {
        tid: {"played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "points": 0}
        for tid in teams
    }
    for mt in matches:
        if mt.home_goals < 0 or mt.away_goals < 0:
            continue
        if side == "home":
            team_id, gf, ga = mt.home_team_ht_id, mt.home_goals, mt.away_goals
        else:
            team_id, gf, ga = mt.away_team_ht_id, mt.away_goals, mt.home_goals
        if team_id not in stats:
            continue
        s = stats[team_id]
        s["played"] += 1
        s["gf"] += gf
        s["ga"] += ga
        if gf > ga:
            s["won"] += 1
            s["points"] += 3
        elif gf < ga:
            s["lost"] += 1
        else:
            s["drawn"] += 1
            s["points"] += 1

    ordered = sorted(
        teams,
        key=lambda tid: (
            -stats[tid]["points"],
            -(stats[tid]["gf"] - stats[tid]["ga"]),
            -stats[tid]["gf"],
        ),
    )
    return [
        StandingRow(
            position=i + 1,
            ht_team_id=tid,
            name=teams[tid],
            played=stats[tid]["played"],
            won=stats[tid]["won"],
            drawn=stats[tid]["drawn"],
            lost=stats[tid]["lost"],
            goals_for=stats[tid]["gf"],
            goals_against=stats[tid]["ga"],
            goal_difference=stats[tid]["gf"] - stats[tid]["ga"],
            points=stats[tid]["points"],
            is_own_team=tid == own_team_ht_id,
        )
        for i, tid in enumerate(ordered)
    ]


class LeagueQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int, runs: int = 10000) -> LeagueResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        # La clasificación más reciente: la última jornada capturada de la
        # serie a la que pertenece el equipo.
        own = await self._s.scalar(
            select(m.Standing)
            .where(m.Standing.team_ht_id == team.ht_team_id)
            .order_by(m.Standing.captured_at.desc(), m.Standing.match_round.desc())
            .limit(1)
        )
        if own is None:
            return None

        rows = list(
            (
                await self._s.execute(
                    select(m.Standing).where(
                        m.Standing.series_ht_id == own.series_ht_id,
                        m.Standing.season == own.season,
                        m.Standing.match_round == own.match_round,
                    )
                )
            ).scalars()
        )
        if not rows:
            return None

        rows.sort(key=lambda r: (-r.points, -(r.goals_for - r.goals_against), -r.goals_for))
        standings = [
            StandingRow(
                position=i + 1,
                ht_team_id=r.team_ht_id,
                name=r.team_name,
                played=r.played,
                won=r.won,
                drawn=r.draws,
                lost=r.lost,
                goals_for=r.goals_for,
                goals_against=r.goals_against,
                goal_difference=r.goals_for - r.goals_against,
                points=r.points,
                is_own_team=r.team_ht_id == team.ht_team_id,
            )
            for i, r in enumerate(rows)
        ]

        ids = {r.team_ht_id for r in rows}
        # leaguefixtures.xml (HL-090 fix): calendario COMPLETO de la serie,
        # con jornada real — a diferencia de matches.xml (solo el equipo
        # propio), esto incluye los cruces entre dos rivales, sin los que
        # el simulador los daba por congelados. `series_ht_id` es NULL en
        # partidos sincronizados antes de este fix; en ese caso se cae al
        # filtro viejo (solo partidos del equipo propio) hasta el próximo
        # sync.
        matches = list(
            (
                await self._s.execute(
                    select(m.Match)
                    .where(
                        m.Match.match_type == LEAGUE_MATCH_TYPE,
                        m.Match.series_ht_id == own.series_ht_id,
                    )
                    .order_by(m.Match.match_round, m.Match.played_at)
                )
            ).scalars()
        )
        if not matches:
            matches = list(
                (
                    await self._s.execute(
                        select(m.Match)
                        .where(
                            m.Match.match_type == LEAGUE_MATCH_TYPE,
                            m.Match.home_team_ht_id.in_(ids),
                            m.Match.away_team_ht_id.in_(ids),
                        )
                        .order_by(m.Match.played_at)
                    )
                ).scalars()
            )

        # Complemento: fotos reales de leaguedetails.xml para jornadas que
        # leaguefixtures.xml todavía no cubre completas (ver
        # `_merge_standing_snapshots`).
        standing_snapshots = list(
            (
                await self._s.execute(
                    select(m.Standing).where(
                        m.Standing.series_ht_id == own.series_ht_id,
                        m.Standing.season == own.season,
                    )
                )
            ).scalars()
        )
        history = _merge_standing_snapshots(
            _history_from_matches(matches, rows, team.ht_team_id),
            standing_snapshots,
        )
        standings_home = _standings_from_matches(matches, rows, team.ht_team_id, "home")
        standings_away = _standings_from_matches(matches, rows, team.ht_team_id, "away")

        fixtures_out: list[FixtureRow] = []
        pending: list[Fixture] = []
        for i, match in enumerate(matches, start=1):
            rnd = match.match_round if match.match_round is not None else i
            played = match.home_goals >= 0
            fixtures_out.append(
                FixtureRow(
                    date=match.played_at.date().isoformat(),
                    match_round=rnd,
                    home=match.home_team_name,
                    away=match.away_team_name,
                    played=played,
                    score=f"{match.home_goals}-{match.away_goals}" if played else None,
                )
            )
            if not played:
                pending.append(
                    Fixture(
                        home_ht_id=match.home_team_ht_id,
                        away_ht_id=match.away_team_ht_id,
                        match_round=rnd,
                    )
                )

        # Una jornada completa de una liga de n equipos trae n//2 partidos
        # SIMULTÁNEOS, jugados o no — ese total no cambia según avanza la
        # temporada, solo se van marcando como jugados uno a uno. Si alguna
        # jornada trae menos partidos EN TOTAL de los que le tocan, es que
        # CHPP solo entregó el calendario del equipo sincronizado (un
        # partido por jornada, el suyo) y los cruces entre dos rivales
        # nunca llegaron a sincronizarse — a diferencia de contar solo los
        # PENDIENTES, que baja legítimamente según se juegan partidos y no
        # sirve para detectar esto.
        round_totals: dict[int, int] = {}
        for f in fixtures_out:
            round_totals[f.match_round] = round_totals.get(f.match_round, 0) + 1
        schedule_incomplete = len(rows) >= 2 and any(
            c < len(rows) // 2 for c in round_totals.values()
        )

        records = [
            TeamRecord(
                ht_team_id=r.team_ht_id,
                name=r.team_name,
                played=r.played,
                won=r.won,
                drawn=r.draws,
                lost=r.lost,
                goals_for=r.goals_for,
                goals_against=r.goals_against,
                points=r.points,
            )
            for r in rows
        ]
        sim = simulate(
            records,
            pending,
            runs=runs,
            league_level=team.league_level,
            max_level=team.max_level,
        )

        by_id = {o.ht_team_id: o for o in sim.teams}
        outlook = [
            OutlookRow(
                ht_team_id=o.ht_team_id,
                name=o.name,
                is_own_team=o.ht_team_id == team.ht_team_id,
                current_position=o.current_position,
                current_points=o.current_points,
                expected_points=o.expected_points,
                expected_position=o.expected_position,
                most_likely_position=o.most_likely_position,
                title_probability=o.title_probability,
                promotion_probability=o.promotion_probability,
                second_to_fourth_probability=o.second_to_fourth_probability,
                relegation_playoff_probability=o.relegation_playoff_probability,
                relegation_probability=o.relegation_probability,
                attack_strength=o.attack_strength,
                defence_strength=o.defence_strength,
                position_distribution=o.position_distribution,
            )
            for o in sim.teams
        ]

        bw = best_worst_case(records, pending, target_team_id=team.ht_team_id, runs=runs)
        best_worst = (
            BestWorstRow(
                ht_team_id=bw.ht_team_id,
                name=bw.name,
                remaining_matches=bw.remaining_matches,
                current_points=bw.current_points,
                current_position=bw.current_position,
                best_case_position_distribution=bw.best_case_position_distribution,
                best_case_expected_points=bw.best_case_expected_points,
                worst_case_position_distribution=bw.worst_case_position_distribution,
                worst_case_expected_points=bw.worst_case_expected_points,
            )
            if bw is not None
            else None
        )

        # Pronóstico del próximo partido propio
        next_match = None
        upcoming = next(
            (f for f in pending if team.ht_team_id in (f.home_ht_id, f.away_ht_id)), None
        )
        if upcoming is not None:
            home_rec = next(r for r in records if r.ht_team_id == upcoming.home_ht_id)
            away_rec = next(r for r in records if r.ht_team_id == upcoming.away_ht_id)
            fc = forecast_match(home_rec, away_rec, records, match_round=upcoming.match_round)
            next_match = {
                "home": fc.home,
                "away": fc.away,
                "round": fc.match_round,
                "homeWin": fc.home_win,
                "draw": fc.draw,
                "awayWin": fc.away_win,
                "expectedHomeGoals": fc.expected_home_goals,
                "expectedAwayGoals": fc.expected_away_goals,
                "mostLikelyScore": fc.most_likely_score,
                "verdict": fc.verdict,
                "isHome": upcoming.home_ht_id == team.ht_team_id,
            }

        caveats = list(sim.caveats)
        if schedule_incomplete:
            caveats.append(
                "El calendario sincronizado sólo trae los partidos DE TU EQUIPO, "
                "Hattrick solo entrega el calendario completo del equipo que pides, "
                "así que los partidos entre dos rivales (ninguno el tuyo) no están "
                "sincronizados. Esos equipos quedan con sus puntos y diferencia de "
                "gol congelados salvo cuando juegan contra ti, así que su rango de "
                "puestos posibles está subestimado en esta simulación."
            )

        return LeagueResponse(
            team_name=team.name,
            series_name=team.series_name,
            season=own.season,
            rounds_played=sim.rounds_played,
            rounds_remaining=sim.rounds_remaining,
            standings=standings,
            standings_home=standings_home,
            standings_away=standings_away,
            history=history,
            fixtures=fixtures_out,
            outlook=outlook,
            own_outlook=(
                next((o for o in outlook if o.is_own_team), None)
                if team.ht_team_id in by_id
                else None
            ),
            best_worst=best_worst,
            next_match=next_match,
            simulation_runs=sim.runs,
            league_avg_goals=sim.league_avg_goals,
            model=model_info(),
            is_top_division=sim.is_top_division,
            is_bottom_division=sim.is_bottom_division,
            caveats=caveats,
        )
