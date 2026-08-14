"""Loyalty Engine — Fidelidad, calibrada transición por transición.

A diferencia de Experiencia, aquí no hay ningún valor configurado de
partida: sin observaciones para una transición, simplemente no aparece en
la tabla — nunca se inventa un promedio.
"""
from app.domain.engines.loyalty_engine import (
    LoyaltyLevelUp,
    calibrate,
    model_info,
    progress_within_level,
)


def test_no_observations_yields_an_empty_table() -> None:
    cal = calibrate([])
    assert cal.transitions == {}
    assert cal.total_observations == 0
    assert cal.for_level(5) is None


def test_transitions_are_calibrated_independently_per_level() -> None:
    """1→2 rápido, 19→20 lento — cada transición es su propio número, no
    una media global que los mezclaría."""
    cal = calibrate([
        LoyaltyLevelUp("A", 1, 2, 5), LoyaltyLevelUp("B", 1, 2, 7),
        LoyaltyLevelUp("C", 19, 20, 300), LoyaltyLevelUp("D", 19, 20, 320),
    ])
    assert cal.total_observations == 4
    fast = cal.for_level(1)
    slow = cal.for_level(19)
    assert fast is not None and slow is not None
    assert fast.avg_days == 6.0
    assert fast.observations == 2
    assert slow.avg_days == 310.0
    assert slow.observations == 2
    assert slow.avg_days > fast.avg_days * 10


def test_a_single_observation_is_still_usable() -> None:
    """A diferencia de Experiencia, no hay mínimo de observaciones: una
    sola es mejor que ninguna para esa transición específica."""
    cal = calibrate([LoyaltyLevelUp("A", 5, 6, 42)])
    t = cal.for_level(5)
    assert t is not None
    assert t.avg_days == 42.0
    assert t.observations == 1
    assert t.std_dev is None  # una sola muestra no tiene desviación


def test_std_dev_only_appears_with_more_than_one_observation() -> None:
    cal = calibrate([
        LoyaltyLevelUp("A", 3, 4, 10), LoyaltyLevelUp("B", 3, 4, 20),
    ])
    t = cal.for_level(3)
    assert t is not None
    assert t.std_dev is not None and t.std_dev > 0


def test_progress_within_level_needs_both_a_start_date_and_calibration() -> None:
    cal = calibrate([LoyaltyLevelUp("A", 5, 6, 40)])

    # Sin fecha de inicio conocida, no hay forma honesta de calcular nada.
    assert progress_within_level(5, None, cal) is None

    # Con fecha pero sin calibración para ESA transición, tampoco.
    assert progress_within_level(9, 10, cal) is None

    # Con ambas, sale un decimal real dentro del nivel.
    halfway = progress_within_level(5, 20, cal)
    assert halfway == 5.5


def test_progress_within_level_caps_below_the_next_level() -> None:
    """Un jugador puede llevar más días de los que promedia la transición
    (todavía no le tocó pese a "deberle tocar") — no se muestra como si ya
    hubiera subido, eso lo confirma Hattrick, no una proyección."""
    cal = calibrate([LoyaltyLevelUp("A", 5, 6, 40)])
    overdue = progress_within_level(5, 500, cal)
    assert overdue is not None
    assert 5 < overdue < 6
    assert overdue == 5.98


def test_model_info_lists_transitions_sorted_by_level() -> None:
    cal = calibrate([
        LoyaltyLevelUp("A", 10, 11, 100),
        LoyaltyLevelUp("B", 2, 3, 8),
        LoyaltyLevelUp("C", 6, 7, 40),
    ])
    info = model_info(cal)
    levels = [t["fromLevel"] for t in info["transitions"]]
    assert levels == [2, 6, 10]
    assert info["totalObservations"] == 3
    assert info["reference"]["status"] == "pending"
