"""Los sesenta perfiles plausibles de la FASE R, con semilla fija.

Genera los mismos sesenta siempre, para poder volver a puntuar el motor contra
Hattrick despues de cambiarlo. Se ejecuta desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/perfiles_plausibles.py

Imprime los perfiles en una linea --para pegarlos en el sondeo del navegador--
y escribe `perfiles.json` con lo que predice el motor para cada uno.
"""

import json
import random
import sys

sys.path.insert(0, 'backend')
from app.domain.engines.criterios_hattrick import criterios_de

HS = ["keeper","defending","playmaking","winger","passing","scoring"]
# Perfiles plausibles: una dominante, una o dos companeras cerca, el resto bajo.
# Por tipo, las companeras se eligen de las que un jugador de ese puesto
# entrena de verdad, para que el perfil se parezca a uno de mercado.
VECINAS = {
    "keeper":     ["defending","set_pieces"],
    "defending":  ["playmaking","passing","winger","keeper"],
    "playmaking": ["passing","defending","winger","scoring"],
    "winger":     ["passing","playmaking","defending","scoring"],
    "scoring":    ["passing","winger","playmaking","set_pieces"],
}
r = random.Random(20261012)
perfiles = []
for _ in range(60):
    tipo = r.choice(list(VECINAS))
    dom = r.randint(8, 18)
    p = {h: 0 for h in HS}
    p["set_pieces"] = 0
    p[tipo] = dom
    for v in r.sample(VECINAS[tipo], r.randint(1, min(3, len(VECINAS[tipo])))):
        p[v] = max(0, dom - r.randint(1, 7))
    for h in HS + ["set_pieces"]:
        if p[h] == 0:
            p[h] = r.randint(0, 6)
    p[tipo] = dom
    # que la dominante siga mandando y el portero no se cuele por el sesgo
    if tipo != "keeper":
        p["keeper"] = min(p["keeper"], 4)
    edad = r.randint(17, 33)
    perfiles.append((edad, p))

ABR = {"keeper":"Por","defending":"Def","playmaking":"Jug","winger":"Lat",
       "passing":"Pas","scoring":"Ano","set_pieces":"BP"}

def pinta(c):
    t = [f"Ed={c.edad_minima}" if c.edad_minima==c.edad_maxima else f"Ed{c.edad_minima}-{c.edad_maxima}"]
    for x in c.habilidades:
        n = ABR[x.habilidad]
        if x.operador == "=": t.append(f"{n}={x.minimo}")
        elif x.operador == "banda": t.append(f"{n} {x.minimo}-{x.maximo}")
        elif x.operador == ">=": t.append(f"{n}>={x.minimo}")
        else: t.append(f"{n}<={x.maximo}")
    return " ".join(t)

salida = []
for edad, p in perfiles:
    c = criterios_de(edad, dict(p))
    salida.append({"edad": edad, "p": p, "modelo": pinta(c),
                   "tres": [ABR[x.habilidad] for x in c.habilidades][:3]})
json.dump(salida, open('perfiles.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(json.dumps([{"e":s["edad"],**{ABR[h]:s["p"][h] for h in s["p"]}} for s in salida], ensure_ascii=False))
