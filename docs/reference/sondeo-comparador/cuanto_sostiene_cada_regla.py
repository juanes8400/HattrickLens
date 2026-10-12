"""Cuanto sostiene cada regla: se quita una y se cuenta lo que se rompe.

PARA QUE SIRVE. El motor es un monton de reglas sacadas de mediciones
distintas, y no todas pesan lo mismo. Esto las quita de una en una y cuenta
cuantos de los casos medidos dejan de salir. Una regla que al quitarla no rompe
NADA no esta sostenida por ninguna medicion: puede ser verdad, pero no hay dato
que lo diga, y conviene saberlo antes de razonar sobre ella.

Se ejecuta desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/cuanto_sostiene_cada_regla.py
"""

import sys

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/tests")
sys.path.insert(0, "docs/reference/sondeo-comparador")

import banco  # noqa: E402
import test_criterios_hattrick as T  # noqa: E402
from app.domain.engines import criterios_hattrick as C  # noqa: E402


def cuantos_bien() -> int:
    """Lo mismo que puntua el banco, en silencio."""
    cas, rej, ords, tps = banco.cadenas(), banco.rejilla(), banco.ordenes(), banco.tipos()
    bien = sum(1 for e, n, s in cas if T._pinta(C.criterios_de(e, dict(n))) == s)
    bien += sum(
        1
        for e, n, s in rej
        if " ".join(
            T.ABREVIATURA[c.habilidad] + ("." if c.operador == "<=" else "")
            for c in C.criterios_de(e, dict(n)).habilidades
        )
        == s
    )
    bien += sum(
        1
        for e, n, s in ords
        if ",".join(
            T.ABREVIATURA[c.habilidad]
            for c in C.criterios_de(e, dict(n)).habilidades
            if c.operador != "<="
        )
        == s
    )
    bien += sum(1 for n, esperado in tps if C._tipo(dict(n)) == esperado)
    return bien


TOTAL = (
    len(banco.cadenas()) + len(banco.rejilla()) + len(banco.ordenes()) + len(banco.tipos())
)


def sin(nombre: str, pon, quita) -> None:
    guardado = pon()
    try:
        quita()
        roto = TOTAL - cuantos_bien()
    finally:
        pon(guardado)
    marca = "  <-- NINGUNA MEDICION LA SOSTIENE" if roto == 0 else ""
    print(f"  sin {nombre:46s} se rompen {roto:3d}/{TOTAL}{marca}")


def _guarda(attr):
    def pon(valor=None):
        if valor is None:
            return getattr(C, attr)
        setattr(C, attr, valor)
        return None
    return pon


print(f"casos medidos: {TOTAL}\n")

# --- el tipo de jugador ----------------------------------------------------
pon = _guarda("_umbral_de_portero")
sin("el sesgo del portero sobre la defensa", pon, lambda: setattr(C, "_umbral_de_portero", lambda d: d + 1))
pon = _guarda("ORDEN_LLANO")
sin(
    "la Porteria quinta en el desempate del tipo",
    pon,
    lambda: setattr(C, "ORDEN_LLANO", ("winger", "scoring", "keeper", "defending", "playmaking", "passing")),
)

# --- quien puede ser criterio ---------------------------------------------
pon = _guarda("EXCLUIDAS")
sin(
    "las exclusiones por tipo",
    pon,
    lambda: setattr(C, "EXCLUIDAS", dict.fromkeys(C.PLANTILLAS, frozenset())),
)
pon = _guarda("_fuera")
ORIG_FUERA = C._fuera


def _sin_tapadera(tipo, niveles):
    fuera = C.EXCLUIDAS[tipo]
    if niveles.get("scoring", 0) < C.ENTRADA_TERCERO:
        fuera |= {"scoring"}
    if tipo == "playmaking" and niveles.get("winger", 0) < C.LATERAL_DEL_MEDIO_SIN_AYUDA:
        ofensivo = (
            niveles.get("scoring", 0) >= C.ENTRADA_TERCERO
            and niveles.get("defending", 0) < C.ENTRADA_TERCERO
        )
        if not ofensivo and niveles.get("winger", 0) < niveles.get("playmaking", 0) - 1:
            fuera |= {"winger"}
    return fuera


def _sin_lateral(tipo, niveles):
    fuera = C.EXCLUIDAS[tipo]
    if niveles.get("scoring", 0) < C.ENTRADA_TERCERO:
        fuera |= {"scoring"}
    if (
        tipo == "winger"
        and "scoring" not in fuera
        and niveles.get("defending", 0) < niveles.get("scoring", 0)
    ):
        fuera |= {"defending"}
    return fuera


def _sin_anotacion(tipo, niveles):
    fuera = C.EXCLUIDAS[tipo]
    if (
        tipo == "winger"
        and niveles.get("defending", 0) < niveles.get("scoring", 0)
    ):
        fuera |= {"defending"}
    if tipo == "playmaking" and niveles.get("winger", 0) < C.LATERAL_DEL_MEDIO_SIN_AYUDA:
        ofensivo = (
            niveles.get("scoring", 0) >= C.ENTRADA_TERCERO
            and niveles.get("defending", 0) < C.ENTRADA_TERCERO
        )
        if not ofensivo and niveles.get("winger", 0) < niveles.get("playmaking", 0) - 1:
            fuera |= {"winger"}
    return fuera


sin("la tapadera de la Anotacion al extremo", pon, lambda: setattr(C, "_fuera", _sin_tapadera))
sin("la regla del Lateral del mediocentro", pon, lambda: setattr(C, "_fuera", _sin_lateral))
sin("que la Anotacion pida cinco", pon, lambda: setattr(C, "_fuera", _sin_anotacion))

# --- el orden -------------------------------------------------------------
pon = _guarda("ORDEN_DE_IMPORTANCIA")
sin("los pesos del extremo", pon, lambda: setattr(C, "ORDEN_DE_IMPORTANCIA", {k: v for k, v in C.ORDEN_DE_IMPORTANCIA.items() if k != "winger"}))
sin("los pesos del mediocentro", pon, lambda: setattr(C, "ORDEN_DE_IMPORTANCIA", {k: v for k, v in C.ORDEN_DE_IMPORTANCIA.items() if k != "playmaking"}))
pon = _guarda("DESEMPATE")
sin("el desempate propio del extremo", pon, lambda: setattr(C, "DESEMPATE", {}))

# --- el dial --------------------------------------------------------------
pon = _guarda("UMBRAL_POR_PAREJA")
sin("la tabla del dial por pareja", pon, lambda: setattr(C, "UMBRAL_POR_PAREJA", {}))
pon = _guarda("PRIMERA_QUE_AFLOJA_SOLA")
sin("que una habilidad de 17 afloje sola", pon, lambda: setattr(C, "PRIMERA_QUE_AFLOJA_SOLA", 99))

# --- los operadores -------------------------------------------------------
pon = _guarda("PRIMERA_QUE_NO_SOSTIENE_TERCERO")
sin("que la primera en 5 no sostenga tercero", pon, lambda: setattr(C, "PRIMERA_QUE_NO_SOSTIENE_TERCERO", 0))
pon = _guarda("TERCERO_QUE_ABRE_AL_SEGUNDO")
sin("que la tercera en 7 abra la segunda", pon, lambda: setattr(C, "TERCERO_QUE_ABRE_AL_SEGUNDO", 99))
