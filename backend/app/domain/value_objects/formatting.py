"""Formato de números en texto generado por el servidor (resúmenes de
Cambios, alertas de insights.py, notas de academia/economía, etc.)
2026-08-15, pedido explícitamente: TODO número de la aplicación usa punto
como separador de miles, nunca coma. `f"{value:,}"` de Python hace lo
contrario (coma de miles, punto decimal), de ahí que varios mensajes
generados a mano se hubieran colado con el formato de EE. UU.

2026-09-19: y al revés en inglés. El texto se traduce al salir, pero los
números ya venían escritos, así que «453.910» se leía como 453 con decimales.
El idioma de la petición lo pone el middleware de traducción en
``idioma_de_la_peticion``; sin petición (un script, un test) manda el español,
que es como se escribió la aplicación.
"""

from contextvars import ContextVar

#: El idioma de la petición que se está respondiendo. Lo pone
#: ``app.i18n.middleware``; fuera de una petición se queda en español.
idioma_de_la_peticion: ContextVar[str] = ContextVar("idioma_de_la_peticion", default="es")


#: Cómo escribe los miles cada idioma. UNA ENTRADA POR IDIOMA Y NO «SI EMPIEZA
#: POR EN» (2026-09-21, al añadir el italiano): con dos idiomas la bifurcación
#: acertaba, pero el italiano habría acertado por casualidad y el francés o el
#: sueco, que separan con un espacio fino, habrían salido mal sin que nadie
#: tocara nada. Añadir un idioma obliga a decidirlo. Tiene que decir lo mismo
#: que `MILES` en `frontend/src/hooks/useFormat.ts`.
MILES = {"es": ".", "en": ",", "it": ".", "de": "."}


def thousands(value: float, decimals: int = 0) -> str:
    """ "615000" -> "615.000" en español y "615,000" en inglés; con decimales,
    "1234567.89" -> "1.234.567,89" y "1,234,567.89". El mismo intercambio que
    hace el frontend (`money`/`number`)."""
    formatted = f"{value:,.{decimals}f}"
    if MILES.get(idioma_de_la_peticion.get()[:2], ".") == ",":
        return formatted
    return formatted.translate(str.maketrans(",.", ".,"))
