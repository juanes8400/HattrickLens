"""El registro de la aplicación, configurado una vez y de verdad.

2026-11-03. Hasta hoy nadie configuraba `logging`, así que todo lo que
escribían los módulos de `app` caía en el handler de «último recurso» de la
biblioteca estándar: publica de WARNING para arriba y TIRA el resto, sin
avisar. Y `settings.log_level` existía desde siempre sin que lo leyera nadie.

LO QUE COSTÓ. Dos diagnósticos a ciegas el mismo día. Por la mañana, Liga
devolvía 500 en producción y el motivo estaba escrito en un `info` que no
salía por ninguna parte; por la tarde, la ficha de rival enseñaba dos partidos
en vez de cinco y el posible fallo de la llamada al archivo se registraba
también en `info`. Las dos veces el arreglo fue de minutos y encontrar la
causa, de horas. Se venía parcheando línea por línea, subiendo avisos a
WARNING según aparecía el siguiente punto ciego.

QUÉ HACE Y QUÉ NO. Pone un handler en la raíz con el nivel de
`settings.log_level`, y nada más. No toca los `uvicorn.*`, que el propio
servidor configura con su formato y sus colores: duplicarlos sacaría cada
petición dos veces. Es idempotente porque `main` se importa muchas veces en
las pruebas y dos handlers imprimirían doble.
"""

import logging

from app.core.config import settings

#: Marca nuestro handler para reconocerlo entre llamadas y no añadir otro.
_NOMBRE = "ht-lens"


def configurar_registro() -> None:
    raiz = logging.getLogger()
    if any(getattr(h, "name", None) == _NOMBRE for h in raiz.handlers):
        return
    handler = logging.StreamHandler()
    handler.name = _NOMBRE
    handler.setFormatter(
        # Sin color y sin marca de tiempo propia: Render ya le pone la suya a
        # cada línea, y repetirla deja el registro ilegible.
        logging.Formatter("%(levelname)-8s %(name)s: %(message)s")
    )
    raiz.addHandler(handler)
    raiz.setLevel(settings.log_level.upper())
