"""Análisis de partido — HL-071, HL-072, HL-073, HL-074.

Replica y supera las pestañas Calificaciones, Eventos y Resumen Eventos de
Hattrick Control. La aportación propia es la **tasa de conversión comparada**:
saber que conviertes el 33% de tus ocasiones y el rival el 51% es lo que
distingue un problema de generación de uno de definición.
"""
from dataclasses import dataclass, field

SECTORS = ("midfield", "right_def", "central_def", "left_def",
           "right_att", "central_att", "left_att")

SECTOR_LABELS = {
    "midfield": "Mediocampo", "right_def": "Defensa derecha",
    "central_def": "Defensa Central", "left_def": "Defensa izquierda",
    "right_att": "Ataque derecha", "central_att": "Ataque central",
    "left_att": "Ataque izquierda",
}

CHANCE_ZONES = ("left", "center", "right", "special", "other")

CHANCE_ZONE_LABELS = {
    "left": "Izquierda", "center": "Centro", "right": "Derecha",
    "special": "Jugadas especiales", "other": "Otras",
}


@dataclass
class SectorComparison:
    sector: str
    label: str
    own: int
    opponent: int

    @property
    def delta(self) -> int:
        return self.own - self.opponent

    @property
    def dominance(self) -> float:
        total = self.own + self.opponent
        return (self.own / total) if total else 0.5


@dataclass
class ChanceTally:
    """Ocasiones por zona, tal como las reporta matchdetails.xml (verificado
    en vivo: sólo trae conteos por zona, nunca un desglose de goles por
    zona) — `goals` es el total del partido/periodo, no atribuible a una
    zona concreta."""
    left: int = 0
    center: int = 0
    right: int = 0
    special: int = 0
    other: int = 0
    goals: int = 0

    @property
    def total(self) -> int:
        return self.left + self.center + self.right + self.special + self.other

    @property
    def conversion(self) -> float:
        return self.goals / self.total if self.total else 0.0


@dataclass
class MatchAnalysis:
    sectors: list[SectorComparison]
    own_chances: ChanceTally
    opponent_chances: ChanceTally
    possession: tuple[int, int]
    hatstats_own: int
    hatstats_opponent: int
    loddar_own: float
    loddar_opponent: float
    verdict: str = ""
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


def hatstats(ratings: dict[str, int]) -> int:
    """Índice HatStats: mediocampo pesa triple. Fórmula estándar de la comunidad."""
    mid = ratings.get("midfield", 0) * 3
    defence = sum(ratings.get(s, 0) for s in ("right_def", "central_def", "left_def"))
    attack = sum(ratings.get(s, 0) for s in ("right_att", "central_att", "left_att"))
    return mid + defence + attack


def loddar_stats(ratings: dict[str, int]) -> float:
    """Índice LoddarStats: pondera mediocampo y equilibra ataque y defensa."""
    def sub(v: int) -> float:
        return max(v - 1, 0) / 4.0 + 1.0

    mid = sub(ratings.get("midfield", 0))
    d = sum(sub(ratings.get(s, 0)) for s in ("right_def", "central_def", "left_def")) / 3
    a = sum(sub(ratings.get(s, 0)) for s in ("right_att", "central_att", "left_att")) / 3
    return round(mid * 3 * (0.5 * d + 0.5 * a), 2)


def analyse(
    own_ratings: dict[str, int],
    opponent_ratings: dict[str, int],
    own_chances: ChanceTally,
    opponent_chances: ChanceTally,
    possession: tuple[int, int] = (50, 50),
) -> MatchAnalysis:
    sectors = [
        SectorComparison(s, SECTOR_LABELS[s], own_ratings.get(s, 0), opponent_ratings.get(s, 0))
        for s in SECTORS
    ]

    strengths = [s.label for s in sectors if s.delta >= 10]
    weaknesses = [s.label for s in sectors if s.delta <= -10]

    own_conv, opp_conv = own_chances.conversion, opponent_chances.conversion
    if own_chances.total and opponent_chances.total:
        if own_chances.total >= opponent_chances.total and own_conv < opp_conv:
            verdict = "generas ocasiones pero no las conviertes: el problema es la definición"
        elif own_chances.total < opponent_chances.total and own_conv >= opp_conv:
            verdict = "eres eficaz, pero llegas poco: el problema es la generación"
        elif own_chances.total < opponent_chances.total:
            verdict = "inferior en generación y en definición"
        else:
            verdict = "dominas en ocasiones y en eficacia"
    else:
        verdict = "sin ocasiones suficientes para valorar"

    return MatchAnalysis(
        sectors=sectors,
        own_chances=own_chances,
        opponent_chances=opponent_chances,
        possession=possession,
        hatstats_own=hatstats(own_ratings),
        hatstats_opponent=hatstats(opponent_ratings),
        loddar_own=loddar_stats(own_ratings),
        loddar_opponent=loddar_stats(opponent_ratings),
        verdict=verdict,
        strengths=strengths,
        weaknesses=weaknesses,
    )


def aggregate_conversion(matches: list[tuple[ChanceTally, ChanceTally]]) -> dict[str, float | int]:
    """Tasas y ocasiones por zona acumuladas, propias y del rival.

    Sólo se puede dar una tasa de conversión GLOBAL (goles ÷ ocasiones
    totales): matchdetails.xml no atribuye goles a una zona concreta, así
    que un "own_special_conversion" no sería un dato real.
    """
    own = ChanceTally()
    opp = ChanceTally()
    for o, p in matches:
        for tally, src in ((own, o), (opp, p)):
            for zone in CHANCE_ZONES:
                setattr(tally, zone, getattr(tally, zone) + getattr(src, zone))
            tally.goals += src.goals
    result: dict[str, float | int] = {
        "ownConversion": round(own.conversion, 4),
        "opponentConversion": round(opp.conversion, 4),
        "ownChances": own.total,
        "opponentChances": opp.total,
        "ownGoals": own.goals,
        "opponentGoals": opp.goals,
    }
    for zone in CHANCE_ZONES:
        result[f"own{zone.capitalize()}"] = getattr(own, zone)
        result[f"opponent{zone.capitalize()}"] = getattr(opp, zone)
    return result
