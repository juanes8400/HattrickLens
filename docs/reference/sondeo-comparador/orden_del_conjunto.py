"""¿El ORDEN depende solo del CONJUNTO de criterios, y no de los niveles?

RESPUESTA: NO. Siete de diecisiete grupos salen en mas de un orden. Se deja en
el repo porque es la prueba que descarta el atajo --«elegir el conjunto y
ordenarlo con una tabla»-- y porque hay que volver a pasarla cuando entren
observaciones nuevas.

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/orden_del_conjunto.py


Si fuera asi, el mecanismo quedaria descrito del todo: primero se elige QUE
habilidades son criterio --cosa que ya sabemos hacer, con los umbrales-- y
luego se ordenan con una tabla por (tipo, conjunto). Y esa tabla es finita y
enumerable, o sea que el mecanismo pasaria de «reglas locales» a «mecanismo».

Se comprueba agrupando las observaciones por (tipo, conjunto de criterios) y
viendo si el ORDEN es siempre el mismo dentro de cada grupo. Un solo grupo con
dos ordenes distintos lo refuta.
"""
import sys
from collections import defaultdict

sys.path.insert(0, 'backend'); sys.path.insert(0, 'backend/tests')
sys.path.insert(0, 'docs/reference/sondeo-comparador')
import banco
import test_criterios_hattrick as T
from app.domain.engines import criterios_hattrick as C

#: Se usa la CADENA OBSERVADA, no la del motor: lo que se estudia es Hattrick.
def orden_observado(esperado: str) -> tuple[str, ...]:
    fuera = []
    for trozo in esperado.split():
        if trozo.startswith(("Ed", "Dias")):
            continue
        for ab in ("Por", "Def", "Jug", "Lat", "Pas", "Ano", "BP"):
            if trozo.startswith(ab):
                if "<=" not in trozo:
                    fuera.append(ab)
                break
    return tuple(fuera)

#: Las cadenas vienen con los rangos pegados --«Pas 12-14»-- asi que hay que
#: rearmarlas antes de leerlas. Se reconstruye desde el formato de `_pinta`.
def partes(esperado: str) -> list[str]:
    bruto = esperado.split()
    salida, i = [], 0
    while i < len(bruto):
        t = bruto[i]
        if i + 1 < len(bruto) and "-" in bruto[i + 1] and not any(
            c in bruto[i + 1] for c in "<>="
        ):
            salida.append(t + " " + bruto[i + 1])
            i += 2
        else:
            salida.append(t)
            i += 1
    return salida

def orden_de(esperado: str) -> tuple[str, ...]:
    fuera = []
    for t in partes(esperado):
        if t.startswith(("Ed", "Dias")):
            continue
        ab = t[:3] if t[:3] in ("Por", "Def", "Jug", "Lat", "Pas", "Ano") else t[:2]
        if "<=" in t:
            continue
        fuera.append(ab)
    return tuple(fuera)

grupos = defaultdict(set)
for edad, niveles, esperado in banco.cadenas():
    tipo = C._tipo(dict(niveles))
    orden = orden_de(esperado)
    if len(orden) >= 3:
        grupos[(tipo, frozenset(orden))].add(orden)

iguales = [g for g, ordenes in grupos.items() if len(ordenes) == 1]
distintos = {g: o for g, o in grupos.items() if len(o) > 1}
print(f"grupos (tipo, conjunto) con tres o mas criterios: {len(grupos)}")
print(f"  con UN solo orden:        {len(iguales)}")
print(f"  con mas de un orden:      {len(distintos)}")
if distintos:
    print("\nREFUTADO. El orden NO es funcion del conjunto. Los contraejemplos:")
    for (tipo, conjunto), ordenes in distintos.items():
        print(f"  {tipo} {{{','.join(sorted(conjunto))}}}:")
        for o in sorted(ordenes):
            print(f"      {','.join(o)}")
else:
    print("\nNO REFUTADO con lo medido: cada conjunto sale siempre en el mismo orden.")
