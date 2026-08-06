"""HL-110 a HL-115 · Academia juvenil."""
from app.domain.engines.academy_engine import (
    Category,
    YouthSkill,
    academy_roi,
    days_until_deadline,
    evaluate,
    rank,
    training_exposure,
)


def _skills(**kw: tuple[int, int | None]) -> dict[str, YouthSkill]:
    return {k: YouthSkill(current=v[0], maximum=v[1]) for k, v in kw.items()}


def test_deadline_counts_down_to_nineteen() -> None:
    assert days_until_deadline(17, 0) == 224
    assert days_until_deadline(18, 100) == 12
    assert days_until_deadline(19, 0) == 0
    assert days_until_deadline(20, 50) == 0        # nunca negativo


def test_star_prospect_is_detected() -> None:
    e = evaluate("Crack", 16, 30, _skills(
        scoring=(8, 14), passing=(6, 11), playmaking=(5, 10), winger=(4, 8),
    ))
    assert e.category is Category.STAR
    assert e.best_skill == "scoring"
    assert e.best_skill_max == 14


def test_plumber_is_detected() -> None:
    e = evaluate("Fontanero", 17, 0, _skills(
        defending=(2, 3), passing=(1, 2), scoring=(1, 3),
    ))
    assert e.category is Category.PLUMBER
    assert "despídelo" in e.promote_advice


def test_urgent_deadline_overrides_other_advice() -> None:
    e = evaluate("Al límite", 18, 100, _skills(scoring=(9, 14)))
    assert "URGENTE" in e.promote_advice
    assert e.days_until_deadline == 12


def test_unrevealed_skills_are_flagged() -> None:
    e = evaluate("Sin revelar", 16, 0, _skills(
        scoring=(5, None), passing=(4, None), defending=(3, None),
    ))
    assert e.revealed_skills == 0
    assert "techo real" in e.promote_advice


def test_ranking_orders_by_potential() -> None:
    a = evaluate("A", 16, 0, _skills(scoring=(8, 14)))
    b = evaluate("B", 16, 0, _skills(scoring=(3, 5)))
    c = evaluate("C", 16, 0, _skills(scoring=(6, 10)))
    r = rank([b, a, c])
    assert [x.name for x in r] == ["A", "C", "B"]


def test_ready_to_promote_at_seventeen() -> None:
    e = evaluate("Listo", 17, 50, _skills(
        playmaking=(9, 11), passing=(7, 9), defending=(6, 8),
    ))
    assert "promocionar" in e.promote_advice


def test_academy_roi_with_the_real_numbers() -> None:
    """Caso real: 20.000/semana desde la temporada 47, sin ventas registradas."""
    r = academy_roi(weekly_investment=20_000, weeks_invested=562, sales_income=0)
    assert r.invested == 11_240_000
    assert r.net == -11_240_000
    assert "pérdidas" in r.verdict
    assert r.seasons == 35


def test_academy_roi_computes_sales_needed_to_break_even() -> None:
    r = academy_roi(20_000, 100, sales_income=500_000, average_sale_price=300_000)
    assert r.net == -1_500_000
    assert r.break_even_sales == 5
    assert "5 venta" in r.verdict


def test_profitable_academy() -> None:
    r = academy_roi(20_000, 100, sales_income=5_000_000)
    assert r.net > 0
    assert "rentable" in r.verdict


def test_closed_academy_reports_nothing_invested() -> None:
    r = academy_roi(0, 0, 0)
    assert "cerrada" in r.verdict


def test_training_exposure_uses_hattrick_control_weights() -> None:
    # 90 minutos en posición principal, partido oficial, entrenamiento principal
    assert training_exposure(90, 0, True, True) == 1.0
    # Amistoso: la mitad
    assert training_exposure(90, 0, False, True) == 0.5
    # Entrenamiento secundario: 0,8
    assert training_exposure(90, 0, True, False) == 0.8
    # Posición secundaria: la mitad de minutos efectivos
    assert training_exposure(0, 90, True, True) == 0.5
    assert training_exposure(0, 0, True, True) == 0.0
