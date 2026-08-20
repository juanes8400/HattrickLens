"""Formato de números en texto generado por el servidor (resúmenes de
Cambios, alertas de insights.py, notas de academia/economía, etc.) —
2026-08-15, pedido explícitamente: TODO número de la aplicación usa punto
como separador de miles, nunca coma. `f"{value:,}"` de Python hace lo
contrario (coma de miles, punto decimal) — de ahí que varios mensajes
generados a mano se hubieran colado con el formato de EE. UU."""


def thousands(value: float, decimals: int = 0) -> str:
    """"615000" -> "615.000"; con decimales, "1234567.89" -> "1.234.567,89"
    (coma decimal, no punto) — el mismo intercambio que ya usa el resto de
    la app (`money`/`number` en el frontend)."""
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
