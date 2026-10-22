"""Mide el error del motor a ciegas: predice primero, puntua despues.

POR QUE EXISTE. El banco (600/600) NO es una tasa de acierto: esos casos son
los que construyeron la regla. La unica medida honesta es predecir perfiles que
el motor no ha visto y comparar con la pantalla de Hattrick. Este fichero hace
que el orden --prediccion antes que captura-- quede escrito y sea auditable, en
vez de ser una promesa.

    # 1. escribe las predicciones, fechadas, antes de mirar nada
    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/medir_el_error.py \
        predecir docs/reference/sondeo-comparador/fichas.txt

    # 2. con las capturas delante, puntua
    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/medir_el_error.py \
        puntuar predicciones-<sello>.txt capturas.txt fichas.txt

SE COMPARA EL SIGNIFICADO, NO EL TEXTO. Lo descubrio el primer ensayo del
2026-10-21: el motor decia «Ed35-99» y la pantalla «Edad >= 35», que es lo
MISMO, y un comparador de cadenas lo marcaba como fallo. Habriamos reportado un
error inflado y, peor, habriamos salido a «arreglar» un motor sano --el mismo
error que costo horas con «Def 5-8» contra «Def 5-7»--. Cada criterio se reduce
a (habilidad, minimo, maximo) y se comparan esas ternas. El OPERADOR NO ENTRA:
«>=11» y «11..20» son el mismo tramo, y «<=4» es «0..4».

LAS DOS REGLAS QUE ESTE FICHERO NO PUEDE VIGILAR, y que son las que se rompen:
  · EL MOTOR SE CONGELA durante la tanda. Si se arregla algo en el caso 7, del
    8 en adelante ya no son ciegos: miden el arreglo.
  · LA MUESTRA SE ELIGE ANTES. Nada de descartar una ficha porque salio mal.

FORMATOS

  fichas.txt      un jugador por linea, `#` comenta
                     nombre | edad | por def jug lat pas ano bp
                     Labrana | 24 | 1 11 4 5 5 3 7

  capturas.txt    el bloque «Criterios de busqueda» PEGADO TAL CUAL de la
                  pantalla, precedido del nombre con `==`
                     == Labrana
                     Edad = 24
                     Defensa = brillante
                     Pases = insuficiente
                     Lateral entre debil y aceptable
                     Jugadas <= debil
"""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, "backend")

from app.domain.engines.criterios_hattrick import (  # noqa: E402
    _tipo,
    EDAD_MAXIMA_DE_LA_ESCALA,
    MAXIMO_DE_LA_ESCALA,
    Criterios,
    criterios_de,
    es_holgado,
)

#: La escala oficial, de `frontend/src/i18n/glosario/es.json`, sin tildes
#: porque aqui todo se compara aplanado. Por encima de 20 Hattrick escribe
#: «divino (+1)».
ESCALA = [
    "nulo", "desastroso", "horrible", "pobre", "debil", "insuficiente",
    "aceptable", "bueno", "excelente", "formidable", "destacado", "brillante",
    "magnifico", "clase mundial", "sobrenatural", "titanico", "extraterrestre",
    "mitico", "magico", "utopico", "divino",
]

#: Como llama Hattrick en espanol a cada habilidad, en su pantalla.
HABILIDAD = {
    "balon parado": "set_pieces",
    "porteria": "keeper",
    "defensa": "defending",
    "jugadas": "playmaking",
    "lateral": "winger",
    "pases": "passing",
    "anotacion": "scoring",
}

ABREVIATURA = {
    "keeper": "Por", "defending": "Def", "playmaking": "Jug", "winger": "Lat",
    "passing": "Pas", "scoring": "Ano", "set_pieces": "BP",
}

K = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")


def _plano(texto: str) -> str:
    """Sin tildes, en minusculas y con los espacios apretados."""
    sin = unicodedata.normalize("NFD", texto.lower())
    sin = "".join(c for c in sin if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sin).strip()


def _nivel(palabra: str) -> int:
    """El numero de una palabra de la escala. «divino (+2)» -> 22."""
    p = _plano(palabra)
    mas = re.search(r"\(\+(\d+)\)", p)
    if mas:
        return MAXIMO_DE_LA_ESCALA + int(mas.group(1))
    if p in ESCALA:
        return ESCALA.index(p)
    if p.isdigit():
        return int(p)
    raise ValueError(f"nivel desconocido: «{palabra}»")


def _ternas_del_motor(c: Criterios) -> tuple[tuple, ...]:
    """La edad y cada criterio, reducidos a (que, minimo, maximo)."""
    return (("EDAD", c.edad_minima, c.edad_maxima),) + tuple(
        (k.habilidad, k.minimo, k.maximo) for k in c.habilidades
    )


def _tramo(resto: str, tope: int = MAXIMO_DE_LA_ESCALA) -> tuple[int, int]:
    """«= brillante» -> (11,11) · «entre debil y aceptable» -> (4,6)
    «<= debil» -> (0,4) · «>= 35» -> (35, tope)"""
    entre = re.match(r"entre (.+?) y (.+)$", resto)
    if entre:
        return _nivel(entre.group(1)), _nivel(entre.group(2))
    m = re.match(r"(<=|>=|=)\s*(.+)$", resto)
    if not m:
        raise ValueError(f"tramo que no se entiende: «{resto}»")
    op, valor = m.group(1), _nivel(m.group(2))
    if op == "=":
        return valor, valor
    if op == "<=":
        return 0, valor
    return valor, tope


def _ternas_de_la_pantalla(bloque: list[str]) -> tuple[tuple, ...]:
    """Lo mismo, leido del bloque «Criterios de busqueda» pegado tal cual."""
    salida = []
    for linea in bloque:
        p = _plano(linea)
        if not p:
            continue
        if p.startswith("edad"):
            salida.append(("EDAD",) + _tramo(p[4:].strip(), tope=EDAD_MAXIMA_DE_LA_ESCALA))
            continue
        for nombre, clave in HABILIDAD.items():
            if p.startswith(nombre):
                salida.append((clave,) + _tramo(p[len(nombre):].strip()))
                break
        else:
            raise ValueError(f"linea que no se entiende: «{linea}»")
    return tuple(salida)


def _pinta(ternas: tuple[tuple, ...]) -> str:
    """Solo para que un fallo se lea. No se compara esto."""
    trozos = []
    for que, lo, hi in ternas:
        nombre = "Ed" if que == "EDAD" else ABREVIATURA[que]
        trozos.append(f"{nombre}={lo}" if lo == hi else f"{nombre} {lo}-{hi}")
    return " ".join(trozos)


def _lee_fichas(ruta: Path) -> list[tuple[str, int, dict[str, int]]]:
    fichas = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        nombre, edad, niveles = (t.strip() for t in linea.split("|"))
        n = dict(zip(K, (int(x) for x in niveles.split()), strict=True))
        n["stamina"] = 0
        fichas.append((nombre, int(edad), n))
    return fichas


def _lee_capturas(ruta: Path) -> dict[str, list[str]]:
    capturas: dict[str, list[str]] = {}
    actual = None
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.startswith("=="):
            actual = linea[2:].strip()
            capturas[actual] = []
        elif actual and linea.strip() and not linea.lstrip().startswith("#"):
            capturas[actual].append(linea)
    return capturas


def predecir(ruta: Path) -> None:
    sello = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")
    destino = ruta.parent / f"predicciones-{sello}.txt"
    fichas = _lee_fichas(ruta)
    lineas = [
        f"# predicciones escritas el {sello} UTC, ANTES de ver ninguna pantalla",
        f"# fichas: {ruta.name}  ({len(fichas)} jugadores)",
        "",
    ]
    for nombre, edad, n in fichas:
        fragil = frontera(edad, n)
        marca = f"   # FRONTERA: {', '.join(fragil)}" if fragil else ""
        lineas.append(f"{nombre} | {_pinta(_ternas_del_motor(criterios_de(edad, n)))}{marca}")
    destino.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"{len(fichas)} predicciones -> {destino}")
    print("NO toques el motor hasta haber puntuado la tanda entera.")


def puntuar(predicciones: Path, capturas: Path, fichas: Path) -> None:
    vistas = _lee_capturas(capturas)
    aciertos, fallos, sin_captura = 0, [], []
    # EL DESGLOSE POR HABILIDAD Y POR PUESTO (idea del usuario, 2026-10-21).
    # El porcentaje global dice CUANTO fallamos; esto dice DONDE, que es lo
    # que lleva a la regla que falta. NO se ajusta nada con ello: son cuentas
    # descriptivas sobre el resultado de la comparacion.
    por_habilidad: dict[str, list[int]] = {}
    por_puesto: dict[int, list[int]] = {}
    print(f"prediccion de: {predicciones.name}\n")
    for nombre, edad, n in _lee_fichas(fichas):
        if nombre not in vistas:
            sin_captura.append(nombre)
            continue
        mio = _ternas_del_motor(criterios_de(edad, n))
        suyo = _ternas_de_la_pantalla(vistas[nombre])
        _desglosa(mio, suyo, por_habilidad, por_puesto)
        if mio == suyo:
            aciertos += 1
            print(f"  ACIERTO  {nombre}")
            continue
        fallos.append(nombre)
        print(f"  FALLO    {nombre}")
        print(f"             predicho  {_pinta(mio)}")
        print(f"             pantalla  {_pinta(suyo)}")
        for a, b in zip(mio, suyo):
            if a != b:
                print(f"             divergen: {a}  vs  {b}")
                break
        else:
            print(f"             numero de criterios: {len(mio)} vs {len(suyo)}")

    n_tanda = aciertos + len(fallos)
    if sin_captura:
        print(f"\n  sin captura ({len(sin_captura)}): {', '.join(sin_captura)}")
    if not n_tanda:
        print("\nninguna ficha puntuada")
        return
    error = 100 - 100 * aciertos / n_tanda
    print(f"\nTANDA: {aciertos}/{n_tanda} acierto  ->  {error:.1f}% de error")
    if not fallos:
        cota = 100 * (1 - 0.05 ** (1 / n_tanda))
        print(f"sin fallos: el error queda por debajo del {cota:.0f}% con 95% de confianza")
    else:
        print("ANOTA LA CAUSA DE CADA FALLO ANTES DE TOCAR NADA. La causa es lo que")
        print("mueve el motor; el porcentaje solo es el titular.")

    _pinta_el_desglose(por_habilidad, por_puesto)


def _desglosa(
    mio: tuple[tuple, ...],
    suyo: tuple[tuple, ...],
    por_habilidad: dict[str, list[int]],
    por_puesto: dict[int, list[int]],
) -> None:
    """Apunta acierto/fallo de cada criterio por su habilidad y por su puesto.

    UN CRITERIO QUE NO ESTA EN LA PANTALLA CUENTA COMO FALLO de esa habilidad,
    que es lo correcto: predecir un criterio de mas es equivocarse igual que
    predecirlo mal. Lo mismo al reves.
    """
    mios = {t[0]: t for t in mio}
    suyos = {t[0]: t for t in suyo}
    for que in mios.keys() | suyos.keys():
        bien = int(mios.get(que) == suyos.get(que))
        por_habilidad.setdefault(que, []).append(bien)
    for puesto, (a, b) in enumerate(zip(mio, suyo)):
        por_puesto.setdefault(puesto, []).append(int(a == b))
    # Si uno tiene mas criterios que el otro, los que sobran son fallos de puesto.
    for puesto in range(min(len(mio), len(suyo)), max(len(mio), len(suyo))):
        por_puesto.setdefault(puesto, []).append(0)


def _pinta_el_desglose(
    por_habilidad: dict[str, list[int]], por_puesto: dict[int, list[int]]
) -> None:
    """Donde falla, que es lo que lleva a la regla que falta."""
    if not por_habilidad:
        return
    nombre = {**ABREVIATURA, 'EDAD': 'Edad'}
    print()
    print('POR HABILIDAD           bien/total    acierto')
    for que, v in sorted(por_habilidad.items(), key=lambda x: sum(x[1]) / len(x[1])):
        aviso = '   <-- el mas flojo' if sum(v) / len(v) < 1 and que == min(
            por_habilidad, key=lambda k: sum(por_habilidad[k]) / len(por_habilidad[k])
        ) else ''
        print(f'  {nombre.get(que, que):18} {sum(v):4}/{len(v):<4}   {100 * sum(v) / len(v):5.0f}%{aviso}')
    print()
    print('POR PUESTO EN LA LISTA  bien/total    acierto')
    for puesto, v in sorted(por_puesto.items()):
        como = 'edad' if puesto == 0 else f'criterio {puesto}'
        print(f'  {como:18} {sum(v):4}/{len(v):<4}   {100 * sum(v) / len(v):5.0f}%')

# --- la frontera: donde la regla cambia de forma con un paso de uno --------
#
# NO SE AJUSTA NADA AQUI. Es la propia regla preguntada por sus vecinos: se
# mueve cada habilidad y la edad un nivel arriba y abajo, y se mira si la
# FORMA de la respuesta cambia --otro tipo, otro lado del dial, otro orden de
# criterios, otro operador--. Que cambien los NUMEROS es normal y no cuenta:
# subir la Defensa un nivel mueve «Def=11» a «Def=12» y eso no es fragilidad.
#
# Para que sirve: los fallos deberian concentrarse en los perfiles de
# frontera. Eso es una prediccion comprobable EN LA MISMA TANDA, y si no se
# cumple, esta medida no vale y hay que tirarla.


def _firma(edad: int, n: dict[str, int]) -> tuple:
    """La FORMA de la respuesta, sin sus numeros."""
    c = criterios_de(edad, n)
    return (
        _tipo(n),
        es_holgado(n, edad=edad),
        tuple((k.habilidad, k.operador) for k in c.habilidades),
    )


def frontera(edad: int, n: dict[str, int]) -> list[str]:
    """Que vecinos a un paso cambian la forma de la respuesta."""
    base = _firma(edad, n)
    avisos = []
    for paso in (-1, 1):
        otra = max(17, edad + paso)
        if otra != edad and _firma(otra, n) != base:
            avisos.append(f"edad {paso:+d}")
    for hab in K:
        for paso in (-1, 1):
            v = n[hab] + paso
            if not 0 <= v <= MAXIMO_DE_LA_ESCALA:
                continue
            vecino = {**n, hab: v}
            if _firma(edad, vecino) != base:
                avisos.append(f"{ABREVIATURA[hab]} {paso:+d}")
    return avisos


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "predecir":
        predecir(Path(sys.argv[2]))
    elif len(sys.argv) >= 5 and sys.argv[1] == "puntuar":
        puntuar(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        print(__doc__)
