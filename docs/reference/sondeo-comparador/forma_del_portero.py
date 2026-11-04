# -*- coding: utf-8 -*-
"""QUE FORMA TIENE EL DIAL DEL PORTERO, y que consulta la decide.

    backend/.venv/Scripts/python.exe docs/reference/sondeo-comparador/forma_del_portero.py

EL PROBLEMA QUE RESUELVE. El 2026-11-04 se cerro el rincon `Por 14`: las veinte
observaciones de portero salen todas. Pero salen con MAS DE UNA lectura. Las
medidas de portero caen casi todas en una diagonal estrecha --Porteria alta con
Defensa baja, o Porteria baja con Defensa alta-- y en una diagonal no se
distingue `Por + Def >= 21` de `Por + (Def - 3) >= 18`, que son la misma recta
corrida. El rincon esta fijado por sus bordes, no por su forma.

LO QUE HACE ESTE FICHERO, y por que no es una regresion sobre nada privado: no
ajusta parametros contra la plantilla de nadie. Enumera a lo bruto una FAMILIA
de lecturas, se queda con las que reproducen lo medido --respuestas del panel
«Editar busqueda» de Hattrick, que son hechos generales del juego-- y despues
busca el perfil cuya respuesta PARTE EN DOS ese conjunto de supervivientes. El
resultado no es un numero ajustado: es una pregunta que hacerle al juego.

COMO SE USA. Se ejecuta, dice la mejor consulta, se mide esa consulta en el
panel, se anota en `MEDIDO` y se vuelve a ejecutar. Cada respuesta parte el
conjunto; con suerte, cinco o seis respuestas lo dejan en una sola lectura.

LA LECTURA BARATA DE CADA CONSULTA: si la linea de Edad sale con un ano clavado
--«Edad = 26»-- el dial va AJUSTADO; si sale con ventana --«Edad >= 25 y
Edad <= 27»-- va HOLGADO. No hace falta copiar la cadena entera.
"""

from __future__ import annotations

import itertools
import sys
from dataclasses import dataclass

sys.path.insert(0, "backend")

#: Lo medido, del registro, SOLO portero y SOLO el dial.
#: (porteria, defensa, balon parado, aflojo)
#:
#: De donde sale cada bloque:
#:   · `Por 14 Def 2 BP 10-16` y `Por 14 BP 13 Def 2/4/6`: sondas del
#:     2026-10-26, en `portero-cerrado.txt`.
#:   · `Por 14 Def 6 BP 9`: FASE AM, `fase-a.txt:305`, y lo delata su banda
#:     `BP 7-11`, la semianchura de dos del dial ajustado.
#:   · `Por 15 Def 5/6/7` y `Por 12 Def 8`, `Por 16 Def 0`: barrido del liston
#:     por tipo, `fase-a.txt:294`.
#:   · `Por 15 Def 5 BP 13`: la consulta del 2026-10-28.
#:   · `Por 8 Def 0 BP 11-16`: `EL_DESCUENTO_DEL_BALON_PARADO` y
#:     `LOS_CINCO_NUMEROS_ACOTADOS`.
#:   · `Por 13 Def 8 BP 1-6`: `EL_BALON_PARADO_ABAJO`, todas con `Ed24-26`.
#:   · `Por 13 Def 8 BP 14-15`: FASE AM6, bandas `[11,17]` y `[12,18]`, que son
#:     la semianchura de TRES del dial holgado.
#:   · `Por 16 Def 10 BP 12`: `fase-a.txt:28`, `Ed24-26`.
#:
#: NO ESTA `Por 14 Def 6 BP 15`: no hay sonda. Ver el apunte en
#: `EL_RINCON_DE_POR_14`.
MEDIDO: list[tuple[int, int, int, bool]] = [
    (14, 2, 10, False),
    (14, 2, 11, False),
    (14, 2, 12, False),
    (14, 2, 13, False),
    (14, 2, 14, False),
    (14, 2, 15, False),
    (14, 2, 16, True),
    (14, 4, 13, False),
    (14, 6, 9, False),
    (14, 6, 13, True),
    (15, 5, 0, False),
    (15, 6, 0, True),
    (15, 7, 0, True),
    (15, 5, 13, True),
    (12, 8, 0, False),
    (16, 0, 0, False),
    (8, 0, 11, False),
    (8, 0, 12, False),
    (8, 0, 13, False),
    (8, 0, 14, False),
    (8, 0, 16, True),
    (13, 8, 1, True),
    (13, 8, 2, True),
    (13, 8, 3, True),
    (13, 8, 4, True),
    (13, 8, 5, True),
    (13, 8, 6, True),
    (13, 8, 14, True),
    (13, 8, 15, True),
    (16, 10, 12, True),
    # --- LA TANDA DEL 2026-11-04, conducida en el panel ---------------------
    (15, 2, 15, False),
    (16, 0, 15, False),
    (9, 8, 15, True),
    (14, 6, 12, True),
    (14, 3, 15, False),
    (14, 4, 14, False),
]

#: La Porteria de 17 afloja ella sola. No es del portero: se midio en los cinco
#: tipos, asi que aqui no se pone en duda, se da por fija.
PRIMERA_QUE_AFLOJA_SOLA = 17
#: El peaje del tercer puesto, medido fuera del portero en decenas de casos.
PEAJE_DEL_TERCERO = 6


@dataclass(frozen=True, slots=True)
class Lectura:
    """Una forma candidata del dial del portero.

    `compite` es el modelo viejo, el que fallaba: el balon parado entra en la
    cola de puestos con su descuento y puede adelantar a la Defensa. Se deja
    dentro de la familia a proposito, como control: si el arnes no lo elimina,
    el arnes esta mal.
    """

    liston: int
    #: Descuento y umbral de entrada de la Defensa.
    desc_def: int
    entra_def: int
    #: Descuento y umbral de entrada del balon parado.
    desc_bp: int
    entra_bp: int
    #: Desde donde el balon parado afloja el solo. 99 = nunca.
    bp_solo: int
    compite: bool

    def rareza(self, por: int, dfn: int, bp: int) -> int:
        if self.compite:
            pesos = sorted([por, dfn, max(0, bp - self.desc_bp)], reverse=True)
            return pesos[0] + pesos[1] + max(0, pesos[2] - PEAJE_DEL_TERCERO)
        de_def = 0 if dfn < self.entra_def else max(0, dfn - self.desc_def)
        de_bp = 0 if bp < self.entra_bp else max(0, bp - self.desc_bp)
        return por + de_def + de_bp

    def holgado(self, por: int, dfn: int, bp: int) -> bool:
        return (
            por >= PRIMERA_QUE_AFLOJA_SOLA
            or bp >= self.bp_solo
            or self.rareza(por, dfn, bp) >= self.liston
        )

    def cuadra(self) -> bool:
        return all(self.holgado(p, d, b) is r for p, d, b, r in MEDIDO)

    def __str__(self) -> str:
        if self.compite:
            return f"COMPITE liston {self.liston} descBP {self.desc_bp}"
        def_ = f"Def-{self.desc_def}"
        if self.entra_def > self.desc_def:
            def_ += f" (desde {self.entra_def})"
        bp = f"BP-{self.desc_bp}"
        if self.entra_bp > self.desc_bp:
            bp += f" (desde {self.entra_bp})"
        solo = f" BP{self.bp_solo} afloja solo" if self.bp_solo < 99 else " sin regla del BP"
        return f"liston {self.liston}, Por + {def_} + {bp},{solo}"


def familia() -> list[Lectura]:
    """Todas las lecturas candidatas, antes de filtrar."""
    fuera: list[Lectura] = []
    for liston, desc_bp in itertools.product(range(14, 29), range(4, 17)):
        fuera.append(Lectura(liston, 0, 0, desc_bp, 0, 99, True))
    rangos = itertools.product(
        range(14, 29),      # liston
        range(0, 9),        # descuento de la Defensa
        range(0, 10),       # entrada de la Defensa
        range(4, 18),       # descuento del balon parado
        range(0, 18),       # entrada del balon parado
        (16, 17, 18, 19, 20, 21, 99),
    )
    for liston, dd, ed, ds, es, solo in rangos:
        # Canonico: una entrada por debajo del descuento no hace nada.
        if ed and ed <= dd:
            continue
        if es and es <= ds:
            continue
        fuera.append(Lectura(liston, dd, ed, ds, es, solo, False))
    return fuera


def sobreviven() -> list[Lectura]:
    return [x for x in familia() if x.cuadra()]


def clases(vivas: list[Lectura], sondas: list[tuple[int, int, int]]) -> dict:
    """Agrupa las lecturas que contestan IGUAL a todas las sondas candidatas.

    Dos lecturas con parametros distintos que predicen lo mismo en todo el
    espacio no son dos lecturas: son la misma escrita de dos maneras, y no hay
    consulta que las separe. Lo que se cuenta son las clases.
    """
    grupos: dict[tuple[bool, ...], list[Lectura]] = {}
    for x in vivas:
        firma = tuple(x.holgado(*s) for s in sondas)
        grupos.setdefault(firma, []).append(x)
    return grupos


def main() -> None:
    todas = familia()
    vivas = sobreviven()
    compiten = [x for x in vivas if x.compite]
    print(f"familia             {len(todas)} lecturas")
    print(f"cuadran con lo medido  {len(vivas)}")
    print(f"  de ellas, del modelo viejo (el que competia): {len(compiten)}")
    if compiten:
        print("  OJO: el arnes no elimina el modelo que sabemos que falla.")
        for x in compiten[:5]:
            print(f"    {x}")

    # Las sondas candidatas: porterias por debajo del 17 que afloja solo, que
    # es donde el dial se puede leer, y el balon parado entero.
    sondas = [
        (p, d, b)
        for p in range(2, 17)
        for d in range(0, 13)
        for b in range(0, 21)
    ]
    grupos = clases(vivas, sondas)
    print(f"\nclases de verdad distintas: {len(grupos)}")
    print("(dos lecturas que contestan igual a TODAS las sondas son la misma)")

    if len(grupos) <= 1:
        print("\nCERRADO: una sola lectura. No hay nada que preguntar.")
        return

    firmas = list(grupos)
    mejor = []
    for i, s in enumerate(sondas):
        dicen_si = sum(1 for f in firmas if f[i])
        parte = min(dicen_si, len(firmas) - dicen_si)
        mejor.append((parte, s, dicen_si))
    mejor.sort(key=lambda x: (-x[0], x[1][0] + x[1][1] + x[1][2]))

    print("\nLAS CONSULTAS QUE MAS PARTEN EL CONJUNTO")
    print("(a los 26 anos, con Lateral, Anotacion y Jugadas por debajo de 5)\n")
    vistas = set()
    puestas = 0
    for parte, (p, d, b), dicen_si in mejor:
        if parte == 0:
            break
        clave = (p, d, b)
        if clave in vistas:
            continue
        vistas.add(clave)
        print(
            f"  Por {p:2d}  Def {d:2d}  BP {b:2d}   ->  "
            f"{dicen_si} clases dicen HOLGADO, {len(firmas) - dicen_si} dicen AJUSTADO"
        )
        puestas += 1
        if puestas >= 12:
            break

    print("\nY LAS CLASES QUE QUEDAN, una lectura de muestra por clase:")
    for n, (firma, lista) in enumerate(sorted(grupos.items(), key=lambda kv: -len(kv[1])), 1):
        print(f"  {n}. ({len(lista):5d} formas de escribirla)  {lista[0]}")
        if n >= 12:
            print(f"  ... y {len(grupos) - 12} clases mas")
            break


if __name__ == "__main__":
    main()
