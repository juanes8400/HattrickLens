"""Qué cuenta como un movimiento de valor, y qué no.

2026-11-07, pedido del usuario: «Cambios: advertir qué movimientos de valor de
los jugadores ocurrieron al conectar, con umbrales (±5 % del valor)».

Lo que se defiende aquí es sobre todo lo que NO se avisa, que es donde está el
riesgo: un informe que inventa un movimiento es peor que uno que se calla.
"""

from datetime import UTC, datetime, timedelta

from app.domain.engines.movimiento_de_valor import (
    MOVIMIENTO_QUE_SE_AVISA,
    Lectura,
    movimiento_de,
    ordenados,
)

ANTES = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
AHORA = ANTES + timedelta(days=6)

#: La ventana con la que se le buscaron comparables. Mientras no cambie, dos
#: lecturas son comparables; cuando cambia, no.
MISMA = "edad=31;AN=18;PA=13;JU=7"
OTRA = "edad=32;AN=18;PA=13;JU=7"


def _lectura(valor: int | None, *, criterios: str = MISMA, n: int = 8, cuando=ANTES) -> Lectura:
    return Lectura(
        ht_player_id=472301981,
        nombre="Iñaki Bordalás",
        valor=valor,
        criterios=criterios,
        n=n,
        cuando=cuando,
    )


# --------------------------------------------------------------------------
# El umbral
# --------------------------------------------------------------------------


def test_el_umbral_es_el_cinco_por_ciento_que_pidio_el_usuario() -> None:
    assert MOVIMIENTO_QUE_SE_AVISA == 5.0


def test_una_subida_que_pasa_del_umbral_se_avisa() -> None:
    mv = movimiento_de(_lectura(1_000_000), _lectura(1_200_000, cuando=AHORA))
    assert mv is not None
    assert mv.clase == "movimiento"
    assert mv.diferencia == 200_000
    assert mv.porcentaje == 20.0


def test_una_bajada_tambien_se_avisa() -> None:
    """ES SIMETRICO A PROPOSITO. Una caída del 20 % en lo que vale un jugador
    es exactamente la misma noticia que una subida, y avisar sólo de lo bueno
    sería un informe que miente por omisión."""
    mv = movimiento_de(_lectura(1_000_000), _lectura(800_000, cuando=AHORA))
    assert mv is not None
    assert mv.clase == "movimiento"
    assert mv.porcentaje == -20.0


def test_un_movimiento_pequeño_no_se_avisa() -> None:
    """Sin umbral, cada sincronización traería la plantilla entera: una lectura
    se anota en cuanto el número cambia aunque sea en un euro, y un aviso que
    sale siempre enseña a saltárselo."""
    assert movimiento_de(_lectura(1_000_000), _lectura(1_030_000, cuando=AHORA)) is None


def test_el_umbral_se_puede_mover_para_quien_llame() -> None:
    chico = movimiento_de(
        _lectura(1_000_000), _lectura(1_030_000, cuando=AHORA), umbral=1.0
    )
    assert chico is not None
    assert chico.porcentaje == 3.0


def test_justo_en_el_umbral_se_avisa() -> None:
    """El borde entra: «a partir del ±5 %» incluye el 5 %."""
    mv = movimiento_de(_lectura(1_000_000), _lectura(1_050_000, cuando=AHORA))
    assert mv is not None
    assert mv.porcentaje == 5.0


# --------------------------------------------------------------------------
# Lo que no es un movimiento
# --------------------------------------------------------------------------


def test_un_cambio_de_criterios_lleva_porcentaje_pero_no_es_del_mercado() -> None:
    """DOS COSAS A LA VEZ, y hay que no confundirlas.

    Cuando cambian los criterios, el 2026-10-26 se decidió que la gráfica del
    precio VUELVE A EMPEZAR: desde ese día Hattrick compara al jugador con otra
    gente, y unir los dos tramos dibuja una subida que no ocurrió. Eso sigue en
    pie, y por eso esta fila va en su propio grupo con su nota.

    PERO EL PORCENTAJE SE ENSEÑA (2026-11-07, pedido del usuario: «quiero que
    se notifique el cambio en % de valoración así haya habido cambio de edad y
    lo otro»). Lo había hecho sin él y se lo discutí; lo reafirmó, y tiene su
    razón: el número que él ve en Valor de Plantilla sí cambió, y el total de
    su plantilla con él. Callar la cifra no la hacía desaparecer, sólo obligaba
    a calcularla a mano.

    Lo que queda separado es el SIGNIFICADO, que es lo que de verdad había que
    no mezclar.
    """
    mv = movimiento_de(
        _lectura(1_000_000),
        _lectura(1_400_000, criterios=OTRA, cuando=AHORA),
    )
    assert mv is not None
    assert mv.clase == "otra gente"
    assert mv.diferencia == 400_000
    assert mv.porcentaje == 40.0


def test_el_umbral_tambien_se_aplica_al_cambio_de_criterios() -> None:
    """Un cumpleaños que mueve la cifra un 1 % no es noticia.

    Sin umbral, este grupo saldría en el informe de cada jugador que cumple
    años --que es uno por semana y pico-- y se llenaría de ruido justo por ser
    el que menos acción pide.
    """
    assert (
        movimiento_de(
            _lectura(1_000_000),
            _lectura(1_010_000, criterios=OTRA, cuando=AHORA),
        )
        is None
    )


def test_un_salto_enorme_con_otros_criterios_sigue_sin_ser_del_mercado() -> None:
    """El porcentaje se enseña, pero la clase no cambia: un 4.900 % con otra
    gente detrás sigue siendo un cambio de pregunta y no una subida."""
    mv = movimiento_de(
        _lectura(100_000),
        _lectura(5_000_000, criterios=OTRA, cuando=AHORA),
    )
    assert mv is not None
    assert mv.clase == "otra gente"
    assert mv.porcentaje == 4900.0


def test_mismo_numero_con_otros_criterios_no_dice_nada() -> None:
    """Cambió con quién se le compara y la cifra salió igual. No hay nada que
    contarle al usuario: ni se movió, ni la diferencia vale nada."""
    assert (
        movimiento_de(
            _lectura(1_000_000),
            _lectura(1_000_000, criterios=OTRA, cuando=AHORA),
        )
        is None
    )


def test_sin_lectura_anterior_no_se_avisa_nada() -> None:
    """Un jugador que llegó entre las dos sincronizaciones NO estrena valor: es
    un jugador nuevo, y de eso Cambios ya avisa por su cuenta. Contarlo aquí lo
    anunciaría dos veces."""
    assert movimiento_de(None, _lectura(1_000_000, cuando=AHORA)) is None


def test_sin_numero_a_los_dos_lados_no_hay_nada() -> None:
    assert movimiento_de(_lectura(None), _lectura(None, cuando=AHORA)) is None


# --------------------------------------------------------------------------
# Estrenar y perder
# --------------------------------------------------------------------------


def test_estrenar_numero_se_cuenta_aparte_y_sin_porcentaje() -> None:
    """No se puede dividir por lo que no había. Un «+∞ %» no es una cifra, y un
    0 % se leería como «no se movió»."""
    mv = movimiento_de(_lectura(None, n=0), _lectura(900_000, cuando=AHORA))
    assert mv is not None
    assert mv.clase == "estreno"
    assert mv.antes is None
    assert mv.ahora == 900_000
    assert mv.porcentaje is None


def test_un_cero_de_antes_tambien_es_un_estreno() -> None:
    """No debería pasar --un valor es `None` o es positivo-- pero si llegara un
    cero, dividir por él rompería. Se trata como lo que sería: no había
    número."""
    mv = movimiento_de(_lectura(0), _lectura(900_000, cuando=AHORA))
    assert mv is not None
    assert mv.clase == "estreno"


def test_perder_el_numero_se_dice_sin_dramatizarlo() -> None:
    """Pasa cuando sus comparables caducan sin que entren otros. NO es que el
    jugador valga menos: es que dejamos de saber lo que vale, y decirlo como
    una caída sería mentir."""
    mv = movimiento_de(_lectura(900_000), _lectura(None, n=0, cuando=AHORA))
    assert mv is not None
    assert mv.clase == "perdido"
    assert mv.antes == 900_000
    assert mv.ahora is None
    assert mv.porcentaje is None


# --------------------------------------------------------------------------
# El orden
# --------------------------------------------------------------------------


def test_el_orden_pone_delante_lo_que_mas_mueve_una_decision() -> None:
    """Los movimientos de verdad primero y por TAMAÑO, sin mirar el signo: una
    caída del 20 % pide tanta atención como una subida del 20 %."""
    sube_poco = movimiento_de(_lectura(1_000_000), _lectura(1_060_000, cuando=AHORA))
    baja_mucho = movimiento_de(_lectura(1_000_000), _lectura(700_000, cuando=AHORA))
    estrena = movimiento_de(_lectura(None, n=0), _lectura(900_000, cuando=AHORA))
    perdido = movimiento_de(_lectura(900_000), _lectura(None, n=0, cuando=AHORA))
    assert sube_poco is not None
    assert baja_mucho is not None
    assert estrena is not None
    assert perdido is not None

    puestos = [mv.clase for mv in ordenados([perdido, estrena, sube_poco, baja_mucho])]
    assert puestos == ["movimiento", "movimiento", "estreno", "perdido"]
    # Y dentro de los movimientos, el -30 % antes del +6 %.
    primero = ordenados([sube_poco, baja_mucho])[0]
    assert primero.porcentaje == -30.0
