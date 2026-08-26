"""Value objects del dominio Hattrick. Sin dependencias externas."""

from dataclasses import dataclass
from enum import IntEnum


class SkillType(IntEnum):
    KEEPER = 1
    DEFENDING = 2
    PLAYMAKING = 3
    WINGER = 4
    PASSING = 5
    SCORING = 6
    SET_PIECES = 7


@dataclass(frozen=True, slots=True)
class Skill:
    """Nivel de skill HT (0=non-existent … 20=divine, >20 divine+N)."""

    type: SkillType
    level: int
    sub_level: float = 0.0  # estimación [0,1) hacia el próximo pop
    sub_level_stddev: float = 0.29  # incertidumbre (uniforme por defecto)

    def __post_init__(self) -> None:
        if self.level < 0:
            raise ValueError("skill level must be >= 0")
        if not 0.0 <= self.sub_level < 1.0:
            raise ValueError("sub_level must be in [0, 1)")

    @property
    def effective(self) -> float:
        return self.level + self.sub_level


@dataclass(frozen=True, slots=True)
class Age:
    """Edad Hattrick: años + días (0-111)."""

    years: int
    days: int

    DAYS_PER_YEAR = 112

    def __post_init__(self) -> None:
        if not 0 <= self.days < self.DAYS_PER_YEAR:
            raise ValueError("days must be in [0, 112)")

    @property
    def as_float(self) -> float:
        return self.years + self.days / self.DAYS_PER_YEAR

    def add_weeks(self, weeks: int) -> "Age":
        return self.add_days(weeks * 7)

    def add_days(self, days: int) -> "Age":
        """`days` negativo retrocede en el tiempo — HL-161: reconstruir la
        edad en una fecha pasada a partir de la edad de hoy, ya que la edad
        es una función pura del tiempo transcurrido (sin entrenamiento ni
        azar de por medio, a diferencia de las habilidades)."""
        total = self.years * self.DAYS_PER_YEAR + self.days + days
        if total < 0:
            raise ValueError("edad resultante negativa, el jugador no existía en esa fecha")
        return Age(total // self.DAYS_PER_YEAR, total % self.DAYS_PER_YEAR)
