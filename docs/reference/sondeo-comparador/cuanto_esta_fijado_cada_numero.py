"""Cuanto esta FIJADO cada numero del motor, y que medirla para fijarlo.

POR QUE. El 2026-10-12 el banco llego a 380/380 sin pendientes, y eso tienta a
creer que los 39 numeros del motor estan medidos. No lo estan todos: un numero
puede estar DENTRO de un intervalo que el banco no distingue. Es el mismo vicio
que el tope de dias de FASE AC --una constante que parece medida y no lo esta--
pero por el otro lado.

QUE HACE. Dos cosas:

  1. Para cada constante entera, barre 0..45 y da el TRAMO CONTIGUO de valores
     que mantiene el banco intacto. Si el tramo es un solo valor, el numero esta
     clavado por la medida. Si es mas ancho, el numero es una ELECCION dentro de
     un intervalo, y eso hay que saberlo antes de apoyarse en el.

  2. Para los que solo estan acotados, busca un PERFIL que separe el valor
     actual de otro del tramo. Ese perfil es la consulta que hay que hacerle a
     Hattrick para fijarlo, y sale con su prediccion calculada.

QUE SALIO EL 2026-10-12: 30 de 39 clavados, 9 solo acotados. De los 9, tres no
son reglas --MAXIMO_DE_LA_ESCALA es de representacion, y las dos del tope de
dias no se consumen, FASE AC--. Los seis restantes tienen su consulta escrita
en fase-a.txt, FASE AJ.

COMO SE USA, desde la raiz del repo:

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/cuanto_esta_fijado_cada_numero.py

Tarda un rato: cada valor candidato reevalua el banco entero.
"""

import io
import sys

sys.path.insert(0, "backend")
sys.path.insert(0, "backend/tests")
sys.path.insert(0, "docs/reference/sondeo-comparador")

import banco  # noqa: E402
import test_criterios_hattrick as T  # noqa: E402

from app.domain.engines import criterios_hattrick as C  # noqa: E402

TOPE = 45


def puntua() -> int:
    """El banco, en silencio."""
    callado = io.StringIO()
    real, sys.stdout = sys.stdout, callado
    try:
        return banco.puntua("x")[0]
    finally:
        sys.stdout = real


def numeros() -> list[str]:
    return sorted(
        n
        for n, v in vars(C).items()
        if n.isupper() and isinstance(v, int) and not isinstance(v, bool)
    )


def tramo(nombre: str, base: int) -> tuple[int, int]:
    """El tramo contiguo alrededor del valor actual que mantiene el banco."""
    actual = getattr(C, nombre)
    buenos = set()
    for cand in range(0, TOPE + 1):
        setattr(C, nombre, cand)
        try:
            if puntua() == base:
                buenos.add(cand)
        except Exception:  # noqa: BLE001 - una constante absurda puede reventar
            pass
    setattr(C, nombre, actual)
    lo = hi = actual
    while lo - 1 in buenos:
        lo -= 1
    while hi + 1 in buenos:
        hi += 1
    return lo, hi


def perfiles_de_prueba():
    """Perfiles variados donde buscar una separacion. No pretende ser exhaustivo."""
    for por in range(8, 19, 2):
        for defe in range(0, 12, 2):
            for bp in range(0, 21):
                yield 25, T.perfil(keeper=por, defending=defe, set_pieces=bp)
    for dom in ("winger", "playmaking", "defending", "scoring"):
        for alto in range(8, 18):
            for a in range(0, 13):
                for b in range(0, 9):
                    for pareja in (("passing", "scoring"), ("winger", "passing")):
                        if dom in pareja:
                            continue
                        yield 25, T.perfil(**{dom: alto, pareja[0]: a, pareja[1]: b})
    for alto in range(10, 18):
        for v in range(6, 12):
            yield 25, T.perfil(winger=alto, playmaking=v, passing=v, defending=v, scoring=v)


def separa(nombre: str, otro: int):
    """El primer perfil donde el valor actual y `otro` dan criterios distintos."""
    actual = getattr(C, nombre)
    try:
        for edad, niv in perfiles_de_prueba():
            setattr(C, nombre, actual)
            try:
                a = T._pinta(C.criterios_de(edad, dict(niv)))
            except Exception:  # noqa: BLE001
                continue
            setattr(C, nombre, otro)
            try:
                b = T._pinta(C.criterios_de(edad, dict(niv)))
            except Exception:  # noqa: BLE001
                continue
            if a != b:
                return edad, dict(niv), a, b
    finally:
        setattr(C, nombre, actual)
    return None


def main() -> None:
    base = puntua()
    print(f"banco {base}")
    print()
    clavados, acotados = [], []
    for nombre in numeros():
        actual = getattr(C, nombre)
        lo, hi = tramo(nombre, base)
        (clavados if lo == hi else acotados).append((nombre, actual, lo, hi))

    print(f"CLAVADOS por la medida ({len(clavados)}): un solo valor mantiene el banco")
    for nombre, v, _lo, _hi in clavados:
        print(f"   {nombre} = {v}")

    print()
    print(f"SOLO ACOTADOS ({len(acotados)}): el banco no distingue dentro del tramo")
    for nombre, v, lo, hi in sorted(acotados, key=lambda f: f[2] - f[3]):
        ancho = hi - lo + 1
        cola = "+" if hi == TOPE else ""
        print(f"   {nombre} = {v}   vale {lo}-{hi}{cola}   ({ancho} valores)")
        otro = lo if lo != v else hi
        r = separa(nombre, otro)
        if r is None:
            print("      no se encontro perfil que lo separe en los barridos probados")
            continue
        edad, niv, a, b = r
        etiq = " ".join(f"{T.ABREVIATURA[k]}{x}" for k, x in niv.items() if x)
        print(f"      para fijarlo: edad {edad}  {etiq}")
        print(f"         con {v}: {a}")
        print(f"         con {otro}: {b}")


if __name__ == "__main__":
    main()
