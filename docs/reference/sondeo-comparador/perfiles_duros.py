"""Segunda tanda de perfiles, la que busca los puntos ciegos de la primera.

`perfiles_plausibles.py` le pone a los jugadores de campo una Porteria de 4
como maximo, y por eso NO cazo el fallo mas gordo del 2026-10-12: a un defensa
con Porteria 7 u 8 se le clavaba la Porteria como segundo criterio. Un
generador que nunca produce un caso no puede delatarlo.

Esta tanda va a por lo que la otra no mira:
  - Porteria alta en jugadores de campo, justo por debajo del sesgo de portero.
  - Empates exactos entre dos y tres habilidades, que es donde el orden falla.
  - Perfiles planos y perfiles de una sola habilidad.
  - Las edades de los bordes: 17, 21, 22, 31, 32, 33.

Se ejecuta desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/perfiles_duros.py
"""

import json
import random
import sys

sys.path.insert(0, 'backend')
from app.domain.engines.criterios_hattrick import _umbral_de_portero, criterios_de

CAMPO = ["defending", "playmaking", "winger", "passing", "scoring"]
TODAS = ["keeper", *CAMPO, "set_pieces"]
BORDES = [17, 21, 22, 31, 32, 33]

ABR = {
    "keeper": "Por",
    "defending": "Def",
    "playmaking": "Jug",
    "winger": "Lat",
    "passing": "Pas",
    "scoring": "Ano",
    "set_pieces": "BP",
}


def pinta(c):
    if c.edad_minima == c.edad_maxima:
        t = [f"Ed={c.edad_minima}"]
    else:
        t = [f"Ed{c.edad_minima}-{c.edad_maxima}"]
    for x in c.habilidades:
        n = ABR[x.habilidad]
        if x.operador == "=":
            t.append(f"{n}={x.minimo}")
        elif x.operador == "banda":
            t.append(f"{n} {x.minimo}-{x.maximo}")
        elif x.operador == ">=":
            t.append(f"{n}>={x.minimo}")
        else:
            t.append(f"{n}<={x.maximo}")
    return " ".join(t)


def con_porteria_alta(r):
    """De campo, con la Porteria justo por debajo de hacerle portero."""
    dom = r.choice(CAMPO)
    nivel = r.randint(10, 18)
    p = {h: r.randint(0, 5) for h in TODAS}
    p[dom] = nivel
    for v in r.sample([h for h in CAMPO if h != dom], 2):
        p[v] = max(0, nivel - r.randint(2, 8))
    if dom == "defending":
        p["keeper"] = max(0, _umbral_de_portero(nivel) - r.randint(1, 3))
    else:
        p["keeper"] = min(nivel - 1, r.randint(6, 13))
    return p


def con_empates(r):
    """Dos o tres habilidades exactamente iguales."""
    dom = r.choice(CAMPO)
    nivel = r.randint(10, 18)
    igual = r.randint(5, nivel - 1)
    p = {h: r.randint(0, 4) for h in TODAS}
    p[dom] = nivel
    p["keeper"] = min(p["keeper"], 3)
    for v in r.sample([h for h in CAMPO if h != dom], r.randint(2, 3)):
        p[v] = igual
    return p


def plano(r):
    nivel = r.randint(6, 14)
    p = {h: nivel for h in TODAS}
    p["keeper"] = min(nivel, 3)
    p[r.choice(CAMPO)] = nivel + r.randint(1, 3)
    return p


def sola(r):
    p = {h: 0 for h in TODAS}
    p[r.choice(CAMPO)] = r.randint(8, 20)
    return p


FAMILIAS = [con_porteria_alta, con_empates, plano, sola]


def genera():
    r = random.Random(20261012)
    perfiles = []
    for i in range(60):
        p = FAMILIAS[i % len(FAMILIAS)](r)
        edad = BORDES[i % len(BORDES)] if i % 3 == 0 else r.randint(17, 33)
        perfiles.append((edad, p))
    return perfiles


if __name__ == "__main__":
    perfiles = genera()
    salida = [
        {"edad": e, "p": p, "modelo": pinta(criterios_de(e, dict(p)))}
        for e, p in perfiles
    ]
    json.dump(salida, open("duros.json", "w", encoding="utf-8"), ensure_ascii=False)
    for i in range(0, 60, 20):
        print("CHUNK", i // 20)
        print(
            json.dumps(
                [{"edad": s["edad"], **{ABR[h].lower(): s["p"][h] for h in s["p"]}} for s in salida[i : i + 20]],
                separators=(",", ":"),
            )
        )
