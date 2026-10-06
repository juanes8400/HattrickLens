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

Y la escalera, que se comprueba escalón por escalón contra lo que dictó el
usuario el 2026-10-06, porque si alguien la "mejora" el motor sigue devolviendo
un número y el número es otro.
"""

from datetime import UTC, datetime, timedelta

from app.domain.engines.mercado_comparable import (
    ESCALERA,
    GRUPOS,
    OBJETIVO,
    ORDEN_DE_DESEMPATE,
    TERCIARIA_ABAJO,
    TERCIARIA_ARRIBA,
    VIDA,
    Guardado,
    Objetivo,
    admitir,
    candidato_de,
    cosecha,
    estimar,
    frontera_semanal,
    hay_que_buscar,
    le_toca,
    objetivo_de,
    perfil_de,
    peso_de,
    plan_de_busqueda,
    quien_sale,
    reemplazable,
    terna,
)

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
    peso: int = 100,
    semanas: float = 0,
    firme: bool = True,
    especialidad: int = 0,
) -> Guardado:
    return Guardado(
        ht_player_id=ident,
        nombre=f"Comparable {ident}",
        precio=precio,
        peso=peso,
        firme=firme,
        visto_el=AHORA - timedelta(weeks=semanas),
        especialidad=especialidad,
    )


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


def test_el_perfil_cambia_con_la_edad_y_con_las_tres_habilidades() -> None:
    """Es lo que decide cuándo hay que tirar lo acumulado."""
    base = perfil_de(_objetivo())
    assert perfil_de(_objetivo(edad=32)) != base
    assert perfil_de(_objetivo(scoring=19, passing=13, playmaking=7)) != base
    assert perfil_de(_objetivo(scoring=18, passing=14, playmaking=7)) != base
    assert perfil_de(_objetivo(scoring=18, passing=13, playmaking=8)) != base
    # La cuarta habilidad no entra en el perfil: no cambia a quién se parece.
    assert perfil_de(_objetivo(scoring=18, passing=13, playmaking=7, winger=5)) == base


# --------------------------------------------------------------------------
# La escalera
# --------------------------------------------------------------------------


def test_la_escalera_es_exactamente_la_que_dicto_el_usuario() -> None:
    """Los cinco escalones, uno a uno, para que nadie los "mejore" sin hablar
    con él. La terciaria no está aquí porque va igual en todos."""
    leida = [(e.edad_desde, e.edad_hasta, e.primaria, e.secundaria, e.peso) for e in ESCALERA]
    assert leida == [
        (0, 0, 0, 0, 100),
        (0, 0, 0, 1, 90),
        (0, 0, 1, 1, 85),
        (1, 1, 1, 1, 80),
        (-1, -1, 1, 1, 75),
    ]


def test_la_terciaria_lleva_la_misma_ventana_en_todos_los_escalones() -> None:
    """Un nivel por encima y dos por debajo, siempre."""
    assert (TERCIARIA_ARRIBA, TERCIARIA_ABAJO) == (1, 2)
    for ventana in plan_de_busqueda(_objetivo()):
        assert ventana.terciaria.minimo == 7 - TERCIARIA_ABAJO
        assert ventana.terciaria.maximo == 7 + TERCIARIA_ARRIBA


def test_las_ventanas_son_las_que_se_le_piden_al_mercado() -> None:
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
    assert leidas == [
        (100, 31, 31, 18, 18, 13, 13),
        (90, 31, 31, 18, 18, 12, 14),
        (85, 31, 31, 17, 19, 12, 14),
        (80, 32, 32, 17, 19, 12, 14),
        (75, 30, 30, 17, 19, 12, 14),
    ]


def test_un_escalon_que_pedira_menos_de_diecisiete_anos_no_se_pide() -> None:
    """Gastar una llamada en un tramo donde no hay nadie es tirar cuota."""
    plan = plan_de_busqueda(_objetivo(edad=17))
    assert all(v.edad_minima >= 17 for v in plan)
    assert len(plan) == len(ESCALERA) - 1
    # Y los que quedan conservan su peso: no se renumeran.
    assert [v.peso for v in plan] == [100, 90, 85, 80]


# --------------------------------------------------------------------------
# El peso de un candidato
# --------------------------------------------------------------------------


def test_cada_escalon_cobra_lo_que_le_toca() -> None:
    objetivo = _objetivo()
    assert peso_de(_candidato(), objetivo) == 100
    assert peso_de(_candidato(scoring=18, passing=14, playmaking=7), objetivo) == 90
    assert peso_de(_candidato(scoring=18, passing=12, playmaking=7), objetivo) == 90
    assert peso_de(_candidato(scoring=17, passing=13, playmaking=7), objetivo) == 85
    assert peso_de(_candidato(scoring=19, passing=13, playmaking=7), objetivo) == 85
    assert peso_de(_candidato(edad=32), objetivo) == 80
    assert peso_de(_candidato(edad=30), objetivo) == 75


def test_fuera_de_la_escalera_no_hay_peso() -> None:
    objetivo = _objetivo()
    assert peso_de(_candidato(scoring=18, passing=15, playmaking=7), objetivo) is None
    assert peso_de(_candidato(scoring=16, passing=13, playmaking=7), objetivo) is None
    assert peso_de(_candidato(edad=33), objetivo) is None
    assert peso_de(_candidato(edad=29), objetivo) is None


def test_la_terciaria_admite_uno_arriba_y_dos_abajo_y_ni_uno_mas() -> None:
    """Y lo hace ya en el escalón del 100%: la ventana de la terciaria es
    parte de "exactamente el mismo tipo de jugador"."""
    objetivo = _objetivo()
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=8), objetivo) == 100
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=5), objetivo) == 100
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=9), objetivo) is None
    assert peso_de(_candidato(scoring=18, passing=13, playmaking=4), objetivo) is None


def test_dos_cosas_abiertas_a_la_vez_pagan_el_escalon_donde_las_dos_caben() -> None:
    objetivo = _objetivo()
    assert peso_de(_candidato(edad=32, scoring=17, passing=12, playmaking=7), objetivo) == 80
    assert peso_de(_candidato(edad=30, scoring=19, passing=14, playmaking=7), objetivo) == 75


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


def test_cada_uno_viaja_con_el_peso_del_escalon_que_lo_admite() -> None:
    con, _ = cosecha(
        _objetivo(),
        [_fila(1), _fila(2, skills=_hab(scoring=17, passing=13, playmaking=7))],
        mi_equipo=MI_EQUIPO,
    )
    assert dict((c.ht_player_id, p) for c, p in con) == {1: 100, 2: 85}


# --------------------------------------------------------------------------
# Caducidad y reemplazo
# --------------------------------------------------------------------------


def test_un_dato_vive_siete_semanas_y_luego_queda_reemplazable() -> None:
    """Cumplir la vida no lo borra: un dato viejo informa más que ninguno, así
    que espera a que algo mejor ocupe su sitio."""
    assert timedelta(weeks=7) == VIDA
    assert reemplazable(_guardado(1, semanas=6), AHORA) is False
    assert reemplazable(_guardado(1, semanas=7), AHORA) is True
    assert reemplazable(_guardado(1, semanas=30), AHORA) is True


def test_sale_el_mas_viejo() -> None:
    sale = quien_sale(
        [_guardado(1, semanas=8), _guardado(2, semanas=20), _guardado(3, semanas=9)],
        _objetivo(),
        AHORA,
    )
    assert sale is not None and sale.ht_player_id == 2


def test_a_igual_edad_sale_el_de_menos_peso() -> None:
    sale = quien_sale(
        [_guardado(1, semanas=8, peso=100), _guardado(2, semanas=8, peso=75)],
        _objetivo(),
        AHORA,
    )
    assert sale is not None and sale.ht_player_id == 2


def test_a_igual_edad_y_peso_sale_el_mas_barato() -> None:
    sale = quien_sale(
        [
            _guardado(1, semanas=8, peso=90, precio=9_000_000),
            _guardado(2, semanas=8, peso=90, precio=2_000_000),
        ],
        _objetivo(),
        AHORA,
    )
    assert sale is not None and sale.ht_player_id == 2


def test_en_el_ultimo_empate_se_queda_el_de_la_misma_especialidad() -> None:
    """Compartir especialidad con tu jugador hace al comparable más parecido,
    así que es el último que se echa."""
    objetivo = Objetivo(
        ht_player_id=777,
        edad=EDAD,
        primaria=_objetivo().primaria,
        secundaria=_objetivo().secundaria,
        terciaria=_objetivo().terciaria,
        especialidad=2,
    )
    sale = quien_sale(
        [
            _guardado(1, semanas=8, especialidad=2),
            _guardado(2, semanas=8, especialidad=0),
        ],
        objetivo,
        AHORA,
    )
    assert sale is not None and sale.ht_player_id == 2


def test_a_un_dato_vivo_no_se_le_echa() -> None:
    assert (
        quien_sale([_guardado(1, semanas=1), _guardado(2, semanas=3)], _objetivo(), AHORA) is None
    )


def test_mientras_no_haya_seis_entran_todos() -> None:
    fondo: tuple[Guardado, ...] = ()
    for ident in range(1, OBJETIVO + 1):
        fondo = admitir(fondo, _guardado(ident), _objetivo(), AHORA)
    assert len(fondo) == OBJETIVO


def test_el_fondo_no_tiene_tope_y_los_vivos_no_se_tocan() -> None:
    """Si un escalón trae diez comparables se guardan los diez: cuantos más
    datos, mejor describen el mercado. Y como ninguno caducó, el que entra no
    echa a nadie."""
    fondo = tuple(_guardado(i, semanas=1) for i in range(1, OBJETIVO + 1))
    despues = admitir(fondo, _guardado(99, peso=100), _objetivo(), AHORA)
    assert len(despues) == OBJETIVO + 1
    assert set(g.ht_player_id for g in fondo) <= {g.ht_player_id for g in despues}


def test_uno_peor_nunca_desplaza_a_uno_mejor() -> None:
    """Aunque el viejo esté caducado: el objetivo es llegar a seis al 100%, y
    retroceder en peso va justo en contra. El que llega se queda como dato de
    más, pero sin echar a nadie."""
    fondo = tuple(_guardado(i, semanas=10, peso=100) for i in range(1, OBJETIVO + 1))
    despues = admitir(fondo, _guardado(99, peso=75), _objetivo(), AHORA)
    assert {g.ht_player_id for g in fondo} <= {g.ht_player_id for g in despues}
    assert len(despues) == OBJETIVO + 1


def test_uno_igual_o_mejor_si_reemplaza_al_caducado() -> None:
    fondo = (
        _guardado(1, semanas=10, peso=75),
        *(_guardado(i, semanas=1) for i in range(2, OBJETIVO + 1)),
    )
    despues = admitir(fondo, _guardado(99, peso=100), _objetivo(), AHORA)
    assert 1 not in [g.ht_player_id for g in despues]
    assert 99 in [g.ht_player_id for g in despues]
    assert len(despues) == OBJETIVO


def test_echar_a_un_caducado_nunca_deja_el_fondo_por_debajo_de_seis() -> None:
    """Un dato viejo informa más que ninguno, así que no se le echa si al
    hacerlo el jugador se quedaría sin número."""
    fondo = tuple(_guardado(i, semanas=10) for i in range(1, OBJETIVO))
    despues = admitir(fondo, _guardado(99), _objetivo(), AHORA)
    assert len(despues) == OBJETIVO


def test_el_mismo_jugador_no_entra_dos_veces() -> None:
    fondo = (_guardado(1),)
    assert admitir(fondo, _guardado(1, precio=9), _objetivo(), AHORA) == fondo


# --------------------------------------------------------------------------
# El número
# --------------------------------------------------------------------------


def test_con_menos_de_seis_no_hay_numero_pero_si_lista() -> None:
    e = estimar([_guardado(i) for i in range(1, OBJETIVO)])
    assert e.media is None and e.mediana is None
    assert e.suficiente is False
    assert e.n == OBJETIVO - 1
    assert len(e.comparables) == OBJETIVO - 1


def test_con_seis_al_mismo_peso_la_media_es_la_de_siempre() -> None:
    precios = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000]
    e = estimar([_guardado(i, precio=p) for i, p in enumerate(precios, start=1)])
    assert e.suficiente is True
    assert e.media == 3_500_000
    assert e.mediana == 3_500_000


def test_los_pesos_mueven_la_media_y_se_comprueba_a_mano() -> None:
    e = estimar(
        [
            _guardado(1, precio=10_000_000, peso=100),
            _guardado(2, precio=10_000_000, peso=100),
            _guardado(3, precio=20_000_000, peso=75),
            _guardado(4, precio=20_000_000, peso=75),
            _guardado(5, precio=20_000_000, peso=75),
            _guardado(6, precio=20_000_000, peso=75),
        ]
    )
    # (2·100·10M + 4·75·20M) / (2·100 + 4·75) = 8.000M / 500 = 16M
    assert e.media == 16_000_000
    assert e.peso_minimo == 75


def test_la_mediana_tambien_va_ponderada() -> None:
    """Con pesos iguales coincide con la de toda la vida; en cuanto difieren,
    el punto que parte la muestra por la mitad se mueve."""
    pesados = [
        _guardado(1, precio=10, peso=100),
        _guardado(2, precio=20, peso=100),
        _guardado(3, precio=30, peso=100),
        _guardado(4, precio=40, peso=100),
        _guardado(5, precio=50, peso=100),
        _guardado(6, precio=60, peso=75),
    ]
    # Peso total 575, mitad 287,5. Acumulando por precio: 100, 200, 300 pasa
    # de la mitad en el tercero, así que la mediana es 30 y no 35.
    assert estimar(pesados).mediana == 30
    assert estimar(pesados).media != 30


def test_se_dice_cuantos_son_todavia_provisionales() -> None:
    """Una puja se queda corta: Valerio tenía 65 millones y cerró en 77,7, un
    16% más. La pantalla tiene que poder avisar."""
    e = estimar(
        [
            *(_guardado(i) for i in range(1, 5)),
            _guardado(5, firme=False),
            _guardado(6, firme=False),
        ]
    )
    assert e.provisionales == 2
    assert e.suficiente is True


def test_se_puede_guardar_mas_de_seis_y_todos_cuentan() -> None:
    """El usuario lo pidió así: cuantos más datos, mejor."""
    e = estimar([_guardado(i, precio=1_000_000 * i) for i in range(1, 11)])
    assert e.n == 10
    assert e.media == 5_500_000


# --------------------------------------------------------------------------
# Cuándo le toca a quién
# --------------------------------------------------------------------------

ECONOMICA = datetime(2026, 10, 9, 21, 25, tzinfo=UTC)
ANCLA = datetime(2026, 1, 1, tzinfo=UTC)


def test_el_disparador_es_la_economica_menos_veinticuatro_horas() -> None:
    """La fecha la publica Hattrick por país, así que no hay que inventar
    zonas horarias ni mantener una tabla a mano."""
    frontera = frontera_semanal(ECONOMICA, datetime(2026, 10, 9, 12, 0, tzinfo=UTC))
    assert frontera == datetime(2026, 10, 8, 21, 25, tzinfo=UTC)


def test_antes_del_disparador_la_frontera_es_la_de_la_semana_pasada() -> None:
    frontera = frontera_semanal(ECONOMICA, datetime(2026, 10, 8, 21, 24, tzinfo=UTC))
    assert frontera == datetime(2026, 10, 1, 21, 25, tzinfo=UTC)


def test_justo_en_el_disparador_ya_cuenta() -> None:
    frontera = frontera_semanal(ECONOMICA, datetime(2026, 10, 8, 21, 25, tzinfo=UTC))
    assert frontera == datetime(2026, 10, 8, 21, 25, tzinfo=UTC)


def test_una_fecha_economica_vieja_se_adelanta_sola() -> None:
    """Si el dato guardado se quedó atrás, la frontera sigue siendo la última
    que pasó de verdad."""
    vieja = datetime(2026, 8, 7, 21, 25, tzinfo=UTC)
    frontera = frontera_semanal(vieja, datetime(2026, 10, 9, 12, 0, tzinfo=UTC))
    assert frontera is not None
    assert frontera == datetime(2026, 10, 8, 21, 25, tzinfo=UTC)


def test_sin_fecha_economica_no_hay_frontera() -> None:
    assert frontera_semanal(None, AHORA) is None


def test_los_turnos_rotan_de_cero_a_cuatro() -> None:
    """El grupo sale del identificador, así que no hay nada que guardar ni que
    recolocar al fichar o vender."""
    vistos = []
    for semanas in range(GRUPOS):
        frontera = ANCLA + timedelta(weeks=semanas)
        grupo = next(i for i in range(GRUPOS) if le_toca(i, frontera, ANCLA))
        vistos.append(grupo)
    assert sorted(vistos) == list(range(GRUPOS))


def test_cada_semana_le_toca_a_un_solo_grupo() -> None:
    frontera = ANCLA + timedelta(weeks=3)
    tocan = [i for i in range(20) if le_toca(i, frontera, ANCLA)]
    assert all(i % GRUPOS == tocan[0] % GRUPOS for i in tocan)
    assert len(tocan) == 4


def test_con_seis_vivos_su_turno_no_gasta_ni_una_llamada() -> None:
    fondo = [_guardado(i, semanas=1) for i in range(1, OBJETIVO + 1)]
    assert hay_que_buscar(fondo, AHORA) is False


def test_si_falta_alguno_o_hay_caducados_si_se_busca() -> None:
    assert hay_que_buscar([_guardado(i) for i in range(1, OBJETIVO)], AHORA) is True
    con_uno_viejo = [
        _guardado(1, semanas=9),
        *(_guardado(i, semanas=1) for i in range(2, OBJETIVO + 1)),
    ]
    assert hay_que_buscar(con_uno_viejo, AHORA) is True


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
