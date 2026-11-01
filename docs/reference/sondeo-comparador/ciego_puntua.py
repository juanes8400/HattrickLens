"""Puntua la prueba a ciegas: la prediccion commiteada contra lo que midio Hattrick.

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/ciego_puntua.py

Lee `ciego-prediccion.json` --escrito y commiteado ANTES de medir-- y
`ciego-medido.txt` --las respuestas copiadas literal-- y traduce las segundas al
mismo formato compacto para compararlas. La traduccion es mecanica: nombre de
nivel a numero y operador a simbolo, sin tocar nada mas.
"""

import json
import pathlib
import re
import sys

sys.path.insert(0, "backend")

from app.domain.value_objects.ht_constants import SKILL_LEVELS  # noqa: E402

AQUI = pathlib.Path(__file__).parent
NIVEL = {n: i for i, n in enumerate(SKILL_LEVELS)}
ABR = {
    "Portería": "Por", "Defensa": "Def", "Jugadas": "Jug", "Lateral": "Lat",
    "Pases": "Pas", "Anotación": "Ano", "Balón parado": "BP",
}
HABILIDADES = "|".join(ABR)


def compacta(lineas: list[str]) -> str:
    """Las lineas de la pantalla, en el formato compacto del sondeo."""
    trozos = []
    for linea in lineas:
        linea = linea.strip()
        if not linea or linea.startswith("("):
            continue
        if m := re.fullmatch(r"Edad = (\d+)", linea):
            trozos.append(f"Ed={m[1]}")
        elif m := re.fullmatch(r"Edad >= (\d+) y Edad <= (\d+)", linea):
            trozos.append(f"Ed{m[1]}-{m[2]}")
        elif m := re.fullmatch(r"Edad >= (\d+)", linea):
            trozos.append(f"Ed>={m[1]}")
        elif m := re.fullmatch(rf"({HABILIDADES}) = (.+)", linea):
            trozos.append(f"{ABR[m[1]]}={NIVEL[m[2]]}")
        elif m := re.fullmatch(rf"({HABILIDADES}) entre (.+) y (.+)", linea):
            trozos.append(f"{ABR[m[1]]} {NIVEL[m[2]]}-{NIVEL[m[3]]}")
        elif m := re.fullmatch(rf"({HABILIDADES}) <= (.+)", linea):
            trozos.append(f"{ABR[m[1]]}<={NIVEL[m[2]]}")
        elif m := re.fullmatch(rf"({HABILIDADES}) >= (.+)", linea):
            trozos.append(f"{ABR[m[1]]}>={NIVEL[m[2]]}")
        else:
            raise SystemExit(f"no se como leer esta linea: {linea!r}")
    return " ".join(trozos)


def medido() -> dict[int, str]:
    bloques: dict[int, list[str]] = {}
    actual = None
    for linea in (AQUI / "ciego-medido.txt").read_text(encoding="utf-8").splitlines():
        if linea.startswith("#"):
            continue
        if m := re.fullmatch(r"C(\d+)", linea.strip()):
            actual = int(m[1])
            bloques[actual] = []
        elif re.fullmatch(r"[A-Z]+\d+", linea.strip()):
            # Otro bloque que no es del ciego --las sondas `K` del portero, que
            # se eligieron MIRANDO el fallo y no pueden contar como ciegas--.
            actual = None
        elif actual is not None:
            bloques[actual].append(linea)
    return {n: compacta(ls) for n, ls in bloques.items()}


datos = json.loads((AQUI / "ciego-prediccion.json").read_text(encoding="utf-8"))
real = medido()

bien = fallos = 0
pendientes = []
for caso in datos["casos"]:
    n = caso["n"]
    if n not in real:
        pendientes.append(n)
        continue
    if caso["prediccion"] == real[n]:
        bien += 1
    else:
        fallos += 1
        print(f"C{n:02d}  Edad {caso['edad']}")
        print(f"   predicho  {caso['prediccion']}")
        print(f"   Hattrick  {real[n]}")

total = bien + fallos
print(f"\nFUERA DE MUESTRA: {bien}/{total} exactas", end="")
if total:
    print(f"  ({100 * bien / total:.1f} %)  --  {fallos} fallos")
if pendientes:
    print(f"sin medir todavia: {len(pendientes)} casos ({pendientes[0]}-{pendientes[-1]})")
