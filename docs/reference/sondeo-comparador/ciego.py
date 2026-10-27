"""LA PRUEBA A CIEGAS: cincuenta perfiles nuevos, predichos ANTES de medir.

Por que hace falta. El banco puntua 612/612, pero eso es EN MUESTRA: las reglas
salieron de esas mismas mediciones, asi que el 100 % es circular y no dice nada
del error real. Un porcentaje honesto pide perfiles que nadie haya visto,
predichos por escrito antes de preguntarle a Hattrick, y puntuados despues sin
tocar la prediccion.

Semilla distinta a la de `perfiles_plausibles.py` a proposito: aquellos sesenta
ya estan en el banco y por tanto en muestra.

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/ciego.py

Escribe `ciego-prediccion.json` --que se commitea ANTES de medir, para que la
prediccion no se pueda retocar-- e imprime la tabla que se le pasa a quien mida,
SIN las predicciones.
"""

import json
import pathlib
import random
import sys

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/tests")

from test_criterios_hattrick import _pinta  # noqa: E402

from app.domain.engines.criterios_hattrick import criterios_de  # noqa: E402

HS = ["keeper", "defending", "playmaking", "winger", "passing", "scoring"]
VECINAS = {
    "keeper": ["defending", "set_pieces"],
    "defending": ["playmaking", "passing", "winger", "keeper"],
    "playmaking": ["passing", "defending", "winger", "scoring"],
    "winger": ["passing", "playmaking", "defending", "scoring"],
    "scoring": ["passing", "winger", "playmaking", "set_pieces"],
}
ABR = {"keeper": "Por", "defending": "Def", "playmaking": "Jug", "winger": "Lat",
       "passing": "Pas", "scoring": "Ano", "set_pieces": "BP"}
ORDEN = ["keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"]

CUANTOS = 50
SEMILLA = 20261026

r = random.Random(SEMILLA)
casos = []
for _ in range(CUANTOS):
    tipo = r.choice(list(VECINAS))
    dom = r.randint(8, 18)
    p = {h: 0 for h in HS}
    p["set_pieces"] = 0
    p[tipo] = dom
    for v in r.sample(VECINAS[tipo], r.randint(1, min(3, len(VECINAS[tipo])))):
        p[v] = max(0, dom - r.randint(1, 7))
    for h in ORDEN:
        if p[h] == 0:
            p[h] = r.randint(0, 6)
    p[tipo] = dom
    if tipo != "keeper":
        p["keeper"] = min(p["keeper"], 4)
    casos.append((r.randint(18, 33), p))

prediccion = [
    {"n": i + 1, "edad": edad, "perfil": p, "prediccion": _pinta(criterios_de(edad, dict(p)))}
    for i, (edad, p) in enumerate(casos)
]
destino = pathlib.Path("docs/reference/sondeo-comparador/ciego-prediccion.json")
destino.write_text(
    json.dumps({"semilla": SEMILLA, "casos": prediccion}, ensure_ascii=False, indent=1),
    encoding="utf-8",
)

for c in prediccion:
    cosas = " ".join(f"{ABR[h]}={c['perfil'][h]}" for h in ORDEN)
    print(f"C{c['n']:02d} | Edad={c['edad']} {cosas}")
