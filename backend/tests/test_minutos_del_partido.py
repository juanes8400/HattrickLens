"""Los minutos por puesto, reconstruidos del partido.

El caso que lo motivó todo está el primero: 87 minutos de lateral y 3 de
extremo, reportado por un usuario el 2026-10-08.
"""

from app.domain.engines.minutos_del_partido import (
    Orden,
    Titular,
    Tramo,
    tramos_del_partido,
    mejores_minutos,
)

LATERAL_IZQ = 105
EXTREMO_IZQ = 110
MEDIO = 108
PORTERO = 100


def once(*pares: tuple[int, int]) -> list[Titular]:
    return [Titular(jugador, puesto) for jugador, puesto in pares]


def de(tramos: list[Tramo], jugador: int) -> dict[int, int]:
    """Los minutos de un jugador, SUMADOS por puesto.

    Se suma y no se sobrescribe porque un jugador puede volver a un puesto en
    el que ya estuvo --sale de mediocentro, lo mueven a extremo, lo devuelven--
    y quedarse con el último tramo perdía los anteriores.
    """
    total: dict[int, int] = {}
    for t in tramos:
        if t.ht_player_id == jugador:
            total[t.position_code] = total.get(t.position_code, 0) + t.minutos
    return total


def test_el_caso_del_usuario_87_de_lateral_y_3_de_extremo() -> None:
    """2026-10-08: «played as WB for 87 minutes and then as W for 3 minutes».

    Antes de esto, la aplicación guardaba una sola fila por partido --el puesto
    en el que acabó y el total de minutos-- así que este jugador entraba como
    «extremo, 90 minutos» y con entrenamiento de Lateral recibía el 100 % de la
    semana. Le tocaba el 51,7 %: el lateral cobra el 50 %.
    """
    tramos = tramos_del_partido(
        once((7, LATERAL_IZQ)),
        [Orden(minuto=87, sale=7, entra=7, nuevo_puesto=EXTREMO_IZQ)],
    )
    assert de(tramos, 7) == {LATERAL_IZQ: 87, EXTREMO_IZQ: 3}


def test_quien_no_se_mueve_sale_con_un_solo_tramo() -> None:
    tramos = tramos_del_partido(once((7, MEDIO), (9, PORTERO)), [])
    assert de(tramos, 7) == {MEDIO: 90}
    assert de(tramos, 9) == {PORTERO: 90}


def test_una_sustitucion_reparte_los_minutos_entre_los_dos() -> None:
    """El que sale se lleva lo jugado; el que entra, lo que queda."""
    tramos = tramos_del_partido(
        once((7, MEDIO)),
        [Orden(minuto=63, sale=7, entra=8, nuevo_puesto=MEDIO)],
    )
    assert de(tramos, 7) == {MEDIO: 63}
    assert de(tramos, 8) == {MEDIO: 27}


def test_el_suplente_puede_entrar_en_un_puesto_distinto_del_que_dejo_el_otro() -> None:
    tramos = tramos_del_partido(
        once((7, LATERAL_IZQ)),
        [Orden(minuto=60, sale=7, entra=8, nuevo_puesto=EXTREMO_IZQ)],
    )
    assert de(tramos, 7) == {LATERAL_IZQ: 60}
    assert de(tramos, 8) == {EXTREMO_IZQ: 30}


def test_un_intercambio_mueve_a_los_dos_y_no_entra_nadie() -> None:
    """La orden de dos jugadores: cada uno se queda con el puesto del otro.

    Se decide por el ESTADO --los dos ya estaban jugando-- y no por el código
    de la orden, así que no hace falta saber qué `OrderType` usa Hattrick.
    """
    tramos = tramos_del_partido(
        once((7, LATERAL_IZQ), (8, EXTREMO_IZQ)),
        [Orden(minuto=30, sale=7, entra=8, nuevo_puesto=LATERAL_IZQ)],
    )
    assert de(tramos, 7) == {LATERAL_IZQ: 30, EXTREMO_IZQ: 60}
    assert de(tramos, 8) == {EXTREMO_IZQ: 30, LATERAL_IZQ: 60}


def test_varias_ordenes_se_aplican_en_orden_de_minuto() -> None:
    """Aunque lleguen desordenadas: el XML no promete ningún orden."""
    tramos = tramos_del_partido(
        once((7, LATERAL_IZQ)),
        [
            Orden(minuto=80, sale=7, entra=7, nuevo_puesto=MEDIO),
            Orden(minuto=40, sale=7, entra=7, nuevo_puesto=EXTREMO_IZQ),
        ],
    )
    assert de(tramos, 7) == {LATERAL_IZQ: 40, EXTREMO_IZQ: 40, MEDIO: 10}


def test_el_expulsado_se_va_cuando_dice_su_total() -> None:
    """Nadie lo sustituye, así que su marcha sólo consta en sus minutos.

    Sin el total se le darían los noventa, que es lo que pasaba antes: el
    expulsado en el minuto 20 cobraba la semana entera de entrenamiento.
    """
    tramos = tramos_del_partido(
        once((7, MEDIO)),
        [],
        minutos_totales={7: 20},
    )
    assert de(tramos, 7) == {MEDIO: 20}


def test_el_total_de_un_suplente_son_minutos_jugados_no_minuto_del_partido() -> None:
    """Entra en el 70 y juega 20: se va en el 90, no en el 20.

    Confundir las dos cosas dejaba al suplente con cero minutos, porque su
    total (20) quedaba por detrás del minuto en que había entrado (70).
    """
    tramos = tramos_del_partido(
        once((7, MEDIO)),
        [Orden(minuto=70, sale=7, entra=8, nuevo_puesto=MEDIO)],
        minutos_totales={7: 70, 8: 20},
    )
    assert de(tramos, 8) == {MEDIO: 20}


def test_con_la_duracion_dicha_un_total_mas_largo_no_alarga_el_partido() -> None:
    """Nadie juega más de lo que duró el partido, dicho lo que duró."""
    tramos = tramos_del_partido(once((7, MEDIO)), [], minutos_totales={7: 120}, duracion=90)
    assert de(tramos, 7) == {MEDIO: 90}


def test_sin_decir_la_duracion_la_prorroga_cuenta() -> None:
    """Y sin decirla, manda lo que publica Hattrick.

    Un partido de copa con prórroga dura 120 minutos, y recortarlos a 90 sería
    quitarle a cada titular media hora de entrenamiento. La duración no se sabe
    por otra vía: el XML de la alineación no la trae.
    """
    tramos = tramos_del_partido(once((7, MEDIO)), [], minutos_totales={7: 120})
    assert de(tramos, 7) == {MEDIO: 120}


def test_la_suma_de_un_jugador_nunca_pasa_de_los_noventa() -> None:
    """Por muchas órdenes que lo muevan."""
    tramos = tramos_del_partido(
        once((7, LATERAL_IZQ)),
        [Orden(minuto=m, sale=7, entra=7, nuevo_puesto=p) for m, p in ((10, MEDIO), (20, EXTREMO_IZQ), (30, MEDIO))],
    )
    assert sum(de(tramos, 7).values()) == 90


def test_una_orden_fuera_del_partido_no_inventa_minutos() -> None:
    """Un minuto por encima del final se recorta; uno negativo, al arranque."""
    tramos = tramos_del_partido(
        once((7, LATERAL_IZQ)),
        [Orden(minuto=200, sale=7, entra=7, nuevo_puesto=MEDIO)],
    )
    assert de(tramos, 7) == {LATERAL_IZQ: 90}


def test_el_partido_771779994_sale_igual_que_lo_cuenta_hattrick() -> None:
    """Contra datos reales, no inventados (2026-10-07, Pulgas Arrechas).

    El once, la única orden --portero cambiado en el minuto 89-- y los minutos
    que Hattrick publica por jugador. Los tres casos raros del partido salen
    solos y son justo los que antes no se sabían:

    · Duró 91 minutos, no 90. Con el 90 cableado, al suplente que entró en el
      89 le salía 1 minuto y Hattrick le cuenta 2.
    · El extremo 461351045 no aparece en ninguna orden y jugó 87: se fue sin
      que lo sustituyeran.
    · El portero sustituido se queda con sus 89.
    """
    titulares = once(
        (444563841, PORTERO),
        (490465993, 101),
        (498724298, 102),
        (479881607, 103),
        (493068717, 104),
        (495010544, 105),
        (497733329, 106),
        (492851039, 107),
        (493777217, 108),
        (498391736, 109),
        (461351045, 110),
    )
    ordenes = [Orden(minuto=89, sale=444563841, entra=434712334, nuevo_puesto=PORTERO)]
    totales = {
        444563841: 89, 490465993: 91, 498724298: 91, 479881607: 91, 493068717: 91,
        495010544: 91, 497733329: 91, 492851039: 91, 493777217: 91, 498391736: 91,
        461351045: 87, 434712334: 2,
    }

    tramos = tramos_del_partido(titulares, ordenes, minutos_totales=totales)

    reconstruido = {
        jugador: sum(t.minutos for t in tramos if t.ht_player_id == jugador)
        for jugador in totales
    }
    assert reconstruido == totales
    assert de(tramos, 434712334) == {PORTERO: 2}
    assert de(tramos, 461351045) == {110: 87}


EXTREMO, LATERAL = 1.0, 0.5  # lo que pesa cada puesto con entrenamiento de Lateral


def test_el_ejemplo_del_usuario_45_de_lateral_y_75_de_extremo() -> None:
    """Regla del usuario, 2026-10-09, con su propio ejemplo.

    «Si un jugador jugó 45 minutos como Defensa Lateral y 75 minutos como
    Extremo (45'+30' de prórroga), el entrenamiento es: 75 minutos al 100 % +
    15 minutos al 50 %.»

    Los 90 minutos de tope no son los primeros del reloj: son los que mejor
    entrenan. Por orden cronológico habrían salido 45 al 50 % y 45 al 100 %, un
    75 % de semana en vez del 91,7 %, y el jugador no eligió ese orden.
    """
    assert mejores_minutos([(45, LATERAL), (75, EXTREMO)]) == [(75, EXTREMO), (15, LATERAL)]

    equivalentes = sum(minutos * peso for minutos, peso in mejores_minutos([(45, LATERAL), (75, EXTREMO)]))
    assert equivalentes == 82.5
    assert round(equivalentes / 90, 4) == 0.9167


def test_sin_prorroga_no_se_descarta_nada() -> None:
    """Noventa minutos o menos caben enteros, y el orden no cambia el total."""
    assert mejores_minutos([(87, LATERAL), (3, EXTREMO)]) == [(3, EXTREMO), (87, LATERAL)]


def test_el_puesto_que_no_entrena_no_ocupa_cupo() -> None:
    """Un peso de cero no se lleva minutos que otro puesto podría aprovechar.

    Un delantero con entrenamiento de Lateral no entrena nada ahí, así que sus
    minutos no pueden quitarle sitio a los que sí valen.
    """
    assert mejores_minutos([(60, 0.0), (60, EXTREMO)]) == [(60, EXTREMO)]


def test_se_llena_de_mayor_a_menor_peso() -> None:
    """Tres tandas distintas: primero la que más vale, hasta llenar el cupo."""
    assert mejores_minutos([(40, 0.5), (40, 1.0), (40, 0.25)]) == [(40, 1.0), (40, 0.5), (10, 0.25)]


def test_lo_que_no_cabe_se_queda_fuera_entero() -> None:
    assert mejores_minutos([(120, EXTREMO)]) == [(90, EXTREMO)]


def test_el_partido_de_seleccion_41943634_con_sus_cambios_de_posicion() -> None:
    """Datos reales, y con la clase de orden que no había en el equipo propio.

    El fixture es Rwanda contra Guinea Ecuatorial del 2026-08-21, que ya vivía
    en el repositorio para otro motor. Trae las dos clases mezcladas: dos
    sustituciones y dos reubicaciones, y las cuatro en el minuto 60.

    Lo importante es lo que enseña: **las cuatro llegan con `OrderType` = 1**.
    El código de la orden NO distingue una sustitución de una reubicación, así
    que decidir por él habría metido a dos suplentes que nunca entraron. Lo que
    las separa es quién estaba en el campo, que es como se decide aquí.
    """
    from pathlib import Path

    from app.infrastructure.chpp.parsers import get_parser

    datos = get_parser("matchlineup")(
        (Path(__file__).parent / "fixtures" / "matchlineup_seleccion.xml").read_bytes()
    )
    titulares = [
        Titular(int(j["ht_player_id"]), int(j["role_id"]))
        for j in datos["starting_players"]
        if int(j["role_id"]) >= 100
    ]
    ordenes = [
        Orden(minuto=c["minuto"], sale=c["sale"], entra=c["entra"], nuevo_puesto=c["nuevo_puesto"])
        for c in datos["substitutions"]
    ]
    assert {c["order_type"] for c in datos["substitutions"]} == {1}

    tramos = tramos_del_partido(titulares, ordenes)

    # El titular sustituido en el 60 y el suplente que entró por él.
    assert de(tramos, 487733739) == {111: 60}
    assert de(tramos, 487848026) == {102: 30}
    # El que sale y entra él mismo no es una sustitución: siguió los 90.
    assert de(tramos, 486496709) == {109: 90}
    # Y como la orden lo mandaba al puesto que ya ocupaba, es UN solo tramo.
    assert len([t for t in tramos if t.ht_player_id == 486496709]) == 1
    # Un suplente que nunca entró no aparece.
    assert de(tramos, 489806840) == {}
