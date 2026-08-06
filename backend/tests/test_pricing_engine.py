"""HL-101, HL-036, HL-107 · Valoración, ROI de entrenamiento y arrepentimiento."""
import pytest

from app.domain.engines.pricing_engine import (
    estimate_salary,
    optimal_sell_window,
    regret_index,
    training_roi,
    value_player,
)

JOVEN = {"defending": 10, "playmaking": 3, "passing": 7, "winger": 8, "scoring": 2}
VETERANO = {"scoring": 18, "passing": 13, "playmaking": 7, "winger": 4, "defending": 4}


def test_price_grows_with_skill() -> None:
    bajo = value_player({"scoring": 8}, 22).expected_price
    alto = value_player({"scoring": 12}, 22).expected_price
    assert alto > bajo * 2      # la curva de valor es fuertemente convexa


def test_price_falls_with_age() -> None:
    joven = value_player(VETERANO, 22).expected_price
    viejo = value_player(VETERANO, 31).expected_price
    assert viejo < joven / 2


def test_band_contains_the_estimate() -> None:
    v = value_player(VETERANO, 26)
    assert v.low < v.expected_price < v.high
    assert v.confidence == "assumed"     # honestidad: no está verificado


def test_currency_conversion_applies() -> None:
    base = value_player(VETERANO, 25, currency_rate=1.0).expected_price
    local = value_player(VETERANO, 25, currency_rate=10.0).expected_price
    assert local == pytest.approx(base / 10, rel=0.01)


def test_specialty_and_form_add_premium() -> None:
    plano = value_player(JOVEN, 21, form=4, specialty=0).expected_price
    premium = value_player(JOVEN, 21, form=8, specialty=2).expected_price
    assert premium > plano


def test_age_factor_keeps_decaying_past_the_table() -> None:
    """Más allá del último año de la tabla (35), el valor debe seguir cayendo
    de forma monótona. Un fallback constante recalculado cada año producía un
    diente de sierra: el valor subía en cada cumpleaños en vez de seguir
    bajando, lo que hacía parecer rentable esperar solo por el efecto del
    redondeo de edad."""
    prices = [value_player(VETERANO, years, 0).expected_price for years in range(35, 46)]
    assert prices == sorted(prices, reverse=True)
    assert prices[-1] > 0  # nunca llega a cero


def test_old_player_should_sell_now() -> None:
    w = optimal_sell_window(VETERANO, 31, 0, weeks_to_next_pop=None, trained_skill=None)
    assert w.best_week == 0
    assert "ahora" in w.verdict


def test_young_trained_player_gains_by_waiting() -> None:
    w = optimal_sell_window(
        JOVEN, 20, 0, weeks_to_next_pop=7.5, trained_skill="defending", horizon_weeks=60
    )
    assert w.best_week > 0
    assert w.peak_price > w.price_now


def test_training_roi_reports_value_per_level() -> None:
    rois = training_roi(JOVEN, "defending", 20, 0, weeks_per_level=7.5, levels=3)
    assert len(rois) == 3
    assert all(r.value_per_week > 0 for r in rois)
    assert rois[0].from_level == 10 and rois[0].to_level == 11


def test_regret_index_flags_cheap_sales() -> None:
    ventas = [
        # Vale ~106.000 hoy y lo soltaste por 20.000
        {"name": "Vendido barato", "sold_for": 20_000, "skills": {"scoring": 14},
         "age_years": 22},
        # Cobraste 5 M por alguien que hoy no vale nada
        {"name": "Buena venta", "sold_for": 5_000_000, "skills": {"scoring": 6},
         "age_years": 33},
        {"name": "Precio justo", "sold_for": 106_000, "skills": {"scoring": 14},
         "age_years": 22},
    ]
    r = regret_index(ventas, currency_rate=10.0)
    por_nombre = {x.player: x for x in r}
    assert por_nombre["Vendido barato"].verdict == "vendiste barato"
    assert por_nombre["Buena venta"].verdict == "buena venta: hoy vale menos"
    assert por_nombre["Precio justo"].verdict == "precio justo"
    # Ordenado de mayor a menor arrepentimiento
    assert r[0].player == "Vendido barato"


def test_estimate_salary_matches_the_published_table_for_a_single_skill() -> None:
    """Manual no Escrito, tabla de sueldos: Defensa Bueno (nivel 7) ~ $330,
    Defensa Excelente (nivel 8) ~ $450, con el resto de habilidades en 0."""
    bueno = estimate_salary({"defending": 7})
    assert bueno.weekly_salary == pytest.approx(330, abs=15)
    assert bueno.main_skill == "defending"

    excelente = estimate_salary({"defending": 8})
    assert excelente.weekly_salary == pytest.approx(450, abs=15)
    assert excelente.weekly_salary > bueno.weekly_salary


def test_estimate_salary_picks_the_skill_with_the_highest_component_as_main() -> None:
    """La habilidad principal es la que paga más, no la de nivel más alto —
    Lateral 12 paga menos que Jugadas 12 según la tabla del manual."""
    est = estimate_salary({"winger": 12, "playmaking": 12})
    assert est.main_skill == "playmaking"


def test_estimate_salary_set_pieces_bonus_increases_salary() -> None:
    base = estimate_salary({"scoring": 10})
    with_pp = estimate_salary({"scoring": 10}, set_pieces=15)
    assert with_pp.weekly_salary > base.weekly_salary


def test_estimate_salary_with_no_skills_is_just_the_base() -> None:
    est = estimate_salary({})
    assert est.weekly_salary == 250
