"""Aporte real de cada categoría de empleado — tablas oficiales de Hattrick
pasadas explícitamente por el usuario 2026-08-12. Cada test aquí reproduce
un ejemplo LITERAL del texto oficial, no un número inventado.
"""
from app.domain.engines.staff_effects import (
    STAFF_FIELD_TO_EFFECT_FN,
    assistant_trainer_effect,
    current_injury_risk_pct,
    doctor_effect,
    financial_director_effect,
    form_coach_effect,
    sport_psychologist_effect,
    tactical_assistant_effect,
)


def test_assistant_trainer_matches_the_official_worked_example() -> None:
    """"Combinación de entrenadores asistentes de nivel 10: 6 semanas" — el
    propio texto dice que sin asistente son 8 semanas y con el combo de
    nivel 5 (un solo empleado) son 7. Aquí se confirma que el módulo reutiliza
    el aporte de 0,032/nivel de la fórmula comunitaria en
    training_engine.py, en vez de mantener una copia que pueda desincronizarse.
    """
    single_five = assistant_trainer_effect(5)
    combo_ten = assistant_trainer_effect(10)
    assert single_five["trainingSpeedPct"] == 16.0   # 5 × 3,2 puntos
    assert combo_ten["trainingSpeedPct"] == 32.0     # 10 × 3,2 puntos


def test_assistant_trainer_injury_risk_and_form_match_the_table() -> None:
    combo_ten = assistant_trainer_effect(10)
    assert combo_ten["injuryRiskPp"] == 25.0     # tabla: nivel 5 = +12.5pp -> x2 = 25
    assert combo_ten["backgroundForm"] == 0.5    # "el máximo de 10 niveles... +0.5"

    level_one = assistant_trainer_effect(1)
    assert level_one["injuryRiskPp"] == 2.5
    assert level_one["backgroundForm"] == 0.05


def test_doctor_matches_the_table() -> None:
    level_five = doctor_effect(5)
    assert level_five["recoverySpeedPct"] == 100.0
    assert level_five["injuryRiskReductionPp"] == 37.5

    level_one = doctor_effect(1)
    assert level_one["recoverySpeedPct"] == 20.0
    assert level_one["injuryRiskReductionPp"] == 7.5


def test_combined_injury_risk_matches_the_two_official_worked_examples() -> None:
    """"2 entrenadores asistentes de nivel 5 dejan tu riesgo de lesiones en
    0.65 lesiones por partido... que sería 0.275 con un doctor de nivel 5"."""
    without_doctor = current_injury_risk_pct(assistant_combined_level=10, doctor_level=0)
    with_doctor = current_injury_risk_pct(assistant_combined_level=10, doctor_level=5)
    assert without_doctor == 65.0
    assert with_doctor == 27.5

    # "un entrenador asistente de nivel 5 incrementa tu riesgo base hasta
    # 0.525... (que sería 0.15 si, además, tienes un doctor de nivel 5)"
    single_assistant = current_injury_risk_pct(assistant_combined_level=5, doctor_level=0)
    single_assistant_with_doctor = current_injury_risk_pct(assistant_combined_level=5, doctor_level=5)
    assert single_assistant == 52.5
    assert single_assistant_with_doctor == 15.0


def test_sport_psychologist_matches_the_table() -> None:
    level_five = sport_psychologist_effect(5)
    assert level_five["teamSpirit"] == 0.5
    assert level_five["confidence"] == 1.12

    level_three = sport_psychologist_effect(3)
    assert level_three["teamSpirit"] == 0.3
    assert level_three["confidence"] == 0.70


def test_form_coach_matches_the_table() -> None:
    assert form_coach_effect(5)["backgroundForm"] == 1.0
    assert form_coach_effect(1)["backgroundForm"] == 0.2


def test_financial_director_matches_the_worked_example() -> None:
    """"Equipo Fantástico" contrata un director financiero de nivel 3...
    21.000.000 US$... 600.000 US$"."""
    level_three = financial_director_effect(3)
    assert level_three["maxFunds"] == 21_000_000
    assert level_three["weeklyReturn"] == 600_000

    level_zero = financial_director_effect(0)
    assert level_zero["maxFunds"] == 15_000_000
    assert level_zero["weeklyReturn"] == 100_000


def test_tactical_assistant_matches_the_table() -> None:
    level_five = tactical_assistant_effect(5)
    assert level_five["extraOrders"] == 5
    assert level_five["styleFlexibilityPp"] == 100

    level_two = tactical_assistant_effect(2)
    assert level_two["extraOrders"] == 2
    assert level_two["styleFlexibilityPp"] == 40


def test_no_bonus_at_level_zero_for_every_role_except_financial_director() -> None:
    """Director financiero es distinto: nivel 0 no es "sin empleado" en el
    sentido de "sin efecto" — la junta YA da un mínimo (15M/100k) sin
    contratar a nadie, tal como dice la propia tabla oficial."""
    for key, fn in STAFF_FIELD_TO_EFFECT_FN.items():
        if key == "financial_director_levels":
            continue
        effect = fn(0)
        assert all(v == 0 for v in effect.values())

    base = financial_director_effect(0)
    assert base["maxFunds"] == 15_000_000
    assert base["weeklyReturn"] == 100_000


def test_spokesperson_has_no_effect_function() -> None:
    """Portavoz no está entre las categorías vigentes que documentó el
    usuario — sin tabla real, no se inventa un aporte."""
    assert "spokesperson_levels" not in STAFF_FIELD_TO_EFFECT_FN


# ── El catálogo de puestos ───────────────────────────────────────────────────

def test_only_the_staff_roles_that_exist_in_hattrick_are_listed() -> None:
    """2026-08-17: la app enseñaba siete puestos y uno no existe.

    "Portavoz" venía del club.xml antiguo, que todavía declara un
    `SpokespersonLevels`, no de la página de Empleados de Hattrick — la misma
    de la que salieron las tablas de este módulo, que lista seis. Se delataba
    solo: era el único puesto sin efecto que calcular.
    """
    from app.domain.value_objects.ht_constants import STAFF_ROLES

    campos = {field for field, _, _ in STAFF_ROLES.values()}
    assert len(STAFF_ROLES) == 6
    assert "spokesperson_levels" not in campos

    # La regla que lo detectó, convertida en red: un puesto sin efecto es un
    # puesto que no existe, y un efecto sin puesto es código muerto.
    assert campos == set(STAFF_FIELD_TO_EFFECT_FN)


def test_an_unknown_staff_type_is_named_as_unknown_not_as_another_role() -> None:
    """El código 3 quedó libre al quitar Portavoz. Si CHPP mandara un empleado
    con ese tipo —o con uno nuevo que esta versión no conozca— hay que decir
    que no se sabe, nunca disfrazarlo con el nombre del puesto de al lado."""
    from app.domain.value_objects.ht_constants import staff_type_name

    assert staff_type_name(2) == "Doctor"
    assert "desconocido" in staff_type_name(3).lower()
    assert "desconocido" in staff_type_name(99).lower()


def test_role_names_follow_hattrick_wording() -> None:
    """Los nombres son los de Hattrick, no los del XML viejo: el campo interno
    sigue llamándose `medic_levels` por compatibilidad con la base, pero en
    pantalla se lee "Doctor"."""
    from app.domain.value_objects.ht_constants import STAFF_ROLES

    por_campo = {field: singular for field, singular, _ in STAFF_ROLES.values()}
    assert por_campo["medic_levels"] == "Doctor"
    assert por_campo["form_coach_levels"] == "Preparador físico"
