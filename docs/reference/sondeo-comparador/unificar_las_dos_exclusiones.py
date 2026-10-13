"""Las dos exclusiones en espejo: siete intentos de convertirlas en UNA.

POR QUE. El 2026-10-12 el banco llego a 380/380 sin pendientes, y lo unico que
quedaba flojo era esto: el motor tiene DOS reglas de exclusion para DOS tipos,

    el EXTREMO pierde los PASES si no alcanzan a la Anotacion
    el MEDIOCENTRO pierde la ANOTACION si no supera al Lateral

y una sola tendria mejor pinta. Si el mecanismo de Hattrick es uno, deberia
haber una regla.

QUE SALIO. Las siete candidatas pierden casos, y las dos mejores pierden SEIS
cuando NO TENER REGLA pierde ocho. O sea: ninguna unificacion de esta familia
aporta casi nada sobre no tener nada.

    dos reglas separadas (motor actual)                        380/380
    C  cae la penultima si no alcanza a la ultima              374
    G  cae la que no alcanza a la anterior en `con_defensa`    374
    Z  NINGUNA EXCLUSION (control)                             372
    F  cae la estrictamente mas baja de las dos ultimas        372
    B  cae la mas baja de las dos ultimas, empate a la primera 367
    H  como G, y el empate tambien cae                         367
    D  cae la ultima si no supera a la penultima               365
    E  cae la que no alcanza a la siguiente de la plantilla     316

DONDE SE ATASCAN TODAS. En la fuerza del empate, que es distinta en cada tipo:

    extremo      Pas 8 = Ano 8  ->  los Pases SE QUEDAN   (hace falta >=)
    mediocentro  Ano 8 = Lat 8  ->  la Anotacion SE VA    (hace falta >)

Cualquier regla con una sola direccion de empate pierde uno de los dos. Se
probo tambien resolver el empate por la clave `nivel - importancia` de la lista
`con_defensa`, y tampoco: ahi los Pases del extremo salen con peor clave que la
Anotacion y tendrian que caer, y Hattrick los lista.

QUE HARIA FALTA PARA SALIR DE AQUI. No mas analisis: mas tipos. El defensa y el
delantero no se han sondeado para esto, y si tienen su propia exclusion, la
forma de las cuatro juntas dira si hay una regla o si de verdad son una por
tipo. El sondeo esta disenado en fase-a.txt, FASE AH.

COMO SE USA, desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/unificar_las_dos_exclusiones.py

Para probar una candidata nueva se escribe una funcion `(tipo, niveles) ->
frozenset` y se anade a CANDIDATAS. Solo vale si llega a 380/380.
"""

import sys

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/tests")
sys.path.insert(0, "docs/reference/sondeo-comparador")

import banco  # noqa: E402

from app.domain.engines import criterios_hattrick as C  # noqa: E402

ORIGINAL = C._fuera_con_defensa


def utiles(tipo: str) -> list[str]:
    """La plantilla sin la Defensa, sin la del tipo y sin lo que nunca cuenta."""
    return [
        h
        for h in C.PLANTILLAS[tipo]
        if h not in ("defending", tipo, "keeper", C.BALON_PARADO)
    ]


def lista_con_defensa(tipo: str) -> list[str]:
    pesos = C.ORDEN_DE_IMPORTANCIA.get(tipo + "_con_defensa")
    if not pesos:
        return []
    plantilla = C.PLANTILLAS[tipo]
    return sorted(utiles(tipo), key=lambda h: (pesos[h], plantilla.index(h)))


def B(tipo, niveles):
    par = utiles(tipo)[-2:]
    if len(par) < 2:
        return frozenset()
    a, b = par
    return frozenset({b}) if niveles.get(b, 0) <= niveles.get(a, 0) else frozenset({a})


def Cc(tipo, niveles):
    par = utiles(tipo)[-2:]
    if len(par) < 2:
        return frozenset()
    a, b = par
    return frozenset({a}) if niveles.get(a, 0) < niveles.get(b, 0) else frozenset()


def D(tipo, niveles):
    par = utiles(tipo)[-2:]
    if len(par) < 2:
        return frozenset()
    a, b = par
    return frozenset({b}) if niveles.get(b, 0) <= niveles.get(a, 0) else frozenset()


def E(tipo, niveles):
    orden = utiles(tipo)
    return frozenset(
        a for a, b in zip(orden, orden[1:]) if niveles.get(a, 0) < niveles.get(b, 0)
    )


def F(tipo, niveles):
    par = utiles(tipo)[-2:]
    if len(par) < 2:
        return frozenset()
    a, b = par
    if niveles.get(a, 0) < niveles.get(b, 0):
        return frozenset({a})
    if niveles.get(b, 0) < niveles.get(a, 0):
        return frozenset({b})
    return frozenset()


def G(tipo, niveles):
    orden = lista_con_defensa(tipo)
    return frozenset(
        b for a, b in zip(orden, orden[1:]) if niveles.get(b, 0) < niveles.get(a, 0)
    )


def H(tipo, niveles):
    orden = lista_con_defensa(tipo)
    return frozenset(
        b for a, b in zip(orden, orden[1:]) if niveles.get(b, 0) <= niveles.get(a, 0)
    )


def Z(tipo, niveles):
    return frozenset()


CANDIDATAS = [
    ("dos reglas separadas (motor actual)", ORIGINAL),
    ("B  cae la mas baja de las dos ultimas, el empate a la primera", B),
    ("C  cae la penultima si no alcanza a la ultima", Cc),
    ("D  cae la ultima si no supera a la penultima", D),
    ("E  cae la que no alcanza a la siguiente de la plantilla", E),
    ("F  cae la estrictamente mas baja de las dos ultimas", F),
    ("G  cae la que no alcanza a la anterior de la lista con_defensa", G),
    ("H  como G, y el empate tambien cae", H),
    ("Z  NINGUNA exclusion (control)", Z),
]


def main() -> None:
    import io

    for nombre, f in CANDIDATAS:
        C._fuera_con_defensa = f
        try:
            salida = io.StringIO()
            real, sys.stdout = sys.stdout, salida
            try:
                bien, total = banco.puntua(nombre)
            finally:
                sys.stdout = real
        finally:
            C._fuera_con_defensa = ORIGINAL
        marca = "  <-- unifica" if bien == total and f is not ORIGINAL else ""
        print(f"  {bien}/{total}  {nombre}{marca}")


if __name__ == "__main__":
    main()
