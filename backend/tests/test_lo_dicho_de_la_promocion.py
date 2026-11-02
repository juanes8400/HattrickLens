"""La terna de la ficha de rival, puesta en local y visitante para guardarla.

La ficha habla de «lo mío» y «lo suyo»; el parte del partido lee local y
visitante. Si la vuelta se da mal, lo que se enseña después del partido es el
pronóstico del rival presentado como el tuyo, y nadie lo notaría.
"""
from app.api.v1.endpoints.rivals import _en_casa_y_fuera

DE_LA_FICHA = {
    "own_probability": 0.52,
    "draw_probability": 0.23,
    "rival_probability": 0.25,
    "expected_own_goals": 1.8,
    "expected_rival_goals": 1.1,
    "most_likely_score": "2-1",
}


def test_jugando_en_casa_lo_mio_es_lo_local() -> None:
    puesto = _en_casa_y_fuera(DE_LA_FICHA, propio_en_casa=True)
    assert puesto["homeWin"] == 0.52
    assert puesto["awayWin"] == 0.25
    assert puesto["expectedHomeGoals"] == 1.8
    assert puesto["mostLikelyScore"] == "2-1"


def test_jugando_fuera_se_da_la_vuelta_a_todo() -> None:
    puesto = _en_casa_y_fuera(DE_LA_FICHA, propio_en_casa=False)
    assert puesto["homeWin"] == 0.25
    assert puesto["awayWin"] == 0.52
    assert puesto["expectedHomeGoals"] == 1.1
    assert puesto["expectedAwayGoals"] == 1.8
    # Y el marcador también: 2-1 a mi favor fuera es 1-2 en el acta.
    assert puesto["mostLikelyScore"] == "1-2"


def test_el_empate_viaja_siempre_con_un_numero() -> None:
    """En copa no hay empate y la ficha manda `None`. La tabla guarda un
    número, así que ahí es cero: en promoción nunca pasa, pero un `None`
    rompería la escritura en vez de guardar algo raro."""
    sin_empate = {**DE_LA_FICHA, "draw_probability": None}
    assert _en_casa_y_fuera(sin_empate, propio_en_casa=True)["draw"] == 0.0
