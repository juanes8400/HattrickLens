"""HL-110 a HL-115 · Academia juvenil."""
import pytest

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
    assert "no ha revelado nada" in e.promote_advice
    # 2026-08-15: sin NINGÚN techo revelado no se nombra una "mejor
    # habilidad". Antes el motor elegía la primera del diccionario usando el
    # techo asumido (8 para todas, así que empataban) y la pantalla lo
    # mostraba como si el ojeador lo hubiera dicho.
    assert e.best_skill == ""
    assert e.best_skill_max is None
    # Aun así no se le degrada a "fontanero" por ignorancia: la categoría usa
    # el techo asumido y `revealed_skills` avisa de que es provisional.
    assert e.category is not Category.PLUMBER


def test_best_skill_only_comes_from_revealed_ceilings() -> None:
    """Con un techo revelado y el resto a oscuras, la mejor habilidad es la
    revelada — aunque otra tenga un nivel actual más alto."""
    e = evaluate("Mixto", 16, 0, _skills(
        scoring=(9, None), passing=(2, 6),
    ))
    assert e.best_skill == "passing"
    assert e.best_skill_max == 6


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
    r = academy_roi(invested=11_240_000, weeks_invested=562, sales_income=0)
    assert r.invested == 11_240_000
    assert r.net == -11_240_000
    assert "pérdidas" in r.verdict
    assert r.seasons == 35


def test_academy_roi_takes_the_investment_already_summed_week_by_week() -> None:
    """2026-08-16, pedido explícitamente: el total NO se reconstruye
    multiplicando el coste semanal de hoy. Si la inversión juvenil cambió a
    mitad de camino, multiplicar reescribe el pasado con el precio actual —
    aquí 3 semanas a 10.000 y 2 a 20.000 son 70.000, no 5 × 20.000."""
    r = academy_roi(
        invested=70_000, weeks_invested=5, sales_income=0, weekly_investment=20_000
    )
    assert r.invested == 70_000
    assert r.weekly_cost == 20_000  # sólo para mostrar "X por semana"
    assert r.net == -70_000


def test_academy_roi_computes_sales_needed_to_break_even() -> None:
    r = academy_roi(2_000_000, 100, sales_income=500_000, average_sale_price=300_000)
    assert r.net == -1_500_000
    assert r.break_even_sales == 5
    assert "5 venta" in r.verdict


def test_profitable_academy() -> None:
    r = academy_roi(2_000_000, 100, sales_income=5_000_000)
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
    # Entrenamiento secundario distinto: dos tercios.
    assert training_exposure(
        90, 0, True, False, ("passing", "passing_defenders")
    ) == pytest.approx(2 / 3, abs=0.0001)
    # Si es exactamente el mismo entrenamiento, el secundario normal se
    # castiga a la mitad: 2/3 x 1/2 = 1/3.
    assert training_exposure(
        90, 0, True, False, ("passing", "passing")
    ) == pytest.approx(1 / 3, abs=0.0001)
    # Dos entrenamientos distintos que suben Pases no son una repetición.
    assert training_exposure(
        90, 0, True, False, ("passing", "passing_defenders")
    ) == pytest.approx(2 / 3, abs=0.0001)
    # Sin los códigos no se puede decidir honestamente si está repetido.
    with pytest.raises(ValueError, match="necesita los códigos"):
        training_exposure(90, 0, True, False)
    # Posición secundaria: la mitad de minutos efectivos
    assert training_exposure(0, 90, True, True) == 0.5
    assert training_exposure(0, 0, True, True) == 0.0


def test_los_cortes_estan_en_la_escala_juvenil() -> None:
    """2026-08-23: estaban en escala de primer equipo --12 para «crack»--, y
    como un techo juvenil no llega ahi, los dieciocho canteranos de la
    academia real salian «aceptable». La etiqueta no distinguia a nadie."""
    def con_techo(techo: int) -> Category:
        return evaluate("X", 16, 0, _skills(scoring=(0, techo))).category

    assert con_techo(8) is Category.STAR
    assert con_techo(7) is Category.PROSPECT
    assert con_techo(6) is Category.ACCEPTABLE
    assert con_techo(5) is Category.SELLABLE
    assert con_techo(4) is Category.PLUMBER


def test_sin_ningun_techo_revelado_no_hay_veredicto() -> None:
    """El techo asumido es 8. Si la categoria lo usara, todo canterano recien
    llegado seria «crack» — afirmar justo lo que nadie ha dicho."""
    e = evaluate("A oscuras", 16, 0, _skills(
        scoring=(5, None), passing=(4, None), defending=(3, None),
    ))
    assert e.category is Category.UNRATED
    assert e.best_skill_max is None
    # El potencial SI sigue usando el supuesto: sirve para ordenar.
    assert e.potential_score > 0


def test_un_techo_revelado_bajo_manda_sobre_el_resto_a_oscuras() -> None:
    """Lo poco que se sabe pesa mas que lo mucho que se supone."""
    e = evaluate("Uno visto", 16, 0, _skills(
        scoring=(2, 4), passing=(6, None), defending=(6, None),
    ))
    assert e.category is Category.PLUMBER


def test_no_se_recomienda_despedir_sobre_una_sola_lectura() -> None:
    """Despedir no se deshace, y lo unico revelado puede ser su peor
    habilidad por pura casualidad del ojeador."""
    e = evaluate("Un solo dato", 16, 0, _skills(
        scoring=(0, 4), passing=(0, None), defending=(0, None),
    ))
    assert e.category is Category.PLUMBER, "la categoria si sale de lo poco que hay"
    assert "despídelo" not in e.promote_advice
    assert "sigue entrenándolo" in e.promote_advice


def test_con_pruebas_suficientes_si_se_recomienda() -> None:
    e = evaluate("Visto de sobra", 16, 0, _skills(
        scoring=(0, 4), passing=(0, 3), defending=(0, 2),
    ))
    assert e.revealed_skills >= 3
    assert "despídelo" in e.promote_advice


# ── Cuando puede ascender un canterano ──────────────────────────────────────

def test_las_dos_reglas_de_ascenso_dan_lo_MISMO_que_hattrick() -> None:
    """17;000 cumplidos Y 112 dias dentro de la academia; manda la que falte mas.

    Dictada por el usuario el 2026-08-26 y comprobada contra los 18 canteranos
    de su cuenta: coinciden los DIECIOCHO con el `CanBePromotedIn` que manda
    Hattrick. Se comprueban aqui cuatro casos reales de aquellos.

    La pantalla no recalcula esto --suma el numero que da Hattrick a la edad de
    hoy-- pero la regla queda fijada: si algun dia deja de cuadrar, es que
    Hattrick la cambio, y este test lo dira.
    """
    DIAS_POR_ANIO = 112
    EDAD_MINIMA = 17 * DIAS_POR_ANIO
    EN_LA_ACADEMIA = 112

    def faltan(edad_dias: int, dias_dentro: float) -> int:
        import math

        return math.floor(
            max(max(0, EDAD_MINIMA - edad_dias), max(0.0, EN_LA_ACADEMIA - dias_dentro))
        )

    #        (edad en dias,        dias dentro, lo que dice Hattrick)
    casos = [
        (17 * 112 + 3, 25.1, 86),    # Angel Castro: ya tiene la edad, le frena la academia
        (16 * 112 + 24, 25.5, 88),   # Nemesio Manotas: le frena la edad
        (16 * 112 + 21, 25.5, 91),   # Lucas Pulecio: le frena la edad
        (16 * 112 + 30, 3.4, 108),   # Luis Felipe Calderon: recien llegado
    ]
    for edad_dias, dentro, esperado in casos:
        assert faltan(edad_dias, dentro) == esperado, (edad_dias, dentro)


def test_a_quien_le_frena_la_edad_asciende_exacto_con_17_000() -> None:
    """Es lo que hace util la columna «Edad al subir»: 17;000 significa que no
    se pierde ni un dia, y cualquier cifra mayor son dias de academia gastados
    esperando el plazo."""
    DIAS_POR_ANIO = 112
    edad_al_subir = lambda edad_dias, faltan: edad_dias + faltan  # noqa: E731

    # Nemesio Manotas, real: 16;024 y 88 dias por delante.
    assert edad_al_subir(16 * DIAS_POR_ANIO + 24, 88) == 17 * DIAS_POR_ANIO
    # Angel Castro, real: 17;003 y 86 dias -> sube con 17;089, no con 17;000.
    assert edad_al_subir(17 * DIAS_POR_ANIO + 3, 86) == 17 * DIAS_POR_ANIO + 89
