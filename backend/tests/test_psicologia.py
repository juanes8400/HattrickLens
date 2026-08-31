"""A qué obedece cada movimiento del ánimo.

Lo que se fija aquí no son cifras sino la REGLA: una causa sólo se afirma si
se puede comprobar. El resto es contexto y se cuenta aparte.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.domain.engines import psicologia as psi

T0 = datetime(2026, 8, 1, 12, 0)


def _l(dias: float, nivel: int) -> psi.Lectura:
    return psi.Lectura(at=T0 + timedelta(days=dias), level=nivel)


def _p(dias: float, actitud: int, gf: int = 1, gc: int = 0) -> psi.Partido:
    return psi.Partido(
        played_at=T0 + timedelta(days=dias),
        rival="Rival F.C.",
        is_home=True,
        goals_for=gf,
        goals_against=gc,
        attitude=actitud,
    )


def test_una_subida_con_PIC_dentro_se_atribuye_al_PIC() -> None:
    mv = psi.movimientos_de_espiritu([_l(0, 5), _l(2, 7)], [_p(1, psi.PIC)], {}, {}, [])
    assert len(mv) == 1
    assert mv[0].delta == 2
    assert "PIC" in mv[0].cause
    assert "Rival F.C." in mv[0].cause


def test_una_bajada_sin_golpe_es_la_vuelta_al_equilibrio() -> None:
    mv = psi.movimientos_de_espiritu([_l(0, 7), _l(1, 6)], [], {}, {}, [])
    assert mv[0].cause == "Vuelta al equilibrio"


def test_un_partido_en_Normal_no_explica_una_bajada() -> None:
    """Normal no empuja: lo que se ve después es la deriva, no el partido.

    El texto tampoco lo menciona — nombrarlo en la causa sugeriría que el
    partido hundió el espíritu, y no lo hizo.
    """
    mv = psi.movimientos_de_espiritu([_l(0, 6), _l(2, 5)], [_p(1, psi.NORMAL)], {}, {}, [])
    assert mv[0].cause == "Vuelta al equilibrio"


def test_un_MOTS_si_explica_una_bajada() -> None:
    mv = psi.movimientos_de_espiritu([_l(0, 7), _l(2, 5)], [_p(1, psi.MOTS)], {}, {}, [])
    assert "MOTS" in mv[0].cause


def test_el_mercado_se_cuenta_pero_nunca_se_declara_causa() -> None:
    """El manual dice que comprar o vender ARRIESGA un bajón, no que lo cause.

    Así que las operaciones del tramo se cuentan y se enseñan al lado, y la
    causa sigue siendo la que sí se puede comprobar.
    """
    dia = (T0 + timedelta(days=1)).date().isoformat()
    mv = psi.movimientos_de_espiritu(
        [_l(0, 6), _l(2, 5)], [], {dia: 2}, {dia: 3}, []
    )
    assert mv[0].cause == "Vuelta al equilibrio"
    assert mv[0].buys == 2
    assert mv[0].sales == 3
    assert "venta" not in mv[0].cause.lower()
    assert "compra" not in mv[0].cause.lower()


def test_bajar_la_intensidad_manda_sobre_el_partido() -> None:
    """El manual: reducir la intensidad da un impulso momentáneo. Si en el
    mismo tramo hay las dos cosas, la intensidad es la explicación directa."""
    mv = psi.movimientos_de_espiritu(
        [_l(0, 5), _l(2, 6)], [_p(1, psi.PIC)], {}, {}, [T0 + timedelta(days=1)]
    )
    assert mv[0].cause == "Bajada del % de entrenamiento"


def test_una_subida_sin_nada_registrado_lo_dice() -> None:
    """No se inventa una causa para cuadrar: se declara que no se sabe."""
    mv = psi.movimientos_de_espiritu([_l(0, 5), _l(2, 7)], [], {}, {}, [])
    assert mv[0].cause == "Subida sin causa registrada"


def test_la_confianza_se_explica_con_resultados_no_con_actitud() -> None:
    """El manual nombra la actitud sólo para el espíritu."""
    mv = psi.movimientos_de_confianza(
        [_l(0, 5), _l(3, 6)], [_p(1, psi.PIC, 4, 0), _p(2, psi.NORMAL, 0, 3)]
    )
    assert "victoria 4-0" in mv[0].cause.lower()
    assert "derrota 0-3" in mv[0].cause.lower()
    assert "PIC" not in mv[0].cause


def test_las_escalas_salen_enteras() -> None:
    """Recortar el eje a lo observado hacía parecer que el mínimo visto era
    un suelo del juego. Los once y los diez niveles salen siempre."""
    assert [p["level"] for p in psi.escala("spirit")] == list(range(11))
    assert [p["level"] for p in psi.escala("confidence")] == list(range(10))


def test_el_equilibrio_base_es_serenos() -> None:
    """Confirmado por el usuario. Es a donde TIENDE, no un suelo: se puede
    bajar de ahí, sólo que en su histórico no ha pasado."""
    assert psi.EQUILIBRIO_BASE == 4


def test_la_serie_llega_hasta_lo_ultimo_que_se_sabe() -> None:
    """Un tramo plano es informacion, no un hueco.

    2026-08-31, visto por el usuario: la confianza no se movia desde el 21 de
    agosto y la linea moria ahi, con diez dias ya conocidos sin dibujar. La
    serie se queda con los CAMBIOS --dos lecturas iguales no son un dato
    nuevo-- pero tiene que terminar en la ultima lectura, no en el ultimo
    cambio, o parece que falta el dato cuando lo que pasa es que no se movio.
    """
    quieta = [_l(0, 7), _l(10, 7)]
    mv = psi.movimientos_de_confianza(quieta, [])
    assert len(mv) == 1
    assert mv[0].delta == 0
    assert mv[0].cause == "Sin cambios"


def test_un_tramo_plano_no_es_una_vuelta_al_equilibrio() -> None:
    """Decir «vuelta al equilibrio» sobre algo que no se movio seria explicar
    un movimiento que no ocurrio."""
    mv = psi.movimientos_de_espiritu([_l(0, 6), _l(4, 6)], [], {}, {}, [])
    assert mv[0].cause == "Sin cambios"
