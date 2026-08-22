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
    #: Los once de mas TSI. El resto de la plantilla no juega los partidos.
    top11_tsi: int
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
    # Dos semanas cerradas, no una. En Hattrick los partidos en casa se
    # alternan, asi que una sola semana sale eufórica o deprimida segun cual
    # toque; dos cubren siempre una taquilla y el numero deja de saltar.
    biweekly_balance: int = 0
    biweekly_income: int = 0
    biweekly_salaries: int = 0
    #: Salarios como parte de los ingresos, transferencias incluidas.
    salary_share_pct: float = 0.0
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
    # Cuánto del entrenamiento máximo posible está recibiendo el club: 100% es
    # entrenador 5/5, dos asistentes de nivel 5 y toda la intensidad en la
    # habilidad. Sale de los mismos coeficientes que la proyección.
    efficiency_pct: float = 0.0
    coach_level: int = 0
    assistant_level_sum: int = 0
    # Edad media de quienes de verdad reciben este entrenamiento, que es lo que
    # decide si la carga está bien dirigida: entrenar Anotación con delanteros
    # de 33 años rinde la mitad que con los de 20.
    trained_avg_age: float | None = None
    trained_players: int = 0


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
