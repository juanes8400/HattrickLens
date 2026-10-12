"""Los cinco ordenes del defensa con el conjunto {Def, Jug, Lat, Pas}.

RESULTADO: no son cinco puestos, son cinco PATRONES DE NIVEL, y el motor actual
los reproduce los cinco. Este script es el que corrigio la prueba mala de
FASE Z: ver FASE Z-BIS en `fase-a.txt`.

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/patron_del_defensa.py


El orden NO es funcion del conjunto: el mismo conjunto sale en cinco ordenes
distintos segun los niveles. Si la hipotesis de los puestos es buena, esos
cinco ordenes son cinco PUESTOS defensivos, y el patron de niveles de cada uno
tiene que ser coherente. Esto saca el patron de lo ya medido, para que el
sondeo por puesto empiece con el mapa a medio hacer.
"""
import sys
from collections import defaultdict

sys.path.insert(0, 'backend'); sys.path.insert(0, 'backend/tests')
sys.path.insert(0, 'docs/reference/sondeo-comparador')
import banco
from app.domain.engines import criterios_hattrick as C

AB = {"keeper": "Por", "defending": "Def", "playmaking": "Jug",
      "winger": "Lat", "passing": "Pas", "scoring": "Ano", "set_pieces": "BP"}

def partes(esperado):
    bruto = esperado.split()
    salida, i = [], 0
    while i < len(bruto):
        t = bruto[i]
        if i + 1 < len(bruto) and "-" in bruto[i + 1] and not any(c in bruto[i + 1] for c in "<>="):
            salida.append(t + " " + bruto[i + 1]); i += 2
        else:
            salida.append(t); i += 1
    return salida

def orden_de(esperado):
    fuera = []
    for t in partes(esperado):
        if t.startswith(("Ed", "Dias")) or "<=" in t:
            continue
        ab = t[:3] if t[:3] in ("Por", "Def", "Jug", "Lat", "Pas", "Ano") else t[:2]
        fuera.append(ab)
    return tuple(fuera)

por_orden = defaultdict(list)
for edad, niveles, esperado in banco.cadenas():
    if C._tipo(dict(niveles)) != "defending":
        continue
    orden = orden_de(esperado)
    if frozenset(orden) != frozenset(("Def", "Jug", "Lat", "Pas")):
        continue
    por_orden[orden].append((edad, niveles))

print(f"ordenes del defensa con el conjunto completo: {len(por_orden)}\n")
for orden in sorted(por_orden):
    casos = por_orden[orden]
    print(f"{','.join(orden)}   ({len(casos)} casos)")
    for edad, n in casos:
        d, p, j, l = n["defending"], n["passing"], n["playmaking"], n["winger"]
        print(f"    Def{d:2d} Pas{p:2d} Jug{j:2d} Lat{l:2d}   (edad {edad})")
    # el patron: que habilidad es la mas alta de las tres companeras
    tres = [("Pas", "passing"), ("Jug", "playmaking"), ("Lat", "winger")]
    cimas = {max(tres, key=lambda t: n[t[1]])[0] for _e, n in casos}
    print(f"    companera mas alta en estos casos: {','.join(sorted(cimas))}\n")
