"""El banco: puntua el motor contra TODO lo medido, sin gastar una consulta.

PARA QUE SIRVE. Hattrick estrangula a las ~300 consultas y a partir de ahi
devuelve 200 con una pagina sin criterios. Cuando eso pasa, medir produce datos
falsos, que es peor que no tener datos. Pero las pruebas ya guardan ~180
observaciones del juego, y contra eso se puede probar un algoritmo candidato
cuantas veces se quiera, gratis.

ASI SE ENCONTRARON DOS ARREGLOS el 2026-10-12 sin red: el corte del orden por
plantilla y el corte condicional de la banda de la tercera. Los dos mantuvieron
los 177 casos y arreglaron uno de la tanda dura cada uno. En los dos, mi
analisis a mano decia lo contrario de lo que dijo el banco.

COMO SE USA. Se ejecuta desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/banco.py

Para probar un candidato, se escribe una variante de la funcion que se quiera
cambiar, se parchea en `C`, y se vuelve a llamar a `puntua`. Un candidato SOLO
vale si mantiene el total medido y sube los pendientes: si baja aunque sea uno
de los medidos, se descarta sin discusion.
"""

import sys

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/tests")

import test_criterios_hattrick as T  # noqa: E402
from app.domain.engines import criterios_hattrick as C  # noqa: E402


def perfil(**kwargs: int) -> dict[str, int]:
    base = dict(
        keeper=0, defending=0, playmaking=0, winger=0, passing=0, scoring=0, set_pieces=0
    )
    base.update(kwargs)
    return base


#: Todo lo que las pruebas guardan como «esto contesto Hattrick», en un solo
#: sitio y como cadena entera de criterios.
def cadenas() -> list[tuple[int, dict[str, int], str]]:
    casos = [(e, dict(n), s) for _d, e, n, s in T.OBSERVADO]
    casos += [(e, dict(n), s) for _d, e, n, s in T.PLAUSIBLES]
    casos += [
        (25, T.perfil(winger=lat, scoring=ano, defending=defe), s)
        for lat, ano, defe, s in T.ANOTACION_TAPA_LA_DEFENSA
    ]
    casos += [
        (25, T.perfil(winger=18, defending=12, scoring=ano), s)
        for ano, s in T.AL_REVES_NO_TAPA
    ]
    casos += [
        (25, T.perfil(defending=defe, keeper=por), s) for defe, por, s in T.PORTERIA_DEL_DEFENSA
    ]
    casos += [
        (25, T.perfil(defending=defe, passing=pas, keeper=por), s)
        for defe, pas, por, s in T.DIAL_SIN_PORTERIA
    ]
    casos += [
        (25, dict(n), s)
        for n, s in T.REJILLA_DEL_LATERAL + T.ENTRA_CON_TRES + T.ANOTACION_PIDE_CINCO
    ]
    return casos


#: La rejilla de 4x4 del extremo, que se puntua por ORDEN y no por cadena.
def rejilla() -> list[tuple[int, dict[str, int], str]]:
    return [
        (25, T.perfil(winger=10, passing=7, playmaking=jug, scoring=ano), s)
        for (jug, ano), s in sorted(T.REJILLA_DEL_ORDEN.items())
    ]


#: Los 23 ordenes medidos del mediocentro.
def ordenes() -> list[tuple[int, dict[str, int], str]]:
    return [(25, dict(n), s) for n, s in T.ORDENES_DEL_MEDIOCENTRO]


#: Lo que el motor TODAVIA no reproduce, de las tandas de perfiles. Se guarda
#: aqui y no en las pruebas porque las pruebas fijan lo que ya funciona; esto
#: es la lista de deberes, y cada entrada dice de que familia es.
PENDIENTES: list[tuple[str, int, dict[str, int], str]] = [
    (
        "D1#12 orden de la cola, dos topes intercambiados",
        31,
        perfil(playmaking=10, keeper=9, passing=8, scoring=5, winger=4, defending=2, set_pieces=5),
        "Ed=31 Jug=10 Pas=8 Ano 4-6 Lat<=4 Def<=4 Por<=10",
    ),
    (
        "D2#9 entrada del tercero: Defensa 5 con la primera tambien en 5",
        27,
        perfil(winger=5, passing=13, defending=5, keeper=3, set_pieces=3, scoring=1),
        "Ed=27 Lat=5 Pas 12-14 Def<=5 Jug<=4 Ano<=4 Por<=4",
    ),
]


def puntua(nombre: str) -> tuple[int, int]:
    cas, rej, ords = cadenas(), rejilla(), ordenes()
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
    total = len(cas) + len(rej) + len(ords)
    fallan = [d for d, e, n, s in PENDIENTES if T._pinta(C.criterios_de(e, dict(n))) != s]
    print(f"{nombre}")
    print(f"  medido     {bien}/{total}")
    print(f"  pendientes {len(PENDIENTES) - len(fallan)}/{len(PENDIENTES)}")
    for d in fallan:
        print(f"    sigue fallando: {d}")
    return bien, total


if __name__ == "__main__":
    bien, total = puntua("motor actual")
    if bien != total:
        print("\nOJO: hay casos MEDIDOS que el motor no reproduce. Eso es una regresion.")
        sys.exit(1)
