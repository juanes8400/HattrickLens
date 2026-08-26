"""Scouting de rivales — el gancho: comparar tu plantilla contra la del
próximo rival con las mismas herramientas que usas para la tuya, dentro de
lo que CHPP realmente deja ver de un equipo ajeno.

Restricción real verificada contra la API: `players.xml` de un equipo que no
es el tuyo da TSI, edad, forma y salario reales, pero las skills exactas
vienen todas en 0 (ocultas) y el nombre viene vacío. Solo `matchlineup.xml`
de un partido ya finalizado revela nombre + posición real jugada — de ambos
equipos, porque un partido jugado es un hecho público permanente, no un
estado de cuenta que se esté trackeando.
"""

import math
import statistics
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.engines.stats import gaussian_kde
from app.domain.value_objects.formatting import thousands
from app.domain.value_objects.ht_constants import (
    MAN_MARKING_ELIGIBLE_MARKERS,
    MAN_MARKING_ELIGIBLE_TARGETS,
    MAN_MARKING_PROXIMITY,
    MATCH_POSITION_KEEPER,
    match_position_name,
    tactic_type_name,
)

# ── Comparación de TSI (KDE) ────────────────────────────────────────────────
# gaussian_kde vive en stats.py (HL-15x): es estadística genérica, reutilizada
# también por las distribuciones de la propia plantilla en la ficha de
# jugador, donde "rival" no aplica.


@dataclass
class TsiDistribution:
    grid: list[float]
    own_density: list[float]
    rival_density: list[float]
    own_values: list[float]
    rival_values: list[float]
    log_transform: bool


def tsi_kde_comparison(
    own_players: list[dict[str, Any]],
    rival_players: list[dict[str, Any]],
    log_transform: bool = False,
    grid_points: int = 200,
) -> TsiDistribution:
    """Compara la distribución de TSI propia vs. la del rival.

    Cada dict de jugador: `{"tsi": int, ...}`. Entran TODOS: hasta 2026-08-18
    hubo un interruptor de "excluir nuestro arquero" que, además de esconder a
    un jugador de la plantilla sin decirlo en el gráfico, descartaba también al
    arquero del rival pese a lo que decía su etiqueta. Un histograma de la
    plantilla es de la plantilla entera.
    """

    def values(players: list[dict[str, Any]]) -> list[float]:
        out = [float(p["tsi"]) for p in players]
        if log_transform:
            out = [math.log1p(v) for v in out]
        return out

    own_values = values(own_players)
    rival_values = values(rival_players)
    all_values = own_values + rival_values
    lo = min(all_values) if all_values else 0.0
    hi = max(all_values) if all_values else 1.0
    if lo == hi:
        hi = lo + 1.0
    pad = (hi - lo) * 0.1
    grid = [lo - pad + (hi - lo + 2 * pad) * i / (grid_points - 1) for i in range(grid_points)]

    return TsiDistribution(
        grid=grid,
        own_density=gaussian_kde(own_values, grid),
        rival_density=gaussian_kde(rival_values, grid),
        own_values=own_values,
        rival_values=rival_values,
        log_transform=log_transform,
    )


# ── Marcaje al hombre ───────────────────────────────────────────────────────


#  Manual no Escrito (wiki.hattrick.org) + reglas oficiales del marcaje
# individual (docs/reference/MAN_MARKING_RULES.md). Cualquiera de {lateral,
# defensa central, interior} puede marcar LEGALMENTE a cualquiera de
# {extremo, delantero, interior} rival — MAN_MARKING_PROXIMITY es solo la
# combinación "cerca" (-50%, la más eficiente); cualquier otra combinación
# de esas dos listas es "lejos" (-65%), sigue siendo una orden válida, solo
# menos eficiente. Este motor prefiere siempre "cerca" y solo cae a "lejos"
# cuando no hay ningún marcador cercano disponible — nunca deja de sugerir
# solo porque la combinación óptima no está disponible.
MARKER_LOSS_PCT_CLOSE = 0.50
MARKER_LOSS_PCT_FAR = 0.65


@dataclass
class ManMarkingSuggestion:
    target_name: str
    target_position: str
    target_tsi: int
    marker_name: str
    marker_position: str
    confidence: str
    rationale: str
    efficiency: str  # "cerca" (-50%) | "lejos" (-65%)
    marker_loss_pct: float
    risk_note: str
    evidence: dict[str, Any] = field(default_factory=dict)


def _close_marker_group(target_position: int) -> frozenset[int] | None:
    return next(
        (
            markers
            for markers, markable in MAN_MARKING_PROXIMITY.items()
            if target_position in markable
        ),
        None,
    )


def suggest_man_marking(
    own_players: list[dict[str, Any]],
    rival_players: list[dict[str, Any]],
) -> ManMarkingSuggestion | None:
    """Sugiere a quién marcar al hombre y con quién, según las reglas reales
    del marcaje individual: cualquiera de tus centrales, laterales o
    interiores puede marcar a cualquier delantero, extremo o interior
    rival — eso SIEMPRE es legal. La tabla del Manual no Escrito
    (lateral↔extremo, central↔delantero, interior↔interior) es solo la
    combinación más EFICIENTE (-50% para el marcado); cualquier otra
    combinación legal es menos eficiente (-65%) pero se sigue pudiendo
    ordenar — este motor prefiere "cerca" y solo ofrece "lejos" cuando no
    hay ningún marcador cercano disponible.

    El TSI del rival es la única señal de peligrosidad disponible (CHPP
    oculta sus skills exactas y su especialidad), así que la confianza de
    la sugerencia se marca explícitamente como aproximada — no se puede
    replicar aquí la fórmula real (Defensa del marcador vs. la habilidad
    más alta del marcado, con modificadores de especialidad/forma/salud).

    Cada dict de jugador: `{"name", "ht_player_id", "position_code", "tsi"?,
    "defending"?}`. Jugadores sin `position_code` conocido (nunca vistos en un
    matchlineup) se ignoran: no se puede recomendar marcar a alguien cuya
    posición no hemos observado.
    """
    targets = [
        p
        for p in rival_players
        if p.get("position_code") is not None and p["position_code"] in MAN_MARKING_ELIGIBLE_TARGETS
    ]
    if not targets:
        return None
    target = max(targets, key=lambda p: p.get("tsi", 0))

    close_group = _close_marker_group(target["position_code"])
    eligible_close = [
        p for p in own_players if close_group is not None and p.get("position_code") in close_group
    ]
    eligible_far = [
        p
        for p in own_players
        if p.get("position_code") in MAN_MARKING_ELIGIBLE_MARKERS
        and p.get("position_code") not in (close_group or frozenset())
    ]

    if eligible_close:
        marker, efficiency, loss_pct = (
            max(eligible_close, key=lambda p: p.get("defending", 0)),
            "cerca",
            MARKER_LOSS_PCT_CLOSE,
        )
    elif eligible_far:
        marker, efficiency, loss_pct = (
            max(eligible_far, key=lambda p: p.get("defending", 0)),
            "lejos",
            MARKER_LOSS_PCT_FAR,
        )
    else:
        return None

    rationale = (
        f"{target['name']} es el {match_position_name(target['position_code']).lower()} "
        f"con más TSI del rival ({thousands(target.get('tsi', 0))}). {marker['name']} puede "
        f"marcarlo desde {match_position_name(marker['position_code']).lower()}"
        + (
            "."
            if efficiency == "cerca"
            else ', combinación "lejos", -65% en vez del -50% '
            "óptimo: no hay ningún lateral/central/interior mejor ubicado disponible."
        )
    )
    risk_note = (
        "Si el rival cambia su alineación antes del partido y este jugador no termina jugando "
        "(o pasa a una posición no marcable), la orden se anula pero tu jugador igual pierde un "
        "10% fijo de su contribución. Mientras la orden esté activa, tampoco contribuye al nivel "
        "de táctica de equipo (Presionar, Contraataques...), solo se puede dar una orden de "
        "marcaje por partido."
    )

    return ManMarkingSuggestion(
        target_name=target["name"],
        target_position=match_position_name(target["position_code"]),
        target_tsi=target.get("tsi", 0),
        marker_name=marker["name"],
        marker_position=match_position_name(marker["position_code"]),
        confidence="aproximada, el TSI es la única señal pública de peligrosidad del rival",
        rationale=rationale,
        efficiency=efficiency,
        marker_loss_pct=loss_pct,
        risk_note=risk_note,
        evidence={
            "targetCandidates": [
                {
                    "name": t["name"],
                    "tsi": t.get("tsi", 0),
                    "position": match_position_name(t["position_code"]),
                }
                for t in sorted(targets, key=lambda p: -p.get("tsi", 0))[:5]
            ],
        },
    )


# ── Probabilidad de ganar ───────────────────────────────────────────────────
#
# HL-140 aclarado por el usuario: "no presentar el futuro como cierto" no
# significa nunca proyectar — significa no MEZCLAR hechos con proyecciones
# sin avisar. Esto SÍ es una proyección, y se presenta siempre separada
# visualmente de los paneles de hechos, con su propio rótulo.
#
# Modelo deliberadamente simple: una función de contienda (contest success
# function) de exponente 1 sobre el TSI total de los probables 11 de cada
# lado — own = tu mejor once real (motor de posiciones), rival = sus 11 de
# mayor TSI (única aproximación honesta, CHPP oculta sus skills). No es la
# fórmula del motor de partido de Hattrick (esa necesita habilidades reales
# de ambos equipos, clima, táctica...) y NO está calibrada contra resultados
# reales — a diferencia de `position_engine`, que sí lo está. Se declara con
# confianza "baja" a propósito.


@dataclass
class WinProbability:
    own_probability: float
    own_tsi_total: int
    rival_tsi_total: int
    confidence: str = (
        "baja, estimación gruesa por TSI total, no la fórmula real del motor de partido "
        "(que necesita habilidades reales de ambos equipos) ni está calibrada contra "
        "resultados reales"
    )


def estimate_win_probability(own_tsi_total: int, rival_tsi_total: int) -> WinProbability:
    """Proyección, no un hecho — HL-144. `own_tsi_total`/`rival_tsi_total`
    deben venir del TSI real de los 11 probables de cada lado (no la
    plantilla completa), calculados por quien llama."""
    total = own_tsi_total + rival_tsi_total
    probability = own_tsi_total / total if total > 0 else 0.5
    return WinProbability(
        own_probability=round(probability, 3),
        own_tsi_total=own_tsi_total,
        rival_tsi_total=rival_tsi_total,
    )


# ── Rotación de lado fuerte ─────────────────────────────────────────────────


@dataclass
class AttackByMatch:
    """El ataque de UN partido, carril por carril."""

    label: str  # rival de aquel día, o la fecha si no se sabe
    date: str
    left: int
    central: int
    right: int
    best: str  # "izquierda" | "centro" | "derecha"


@dataclass
class SideRotation:
    attack_left_avg: float
    attack_central_avg: float
    attack_right_avg: float
    attack_left_std: float
    attack_central_std: float
    attack_right_std: float
    strong_side: str
    # % de los partidos vistos en los que `strong_side` fue el lado con
    # mejor rating ESE partido concreto — 100% es "el mismo lado, partido
    # tras partido, sin excepción"; un valor bajo con std alto es "rota de
    # verdad", no solo "por poco no domina siempre".
    dominant_pct: float
    dominant_side_by_match: list[str]
    # Un renglón por partido con los tres carriles: es lo que permite ver la
    # secuencia real en vez de tres promedios. Un promedio de 45 puede ser
    # "45 todas las semanas" o "70, 20, 45", y para preparar un partido no es
    # lo mismo.
    attack_by_match: list[AttackByMatch]
    rotates: bool
    matches_analysed: int


def analyse_side_rotation(match_ratings: list[dict[str, Any]]) -> SideRotation | None:
    """¿El rival ataca siempre por el mismo lado o rota? Usa los ratings de
    sector ya reales e históricos de los partidos jugados contra él
    (`left_att`, `central_att`, `right_att` de MatchRating).

    Si el lado con mejor rating medio cambia partido a partido (no es
    consistentemente el mismo), se considera que rota; si el mismo lado
    domina en la mayoría de partidos, se marca como su lado fuerte fijo.
    La desviación estándar por carril y la secuencia partido a partido
    (`dominant_side_by_match`) distinguen "siempre exactamente el mismo
    lado, por mucho margen" de "el mismo lado en promedio, pero muy reñido"
    — un solo booleano (`rotates`) no alcanza para esa diferencia.
    """
    if not match_ratings:
        return None
    left = [m["left_att"] for m in match_ratings]
    central = [m["central_att"] for m in match_ratings]
    right = [m["right_att"] for m in match_ratings]
    n = len(match_ratings)

    best_side_per_match = []
    for m in match_ratings:
        sides = {"izquierda": m["left_att"], "centro": m["central_att"], "derecha": m["right_att"]}
        best_side_per_match.append(max(sides, key=lambda s: sides[s]))

    avg = {"izquierda": sum(left) / n, "centro": sum(central) / n, "derecha": sum(right) / n}
    std = {
        "izquierda": statistics.pstdev(left) if n > 1 else 0.0,
        "centro": statistics.pstdev(central) if n > 1 else 0.0,
        "derecha": statistics.pstdev(right) if n > 1 else 0.0,
    }
    strong_side = max(avg, key=lambda s: avg[s])
    dominant_count = best_side_per_match.count(strong_side)
    dominant_pct = round(100 * dominant_count / n, 1)
    rotates = dominant_count < (n * 0.6)  # domina en menos del 60% de los partidos vistos

    por_partido = [
        AttackByMatch(
            label=str(m.get("opponent") or m.get("match_date", ""))[:24],
            date=str(m.get("match_date", "")),
            left=m["left_att"],
            central=m["central_att"],
            right=m["right_att"],
            best=mejor,
        )
        for m, mejor in zip(match_ratings, best_side_per_match, strict=True)
    ]

    return SideRotation(
        attack_left_avg=round(avg["izquierda"], 1),
        attack_central_avg=round(avg["centro"], 1),
        attack_right_avg=round(avg["derecha"], 1),
        attack_left_std=round(std["izquierda"], 1),
        attack_central_std=round(std["centro"], 1),
        attack_right_std=round(std["derecha"], 1),
        strong_side=strong_side,
        dominant_pct=dominant_pct,
        dominant_side_by_match=best_side_per_match,
        attack_by_match=por_partido,
        rotates=rotates,
        matches_analysed=n,
    )


# ── Mapa de calor por zona de la cancha ─────────────────────────────────────


class PitchZoneMethod(StrEnum):
    """Cómo se resume una zona a lo largo de varios partidos.

    Todas las herramientas se quedan en el promedio, y el promedio esconde
    cosas: un rival que en un partido clavó un ataque brutal por la derecha y
    en los otros cuatro no atacó por ahí sale flojo por la derecha. Estos
    cuatro resúmenes responden preguntas distintas sobre los mismos datos.
    """

    AVERAGE = "average"  # cómo juega de costumbre
    MAX = "max"  # de lo que es capaz en cada zona
    MAX_PARALLEL = "max_parallel"  # de lo que es capaz por CUALQUIER carril
    LAST = "last"  # con lo que salió el último día
    # Solo para el lado PROPIO: la predicción de minuto 0 que da el mismo
    # Hattrick para las órdenes ya enviadas. De un rival no existe, porque sus
    # órdenes son privadas hasta que se juega.
    SUBMITTED = "submitted"


@dataclass
class PitchZoneValues:
    left_def: float
    central_def: float
    right_def: float
    midfield: float
    left_att: float
    central_att: float
    right_att: float
    matches_analysed: int


PITCH_ZONE_KEYS = (
    "left_def",
    "central_def",
    "right_def",
    "midfield",
    "left_att",
    "central_att",
    "right_att",
)


# Los tres carriles de cada mitad. Sirven para el resumen "de lo que es capaz
# por cualquier carril": un ataque que rompió por la izquierda puede volver a
# romper por la derecha si el rival mueve a sus hombres.
PARALLEL_ZONES: tuple[tuple[str, ...], ...] = (
    ("left_def", "central_def", "right_def"),
    ("left_att", "central_att", "right_att"),
)


def pitch_zone_values(
    match_ratings: list[dict[str, int]],
    method: str = PitchZoneMethod.AVERAGE,
) -> PitchZoneValues | None:
    """Las 7 zonas de la cancha (3 defensa, medio, 3 ataque) resumidas sobre
    los partidos ya vistos, con los mismos ratings de `matchdetails` que usa
    `analyse_side_rotation` pero sin reducir a "lado fuerte".

    `match_ratings` llega del más viejo al más reciente: LAST se queda con el
    último de la lista.
    """
    if not match_ratings:
        return None
    n = len(match_ratings)
    if method == PitchZoneMethod.LAST:
        valores = {key: float(match_ratings[-1][key]) for key in PITCH_ZONE_KEYS}
    elif method in (PitchZoneMethod.MAX, PitchZoneMethod.MAX_PARALLEL):
        valores = {key: float(max(r[key] for r in match_ratings)) for key in PITCH_ZONE_KEYS}
        if method == PitchZoneMethod.MAX_PARALLEL:
            for carriles in PARALLEL_ZONES:
                techo = max(valores[key] for key in carriles)
                for key in carriles:
                    valores[key] = techo
    else:
        valores = {key: round(sum(r[key] for r in match_ratings) / n, 1) for key in PITCH_ZONE_KEYS}
    return PitchZoneValues(matches_analysed=n, **valores)


# ── Duelos cabeza a cabeza por carril (cancha horizontal) ───────────────────
#
# Un extremo IZQUIERDO ataca por el mismo lateral físico que defiende el
# LATERAL DERECHO rival — como en cualquier alineación de fútbol reflejada:
# de pie detrás de tu portería mirando hacia la del rival, el carril físico
# de la izquierda es siempre el mismo carril, y por él corren TU ataque
# izquierdo cuando atacas y el ataque DERECHO del rival cuando ataca él (va
# en la dirección contraria). Por eso cada carril empareja tu zona con la
# zona ESPEJADA del rival, en las dos mitades de la cancha.


@dataclass
class ZoneDuel:
    zone: str  # "left" | "central" | "right" | "midfield"
    half: str  # "own" (tu campo) | "rival" (su campo) | "midfield"
    own_value: float
    rival_value: float
    own_pct: float
    rival_pct: float


def pitch_zone_duels(own: PitchZoneValues, rival: PitchZoneValues) -> list[ZoneDuel]:
    """7 duelos cabeza a cabeza: 3 en tu campo (tu defensa contra su ataque
    reflejado), 3 en el campo rival (tu ataque contra su defensa reflejada) y
    el de medio campo (posesión). El % es la misma función de contienda
    simple que `estimate_win_probability` (rating / (rating + rating)) — una
    aproximación declarada, no la fórmula real (mucho más rica) del motor de
    partido de Hattrick."""

    def duel(zone: str, half: str, own_value: float, rival_value: float) -> ZoneDuel:
        total = own_value + rival_value
        own_pct = own_value / total if total > 0 else 0.5
        return ZoneDuel(
            zone=zone,
            half=half,
            own_value=own_value,
            rival_value=rival_value,
            own_pct=round(own_pct, 3),
            rival_pct=round(1 - own_pct, 3),
        )

    return [
        duel("left", "own", own.left_def, rival.right_att),
        duel("central", "own", own.central_def, rival.central_att),
        duel("right", "own", own.right_def, rival.left_att),
        duel("left", "rival", own.left_att, rival.right_def),
        duel("central", "rival", own.central_att, rival.central_def),
        duel("right", "rival", own.right_att, rival.left_def),
        duel("midfield", "midfield", own.midfield, rival.midfield),
    ]


# ── Historial de táctica ─────────────────────────────────────────────────────
#
# La actitud (TeamAttitude) se dejó fuera a propósito: CHPP nunca la incluye
# para el lado que no es el tuyo (verificado en vivo), así que no hay nada
# honesto que resumir ahí. Táctica (TacticType), su nivel (TacticSkill) y la
# formación sí son públicos para CUALQUIER equipo — también verificado en
# vivo — así que esos tres son los que arma este resumen.


@dataclass
class TacticFrequency:
    code: int
    label: str
    count: int
    pct: float


@dataclass
class FormationFrequency:
    formation: str
    count: int
    pct: float


@dataclass
class TacticHistory:
    matches_analysed: int
    tactics: list[TacticFrequency]
    most_common_tactic: TacticFrequency | None
    avg_tactic_skill: float | None
    formations: list[FormationFrequency]
    most_common_formation: FormationFrequency | None


def _frequencies(codes: list[int], name_fn: Any) -> list[TacticFrequency]:
    counts: dict[int, int] = {}
    for c in codes:
        counts[c] = counts.get(c, 0) + 1
    total = len(codes)
    out = [
        TacticFrequency(code=c, label=name_fn(c), count=cnt, pct=round(100 * cnt / total, 1))
        for c, cnt in counts.items()
    ]
    return sorted(out, key=lambda f: -f.count)


def _formation_frequencies(formations: list[str]) -> list[FormationFrequency]:
    real = [f for f in formations if f]
    if not real:
        return []
    counts: dict[str, int] = {}
    for f in real:
        counts[f] = counts.get(f, 0) + 1
    total = len(real)
    out = [
        FormationFrequency(formation=f, count=cnt, pct=round(100 * cnt / total, 1))
        for f, cnt in counts.items()
    ]
    return sorted(out, key=lambda f: -f.count)


def summarise_tactics(
    tactic_types: list[int], tactic_skills: list[int], formations: list[str]
) -> TacticHistory | None:
    """Con qué táctica juega este rival normalmente, a qué nivel y en qué
    formación, según TODOS los partidos con datos de sector ya sincronizados
    contra él (no el cap de `MAX_MATCHES_ANALYSED` que limita las llamadas en
    vivo a matchlineup — esto es una consulta a la propia base, sin llamadas
    nuevas a CHPP). Son datos de partidos ya finalizados: un hecho público
    permanente, no un estado de cuenta ajena que se esté trackeando en el
    tiempo.

    `tactic_skills` en 0 no se filtra: coincide con TacticType=0 ("Normal")
    y es un valor real, no ausente — un partido sin táctica especial de
    verdad gasta 0 de nivel. `formations` puede traer cadenas vacías (filas
    de antes de que se empezara a guardar esa columna); esas sí se excluyen
    del reparto, para no inventar una formación."""
    if not tactic_types:
        return None

    tactics = _frequencies(tactic_types, tactic_type_name)
    avg_tactic_skill = round(sum(tactic_skills) / len(tactic_skills), 1) if tactic_skills else None
    formation_freq = _formation_frequencies(formations)

    return TacticHistory(
        matches_analysed=len(tactic_types),
        tactics=tactics,
        most_common_tactic=tactics[0] if tactics else None,
        avg_tactic_skill=avg_tactic_skill,
        formations=formation_freq,
        most_common_formation=formation_freq[0] if formation_freq else None,
    )
