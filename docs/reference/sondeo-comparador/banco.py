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
    casos += [(e, dict(n), s) for e, n, s in T.LA_ENTRADA_DEL_CUARTO]
    casos += [(25, T.perfil(**n), s) for n, s in T.LOS_CINCO_NUMEROS_ACOTADOS]
    casos += [(25, T.perfil(keeper=8, set_pieces=bp), s) for bp, s in T.EL_DESCUENTO_DEL_BALON_PARADO]
    casos += [(25, T.perfil(**n), s) for n, s in T.EL_MONTON_VA_POR_NIVEL]
    casos += [(25, T.perfil(**n), s) for n, s in T.UN_ACOMPANANTE_EN_CUATRO]
    casos += [
        (
            e,
            T.perfil(defending=16, playmaking=12)
            if h
            else T.perfil(defending=12, playmaking=9),
            s,
        )
        for e, h, s in T.LA_EDAD_POR_ENCIMA_DE_33
    ]
    casos += [(25, T.perfil(**n), s) for n, s in T.EL_PASADOR_SE_RECLASIFICA]
    casos += [
        (25, T.perfil(keeper=13, defending=8, set_pieces=bp), s)
        for bp, s in T.EL_SUELO_DEL_BALON_PARADO
    ]
    casos += [
        (e, T.perfil(**n), s)
        for e, n, s, _d in T.EL_BALON_PARADO_Y_EL_TOPE_DE_DIAS
    ]
    casos += [
        (25, T.perfil(defending=16, playmaking=10, passing=9, winger=lat), s)
        for lat, s in T.EL_DEFENSA_NO_TIENE_SEGUNDA_LISTA
    ]
    casos += [
        (25, T.perfil(scoring=16, passing=9, winger=10, defending=defe), s)
        for defe, s in T.AL_DELANTERO_NO_LE_ENTRA_LA_DEFENSA
    ]
    return casos


#: La rejilla de 4x4 del extremo, que se puntua por ORDEN y no por cadena.
def rejilla() -> list[tuple[int, dict[str, int], str]]:
    return [
        (25, T.perfil(winger=10, passing=7, playmaking=jug, scoring=ano), s)
        for (jug, ano), s in sorted(T.REJILLA_DEL_ORDEN.items())
    ]


#: EL TOPE DE DIAS, que no sale en la CADENA de criterios y por eso el banco no
#: lo veia. QUINTO punto ciego del mismo tipo, y se destapo igual que los otros:
#: la auditoria de `cuanto_esta_fijado_cada_numero.py` daba EDAD_CON_TOPE_DE_DIAS
#: y TOPE_DE_DIAS_OBSERVADO como «sin fijar» cuando estan medidos en cuatro
#: perfiles. No es que no estuvieran medidos: es que el banco no los miraba.
def dias() -> list[tuple[int, dict[str, int], int | None]]:
    return [(e, dict(n), d) for e, n, _s, d in T.EL_BALON_PARADO_Y_EL_TOPE_DE_DIAS]


#: EL LATERAL DEL MEDIOCENTRO, que se puntua por un BOOLEANO --si es criterio
#: o no-- y por eso el banco no lo miraba. Punto ciego real: el 2026-10-12 una
#: medida nueva («Jugadas 8, Lateral 6 y nada mas») me hizo cambiar el umbral
#: del Lateral de 7 a 6, el banco dio 404/404 y fueron las PRUEBAS SUELTAS las
#: que cazaron que eso rompia las noventa celdas de la rejilla. Lo que estaba
#: mal era el hueco a la dominante, no el umbral.
#:
#: Cuarta vez que un banco incompleto da el visto bueno a un cambio malo.
def laterales() -> list[tuple[dict[str, int], bool]]:
    casos: list[tuple[dict[str, int], bool]] = []
    for dominante in (12, 14, 16, 18, 20):
        for lat in (4, 5, 6, 7, 8, 9):
            casos.append(
                (perfil(playmaking=dominante, passing=9, winger=lat), lat >= 7)
            )
    for lat in (4, 5, 6, 7, 8):
        casos.append((perfil(playmaking=16, defending=10, winger=lat), lat >= 7))
        casos.append((perfil(playmaking=16, scoring=10, winger=lat), lat >= 5))
    for ano in (4, 5, 6, 7, 8, 9):
        casos.append((perfil(playmaking=16, winger=5, scoring=ano), ano >= 5))
    for defe in (4, 5, 6, 7, 8, 9):
        for ano in (10, 14):
            casos.append(
                (perfil(playmaking=16, winger=5, scoring=ano, defending=defe), defe <= 4)
            )
    # y el barrido del 2026-10-12 con el Lateral A SOLAS, que fija el hueco
    casos += [(perfil(playmaking=j, winger=l), b) for j, l, b in T.EL_LATERAL_A_SOLAS]
    return casos


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
    # VACIO otra vez, y esta vez cerrando la ultima familia que quedaba: la
    # ENTRADA DEL CUARTO. Los catorce que habia aqui se arreglaron el
    # 2026-10-12 con dos piezas --el corte por NIVEL en vez de por
    # `nivel - posicion`, y el cuarto puesto que en 5 pide que la segunda de
    # la plantilla no pase de 7-- y estan fijados en
    # `test_criterios_hattrick.LA_ENTRADA_DEL_CUARTO`.
    #
    # Cuando una tanda saque un fallo nuevo, va aqui con su familia, y se
    # queda hasta que un candidato lo arregle SIN bajar el total medido.
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
    lat = laterales()
    dia = dias()
    ext = ordenes_del_extremo()
    bien += sum(
        1
        for n, esperado in ext
        if " ".join(
            T.ABREVIATURA[h] for h in C._puestos(dict(n), C._tipo(dict(n)))[: len(esperado.split())]
        )
        == esperado
    )
    bien += sum(
        1
        for n, esperado in lat
        if any(
            c.habilidad == "winger" and (c.operador != "<=") == esperado
            for c in C.criterios_de(25, dict(n)).habilidades
        )
    )
    bien += sum(
        1 for e, n, d in dia if C.criterios_de(e, dict(n)).tope_de_dias == d
    )
    tps = tipos()
    bien += sum(1 for n, esperado in tps if C._tipo(dict(n)) == esperado)
    total = len(cas) + len(rej) + len(ords) + len(ext) + len(lat) + len(dia) + len(tps)
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
