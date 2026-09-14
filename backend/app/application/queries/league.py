"""LeagueQueryService, HL-080, HL-083, HL-090, HL-091, HL-094.

Clasificación, calendario y la simulación de temporada que los convierte en
probabilidades.

Una nota sobre las reglas de CHPP que da forma a este módulo: está permitido
mostrar los datos actuales de otros equipos, pero no llevar un histórico de la
evolución de sus jugadores. Por eso aquí se trabaja con **resultados y
clasificación**, que son públicos y colectivos, y nunca con la ficha
individual de los jugadores rivales.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.prediccion_liga import reparto_de_tacticas
from app.domain.engines.prediccion import (  # type: ignore[attr-defined]
    PitchZoneMethod,
    factor_de_tactica,
    goles_esperados,
    marcador_mas_probable,
    probabilidades_de_partido,
    probabilidades_del_motor,
    resumen_de_lecturas,
)
from app.domain.engines.season_simulator import (
    Fixture,
    MatchForecast,
    TeamRecord,
    best_worst_case,
    forecast_match,
    model_info,
    simulate,
)
from app.domain.value_objects.ht_constants import tactic_type_name
from app.infrastructure.db import models as m

if TYPE_CHECKING:
    from app.application.queries.alineacion_enviada import AlineacionEnviada

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
    # Alineados con LeagueHistory.rounds, None donde esa jornada no se ha
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
class CambioDeJornada:
    """Cuánto movió la última jornada jugada.

    Existe porque un porcentaje suelto no dice si vas mejor o peor: «57 % de
    ser campeón» se lee muy distinto viniendo de 60 % que viniendo de 47 %.
    La pantalla ya enseñaba la foto de hoy; esto es la diferencia con la de
    antes de jugarse la jornada.

    Se calcula volviendo a simular con la clasificación y el calendario tal
    como estaban entonces, no guardando la simulación anterior: así el número
    no depende de que el usuario abriera la pantalla la semana pasada.
    """

    match_round: int
    #: Puntos PORCENTUALES de diferencia por puesto, del equipo propio.
    #:
    #: NO se publica «el puesto más probable del peor caso» aunque sería una
    #: frase bonita: con 4º al 49,1 % y 5º al 48,9 %, cuál gana depende de la
    #: tirada de Monte Carlo y cambia entre dos cargas de la misma pantalla.
    #: Lo que sí aguanta es cuánto se movió cada puesto, que es esto.
    position_delta: dict[int, float]
    best_case_delta: dict[int, float]
    worst_case_delta: dict[int, float]
    own_title_before: float
    own_title_after: float
    #: Quién ganó más con la jornada. Puede ser el propio equipo.
    biggest_gainer: str | None
    biggest_gainer_before: float
    biggest_gainer_after: float


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
    # Clasificación Local/Visitante, pedido explícitamente 2026-08-08,
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
    #: Nada la primera jornada, cuando no hay con qué comparar.
    change: CambioDeJornada | None
    is_top_division: bool = False
    is_bottom_division: bool = False
    caveats: list[str] = field(default_factory=list)
    #: Con qué resumen se calcularon las predicciones de esta respuesta. Viaja
    #: de vuelta para que la pantalla pinte marcado el que de verdad se usó y
    #: no el que ella cree haber pedido: si un día el servidor rechaza uno,
    #: quien mira no se queda con un selector que miente.
    pitch_zone_method: str = PitchZoneMethod.AVERAGE


def _clasificacion_hasta(
    matches: list[m.Match], corte: int
) -> tuple[list[TeamRecord], list[Fixture]]:
    """La clasificación y lo que quedaba por jugar tras esa jornada.

    Se reconstruye desde los resultados y no desde las fotos guardadas de la
    clasificación, porque las fotos dependen de cuándo sincronizó el usuario y
    los resultados no.
    """
    nombres: dict[int, str] = {}
    for mt in matches:
        nombres.setdefault(mt.home_team_ht_id, mt.home_team_name)
        nombres.setdefault(mt.away_team_ht_id, mt.away_team_name)

    acumulado: dict[int, dict[str, int]] = {
        t: {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "pts": 0} for t in nombres
    }
    pendientes: list[Fixture] = []
    for mt in matches:
        rnd = mt.match_round or 0
        jugado = mt.home_goals >= 0 and rnd <= corte
        if not jugado:
            pendientes.append(Fixture(mt.home_team_ht_id, mt.away_team_ht_id, rnd))
            continue
        for yo, mios, suyos in (
            (mt.home_team_ht_id, mt.home_goals, mt.away_goals),
            (mt.away_team_ht_id, mt.away_goals, mt.home_goals),
        ):
            a = acumulado[yo]
            a["pj"] += 1
            a["gf"] += mios
            a["gc"] += suyos
            if mios > suyos:
                a["g"] += 1
                a["pts"] += 3
            elif mios == suyos:
                a["e"] += 1
                a["pts"] += 1
            else:
                a["p"] += 1
    registros = [
        TeamRecord(t, nombres[t], v["pj"], v["g"], v["e"], v["p"], v["gf"], v["gc"], v["pts"])
        for t, v in acumulado.items()
    ]
    return registros, pendientes


def _history_from_matches(
    matches: list[m.Match],
    rows: list[m.Standing],
    team_ht_id: int,
) -> LeagueHistory:
    """Posición/puntos reales de cada equipo después de cada jornada,
    calculados a partir de los resultados de partidos ya conocidos
    `leaguefixtures.xml` trae el calendario COMPLETO de la serie, cruces
    entre dos rivales incluidos, así que el resultado de una jornada ya
    jugada se conoce aunque nunca se haya sincronizado una foto de
    `leaguedetails.xml` justo en ese momento. Antes, el historial dependía
    de que el usuario sincronizara exactamente en cada jornada, con un
    solo sync a mitad de temporada, jornadas enteras (p. ej. la 1) se
    quedaban sin fila aunque sus resultados fueran perfectamente
    conocidos. 2026-08-08, pedido explícitamente tras comparar con
    Hattrick Control.

    Una jornada solo cuenta como fila del historial cuando TODOS sus
    partidos están resueltos, un resultado suelto de una jornada en
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
    # nada, no un dato inventado, se antepone sin necesitar ningún partido
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
    todavía no refleja completa, CHPP a veces tarda en actualizar el
    marcador de ese fichero aunque `leaguedetails.xml` ya sepa que la
    jornada terminó (visto en vivo 2026-08-08: jornada 2 con Standing real,
    pero solo 1 de 4 partidos con marcador en Match). Si los partidos YA
    cubren esa jornada completa, esa fuente manda, nunca se pisa."""
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
    """Clasificación Local o Visitante, pedido explícitamente 2026-08-08.
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


# ── El próximo partido del Resumen ──────────────────────────────────────────
#
# 2026-09-12, pedido del usuario: «la última alineación para el rival, y la
# enviada (o si no, la última) para nosotros», y que la pantalla deje claro
# cuál se toma y por qué. Es el único sitio de Liga que pronostica UN partido,
# y un partido se juega con un once, no con el promedio de cinco.

#: Tu lado, con las órdenes que ya mandaste para ese partido.
FUENTE_ENVIADA = "submitted"
#: El último partido de liga del equipo, tal cual.
FUENTE_ULTIMO = "last"


def _partido_nombrado(partido: m.Match | None) -> dict[str, Any] | None:
    """Lo justo para escribir «Deportivo Uno 1 - 2 Pulgas Arrechas»."""
    if partido is None:
        return None
    return {
        "round": partido.match_round,
        "home": partido.home_team_name,
        "away": partido.away_team_name,
        "homeGoals": partido.home_goals,
        "awayGoals": partido.away_goals,
    }


def _su_ultimo_partido(
    lecturas: list[dict[str, float]], por_id: dict[int, m.Match], en_casa: bool
) -> tuple[dict[str, float], int, m.Match | None] | None:
    """Los nueve ratings del último partido de un equipo, su táctica y cuál fue.

    LA TÁCTICA VA CON LA ALINEACIÓN, no con la costumbre. Los factores por
    táctica se ajustaron con los ratings de un partido y la táctica con la que
    se jugó ESE partido: si los ratings son los de un partido concreto, la
    táctica que les corresponde es la suya, no un reparto de la temporada.
    """
    # Con la sede del partido que viene: el último pudo ser fuera y el
    # próximo en casa. Ver `corregir_sede`.
    resumen = resumen_de_lecturas(lecturas, PitchZoneMethod.LAST, en_casa=en_casa)
    if resumen is None:
        return None
    ultima = lecturas[-1]
    cual = ultima.get("ht_match_id")
    partido = por_id.get(int(cual)) if cual is not None else None
    return resumen, int(ultima.get("tactic_type") or 0), partido


def _proximo_con_alineaciones(
    upcoming: Fixture,
    propio: int,
    lecturas: dict[int, list[dict[str, float]]],
    enviada: "AlineacionEnviada | None",
    partido: m.Match | None,
    por_id: dict[int, m.Match],
    nombre_local: str,
    nombre_visitante: str,
) -> dict[str, Any] | None:
    """Los números del próximo partido y de dónde sale cada lado, o nada.

    `None` si a alguno de los dos le falta un partido con ratings: entonces la
    pantalla se queda con la Poisson de la temporada, y lo dice.

    UNAS ÓRDENES SÓLO VALEN PARA SU PARTIDO. `enviada` trae su `ht_match_id`
    y se compara con el del próximo cruce: si el endpoint hubiera encontrado
    otro --un calendario a medio sincronizar--, se ignora y tu lado cae a tu
    último partido, en vez de pronosticar este con las órdenes de aquel.
    """
    rival = upcoming.away_ht_id if upcoming.home_ht_id == propio else upcoming.home_ht_id
    propio_en_casa = upcoming.home_ht_id == propio
    mio = _su_ultimo_partido(lecturas.get(propio, []), por_id, propio_en_casa)
    suyo = _su_ultimo_partido(lecturas.get(rival, []), por_id, not propio_en_casa)
    if mio is None or suyo is None:
        return None
    ratings_mios, tactica_mia, ultimo_mio = mio
    ratings_suyos, tactica_suya, ultimo_suyo = suyo

    fuente_mia = FUENTE_ULTIMO
    if enviada is not None and partido is not None and enviada.ht_match_id == partido.ht_match_id:
        # Los siete sectores que Hattrick prevé sustituyen a los de tu último
        # partido. Las dos indirectas a balón parado no las prevé: se quedan
        # con las de tu último partido, que es la misma regla --«si no, la
        # última»-- aplicada a lo que falta.
        ratings_mios = {**ratings_mios, **{k: float(v) for k, v in enviada.ratings.items()}}
        if enviada.tactica is not None:
            tactica_mia = enviada.tactica
        fuente_mia = FUENTE_ENVIADA

    # Desde el LOCAL, igual que `probabilidades_de_partido`: la terna, los
    # goles y el marcador salen orientados como los pinta la pantalla.
    en_casa = upcoming.home_ht_id == propio
    local, visita = (ratings_mios, ratings_suyos) if en_casa else (ratings_suyos, ratings_mios)
    f_mio, f_suyo = factor_de_tactica(exacta=tactica_mia), factor_de_tactica(exacta=tactica_suya)
    f_local, f_visita = (f_mio, f_suyo) if en_casa else (f_suyo, f_mio)

    terna = probabilidades_del_motor(local, visita, f_local, f_visita)
    goles_local = goles_esperados(local, visita, f_local)
    goles_visita = goles_esperados(visita, local, f_visita)
    marcador = marcador_mas_probable(local, visita, f_local, f_visita)

    # EL VEREDICTO SALE DE ESTA MISMA TERNA. Salía de la Poisson de la
    # temporada mientras la barra pintaba el modelo de zonas, y así la
    # pantalla llegó a decir «favorito Pulgas Arrechas» encima de un empate
    # del 47 %.
    veredicto = MatchForecast(
        home=nombre_local,
        away=nombre_visitante,
        match_round=upcoming.match_round,
        home_win=terna.victoria,
        draw=terna.empate,
        away_win=terna.derrota,
        expected_home_goals=goles_local,
        expected_away_goals=goles_visita,
        most_likely_score=f"{marcador[0]}-{marcador[1]}",
    ).verdict

    return {
        "homeWin": round(terna.victoria, 4),
        "draw": round(terna.empate, 4),
        "awayWin": round(terna.derrota, 4),
        "expectedHomeGoals": round(goles_local, 2),
        "expectedAwayGoals": round(goles_visita, 2),
        "mostLikelyScore": f"{marcador[0]}-{marcador[1]}",
        "verdict": veredicto,
        "sources": {
            "own": {
                "kind": fuente_mia,
                "match": _partido_nombrado(ultimo_mio) if fuente_mia == FUENTE_ULTIMO else None,
                "setPiecesFrom": (
                    _partido_nombrado(ultimo_mio) if fuente_mia == FUENTE_ENVIADA else None
                ),
                "tactic": tactic_type_name(tactica_mia),
            },
            "rival": {
                "kind": FUENTE_ULTIMO,
                "match": _partido_nombrado(ultimo_suyo),
                "tactic": tactic_type_name(tactica_suya),
            },
        },
    }


class LeagueQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        team_id: int,
        runs: int = 10_000,
        lecturas: dict[int, list[dict[str, float]]] | None = None,
        metodo: str = PitchZoneMethod.AVERAGE,
        enviada: "AlineacionEnviada | None" = None,
    ) -> LeagueResponse | None:
        """`lecturas` son los ratings por zona de cada equipo de la serie.

        Las trae el endpoint, que es quien tiene el cliente de Hattrick. Sin
        ellas la pantalla sigue funcionando exactamente como antes, sólo con
        la Poisson: es lo que pasa la primera vez que alguien abre Liga sin
        haber sincronizado nunca, y no es motivo para no enseñar nada.

        `metodo` es CÓMO se resumen esas lecturas en la Proyección, y es UNO
        para los ocho equipos (2026-09-09, pedido del usuario): lo comen los
        puntos esperados con su distribución de puestos, los límites, y la
        misma cuenta rehecha «como estaba hace una jornada».

        EL PRÓXIMO PARTIDO DEL RESUMEN NO LO SIGUE (2026-09-12, pedido del
        usuario). Ahí se pronostica UN partido, así que cada lado va con una
        alineación concreta: la tuya enviada si ya mandaste órdenes --`enviada`,
        que la trae el endpoint porque es quien habla con Hattrick-- y si no la
        de tu último partido; la del rival, siempre la de su último partido,
        porque sus órdenes son privadas hasta que se juega. Como resumen de
        ocho equipos la enviada sigue sin existir: de siete no se ven las
        órdenes.
        """
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
        # con jornada real, a diferencia de matches.xml (solo el equipo
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

        # UN EQUIPO REEMPLAZADO A MITAD DE TEMPORADA (etbenianos1 → Kivaré,
        # visto en vivo). Hattrick le da otro id al nuevo, y lo guardado queda
        # partido en dos: las jornadas 1-7 --partidos y fotos-- con el viejo, y
        # desde la 8 el nuevo. La clasificación de hoy sólo conoce al nuevo, así
        # que todo lo del viejo no casaba con nadie:
        #   · 2026-09-13, la proyección dejaba al nuevo sin sus partidos
        #     pendientes;
        #   · 2026-09-14, el Historial de la serie se volvió loco: las jornadas
        #     1-7 salían incompletas y la 8 sin los puntos ganados al viejo
        #     (Pulgas con 19 en vez de 22, LosNeithas BAJANDO de 17 a 16).
        # Se traduce el viejo al nuevo en todo lo leído. El nuevo es el único
        # equipo de hoy que nunca coincidió con el viejo: ni en una misma foto
        # ni jugando contra él. Si no hay exactamente uno así, no se adivina.
        vistos = (
            {mt.home_team_ht_id for mt in matches}
            | {mt.away_team_ht_id for mt in matches}
            | {s.team_ht_id for s in standing_snapshots}
        )
        viejos = vistos - ids
        if len(viejos) == 1:
            viejo = next(iter(viejos))
            fotos_por_ronda: dict[int, set[int]] = {}
            for s in standing_snapshots:
                fotos_por_ronda.setdefault(s.match_round, set()).add(s.team_ht_id)
            junto_al_viejo = {
                t for equipos in fotos_por_ronda.values() if viejo in equipos for t in equipos
            } | {
                t
                for mt in matches
                if viejo in (mt.home_team_ht_id, mt.away_team_ht_id)
                for t in (mt.home_team_ht_id, mt.away_team_ht_id)
            }
            candidatos = ids - junto_al_viejo
            if len(candidatos) == 1:
                nuevo = next(iter(candidatos))
                nombre_nuevo = next(r.team_name for r in rows if r.team_ht_id == nuevo)
                # Fuera de la sesión antes de tocarlos: esto es para leer,
                # nunca para guardar.
                for mt in matches:
                    if viejo in (mt.home_team_ht_id, mt.away_team_ht_id):
                        self._s.expunge(mt)
                        if mt.home_team_ht_id == viejo:
                            mt.home_team_ht_id, mt.home_team_name = nuevo, nombre_nuevo
                        if mt.away_team_ht_id == viejo:
                            mt.away_team_ht_id, mt.away_team_name = nuevo, nombre_nuevo
                for s in standing_snapshots:
                    if s.team_ht_id == viejo:
                        self._s.expunge(s)
                        s.team_ht_id, s.team_name = nuevo, nombre_nuevo
        history = _merge_standing_snapshots(
            _history_from_matches(matches, rows, team.ht_team_id),
            standing_snapshots,
        )
        standings_home = _standings_from_matches(matches, rows, team.ht_team_id, "home")
        standings_away = _standings_from_matches(matches, rows, team.ht_team_id, "away")

        fixtures_out: list[FixtureRow] = []
        pending: list[Fixture] = []
        # El partido de cada cruce pendiente: el próximo del Resumen tiene
        # que saber su `ht_match_id` para aceptar sólo SUS órdenes.
        pendiente_de: dict[tuple[int, int, int], m.Match] = {}
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
                pendiente_de.setdefault((match.home_team_ht_id, match.away_team_ht_id, rnd), match)

        # Una jornada completa de una liga de n equipos trae n//2 partidos
        # SIMULTÁNEOS, jugados o no, ese total no cambia según avanza la
        # temporada, solo se van marcando como jugados uno a uno. Si alguna
        # jornada trae menos partidos EN TOTAL de los que le tocan, es que
        # CHPP solo entregó el calendario del equipo sincronizado (un
        # partido por jornada, el suyo) y los cruces entre dos rivales
        # nunca llegaron a sincronizarse, a diferencia de contar solo los
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
        # 2026-09-13, bug en vivo: la jornada 8 ya tenía sus cuatro resultados
        # pero la última foto de la clasificación seguía en la 7. La pantalla
        # decía «7 jugadas» y, peor, la simulación sumaba los puntos de la foto
        # vieja mientras daba la jornada 8 por jugada: esos puntos se perdían.
        # Si los resultados van por delante de la foto y el calendario está
        # completo, la tabla se reconstruye desde ellos.
        con_resultado = [mt.match_round or 0 for mt in matches if mt.home_goals >= 0]
        ultima_con_resultado = max(con_resultado, default=0)
        if ultima_con_resultado > max((r.played for r in rows), default=0) and (
            not schedule_incomplete
        ):
            reconstruida, _ = _clasificacion_hasta(matches, ultima_con_resultado)
            if {r.ht_team_id for r in reconstruida} == ids:
                # El nombre, el de la foto: el de un partido viejo puede ser
                # uno que el equipo ya cambió.
                nombre_actual = {r.team_ht_id: r.team_name for r in rows}
                records = [
                    dataclasses.replace(r, name=nombre_actual.get(r.ht_team_id, r.name))
                    for r in reconstruida
                ]
                ordenada = sorted(
                    records,
                    key=lambda r: (-r.points, -(r.goals_for - r.goals_against), -r.goals_for),
                )
                standings = [
                    StandingRow(
                        position=i + 1,
                        ht_team_id=r.ht_team_id,
                        name=r.name,
                        played=r.played,
                        won=r.won,
                        drawn=r.drawn,
                        lost=r.lost,
                        goals_for=r.goals_for,
                        goals_against=r.goals_against,
                        goal_difference=r.goals_for - r.goals_against,
                        points=r.points,
                        is_own_team=r.ht_team_id == team.ht_team_id,
                    )
                    for i, r in enumerate(ordenada)
                ]
        # ── El modelo de zonas, si hay ratings con los que alimentarlo ────
        #
        # La terna de cada partido se calcula UNA vez y de ella salen las dos
        # cosas que enseña la pantalla: los puntos esperados y la distribución
        # de puestos. Calcularlas por separado sería dejar que discrepen.
        zonas: dict[tuple[int, int], tuple[float, float, float]] = {}
        # LA TÁCTICA DE CADA EQUIPO, ponderada. Aquí no se sabe qué va a
        # jugar nadie --son partidos futuros de ocho equipos-- así que se usa
        # el reparto de lo que cada uno viene jugando y se promedian los
        # factores. Ver `factor_de_tactica`.
        factores = {
            equipo: factor_de_tactica(reparto_de_tacticas(lect))
            for equipo, lect in (lecturas or {}).items()
        }

        if lecturas:
            por_equipo = {r.ht_team_id: r for r in records}
            for cruce in pending:
                if cruce.home_ht_id not in por_equipo or cruce.away_ht_id not in por_equipo:
                    continue
                local, visita = lecturas.get(cruce.home_ht_id), lecturas.get(cruce.away_ht_id)
                if not local or not visita:
                    continue
                terna = probabilidades_de_partido(
                    local,
                    visita,
                    metodo=metodo,
                    factor_local=factores.get(cruce.home_ht_id, 1.0),
                    factor_visitante=factores.get(cruce.away_ht_id, 1.0),
                )
                if terna is None:
                    continue
                zonas[(cruce.home_ht_id, cruce.away_ht_id)] = (
                    terna.victoria,
                    terna.empate,
                    terna.derrota,
                )

        sim = simulate(
            records,
            pending,
            runs=runs,
            league_level=team.league_level,
            max_level=team.max_level,
            probabilidades=zonas or None,
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

        # Con las MISMAS ternas que la simulación de arriba: los dos paneles
        # de Proyección están uno encima del otro y hablan del mismo resto de
        # liga, así que no pueden usar dos motores distintos para él.
        bw = best_worst_case(
            records,
            pending,
            target_team_id=team.ht_team_id,
            runs=runs,
            probabilidades=zonas or None,
        )
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

        # ── Cuánto movió la última jornada ───────────────────────────────
        #
        # Se vuelve a simular con el estado ANTERIOR y se restan las dos
        # distribuciones. Cuesta una segunda tanda de Monte Carlo, que a estos
        # tamaños es décimas de segundo, y a cambio el número no depende de
        # que el usuario abriera la pantalla la semana pasada.
        cambio: CambioDeJornada | None = None
        jugadas = [mt.match_round or 0 for mt in matches if mt.home_goals >= 0]
        ultima = max(jugadas) if jugadas else 0
        if ultima >= 2 and team.ht_team_id in {r.ht_team_id for r in records}:
            antes_reg, antes_pen = _clasificacion_hasta(matches, ultima - 1)
            zonas_antes = dict(zonas)
            for pendiente in antes_pen:
                clave = (pendiente.home_ht_id, pendiente.away_ht_id)
                if clave in zonas_antes or not lecturas:
                    continue
                local = lecturas.get(pendiente.home_ht_id)
                visita = lecturas.get(pendiente.away_ht_id)
                if not local or not visita:
                    continue
                terna = probabilidades_de_partido(
                    local,
                    visita,
                    metodo=metodo,
                    factor_local=factores.get(pendiente.home_ht_id, 1.0),
                    factor_visitante=factores.get(pendiente.away_ht_id, 1.0),
                )
                if terna is not None:
                    zonas_antes[clave] = (
                        terna.victoria,
                        terna.empate,
                        terna.derrota,
                    )
            sim_antes = simulate(
                antes_reg,
                antes_pen,
                runs=runs,
                league_level=team.league_level,
                max_level=team.max_level,
                probabilidades=zonas_antes or None,
            )
            bw_antes = best_worst_case(
                antes_reg,
                antes_pen,
                target_team_id=team.ht_team_id,
                runs=runs,
                probabilidades=zonas_antes or None,
            )
            yo_antes = next(o for o in sim_antes.teams if o.ht_team_id == team.ht_team_id)
            yo_ahora = next(o for o in sim.teams if o.ht_team_id == team.ht_team_id)
            # A quién le vino mejor la jornada. Puede ser uno mismo.
            por_id_antes = {o.ht_team_id: o for o in sim_antes.teams}

            def mejora(o: Any) -> float:
                previo = por_id_antes.get(o.ht_team_id)
                base = previo.title_probability if previo is not None else o.title_probability
                return float(o.title_probability - base)

            ganador = max(sim.teams, key=mejora)

            def resta(a: dict[Any, float], b: dict[Any, float]) -> dict[Any, float]:
                return {k: round((a.get(k, 0.0) - b.get(k, 0.0)) * 100, 2) for k in set(a) | set(b)}

            mejor_ahora = bw.best_case_position_distribution if bw else {}
            peor_ahora = bw.worst_case_position_distribution if bw else {}
            mejor_antes = bw_antes.best_case_position_distribution if bw_antes else {}
            peor_antes = bw_antes.worst_case_position_distribution if bw_antes else {}
            cambio = CambioDeJornada(
                match_round=ultima,
                position_delta=resta(
                    yo_ahora.position_distribution, yo_antes.position_distribution
                ),
                best_case_delta=resta(mejor_ahora, mejor_antes),
                worst_case_delta=resta(peor_ahora, peor_antes),
                own_title_before=round(yo_antes.title_probability, 4),
                own_title_after=round(yo_ahora.title_probability, 4),
                biggest_gainer=ganador.name,
                biggest_gainer_before=round(
                    por_id_antes.get(ganador.ht_team_id, ganador).title_probability, 4
                ),
                biggest_gainer_after=round(ganador.title_probability, 4),
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
                # Sin ratings no hay alineación que nombrar: sale de los
                # goles de la temporada y la pantalla lo dice.
                "sources": None,
            }
            # UNA ALINEACIÓN CONCRETA POR LADO (2026-09-12, pedido del usuario).
            # La Poisson de arriba sólo mira goles agregados de la temporada y
            # queda de respaldo para cuando falten ratings. Con ellos cada lado
            # va con un partido concreto, y NO con el resumen del selector de
            # Proyección: ver `_proximo_con_alineaciones`.
            proximo = _proximo_con_alineaciones(
                upcoming,
                team.ht_team_id,
                lecturas or {},
                enviada,
                pendiente_de.get((upcoming.home_ht_id, upcoming.away_ht_id, upcoming.match_round)),
                {mt.ht_match_id: mt for mt in matches},
                fc.home,
                fc.away,
            )
            if proximo is not None:
                next_match |= proximo

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
            change=cambio,
            is_top_division=sim.is_top_division,
            is_bottom_division=sim.is_bottom_division,
            caveats=caveats,
            pitch_zone_method=metodo,
        )
