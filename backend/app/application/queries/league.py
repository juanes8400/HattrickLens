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
from typing import Any

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
                position=i + 1, ht_team_id=r.team_ht_id, name=r.team_name,
                played=r.played, won=r.won, drawn=r.draws, lost=r.lost,
                goals_for=r.goals_for, goals_against=r.goals_against,
                goal_difference=r.goals_for - r.goals_against, points=r.points,
                is_own_team=r.team_ht_id == team.ht_team_id,
            )
            for i, r in enumerate(rows)
        ]

        # Historial de posición/puntos por jornada: cada sync guarda una foto
        # de TODA la serie (Standing, no solo el equipo propio), así que con
        # varios syncs a lo largo de la temporada hay una serie temporal real
        # — no una jornada, la secuencia completa. None donde falta una
        # jornada sincronizada, nunca un valor inventado.
        history_snapshots = list(
            (
                await self._s.execute(
                    select(m.Standing)
                    .where(
                        m.Standing.series_ht_id == own.series_ht_id,
                        m.Standing.season == own.season,
                        # La foto de antes de jugar nada (todos 0 partidos,
                        # posición sin sentido — CHPP la reparte arbitraria
                        # entre empatados a 0) no es una jornada real.
                        m.Standing.played > 0,
                    )
                    .order_by(m.Standing.match_round)
                )
            ).scalars()
        )
        real_rounds = sorted({s.match_round for s in history_snapshots})
        # Jornada 0 simbólica: 0 puntos es un HECHO para todos antes de jugar
        # nada, no un dato inventado — se puede anteponer sin sincronizar
        # nada. El puesto en cambio no tiene un valor real ahí (empate a 0
        # entre los n equipos, sin desempate posible), así que queda None:
        # la línea de puntos arranca visiblemente en (0, 0), la de puesto
        # simplemente no dibuja nada en esa jornada.
        history_rounds = [0, *real_rounds] if real_rounds else []
        by_team_round: dict[int, dict[int, m.Standing]] = {}
        for s in history_snapshots:
            by_team_round.setdefault(s.team_ht_id, {})[s.match_round] = s
        history = LeagueHistory(
            rounds=history_rounds,
            teams=[
                TeamHistoryRow(
                    ht_team_id=r.team_ht_id, name=r.team_name,
                    is_own_team=r.team_ht_id == team.ht_team_id,
                    positions=[
                        None if rnd == 0 else (
                            snap.position
                            if (snap := by_team_round.get(r.team_ht_id, {}).get(rnd))
                            else None
                        )
                        for rnd in history_rounds
                    ],
                    points=[
                        0 if rnd == 0 else (
                            snap.points
                            if (snap := by_team_round.get(r.team_ht_id, {}).get(rnd))
                            else None
                        )
                        for rnd in history_rounds
                    ],
                )
                for r in rows
            ],
        )

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
                ht_team_id=r.team_ht_id, name=r.team_name, played=r.played,
                won=r.won, drawn=r.draws, lost=r.lost, goals_for=r.goals_for,
                goals_against=r.goals_against, points=r.points,
            )
            for r in rows
        ]
        sim = simulate(
            records, pending, runs=runs,
            league_level=team.league_level, max_level=team.max_level,
        )

        by_id = {o.ht_team_id: o for o in sim.teams}
        outlook = [
            OutlookRow(
                ht_team_id=o.ht_team_id, name=o.name,
                is_own_team=o.ht_team_id == team.ht_team_id,
                current_position=o.current_position, current_points=o.current_points,
                expected_points=o.expected_points, expected_position=o.expected_position,
                most_likely_position=o.most_likely_position,
                title_probability=o.title_probability,
                promotion_probability=o.promotion_probability,
                second_to_fourth_probability=o.second_to_fourth_probability,
                relegation_playoff_probability=o.relegation_playoff_probability,
                relegation_probability=o.relegation_probability,
                attack_strength=o.attack_strength, defence_strength=o.defence_strength,
                position_distribution=o.position_distribution,
            )
            for o in sim.teams
        ]

        bw = best_worst_case(records, pending, target_team_id=team.ht_team_id, runs=runs)
        best_worst = (
            BestWorstRow(
                ht_team_id=bw.ht_team_id, name=bw.name,
                remaining_matches=bw.remaining_matches,
                current_points=bw.current_points, current_position=bw.current_position,
                best_case_position_distribution=bw.best_case_position_distribution,
                best_case_expected_points=bw.best_case_expected_points,
                worst_case_position_distribution=bw.worst_case_position_distribution,
                worst_case_expected_points=bw.worst_case_expected_points,
            )
            if bw is not None else None
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
                "home": fc.home, "away": fc.away, "round": fc.match_round,
                "homeWin": fc.home_win, "draw": fc.draw, "awayWin": fc.away_win,
                "expectedHomeGoals": fc.expected_home_goals,
                "expectedAwayGoals": fc.expected_away_goals,
                "mostLikelyScore": fc.most_likely_score,
                "verdict": fc.verdict,
                "isHome": upcoming.home_ht_id == team.ht_team_id,
            }

        caveats = list(sim.caveats)
        if schedule_incomplete:
            caveats.append(
                "El calendario sincronizado sólo trae los partidos DE TU EQUIPO — "
                "CHPP solo entrega el calendario completo del equipo que pides, "
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
            history=history,
            fixtures=fixtures_out,
            outlook=outlook,
            own_outlook=(
                next((o for o in outlook if o.is_own_team), None)
                if team.ht_team_id in by_id else None
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
