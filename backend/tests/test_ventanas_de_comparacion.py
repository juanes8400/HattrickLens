"""Contra qué cierre semanal compara cada ventana de Jugadores.

2026-09-20: las ventanas de comparación pasaron de ser un desplegable de
sincronizaciones a una barra de «último cambio / 1 / 2 / 4 / 8 / 16 semanas /
siempre». La cuenta de fechas vive en el servidor, que es quien tiene los
cierres, y esto la fija.
"""

from datetime import datetime, timedelta

import pytest

from app.application.dto.squad import SquadHistoryEntry
from app.application.queries.squad import cierre_de_la_ventana

HOY = datetime(2026, 9, 17, 10, 30)


def historia(*semanas_atras: float) -> list[SquadHistoryEntry]:
    """Cierres de más reciente a más antiguo, como los devuelve la consulta."""
    return [
        SquadHistoryEntry(
            sync_id=100 + i,
            captured_at=(HOY - timedelta(weeks=s)).isoformat(),
            snapshots=25,
        )
        for i, s in enumerate(semanas_atras)
    ]


def test_el_ultimo_cambio_no_elige_cierre():
    # `None` es la señal de comparar cada jugador con su propio snapshot
    # anterior, que es lo que hacía la pantalla antes de tener ventanas.
    assert cierre_de_la_ventana(historia(0, 1, 2), "change") is None


def test_cada_ventana_coge_su_semana():
    h = historia(0, 1, 2, 3, 4)
    assert cierre_de_la_ventana(h, "w1") == 101
    assert cierre_de_la_ventana(h, "w2") == 102
    assert cierre_de_la_ventana(h, "w4") == 104


def test_una_sincronizacion_a_deshora_no_descoloca_la_ventana():
    # EL CASO QUE OBLIGA A COGER EL MÁS CERCANO Y NO «EL PRIMERO QUE SEA AL
    # MENOS TAN VIEJO»: el cierre de hace una semana se tomó unas horas ANTES
    # de cumplirse la semana, y con la regla estricta la ventana de una semana
    # se saltaba a la de dos.
    h = historia(0, 0.99, 2)
    assert cierre_de_la_ventana(h, "w1") == 101


def test_siempre_es_el_cierre_mas_antiguo():
    assert cierre_de_la_ventana(historia(0, 1, 2, 9), "all") == 103


def test_sin_historia_que_llegue_tan_atras_no_hay_ventana():
    # Tres semanas guardadas no pueden contestar «hace ocho»; la pantalla la
    # enseña apagada en vez de comparar contra otra cosa y callarse.
    h = historia(0, 1, 2, 3)
    assert cierre_de_la_ventana(h, "w8") is None
    assert cierre_de_la_ventana(h, "w16") is None


def test_ocho_semanas_justas_entran_por_el_margen():
    # Ocho cierres semanales, el más antiguo unas horas corto de las ocho
    # semanas. Cuenta: si no, la ventana se apaga el día que se cumple.
    h = historia(0, 1, 2, 3, 4, 5, 6, 7.9)
    assert cierre_de_la_ventana(h, "w8") == 107


def test_el_primer_cierre_nunca_es_la_referencia():
    # Es el retrato de hoy: compararlo consigo mismo daría cero en todas las
    # filas y parecería que no cambió nada.
    assert cierre_de_la_ventana(historia(0), "w1") is None
    assert cierre_de_la_ventana(historia(0), "all") is None


def test_una_ventana_que_no_existe_se_rechaza():
    with pytest.raises(KeyError):
        cierre_de_la_ventana(historia(0, 1), "w3")
