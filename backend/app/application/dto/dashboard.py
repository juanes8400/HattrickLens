"""DTOs de salida del dashboard. camelCase hacia el cliente (docs/03)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


def _camel(s: str) -> str:
    head, *rest = s.split("_")
    return head + "".join(w.capitalize() for w in rest)


class Base(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class SquadSummary(Base):
    player_count: int
    avg_age: float
    total_tsi: int
    total_salary: int
    injured_count: int


class FinanceSummary(Base):
    cash: int
    expected_cash: int
    weekly_delta: int
    income_sum: int
    costs_sum: int
    costs_players: int
    fan_club_size: int
    last_weeks_total: int
    # Balance recurrente sin transferencias — el número que revela si la
    # operación del club es sostenible (idea tomada del "sin Otros" de HC).
    structural_balance: int = 0
    currency: str = ""


class TrainingSummary(Base):
    type_id: int
    type_name: str
    level: int
    stamina_part: int
    trainer_name: str
    morale: int
    morale_name: str
    confidence: int
    confidence_name: str


class PlayerRow(Base):
    ht_player_id: int
    name: str
    age_years: int
    age_days: int
    tsi: int
    form: int
    stamina: int
    salary: int
    injury_level: int
    skills: dict[str, int]


class Alert(Base):
    kind: str
    severity: str
    message: str


class DashboardResponse(Base):
    team_id: int
    team_name: str
    league_name: str | None = None
    series_name: str | None = None
    synced_at: datetime | None = None
    sync_id: int | None = None
    stale: bool
    squad: SquadSummary | None = None
    finance: FinanceSummary | None = None
    training: TrainingSummary | None = None
    top_salaries: list[PlayerRow] = []
    alerts: list[Alert] = []
