"""La asistencia por sector se lee y se guarda, pero NO SE ENSEÑA NUNCA.

Dos decisiones, y la de ahora es una correccion de la de antes.

2026-09-01: se dejo de leer, guardar y usar por completo. Las reglas de CHPP
prohiben replicar o imitar las funciones de HT Supporter, y el desglose de
asistencia por sector (`SoldTerraces`, `SoldBasic`, `SoldRoof`, `SoldVIP`) es
una de ellas. Se borraron las columnas, el parser dejo de leerlas y la
taquilla paso a salir de `revenue`.

2026-09-28: se vuelve a leer y a guardar, y se mantiene lo de no enseñarla,
con estas palabras del usuario: «guarda el desglose, calcula con el, y no lo
enseñes nunca». El motivo es que `revenue` NUNCA se rellena --el fichero del
partido no la trae-- asi que el panel de Copa llevaba un mes enseñando «0 US$»
con sesenta y seis partidos jugados en casa, y no hay otra forma de tener la
taquilla por partido: Hattrick la publica por semana y sumada, y los partidos
de Copa comparten semana con los de liga casi siempre.

O sea que la linea se movio de GUARDARLO a ENSEÑARLO, que es lo que de verdad
imitaria la funcion. Este fichero es quien la vigila ahora: los cuatro nombres
solo pueden aparecer donde se leen del fichero, se guardan y se suman. En
cuanto uno se asoma a un endpoint, a un DTO o a una consulta que arma una
respuesta, esto falla.

Sigue siendo una comprobacion ESTATICA sobre el codigo y no sobre una
respuesta concreta, porque lo que hay que impedir no es un valor sino una
capacidad: un test que solo mirase el JSON de hoy no veria aparecer el campo
manana.
"""

from __future__ import annotations

import tokenize
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "app"

#: Los cuatro campos del fichero y las cuatro columnas que los guardan, en las
#: dos formas en que podrian asomarse a una respuesta.
PROHIBIDOS = (
    "SoldTerraces",
    "SoldBasic",
    "SoldRoof",
    "SoldVIP",
    "sold_terraces",
    "sold_basic",
    "sold_roof",
    "sold_vip",
    "soldTerraces",
    "soldBasic",
    "soldRoof",
    "soldVip",
)

#: Los tres sitios donde SI pueden estar: donde se leen, donde se guardan y
#: donde se convierten en dinero. Ni uno mas.
PERMITIDOS = {
    "parsers/__init__.py",  # se lee del fichero de Hattrick
    "models.py",  # se guarda
    # El sync, que es donde se escriben y se rellenan hacia atras. Son los
    # dos ficheros del paquete que los tocan, no el paquete entero: antes
    # valia `sync_team.py` a secas, o sea sus 7257 lineas de una vez.
    "sync_team/economia.py",
    "sync_team/partidos.py",
    "taquilla.py",  # se convierte en el total, que es lo unico que viaja
}

#: Lo que se derivaba de ella y NO vuelve: eran la funcion de Supporter en si,
#: no un total. Reconstruir la demanda real de un sector agotado, o decir que
#: sectores se llenaron, es exactamente lo que no se puede imitar.
DERIVADOS = ("estimate_true_demand", "analyse_match", "sold_out_sectors")


def _fuentes() -> list[Path]:
    return [f for f in RAIZ.rglob("*.py") if "__pycache__" not in f.parts]


def _codigo(fichero: Path) -> list[tuple[int, str]]:
    """Los identificadores del CÓDIGO, sin comentarios ni cadenas.

    Se tokeniza en vez de leer líneas sueltas porque los comentarios y los
    docstrings explican qué se hace y por qué, y para eso tienen que poder
    nombrar los campos. Nombrarlos no es usarlos.
    """
    piezas: list[tuple[int, str]] = []
    with open(fichero, "rb") as fh:
        try:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                if tok.string:
                    piezas.append((tok.start[0], tok.string))
        except (tokenize.TokenError, SyntaxError):  # pragma: no cover
            return []
    return piezas


def test_el_desglose_por_sector_no_sale_nunca() -> None:
    """La condición con la que se aceptó volver a guardarlo."""
    culpables: list[str] = []
    for fichero in _fuentes():
        if fichero.name in PERMITIDOS or f"{fichero.parent.name}/{fichero.name}" in PERMITIDOS:
            continue
        for numero, pieza in _codigo(fichero):
            if pieza in PROHIBIDOS:
                culpables.append(f"{fichero.relative_to(RAIZ).as_posix()}:{numero} → {pieza}")

    assert not culpables, (
        "El desglose de asistencia por sector se guarda para CALCULAR y no "
        "para enseñar (decisión del usuario, 2026-09-28). Aparece fuera de "
        "donde se lee, se guarda y se suma:\n  "
        + "\n  ".join(culpables)
        + "\nLo que puede viajar es el TOTAL, y la suma vive en "
        "`domain/engines/taquilla.py`."
    )


def test_tampoco_vuelve_lo_que_se_derivaba_de_ella() -> None:
    """Un total de taquilla no es la función de Supporter; esto sí lo era.

    Decir cuánta gente HABRÍA entrado en un sector agotado, o cuáles se
    llenaron, es reconstruir la función. Sumar entradas por precio para dar un
    ingreso no: el ingreso es un número del club, no un desglose del público.
    """
    culpables: list[str] = []
    for fichero in _fuentes():
        for numero, pieza in _codigo(fichero):
            if pieza in DERIVADOS:
                culpables.append(f"{fichero.name}:{numero} → {pieza}")

    assert not culpables, (
        "Volvió lo que reconstruía la asistencia por sector, que es la función "
        "de HT Supporter en sí:\n  " + "\n  ".join(culpables)
    )
