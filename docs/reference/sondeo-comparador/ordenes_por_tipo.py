"""Cuantos ORDENES distintos hacen falta por tipo: la prueba de la hipotesis.

Se ejecuta desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/ordenes_por_tipo.py

Mide, contra todo lo ya observado y sin gastar una consulta, cuantos ordenes de
prioridad distintos hace falta suponer por tipo de jugador. Es la prueba
cuantitativa de la hipotesis de los PUESTOS: ver FASE Z en `fase-a.txt`.


Cada plantilla observada es un prefijo del orden de prioridad del jugador. Si
dos plantillas se contradicen en el orden relativo de dos habilidades que las
dos contienen, hacen falta DOS ordenes distintos: o sea, dos puestos.

Si cada tipo necesita dos o tres ordenes, eso encaja con que Hattrick tenga dos
o tres puestos por zona --extremo, extremo defensivo, extremo ofensivo-- y la
hipotesis de los puestos gana fuerza. Si necesita diez, la pierde.
"""
import sys
from collections import defaultdict
from itertools import combinations

sys.path.insert(0, 'backend'); sys.path.insert(0, 'backend/tests')
sys.path.insert(0, 'docs/reference/sondeo-comparador')
import banco
import test_criterios_hattrick as T
from app.domain.engines import criterios_hattrick as C

obs = banco.cadenas()
plantillas = defaultdict(set)
for edad, niveles, _esp in obs:
    criterios = C.criterios_de(edad, dict(niveles))
    tipo = C._tipo(dict(niveles))
    orden = tuple(
        T.ABREVIATURA[c.habilidad] for c in criterios.habilidades if c.operador != "<="
    )
    if len(orden) >= 3:  # con menos de tres no hay orden que contradecir
        plantillas[tipo].add(orden)


def pares(orden):
    return {(a, b) for i, a in enumerate(orden) for b in orden[i + 1:]}


def compatibles(uno, otro):
    """Dos plantillas chocan si una pone a antes de b y la otra al contrario."""
    p1, p2 = pares(uno), pares(otro)
    return not any((b, a) in p2 for a, b in p1)


print(f"{'tipo':12s} {'plantillas':>10s} {'choques':>8s} {'ordenes minimos':>16s}")
for tipo in sorted(plantillas):
    ps = sorted(plantillas[tipo])
    choques = sum(1 for a, b in combinations(ps, 2) if not compatibles(a, b))
    # cobertura voraz: cada grupo es un conjunto mutuamente compatible
    grupos: list[list[tuple[str, ...]]] = []
    for p in sorted(ps, key=lambda x: -len(x)):
        for g in grupos:
            if all(compatibles(p, q) for q in g):
                g.append(p)
                break
        else:
            grupos.append([p])
    print(f"{tipo:12s} {len(ps):10d} {choques:8d} {len(grupos):16d}")
    for g in grupos:
        union = sorted({h for p in g for h in p})
        print(f"             grupo: {len(g)} plantillas, habilidades {','.join(union)}")
        for p in g:
            print(f"                {','.join(p)}")
