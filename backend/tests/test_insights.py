"""HL-130 y familia · Motor de alertas accionables."""
from app.domain.engines.insights import (
    Severity,
    academy_roi,
    ageing_squad,
    arena_expansion_opportunity,
    assistant_trainers_below_reference,
    cash_vs_expected_mismatch,
    collect,
    cup_streak_notable,
    fan_club_trend,
    high_form,
    income_concentration,
    inefficient_training,
    injuries,
    low_form,
    missing_medic_or_psych,
    next_match_forecast,
    promotion_chance,
    relegation_danger,
    salary_market_mismatch,
    sector_standouts,
    sold_out_sectors,
    sponsor_popularity_trend,
    stale_data,
    starter_injured,
    structural_deficit,
    thin_keeper_depth,
    transfer_listed,
    upcoming_pops,
    wage_concentration,
    youth_deadline,
    youth_star_prospect,
)

TRAINEES = [
    {"name": "Raúl Cobos", "age_years": 28, "weeks_to_pop": 11.7},
    {"name": "Klaus Bahlek", "age_years": 27, "weeks_to_pop": 10.8},
    {"name": "Florin Tilvar", "age_years": 20, "weeks_to_pop": 7.5},
    {"name": "Aydin Davey", "age_years": 22, "weeks_to_pop": 3.2},
]


def test_detects_expensive_training_real_case() -> None:
    out = inefficient_training(TRAINEES)
    assert len(out) == 1
    assert out[0].severity is Severity.WARNING
    assert "Cobos" in out[0].detail
    assert out[0].action                       # toda alerta lleva acción


def test_no_warning_when_training_the_young() -> None:
    assert inefficient_training(TRAINEES[2:]) == []


def test_upcoming_pops_are_opportunities() -> None:
    out = upcoming_pops(TRAINEES, weeks_ahead=4)
    assert out and out[0].severity is Severity.OPPORTUNITY
    assert "Davey" in out[0].detail


def test_structural_deficit_uses_real_numbers() -> None:
    out = structural_deficit(-217_000, 21_034_174, "US$")
    assert out and out[0].severity is Severity.WARNING
    assert "96" in out[0].detail or "97" in out[0].detail   # ~96 semanas de margen


def test_deficit_becomes_danger_when_runway_is_short() -> None:
    out = structural_deficit(-500_000, 2_000_000)
    assert out[0].severity is Severity.DANGER


def test_positive_balance_produces_no_alert() -> None:
    assert structural_deficit(50_000, 1_000_000) == []


def test_sold_out_sectors_flag_censored_demand() -> None:
    out = sold_out_sectors(["general", "preferentes", "palcos"], 95_437, "US$")
    assert out and out[0].severity is Severity.OPPORTUNITY
    assert "95,437" in out[0].detail


def test_academy_roi_both_directions() -> None:
    malo = academy_roi(11_240_000, 0, "US$")
    assert malo[0].severity is Severity.WARNING
    bueno = academy_roi(1_000_000, 3_000_000)
    assert bueno[0].severity is Severity.INFO


def test_youth_deadline_is_danger() -> None:
    out = youth_deadline([{"name": "Juvenil", "days_until_deadline": 5}])
    assert out[0].severity is Severity.DANGER
    assert "5 días" in out[0].detail


def test_injuries_and_ageing() -> None:
    squad = [
        {"name": "A", "age_years": 31, "injury_level": 2},
        {"name": "B", "age_years": 30, "injury_level": -1},
        {"name": "C", "age_years": 33, "injury_level": -1},
    ]
    assert injuries(squad)[0].severity is Severity.WARNING
    assert ageing_squad(squad)[0].severity is Severity.INFO


def test_collect_orders_by_urgency() -> None:
    todo = collect(
        stale_data(48),
        structural_deficit(-500_000, 1_000_000),
        upcoming_pops(TRAINEES),
        injuries([{"name": "X", "age_years": 25, "injury_level": 1}]),
    )
    severidades = [i.severity for i in todo]
    assert severidades[0] is Severity.DANGER
    assert severidades[-1] is Severity.INFO


def test_every_insight_has_a_message_and_module() -> None:
    todo = collect(
        inefficient_training(TRAINEES),
        structural_deficit(-217_000, 21_034_174),
        sold_out_sectors(["general"], 1000),
        academy_roi(11_240_000, 0),
    )
    assert todo
    for i in todo:
        assert i.title and i.detail and i.module


# ── Plantilla, jugador a jugador ────────────────────────────────────────────

def test_low_form_flags_horrible_or_worse() -> None:
    out = low_form([
        {"ht_player_id": 1, "name": "Malo", "form": 1},
        {"ht_player_id": 2, "name": "Bien", "form": 5},
    ])
    assert len(out) == 1
    assert out[0].severity is Severity.WARNING
    assert "Malo" in out[0].title


def test_high_form_flags_excellent_or_better() -> None:
    out = high_form([{"ht_player_id": 1, "name": "Crack", "form": 9}])
    assert out and out[0].severity is Severity.OPPORTUNITY


def test_transfer_listed_only_flags_true() -> None:
    out = transfer_listed([
        {"ht_player_id": 1, "name": "Listado", "is_transfer_listed": True},
        {"ht_player_id": 2, "name": "Normal", "is_transfer_listed": False},
    ])
    assert len(out) == 1 and "Listado" in out[0].title


def test_salary_market_mismatch_flags_both_directions() -> None:
    caro = salary_market_mismatch([
        {"ht_player_id": 1, "name": "Caro", "currency": "US$",
         "real_salary": 14_000, "estimated_salary": 5_000},
    ])
    assert caro[0].severity is Severity.WARNING and "overpaid" in caro[0].key

    barato = salary_market_mismatch([
        {"ht_player_id": 2, "name": "Ganga", "currency": "US$",
         "real_salary": 1_000, "estimated_salary": 5_000},
    ])
    assert barato[0].severity is Severity.INFO and "underpaid" in barato[0].key

    assert salary_market_mismatch([
        {"ht_player_id": 3, "name": "Justo", "currency": "US$",
         "real_salary": 5_000, "estimated_salary": 5_000},
    ]) == []


def test_wage_concentration_flags_a_single_heavy_salary() -> None:
    players = [
        {"ht_player_id": 1, "name": "Estrella", "salary_local": 20_000},
        {"ht_player_id": 2, "name": "Resto", "salary_local": 3_000},
    ]
    out = wage_concentration(players, total_salary=100_000, currency="US$")
    assert len(out) == 1 and "Estrella" in out[0].title


def test_starter_injured_only_flags_the_injured_starter() -> None:
    starters = [
        {"ht_player_id": 1, "name": "Sano", "label": "MC", "injury_level": -1},
        {"ht_player_id": 2, "name": "Tocado", "label": "DFC", "injury_level": 1},
    ]
    out = starter_injured(starters)
    assert len(out) == 1 and out[0].severity is Severity.DANGER and "Tocado" in out[0].title


def test_thin_keeper_depth_escalates_with_zero_keepers() -> None:
    ninguno = thin_keeper_depth([{"name": "A", "best_position": "forward"}])
    assert ninguno[0].severity is Severity.DANGER

    uno = thin_keeper_depth([
        {"name": "A", "best_position": "keeper"}, {"name": "B", "best_position": "forward"},
    ])
    assert uno[0].severity is Severity.WARNING

    dos = thin_keeper_depth([
        {"name": "A", "best_position": "keeper"}, {"name": "B", "best_position": "keeper"},
    ])
    assert dos == []


def test_sector_standouts_names_the_top_contributor() -> None:
    out = sector_standouts([
        {"sector": "midfield", "label": "Mediocampo", "player": "Ancker",
         "positionLabel": "MC", "amount": 12.5},
    ])
    assert out and "Ancker" in out[0].title


# ── Economía ─────────────────────────────────────────────────────────────────

def test_income_concentration_flags_a_dominant_source() -> None:
    out = income_concentration([
        ("Espectadores", 90_000), ("Patrocinadores", 5_000), ("Financieros", 5_000),
    ], currency="US$")
    assert out and "espectadores" in out[0].title.lower()


def test_cash_vs_expected_mismatch_directions() -> None:
    peor = cash_vs_expected_mismatch(1_000_000, 2_000_000, "US$")
    assert peor[0].severity is Severity.WARNING
    mejor = cash_vs_expected_mismatch(2_000_000, 1_000_000, "US$")
    assert mejor[0].severity is Severity.INFO
    assert cash_vs_expected_mismatch(1_000_000, 1_100_000, "US$") == []


def test_sponsor_popularity_trend_only_flags_a_real_drop() -> None:
    assert sponsor_popularity_trend(80, 74)
    assert sponsor_popularity_trend(80, 79) == []


def test_fan_club_trend_only_flags_a_relative_drop() -> None:
    assert fan_club_trend(1000, 900)
    assert fan_club_trend(1000, 990) == []


# ── Liga ─────────────────────────────────────────────────────────────────────

RELEGATION_ROW = {
    "name": "Pulgas Arrechas", "expected_position": 7.5, "expected_points": 12.0,
    "relegation_probability": 0.55, "relegation_playoff_probability": 0.1,
    "promotion_probability": 0.0, "title_probability": 0.0,
    "attack_strength": 0.7, "defence_strength": 1.4,
}


def test_relegation_danger_fires_above_threshold() -> None:
    out = relegation_danger(RELEGATION_ROW)
    assert out and out[0].severity is Severity.DANGER


def test_promotion_chance_fires_for_a_leader() -> None:
    lider = {**RELEGATION_ROW, "promotion_probability": 0.6, "relegation_probability": 0.0}
    out = promotion_chance(lider)
    assert out and out[0].severity is Severity.OPPORTUNITY
    # `promotion_probability` es en realidad P(terminar 1º) — nunca prometer
    # "ascenso" sin más: el ascenso real depende del ranking nacional de
    # campeones, que el motor no modela (ver season_simulator.py).
    assert "ascender" not in out[0].title.lower()
    assert "1º" in out[0].title
    assert "ranking nacional" in out[0].detail


def test_next_match_forecast_labels_favorite_and_underdog() -> None:
    favorito = next_match_forecast({
        "home": "Nosotros", "away": "Rival", "isHome": True,
        "homeWin": 0.7, "draw": 0.2, "awayWin": 0.1,
    })
    assert favorito and favorito[0].severity is Severity.OPPORTUNITY

    perdedor = next_match_forecast({
        "home": "Rival", "away": "Nosotros", "isHome": False,
        "homeWin": 0.7, "draw": 0.2, "awayWin": 0.1,
    })
    assert perdedor and perdedor[0].severity is Severity.WARNING


# ── Copa, academia, estadio, staff ───────────────────────────────────────────

def test_cup_streak_notable_reads_wins_and_losses() -> None:
    victorias = cup_streak_notable({"count": 4, "result": "V"})
    assert victorias and victorias[0].severity is Severity.OPPORTUNITY
    derrotas = cup_streak_notable({"count": 3, "result": "D"})
    assert derrotas and derrotas[0].severity is Severity.WARNING
    assert cup_streak_notable({"count": 2, "result": "V"}) == []
    assert cup_streak_notable(None) == []


def test_youth_star_prospect_needs_a_non_provisional_verdict() -> None:
    listo = youth_star_prospect([{
        "ht_youth_player_id": 1, "name": "Promesa", "category": "crack",
        "best_skill": "scoring", "best_skill_max": 14, "verdict_is_provisional": False,
        "promote_advice": "promociónalo",
    }])
    assert listo and "Promesa" in listo[0].title

    provisional = youth_star_prospect([{
        "ht_youth_player_id": 2, "name": "Duda", "category": "crack",
        "best_skill": "scoring", "best_skill_max": 14, "verdict_is_provisional": True,
        "promote_advice": "",
    }])
    assert provisional == []


def test_arena_expansion_opportunity_needs_a_reasonable_payback() -> None:
    out = arena_expansion_opportunity([
        {"label": "Chica", "netPerSeason": 50_000, "paybackSeasons": 3.0},
        {"label": "Grande", "netPerSeason": -1000, "paybackSeasons": None},
    ], currency="US$")
    assert out and "Chica" in out[0].detail


def test_missing_medic_or_psych_is_a_binary_fact() -> None:
    out = missing_medic_or_psych({"medic_levels": 0, "sport_psychologist_levels": 2})
    assert len(out) == 1 and "médico" in out[0].title.lower()


def test_assistant_trainers_below_reference() -> None:
    out = assistant_trainers_below_reference({"assistant_trainer_levels": 3})
    assert out
    assert assistant_trainers_below_reference({"assistant_trainer_levels": 10}) == []
