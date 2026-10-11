"""La tabla de criterios, fijada contra lo que contestó el propio Hattrick.

Cada caso de `OBSERVADO` es un sondeo real del 2026-10-10: un perfil que se le
metió al panel «Editar búsqueda» del Comparador de Transferencias y la lista de
criterios que devolvió, traducida a números con el glosario oficial.

Esto no comprueba que el motor sea coherente consigo mismo: lo comprueba contra
una fuente ajena. Si alguien toca una constante, estas pruebas lo cazan.

Los datos en bruto, con el método y las fronteras que se buscaron por bisección,
están en `docs/reference/sondeo-comparador/`.
"""

from __future__ import annotations

import pytest

from app.domain.engines.criterios_hattrick import (
    Criterios,
    criterios_de,
    es_holgado,
    rareza,
)

ABREVIATURA = {
    "keeper": "Por",
    "defending": "Def",
    "playmaking": "Jug",
    "winger": "Lat",
    "passing": "Pas",
    "scoring": "Ano",
    "set_pieces": "BP",
}


def _pinta(criterios: Criterios) -> str:
    """Los criterios en el mismo formato compacto con que se anotó el sondeo."""
    if criterios.edad_minima == criterios.edad_maxima:
        trozos = [f"Ed={criterios.edad_minima}"]
    else:
        trozos = [f"Ed{criterios.edad_minima}-{criterios.edad_maxima}"]
    for c in criterios.habilidades:
        nombre = ABREVIATURA[c.habilidad]
        if c.operador == "=":
            trozos.append(f"{nombre}={c.minimo}")
        elif c.operador == "banda":
            trozos.append(f"{nombre} {c.minimo}-{c.maximo}")
        elif c.operador == ">=":
            trozos.append(f"{nombre}>={c.minimo}")
        else:
            trozos.append(f"{nombre}<={c.maximo}")
    return " ".join(trozos)


def perfil(
    *,
    keeper: int = 0,
    defending: int = 0,
    playmaking: int = 0,
    winger: int = 0,
    passing: int = 0,
    scoring: int = 0,
    set_pieces: int = 0,
) -> dict[str, int]:
    return {
        "keeper": keeper,
        "defending": defending,
        "playmaking": playmaking,
        "winger": winger,
        "passing": passing,
        "scoring": scoring,
        "set_pieces": set_pieces,
    }


#: (qué es, edad, perfil, lo que contestó Hattrick)
OBSERVADO: list[tuple[str, int, dict[str, int], str]] = [
    # --- Los dos jugadores reales con los que empezó todo ---
    (
        "Moises Llauge, defensa de 29",
        29,
        perfil(
            defending=14, passing=13, winger=11, playmaking=4, scoring=2, keeper=1, set_pieces=6
        ),
        "Ed28-30 Def=14 Pas 12-14 Lat>=11 Jug<=5 Ano<=5 Por<=5",
    ),
    (
        "Anders Ebbesen, portero de 28",
        28,
        perfil(keeper=15, defending=8, scoring=3, playmaking=2, passing=2, winger=1, set_pieces=22),
        "Ed27-29 Por=15 Def 7-9 BP>=14 Lat<=5 Ano<=5 Jug<=5",
    ),
    # --- Los tres operadores de la tercera, con el mismo perfil ---
    (
        "tercera baja, se cae",
        25,
        perfil(defending=16, playmaking=12, passing=4),
        "Ed24-26 Def=16 Jug 11-13 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "tercera media, banda",
        25,
        perfil(defending=16, playmaking=12, passing=8),
        "Ed24-26 Def=16 Jug 11-13 Pas 7-10 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "tercera alta, suelo",
        25,
        perfil(defending=16, playmaking=12, passing=11),
        "Ed24-26 Def=16 Jug 11-13 Pas>=11 Lat<=5 Ano<=5 Por<=5",
    ),
    # --- La segunda: la abre su propio nivel, o la tercera ---
    (
        "segunda clavada",
        25,
        perfil(defending=13, playmaking=9, passing=6),
        "Ed=25 Def=13 Jug=9 Pas 5-7 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "la tercera en 7 abre la segunda",
        25,
        perfil(defending=13, playmaking=9, passing=7),
        "Ed=25 Def=13 Jug 8-10 Pas 6-8 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "segunda en 10, banda sin ayuda",
        25,
        perfil(defending=18, playmaking=10),
        "Ed24-26 Def=18 Jug 9-11 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "segunda en 8, clavada",
        25,
        perfil(defending=18, playmaking=8),
        "Ed24-26 Def=18 Jug=8 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    # --- El dial, en sus dos fronteras medidas ---
    (
        "justo por debajo del dial",
        25,
        perfil(defending=14, playmaking=10, passing=6),
        "Ed=25 Def=14 Jug 9-11 Pas 5-7 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "justo por encima del dial",
        25,
        perfil(defending=14, playmaking=10, passing=7),
        "Ed24-26 Def=14 Jug 9-11 Pas 6-9 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "la primera en 17 afloja sola",
        25,
        perfil(defending=17, playmaking=5),
        "Ed24-26 Def=17 Jug=5 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "la primera en 16 no",
        25,
        perfil(defending=16, playmaking=5),
        "Ed=25 Def=16 Jug=5 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    # --- El reparto de puestos ---
    (
        "el valor manda sobre la plantilla",
        25,
        perfil(defending=16, playmaking=8),
        "Ed=25 Def=16 Jug=8 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "empatadas, manda la plantilla",
        25,
        perfil(defending=16, playmaking=8, passing=8),
        "Ed24-26 Def=16 Pas 7-9 Jug 7-10 Lat<=5 Ano<=5 Por<=5",
    ),
    # --- El tipo Pases, que clava Lateral valga lo que valga ---
    (
        "pasador puro: Lateral primero, en cero",
        25,
        perfil(passing=16),
        "Ed=25 Lat=0 Pas 15-17 Jug<=4 Def<=4 Ano<=4 Por<=4",
    ),
    (
        "pasador con algo de Lateral",
        25,
        perfil(passing=16, winger=12),
        "Ed24-26 Lat=12 Pas 15-17 Jug<=5 Def<=5 Ano<=5 Por<=5",
    ),
    # --- Las plantillas desnudas de cada tipo ---
    (
        "plantilla del portero",
        25,
        perfil(keeper=16),
        "Ed=25 Por=16 Def<=1 BP<=4 Lat<=4 Ano<=4 Jug<=4",
    ),
    (
        "la segunda del portero, clavada en 6",
        25,
        perfil(keeper=15, defending=6),
        "Ed24-26 Por=15 Def=6 BP<=5 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "y con banda ya en 7",
        25,
        perfil(keeper=15, defending=7),
        "Ed24-26 Por=15 Def 6-8 BP<=5 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "el dial del portero salta justo en 21",
        25,
        perfil(keeper=15, defending=5),
        "Ed=25 Por=15 Def=5 BP<=4 Lat<=4 Ano<=4 Jug<=4",
    ),
    (
        "plantilla del defensa",
        25,
        perfil(defending=16),
        "Ed=25 Def=16 Pas<=2 Jug<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "plantilla del medio",
        25,
        perfil(playmaking=16),
        "Ed=25 Jug=16 Pas<=2 Def<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "plantilla del extremo",
        25,
        perfil(winger=16),
        "Ed=25 Lat=16 Jug<=2 Pas<=4 Def<=4 Ano<=4 Por<=4",
    ),
    (
        "plantilla del delantero",
        25,
        perfil(scoring=16),
        "Ed=25 Ano=16 Pas<=2 Lat<=4 Jug<=4 Def<=4 Por<=4",
    ),
    # --- El portero y su balon parado ---
    (
        "balon parado medio, banda ancha",
        25,
        perfil(keeper=15, defending=8, set_pieces=10),
        "Ed24-26 Por=15 Def 7-9 BP 7-13 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "balon parado al tope, suelo fijo",
        25,
        perfil(keeper=15, defending=8, set_pieces=20),
        "Ed24-26 Por=15 Def 7-9 BP>=14 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "el balon parado del portero mueve el dial",
        25,
        perfil(keeper=12, defending=8),
        "Ed=25 Por=12 Def 7-9 BP<=4 Lat<=4 Ano<=4 Jug<=4",
    ),
    (
        "y con el alto, se abre",
        25,
        perfil(keeper=12, defending=8, set_pieces=15),
        "Ed24-26 Por=12 Def 7-9 BP 12-18 Lat<=5 Ano<=5 Jug<=5",
    ),
    # --- La edad, en sus tres zonas ---
    (
        "al joven le aprietan TODA la busqueda",
        20,
        perfil(defending=16, playmaking=12),
        "Ed=20 Def=16 Jug 11-13 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "y a los 22 ya no",
        22,
        perfil(defending=16, playmaking=12),
        "Ed21-23 Def=16 Jug 11-13 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "de viejo se abre la edad pero no el resto",
        32,
        perfil(defending=12, playmaking=9, passing=5),
        "Ed31-33 Def=12 Jug=9 Pas 4-6 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "adelantar cuesta la distancia en la plantilla",
        25,
        perfil(defending=16, passing=7, winger=8),
        "Ed24-26 Def=16 Pas 6-8 Lat 7-10 Jug<=5 Ano<=5 Por<=5",
    ),
    (
        "con un nivel mas, ya adelanta",
        25,
        perfil(defending=16, passing=7, winger=9),
        "Ed24-26 Def=16 Lat 8-10 Pas 6-9 Jug<=5 Ano<=5 Por<=5",
    ),
    (
        "en medio: sigue al dial",
        25,
        perfil(defending=12, playmaking=9),
        "Ed=25 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "viejo: abierta aunque el dial este ajustado",
        32,
        perfil(defending=12, playmaking=9),
        "Ed31-33 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    # --- Los quince de la validacion ciega final: el modulo predijo los quince
    # --- antes de que Hattrick los contestara, y acerto los quince.
    (
        "ciego: lateral con cuarta habilidad",
        26,
        perfil(defending=15, playmaking=5, winger=11, passing=9),
        "Ed25-27 Def=15 Lat 10-12 Pas 8-11 Jug 4-7 Ano<=5 Por<=5",
    ),
    (
        "ciego: medio con empate arriba",
        24,
        perfil(defending=8, playmaking=11, passing=11),
        "Ed=24 Jug=11 Pas 10-12 Def 7-9 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "ciego: delantero joven",
        20,
        perfil(winger=11, passing=9, scoring=13),
        "Ed=20 Ano=13 Lat 10-12 Pas 8-10 Jug<=4 Def<=4 Por<=4",
    ),
    (
        "ciego: extremo viejo",
        32,
        perfil(playmaking=10, winger=14, passing=7),
        "Ed31-33 Lat=14 Jug 9-11 Pas 6-8 Def<=4 Ano<=4 Por<=4",
    ),
    (
        "ciego: portero con balon parado alto",
        27,
        perfil(keeper=16, defending=9, set_pieces=14),
        "Ed26-28 Por=16 Def 8-10 BP 11-17 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "ciego: cuatro habilidades iguales",
        23,
        perfil(defending=10, playmaking=10, winger=10, passing=10),
        "Ed22-24 Lat=10 Jug 9-11 Pas 9-12 Def 8-10 Ano<=5 Por<=5",
    ),
    (
        "ciego: pasador tratado como medio",
        29,
        perfil(playmaking=12, winger=9, passing=15),
        "Ed28-30 Jug=12 Pas 14-16 Lat 8-11 Def<=5 Ano<=5 Por<=5",
    ),
    (
        "ciego: delantero de 18",
        18,
        perfil(passing=7, scoring=11),
        "Ed=18 Ano=11 Pas=7 Lat<=4 Jug<=4 Def<=4 Por<=4",
    ),
    (
        "ciego: defensa con medio alto",
        25,
        perfil(defending=13, playmaking=12, passing=6),
        "Ed24-26 Def=13 Jug 11-13 Pas 5-8 Lat<=5 Ano<=5 Por<=5",
    ),
    (
        "ciego: portero con balon parado bajo",
        30,
        perfil(keeper=13, defending=11, set_pieces=6),
        "Ed29-31 Por=13 Def 10-12 BP 3-9 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "ciego: extremo de 17 con poco mas",
        22,
        perfil(playmaking=3, winger=17, passing=8),
        "Ed21-23 Lat=17 Pas=8 Jug<=5 Def<=5 Ano<=5 Por<=5",
    ),
    (
        "ciego: cuatro a nueve",
        28,
        perfil(defending=9, playmaking=9, winger=9, passing=9),
        "Ed=28 Lat=9 Jug 8-10 Pas 8-10 Def 7-9 Ano<=4 Por<=4",
    ),
    (
        "ciego: goleador de elite",
        31,
        perfil(winger=10, passing=14, scoring=18),
        "Ed30-32 Ano=18 Pas 13-15 Lat 9-12 Jug<=5 Def<=5 Por<=5",
    ),
    (
        "ciego: defensa joven",
        19,
        perfil(defending=14, playmaking=8, passing=6),
        "Ed=19 Def=14 Jug=8 Pas 5-7 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "ciego: extremo y pases empatados",
        25,
        perfil(defending=5, playmaking=7, winger=11, passing=11),
        "Ed=25 Lat=11 Pas 10-12 Jug 6-8 Def 4-6 Ano<=4 Por<=4",
    ),
    # --- El cuarto puesto, barrido con Def 14, Jug 10 y Pases 8 de tercera
    (
        "4o por debajo del 3o",
        25,
        perfil(defending=14, playmaking=10, passing=8, winger=7),
        "Ed24-26 Def=14 Jug 9-11 Pas 7-10 Lat 6-9 Ano<=5 Por<=5",
    ),
    (
        "4o al alcanzar al 3o se abre",
        25,
        perfil(defending=14, playmaking=10, passing=8, winger=8),
        "Ed24-26 Def=14 Jug 9-11 Pas 7-10 Lat 6-11 Ano<=5 Por<=5",
    ),
    (
        "4o por encima del 3o",
        25,
        perfil(defending=14, playmaking=10, passing=8, winger=9),
        "Ed24-26 Def=14 Jug 9-11 Pas 7-10 Lat 7-12 Ano<=5 Por<=5",
    ),
    (
        "y con 10 el 4o ya adelanta al 3o",
        25,
        perfil(defending=14, playmaking=10, passing=8, winger=10),
        "Ed24-26 Def=14 Jug 9-11 Lat 9-12 Pas 6-11 Ano<=5 Por<=5",
    ),
    # --- El techo de los sobrantes, con valor propio
    (
        "sobrante con valor, holgado: v+2",
        25,
        perfil(defending=16, playmaking=12, passing=10, winger=8, scoring=7),
        "Ed24-26 Def=16 Jug 11-13 Pas 9-12 Lat 6-11 Ano<=9 Por<=5",
    ),
    (
        "sobrante con valor, ajustado: v+1",
        25,
        perfil(defending=9, playmaking=8, passing=7, winger=7, scoring=7),
        "Ed=25 Def=9 Jug 7-9 Pas 6-8 Lat 6-8 Ano<=8 Por<=4",
    ),
    # --- El clamp del joven aguanta hasta con un perfil de elite
    (
        "a los 20, ni con Defensa 19 se afloja",
        20,
        perfil(defending=19, playmaking=15),
        "Ed=20 Def=19 Jug 14-16 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "y a los 22 ya se afloja",
        22,
        perfil(defending=19, playmaking=15),
        "Ed21-23 Def=19 Jug 14-16 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    # --- Segunda validacion ciega, doce perfiles nuevos, doce aciertos
    (
        "ciego2: defensa con cuarta alta",
        26,
        perfil(defending=17, playmaking=13, passing=11, winger=9),
        "Ed25-27 Def=17 Jug 12-14 Pas>=11 Lat 7-12 Ano<=5 Por<=5",
    ),
    (
        "ciego2: medio con cuatro",
        24,
        perfil(playmaking=13, passing=10, defending=9, winger=8),
        "Ed23-25 Jug=13 Pas 9-11 Def 8-11 Lat 6-11 Ano<=5 Por<=5",
    ),
    (
        "ciego2: delantero de 21",
        21,
        perfil(scoring=15, passing=12, winger=10),
        "Ed=21 Ano=15 Pas 11-13 Lat 9-11 Jug<=4 Def<=4 Por<=4",
    ),
    (
        "ciego2: portero viejo",
        33,
        perfil(keeper=15, defending=10, set_pieces=11),
        "Ed32-34 Por=15 Def 9-11 BP 8-14 Lat<=5 Ano<=5 Jug<=5",
    ),
    (
        "ciego2: extremo con cinco habilidades",
        28,
        perfil(defending=8, playmaking=11, winger=12, passing=10, scoring=6),
        "Ed27-29 Lat=12 Jug 10-12 Pas 9-12 Def 6-11 Ano<=8 Por<=5",
    ),
    (
        "ciego2: defensa de 19",
        19,
        perfil(defending=11, playmaking=9, passing=8),
        "Ed=19 Def=11 Jug 8-10 Pas 7-9 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "ciego2: pasador de elite",
        30,
        perfil(defending=7, playmaking=13, winger=11, passing=16),
        "Ed29-31 Jug=13 Pas 15-17 Lat>=11 Def 6-9 Ano<=5 Por<=5",
    ),
    (
        "ciego2: empate arriba baja el umbral",
        25,
        perfil(winger=12, passing=8, scoring=12),
        "Ed24-26 Lat=12 Ano 11-13 Pas 7-10 Jug<=5 Def<=5 Por<=5",
    ),
    (
        "ciego2: portero modesto",
        22,
        perfil(keeper=10, defending=7, set_pieces=3),
        "Ed=22 Por=10 Def 6-8 BP<=4 Lat<=4 Ano<=4 Jug<=4",
    ),
    (
        "ciego2: tres a ocho detras de un 16",
        31,
        perfil(defending=16, playmaking=8, winger=8, passing=8),
        "Ed30-32 Def=16 Pas 7-9 Jug 7-10 Lat 6-11 Ano<=5 Por<=5",
    ),
    (
        "ciego2: medio de 18",
        18,
        perfil(defending=6, playmaking=12, passing=9),
        "Ed=18 Jug=12 Pas=9 Def 5-7 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "ciego2: extremo completo",
        27,
        perfil(defending=11, playmaking=12, winger=14, passing=13),
        "Ed26-28 Lat=14 Pas 12-14 Jug>=12 Def 9-14 Ano<=5 Por<=5",
    ),
    # --- El cuarto puesto se corta en la PRIMERA habilidad (2026-10-10)
    ("4o cortado por la primera, en 9", 25,
     perfil(defending=9, playmaking=8, passing=8, winger=8),
     "Ed=25 Def=9 Pas 7-9 Jug 7-9 Lat 6-9 Ano<=4 Por<=4"),
    ("y subiendo solo la primera a 10, el corte sube", 25,
     perfil(defending=10, playmaking=8, passing=8, winger=8),
     "Ed=25 Def=10 Pas 7-9 Jug 7-9 Lat 6-10 Ano<=4 Por<=4"),
    ("con la segunda en 9 el reparto cambia pero el corte sigue", 25,
     perfil(defending=9, playmaking=9, passing=8, winger=8),
     "Ed=25 Def=9 Jug 8-10 Pas 7-9 Lat 6-9 Ano<=4 Por<=4"),
    # --- Un cuarto criterio de identidad baja el liston del dial (2026-10-10)
    ("ciego3: delantero con cuatro habilidades", 28,
     perfil(scoring=11, passing=10, winger=9, playmaking=8),
     "Ed27-29 Ano=11 Pas 9-11 Lat 8-11 Jug 6-11 Def<=5 Por<=5"),
    ("ciego3: defensa con cuatro a nueve", 25,
     perfil(defending=11, playmaking=9, passing=9, winger=9),
     "Ed24-26 Def=11 Pas 8-10 Jug 8-11 Lat 7-11 Ano<=5 Por<=5"),
    ("ciego3: extremo completo", 25,
     perfil(defending=8, playmaking=10, winger=12, passing=9),
     "Ed24-26 Lat=12 Jug 9-11 Pas 8-11 Def 6-11 Ano<=5 Por<=5"),
    ("ciego3: medio con cuatro", 24,
     perfil(defending=9, playmaking=13, winger=8, passing=11),
     "Ed23-25 Jug=13 Pas 10-12 Def 8-11 Lat 6-11 Ano<=5 Por<=5"),
    ("ciego3: lateral con suelo en la tercera", 26,
     perfil(defending=14, playmaking=8, winger=11, passing=12),
     "Ed25-27 Def=14 Pas 11-13 Lat>=11 Jug 6-11 Ano<=5 Por<=5"),
    ("ciego3: chaval de 17", 17, perfil(defending=10, playmaking=8),
     "Ed=17 Def=10 Jug=8 Pas<=4 Lat<=4 Ano<=4 Por<=4"),
    # --- La edad de los mayores: suelo abierto, no ventana (2026-10-11)
    ("a los 34 todavia es ventana", 34, perfil(defending=12, playmaking=9),
     "Ed33-35 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4"),
    ("a los 35 se abre por arriba y no se cierra", 35, perfil(defending=12, playmaking=9),
     "Ed35-99 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4"),
    ("y a los 40 sigue siendo el mismo suelo", 40, perfil(defending=12, playmaking=9),
     "Ed35-99 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4"),
    ("pero con la busqueda holgada sigue siendo ventana", 35,
     perfil(defending=16, playmaking=12),
     "Ed34-36 Def=16 Jug 11-13 Pas<=5 Lat<=5 Ano<=5 Por<=5"),
    # --- Al pasador la edad no se le abre a los 32 (2026-10-11)
    ("el perfil que mando el usuario, clavado", 23,
     perfil(keeper=1, defending=10, playmaking=3, winger=4, passing=10, scoring=3, set_pieces=6),
     "Ed=23 Def=10 Pas 9-11 Lat<=4 Jug<=4 Ano<=4 Por<=4"),
    ("pasador de 33: edad clavada", 33, perfil(passing=13, playmaking=7, defending=5),
     "Ed=33 Jug=7 Pas 12-14 Def 4-6 Lat<=4 Ano<=4 Por<=4"),
    ("pasador de 34: todavia clavada", 34, perfil(passing=13, playmaking=7, defending=5),
     "Ed=34 Jug=7 Pas 12-14 Def 4-6 Lat<=4 Ano<=4 Por<=4"),
    ("pero al medio de 33 si se le abre", 33, perfil(playmaking=13, passing=7, defending=5),
     "Ed32-34 Jug=13 Pas=7 Def 4-6 Lat<=4 Ano<=4 Por<=4"),
    ("y al pasador a los 35 tambien se le abre el suelo", 35,
     perfil(passing=13, playmaking=7, defending=5),
     "Ed35-99 Jug=7 Pas 12-14 Def 4-6 Lat<=4 Ano<=4 Por<=4"),
    # --- Cada tipo tiene su juego de habilidades elegibles (2026-10-11)
    ("al defensa NO se le compara por Anotacion, ni con 9", 25,
     perfil(defending=12, passing=10, scoring=9),
     "Ed=25 Def=12 Pas 9-11 Jug<=4 Lat<=4 Ano<=10 Por<=4"),
    ("pero al extremo si, ya con 5", 25,
     perfil(winger=10, passing=7, playmaking=5, scoring=5),
     "Ed=25 Lat=10 Pas=7 Jug 4-6 Ano 4-6 Def<=4 Por<=4"),
    # --- La rejilla fina de la tercera contra la cuarta
    ("tercera y cuarta en 4: las dos a tope", 25,
     perfil(defending=12, passing=10, playmaking=4, winger=4),
     "Ed=25 Def=12 Pas 9-11 Jug<=4 Lat<=4 Ano<=4 Por<=4"),
    ("las dos en 5: las dos con banda", 25,
     perfil(defending=12, passing=10, playmaking=5, winger=5),
     "Ed=25 Def=12 Pas 9-11 Jug 4-6 Lat 4-6 Ano<=4 Por<=4"),
    ("la cuarta en 6 empuja el dial", 25,
     perfil(defending=12, passing=10, playmaking=6, winger=7),
     "Ed24-26 Def=12 Pas 9-11 Lat 6-9 Jug 5-8 Ano<=5 Por<=5"),
    ("sin cuarta no lo empuja", 25,
     perfil(defending=12, passing=10, playmaking=6, winger=6),
     "Ed=25 Def=12 Pas 9-11 Jug 5-7 Lat 5-7 Ano<=4 Por<=4"),
    ("lo que no puede ser criterio tampoco cuenta para la rareza", 25,
     perfil(defending=12, passing=10, scoring=9),
     "Ed=25 Def=12 Pas 9-11 Jug<=4 Lat<=4 Ano<=10 Por<=4"),
    # --- En el extremo, Defensa y Anotacion pesan lo mismo (2026-10-11)
    ("extremo real: Defensa adelanta a Jugadas por nivel", 29,
     perfil(winger=15, defending=13, playmaking=11, passing=11),
     "Ed28-30 Lat=15 Def 12-14 Jug>=11 Pas 9-14 Ano<=5 Por<=5"),
]


@pytest.mark.parametrize(
    ("que_es", "edad", "niveles", "esperado"),
    OBSERVADO,
    ids=[caso[0] for caso in OBSERVADO],
)
def test_reproduce_lo_que_contesto_hattrick(
    que_es: str, edad: int, niveles: dict[str, int], esperado: str
) -> None:
    assert _pinta(criterios_de(edad, niveles)) == esperado, que_es


def test_a_los_diecisiete_hay_tope_de_dias() -> None:
    """Y solo a los diecisiete. El panel no tiene campo de dias, asi que el 24
    esta observado pero no entendido."""
    assert criterios_de(17, perfil(defending=12, playmaking=9)).tope_de_dias == 24
    assert criterios_de(18, perfil(defending=12, playmaking=9)).tope_de_dias is None


def test_el_balon_parado_no_toca_al_jugador_de_campo() -> None:
    """Medido: Defensa 14 y Jugadas 10 dan lo mismo con balon parado 0, 12 o 20."""
    sin = criterios_de(25, perfil(defending=14, playmaking=10))
    for nivel in (12, 20):
        con = criterios_de(25, perfil(defending=14, playmaking=10, set_pieces=nivel))
        assert _pinta(con) == _pinta(sin)


def test_la_rareza_solo_cuenta_cuatro_habilidades() -> None:
    """Con seis habilidades a 9 sigue ajustado, y con cuatro a 10 no.

    Es lo que corrigio la validacion ciega: la suma no acumula sin fin.
    """
    seis_a_nueve = perfil(defending=9, playmaking=9, winger=9, passing=9, scoring=9, keeper=9)
    assert not es_holgado(seis_a_nueve)
    assert rareza(seis_a_nueve) == 24
    cuatro_a_diez = perfil(defending=10, playmaking=10, winger=10, passing=10)
    assert es_holgado(cuatro_a_diez)


def test_el_portero_afloja_antes_que_el_jugador_de_campo() -> None:
    """Veintiuno contra veinticinco, medido por biseccion en los dos."""
    assert not es_holgado(perfil(keeper=12, defending=8))
    assert es_holgado(perfil(keeper=13, defending=8))
    assert not es_holgado(perfil(defending=16, playmaking=8))
    assert es_holgado(perfil(defending=16, playmaking=9))


# --- El orden cuando la tercera y la cuarta compiten de cerca ---------------

#: Rejilla de 4x4 sondeada el 2026-10-11 sobre un extremo con Lateral 10 y
#: Pases 7 fijos, moviendo Jugadas y Anotacion de 5 a 8. Es la que obligo a
#: darle al extremo un orden de desempate propio, con Anotacion por delante de
#: Defensa: los dieciseis salen con ella en la posicion 3 y ninguno con la 4.
REJILLA_DEL_ORDEN = {
    (5, 5): "Lat Pas Jug Ano Def. Por.",
    (5, 6): "Lat Pas Jug Ano Def. Por.",
    (5, 7): "Lat Pas Ano Jug Def. Por.",
    (5, 8): "Lat Ano Pas Jug Def. Por.",
    (6, 5): "Lat Pas Jug Ano Def. Por.",
    (6, 6): "Lat Pas Jug Ano Def. Por.",
    (6, 7): "Lat Pas Jug Ano Def. Por.",
    (6, 8): "Lat Ano Pas Jug Def. Por.",
    (7, 5): "Lat Jug Pas Ano Def. Por.",
    (7, 6): "Lat Jug Pas Ano Def. Por.",
    (7, 7): "Lat Jug Pas Ano Def. Por.",
    (7, 8): "Lat Jug Ano Pas Def. Por.",
    (8, 5): "Lat Jug Pas Ano Def. Por.",
    (8, 6): "Lat Jug Pas Ano Def. Por.",
    (8, 7): "Lat Jug Pas Ano Def. Por.",
    (8, 8): "Lat Jug Ano Pas Def. Por.",
}


@pytest.mark.parametrize(("par", "esperado"), sorted(REJILLA_DEL_ORDEN.items()))
def test_el_orden_de_la_tercera_y_la_cuarta(par: tuple[int, int], esperado: str) -> None:
    """IMPORTA PARA LA BUSQUEDA, no solo para la pantalla: `transfersearch`
    acepta tres filtros de habilidad, asi que el orden decide CUALES TRES le
    pedimos al mercado. Equivocarlo es pedir otra cosa."""
    jugadas, anotacion = par
    criterios = criterios_de(
        25, perfil(winger=10, passing=7, playmaking=jugadas, scoring=anotacion)
    )
    leido = " ".join(
        ABREVIATURA[c.habilidad] + ("." if c.operador == "<=" else "")
        for c in criterios.habilidades
    )
    assert leido == esperado
