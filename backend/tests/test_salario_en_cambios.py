"""El salario de «Cambios» va en la moneda del club, no en la de Hattrick.

2026-09-01, visto por el usuario en producción: el salario salía diez veces
más grande. `diff_player_skills` escribía el número crudo de Hattrick mientras
que TODAS las demás pantallas --plantilla, panel, historial, comparación de
sincronizaciones-- lo dividían por la tasa del país. En Colombia esa tasa es
10, así que la misma ficha se leía como 120.000 en una pantalla y 1.200.000 en
la otra.

Y no era un error de pintado: la frase se congela en la fila del cambio cuando
se sincroniza, así que cada sync dejaba escrito un número falso para siempre.
Por eso la conversión tiene que ocurrir aquí, en el origen, y no al leer.

La moneda en la frase no es adorno: es lo que distingue una fila ya convertida
de las viejas, y de eso depende poder repararlas sin dividir dos veces.
"""

from app.domain.engines.sync_diff import diff_player_skills

ANTES = {"salary": 1_200_000, "tsi": 9000, "skills": {}}
DESPUES = {"salary": 1_350_000, "tsi": 9500, "skills": {}}


def _salario(cambios):
    return next(c for c in cambios if c.metric == "salary")


def test_el_salario_se_divide_por_la_tasa_del_pais() -> None:
    c = _salario(diff_player_skills(ANTES, DESPUES, "Juan Pérez", 10.0, "COL$"))
    assert c.before == 120_000
    assert c.after == 135_000
    assert "120.000 -> 135.000 COL$" in c.summary
    assert c.currency == "COL$"


def test_sin_tasa_el_numero_no_se_toca() -> None:
    """Los países cuya moneda es la base de Hattrick tienen tasa 1."""
    c = _salario(diff_player_skills(ANTES, DESPUES, "Juan Pérez", 1.0, "€"))
    assert c.before == 1_200_000
    assert c.after == 1_350_000


def test_una_tasa_en_cero_no_revienta_ni_borra_el_dato() -> None:
    """Un equipo recién importado puede no tener tasa todavía. Dividir por cero
    tumbaría el sync entero por una frase; se deja el número crudo."""
    c = _salario(diff_player_skills(ANTES, DESPUES, "Juan Pérez", 0.0, ""))
    assert c.before == 1_200_000


def test_el_tsi_no_es_dinero_y_no_se_convierte() -> None:
    """El fallo contrario, y sería igual de invisible: el TSI es un índice, no
    una cantidad de dinero, y dividirlo por la tasa lo estropearía."""
    cambios = diff_player_skills(ANTES, DESPUES, "Juan Pérez", 10.0, "COL$")
    tsi = next(c for c in cambios if c.metric == "tsi")
    assert tsi.before == 9000
    assert tsi.after == 9500


def test_por_omision_se_comporta_como_antes() -> None:
    """La firma vieja sigue valiendo: hay llamadas en tests y en herramientas
    que no conocen el equipo."""
    c = _salario(diff_player_skills(ANTES, DESPUES, "Juan Pérez"))
    assert c.before == 1_200_000
    assert c.summary.endswith("1.200.000 -> 1.350.000")
