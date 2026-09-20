"""Las respuestas de la API viajan comprimidas, menos el chorro de progreso.

2026-09-20, midiendo los tiempos de carga: el listado de partidos pesaba
314.684 bytes y salia tal cual, sin una sola cabecera de compresion. Es JSON,
o sea las mismas veinte claves repetidas setecientas veces, que es el caso en
el que comprimir gana mas.

Lo que se fija aqui es lo que se puede romper sin que nadie lo note:

  1. Que la compresion sigue puesta. Quitar el middleware no rompe ninguna
     prueba funcional, y la regresion seria invisible hasta que alguien mida.
  2. Que el chorro de la sincronizacion NO se comprime. Un flujo comprimido se
     queda esperando a llenar el bufer, asi que la barra de progreso no se
     moveria hasta el final, que es cuando ya no sirve de nada.
"""

from __future__ import annotations

from starlette.middleware.gzip import GZipMiddleware

from app.main import app


def _capas() -> list[type]:
    return [c.cls for c in app.user_middleware]


def test_la_api_comprime_sus_respuestas() -> None:
    assert GZipMiddleware in _capas(), "se cayo la compresion de las respuestas"


def test_comprimir_va_por_fuera_de_traducir() -> None:
    """El orden importa y no es simetrico.

    `add_middleware` apila de dentro hacia fuera, asi que la compresion tiene
    que anadirse DESPUES de la traduccion para quedar por fuera y comprimir el
    texto ya traducido. Al reves, la traduccion recibiria un cuerpo binario y
    la respuesta saldria en espanol para todo el mundo.
    """
    from app.i18n.middleware import TraducirRespuestas

    capas = _capas()
    assert capas.index(GZipMiddleware) < capas.index(TraducirRespuestas), (
        "la compresion quedo por dentro de la traduccion"
    )


def test_el_chorro_de_la_sincronizacion_se_declara_sin_comprimir() -> None:
    """La marca que lo salva es `Content-Encoding: identity` en su respuesta.

    Starlette respeta una codificacion que ya venga puesta, asi que esa
    cabecera es lo unico que impide que el progreso se quede en el bufer. Se
    comprueba en el codigo del endpoint porque montar el chorro entero pediria
    un sync de verdad.
    """
    import inspect

    from app.api.v1.endpoints import teams

    fuente = inspect.getsource(teams)
    assert '"Content-Encoding": "identity"' in fuente
