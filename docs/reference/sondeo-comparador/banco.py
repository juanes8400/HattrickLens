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
    # LOS SUELTOS TAMBIEN, y esto no es cosmetico: el 2026-10-12 el banco dio
    # por bueno un candidato que rompia uno de ellos precisamente porque no los
    # miraba. Un banco con datos a medias miente con mas aplomo que no tenerlo.
    # Si se anade una prueba de caso suelto a `test_criterios_hattrick`, va
    # tambien aqui.
    casos += [
        (
            17,
            perfil(playmaking=13, passing=11, defending=11, winger=11, scoring=11,
                   set_pieces=11, keeper=3),
            "Ed=17 Jug=13 Pas 10-12 Def>=11 Lat 9-13 Ano<=12 Por<=4",
        ),
        (
            17,
            perfil(winger=6, passing=7, playmaking=6, defending=6, scoring=6,
                   set_pieces=6, keeper=3),
            "Ed=17 Lat=6 Pas=7 Jug 5-6 Def 5-6 Ano<=7 Por<=4",
        ),
        (
            31,
            perfil(playmaking=7, passing=6, defending=6, winger=6, scoring=6,
                   set_pieces=6, keeper=3),
            "Ed=31 Jug=7 Pas=6 Def 5-7 Lat 5-7 Ano<=7 Por<=4",
        ),
        (
            25,
            perfil(winger=16, defending=3, scoring=4),
            "Ed=25 Lat=16 Def=3 Jug<=4 Pas<=4 Ano<=4 Por<=4",
        ),
        (
            25,
            perfil(winger=16, defending=3, scoring=2),
            "Ed=25 Lat=16 Def=3 Jug<=4 Pas<=4 Ano<=4 Por<=4",
        ),
        (
            29,
            perfil(playmaking=14, keeper=13, winger=9, passing=8, defending=5,
                   scoring=3, set_pieces=1),
            "Ed=29 Jug=14 Pas 7-9 Lat 8-10 Def 4-6 Ano<=4 Por<=14",
        ),
        (
            31,
            perfil(playmaking=10, keeper=9, passing=8, scoring=5, winger=4,
                   defending=2, set_pieces=5),
            "Ed=31 Jug=10 Pas=8 Ano 4-6 Lat<=4 Def<=4 Por<=10",
        ),
        (
            27,
            perfil(winger=5, passing=13, defending=5, keeper=3, set_pieces=3, scoring=1),
            "Ed=27 Lat=5 Pas 12-14 Def<=5 Jug<=4 Ano<=4 Por<=4",
        ),
    ]
    # LA TANDA DEL 2026-10-12 CON SESION NUEVA (www84): la primera debil contra
    # la tercera, el empate de la segunda y el 17 que no afloja.
    casos += [
        (25, T.perfil(winger=lat, defending=defe, passing=13), s)
        for lat, defe, s in T.PRIMERA_QUE_COMPRIME_AL_TERCERO
    ]
    casos += [
        (25, T.perfil(winger=6, defending=6, passing=pas), s)
        for pas, s in T.LA_SEGUNDA_NO_MUEVE_LA_COMPRESION
    ]
    casos += [(25, T.perfil(winger=n, defending=n), s) for n, s in T.EMPATE_DE_LA_SEGUNDA]
    casos += [(25, dict(n), s) for n, s in T.EL_DIECISIETE_QUE_NO_AFLOJA]
    casos += [
        (25, T.perfil(winger=lat, passing=pas, playmaking=jug, defending=defe), s)
        for lat, pas, jug, defe, s in T.LA_CUARTA_ABRE_AL_SEGUNDO
    ]
    casos += [
        (25, T.perfil(winger=16, defending=9, passing=pas, scoring=ano), s)
        for pas, ano, s in T.ENTRADA_DEL_CUARTO
    ]
    casos += [
        (25, T.perfil(playmaking=16, **extra), s)
        for extra, s in T.LAS_DOS_LISTAS_DEL_MEDIOCENTRO
    ]
    casos += [
        (25, T.perfil(playmaking=16, **extra), s)
        for extra, s in T.LA_ANOTACION_Y_EL_LATERAL_DEL_MEDIO
    ]
    casos += [(e, dict(n), s) for e, n, s in T.LAS_FICHAS_REALES]
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


#: LOS ORDENES DEL EXTREMO, que se puntuan por PREFIJO del orden y no por
#: cadena, porque asi se midieron. Aqui estan los quince subconjuntos de FASE Q
#: y los dos barridos de la Defensa del 2026-10-12: son la prueba de las dos
#: listas iniciales, y un candidato que las rompa esta roto.
def ordenes_del_extremo() -> list[tuple[dict[str, int], str]]:
    casos = [
        (perfil(winger=16, **{c: 9 for c in cuales}), esperado)
        for cuales, esperado in T.QUINCE_SUBCONJUNTOS_DEL_EXTREMO
    ]
    casos += [
        (perfil(winger=16, passing=par, scoring=par, defending=defe), esperado)
        for par, defe, esperado in T.GIRO_DEL_EXTREMO_CON_DEFENSA
    ]
    return casos


#: Lo que el motor TODAVIA no reproduce, de las tandas de perfiles. Se guarda
#: aqui y no en las pruebas porque las pruebas fijan lo que ya funciona; esto
#: es la lista de deberes, y cada entrada dice de que familia es.
PENDIENTES: list[tuple[str, int, dict[str, int], str]] = [
    # LA ENTRADA DEL CUARTO, medida el 2026-10-12 y sin regla. Extremo de
    # Lateral 16 y Defensa 9: cuando los Pases quedan POR DEBAJO de la
    # Anotacion, Hattrick los tira al monton y deja solo Defensa y Anotacion.
    # El motor los mantiene como criterio y de paso reordena Def/Ano.
    #
    # La regla simetrica obvia --«la Anotacion tapa tambien a los Pases», como
    # ya tapa a la Defensa-- ROMPE un caso medido: Lat16 Pas8 Ano9 Def7, donde
    # los Pases SI entran estando por debajo de la Anotacion. La diferencia es
    # que alli la Defensa esta fuera. No se ha sacado la regla.
    (
        "entrada del cuarto",
        25,
        perfil(winger=16, defending=9, passing=5, scoring=8),
        "Ed24-26 Lat=16 Def 8-10 Ano 7-10 Jug<=5 Pas<=7 Por<=5",
    ),
    (
        "entrada del cuarto",
        25,
        perfil(winger=16, defending=9, passing=6, scoring=8),
        "Ed24-26 Lat=16 Def 8-10 Ano 7-10 Jug<=5 Pas<=8 Por<=5",
    ),
    (
        "entrada del cuarto",
        25,
        perfil(winger=16, defending=9, passing=7, scoring=8),
        "Ed24-26 Lat=16 Def 8-10 Ano 7-10 Jug<=5 Pas<=9 Por<=5",
    ),
    # Y EL MEDIOCENTRO GEMELO, misma forma y tampoco sale: Hattrick lista los
    # Pases 7 antes que la Anotacion 8 y el motor al contrario. Al mediocentro
    # le faltaria su segunda lista inicial, igual que al extremo.
    (
        "segunda lista del mediocentro",
        25,
        perfil(playmaking=16, defending=9, passing=7, scoring=8),
        "Ed24-26 Jug=16 Def 8-10 Pas 6-9 Ano 6-11 Lat<=5 Por<=5",
    ),
    # Y UNO MAS DE LA MISMA FAMILIA: con «Jug16 Lat9 Ano6 Def5» la Anotacion 6
    # no entra como cuarta, y el motor la mete. Mientras que con «Jug16 Pas5
    # Ano6 Def5» la Defensa 5 SI entra como cuarta un nivel por debajo de la
    # tercera. Mismo hueco, distinta habilidad, y sin regla.
    (
        "entrada del cuarto",
        25,
        perfil(playmaking=16, winger=9, scoring=6, defending=5),
        "Ed24-26 Jug=16 Lat=9 Def 4-7 Pas<=5 Ano<=8 Por<=5",
    ),
    # LOS DIEZ DE LOS BARRIDOS DEL MEDIOCENTRO que la segunda lista NO arregla.
    # Tres familias: el orden del MONTON --Hattrick lista el Lateral antes que
    # la Defensa aunque la Defensa tenga mas nivel, y eso no viaja a la
    # busqueda--; la ENTRADA DEL CUARTO otra vez, que aqui no abre con la
    # Defensa en 5 y si en 6, al contrario que la Anotacion 5 del extremo; y la
    # ANOTACION EXPULSADA del conjunto cuando entra la Defensa, que es la misma
    # forma que la tapadera del extremo y sin regla.
    (
        "entrada del cuarto / orden del monton",
        25,
        perfil(playmaking=16, passing=9, scoring=10, defending=0),
        "Ed24-26 Jug=16 Ano 9-11 Pas 8-11 Lat<=5 Def<=5 Por<=5",
    ),
    (
        "entrada del cuarto / orden del monton",
        25,
        perfil(playmaking=16, passing=9, scoring=10, defending=3),
        "Ed24-26 Jug=16 Ano 9-11 Pas 8-11 Lat<=5 Def<=5 Por<=5",
    ),
    (
        "entrada del cuarto / orden del monton",
        25,
        perfil(playmaking=16, passing=9, scoring=10, defending=4),
        "Ed24-26 Jug=16 Ano 9-11 Pas 8-11 Lat<=5 Def<=5 Por<=5",
    ),
    (
        "entrada del cuarto / orden del monton",
        25,
        perfil(playmaking=16, passing=9, scoring=10, defending=5),
        "Ed24-26 Jug=16 Ano 9-11 Pas 8-11 Lat<=5 Def<=7 Por<=5",
    ),
    (
        "entrada del cuarto / orden del monton",
        25,
        perfil(playmaking=16, passing=12, scoring=13, defending=5),
        "Ed24-26 Jug=16 Ano 12-14 Pas>=12 Lat<=5 Def<=7 Por<=5",
    ),
    (
        "entrada del cuarto / orden del monton",
        25,
        perfil(playmaking=16, passing=7, scoring=8, defending=4),
        "Ed24-26 Jug=16 Ano 7-9 Pas 6-9 Lat<=5 Def<=5 Por<=5",
    ),
    (
        "la Anotacion fuera del conjunto del mediocentro",
        25,
        perfil(playmaking=16, winger=8, scoring=8, defending=4),
        "Ed24-26 Jug=16 Ano 7-9 Lat 7-10 Pas<=5 Def<=5 Por<=5",
    ),
    (
        "la Anotacion fuera del conjunto del mediocentro",
        25,
        perfil(playmaking=16, winger=8, scoring=8, defending=5),
        "Ed=25 Jug=16 Lat=8 Def 4-6 Pas<=4 Ano<=9 Por<=4",
    ),
    (
        "la Anotacion fuera del conjunto del mediocentro",
        25,
        perfil(playmaking=16, winger=8, scoring=8, defending=6),
        "Ed=25 Jug=16 Lat=8 Def 5-8 Pas<=4 Ano<=9 Por<=4",
    ),
    (
        "la Anotacion fuera del conjunto del mediocentro",
        25,
        perfil(playmaking=16, winger=8, scoring=8, defending=7),
        "Ed24-26 Jug=16 Lat 7-9 Def 6-9 Pas<=5 Ano<=10 Por<=5",
    ),
]


#: EL TIPO DE JUGADOR, que es otra clase de observacion y el banco no la miraba.
#: Se noto el 2026-10-12 haciendo el estudio de cuanto sostiene cada regla: el
#: sesgo del portero salia «sin sostener» cuando tiene veinte filas medidas,
#: solo porque sus pruebas llaman a `_tipo` y no a `criterios_de`. Un banco que
#: solo mira una salida no puede juzgar las reglas de las otras.
def tipos() -> list[tuple[dict[str, int], str]]:
    casos: list[tuple[dict[str, int], str]] = []
    for defensa, porteria in T.FRONTERA_DEL_PORTERO.items():
        casos.append((perfil(defending=defensa, keeper=porteria), "keeper"))
        casos.append((perfil(defending=defensa, keeper=porteria - 1), "defending"))
    for rival, gana in T.EMPATES_CON_LA_PORTERIA.items():
        casos.append((perfil(keeper=10, **{rival: 10}), gana))
    for defensa in (1, 2, 3):
        casos.append((perfil(defending=defensa, keeper=defensa), "defending"))
        casos.append((perfil(defending=defensa, keeper=4), "keeper"))
    casos += [
        (perfil(defending=16, keeper=12, winger=14), "keeper"),
        (perfil(defending=16, keeper=11, winger=14), "defending"),
        (perfil(winger=17, defending=16, keeper=16), "winger"),
        (perfil(passing=16, defending=14, keeper=10), "keeper"),
        (perfil(passing=16, defending=14, keeper=9), "defending"),
        (perfil(defending=12, playmaking=12), "defending"),
    ]
    return casos


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
    ext = ordenes_del_extremo()
    bien += sum(
        1
        for n, esperado in ext
        if " ".join(
            T.ABREVIATURA[h] for h in C._puestos(dict(n), C._tipo(dict(n)))[: len(esperado.split())]
        )
        == esperado
    )
    tps = tipos()
    bien += sum(1 for n, esperado in tps if C._tipo(dict(n)) == esperado)
    total = len(cas) + len(rej) + len(ords) + len(ext) + len(tps)
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
