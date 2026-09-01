"""Ni se pide, ni se guarda, ni se enseña la asistencia por sector.

Las reglas de CHPP prohíben replicar o imitar las funciones de HT Supporter, y
el desglose de asistencia por sector es una de ellas: `SoldTerraces`,
`SoldBasic`, `SoldRoof` y `SoldVIP` de matchdetails (requisito del 2026-09-01).

Esto es una comprobación ESTÁTICA sobre el código, no sobre una respuesta
concreta, porque lo que hay que impedir no es un valor sino una capacidad: que
alguien vuelva a leer esos campos, a guardarlos o a derivar de ellos. Un test
que sólo mirase el JSON de hoy no vería reaparecer el parser.

Lo que SÍ es público y no se toca:
  * `SoldTotal` — Hattrick lo enseña en la página del partido.
  * El aforo por sector — es la configuración de tu propio estadio y llega por
    arenadetails.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1] / "app"

#: Los cuatro campos del XML y las cuatro columnas que los guardaban.
PROHIBIDOS = (
    "SoldTerraces",
    "SoldBasic",
    "SoldRoof",
    "SoldVIP",
    "sold_terraces",
    "sold_basic",
    "sold_roof",
    "sold_vip",
)

#: Nombres de lo que se construía a partir de ellos. Si reaparecen es que
#: volvió el cálculo, aunque los campos se llamen de otra forma.
DERIVADOS = ("estimate_true_demand", "analyse_match", "sold_out_sectors")


def _fuentes() -> list[Path]:
    return [f for f in RAIZ.rglob("*.py") if "__pycache__" not in f.parts]


def _codigo(fichero: Path) -> list[tuple[int, str]]:
    """Los identificadores del CÓDIGO, sin comentarios ni cadenas.

    Se tokeniza en vez de leer líneas sueltas porque los comentarios y los
    docstrings explican qué se quitó y por qué, y para eso tienen que poder
    nombrar los campos. Nombrarlos no es usarlos: si no se descartaran, este
    test obligaría a borrar justo la explicación que evita que alguien lo
    reintroduzca.
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
            # Un fichero que no tokeniza no compila, y eso ya lo dice otro test.
            return []
    return piezas


def test_nadie_lee_ni_guarda_la_asistencia_por_sector() -> None:
    culpables: list[str] = []
    for fichero in _fuentes():
        for numero, pieza in _codigo(fichero):
            if pieza in PROHIBIDOS:
                culpables.append(f"{fichero.name}:{numero} → {pieza}")

    assert not culpables, (
        "La asistencia por sector es una función de HT Supporter y las reglas "
        "de CHPP prohíben replicarla. Reaparece en:\n  " + "\n  ".join(culpables)
    )


def test_tampoco_vuelve_lo_que_se_derivaba_de_ella() -> None:
    culpables: list[str] = []
    for fichero in _fuentes():
        for numero, pieza in _codigo(fichero):
            if pieza in DERIVADOS:
                culpables.append(f"{fichero.name}:{numero} → {pieza}")

    assert not culpables, (
        "Esto se calculaba a partir de la asistencia por sector:\n  " + "\n  ".join(culpables)
    )


def test_el_total_y_el_aforo_por_sector_siguen_permitidos() -> None:
    """El test de arriba no puede llevarse por delante lo que sí es público."""
    modelos = (RAIZ / "infrastructure" / "db" / "models.py").read_text(encoding="utf-8")
    assert "sold_total" in modelos, "el total de espectadores es público y se guarda"
    assert "capacity_terraces" in modelos, "el aforo por sector es tu configuración"


def test_el_guardian_reconoce_el_patron_malo() -> None:
    """Sirve de poco si no distingue el código de la explicación."""
    fuente = io.StringIO(
        '"""Aquí vivía sold_terraces, que era SoldTerraces."""\n'
        "# tampoco cuenta sold_basic en un comentario\n"
        "x = 1\n"
    )
    piezas = [
        t.string
        for t in tokenize.generate_tokens(fuente.readline)
        if t.type not in (tokenize.COMMENT, tokenize.STRING) and t.string
    ]
    assert not [p for p in piezas if p in PROHIBIDOS], "una mención no es un uso"

    fuente = io.StringIO("valor = fila.sold_terraces\n")
    piezas = [
        t.string
        for t in tokenize.generate_tokens(fuente.readline)
        if t.type not in (tokenize.COMMENT, tokenize.STRING) and t.string
    ]
    assert "sold_terraces" in piezas, "un uso real sí tiene que saltar"
    assert re.match(r"^\w+$", "sold_terraces")
