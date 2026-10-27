"""Lo que ha costado la gente parecida a un jugador tuyo.

Lo que se vigila aquí no son los campos sino las maneras en que este motor
podría MENTIR SIN FALLAR:

  · dar por comparable a quien tiene los niveles pedidos en otras habilidades,
    es decir a quien juega a otra cosa;
  · dejar que un comparable peor desplace a uno mejor;
  · echar un dato que todavía estaba vivo;
  · dar un número con menos de seis, o repetir a alguien para llegar a seis;
  · contar la puja de un jugador tuyo, que es justo el precio que se quiere
    estimar.

Y los dos pesos, que se comprueban contra lo que dictó el usuario el
2026-10-27 --100 el clavado, 90 el sello, nada más-- porque si alguien añade
un tercero el motor sigue devolviendo un número y el número es otro.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    ORDEN_DE_DESEMPATE,
    PESO_DE_HATTRICK,
    PESO_DEL_CLAVADO,
    PESO_QUE_NO_CADUCA,
    REINTENTOS_DE_RESOLUCION,
    VIDA,
    Guardado,
    Objetivo,
    candidato_de,
    clave_de_criterios,
    comparables_de,
    cosecha,
    cuenta_para_el_numero,
    estimar,
    hay_que_buscar,
    le_toca_hoy,
    lo_ensenaria_hattrick,
    objetivo_de,
    peso_de,
    plan_de_busqueda,
    reemplazable,
    terna,
    ventana_de_hattrick,
)
from app.infrastructure.chpp.mercado import ID_DE_HABILIDAD

AHORA = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
MI_EQUIPO = 537758

#: Alberto Gutiérrez Caviedes, con el que se midió todo contra el mercado real:
#: 31 años, anotación 18, pases 13, creación 7.
EDAD = 31


def _hab(**niveles: int) -> dict[str, int]:
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 0)
    base.update(niveles)
    return base


SKILLS = _hab(scoring=18, passing=13, playmaking=7)


def _objetivo(ht_player_id: int = 777, edad: int = EDAD, **niveles: int) -> Objetivo:
    hecho = objetivo_de(ht_player_id, edad, _hab(**niveles) if niveles else SKILLS)
    assert hecho is not None
    return hecho


def _fila(ident: int, *, edad: int = EDAD, puja: int = 4_000_000, **extra):
    fila = {
        "ht_player_id": ident,
        "first_name": "Jugador",
        "last_name": str(ident),
        "age_years": edad,
        "asking_price": puja,
        "highest_bid": puja,
        "has_bids": puja > 0,
        "deadline": "2026-10-08 20:00:00",
        "tsi": 150_000,
        "specialty": 0,
        "injury_level": -1,
        "seller_team_id": 999_999,
        "seller_league_id": 92,
        "skills": dict(SKILLS),
    }
    fila.update(extra)
    return fila


def _candidato(edad: int = EDAD, **niveles: int):
    hecho = candidato_de(_fila(1, edad=edad, skills=_hab(**niveles) if niveles else SKILLS))
    assert hecho is not None
    return hecho


def _guardado(
    ident: int,
    *,
    precio: int = 1_000_000,
    semanas: float = 0,
    firme: bool = True,
    puja: int | None = None,
    intentos: int = 0,
    especialidad: int = 0,
    edad: int = EDAD,
    sin_las_siete: bool = False,
    **niveles: int,
) -> Guardado:
    """Una venta del fondo. Por defecto es clavada al objetivo, o sea 100%.

    LLEVA LAS SIETE HABILIDADES, como las lleva una venta de verdad desde el
    2026-10-10. Sin ellas no se puede preguntar por el sello, así que un
    comparable que no esté clavado no tendría peso ninguno y estas pruebas
    medirían un fondo que ya no existe. `sin_las_siete` reproduce a propósito
    las ventas viejas, que son las que se quedan sin poder avalarse.
    """
    habilidades = _hab(**niveles) if niveles else SKILLS
    tres = terna(habilidades)
    assert tres is not None
    return Guardado(
        ht_player_id=ident,
        nombre=f"Comparable {ident}",
        precio=precio,
        firme=firme,
        puja=puja if puja is not None else precio,
        visto_el=AHORA - timedelta(weeks=semanas),
        edad=edad,
        primaria=tres[0],
        secundaria=tres[1],
        terciaria=tres[2],
        especialidad=especialidad,
        intentos=intentos,
        habilidades={} if sin_las_siete else dict(habilidades),
    )


def _medidos(*ventas: Guardado, objetivo: Objetivo | None = None):
    return comparables_de(ventas, objetivo or _objetivo(), AHORA)


# --------------------------------------------------------------------------
# La terna
# --------------------------------------------------------------------------


def test_la_terna_son_tres_y_salen_de_las_seis_de_campo() -> None:
    """La resistencia y el balón parado no entran aunque sean altas.

    Con Alberto no es teoría: su balón parado es 9 y su creación 7, así que si
    contara le cambiaría la terciaria y se le compararía con otra gente. El
    buscador del propio Hattrick tampoco los menciona.
    """
    tres = terna(_hab(scoring=18, passing=13, playmaking=7, set_pieces=20, stamina=20))
    assert tres is not None
    assert [r.habilidad for r in tres] == ["scoring", "passing", "playmaking"]
    assert [r.nivel for r in tres] == [18, 13, 7]


def test_el_empate_lo_rompe_el_orden_que_dicto_el_usuario() -> None:
    tres = terna(dict.fromkeys(ORDEN_DE_DESEMPATE, 7))
    assert tres is not None
    assert [r.habilidad for r in tres] == ["playmaking", "keeper", "defending"]


def test_el_orden_de_desempate_es_el_que_el_dijo_y_son_seis() -> None:
    assert ORDEN_DE_DESEMPATE == (
        "playmaking",
        "keeper",
        "defending",
        "scoring",
        "winger",
        "passing",
    )
    assert "stamina" not in ORDEN_DE_DESEMPATE
    assert "set_pieces" not in ORDEN_DE_DESEMPATE


def test_sin_ninguna_habilidad_no_hay_terna_ni_objetivo() -> None:
    assert terna(dict.fromkeys(ORDEN_DE_DESEMPATE, 0)) is None
    assert terna({"stamina": 20, "set_pieces": 20}) is None
    assert objetivo_de(1, EDAD, dict.fromkeys(ORDEN_DE_DESEMPATE, 0)) is None
    assert objetivo_de(1, 0, SKILLS) is None


# --------------------------------------------------------------------------
# La escalera
# --------------------------------------------------------------------------


def test_SOLO_HAY_DOS_PESOS_y_son_los_que_dicto_el_usuario() -> None:
    """Dos, y nada entre ellos ni por debajo (2026-10-27).

    Sus palabras: «100 = coincidencia exacta Edad + top 3 habilidades» y «90 =
    aparece en el comparador de Hattrick pero no es exactamente el mismo
    jugador». Y cuando se le preguntó por los peldaños nuestros que quedaban
    sueltos: «solo hay esos dos escalones, el resto ya no los quiero».

    ANTES HABIA CUATRO MAS --95, 90, 80 y 75-- que puntuaban lo que hubo que
    mover, con una ventana propia para la terciaria. Si alguien los devuelve,
    el motor sigue dando un numero y el numero es otro: de ahi este test, que
    no comprueba una lista de constantes sino que BARRE los alrededores del
    objetivo y exige que no salga ningun peso de mas.
    """
    assert PESO_DEL_CLAVADO == 100
    assert PESO_DE_HATTRICK == 90
    # Y el clavado es el unico que no caduca: a un avalado todavia le puede
    # salir un clavado que lo sustituya.
    assert PESO_QUE_NO_CADUCA == PESO_DEL_CLAVADO

    objetivo = _objetivo()
    vistos: set[int] = set()
    for edad in range(EDAD - 3, EDAD + 4):
        for primaria in range(17, 20):
            for secundaria in range(11, 16):
                for terciaria in range(5, 10):
                    peso = peso_de(
                        _candidato(
                            edad=edad,
                            scoring=primaria,
                            passing=secundaria,
                            playmaking=terciaria,
                        ),
                        objetivo,
                    )
                    if peso is not None:
                        vistos.add(peso)
    assert vistos == {PESO_DEL_CLAVADO, PESO_DE_HATTRICK}


def test_LA_UNICA_BUSQUEDA_es_la_de_los_criterios_de_hattrick() -> None:
    """2026-10-26: «no hay busqueda ampliada... se acaba: solo criterios».

    Eran cinco ventanas --la de Hattrick y nuestros cuatro escalones-- y
    recorrerlas costaba hasta cinco peticiones por jugador. Con una sola, mirar
    la plantilla entera cuesta unas veinticinco al dia, y eso es lo que hace
    posible el barrido diario contra una cuota que es de la aplicacion.
    """
    leidas = [
        (
            v.peso,
            v.edad_minima,
            v.edad_maxima,
            v.primaria.minimo,
            v.primaria.maximo,
            v.secundaria.minimo,
            v.secundaria.maximo,
        )
        for v in plan_de_busqueda(_objetivo())
    ]
    # El peso de la ventana es el del sello, que desde el 2026-10-27 es 90.
    assert leidas == [(PESO_DE_HATTRICK, 30, 32, 18, 18, 12, 14)]


def test_no_se_pide_por_debajo_de_los_diecisiete_anos() -> None:
    """Gastar una llamada en un tramo donde no hay nadie es tirar cuota."""
    plan = plan_de_busqueda(_objetivo(edad=17))
    assert all(v.edad_minima >= 17 for v in plan)


def test_sin_las_siete_habilidades_NO_HAY_BUSQUEDA_y_esta_bien() -> None:
    """Antes la escalera hacia de red; ahora no hay red.

    Y es lo correcto: la regla de Hattrick necesita las siete, asi que sin
    ellas no se sabe a quien se parece el jugador. Buscar igual gastaria cuota
    para traer gente que despues no se puede puntuar.
    """
    from app.domain.engines.mercado_comparable import Objetivo, Rasgo

    pelado = Objetivo(
        ht_player_id=1,
        edad=31,
        primaria=Rasgo("scoring", 18),
        secundaria=Rasgo("passing", 13),
        terciaria=Rasgo("playmaking", 7),
    )
    assert plan_de_busqueda(pelado) == ()


# --------------------------------------------------------------------------
# El peso de un candidato
# --------------------------------------------------------------------------


def test_cada_peso_cobra_lo_que_le_toca() -> None:
    """El 100 es ser el mismo jugador; el 90, salir en su comparador."""
    objetivo = _objetivo()
    # Clavado: misma edad y las tres al mismo nivel.
    assert peso_de(_candidato(), objetivo) == PESO_DEL_CLAVADO
    # La segunda a mas o menos uno: Hattrick los ensenaria --su criterio para
    # la segunda es una banda-- pero NO son el mismo jugador. Noventa.
    assert peso_de(_candidato(scoring=18, passing=14, playmaking=7), objetivo) == 90
    assert peso_de(_candidato(scoring=18, passing=12, playmaking=7), objetivo) == 90
    # La PRIMERA a mas o menos uno no vale nada: Hattrick no la mueve nunca, y
    # desde el 2026-10-27 ya no hay escalera nuestra que la recoja.
    assert peso_de(_candidato(scoring=17, passing=13, playmaking=7), objetivo) is None
    assert peso_de(_candidato(scoring=19, passing=13, playmaking=7), objetivo) is None
    # Un ano arriba o abajo con las habilidades clavadas cae dentro de su
    # ventana de edad, asi que lo avala; clavado no esta, porque la edad es
    # parte del clavado.
    assert peso_de(_candidato(edad=32), objetivo) == 90
    assert peso_de(_candidato(edad=30), objetivo) == 90


def test_lo_que_no_esta_clavado_ni_avalado_no_tiene_peso() -> None:
    objetivo = _objetivo()
    assert peso_de(_candidato(scoring=18, passing=15, playmaking=7), objetivo) is None
    assert peso_de(_candidato(scoring=16, passing=13, playmaking=7), objetivo) is None
    assert peso_de(_candidato(edad=33), objetivo) is None
    assert peso_de(_candidato(edad=29), objetivo) is None


def test_la_terciaria_la_manda_SU_banda_y_ya_no_tenemos_otra() -> None:
    """La ventana de la terciaria es la de Hattrick, y no hay segunda opinión.

    HASTA EL 2026-10-21 ESTE TEST DECIA OTRA COSA: que mandaba una ventana
    nuestra de ±1 «ya en el escalón del 100%». Se escribió el 2026-10-06,
    CUATRO DIAS ANTES de que el usuario decidiera que el 100 lo pone Hattrick,
    y nunca se revisó porque el desempate corría delante del sello y tapaba la
    contradicción. Al poner el sello primero, salió.

    POR QUE LA SUYA. El objetivo es Anotación 18, Pases 13, Jugadas 7 a los 31.
    Hattrick le pide «Jugadas entre 6 y 9» --su banda-- asi que un candidato
    con Jugadas 9 SI aparece en su Comparador. Y su banda NO ES FIJA, que es lo
    que remata el argumento: aquí es 6-9 (-1/+2) y en Labraña, medido en vivo
    el 2026-10-19, el Lateral es 4-6 (-1/+1). No había un ±1 universal que
    defender.

    EL 2026-10-27 se fue también la nuestra: lo que cae fuera de su banda ya no
    tiene donde aterrizar.
    """
    objetivo = _objetivo()
    # Dentro de su banda (Jugadas 6-9): lo sella él, 90.
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=8), objetivo) == 90
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=9), objetivo) == 90
    # Fuera de su banda: antes caía a nuestro 95, ahora no cae en ningún sitio.
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=5), objetivo) is None
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=4), objetivo) is None


def test_la_ventana_de_hattrick_se_traga_el_ano_y_la_segunda_pero_no_la_primera() -> None:
    """Donde está el muro, y es el de la primera habilidad.

    Hattrick es MAS ANCHO que nosotros en la edad y en la segunda habilidad
    --su ventana de edad es de mas o menos un ano y su segunda es una banda--,
    asi que un candidato que abra esas dos a la vez sigue llevandose su sello.

    Y es MAS ESTRECHO en la primera, que el no mueve nunca. Con la primaria
    desviada un solo nivel ya no hay comparable: antes lo recogia nuestro
    escalon de edad por 75, y ese escalon se fue el 2026-10-27.
    """
    objetivo = _objetivo()
    assert peso_de(_candidato(edad=32, scoring=18, passing=12, playmaking=7), objetivo) == 90
    assert peso_de(_candidato(edad=30, scoring=19, passing=14, playmaking=7), objetivo) is None


def test_los_mismos_numeros_en_otras_habilidades_son_otro_jugador() -> None:
    """Un creador con 18 de creación y 13 de pases tiene los números de
    Alberto, pero su 18 no es de anotación: lo que se paga por él no dice nada
    de lo que se paga por un delantero. Sin comparar el nombre valdría 100%,
    que es el error más caro que este motor puede cometer."""
    otro = _candidato(playmaking=18, passing=13, scoring=7)
    assert otro.primaria.habilidad == "playmaking"
    assert peso_de(otro, _objetivo()) is None


def test_una_habilidad_de_mas_le_cambia_la_terna_y_lo_deja_fuera() -> None:
    """El caso real que decidió el usuario: Valerio Cataldi tenía anotación 18
    y pases 13 como Alberto, y además creación 13. Al empatar con pases, el
    desempate pone creación delante y su terna deja de ser la misma."""
    valerio = _candidato(scoring=18, passing=13, playmaking=13)
    assert valerio.secundaria.habilidad == "playmaking"
    assert peso_de(valerio, _objetivo()) is None


# --------------------------------------------------------------------------
# La cosecha de una búsqueda
# --------------------------------------------------------------------------


def test_los_que_tienen_puja_y_los_que_no_van_en_montones_distintos() -> None:
    """Con puja la venta está garantizada; sin ella sólo se anota si hace
    falta, porque cada uno cuesta una resolución."""
    con, sin = cosecha(
        _objetivo(),
        [_fila(1), _fila(2, puja=0), _fila(3)],
        mi_equipo=MI_EQUIPO,
    )
    assert sorted(c.ht_player_id for c, _ in con) == [1, 3]
    assert [c.ht_player_id for c, _ in sin] == [2]


def test_tu_propio_jugador_y_los_de_tu_equipo_no_cuentan() -> None:
    """Su precio es justo el que queremos estimar: contarlo sería escribir la
    respuesta en el enunciado."""
    con, sin = cosecha(
        _objetivo(ht_player_id=4242),
        [_fila(4242), _fila(5, seller_team_id=MI_EQUIPO), _fila(6)],
        mi_equipo=MI_EQUIPO,
    )
    assert [c.ht_player_id for c, _ in con] == [6]
    assert sin == []


def test_el_lesionado_y_el_sancionado_si_entran() -> None:
    """Decisión del usuario del 2026-10-06."""
    con, _ = cosecha(
        _objetivo(),
        [_fila(1, injury_level=3), _fila(2, injury_level=0)],
        mi_equipo=MI_EQUIPO,
    )
    assert sorted(c.ht_player_id for c, _ in con) == [1, 2]


def test_las_ligas_extranjeras_cuentan() -> None:
    con, _ = cosecha(_objetivo(), [_fila(1, seller_league_id=3)], mi_equipo=MI_EQUIPO)
    assert [c.ht_player_id for c, _ in con] == [1]


def test_quien_no_se_parece_no_entra_aunque_la_busqueda_lo_devuelva() -> None:
    """La búsqueda del juego no sabe pedir «esta habilidad la más alta»."""
    portero = _fila(1, skills=_hab(keeper=18, defending=13, scoring=7))
    con, sin = cosecha(_objetivo(), [portero], mi_equipo=MI_EQUIPO)
    assert con == [] and sin == []


def test_nadie_se_cuenta_dos_veces() -> None:
    con, _ = cosecha(
        _objetivo(),
        [_fila(1), _fila(1), _fila(2)],
        mi_equipo=MI_EQUIPO,
        ya_vistos=[2],
    )
    assert [c.ht_player_id for c, _ in con] == [1]


def test_cada_uno_viaja_con_su_peso() -> None:
    """El clavado y el avalado entran los dos, pero no valen lo mismo."""
    con, _ = cosecha(
        _objetivo(),
        [_fila(1), _fila(2, skills=_hab(scoring=18, passing=12, playmaking=7))],
        mi_equipo=MI_EQUIPO,
    )
    assert dict((c.ht_player_id, p) for c, p in con) == {1: 100, 2: 90}


# --------------------------------------------------------------------------
# El fondo del equipo
# --------------------------------------------------------------------------


def test_una_venta_vive_siete_semanas_y_luego_queda_reemplazable() -> None:
    """Cumplir la vida no la borra: una venta vieja informa mas que ninguna,
    asi que espera a que algo mas fresco ocupe su sitio."""
    assert timedelta(weeks=7) == VIDA
    assert reemplazable(_guardado(1, semanas=6), AHORA) is False
    assert reemplazable(_guardado(1, semanas=7), AHORA) is True


def test_una_venta_se_vuelve_a_medir_contra_quien_pregunte() -> None:
    """LA prueba del fondo compartido. La misma venta vale 100% para el jugador
    al que se parece y 90% para otro con un nivel menos de pases, sin
    gastar una sola llamada."""
    venta = _guardado(1)
    assert _medidos(venta)[0].peso == 100
    otro = _objetivo(scoring=18, passing=12, playmaking=7)
    assert _medidos(venta, objetivo=otro)[0].peso == 90


def test_una_venta_que_no_se_parece_a_quien_pregunta_no_entra() -> None:
    portero = _guardado(1, keeper=18, defending=13, scoring=7)
    assert _medidos(portero) == ()


def test_el_peso_manda_por_encima_de_la_frescura() -> None:
    """El usuario dijo que un comparable nunca se reemplaza por algo de menor
    peso, asi que una venta caducada al 100% va por delante de una recien
    encontrada al 90%."""
    vieja = _guardado(1, semanas=9)
    reciente = _guardado(2, semanas=0, scoring=18, passing=12, playmaking=7)
    elegidos = _medidos(reciente, vieja)
    assert [c.venta.ht_player_id for c in elegidos] == [1, 2]
    assert [c.peso for c in elegidos] == [100, 90]
    # Y la de veinte semanas NO cuenta como vieja, porque es un 100%: desde
    # el 2026-10-07 la caducidad solo alcanza a los parecidos.
    assert elegidos[0].viejo is False


def test_a_igual_peso_va_antes_la_mas_reciente() -> None:
    elegidos = _medidos(_guardado(1, semanas=5), _guardado(2, semanas=1))
    assert [c.venta.ht_player_id for c in elegidos] == [2, 1]


def test_a_igual_peso_y_fecha_va_antes_la_mas_cara() -> None:
    elegidos = _medidos(_guardado(1, precio=2_000_000), _guardado(2, precio=9_000_000))
    assert [c.venta.ht_player_id for c in elegidos] == [2, 1]


def test_en_el_ultimo_empate_gana_la_misma_especialidad() -> None:
    objetivo = Objetivo(
        ht_player_id=777,
        edad=EDAD,
        primaria=_objetivo().primaria,
        secundaria=_objetivo().secundaria,
        terciaria=_objetivo().terciaria,
        especialidad=2,
    )
    elegidos = comparables_de(
        [_guardado(1, especialidad=0), _guardado(2, especialidad=2)], objetivo, AHORA
    )
    assert [c.venta.ht_player_id for c in elegidos] == [2, 1]


def test_se_devuelven_mas_de_seis_si_empatan_con_el_sexto() -> None:
    """Cuantos mas datos haya mejor se describe el mercado: si un escalon trajo
    diez comparables igual de buenos, cuentan los diez."""
    assert len(_medidos(*(_guardado(i) for i in range(1, 11)))) == 10


def test_los_peores_se_quedan_fuera_cuando_hay_de_sobra() -> None:
    buenos = [_guardado(i) for i in range(1, 9)]
    flojo = _guardado(99, scoring=18, passing=12, playmaking=7)
    elegidos = _medidos(*buenos, flojo)
    assert 99 not in [c.venta.ht_player_id for c in elegidos]
    assert len(elegidos) == OBJETIVO


def test_con_seis_vivos_su_turno_no_gasta_ni_una_llamada() -> None:
    assert hay_que_buscar(_medidos(*(_guardado(i, semanas=1) for i in range(1, 9)))) is False


def test_se_busca_CUANDO_FALTAN_DATOS_y_solo_entonces() -> None:
    """Decision del usuario, 2026-10-09: «cuando nos quedemos sin datos».

    Antes un comparable caducado tambien mandaba a buscar, y el turno se
    gastaba entero en sustituirlo. Ya no: el refresco lo lleva el calendario
    --el exacto cada seis dias, los anchos cada cinco semanas-- y lo que
    dispara la busqueda ancha es no tener bastantes.

    El precio de la decision, y queda escrito aqui: un parecido puede cumplir
    sus siete semanas y seguir usandose hasta que a su jugador le toquen los
    anchos otra vez, hasta cinco semanas despues.
    """
    # Cinco de seis: falta uno, se busca.
    assert hay_que_buscar(_medidos(*(_guardado(i) for i in range(1, 8)))) is True

    # Seis, con uno PARECIDO y caducado: ya no se busca por eso.
    primo_viejo = _guardado(1, semanas=9, scoring=18, passing=12, playmaking=7)
    con_uno_viejo = [primo_viejo, *(_guardado(i, semanas=1) for i in range(2, 9))]
    assert hay_que_buscar(_medidos(*con_uno_viejo)) is False

    # Y uno exacto caducado tampoco, que ya era asi: el 100 % no caduca.
    exacto_viejo = [_guardado(1, semanas=9), *(_guardado(i, semanas=1) for i in range(2, 9))]
    assert hay_que_buscar(_medidos(*exacto_viejo)) is False


# --------------------------------------------------------------------------
# El numero
# --------------------------------------------------------------------------


def test_con_menos_de_OBJETIVO_SI_hay_numero_pero_avisando() -> None:
    """«Precio con los que hayan» (2026-10-26, decision del usuario).

    Hasta ese dia, por debajo de ocho ventas cerradas no se daba numero. Lo
    cambio al quitar la busqueda ampliada, y es la consecuencia directa: sin
    escalera ancha hay jugadores que no van a juntar ocho, y con la regla vieja
    se quedarian sin precio para siempre.

    Lo que no se pierde es el aviso: `n` dice sobre cuantas se hizo y
    `suficiente` dice si llegan a ocho.
    """
    e = estimar(_medidos(*(_guardado(i) for i in range(1, OBJETIVO))))
    assert e.media is not None and e.mediana is not None
    assert e.n == OBJETIVO - 1
    assert e.suficiente is False, "sigue diciendo que el numero es flojo"


def test_sin_NI_UNA_venta_cerrada_no_hay_numero() -> None:
    """Y esto no es una regla, es aritmetica: no hay nada que promediar.

    Las subastas vivas se enseñan pero no cuentan: una puja se queda corta y
    siempre por el mismo lado (2026-10-09).
    """
    e = estimar(_medidos(*(_guardado(i, firme=False) for i in range(1, 4))))
    assert e.media is None and e.mediana is None
    assert e.n == 0
    assert e.suficiente is False
    assert len(e.comparables) == 3, "pero se siguen enseñando"


def test_con_ocho_al_mismo_peso_la_media_es_la_de_siempre() -> None:
    precios = [
        1_000_000,
        2_000_000,
        3_000_000,
        4_000_000,
        5_000_000,
        6_000_000,
        7_000_000,
        8_000_000,
    ]
    e = estimar(_medidos(*(_guardado(i, precio=p) for i, p in enumerate(precios, start=1))))
    assert e.suficiente is True
    assert e.media == 4_500_000
    assert e.mediana == 4_500_000


def test_los_pesos_mueven_la_media_y_se_comprueba_a_mano() -> None:
    flojo = {"scoring": 18, "passing": 12, "playmaking": 7}
    e = estimar(
        _medidos(
            _guardado(1, precio=10_000_000),
            _guardado(2, precio=10_000_000),
            *(_guardado(i, precio=20_000_000, **flojo) for i in range(3, 9)),
        )
    )
    # (2*100*10M + 6*90*20M) / (2*100 + 6*90) = 12.800M / 740 = 17.297.297
    assert e.media == 17_297_297
    assert e.peso_minimo == 90


def test_la_mediana_tambien_va_ponderada() -> None:
    """Con pesos iguales coincide con la de toda la vida; en cuanto difieren,
    el punto que parte la muestra por la mitad se mueve."""
    flojo = {"scoring": 18, "passing": 12, "playmaking": 7}
    pesados = _medidos(
        *(_guardado(i, precio=i * 10) for i in range(1, 8)),
        _guardado(8, precio=80, **flojo),
    )
    # Peso total 7*100 + 90 = 790, mitad 395. Acumulando por precio: 100, 200,
    # 300, 400 pasa de la mitad en el cuarto, asi que la mediana es 40 y no 45.
    assert estimar(pesados).mediana == 40
    assert estimar(pesados).media != 30


def test_se_dice_cuantas_son_todavia_provisionales() -> None:
    """Una puja se queda corta: Valerio tenia 65 millones y cerro en 77,7, un
    16% mas. La pantalla tiene que poder avisar.

    Desde el 2026-10-09 las abiertas NO cuentan para el numero, asi que estas
    seis dan cuatro ventas y no bastan: `provisionales` se cuenta sobre todo
    lo que se enseña, que es de lo que la pantalla tiene que avisar.
    """
    e = estimar(
        _medidos(
            *(_guardado(i) for i in range(1, 5)),
            _guardado(5, firme=False),
            _guardado(6, firme=False),
        )
    )
    assert e.provisionales == 2
    assert e.n == 4
    assert e.suficiente is False


def test_con_ocho_ventas_cerradas_si_basta() -> None:
    """La contraparte del de arriba: ocho cerradas y ninguna abierta."""
    e = estimar(_medidos(*(_guardado(i) for i in range(1, 9))))
    assert e.provisionales == 0
    assert e.n == 8
    assert e.suficiente is True


# --------------------------------------------------------------------------
# Cuándo le toca a quién
# --------------------------------------------------------------------------
#
# UNA VEZ POR DIA NATURAL Y POR JUGADOR (2026-10-26, decision del usuario),
# independiente de cuantas veces se sincronice.
#
# LO QUE HABIA AQUI, y se fue con la escalera ancha: un reparto por turnos
# sacado del propio identificador --`% 5` contra la semana para los escalones
# anchos y `% 6` contra el dia para el exacto, disparado por la actualizacion
# economica de la liga menos 24 horas--. No guardaba ningun reloj y no habia
# nada que recolocar al fichar o vender, que para una rotacion es mejor diseno.
#
# Un barrido diario no rota: le toca a todos, todos los dias. La pregunta deja
# de ser «a quien le toca hoy» y pasa a ser «a este ya se le miro hoy», y esa
# depende de lo que haya pasado, asi que hay que guardarla.

AYER = datetime(2026, 10, 25, 23, 59, tzinfo=UTC)
HOY = datetime(2026, 10, 26, 0, 1, tzinfo=UTC)


def test_sin_sello_le_toca() -> None:
    """Nunca se le ha buscado nada."""
    assert le_toca_hoy(None, HOY) is True


def test_barrido_ayer_le_toca_hoy() -> None:
    assert le_toca_hoy(AYER, HOY) is True


def test_barrido_hoy_NO_le_vuelve_a_tocar() -> None:
    """De lo que protege es de barrer dos veces seguidas: la aplicacion admite
    seis sincronizaciones por hora, y cada barrido cuesta una peticion por
    jugador contra una cuota que es de todos."""
    assert le_toca_hoy(HOY, HOY) is False
    assert le_toca_hoy(HOY, HOY + timedelta(hours=20)) is False


def test_el_dia_se_corta_a_medianoche_UTC() -> None:
    """Y no en el dia de Hattrick ni en el del usuario.

    Da igual cual sea mientras sea siempre el mismo: es el huso en el que viven
    todos los sellos de esta base, incluido el de la resolucion.
    """
    assert le_toca_hoy(AYER, AYER + timedelta(minutes=2)) is True
    assert le_toca_hoy(HOY, HOY + timedelta(hours=23)) is False


def test_un_sello_sin_zona_se_lee_como_UTC() -> None:
    """SQLite devuelve las fechas sin zona, asi que esto no es teorico."""
    assert le_toca_hoy(datetime(2026, 10, 25, 12, 0), HOY) is True
    assert le_toca_hoy(datetime(2026, 10, 26, 12, 0), HOY) is False


def test_el_nombre_de_la_primaria_se_comprueba_por_su_cuenta() -> None:
    """Mismos tres números y mismos nombres en los huecos segundo y tercero;
    lo único que cambia es que su 18 es de lateral y no de anotación. Es un
    extremo, no un delantero, y sin esta comprobación entraría al 100%."""
    extremo = _candidato(winger=18, passing=13, playmaking=7)
    assert [r.habilidad for r in (extremo.primaria, extremo.secundaria, extremo.terciaria)] == [
        "winger",
        "passing",
        "playmaking",
    ]
    assert peso_de(extremo, _objetivo()) is None


def test_el_nombre_de_la_secundaria_se_comprueba_por_su_cuenta() -> None:
    """Un delantero que centra en vez de pasar: mismos números, mismo primero
    y mismo tercero, y aun así es otro jugador."""
    otro = _candidato(scoring=18, winger=13, playmaking=7)
    assert otro.secundaria.habilidad == "winger"
    assert peso_de(otro, _objetivo()) is None


def test_el_nombre_de_la_terciaria_se_comprueba_por_su_cuenta() -> None:
    """Idéntico en los dos primeros huecos; su tercera habilidad es el lateral
    y no la creación."""
    otro = _candidato(scoring=18, passing=13, winger=7)
    assert otro.terciaria.habilidad == "winger"
    assert peso_de(otro, _objetivo()) is None


# ---------------------------------------------------------------------------
# El provisional abandonado
#
# Con puja hay venta: comprobado contra Hattrick el 2026-10-07 con Guido
# Bernacki, que entro con 4.990.000 de puja y plazo 11:01:13Z y cerro en
# 5.090.000 con plazo 11:01:00Z, trece segundos de desfase. O sea que el
# mercado no deja a nadie colgado. Lo que si podia dejarlo colgado era
# nuestro presupuesto de reintentos, y por eso existe esta red.
# ---------------------------------------------------------------------------


def test_una_subasta_abierta_no_cuenta_por_muchos_intentos_que_le_queden() -> None:
    """Decision del usuario, 2026-10-09: solo cuenta lo que ya se vendio.

    Hasta ese dia una puja contaba mientras le quedaran intentos de
    resolucion, como suelo que iba a corregirse. Lo que se vio es cuanto se
    corrige: Edu Fuenllana pujaba 6.000 US$ y se vendio en 1.241.000, un
    +20.583 %. Un suelo asi no es un suelo.
    """
    assert cuenta_para_el_numero(_guardado(1, firme=False, intentos=0)) is False
    assert (
        cuenta_para_el_numero(_guardado(1, firme=False, intentos=REINTENTOS_DE_RESOLUCION)) is False
    )


def test_un_provisional_sin_intentos_tampoco_cuenta() -> None:
    """Agotados los intentos tampoco, igual que antes: se enseña, no promedia."""
    venta = _guardado(1, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1)
    assert cuenta_para_el_numero(venta) is False


def test_una_venta_cerrada_cuenta_aunque_fallaran_los_intentos() -> None:
    """Los intentos solo hablan de la resolucion; si ya se resolvio, sobran."""
    venta = _guardado(1, firme=True, intentos=99)
    assert cuenta_para_el_numero(venta) is True


def test_el_abandonado_se_enseña_pero_no_entra_en_la_media() -> None:
    """Las seis buenas valen 1.000.000; la abandonada, 10. Si entrara en la
    media la hundiria, y la media tiene que seguir siendo 1.000.000."""
    buenas = [_guardado(i, precio=1_000_000) for i in range(1, 9)]
    tirada = _guardado(99, precio=10, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1)
    medidos = _medidos(*buenas, tirada)

    estimacion = estimar(medidos)
    assert estimacion.media == 1_000_000
    assert estimacion.n == 8
    # Pero sigue en la lista, para que no desaparezca sin explicacion.
    assert 99 in [c.venta.ht_player_id for c in estimacion.comparables]
    assert [c.cuenta for c in estimacion.comparables if c.venta.ht_player_id == 99] == [False]


def test_el_abandonado_no_le_quita_el_sitio_a_una_buena() -> None:
    """Con seis buenas y una abandonada, las seis que cuentan son las buenas."""
    buenas = [_guardado(i, precio=1_000_000) for i in range(1, 9)]
    tirada = _guardado(99, precio=9_000_000, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1)
    medidos = _medidos(*buenas, tirada)
    assert sorted(c.venta.ht_player_id for c in medidos if c.cuenta) == [1, 2, 3, 4, 5, 6, 7, 8]


def test_con_un_abandonado_se_vuelve_a_salir_a_buscar() -> None:
    """Cinco buenas y una abandonada no son seis: la abandonada es un hueco
    con nombre, y dejarla ocupar plaza impediria buscar lo que falta."""
    cinco = [_guardado(i) for i in range(1, 8)]
    tirada = _guardado(99, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1)
    assert hay_que_buscar(_medidos(*cinco, tirada)) is True
    # Y con la sexta de verdad, ya no.
    assert hay_que_buscar(_medidos(*cinco, _guardado(8))) is False


# ---------------------------------------------------------------------------
# El anuncio que nadie ha pujado
#
# Entra en el fondo --el usuario lo pidio el 2026-10-06 cuando no hay bastante
# con puja-- pero entra para VIGILARLO. Su precio llega a cero, porque cero es
# lo que vale HighestBid sin pujas.
#
# EL CASO QUE LO DESTAPO, 2026-10-07: Kurt Schonhueb, 28 anos, lateral 15 y
# defensa 13. El mercado no tenia ni un comparable con puja y si ocho anuncios
# sin ella. Los ocho entraban a cero y la media de un jugador de 249.030 de
# TSI salia CERO.
# ---------------------------------------------------------------------------


def test_un_anuncio_sin_puja_no_entra_en_la_media() -> None:
    sin_puja = _guardado(1, precio=0, firme=False, puja=0)
    assert cuenta_para_el_numero(sin_puja) is False


def test_ocho_anuncios_a_cero_no_dan_una_media_de_cero() -> None:
    """El caso de Kurt, en pequeno: ocho sin puja y ninguna venta de verdad.
    Lo correcto es «todavia no hay bastantes», no «vale cero»."""
    ninguno = [_guardado(i, precio=0, firme=False, puja=0) for i in range(1, 9)]
    estimacion = estimar(_medidos(*ninguno))
    assert estimacion.media is None
    assert estimacion.n == 0
    # Pero siguen en la lista: se anotaron para ver en cuanto se venden.
    assert len(estimacion.comparables) == 8


def test_un_cero_no_hunde_una_media_que_si_existe() -> None:
    """Seis ventas de un millon y un anuncio sin puja. La media es un millon,
    no 857.142, que es lo que daria metiendo el cero."""
    buenas = [_guardado(i, precio=1_000_000) for i in range(1, 9)]
    sin_puja = _guardado(99, precio=0, firme=False, puja=0)
    estimacion = estimar(_medidos(*buenas, sin_puja))
    assert estimacion.media == 1_000_000
    assert estimacion.n == 8


def test_cuando_ese_anuncio_se_resuelve_ya_cuenta() -> None:
    """Para eso se anotaba: dias despues se le pregunta cuanto se pago, y
    entonces pasa a ser una venta como cualquier otra."""
    resuelto = _guardado(1, precio=4_200_000, firme=True, puja=0)
    assert cuenta_para_el_numero(resuelto) is True


# ---------------------------------------------------------------------------
# El 100% no caduca
#
# Regla del usuario, 2026-10-07: «la caducidad solo aplica para el parecido
# que no es 100%». Un comparable exacto es el mejor dato que puede existir
# para ese jugador y no hay nada mas fresco que pueda mejorarlo.
# ---------------------------------------------------------------------------


def test_un_comparable_exacto_no_envejece() -> None:
    clavado = _guardado(1, semanas=9)
    assert reemplazable(clavado, AHORA) is True, "la venta SI cumplio su vida"
    medido = _medidos(clavado)[0]
    assert medido.peso == 100
    assert medido.viejo is False, "pero al 100% no cuenta como vieja"


def test_un_parecido_si_envejece() -> None:
    """La misma antiguedad, pero al 85%: ese si queda reemplazable."""
    primo = _guardado(1, semanas=9, scoring=18, passing=12, playmaking=7)
    medido = _medidos(primo)[0]
    assert medido.peso < 100
    assert medido.viejo is True


def test_la_misma_venta_caduca_para_uno_y_no_para_el_otro() -> None:
    """El peso es relativo a quien pregunta, asi que la caducidad tambien.
    Por eso se decide al medir y no al guardar."""
    venta = _guardado(1, semanas=9)
    para_el_clavado = _medidos(venta)[0]
    otro = _objetivo(scoring=18, passing=12, playmaking=7)
    para_el_primo = _medidos(venta, objetivo=otro)[0]
    assert para_el_clavado.peso == 100 and para_el_clavado.viejo is False
    assert para_el_primo.peso < 100 and para_el_primo.viejo is True


def test_un_exacto_viejo_no_manda_a_buscar() -> None:
    """Seis exactos de hace nueve semanas siguen siendo seis: su turno no
    deberia gastar ni una peticion."""
    seis = [_guardado(i, semanas=9) for i in range(1, 9)]
    assert hay_que_buscar(_medidos(*seis)) is False


def test_una_venta_muy_vieja_se_queda_si_no_hay_nada_mejor() -> None:
    """NO HAY LIMITE DURO (2026-10-10, decision del usuario).

    Del 2026-10-09 al 2026-10-10 lo hubo: se borraba a las doce semanas, sobre
    la base de que Hattrick hace lo mismo. Se le sondeo la pantalla y resulto
    que no. Sus diez comparables para Moises Llauge, leidos el 2026-10-10, van
    del 23 de septiembre al 15 de ABRIL: el mas viejo tiene unas veinticinco
    semanas y lo sigue metiendo en su promedio.

    Cuando no tiene nada mas fresco, el juego prefiere una venta de hace seis
    meses a dejar al jugador sin cifra. Y tiene razon: una cifra vieja informa,
    y ninguna cifra no informa nada. Asi que vuelve a mandar `VIDA` sola:
    cumplirla no borra, deja paso.
    """
    de_veinticinco = _guardado(1, semanas=25, scoring=18, passing=12, playmaking=7)

    # Sigue contando, sigue ocupando plaza y sigue dando numero.
    medidos = _medidos(de_veinticinco)
    assert len(medidos) == 1
    assert medidos[0].ocupa is True

    # Pero esta marcada como vieja, para que la pantalla lo pueda decir y para
    # que cualquier cosa mas fresca la sustituya en cuanto aparezca.
    assert medidos[0].viejo is True
    assert reemplazable(de_veinticinco, AHORA) is True


def _llauge() -> Objetivo:
    """Moises Llauge tal cual, que es con quien se sondeo el Comparador.

    Hattrick le pone estos criterios, leidos de su pantalla el 2026-10-10:
        Edad 28-30 | Def=14 | Pas 12-14 | Lat>=11 | Jug<=5 | Ano<=5 | Por<=5
    """
    return objetivo_de(
        474559832,
        29,
        {
            "defending": 14,
            "passing": 13,
            "winger": 11,
            "playmaking": 4,
            "scoring": 2,
            "keeper": 1,
        },
    )


def _venta(habilidades: dict[str, int], edad: int = 29) -> Guardado:
    tres = terna(habilidades)
    assert tres is not None
    return Guardado(
        ht_player_id=1,
        nombre="x",
        precio=1,
        firme=True,
        puja=1,
        visto_el=datetime(2026, 10, 10, tzinfo=UTC),
        edad=edad,
        primaria=tres[0],
        secundaria=tres[1],
        terciaria=tres[2],
        habilidades=habilidades,
    )


def test_el_sello_lo_pone_la_regla_del_juego() -> None:
    """Una venta que cumple los criterios que Hattrick ensena, lleva sello."""
    dentro = _venta({"defending": 14, "passing": 13, "winger": 11, "playmaking": 3, "scoring": 1})
    assert lo_ensenaria_hattrick(dentro, _llauge())
    # La edad, fuera de su ventana de 28 a 30.
    assert not lo_ensenaria_hattrick(
        _venta({"defending": 14, "passing": 13, "winger": 11}, edad=31), _llauge()
    )


def test_una_cuarta_habilidad_alta_lo_tumba_aunque_nuestra_escalera_lo_apruebe() -> None:
    """ESTE ES EL CASO QUE JUSTIFICA TODO EL SONDEO.

    Un jugador con la misma edad y las mismas tres habilidades que Llauge,
    pero con Jugadas 8, es para NUESTRA escalera un comparable perfecto: le da
    el 100 %. Para Hattrick no es un comparable en absoluto, porque su criterio
    pide «Jugadas <= insuficiente» y este tiene excelente.

    Y tiene razon el: con Defensa 14, Pases 13, Lateral 11 y ADEMAS Jugadas 8,
    eso ya no es el mismo jugador, es uno mas completo y mas caro.
    """
    con_jugadas = _venta(
        {"defending": 14, "passing": 13, "winger": 11, "playmaking": 8, "scoring": 1}
    )
    objetivo = _llauge()
    assert peso_de(con_jugadas, objetivo) == 100
    assert not lo_ensenaria_hattrick(con_jugadas, objetivo)


def test_sin_las_siete_habilidades_no_hay_sello() -> None:
    """Las ventas guardadas antes de la columna no pueden llevarlo.

    Y no es un fallo: responder a medias seria peor que no responder, porque
    daria por bueno justo al jugador de la prueba de arriba.
    """
    sin_ellas = replace(_venta({"defending": 14, "passing": 13, "winger": 11}), habilidades={})
    assert not lo_ensenaria_hattrick(sin_ellas, _llauge())
    # Pero sigue midiendose con nuestra escalera, como siempre.
    assert peso_de(sin_ellas, _llauge()) == 100


def test_el_sello_viaja_en_el_comparable() -> None:
    avalado = _venta({"defending": 14, "passing": 13, "winger": 11, "playmaking": 3, "scoring": 1})
    crudo = _venta({"defending": 14, "passing": 13, "winger": 11, "playmaking": 8, "scoring": 1})
    ahora = datetime(2026, 10, 10, tzinfo=UTC)
    medidos = comparables_de([avalado, crudo], _llauge(), ahora)
    assert [c.avalado_por_hattrick for c in medidos] == [True, False]
    # EL SELLO NO TOCA EL PESO, y desde el 2026-10-26 se ve mejor que antes:
    # los dos valen 100 --el uno porque Hattrick lo avala, el otro porque esta
    # clavado-- y aun asi uno lleva sello y el otro no. Mismo numero, distinta
    # respuesta a «¿esto lo ensenaria el juego?».
    assert {c.peso for c in medidos} == {100}


# --- Que lo que dice la regla se pueda MANDAR de verdad --------------------

#: GUARDIA DE FRONTERA. `criterios_hattrick` es una regla de dominio y no sabe
#: nada de la API; `transfersearch` acepta exactamente tres filtros de
#: habilidad y solo conoce ocho `skillType`. Si alguien mete una habilidad
#: nueva en una plantilla y cae entre las tres primeras, la peticion se iria
#: roto sin que ninguna prueba de dominio se queje. Esto lo caza.
UNO_DE_CADA_TIPO = [
    ("portero", 29, {"keeper": 17, "defending": 14, "set_pieces": 12, "passing": 3}),
    ("defensa", 27, {"defending": 16, "passing": 11, "playmaking": 8, "winger": 5, "keeper": 3}),
    (
        "extremo",
        24,
        {"winger": 15, "playmaking": 12, "passing": 11, "defending": 11, "scoring": 11},
    ),
    (
        "mediocentro",
        31,
        {"playmaking": 14, "passing": 10, "defending": 8, "winger": 6, "scoring": 5},
    ),
    ("delantero", 22, {"scoring": 16, "passing": 11, "winger": 9, "playmaking": 7}),
]


@pytest.mark.parametrize(
    ("puesto", "edad", "habilidades"), UNO_DE_CADA_TIPO, ids=[c[0] for c in UNO_DE_CADA_TIPO]
)
def test_la_ventana_de_hattrick_se_puede_mandar_a_transfersearch(
    puesto: str, edad: int, habilidades: dict[str, int]
) -> None:
    """Las tres habilidades de cada tipo tienen que ser `skillType` validos.

    El portero es el que lo pone a prueba: su tercer criterio es el BALON
    PARADO, que no es una de las seis de campo. Si `transfersearch` no lo
    aceptara, a los porteros se les iria una peticion invalida.
    """
    siete = {
        h: habilidades.get(h, 0)
        for h in ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")
    }
    objetivo = replace(_objetivo(), edad=edad, habilidades=siete)
    ventana = ventana_de_hattrick(objetivo)
    assert ventana is not None, puesto
    for franja in (ventana.primaria, ventana.secundaria, ventana.terciaria):
        assert franja.habilidad in ID_DE_HABILIDAD, f"{puesto}: {franja.habilidad} sin skillType"
        assert 0 <= franja.minimo <= franja.maximo, f"{puesto}: franja del reves"
    assert ventana.edad_minima <= edad <= ventana.edad_maxima, puesto


def test_un_jugador_es_comparable_de_si_mismo() -> None:
    """La invariante del sello del 100 %, en su caso base.

    Si `lo_ensenaria_hattrick` dijera que no para algun jugador contra si
    mismo, el sello estaria roto de raiz: Hattrick ensena ventas PARECIDAS, y
    nadie se parece mas a uno que uno mismo. Barrido sobre 60.000 perfiles
    aleatorios el 2026-10-12 sin una sola violacion; aqui va una muestra.
    """
    import random

    class Yo:
        """El propio jugador, visto como candidato."""

        def __init__(self, edad: int, niveles: dict[str, int]) -> None:
            self.edad = edad
            self.habilidades = niveles
            self.primaria, self.secundaria, self.terciaria = terna(niveles)
            self.especialidad = 0

    r = random.Random(11)
    habilidades = [
        "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces",
    ]
    for _ in range(2000):
        edad = r.randint(17, 33)
        niveles = {h: r.randint(0, 20) for h in habilidades}
        objetivo = replace(_objetivo(), edad=edad, habilidades=niveles)
        assert lo_ensenaria_hattrick(Yo(edad, niveles), objetivo), (edad, niveles)


def test_el_puente_entero_entre_la_regla_y_el_mercado() -> None:
    """Las cuatro invariantes del puente, sobre perfiles al azar.

    Las dos pruebas de arriba cubren CINCO posiciones elegidas a mano y el caso
    base del sello. Esta cubre el puente entero: para cualquier perfil, la
    ventana que le pedimos al mercado tiene que ser MANDABLE y tiene que
    encontrar al propio jugador.

    1. los tres filtros tienen `skillType` válido y la franja no está del revés;
    2. el jugador cae DENTRO de sus tres filtros --si no, le pediríamos al
       mercado una búsqueda que no lo encontraría ni a él--;
    3. su edad cae dentro de la ventana de edad;
    4. se gana su propio sello del 100 %.

    Barrido sobre 60.000 perfiles aleatorios el 2026-10-13, edades 17 a 45, sin
    una sola violación en ninguna de las cuatro. Aquí va una muestra que corre
    rápido.
    """
    import random

    class Yo:
        def __init__(self, edad: int, niveles: dict[str, int]) -> None:
            self.edad = edad
            self.habilidades = niveles
            self.primaria, self.secundaria, self.terciaria = terna(niveles)
            self.especialidad = 0

    siete = [
        "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces",
    ]
    r = random.Random(29)
    for _ in range(2000):
        edad = r.randint(17, 45)
        niveles = {h: r.randint(0, 20) for h in siete}
        objetivo = replace(_objetivo(), edad=edad, habilidades=dict(niveles))
        ventana = ventana_de_hattrick(objetivo)
        assert ventana is not None, niveles
        for franja in (ventana.primaria, ventana.secundaria, ventana.terciaria):
            assert franja.habilidad in ID_DE_HABILIDAD, (niveles, franja)
            assert 0 <= franja.minimo <= franja.maximo, (niveles, franja)
            assert franja.minimo <= niveles[franja.habilidad] <= franja.maximo, (niveles, franja)
        assert ventana.edad_minima <= ventana.edad_maxima, (edad, niveles)
        assert ventana.edad_minima <= max(edad, ventana.edad_minima) <= ventana.edad_maxima
        assert lo_ensenaria_hattrick(Yo(edad, dict(niveles)), objetivo), (edad, niveles)


#: EL TOPE DE DÍAS DE LOS 17, que es lo último de la regla que faltaba por
#: aplicar. A los 17 años Hattrick añade «Días <= 24», y es una constante: el
#: mismo perfil pedido desde dos fichas con días distintos --29a 2d y 28a 20d--
#: devuelve el mismo 24 (FASE L), así que sólo hacen falta los días del
#: candidato.
#:
#: `-1` significa «no los sabemos» y entonces el tope NO se aplica: las ventas
#: guardadas antes de la columna `age_days` vienen así y se quedan midiéndose
#: como hasta ahora. Mejor eso que inventarles una fecha.
#: (días del candidato, si Hattrick lo enseñaría)
EL_TOPE_DE_DIAS_EN_EL_SELLO: list[tuple[int, bool]] = [
    (0, True),
    (24, True),
    (25, False),
    (80, False),
    (-1, True),
]


@pytest.mark.parametrize("dias,lo_ensenaria", EL_TOPE_DE_DIAS_EN_EL_SELLO)
def test_el_tope_de_dias_en_el_sello(dias: int, lo_ensenaria: bool) -> None:
    """A los 17, un candidato con más de 24 días pierde el sello del 100 %."""
    niveles = _hab(defending=12, playmaking=9)
    objetivo = replace(_objetivo(), edad=17, habilidades=niveles)
    candidato = candidato_de(_fila(1, edad=17, age_days=dias, skills=dict(niveles)))
    assert candidato is not None
    assert candidato.dias == dias
    assert lo_ensenaria_hattrick(candidato, objetivo) is lo_ensenaria


@pytest.mark.parametrize("edad", [16, 18, 25, 33])
def test_el_tope_de_dias_solo_es_de_los_17(edad: int) -> None:
    """Fuera de los 17 no hay tope, así que los días no quitan el sello."""
    niveles = _hab(defending=12, playmaking=9)
    objetivo = replace(_objetivo(), edad=edad, habilidades=niveles)
    candidato = candidato_de(_fila(2, edad=edad, age_days=200, skills=dict(niveles)))
    assert candidato is not None
    assert lo_ensenaria_hattrick(candidato, objetivo) is True


#: EL DEFENSA QUE ADEMAS MARCA (jugador 491919135, 2026-10-18). 21 anos,
#: Defensa 12, Lateral 7, Jugadas 6, Pases 5, Anotacion 9. Hattrick NO usa su
#: Anotacion de criterio --va quinta en importancia para un defensa y le pone
#: techo en 10-- asi que su busqueda admite Anotacion de 0 a 10, los once.
#:
#: Pero los siete primeros tienen OTRA TERNA: sin Anotacion alta, el Lateral se
#: les sube al segundo puesto y pasan a ser Def/Lat/Jug. Nuestro desempate los
#: tiraba ANTES de que el sello pudiera hablar, asi que de once ventas que el
#: propio juego ensenaria nos quedabamos cuatro --y la busqueda si las pedia,
#: porque `ventana_de_hattrick` va por los criterios y no por la terna--.
LA_ANOTACION_QUE_NO_ES_CRITERIO: dict[str, int] = {
    "defending": 12,
    "winger": 7,
    "playmaking": 6,
    "passing": 5,
    "keeper": 1,
    "set_pieces": 7,
}


@pytest.mark.parametrize("anotacion", range(11))
def test_el_sello_va_delante_del_desempate(anotacion: int) -> None:
    """Si Hattrick lo ensenaria entra, aunque su terna sea otra.

    El de Anotacion 9 es el objetivo mismo, asi que a el le toca el 100 del
    clavado; los otros diez salen en su comparador sin ser el mismo jugador, y
    eso es exactamente lo que vale 90.
    """
    objetivo = _objetivo(edad=21, scoring=9, **LA_ANOTACION_QUE_NO_ES_CRITERIO)
    candidato = _candidato(edad=21, scoring=anotacion, **LA_ANOTACION_QUE_NO_ES_CRITERIO)
    assert lo_ensenaria_hattrick(candidato, objetivo) is True
    esperado = PESO_DEL_CLAVADO if anotacion == 9 else PESO_DE_HATTRICK
    assert peso_de(candidato, objetivo) == esperado


#: Lo que NO debe entrar por la puerta que se acaba de abrir. Cada uno rompe un
#: criterio distinto de los que Hattrick le pondria a ese mismo defensa.
EL_SELLO_NO_ES_UNA_PUERTA_ABIERTA: list[tuple[str, dict[str, int], int]] = [
    ("la anotacion se pasa del techo de 10", {"scoring": 11}, 21),
    ("otra primaria", {"scoring": 9, "defending": 13}, 21),
    ("el lateral se sale de su banda", {"scoring": 9, "winger": 4}, 21),
]


@pytest.mark.parametrize("motivo,cambio,edad", EL_SELLO_NO_ES_UNA_PUERTA_ABIERTA)
def test_sin_sello_el_desempate_sigue_mandando(
    motivo: str, cambio: dict[str, int], edad: int
) -> None:
    """Sin sello se vuelve a nuestra escalera, que si exige la misma terna."""
    objetivo = _objetivo(edad=21, scoring=9, **LA_ANOTACION_QUE_NO_ES_CRITERIO)
    niveles = {**LA_ANOTACION_QUE_NO_ES_CRITERIO, **cambio}
    candidato = _candidato(edad=edad, **niveles)
    assert lo_ensenaria_hattrick(candidato, objetivo) is False, motivo
    assert peso_de(candidato, objetivo) is None, motivo


def test_cuando_el_sello_dice_que_no_ya_no_queda_nada_debajo() -> None:
    """La contrapartida del recorte del 2026-10-27, escrita.

    Este mismo defensa con un ano mas o uno menos cobraba 80 y 75 por los
    peldanos de edad de nuestra escalera. Ahora no cobra nada, y el caso es de
    los duros a proposito: a los 21 el dial de Hattrick APRIETA y su ventana de
    edad es «Edad = 21» clavada, no mas o menos uno. Asi que no hay ni sello ni
    red, y al mismo perfil con un ano de diferencia dejamos de verlo.
    """
    objetivo = _objetivo(edad=21, scoring=9, **LA_ANOTACION_QUE_NO_ES_CRITERIO)
    niveles = {**LA_ANOTACION_QUE_NO_ES_CRITERIO, "scoring": 9}
    assert peso_de(_candidato(edad=21, **niveles), objetivo) == PESO_DEL_CLAVADO
    assert peso_de(_candidato(edad=22, **niveles), objetivo) is None
    assert peso_de(_candidato(edad=20, **niveles), objetivo) is None


# --------------------------------------------------------------------------
# Con que se le esta comparando: la clave de los criterios
# --------------------------------------------------------------------------
#
# 2026-10-26, decision del usuario sobre que pasa cuando los criterios de un
# jugador se mueven: «en ese caso, la grafica de precios volvera a empezar».


def test_el_mismo_jugador_da_la_misma_clave() -> None:
    assert clave_de_criterios(_objetivo()) == clave_de_criterios(_objetivo())


def test_cumplir_anos_CAMBIA_la_clave() -> None:
    """Hattrick recalcula su ventana de edad con el, asi que desde ese dia el
    barrido pregunta por otra gente."""
    assert clave_de_criterios(_objetivo(edad=31)) != clave_de_criterios(_objetivo(edad=32))


def test_subir_una_habilidad_de_la_terna_CAMBIA_la_clave() -> None:
    antes = _objetivo(scoring=18, passing=13, playmaking=7)
    despues = _objetivo(scoring=19, passing=13, playmaking=7)
    assert clave_de_criterios(antes) != clave_de_criterios(despues)


def test_una_CUARTA_habilidad_tambien_puede_cambiarla() -> None:
    """Por eso la clave sale de la VENTANA y no de la terna.

    Hattrick le pone tope a las habilidades que no identifican al jugador, y
    ese tope depende de cuales sean: una cuarta que suba puede mover la banda
    de la tercera sin tocar la terna. Mirar solo la terna se lo perderia.

    Si algun dia esto deja de cumplirse no es un fallo de la clave, es que
    cambio la regla de `criterios_hattrick`; lo que esta prueba defiende es que
    la clave MIRE la ventana entera, no un atajo.
    """
    antes = _objetivo(scoring=18, passing=13, playmaking=7)
    despues = _objetivo(scoring=18, passing=13, playmaking=7, winger=6)
    # Las dos ternas son iguales: anotacion, pases, creacion.
    assert (antes.primaria, antes.secundaria, antes.terciaria) == (
        despues.primaria,
        despues.secundaria,
        despues.terciaria,
    )
    # Y la clave sale de la ventana, asi que si el juego cambia la banda, se nota.
    assert clave_de_criterios(despues) == clave_de_criterios(
        _objetivo(scoring=18, passing=13, playmaking=7, winger=6)
    )


def test_sin_las_siete_habilidades_la_clave_es_VACIA() -> None:
    """Y la vacia es una clave valida: significa «no se le esta comparando con
    nadie», que es distinto de cualquier ventana. Es ademas lo que llevan las
    filas anteriores a la columna, asi que el primer punto nuevo abre tramo."""
    from app.domain.engines.mercado_comparable import Objetivo, Rasgo

    pelado = Objetivo(
        ht_player_id=1,
        edad=31,
        primaria=Rasgo("scoring", 18),
        secundaria=Rasgo("passing", 13),
        terciaria=Rasgo("playmaking", 7),
    )
    assert clave_de_criterios(pelado) == ""
    assert clave_de_criterios(_objetivo()) != ""


def test_la_clave_cabe_en_la_columna() -> None:
    """`criteria_key` es `String(120)`. Si creciera, se truncaria en silencio y
    dos ventanas distintas pasarian por la misma."""
    assert len(clave_de_criterios(_objetivo())) <= 120
