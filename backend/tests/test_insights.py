"""HL-130 y familia · Motor de alertas accionables."""
import re
from pathlib import Path

from app.domain.engines import insights as ins
from app.domain.engines.insights import (
    Severity,
    academy_roi,
    ageing_squad,
    arena_expansion_opportunity,
    assistant_trainers_below_reference,
    cash_vs_expected_mismatch,
    collect,
    fan_club_trend,
    income_concentration,
    inefficient_training,
    injuries,
    low_form,
    missing_medic_or_psych,
    next_match_forecast,
    relegation_danger,
    sector_standouts,
    stale_data,
    structural_deficit,
    thin_keeper_depth,
    title_race,
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


def test_structural_deficit_uses_real_numbers() -> None:
    out = structural_deficit(-217_000, 21_034_174, "US$")
    assert out and out[0].severity is Severity.WARNING
    assert "96" in out[0].detail or "97" in out[0].detail   # ~96 semanas de margen


def test_deficit_becomes_danger_when_runway_is_short() -> None:
    out = structural_deficit(-500_000, 2_000_000)
    assert out[0].severity is Severity.DANGER


def test_positive_balance_produces_no_alert() -> None:
    assert structural_deficit(50_000, 1_000_000) == []


# `test_sold_out_sectors_flag_censored_demand` se retiro el 2026-09-01 con la
# alerta que probaba: avisaba de sectores agotados y de la demanda que no cabia,
# y eso exige la asistencia POR SECTOR, que es funcion de HT Supporter.

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
        {"ht_player_id": 1, "name": "A", "age_years": 33, "injury_level": 2, "tsi": 900},
        {"ht_player_id": 2, "name": "B", "age_years": 32, "injury_level": -1, "tsi": 800},
        {"ht_player_id": 3, "name": "C", "age_years": 34, "injury_level": -1, "tsi": 700},
    ]
    assert injuries(squad)[0].severity is Severity.WARNING
    assert ageing_squad(squad)[0].severity is Severity.INFO


def test_ageing_only_looks_at_the_top_tsi_core() -> None:
    """2026-08-16, redefinida por el usuario: 3+ de 32 años entre los 11 de
    más TSI. Que envejezcan los suplentes no obliga a nada; que envejezca el
    once que juega, sí — antes bastaban tres treintañeros en cualquier parte
    del plantel y eso se cumplía casi siempre."""
    core = [
        {"ht_player_id": i, "name": f"Joven {i}", "age_years": 24, "tsi": 10_000 - i}
        for i in range(11)
    ]
    viejos_suplentes = [
        {"ht_player_id": 100 + i, "name": f"Veterano {i}", "age_years": 35, "tsi": 10}
        for i in range(4)
    ]
    assert ageing_squad(core + viejos_suplentes) == []

    core[0]["age_years"] = 32
    core[1]["age_years"] = 33
    assert ageing_squad(core + viejos_suplentes) == []  # solo dos, no llega a tres
    core[2]["age_years"] = 32
    out = ageing_squad(core + viejos_suplentes)
    assert out and "3 de tus 11" in out[0].title


def test_a_bruised_player_is_not_an_injury() -> None:
    """`InjuryLevel` 0 es magullado y puede jugar: no es una baja, así que no
    genera aviso. Solo desde 1 (semanas fuera) cuenta como lesión."""
    magullado = [{"ht_player_id": 1, "name": "Magullado", "injury_level": 0}]
    assert injuries(magullado) == []
    lesionado = [{"ht_player_id": 1, "name": "Lesionado", "injury_level": 1}]
    assert len(injuries(lesionado)) == 1


def test_each_injured_player_gets_his_own_alert() -> None:
    """Agrupadas en una sola, archivar la del primer lesionado tapaba al
    segundo. Una clave por jugador."""
    out = injuries([
        {"ht_player_id": 1, "name": "Uno", "injury_level": 2},
        {"ht_player_id": 2, "name": "Dos", "injury_level": 3},
    ])
    assert [i.key for i in out] == ["player.injured.1", "player.injured.2"]


def test_collect_orders_by_urgency() -> None:
    todo = collect(
        stale_data(48),
        structural_deficit(-500_000, 1_000_000),
        injuries([{"ht_player_id": 9, "name": "X", "age_years": 25, "injury_level": 1}]),
    )
    severidades = [i.severity for i in todo]
    assert severidades[0] is Severity.DANGER
    assert severidades[-1] is Severity.INFO


def test_every_insight_has_a_message_and_module() -> None:
    todo = collect(
        inefficient_training(TRAINEES),
        structural_deficit(-217_000, 21_034_174),
        academy_roi(11_240_000, 0),
    )
    assert todo
    for i in todo:
        assert i.title and i.detail and i.module


# ── Plantilla, jugador a jugador ────────────────────────────────────────────

def test_low_form_flags_up_to_the_configured_threshold() -> None:
    """2026-08-16, umbral fijado por el usuario en 4: una forma de 4 entra y
    una de 5 se queda fuera."""
    out = low_form([
        {"ht_player_id": 1, "name": "Malo", "form": 1},
        {"ht_player_id": 2, "name": "Justo", "form": 4},
        {"ht_player_id": 3, "name": "Bien", "form": 5},
    ])
    assert [i.evidence["player"] for i in out] == ["Malo", "Justo"]
    assert all(i.severity is Severity.WARNING for i in out)


def test_wage_concentration_flags_a_single_heavy_salary() -> None:
    players = [
        {"ht_player_id": 1, "name": "Estrella", "salary_local": 20_000},
        {"ht_player_id": 2, "name": "Resto", "salary_local": 3_000},
    ]
    out = wage_concentration(players, total_salary=100_000, currency="US$")
    assert len(out) == 1 and "Estrella" in out[0].title


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


def test_cash_vs_expected_mismatch_only_looks_down() -> None:
    """2026-08-16: tener MÁS caja de la esperada no pide nada, así que la rama
    "vas por encima" se eliminó. Solo queda el faltante."""
    peor = cash_vs_expected_mismatch(1_000_000, 2_000_000, "US$")
    assert peor[0].severity is Severity.WARNING
    assert cash_vs_expected_mismatch(2_000_000, 1_000_000, "US$") == []
    assert cash_vs_expected_mismatch(1_000_000, 1_100_000, "US$") == []


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


def test_el_titulo_es_una_sola_alerta_con_todo_dentro() -> None:
    """Una alerta, no dos. `promotion_probability` y `title_probability` son
    el mismo número, así que separarlas producía dos avisos seguidos con la
    misma cifra (2026-08-30)."""
    lider = {
        **RELEGATION_ROW,
        "title_probability": 0.6,
        "promotion_probability": 0.6,
        "expected_points": 35.5,
        "relegation_probability": 0.0,
    }
    out = title_race(lider)
    assert len(out) == 1
    assert out[0].severity is Severity.OPPORTUNITY
    # Nunca prometer "ascenso" sin más: el ascenso real depende del ranking
    # nacional de campeones, que el motor no modela (ver season_simulator.py).
    assert "ascender" not in out[0].title.lower()
    # Lo que aportaba cada una de las dos viejas sigue estando.
    assert "Posición esperada" in out[0].detail
    assert "Puntos esperados" in out[0].detail
    assert "ranking nacional" in out[0].detail


def test_en_la_division_mas_alta_no_se_habla_de_ascenso() -> None:
    campeon = {
        **RELEGATION_ROW,
        "title_probability": 0.6,
        "promotion_probability": 0.0,
        "relegation_probability": 0.0,
    }
    out = title_race(campeon)
    assert out and "ranking nacional" not in out[0].detail


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


# ── El catálogo de claves ────────────────────────────────────────────────────

def test_known_key_roots_matches_the_keys_the_module_really_emits() -> None:
    """`KNOWN_KEY_ROOTS` es lo que deja al buzón distinguir una archivada viva
    de una huérfana, así que una lista desfasada volvería a llenarlo de avisos
    que nunca pueden reaparecer. En vez de confiar en la memoria, se leen las
    claves del propio fichero y se comparan.

    Las claves con sufijo (`player.injured.{id}`) se escriben como f-string, de
    modo que la raíz es todo lo que hay antes de la primera llave."""
    fuente = Path(ins.__file__).read_text(encoding="utf-8")
    literales = re.findall(r'key=\(?\s*f?"([^"]+)"', fuente)
    raices = {lit.split("{")[0].rstrip(".") for lit in literales}
    assert raices, "no se encontró ninguna clave en el módulo"
    assert raices == set(ins.KNOWN_KEY_ROOTS)


def test_an_orphaned_key_is_recognisable() -> None:
    """Reglas borradas de verdad el 2026-08-16 al aplicar los veredictos. Sus
    archivadas siguen en la base y el buzón tiene que poder tirarlas."""
    for huerfana in (
        "player.transfer_listed.483141997",  # la lista de transferibles no es una alerta
        "player.overpaid.474426586",         # se fue con salario contra mercado
        "training.pop_soon",                 # subidas de nivel próximas
        "squad.injuries",                    # ahora se avisa una por jugador
    ):
        assert not ins.is_known_key(huerfana)

    assert ins.is_known_key("player.injured.474559832")
    assert ins.is_known_key("squad.ageing")
    assert ins.is_known_key("economy.structural_deficit.83-04")


def test_structural_deficit_calla_cuando_es_el_redondeo_del_equilibrio() -> None:
    """Un déficit pequeño al lado de lo que entra no es un agujero.

    Pulgas Arrechas, 2026-09-02: -21.259 a la semana contra 538.088 de ingreso
    recurrente, o sea un 4%, y caja para 441 semanas. Antes de que la taquilla
    entrara en el balance recurrente ese mismo club salía con -435.347 y la
    alerta tenía todo el sentido; con el número bueno, avisar de esto es
    llenar el buzón de ruido.
    """
    assert (
        structural_deficit(-21_259, 9_391_047, "US$", weekly_income=538_088) == []
    )


def test_structural_deficit_avisa_aunque_haya_caja_de_sobra() -> None:
    """El tamaño manda sobre las semanas de caja: un agujero del 40% del
    ingreso recurrente no se cierra solo por tener el colchón grande."""
    out = structural_deficit(-217_000, 21_034_174, "US$", weekly_income=538_088)
    assert out and out[0].severity is Severity.WARNING
