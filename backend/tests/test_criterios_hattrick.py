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
    _puestos,
    _tipo,
    _umbral_de_portero,
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
    (
        "4o cortado por la primera, en 9",
        25,
        perfil(defending=9, playmaking=8, passing=8, winger=8),
        "Ed=25 Def=9 Pas 7-9 Jug 7-9 Lat 6-9 Ano<=4 Por<=4",
    ),
    (
        "y subiendo solo la primera a 10, el corte sube",
        25,
        perfil(defending=10, playmaking=8, passing=8, winger=8),
        "Ed=25 Def=10 Pas 7-9 Jug 7-9 Lat 6-10 Ano<=4 Por<=4",
    ),
    (
        "con la segunda en 9 el reparto cambia pero el corte sigue",
        25,
        perfil(defending=9, playmaking=9, passing=8, winger=8),
        "Ed=25 Def=9 Jug 8-10 Pas 7-9 Lat 6-9 Ano<=4 Por<=4",
    ),
    # --- Un cuarto criterio de identidad baja el liston del dial (2026-10-10)
    (
        "ciego3: delantero con cuatro habilidades",
        28,
        perfil(scoring=11, passing=10, winger=9, playmaking=8),
        "Ed27-29 Ano=11 Pas 9-11 Lat 8-11 Jug 6-11 Def<=5 Por<=5",
    ),
    (
        "ciego3: defensa con cuatro a nueve",
        25,
        perfil(defending=11, playmaking=9, passing=9, winger=9),
        "Ed24-26 Def=11 Pas 8-10 Jug 8-11 Lat 7-11 Ano<=5 Por<=5",
    ),
    (
        "ciego3: extremo completo",
        25,
        perfil(defending=8, playmaking=10, winger=12, passing=9),
        "Ed24-26 Lat=12 Jug 9-11 Pas 8-11 Def 6-11 Ano<=5 Por<=5",
    ),
    (
        "ciego3: medio con cuatro",
        24,
        perfil(defending=9, playmaking=13, winger=8, passing=11),
        "Ed23-25 Jug=13 Pas 10-12 Def 8-11 Lat 6-11 Ano<=5 Por<=5",
    ),
    (
        "ciego3: lateral con suelo en la tercera",
        26,
        perfil(defending=14, playmaking=8, winger=11, passing=12),
        "Ed25-27 Def=14 Pas 11-13 Lat>=11 Jug 6-11 Ano<=5 Por<=5",
    ),
    (
        "ciego3: chaval de 17",
        17,
        perfil(defending=10, playmaking=8),
        "Ed=17 Def=10 Jug=8 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    # --- La edad de los mayores: suelo abierto, no ventana (2026-10-11)
    (
        "a los 34 todavia es ventana",
        34,
        perfil(defending=12, playmaking=9),
        "Ed33-35 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "a los 35 se abre por arriba y no se cierra",
        35,
        perfil(defending=12, playmaking=9),
        "Ed35-99 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "y a los 40 sigue siendo el mismo suelo",
        40,
        perfil(defending=12, playmaking=9),
        "Ed35-99 Def=12 Jug=9 Pas<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "pero con la busqueda holgada sigue siendo ventana",
        35,
        perfil(defending=16, playmaking=12),
        "Ed34-36 Def=16 Jug 11-13 Pas<=5 Lat<=5 Ano<=5 Por<=5",
    ),
    # --- Al pasador la edad no se le abre a los 32 (2026-10-11)
    (
        "el perfil que mando el usuario, clavado",
        23,
        perfil(keeper=1, defending=10, playmaking=3, winger=4, passing=10, scoring=3, set_pieces=6),
        "Ed=23 Def=10 Pas 9-11 Lat<=4 Jug<=4 Ano<=4 Por<=4",
    ),
    (
        "pasador de 33: edad clavada",
        33,
        perfil(passing=13, playmaking=7, defending=5),
        "Ed=33 Jug=7 Pas 12-14 Def 4-6 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "pasador de 34: todavia clavada",
        34,
        perfil(passing=13, playmaking=7, defending=5),
        "Ed=34 Jug=7 Pas 12-14 Def 4-6 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "pero al medio de 33 si se le abre",
        33,
        perfil(playmaking=13, passing=7, defending=5),
        "Ed32-34 Jug=13 Pas=7 Def 4-6 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "y al pasador a los 35 tambien se le abre el suelo",
        35,
        perfil(passing=13, playmaking=7, defending=5),
        "Ed35-99 Jug=7 Pas 12-14 Def 4-6 Lat<=4 Ano<=4 Por<=4",
    ),
    # --- Cada tipo tiene su juego de habilidades elegibles (2026-10-11)
    (
        "al defensa NO se le compara por Anotacion, ni con 9",
        25,
        perfil(defending=12, passing=10, scoring=9),
        "Ed=25 Def=12 Pas 9-11 Jug<=4 Lat<=4 Ano<=10 Por<=4",
    ),
    (
        "pero al extremo si, ya con 5",
        25,
        perfil(winger=10, passing=7, playmaking=5, scoring=5),
        "Ed=25 Lat=10 Pas=7 Jug 4-6 Ano 4-6 Def<=4 Por<=4",
    ),
    # --- La rejilla fina de la tercera contra la cuarta
    (
        "tercera y cuarta en 4: las dos a tope",
        25,
        perfil(defending=12, passing=10, playmaking=4, winger=4),
        "Ed=25 Def=12 Pas 9-11 Jug<=4 Lat<=4 Ano<=4 Por<=4",
    ),
    (
        "las dos en 5: las dos con banda",
        25,
        perfil(defending=12, passing=10, playmaking=5, winger=5),
        "Ed=25 Def=12 Pas 9-11 Jug 4-6 Lat 4-6 Ano<=4 Por<=4",
    ),
    (
        "la cuarta en 6 empuja el dial",
        25,
        perfil(defending=12, passing=10, playmaking=6, winger=7),
        "Ed24-26 Def=12 Pas 9-11 Lat 6-9 Jug 5-8 Ano<=5 Por<=5",
    ),
    (
        "sin cuarta no lo empuja",
        25,
        perfil(defending=12, passing=10, playmaking=6, winger=6),
        "Ed=25 Def=12 Pas 9-11 Jug 5-7 Lat 5-7 Ano<=4 Por<=4",
    ),
    (
        "lo que no puede ser criterio tampoco cuenta para la rareza",
        25,
        perfil(defending=12, passing=10, scoring=9),
        "Ed=25 Def=12 Pas 9-11 Jug<=4 Lat<=4 Ano<=10 Por<=4",
    ),
    # --- En el extremo, Defensa y Anotacion pesan lo mismo (2026-10-11)
    (
        "extremo real: Defensa adelanta a Jugadas por nivel",
        29,
        perfil(winger=15, defending=13, playmaking=11, passing=11),
        "Ed28-30 Lat=15 Def 12-14 Jug>=11 Pas 9-14 Ano<=5 Por<=5",
    ),
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


# --- La Porteria no compite de igual a igual --------------------------------

#: La frontera bisectada el 2026-10-11 para cada Defensa de 1 a 20, con el
#: resto del perfil a cero: la Porteria minima que convierte al jugador en
#: portero. Hasta Defensa 3 no hay ninguna que valga --hace falta un 4-- y de
#: Defensa 12 en adelante gana con cuatro niveles menos en vez de tres.
FRONTERA_DEL_PORTERO = {
    4: 4,
    5: 4,
    6: 4,
    7: 4,
    8: 5,
    9: 6,
    10: 7,
    11: 8,
    12: 8,
    13: 9,
    14: 10,
    15: 11,
    16: 12,
    17: 13,
    18: 14,
    19: 15,
    20: 16,
}


@pytest.mark.parametrize(("defensa", "porteria"), sorted(FRONTERA_DEL_PORTERO.items()))
def test_la_frontera_entre_portero_y_defensa(defensa: int, porteria: int) -> None:
    """Un nivel menos y es defensa; ese nivel y ya es portero."""
    assert _umbral_de_portero(defensa) == porteria
    assert _tipo(perfil(defending=defensa, keeper=porteria)) == "keeper"
    assert _tipo(perfil(defending=defensa, keeper=porteria - 1)) == "defending"


@pytest.mark.parametrize("defensa", [1, 2, 3])
def test_con_poca_defensa_no_basta_empatarla(defensa: int) -> None:
    """Con Defensa 3 y Porteria 3 sale defensa: el suelo de 4 manda sobre el
    sesgo. Fue el caso que delato que la Porteria tiene suelo propio."""
    assert _tipo(perfil(defending=defensa, keeper=defensa)) == "defending"
    assert _tipo(perfil(defending=defensa, keeper=4)) == "keeper"


#: El empate de la Porteria contra cada una de las otras, medido de uno en uno.
#: La Porteria PIERDE todos menos el de Pases. La primera medicion la puso
#: tercera en el desempate y era falso: lo que parecia desempate era el sesgo
#: contra la Defensa.
EMPATES_CON_LA_PORTERIA = {
    "winger": "winger",
    "scoring": "scoring",
    "playmaking": "playmaking",
    "passing": "keeper",
    "defending": "keeper",
}


@pytest.mark.parametrize(("rival", "gana"), sorted(EMPATES_CON_LA_PORTERIA.items()))
def test_quien_gana_el_empate_a_la_porteria(rival: str, gana: str) -> None:
    assert _tipo(perfil(keeper=10, **{rival: 10})) == gana


#: Las treinta parejas con una habilidad a 16 y otra a 13. Solo una se sale de
#: «manda la mas alta»: la Porteria 13 contra la Defensa 16.
def test_solo_la_porteria_gana_desde_abajo() -> None:
    hs = ["keeper", "defending", "playmaking", "winger", "passing", "scoring"]
    sorpresas = []
    for alta in hs:
        for baja in hs:
            if alta == baja:
                continue
            tipo = _tipo(perfil(**{alta: 16, baja: 13}))
            # Un Pases 16 no hace pasador: manda la mejor de las demas.
            esperado = baja if alta == "passing" else alta
            if tipo != esperado:
                sorpresas.append((alta, baja, tipo))
    assert sorpresas == [("defending", "keeper", "keeper")]


def test_el_sesgo_del_portero_no_lo_mueve_nada_mas() -> None:
    """Con Defensa 16 la frontera sigue en 12 llene lo demas como quiera:
    Pases, Lateral, Jugadas, Anotacion y balon parado no la tocan."""
    for extra in [
        {},
        {"passing": 10},
        {"winger": 14},
        {"playmaking": 15},
        {"scoring": 15},
        {"set_pieces": 20},
    ]:
        assert _tipo(perfil(defending=16, keeper=12, **extra)) == "keeper"
        assert _tipo(perfil(defending=16, keeper=11, **extra)) == "defending"


def test_el_sesgo_se_aplica_a_la_defensa_que_gano_por_reclasificacion() -> None:
    """Con Pases 16 y Defensa 14 el rey de campo es la Defensa, y la frontera
    de la Porteria es la de la Defensa: 10, no la de los Pases."""
    assert _tipo(perfil(passing=16, defending=14, keeper=10)) == "keeper"
    assert _tipo(perfil(passing=16, defending=14, keeper=9)) == "defending"


def test_una_porteria_mas_alta_no_siempre_gana() -> None:
    """Con Lateral 17 y Defensa 16, una Porteria 16 no hace portero: el sesgo
    es contra la Defensa, y la Defensa ya habia perdido el reinado."""
    assert _tipo(perfil(winger=17, defending=16, keeper=16)) == "winger"


# --- Lo que los perfiles plausibles del 2026-10-12 dejaron fijado -----------

#: Sesenta perfiles realistas, generados con semilla fija y preguntados a
#: Hattrick uno a uno. Estos son los que destaparon un fallo del motor; el
#: recuento completo --53/60 la cadena entera, 59/60 los tres filtros-- esta en
#: `CRITERIOS_DEL_COMPARADOR.md` y las medidas en fase-a.txt, FASE R.
PLAUSIBLES = [
    (
        "la cuarta NO abre la segunda: extremo con Jugadas y Defensa a 6",
        19,
        perfil(keeper=4, defending=6, playmaking=6, winger=8, passing=7, scoring=4, set_pieces=5),
        "Ed=19 Lat=8 Pas=7 Jug 5-7 Def 5-7 Ano<=4 Por<=4",
    ),
    (
        "ni con la cuarta a 6 en un delantero",
        21,
        perfil(keeper=4, defending=4, playmaking=6, winger=6, passing=6, scoring=13, set_pieces=12),
        "Ed=21 Ano=13 Pas=6 Lat 5-7 Jug 5-7 Def<=4 Por<=4",
    ),
    (
        "al portero no se le hace criterio del Lateral",
        33,
        perfil(keeper=18, defending=15, playmaking=4, winger=5, passing=1, scoring=1),
        "Ed32-34 Por=18 Def 14-16 BP<=5 Lat<=7 Ano<=5 Jug<=5",
    ),
    (
        "ni abriendo la banda de su Defensa de rebote",
        28,
        perfil(keeper=10, defending=4, playmaking=0, winger=6, passing=1, scoring=6, set_pieces=8),
        "Ed=28 Por=10 Def=4 BP 6-10 Lat<=7 Ano<=7 Jug<=4",
    ),
    (
        "en el extremo el empate de Defensa y Anotacion lo gana ella",
        32,
        perfil(
            keeper=1, defending=11, playmaking=12, winger=15, passing=6, scoring=11, set_pieces=1
        ),
        "Ed31-33 Lat=15 Jug 11-13 Ano>=11 Def 9-14 Pas<=8 Por<=5",
    ),
]


@pytest.mark.parametrize(
    ("descripcion", "edad", "niveles", "esperado"),
    PLAUSIBLES,
    ids=[c[0] for c in PLAUSIBLES],
)
def test_los_perfiles_plausibles(
    descripcion: str, edad: int, niveles: dict[str, int], esperado: str
) -> None:
    assert _pinta(criterios_de(edad, niveles)) == esperado


# --- Al extremo, la Defensa tiene que llegarle a la Anotacion ---------------

#: Bisectado el 2026-10-12 sobre un extremo: con la Anotacion por encima, la
#: Defensa no llega a ser criterio --solo le sube el techo-- hasta que la
#: iguala. Al reves no pasa: con la Defensa arriba, la Anotacion entra siempre.
#: Y no es general: ni el mediocentro ni el defensa lo hacen.
ANOTACION_TAPA_LA_DEFENSA = [
    (18, 12, 11, "Ed24-26 Lat=18 Ano 11-13 Jug<=5 Pas<=5 Def<=13 Por<=5"),
    (18, 12, 12, "Ed24-26 Lat=18 Ano 11-13 Def>=12 Jug<=5 Pas<=5 Por<=5"),
    (18, 9, 8, "Ed24-26 Lat=18 Ano=9 Jug<=5 Pas<=5 Def<=10 Por<=5"),
    (18, 9, 9, "Ed24-26 Lat=18 Ano 8-10 Def 8-11 Jug<=5 Pas<=5 Por<=5"),
    (16, 14, 8, "Ed24-26 Lat=16 Ano 13-15 Jug<=5 Pas<=5 Def<=10 Por<=5"),
]


@pytest.mark.parametrize(("lateral", "anotacion", "defensa", "esperado"), ANOTACION_TAPA_LA_DEFENSA)
def test_la_anotacion_tapa_la_defensa_del_extremo(
    lateral: int, anotacion: int, defensa: int, esperado: str
) -> None:
    criterios = criterios_de(25, perfil(winger=lateral, scoring=anotacion, defending=defensa))
    assert _pinta(criterios) == esperado


#: Con la Defensa arriba la Anotacion entra siempre: cuatro niveles seguidos.
AL_REVES_NO_TAPA = [
    (9, "Ed24-26 Lat=18 Def 11-13 Ano 8-11 Jug<=5 Pas<=5 Por<=5"),
    (10, "Ed24-26 Lat=18 Def 11-13 Ano 9-12 Jug<=5 Pas<=5 Por<=5"),
    (11, "Ed24-26 Lat=18 Def 11-13 Ano>=11 Jug<=5 Pas<=5 Por<=5"),
    (12, "Ed24-26 Lat=18 Ano 11-13 Def>=12 Jug<=5 Pas<=5 Por<=5"),
]


@pytest.mark.parametrize(("anotacion", "esperado"), AL_REVES_NO_TAPA)
def test_la_defensa_no_tapa_a_la_anotacion(anotacion: int, esperado: str) -> None:
    criterios = criterios_de(25, perfil(winger=18, defending=12, scoring=anotacion))
    assert _pinta(criterios) == esperado


def test_al_mediocentro_y_al_defensa_no_les_pasa() -> None:
    """La tapadera es del extremo. Con Jugadas 18 y Anotacion 12, una Defensa 9
    si es criterio; y al defensa su Lateral tambien, con los Pases por encima."""
    medio = criterios_de(25, perfil(playmaking=18, scoring=12, defending=9))
    assert _pinta(medio) == "Ed24-26 Jug=18 Ano 11-13 Def 8-11 Pas<=5 Lat<=5 Por<=5"
    defensa = criterios_de(25, perfil(defending=18, passing=12, winger=9))
    assert _pinta(defensa) == "Ed24-26 Def=18 Pas 11-13 Lat 8-11 Jug<=5 Ano<=5 Por<=5"


# --- A nadie de campo se le compara por Porteria ---------------------------

#: Barrido el 2026-10-12: la Porteria de un defensa nunca llega a ser criterio,
#: solo le sube el techo. La primera medicion la daba como elegible y era
#: falso; hacia que a un defensa con algo de Porteria se le clavara como
#: SEGUNDO criterio, que es el error mas gordo posible aqui porque ese criterio
#: si se le manda a `transfersearch`.
PORTERIA_DEL_DEFENSA = [
    (18, 5, "Ed24-26 Def=18 Pas<=2 Jug<=5 Lat<=5 Ano<=5 Por<=7"),
    (18, 9, "Ed24-26 Def=18 Pas<=2 Jug<=5 Lat<=5 Ano<=5 Por<=11"),
    (18, 13, "Ed24-26 Def=18 Pas<=2 Jug<=5 Lat<=5 Ano<=5 Por<=15"),
    (12, 5, "Ed=25 Def=12 Pas<=2 Jug<=4 Lat<=4 Ano<=4 Por<=6"),
    (12, 7, "Ed=25 Def=12 Pas<=2 Jug<=4 Lat<=4 Ano<=4 Por<=8"),
]


@pytest.mark.parametrize(("defensa", "porteria", "esperado"), PORTERIA_DEL_DEFENSA)
def test_al_defensa_no_se_le_compara_por_porteria(
    defensa: int, porteria: int, esperado: str
) -> None:
    criterios = criterios_de(25, perfil(defending=defensa, keeper=porteria))
    assert _pinta(criterios) == esperado


#: Y tampoco cuando tiene una segunda de verdad por delante: la Porteria 9 se
#: queda en el monton de los techos sea quien sea la segunda.
@pytest.mark.parametrize(
    ("segunda", "esperado"),
    [
        ("passing", "Ed24-26 Def=18 Pas 11-13 Jug<=5 Lat<=5 Ano<=5 Por<=11"),
        ("playmaking", "Ed24-26 Def=18 Jug 11-13 Pas<=5 Lat<=5 Ano<=5 Por<=11"),
        ("winger", "Ed24-26 Def=18 Lat 11-13 Pas<=5 Jug<=5 Ano<=5 Por<=11"),
    ],
)
def test_la_porteria_del_defensa_se_queda_en_los_techos(segunda: str, esperado: str) -> None:
    criterios = criterios_de(25, perfil(defending=18, keeper=9, **{segunda: 12}))
    assert _pinta(criterios) == esperado


#: Y de rebote, la Porteria tampoco cuenta para el DIAL del defensa. Si
#: contara, un Defensa 14 con Pases 10 y Porteria 9 llegaria a rareza 27 y se
#: aflojaria; medido, sigue clavando la edad en 25.
DIAL_SIN_PORTERIA = [
    (14, 10, 0, "Ed=25 Def=14 Pas 9-11 Jug<=4 Lat<=4 Ano<=4 Por<=4"),
    (14, 10, 9, "Ed=25 Def=14 Pas 9-11 Jug<=4 Lat<=4 Ano<=4 Por<=10"),
    (16, 8, 0, "Ed=25 Def=16 Pas=8 Jug<=4 Lat<=4 Ano<=4 Por<=4"),
    (16, 8, 11, "Ed=25 Def=16 Pas=8 Jug<=4 Lat<=4 Ano<=4 Por<=12"),
    (14, 11, 0, "Ed24-26 Def=14 Pas 10-12 Jug<=5 Lat<=5 Ano<=5 Por<=5"),
    (14, 11, 9, "Ed24-26 Def=14 Pas 10-12 Jug<=5 Lat<=5 Ano<=5 Por<=11"),
]


@pytest.mark.parametrize(("defensa", "pases", "porteria", "esperado"), DIAL_SIN_PORTERIA)
def test_la_porteria_no_mueve_el_dial_del_defensa(
    defensa: int, pases: int, porteria: int, esperado: str
) -> None:
    criterios = criterios_de(25, perfil(defending=defensa, passing=pases, keeper=porteria))
    assert _pinta(criterios) == esperado


def test_con_bastante_porteria_el_defensa_pasa_a_portero() -> None:
    """Defensa 14 y Porteria 13: el umbral de la Defensa 14 es 10, asi que a
    los 13 ya es portero y le cambia la plantilla entera."""
    criterios = criterios_de(25, perfil(defending=14, passing=10, keeper=13))
    assert _pinta(criterios) == "Ed24-26 Por=13 Def 13-15 BP<=5 Lat<=5 Ano<=5 Jug<=5"


# --- El liston del dial es por PAREJA, no por tipo -------------------------

#: Las doce fronteras barridas el 2026-10-12 con la primera en 16: la rareza a
#: la que la pareja afloja. La primera medicion usaba una sola segunda por tipo
#: y de ahi salio un liston por tipo, que es falso en cuatro de las doce.
FRONTERAS_DEL_DIAL = {
    ("defending", "passing"): 25,
    ("defending", "playmaking"): 25,
    ("defending", "winger"): 25,
    ("playmaking", "passing"): 27,
    ("playmaking", "defending"): 26,
    ("playmaking", "winger"): 25,
    ("playmaking", "scoring"): 25,
    ("winger", "passing"): 27,
    ("scoring", "passing"): 27,
    ("scoring", "playmaking"): 27,
    ("scoring", "winger"): 25,
    ("keeper", "defending"): 21,
}


@pytest.mark.parametrize(
    ("pareja", "frontera"),
    sorted(FRONTERAS_DEL_DIAL.items()),
    ids=[f"{a}+{b}" for a, b in sorted(FRONTERAS_DEL_DIAL)],
)
def test_la_frontera_del_dial_por_pareja(pareja: tuple[str, str], frontera: int) -> None:
    """Justo en la frontera afloja, y un nivel por debajo no."""
    dominante, segunda = pareja
    segundo_nivel = frontera - 16
    assert es_holgado(perfil(**{dominante: 16, segunda: segundo_nivel}), None, 25) is True
    assert es_holgado(perfil(**{dominante: 16, segunda: segundo_nivel - 1}), None, 25) is False


#: Y una habilidad sola afloja desde 17, no desde 16. Barrido de 13 a 18 en
#: Anotacion, Defensa y Porteria: los tres saltan igual, en 17.
@pytest.mark.parametrize("habilidad", ["scoring", "defending", "keeper"])
def test_una_sola_habilidad_afloja_en_17(habilidad: str) -> None:
    assert es_holgado(perfil(**{habilidad: 16}), None, 25) is False
    assert es_holgado(perfil(**{habilidad: 17}), None, 25) is True


# --- El Lateral del mediocentro pide mas que los demas ---------------------


#: Unas noventa celdas del 2026-10-12. Entra con 7, o con 5 si la Anotacion
#: llega a 5 y la Defensa no pasa de 4 --que son justo las fronteras de SER
#: criterio--. Es la lectura de mediocentro OFENSIVO.
def _lateral_es_criterio(niveles: dict[str, int]) -> bool:
    for c in criterios_de(25, niveles).habilidades:
        if c.habilidad == "winger":
            return c.operador != "<="
    return False


@pytest.mark.parametrize("dominante", [12, 14, 16, 18, 20])
@pytest.mark.parametrize("lateral", [4, 5, 6, 7, 8, 9])
def test_el_lateral_del_medio_sin_ayuda_pide_siete(dominante: int, lateral: int) -> None:
    """Cinco filas identicas: el nivel de la dominante no lo mueve."""
    niveles = perfil(playmaking=dominante, passing=9, winger=lateral)
    assert _lateral_es_criterio(niveles) is (lateral >= 7)


@pytest.mark.parametrize("lateral", [4, 5, 6, 7, 8])
def test_con_defensa_al_lado_sigue_pidiendo_siete(lateral: int) -> None:
    niveles = perfil(playmaking=16, defending=10, winger=lateral)
    assert _lateral_es_criterio(niveles) is (lateral >= 7)


@pytest.mark.parametrize("lateral", [4, 5, 6, 7, 8])
def test_con_anotacion_al_lado_le_basta_cinco(lateral: int) -> None:
    niveles = perfil(playmaking=16, scoring=10, winger=lateral)
    assert _lateral_es_criterio(niveles) is (lateral >= 5)


@pytest.mark.parametrize("anotacion", [4, 5, 6, 7, 8, 9])
def test_la_frontera_de_la_anotacion_que_le_abre_el_lateral(anotacion: int) -> None:
    niveles = perfil(playmaking=16, winger=5, scoring=anotacion)
    assert _lateral_es_criterio(niveles) is (anotacion >= 5)


@pytest.mark.parametrize("defensa", [4, 5, 6, 7, 8, 9])
@pytest.mark.parametrize("anotacion", [10, 14])
def test_la_defensa_le_vuelve_a_cerrar_el_lateral(defensa: int, anotacion: int) -> None:
    niveles = perfil(playmaking=16, winger=5, scoring=anotacion, defending=defensa)
    assert _lateral_es_criterio(niveles) is (defensa <= 4)


#: Y las cadenas enteras de la rejilla, que es donde se ve que no es el dial:
#: los dos primeros son holgados --topes de 5, bandas de [v-1, v+2]-- y uno le
#: pone tope al Lateral y el otro criterio.
REJILLA_DEL_LATERAL = [
    (
        perfil(playmaking=16, defending=10, winger=5),
        "Ed24-26 Jug=16 Def 9-11 Pas<=5 Lat<=7 Ano<=5 Por<=5",
    ),
    (
        perfil(playmaking=16, defending=10, winger=7),
        "Ed24-26 Jug=16 Def 9-11 Lat 6-9 Pas<=5 Ano<=5 Por<=5",
    ),
    (
        perfil(playmaking=16, scoring=10, winger=5),
        "Ed24-26 Jug=16 Ano 9-11 Lat 4-7 Pas<=5 Def<=5 Por<=5",
    ),
    (
        perfil(playmaking=16, passing=10, winger=5),
        "Ed=25 Jug=16 Pas 9-11 Def<=4 Lat<=6 Ano<=4 Por<=4",
    ),
]


@pytest.mark.parametrize(("niveles", "esperado"), REJILLA_DEL_LATERAL)
def test_la_rejilla_del_lateral_entera(niveles: dict[str, int], esperado: str) -> None:
    assert _pinta(criterios_de(25, niveles)) == esperado


# --- La Anotacion necesita cinco; a las demas les basta tres ---------------

#: Medido el 2026-10-12 poniendole una sola companera a la dominante. Es de la
#: habilidad y no del tipo: pasa igual en el extremo y en el mediocentro.
ENTRA_CON_TRES = [
    (perfil(winger=16, defending=3), "Ed=25 Lat=16 Def=3 Jug<=4 Pas<=4 Ano<=4 Por<=4"),
    (perfil(winger=16, defending=4), "Ed=25 Lat=16 Def=4 Jug<=4 Pas<=4 Ano<=4 Por<=4"),
    (perfil(winger=16, playmaking=3), "Ed=25 Lat=16 Jug=3 Pas<=4 Def<=4 Ano<=4 Por<=4"),
    (perfil(winger=16, passing=3), "Ed=25 Lat=16 Pas=3 Jug<=4 Def<=4 Ano<=4 Por<=4"),
    (perfil(scoring=16, winger=4), "Ed=25 Ano=16 Lat=4 Pas<=4 Jug<=4 Def<=4 Por<=4"),
    (perfil(scoring=16, playmaking=4), "Ed=25 Ano=16 Jug=4 Pas<=4 Lat<=4 Def<=4 Por<=4"),
    (perfil(defending=16, passing=4), "Ed=25 Def=16 Pas=4 Jug<=4 Lat<=4 Ano<=4 Por<=4"),
    (perfil(defending=16, playmaking=4), "Ed=25 Def=16 Jug=4 Pas<=4 Lat<=4 Ano<=4 Por<=4"),
]


@pytest.mark.parametrize(("niveles", "esperado"), ENTRA_CON_TRES)
def test_las_demas_entran_con_tres(niveles: dict[str, int], esperado: str) -> None:
    assert _pinta(criterios_de(25, niveles)) == esperado


ANOTACION_PIDE_CINCO = [
    (perfil(winger=16, scoring=3), "Ed=25 Lat=16 Jug<=2 Pas<=4 Def<=4 Ano<=4 Por<=4"),
    (perfil(winger=16, scoring=4), "Ed=25 Lat=16 Jug<=2 Pas<=4 Def<=4 Ano<=4 Por<=4"),
    (perfil(winger=16, scoring=5), "Ed=25 Lat=16 Ano=5 Jug<=4 Pas<=4 Def<=4 Por<=4"),
    (perfil(playmaking=16, scoring=4), "Ed=25 Jug=16 Pas<=2 Def<=4 Lat<=4 Ano<=4 Por<=4"),
]


@pytest.mark.parametrize(("niveles", "esperado"), ANOTACION_PIDE_CINCO)
def test_la_anotacion_pide_cinco(niveles: dict[str, int], esperado: str) -> None:
    """Con 3 y con 4 recibe tope, con 5 ya es criterio. Y cuando no entra, el
    segundo puesto se lo queda otra --de ahi el tope de 2 en Jugadas."""
    assert _pinta(criterios_de(25, niveles)) == esperado


def test_una_anotacion_que_no_entra_no_tapa_a_la_defensa() -> None:
    """La tapadera del extremo solo muerde si la Anotacion es criterio: con
    Lateral 16, Defensa 3 y Anotacion 4, la Defensa 3 si sale."""
    for anotacion in (2, 4):
        criterios = criterios_de(25, perfil(winger=16, defending=3, scoring=anotacion))
        assert _pinta(criterios) == "Ed=25 Lat=16 Def=3 Jug<=4 Pas<=4 Ano<=4 Por<=4"


# --- El mediocentro tambien le da a la Anotacion el peso de la Defensa -----

#: Estaba medido desde el 2026-10-11 y se habia quedado sin escribir. Estos son
#: los 23 ordenes medidos del mediocentro; el que lo destapo es el de Lateral 5
#: y Anotacion 5, que lista la Anotacion segunda.
ORDENES_DEL_MEDIOCENTRO = [
    (perfil(playmaking=12, passing=7, defending=6), "Jug,Pas,Def"),
    (perfil(playmaking=12, passing=7, defending=8), "Jug,Def,Pas"),
    (perfil(playmaking=12, defending=7, winger=7), "Jug,Def,Lat"),
    (perfil(playmaking=12, defending=7, winger=8), "Jug,Lat,Def"),
    (perfil(playmaking=12, winger=7, scoring=6), "Jug,Lat,Ano"),
    (perfil(playmaking=12, winger=7, scoring=7), "Jug,Ano,Lat"),
    (perfil(playmaking=12, defending=7, scoring=7), "Jug,Def,Ano"),
    (perfil(playmaking=12, defending=7, scoring=8), "Jug,Ano,Def"),
    (perfil(playmaking=12, passing=7, scoring=7), "Jug,Pas,Ano"),
    (perfil(playmaking=12, passing=7, scoring=8), "Jug,Ano,Pas"),
    (perfil(playmaking=16, passing=10, scoring=10), "Jug,Pas,Ano"),
    (perfil(playmaking=16, passing=10, scoring=11), "Jug,Ano,Pas"),
    (perfil(playmaking=16, passing=10, winger=11), "Jug,Pas,Lat"),
    (perfil(playmaking=16, passing=10, winger=12), "Jug,Lat,Pas"),
    (perfil(playmaking=16, defending=10, scoring=10), "Jug,Def,Ano"),
    (perfil(playmaking=16, defending=10, scoring=11), "Jug,Ano,Def"),
    (perfil(playmaking=16, passing=9, defending=8, scoring=7), "Jug,Pas,Def,Ano"),
    (perfil(playmaking=16, passing=7, defending=8, scoring=9), "Jug,Ano,Def,Pas"),
    (perfil(playmaking=16, passing=8, defending=9, scoring=7), "Jug,Def,Pas,Ano"),
    (perfil(playmaking=16, passing=9, defending=9, scoring=9), "Jug,Pas,Def,Ano"),
    (perfil(playmaking=16, winger=5, scoring=5, defending=4), "Jug,Ano,Lat"),
    (perfil(playmaking=18, scoring=12, defending=9), "Jug,Ano,Def"),
    (perfil(playmaking=18, defending=12, scoring=12), "Jug,Def,Ano"),
]


@pytest.mark.parametrize(("niveles", "esperado"), ORDENES_DEL_MEDIOCENTRO)
def test_el_orden_del_mediocentro(niveles: dict[str, int], esperado: str) -> None:
    criterios = criterios_de(25, niveles)
    leido = ",".join(ABREVIATURA[c.habilidad] for c in criterios.habilidades if c.operador != "<=")
    assert leido == esperado


#: Y el inventario de entradas queda CERRADO: al defensa y al delantero se les
#: barrio igual que al mediocentro y no tienen nada propio. 3 de segunda y 5 de
#: tercera, la regla general. Son confirmaciones, no reglas nuevas, y estan aqui
#: para que nadie vuelva a gastar las consultas.
SIN_ENTRADA_PROPIA = [
    ("defensa, Lateral de segunda", perfil(defending=16), "winger", 3),
    ("defensa, Lateral de tercera con Pases", perfil(defending=16, passing=10), "winger", 5),
    ("defensa, Lateral de tercera con Jugadas", perfil(defending=16, playmaking=10), "winger", 5),
    ("delantero, Jugadas de segunda", perfil(scoring=16), "playmaking", 3),
    ("delantero, Jugadas de tercera con Pases", perfil(scoring=16, passing=10), "playmaking", 5),
    ("delantero, Jugadas de tercera con Lateral", perfil(scoring=16, winger=10), "playmaking", 5),
]


@pytest.mark.parametrize(
    ("descripcion", "base", "habilidad", "entrada"),
    SIN_ENTRADA_PROPIA,
    ids=[c[0] for c in SIN_ENTRADA_PROPIA],
)
def test_el_defensa_y_el_delantero_no_tienen_entrada_propia(
    descripcion: str, base: dict[str, int], habilidad: str, entrada: int
) -> None:
    for nivel in range(3, 9):
        niveles = {**base, habilidad: nivel}
        criterios = criterios_de(25, niveles)
        es_criterio = any(
            c.habilidad == habilidad and c.operador != "<=" for c in criterios.habilidades
        )
        assert es_criterio is (nivel >= entrada), f"{descripcion} con {nivel}"


# --- Los dos que arreglo el banco, sin gastar una consulta -----------------


#: Encontrados el 2026-10-12 con `docs/reference/sondeo-comparador/banco.py`,
#: puntuando candidatos contra todo lo ya medido cuando Hattrick ya devolvia
#: paginas vacias. En los dos casos mi analisis a mano decia lo contrario de lo
#: que dijo el banco, asi que van fijados con su perfil entero.
def test_el_corte_del_orden_va_por_plantilla() -> None:
    """Mediocentro con Pases, Defensa, Lateral y Anotacion los cuatro a 11:
    Hattrick se queda con la Defensa y el LATERAL y deja fuera la Anotacion.
    Con los pesos medidos en el corte se quedaba la Anotacion."""
    criterios = criterios_de(
        17,
        perfil(
            playmaking=13,
            passing=11,
            defending=11,
            winger=11,
            scoring=11,
            set_pieces=11,
            keeper=3,
        ),
    )
    assert _pinta(criterios) == "Ed=17 Jug=13 Pas 10-12 Def>=11 Lat 9-13 Ano<=12 Por<=4"


def test_la_banda_se_corta_si_la_segunda_supera_a_la_primera() -> None:
    """Extremo de Lateral 6 con Pases 7: la banda de la tercera se corta en 6.
    Con la segunda IGUALANDO a la primera no se corta --Lat9 Jug9 Pas9 Def9 da
    «Pases 8-10»--, asi que la condicion no es de adorno."""
    criterios = criterios_de(
        17,
        perfil(
            winger=6,
            passing=7,
            playmaking=6,
            defending=6,
            scoring=6,
            set_pieces=6,
            keeper=3,
        ),
    )
    assert _pinta(criterios) == "Ed=17 Lat=6 Pas=7 Jug 5-6 Def 5-6 Ano<=7 Por<=4"


def test_la_regla_del_lateral_no_se_aplica_a_un_medio_plano() -> None:
    """La rejilla del Lateral se midio con la dominante entre 12 y 20. Con un
    mediocentro plano --Jugadas 7 y las demas a 6-- el Lateral no es periferico
    sino codominante, y SI es criterio. Descansa en un solo caso."""
    criterios = criterios_de(
        31,
        perfil(
            playmaking=7,
            passing=6,
            defending=6,
            winger=6,
            scoring=6,
            set_pieces=6,
            keeper=3,
        ),
    )
    assert _pinta(criterios) == "Ed=31 Jug=7 Pas=6 Def 5-7 Lat 5-7 Ano<=7 Por<=4"


def test_la_cola_va_en_el_orden_del_corte_y_no_de_la_plantilla() -> None:
    """Mediocentro de Jugadas 10 y Porteria 9: Hattrick lista el Lateral 4
    antes que la Defensa 2, y el orden de plantilla los daba al reves. La cola
    es lo que sobra de la misma ordenacion, no una lista aparte."""
    criterios = criterios_de(
        31,
        perfil(
            playmaking=10, keeper=9, passing=8, scoring=5, winger=4,
            defending=2, set_pieces=5,
        ),
    )
    assert _pinta(criterios) == "Ed=31 Jug=10 Pas=8 Ano 4-6 Lat<=4 Def<=4 Por<=10"


def test_con_la_primera_en_cinco_el_tercero_no_llega_a_criterio() -> None:
    """Pasador reclasificado de Lateral 5, Pases 13 y Defensa 5: la Defensa
    saca TECHO y no banda, y el techo sale 5 --el corte en la primera--.

    Descansa en un caso. Lo que lo separaria de verdad de la regla mas amplia
    es medir la misma forma con la primera en 6: Lat6 Pas13 Def6."""
    criterios = criterios_de(
        27, perfil(winger=5, passing=13, defending=5, keeper=3, set_pieces=3, scoring=1)
    )
    assert _pinta(criterios) == "Ed=27 Lat=5 Pas 12-14 Def<=5 Jug<=4 Ano<=4 Por<=4"


# --- La invariante mas fuerte: el jugador cumple sus propios criterios -----

#: POR QUE IMPORTA. Los criterios describen jugadores PARECIDOS al nuestro, asi
#: que el nuestro tiene que entrar en todos: si una banda no contiene su propio
#: nivel, o la ventana de edad no contiene su edad, en produccion sale como una
#: busqueda que no encontraria ni a su gemelo.
#:
#: Barrido el 2026-10-12 sobre 204.116 perfiles --aleatorios de 0 a 20 en las
#: siete habilidades, mas todos los planos y casi planos de cada nivel y cada
#: edad de borde-- sin una sola violacion. Aqui se deja una muestra que corre
#: rapido; el barrido entero esta en la nota de FASE AB de fase-a.txt.
def test_el_jugador_cumple_sus_propios_criterios() -> None:
    import random

    r = random.Random(7)
    habilidades = [
        "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces",
    ]
    for _ in range(3000):
        edad = r.randint(17, 33)
        niveles = {h: r.randint(0, 20) for h in habilidades}
        criterios = criterios_de(edad, dict(niveles))
        assert criterios.edad_minima <= edad <= criterios.edad_maxima, (edad, niveles)
        for c in criterios.habilidades:
            nivel = max(0, niveles.get(c.habilidad, 0))
            assert c.admite(nivel), (edad, niveles, c)


@pytest.mark.parametrize("nivel", list(range(0, 21)))
@pytest.mark.parametrize("edad", [17, 21, 22, 31, 32, 33])
def test_los_perfiles_planos_tambien(nivel: int, edad: int) -> None:
    """Los planos son donde se juntan todos los empates, que es donde el orden
    y los operadores se pisan. Si la invariante aguanta ahi, aguanta."""
    habilidades = [
        "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces",
    ]
    for quien in habilidades:
        for extra in range(0, 4):
            niveles = dict.fromkeys(habilidades, nivel)
            niveles[quien] = min(20, nivel + extra)
            criterios = criterios_de(edad, niveles)
            assert criterios.edad_minima <= edad <= criterios.edad_maxima
            for c in criterios.habilidades:
                assert c.admite(max(0, niveles.get(c.habilidad, 0))), (niveles, c)


#: LA PRIMERA DEBIL Y LA TERCERA, sondeo del 2026-10-12 con Pases 13 fijo como
#: segunda --siempre por encima de la primera-- y el Lateral y la Defensa
#: barridos. (lateral, defensa, lo que contestó Hattrick)
#:
#: Lo que enseña, de abajo arriba: hasta 4 la tercera no entra y cae al montón;
#: con la primera en 5 y la tercera igualándola, la tercera recibe TECHO; con
#: las dos en 6, BANDA cortada en la primera; y de 7 en adelante la banda ya no
#: se corta. Con la primera en 5 y la tercera en 6 se reordenan los puestos: la
#: Defensa pasa a ser primera y el Lateral tercero.
PRIMERA_QUE_COMPRIME_AL_TERCERO: list[tuple[int, int, str]] = [
    (3, 3, "Ed=25 Lat=3 Pas 12-14 Def<=4 Jug<=4 Ano<=4 Por<=4"),
    (4, 4, "Ed=25 Lat=4 Pas 12-14 Def<=4 Jug<=4 Ano<=4 Por<=4"),
    (5, 4, "Ed=25 Lat=5 Pas 12-14 Def<=4 Jug<=4 Ano<=4 Por<=4"),
    (5, 5, "Ed=25 Lat=5 Pas 12-14 Def<=5 Jug<=4 Ano<=4 Por<=4"),
    (5, 6, "Ed=25 Def=6 Pas 12-14 Lat 4-6 Jug<=4 Ano<=4 Por<=4"),
    (6, 5, "Ed=25 Lat=6 Pas 12-14 Def 4-6 Jug<=4 Ano<=4 Por<=4"),
    (6, 6, "Ed=25 Lat=6 Pas 12-14 Def 5-6 Jug<=4 Ano<=4 Por<=4"),
    (7, 7, "Ed=25 Lat=7 Pas 12-14 Def 6-8 Jug<=4 Ano<=4 Por<=4"),
    (8, 8, "Ed=25 Lat=8 Pas 12-14 Def 7-9 Jug<=4 Ano<=4 Por<=4"),
    (9, 9, "Ed=25 Lat=9 Pas 12-14 Def 8-10 Jug<=4 Ano<=4 Por<=4"),
    (10, 10, "Ed24-26 Lat=10 Pas 12-14 Def 9-12 Jug<=5 Ano<=5 Por<=5"),
]


@pytest.mark.parametrize("lateral,defensa,esperado", PRIMERA_QUE_COMPRIME_AL_TERCERO)
def test_la_primera_debil_comprime_al_tercero(lateral: int, defensa: int, esperado: str) -> None:
    niveles = perfil(winger=lateral, defending=defensa, passing=13)
    assert _pinta(criterios_de(25, niveles)) == esperado


#: Y LA COMPRESION NO ES COSA DEL HUECO. Mismo Lateral 6 y Defensa 6, moviendo
#: la segunda: la Defensa sale «5-6» con la segunda en 8, en 13 y en 20, y con
#: la segunda POR DEBAJO (5) la Defensa asciende a segunda y se clava.
#: (pases, lo que contestó Hattrick)
LA_SEGUNDA_NO_MUEVE_LA_COMPRESION: list[tuple[int, str]] = [
    (5, "Ed=25 Lat=6 Def=6 Pas 4-6 Jug<=4 Ano<=4 Por<=4"),
    (8, "Ed=25 Lat=6 Pas=8 Def 5-6 Jug<=4 Ano<=4 Por<=4"),
    (20, "Ed=25 Lat=6 Pas 19-21 Def 5-6 Jug<=4 Ano<=4 Por<=4"),
]


@pytest.mark.parametrize("pases,esperado", LA_SEGUNDA_NO_MUEVE_LA_COMPRESION)
def test_la_segunda_no_mueve_la_compresion(pases: int, esperado: str) -> None:
    assert _pinta(criterios_de(25, perfil(winger=6, defending=6, passing=pases))) == esperado


#: EL EMPATE DE LA SEGUNDA CON LA PRIMERA, barrido el 2026-10-12 sin tercera
#: que estorbe --Lateral y Defensa al mismo nivel y nada más--. Clavada en 6 y
#: en 7, banda en 8 y en 9: la frontera son los OCHO, y el caso que sostenía
#: antes la regla --el (8,8,6)-- cae justo encima y por eso no la enseñaba.
#: (nivel de las dos, lo que contestó Hattrick)
EMPATE_DE_LA_SEGUNDA: list[tuple[int, str]] = [
    (6, "Ed=25 Lat=6 Def=6 Jug<=4 Pas<=4 Ano<=4 Por<=4"),
    (7, "Ed=25 Lat=7 Def=7 Jug<=4 Pas<=4 Ano<=4 Por<=4"),
    (8, "Ed=25 Lat=8 Def 7-9 Jug<=4 Pas<=4 Ano<=4 Por<=4"),
    (9, "Ed=25 Lat=9 Def 8-10 Jug<=4 Pas<=4 Ano<=4 Por<=4"),
]


@pytest.mark.parametrize("nivel,esperado", EMPATE_DE_LA_SEGUNDA)
def test_el_empate_abre_la_segunda_desde_ocho(nivel: int, esperado: str) -> None:
    assert _pinta(criterios_de(25, perfil(winger=nivel, defending=nivel))) == esperado


#: UN 17 QUE NO ES LA PRIMERA NO AFLOJA NADA. Los tres primeros llevan un 17 o
#: más y salen AJUSTADOS --edad clavada, techos en 4--; el cuarto y el quinto
#: son el contraste que sí afloja, y lo hace por rareza, no por el 17.
#: (perfil, lo que contestó Hattrick)
EL_DIECISIETE_QUE_NO_AFLOJA: list[tuple[dict[str, int], str]] = [
    (
        perfil(winger=5, defending=5, passing=18),
        "Ed=25 Lat=5 Pas 17-19 Def<=5 Jug<=4 Ano<=4 Por<=4",
    ),
    (
        perfil(winger=6, passing=17),
        "Ed=25 Lat=6 Pas 16-18 Jug<=4 Def<=4 Ano<=4 Por<=4",
    ),
    (
        perfil(winger=6, defending=6, passing=20),
        "Ed=25 Lat=6 Pas 19-21 Def 5-6 Jug<=4 Ano<=4 Por<=4",
    ),
    (
        perfil(winger=7, defending=7, passing=20),
        "Ed24-26 Lat=7 Pas 19-21 Def 6-9 Jug<=5 Ano<=5 Por<=5",
    ),
    (
        perfil(winger=12, defending=12, passing=20),
        "Ed24-26 Lat=12 Pas 19-21 Def>=12 Jug<=5 Ano<=5 Por<=5",
    ),
]


@pytest.mark.parametrize("niveles,esperado", EL_DIECISIETE_QUE_NO_AFLOJA)
def test_el_diecisiete_que_no_es_la_primera_no_afloja(
    niveles: dict[str, int], esperado: str
) -> None:
    assert _pinta(criterios_de(25, dict(niveles))) == esperado


#: LA CUARTA ABRE LA SEGUNDA, SI LA SEGUNDA ES ALTA. Lo decía la fuente de 2009
#: --«The same happen if the third skill is high or if the third and fourth
#: skills are quite high and secondary is high»-- y estuvo dos días dado por
#: refutado porque los dos barridos que lo buscaban tenían la segunda en 7,
#: justo por debajo de la frontera.
#:
#: Rejilla del 2026-10-12. Extremo con el Lateral de primera, los Pases de
#: segunda, las Jugadas de tercera y la Defensa de cuarta.
#: (lateral, pases, jugadas, defensa, lo que contestó Hattrick)
LA_CUARTA_ABRE_AL_SEGUNDO: list[tuple[int, int, int, int, str]] = [
    # la cuarta en 0 y en 4 no abre; en 5 y en 6 sí
    (16, 8, 5, 0, "Ed=25 Lat=16 Pas=8 Jug 4-6 Def<=4 Ano<=4 Por<=4"),
    (16, 8, 5, 4, "Ed=25 Lat=16 Pas=8 Jug 4-6 Def<=4 Ano<=4 Por<=4"),
    (16, 8, 5, 5, "Ed=25 Lat=16 Pas 7-9 Jug 4-6 Def 4-6 Ano<=4 Por<=4"),
    (16, 8, 5, 6, "Ed=25 Lat=16 Pas 7-9 Jug 4-6 Def 5-7 Ano<=4 Por<=4"),
    (16, 8, 6, 0, "Ed=25 Lat=16 Pas=8 Jug 5-7 Def<=4 Ano<=4 Por<=4"),
    (16, 8, 6, 4, "Ed=25 Lat=16 Pas=8 Jug 5-7 Def<=4 Ano<=4 Por<=4"),
    (16, 8, 6, 5, "Ed=25 Lat=16 Pas 7-9 Jug 5-7 Def 4-6 Ano<=4 Por<=4"),
    (16, 8, 6, 6, "Ed=25 Lat=16 Pas 7-9 Jug 5-7 Def 5-7 Ano<=4 Por<=4"),
    (16, 9, 5, 0, "Ed=25 Lat=16 Pas=9 Jug 4-6 Def<=4 Ano<=4 Por<=4"),
    (16, 9, 5, 4, "Ed=25 Lat=16 Pas=9 Jug 4-6 Def<=4 Ano<=4 Por<=4"),
    (16, 9, 5, 5, "Ed=25 Lat=16 Pas 8-10 Jug 4-6 Def 4-6 Ano<=4 Por<=4"),
    (16, 9, 5, 6, "Ed=25 Lat=16 Pas 8-10 Jug 4-6 Def 5-7 Ano<=4 Por<=4"),
    (16, 9, 6, 0, "Ed=25 Lat=16 Pas=9 Jug 5-7 Def<=4 Ano<=4 Por<=4"),
    (16, 9, 6, 4, "Ed=25 Lat=16 Pas=9 Jug 5-7 Def<=4 Ano<=4 Por<=4"),
    (16, 9, 6, 5, "Ed=25 Lat=16 Pas 8-10 Jug 5-7 Def 4-6 Ano<=4 Por<=4"),
    (16, 9, 6, 6, "Ed24-26 Lat=16 Pas 8-10 Jug 5-8 Def 5-8 Ano<=5 Por<=5"),
    # ...y con la segunda en 6 y en 7 no abre ni con la cuarta en 6
    (16, 7, 5, 5, "Ed=25 Lat=16 Pas=7 Jug 4-6 Def 4-6 Ano<=4 Por<=4"),
    (16, 7, 6, 6, "Ed=25 Lat=16 Pas=7 Jug 5-7 Def 5-7 Ano<=4 Por<=4"),
    (16, 6, 5, 5, "Ed=25 Lat=16 Pas=6 Jug 4-6 Def 4-6 Ano<=4 Por<=4"),
    # no depende de la primera: 12, 16 y 20 abren igual
    (12, 8, 5, 5, "Ed=25 Lat=12 Pas 7-9 Jug 4-6 Def 4-6 Ano<=4 Por<=4"),
    (20, 8, 5, 5, "Ed24-26 Lat=20 Pas 7-9 Jug 4-7 Def 4-7 Ano<=5 Por<=5"),
    # control: la segunda en 10 abre ella sola, sin cuarta
    (16, 10, 5, 0, "Ed=25 Lat=16 Pas 9-11 Jug 4-6 Def<=4 Ano<=4 Por<=4"),
]


@pytest.mark.parametrize("lateral,pases,jugadas,defensa,esperado", LA_CUARTA_ABRE_AL_SEGUNDO)
def test_la_cuarta_abre_al_segundo(
    lateral: int, pases: int, jugadas: int, defensa: int, esperado: str
) -> None:
    niveles = perfil(winger=lateral, passing=pases, playmaking=jugadas, defending=defensa)
    assert _pinta(criterios_de(25, niveles)) == esperado


#: LAS DOS LISTAS INICIALES DEL EXTREMO. El 2026-10-12, con la fuente de 2009
#: delante --«the list of skills is sorted by the initial order having
#: importance unless the skills are higher then the skill before them in the
#: initial list by more then the difference in the initial skills»-- se
#: entendió que el mecanismo ES un orden total por `nivel − importancia`, y que
#: lo que el texto no dice es CUÁNTAS listas iniciales hay.
#:
#: Un extremo con Pases, Defensa y Anotación los tres en el conjunto usa otra
#: lista, y con eso la familia de FASE Q --que llevaba dos días «descartando
#: cualquier orden por clave»-- sale entera.
#: (defensa, el orden que contestó Hattrick)
GIRO_DEL_EXTREMO_CON_DEFENSA: list[tuple[int, int, str]] = [
    # Lateral 16, Pases 9 y Anotación 9 fijas, la Defensa barrida.
    (9, 4, "Lat Pas Ano"),
    (9, 5, "Lat Pas Ano"),
    (9, 6, "Lat Pas Ano"),
    (9, 7, "Lat Pas Ano"),
    (9, 8, "Lat Pas Ano"),
    (9, 9, "Lat Ano Pas Def"),
    (9, 10, "Lat Ano Def Pas"),
    (9, 11, "Lat Def Ano Pas"),
    # Y LA PREDICCIÓN: con Pases 7 y Anotación 7 el giro no cae en 9 --no es un
    # nivel-- sino en 7, que es donde la Defensa entra en el conjunto.
    (7, 4, "Lat Pas Ano"),
    (7, 5, "Lat Pas Ano"),
    (7, 6, "Lat Pas Ano"),
    (7, 7, "Lat Ano Pas Def"),
    (7, 8, "Lat Ano Def Pas"),
    (7, 9, "Lat Def Ano Pas"),
]


@pytest.mark.parametrize("par,defensa,esperado", GIRO_DEL_EXTREMO_CON_DEFENSA)
def test_el_extremo_con_defensa_usa_otra_lista(par: int, defensa: int, esperado: str) -> None:
    niveles = perfil(winger=16, passing=par, scoring=par, defending=defensa)
    orden = _puestos(niveles, _tipo(niveles))
    assert " ".join(ABREVIATURA[h] for h in orden[: len(esperado.split())]) == esperado


#: Y LOS QUINCE SUBCONJUNTOS DE FASE Q, que son la prueba de verdad: un extremo
#: de Lateral 16 con las demás a 9. La fila de `Pas,Ano` y la de `Pas,Def,Ano`
#: ordenan la misma pareja al revés, y eso era lo que parecía imposible.
#: (habilidades a 9, el orden que contestó Hattrick)
QUINCE_SUBCONJUNTOS_DEL_EXTREMO: list[tuple[tuple[str, ...], str]] = [
    (("playmaking",), "Lat Jug"),
    (("passing",), "Lat Pas"),
    (("defending",), "Lat Def"),
    (("scoring",), "Lat Ano"),
    (("playmaking", "passing"), "Lat Jug Pas"),
    (("playmaking", "defending"), "Lat Jug Def"),
    (("playmaking", "scoring"), "Lat Jug Ano"),
    (("passing", "defending"), "Lat Pas Def"),
    (("passing", "scoring"), "Lat Pas Ano"),
    (("defending", "scoring"), "Lat Ano Def"),
    (("playmaking", "passing", "defending"), "Lat Jug Pas Def"),
    (("playmaking", "passing", "scoring"), "Lat Jug Pas Ano"),
    (("playmaking", "defending", "scoring"), "Lat Jug Ano Def"),
    (("passing", "defending", "scoring"), "Lat Ano Pas Def"),
    (("playmaking", "passing", "defending", "scoring"), "Lat Jug Pas Def"),
]


@pytest.mark.parametrize("cuales,esperado", QUINCE_SUBCONJUNTOS_DEL_EXTREMO)
def test_los_quince_subconjuntos_de_fase_q(cuales: tuple[str, ...], esperado: str) -> None:
    niveles = perfil(winger=16, **{c: 9 for c in cuales})
    orden = _puestos(niveles, _tipo(niveles))
    assert " ".join(ABREVIATURA[h] for h in orden[: len(esperado.split())]) == esperado


#: LA ENTRADA DEL CUARTO, medida y todavía sin regla. Extremo de Lateral 16 con
#: la Defensa en 9. Lo que el motor SÍ reproduce de estas ocho celdas; las tres
#: que no están en `PENDIENTES` del banco, con su medida.
#: (pases, anotacion, lo que contestó Hattrick)
ENTRADA_DEL_CUARTO: list[tuple[int, int, str]] = [
    (8, 8, "Ed24-26 Lat=16 Ano 7-9 Def 8-11 Pas 6-11 Jug<=5 Por<=5"),
    (9, 8, "Ed24-26 Lat=16 Pas 8-10 Ano 7-10 Def 7-12 Jug<=5 Por<=5"),
    (8, 5, "Ed24-26 Lat=16 Def 8-10 Pas 7-10 Ano 4-7 Jug<=5 Por<=5"),
    (8, 6, "Ed24-26 Lat=16 Def 8-10 Pas 7-10 Ano 5-8 Jug<=5 Por<=5"),
    (8, 7, "Ed24-26 Lat=16 Def 8-10 Pas 7-10 Ano 6-9 Jug<=5 Por<=5"),
]


@pytest.mark.parametrize("pases,anotacion,esperado", ENTRADA_DEL_CUARTO)
def test_la_entrada_del_cuarto(pases: int, anotacion: int, esperado: str) -> None:
    niveles = perfil(winger=16, defending=9, passing=pases, scoring=anotacion)
    assert _pinta(criterios_de(25, niveles)) == esperado
