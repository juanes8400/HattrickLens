"""El -1 de la popularidad con la afición tampoco es un nivel.

2026-09-02, pedido del usuario: Espíritu y Confianza ya ignoraban el marcador
temporal de Hattrick; la afición faltaba. Es la misma clase de dato --un nivel
en una escala-- y la misma clase de fallo: guardado como número, la afición
aparecería odiándote sin que nada hubiera pasado.

Se cubre aunque no se haya visto nunca. Comprobadas las dos bases antes de
escribir esto: cero filas con -1, con quince equipos y semanas de historial.
Lo que estos tests fijan es que si algún día llega, no se cuela.
"""

from app.application.commands.sync_team import (
    PLACEHOLDERS_DE_ANIMO,
    _sin_placeholders_de_animo,
)
from app.domain.engines.sync_diff import diff_economy

CAMPOS_ECONOMIA = PLACEHOLDERS_DE_ANIMO["economy"]


def test_la_aficion_esta_entre_los_indicadores_que_se_limpian() -> None:
    assert "supporters_popularity" in CAMPOS_ECONOMIA


def test_un_menos_uno_conserva_la_ultima_lectura_real() -> None:
    """Lo que sigue siendo cierto es lo último que se supo, no un cero."""
    limpio = _sin_placeholders_de_animo(
        {"supporters_popularity": -1, "cash": 100},
        {"supporters_popularity": 7, "cash": 90},
        CAMPOS_ECONOMIA,
    )
    assert limpio["supporters_popularity"] == 7
    # Y no toca nada más de la foto.
    assert limpio["cash"] == 100


def test_sin_lectura_previa_se_guarda_la_ausencia_y_no_un_cero() -> None:
    """Un cero es «la afición te odia»; la ausencia es «todavía no se sabe»."""
    limpio = _sin_placeholders_de_animo(
        {"supporters_popularity": -1}, None, CAMPOS_ECONOMIA
    )
    assert limpio["supporters_popularity"] is None

    tampoco = _sin_placeholders_de_animo(
        {"supporters_popularity": -1}, {"supporters_popularity": -1}, CAMPOS_ECONOMIA
    )
    assert tampoco["supporters_popularity"] is None


def test_un_cero_de_verdad_no_se_toca() -> None:
    """Cero SÍ es un nivel de la escala --el peor-- y hay que respetarlo."""
    limpio = _sin_placeholders_de_animo(
        {"supporters_popularity": 0}, {"supporters_popularity": 9}, CAMPOS_ECONOMIA
    )
    assert limpio["supporters_popularity"] == 0


def test_cambios_no_anuncia_un_desplome_que_no_ocurrio() -> None:
    """El fallo que se ve: «Popularidad con la afición 7 → -1» en el buzón."""
    cambios = diff_economy(
        {"supporters_popularity": 7, "cash": 100},
        {"supporters_popularity": -1, "cash": 100},
    )
    assert not [c for c in cambios if c.metric == "supporters_popularity"]

    # Y tampoco al volver: «-1 → 7» sería una subida igual de falsa.
    cambios = diff_economy(
        {"supporters_popularity": -1, "cash": 100},
        {"supporters_popularity": 7, "cash": 100},
    )
    assert not [c for c in cambios if c.metric == "supporters_popularity"]


def test_un_cambio_real_de_la_aficion_si_se_anuncia() -> None:
    """La red de seguridad del test anterior: que no lo silencie todo."""
    cambios = diff_economy(
        {"supporters_popularity": 7, "cash": 100},
        {"supporters_popularity": 8, "cash": 100},
    )
    afición = [c for c in cambios if c.metric == "supporters_popularity"]
    assert len(afición) == 1
    assert afición[0].before == 7
    assert afición[0].after == 8
