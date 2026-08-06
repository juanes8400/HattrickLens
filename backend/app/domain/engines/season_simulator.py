"""Season Simulator — HL-090, HL-091, HL-092, HL-094.

Responde la única pregunta que un manager se hace cada semana: ¿en qué puesto
voy a acabar? Y la responde con una distribución, no con un número, porque una
liga de dieciséis jornadas es demasiado corta para que el mejor equipo gane
siempre.

EL MODELO
---------
Cada equipo tiene una fuerza de ataque y una de defensa. Los goles de un
partido se sacan de dos Poisson independientes:

    λ_local    = media_liga × ataque_local    × defensa_visitante × ventaja_local
    λ_visitante = media_liga × ataque_visitante × defensa_local

Se simulan las jornadas que faltan miles de veces, se ordena la tabla con los
criterios de Hattrick y se cuenta en qué posición acaba cada equipo.

POR QUÉ HAY ENCOGIMIENTO BAYESIANO
----------------------------------
Con cuatro o cinco jornadas jugadas, un equipo que ha marcado 12 goles parece
tres veces mejor que uno que ha marcado 4. Casi siempre es ruido. Sin corregir
eso, el simulador produce probabilidades ridículamente confiadas en septiembre
y ridículamente equivocadas en diciembre.

La corrección es encoger cada fuerza hacia la media de la liga con un peso que
depende de los partidos jugados:

    fuerza = (goles_observados + k × media_liga) / (partidos + k)

Con `k = 5`, un equipo con 2 jornadas pesa 2/7 de su propia evidencia y 5/7 de
la media; con 14 jornadas pesa 14/19. El modelo empieza siendo humilde y se va
volviendo específico según llegan los datos, que es exactamente lo que debe
hacer.

LO QUE NO MODELA
----------------
Lesiones, cambios de plantilla, tácticas y el partido concreto. Es un modelo de
forma agregada: sirve para «¿tengo opciones de ascender?» y no para «¿gano el
sábado?». La ventaja de campo es un parámetro global, no por estadio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Fuerza del encogimiento: partidos equivalentes de "prior" que pesa la media
# de la liga frente a la evidencia propia de cada equipo.
SHRINKAGE_K = 5.0

# Ventaja de jugar en casa, como multiplicador sobre λ del local. Valor de la
# comunidad de Hattrick; se recalibra en cuanto haya partidos suficientes.
HOME_ADVANTAGE = 1.20

POINTS_WIN, POINTS_DRAW, POINTS_LOSS = 3, 1, 0


@dataclass(frozen=True)
class TeamRecord:
    """Lo que ya ha pasado, tal cual sale de la clasificación."""

    ht_team_id: int
    name: str
    played: int
    won: int
    drawn: int
    lost: int
    goals_for: int
    goals_against: int
    points: int


@dataclass(frozen=True)
class Fixture:
    home_ht_id: int
    away_ht_id: int
    match_round: int


@dataclass
class TeamOutlook:
    ht_team_id: int
    name: str
    current_points: int
    current_position: int
    expected_points: float
    expected_position: float
    position_distribution: dict[int, float]   # posición → probabilidad
    title_probability: float
    promotion_probability: float              # 1º, solo si no es ya primera división
    second_to_fourth_probability: float       # 2º-4º
    relegation_playoff_probability: float     # 5º-6º: promoción para no descender
    relegation_probability: float             # 7º-8º, solo si no es ya la última división
    attack_strength: float
    defence_strength: float

    @property
    def most_likely_position(self) -> int:
        return max(self.position_distribution, key=lambda p: self.position_distribution[p])


@dataclass
class MatchForecast:
    home: str
    away: str
    match_round: int
    home_win: float
    draw: float
    away_win: float
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str

    @property
    def verdict(self) -> str:
        best = max(self.home_win, self.draw, self.away_win)
        if best == self.home_win:
            return f"favorito {self.home}"
        if best == self.away_win:
            return f"favorito {self.away}"
        return "empate como resultado más probable"


@dataclass
class BestWorstCase:
    ht_team_id: int
    name: str
    remaining_matches: int
    current_points: int
    current_position: int
    best_case_position_distribution: dict[int, float]
    best_case_expected_points: float
    worst_case_position_distribution: dict[int, float]
    worst_case_expected_points: float


# Goles de una goleada: suficientemente altos para que el desempate de
# diferencia de goles nunca entre en juego frente al resto de la liga, que
# juega con marcadores realistas.
_LANDSLIDE_GOALS = 14
# No 0 exacto: 0 simulado con Poisson(0.001) dista igual de "casi seguro" y
# deja una probabilidad ínfima de un gol suelto, que es lo que pide la
# especificación en vez de fijarlo también a un número.
_NEGLIGIBLE_LAMBDA = 0.001


def best_worst_case(
    records: list[TeamRecord],
    fixtures: list[Fixture],
    target_team_id: int,
    runs: int = 10000,
    seed: int = 42,
) -> BestWorstCase | None:
    """Mejor y peor caso del equipo analizado, como DISTRIBUCIÓN de puestos.

    Reusa el mismo motor de Poisson que `simulate`, pero para los partidos
    pendientes DEL EQUIPO ANALIZADO fuerza el resultado a un extremo:

    - Peor caso: sus goles a favor salen de Poisson(λ=0.001) — casi siempre
      0 — y sus goles en contra se fijan directamente en 14 (goleada, no
      simulada).
    - Mejor caso: al revés — 14 goles a favor fijos, goles en contra con
      Poisson(λ=0.001).

    El resto de partidos (los que no involucran al equipo analizado) se
    simulan exactamente igual que en `simulate`, con las fuerzas de ataque y
    defensa reales de cada equipo — por eso el resultado es una distribución
    y no un único número: aunque el equipo analizado tenga un resultado
    fijado, el resto de la liga sigue siendo incierto.
    """
    if not records or not any(r.ht_team_id == target_team_id for r in records):
        return None

    attack, defence, avg = _strengths(records)
    ids = [r.ht_team_id for r in records]
    index = {t: i for i, t in enumerate(ids)}
    n = len(ids)
    target = next(r for r in records if r.ht_team_id == target_team_id)

    current_order = sorted(
        records, key=lambda r: (-r.points, -(r.goals_for - r.goals_against), -r.goals_for)
    )
    current_position = {r.ht_team_id: i + 1 for i, r in enumerate(current_order)}
    remaining_matches = sum(
        1 for fx in fixtures if target_team_id in (fx.home_ht_id, fx.away_ht_id)
    )

    def run_scenario(
        target_for_lambda: float | None, target_for_fixed: int | None,
        target_against_lambda: float | None, target_against_fixed: int | None,
    ) -> tuple[dict[int, float], float]:
        rng = np.random.default_rng(seed)
        points = np.tile(np.array([r.points for r in records], dtype=float), (runs, 1))
        gd = np.tile(
            np.array([r.goals_for - r.goals_against for r in records], dtype=float), (runs, 1)
        )
        gf = np.tile(np.array([r.goals_for for r in records], dtype=float), (runs, 1))

        for fx in fixtures:
            if fx.home_ht_id not in index or fx.away_ht_id not in index:
                continue
            h, a = index[fx.home_ht_id], index[fx.away_ht_id]
            if target_team_id in (fx.home_ht_id, fx.away_ht_id):
                target_goals = (
                    np.full(runs, target_for_fixed, dtype=float)
                    if target_for_fixed is not None
                    else rng.poisson(target_for_lambda, runs).astype(float)
                )
                rival_goals = (
                    np.full(runs, target_against_fixed, dtype=float)
                    if target_against_fixed is not None
                    else rng.poisson(target_against_lambda, runs).astype(float)
                )
                gh, ga = (
                    (target_goals, rival_goals)
                    if fx.home_ht_id == target_team_id
                    else (rival_goals, target_goals)
                )
            else:
                lh, la = _lambdas(fx.home_ht_id, fx.away_ht_id, attack, defence, avg)
                gh = rng.poisson(lh, runs).astype(float)
                ga = rng.poisson(la, runs).astype(float)

            points[:, h] += np.where(gh > ga, POINTS_WIN, np.where(gh == ga, POINTS_DRAW, POINTS_LOSS))
            points[:, a] += np.where(ga > gh, POINTS_WIN, np.where(gh == ga, POINTS_DRAW, POINTS_LOSS))
            gd[:, h] += gh - ga
            gd[:, a] += ga - gh
            gf[:, h] += gh
            gf[:, a] += ga

        key = points * 1_000_000 + gd * 1_000 + gf
        order = np.argsort(-key, axis=1)
        positions = np.empty_like(order)
        rows = np.arange(runs)[:, None]
        positions[rows, order] = np.arange(1, n + 1)[None, :]

        col = positions[:, index[target_team_id]]
        dist = {p: round(float(np.mean(col == p)), 4) for p in range(1, n + 1)}
        expected_pts = round(float(points[:, index[target_team_id]].mean()), 2)
        return dist, expected_pts

    worst_dist, worst_pts = run_scenario(
        target_for_lambda=_NEGLIGIBLE_LAMBDA, target_for_fixed=None,
        target_against_lambda=None, target_against_fixed=_LANDSLIDE_GOALS,
    )
    best_dist, best_pts = run_scenario(
        target_for_lambda=None, target_for_fixed=_LANDSLIDE_GOALS,
        target_against_lambda=_NEGLIGIBLE_LAMBDA, target_against_fixed=None,
    )

    return BestWorstCase(
        ht_team_id=target_team_id, name=target.name,
        remaining_matches=remaining_matches,
        current_points=target.points, current_position=current_position[target_team_id],
        best_case_position_distribution=best_dist, best_case_expected_points=best_pts,
        worst_case_position_distribution=worst_dist, worst_case_expected_points=worst_pts,
    )


@dataclass
class SeasonSimulation:
    teams: list[TeamOutlook]
    runs: int
    rounds_played: int
    rounds_remaining: int
    league_avg_goals: float
    shrinkage_k: float
    home_advantage: float
    is_top_division: bool = False
    is_bottom_division: bool = False
    next_matches: list[MatchForecast] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


def _strengths(records: list[TeamRecord]) -> tuple[dict[int, float], dict[int, float], float]:
    """Ataque y defensa encogidos hacia la media de la liga.

    Un valor de ataque de 1.0 es exactamente la media; 1.3 es marcar un 30% más
    que un equipo medio. Defensa funciona al revés: 0.8 es encajar un 20% menos.
    """
    total_goals = sum(r.goals_for for r in records)
    total_matches = sum(r.played for r in records)
    league_avg = total_goals / total_matches if total_matches else 1.0
    if league_avg <= 0:
        league_avg = 1.0

    attack, defence = {}, {}
    for r in records:
        # (observado + k × prior) / (n + k). El prior es "un equipo medio".
        att = (r.goals_for + SHRINKAGE_K * league_avg) / (r.played + SHRINKAGE_K)
        dfn = (r.goals_against + SHRINKAGE_K * league_avg) / (r.played + SHRINKAGE_K)
        attack[r.ht_team_id] = att / league_avg
        defence[r.ht_team_id] = dfn / league_avg
    return attack, defence, league_avg


def _lambdas(
    home: int, away: int, attack: dict[int, float], defence: dict[int, float], avg: float
) -> tuple[float, float]:
    lh = avg * attack[home] * defence[away] * HOME_ADVANTAGE
    la = avg * attack[away] * defence[home]
    return max(lh, 0.05), max(la, 0.05)


def simulate(
    records: list[TeamRecord],
    fixtures: list[Fixture],
    runs: int = 10000,
    seed: int = 42,
    league_level: int = -1,
    max_level: int = -1,
) -> SeasonSimulation:
    """Simula lo que queda de temporada y devuelve la distribución de puestos.

    `league_level`/`max_level` (de leaguedetails.xml, HL-145) determinan si
    hay a dónde ascender o descender: el 1º de la división más alta del país
    no asciende más, y el 7º-8º de la más baja no desciende más — ninguna de
    las dos cosas es una elección de diseño, son hechos de la pirámide.
    -1 = desconocido: no se filtra nada y se avisa en `caveats`.
    """
    if not records:
        raise ValueError("no hay clasificación que simular")

    is_top_division = league_level == 1
    is_bottom_division = league_level > 0 and max_level > 0 and league_level == max_level
    division_known = league_level > 0

    rng = np.random.default_rng(seed)
    ids = [r.ht_team_id for r in records]
    index = {t: i for i, t in enumerate(ids)}
    n = len(ids)

    attack, defence, avg = _strengths(records)

    base_points = np.array([r.points for r in records], dtype=float)
    base_gd = np.array([r.goals_for - r.goals_against for r in records], dtype=float)
    base_gf = np.array([r.goals_for for r in records], dtype=float)

    points = np.tile(base_points, (runs, 1))
    gd = np.tile(base_gd, (runs, 1))
    gf = np.tile(base_gf, (runs, 1))

    for fx in fixtures:
        if fx.home_ht_id not in index or fx.away_ht_id not in index:
            continue
        h, a = index[fx.home_ht_id], index[fx.away_ht_id]
        lh, la = _lambdas(fx.home_ht_id, fx.away_ht_id, attack, defence, avg)
        gh = rng.poisson(lh, runs)
        ga = rng.poisson(la, runs)

        points[:, h] += np.where(gh > ga, POINTS_WIN, np.where(gh == ga, POINTS_DRAW, POINTS_LOSS))
        points[:, a] += np.where(ga > gh, POINTS_WIN, np.where(gh == ga, POINTS_DRAW, POINTS_LOSS))
        gd[:, h] += gh - ga
        gd[:, a] += ga - gh
        gf[:, h] += gh
        gf[:, a] += ga

    # Orden de Hattrick: puntos, luego diferencia de goles, luego goles a favor.
    # Se combinan en una clave única para poder ordenar de una vez.
    key = points * 1_000_000 + gd * 1_000 + gf
    order = np.argsort(-key, axis=1)
    positions = np.empty_like(order)
    rows = np.arange(runs)[:, None]
    positions[rows, order] = np.arange(1, n + 1)[None, :]

    current = sorted(
        records, key=lambda r: (-r.points, -(r.goals_for - r.goals_against), -r.goals_for)
    )
    current_pos = {r.ht_team_id: i + 1 for i, r in enumerate(current)}

    outlooks: list[TeamOutlook] = []
    for team_id in ids:
        i = index[team_id]
        rec = next(r for r in records if r.ht_team_id == team_id)
        col = positions[:, i]
        dist = {p: float(np.mean(col == p)) for p in range(1, n + 1)}
        outlooks.append(
            TeamOutlook(
                ht_team_id=team_id,
                name=rec.name,
                current_points=rec.points,
                current_position=current_pos[team_id],
                expected_points=round(float(points[:, i].mean()), 2),
                expected_position=round(float(col.mean()), 2),
                position_distribution={p: round(v, 4) for p, v in dist.items()},
                title_probability=round(dist[1], 4),
                # 1º asciende directo — nada si ya está en la división más alta.
                promotion_probability=0.0 if is_top_division else round(dist[1], 4),
                # 2º-4º: ni título ni promoción/descenso, la zona "intermedia alta".
                second_to_fourth_probability=round(
                    dist.get(2, 0.0) + dist.get(3, 0.0) + dist.get(4, 0.0), 4
                ),
                # 5º-6º juegan una promoción para NO descender (no es un ascenso
                # extra) — no aplica si no hay a dónde descender.
                relegation_playoff_probability=(
                    0.0 if is_bottom_division
                    else round(dist.get(5, 0.0) + dist.get(6, 0.0), 4)
                ),
                # 7º-8º descienden directo — nada si ya está en la última división.
                relegation_probability=(
                    0.0 if is_bottom_division
                    else round(dist.get(n, 0.0) + dist.get(n - 1, 0.0), 4)
                ),
                attack_strength=round(attack[team_id], 3),
                defence_strength=round(defence[team_id], 3),
            )
        )
    outlooks.sort(key=lambda o: o.expected_position)

    played = max((r.played for r in records), default=0)
    remaining = len({f.match_round for f in fixtures})

    caveats: list[str] = []
    # El umbral no es arbitrario: mientras las jornadas jugadas sean menos que
    # k, el prior de "equipo medio" pesa más que la evidencia propia de cada
    # equipo, y conviene decirlo en vez de dejar que el usuario lea las
    # probabilidades como si vinieran de sus datos.
    if played < SHRINKAGE_K:
        caveats.append(
            f"Sólo {played} jornadas jugadas frente a un peso de prior de "
            f"{SHRINKAGE_K:g}: el encogimiento hacia la media de la liga pesa "
            "más que la evidencia propia de cada equipo, así que las "
            "probabilidades tiran hacia el sorteo. Es lo correcto, no un "
            "defecto: con esta muestra, la confianza sería falsa."
        )
    if not division_known:
        caveats.append(
            "No se sabe si esta es la división más alta o la más baja del país "
            "(falta sincronizar `LeagueLevel` de leaguedetails), así que ascenso "
            "y descenso se calculan sin filtrar esos dos casos límite."
        )
    if not fixtures:
        caveats.append(
            "No hay calendario pendiente sincronizado, así que la simulación "
            "sólo refleja la tabla actual sin jugar nada más."
        )
    caveats.append(
        "El modelo usa forma agregada: no conoce lesiones, alineaciones ni "
        "tácticas. Sirve para las opciones de la temporada, no para acertar un "
        "partido concreto."
    )

    return SeasonSimulation(
        teams=outlooks,
        runs=runs,
        rounds_played=played,
        rounds_remaining=remaining,
        league_avg_goals=round(avg, 3),
        shrinkage_k=SHRINKAGE_K,
        home_advantage=HOME_ADVANTAGE,
        is_top_division=is_top_division,
        is_bottom_division=is_bottom_division,
        caveats=caveats,
    )


def forecast_match(
    home: TeamRecord,
    away: TeamRecord,
    records: list[TeamRecord],
    match_round: int = 0,
    runs: int = 20000,
    seed: int = 7,
) -> MatchForecast:
    """Probabilidades de un partido concreto con el mismo modelo de goles."""
    attack, defence, avg = _strengths(records)
    lh, la = _lambdas(home.ht_team_id, away.ht_team_id, attack, defence, avg)

    rng = np.random.default_rng(seed)
    gh = rng.poisson(lh, runs)
    ga = rng.poisson(la, runs)

    scores: dict[str, int] = {}
    for h, a in zip(gh[:2000], ga[:2000], strict=True):
        scores[f"{h}-{a}"] = scores.get(f"{h}-{a}", 0) + 1

    return MatchForecast(
        home=home.name,
        away=away.name,
        match_round=match_round,
        home_win=round(float(np.mean(gh > ga)), 4),
        draw=round(float(np.mean(gh == ga)), 4),
        away_win=round(float(np.mean(ga > gh)), 4),
        expected_home_goals=round(lh, 2),
        expected_away_goals=round(la, 2),
        most_likely_score=max(scores, key=lambda s: scores[s]) if scores else "0-0",
    )


def model_info() -> dict[str, object]:
    return {
        "model": "Poisson independiente con encogimiento bayesiano",
        "shrinkageK": SHRINKAGE_K,
        "homeAdvantage": HOME_ADVANTAGE,
        "shrinkageFormula": "(goles + k × media_liga) / (partidos + k)",
        "tieBreakers": ["puntos", "diferencia de goles", "goles a favor"],
        "doesNotModel": ["lesiones", "alineaciones", "tácticas", "clima"],
    }
