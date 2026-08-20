"""DTOs de plantilla y ratings de posición. HL-021, HL-022."""
from app.application.dto.dashboard import Base


class PositionRatingDTO(Base):
    position: str
    label: str
    rating: float
    # Índice de aporte del Manual no Escrito; el nombre `rating` se conserva
    # para compatibilidad del contrato API.
    confidence: str


class SquadPlayer(Base):
    ht_player_id: int
    name: str
    age_years: int
    age_days: int
    tsi: int
    form: int
    stamina: int
    experience: int
    salary: int
    specialty: str
    injury_level: int
    is_transfer_listed: bool
    loyalty: int
    leadership: int
    # HL-15x: nivel crudo (0-5, para ordenar/CSV — son escalas, no
    # categorías) + palabra traducida con el translations.xml oficial de
    # CHPP (docs/chpp-reference/Traslation_ESP.txt) para mostrar.
    agreeability: int
    agreeability_label: str
    aggressiveness: int
    aggressiveness_label: str
    honesty: int
    honesty_label: str
    country_id: int
    country_code: str | None
    league_goals: int
    cup_goals: int
    friendlies_goals: int
    career_goals: int
    career_hattricks: int
    career_assists: int
    player_trainer_skill_level: int
    player_trainer_type: int
    mother_club_bonus: bool
    mother_club_team_name: str | None
    native_league_name: str | None
    confirmed_career_stage: str | None
    confirmed_career_stage_at: str | None
    purchase_price: int | None
    purchased_at: str | None
    last_match_position: str | None
    last_match_rating: float | None
    last_match_played_minutes: int | None
    # 2026-08-05: totales de carrera con la selección nacional
    # (Caps/CapsU20 de playerdetails.xml). None = todavía no se ha pedido
    # playerdetails.xml para este jugador, distinto de 0 caps reales.
    career_caps: int | None
    career_caps_u20: int | None
    skills: dict[str, int]
    # Diferencias contra el snapshot elegido. Se calculan en el servidor a
    # partir de player_snapshots; la tabla no interpreta textos de novedades.
    deltas: dict[str, int] = {}
    best_position: PositionRatingDTO
    position_rating: PositionRatingDTO | None = None


class SquadHistoryEntry(Base):
    sync_id: int
    captured_at: str
    snapshots: int


class SquadTotals(Base):
    average_age: float
    average_form: float
    average_experience: float
    average_tsi: int
    total_tsi: int
    average_salary: int
    total_salary: int


class SquadComparison(Base):
    mode: str
    baseline_sync_id: int | None = None
    baseline_captured_at: str | None = None


class SquadResponse(Base):
    team_id: int
    team_name: str
    currency: str
    position: str | None
    player_count: int
    totals: SquadTotals
    comparison: SquadComparison
    history: list[SquadHistoryEntry] = []
    players: list[SquadPlayer]
