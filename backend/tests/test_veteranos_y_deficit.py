"""Segunda tanda de mejoras (2026-09-13): veteranos sin habilidades de campo y
el nombre de la alerta de déficit."""

from app.domain.engines.insights import structural_deficit
from app.domain.value_objects.ht_constants import sin_habilidades_de_campo


def _habilidades(**valores: int) -> dict[str, int | None]:
    base = dict.fromkeys(
        ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"), 0
    )
    return base | valores


def test_los_veteranos_reales_de_la_plantilla_quedan_fuera() -> None:
    # Manakin, Cacheiro y Horhoi, con sus números del 2026-09-13.
    assert sin_habilidades_de_campo(44, _habilidades(set_pieces=7))
    assert sin_habilidades_de_campo(42, _habilidades(playmaking=2, passing=1))
    assert sin_habilidades_de_campo(41, _habilidades(keeper=5, set_pieces=11))


def test_una_sola_habilidad_de_campo_por_encima_del_tope_basta_para_quedarse() -> None:
    assert not sin_habilidades_de_campo(33, _habilidades(defending=6))


def test_el_balon_parado_no_cuenta_como_habilidad_de_campo() -> None:
    assert sin_habilidades_de_campo(35, _habilidades(set_pieces=20))


def test_un_joven_con_todo_bajo_no_se_esconde() -> None:
    """A los 19 es alguien a quien entrenar, no ruido."""
    assert not sin_habilidades_de_campo(19, _habilidades())


def test_una_habilidad_sin_dato_cuenta_como_cero() -> None:
    assert sin_habilidades_de_campo(40, _habilidades(scoring=None))


def test_la_alerta_de_deficit_dice_que_es_el_de_fondo() -> None:
    out = structural_deficit(-217_000, 21_034_174, "US$", season_week="83-08")
    assert out[0].title.startswith("Déficit de fondo")
    assert "esta semana" not in out[0].title
    assert "sin compraventa" in out[0].detail
    # La clave sigue llevando la semana: archivar una no calla las siguientes.
    assert out[0].key == "economy.structural_deficit.83-08"
