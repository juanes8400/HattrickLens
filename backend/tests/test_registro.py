"""El registro se configura, y una sola vez.

2026-11-03. La aplicación no configuraba `logging`, así que todo lo que
escribían sus módulos por debajo de WARNING se perdía sin dejar rastro, y
`settings.log_level` llevaba ahí desde siempre sin que lo leyera nadie. Dos
diagnósticos a ciegas el mismo día salieron de ahí.
"""

import logging

from app.core.config import settings
from app.core.registro import _NOMBRE, configurar_registro


def test_pone_un_handler_con_el_nivel_configurado() -> None:
    configurar_registro()
    raiz = logging.getLogger()
    mios = [h for h in raiz.handlers if getattr(h, "name", None) == _NOMBRE]
    assert len(mios) == 1
    assert logging.getLevelName(raiz.level) == settings.log_level.upper()


def test_llamarlo_dos_veces_no_duplica_la_salida() -> None:
    """`main` se importa muchas veces en las pruebas; dos handlers imprimirían
    cada línea dos veces."""
    configurar_registro()
    configurar_registro()
    raiz = logging.getLogger()
    assert sum(1 for h in raiz.handlers if getattr(h, "name", None) == _NOMBRE) == 1


def test_un_info_de_la_aplicacion_llega(caplog) -> None:
    """Lo que de verdad importa: que un `info` de un módulo de `app` no se
    pierda. Antes se lo tragaba el handler de «último recurso»."""
    configurar_registro()
    with caplog.at_level(logging.INFO, logger="app.prueba"):
        logging.getLogger("app.prueba").info("esto tiene que verse")
    assert "esto tiene que verse" in caplog.text
