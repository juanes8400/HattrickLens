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
    REINTENTOS_DE_RESOLUCION,
    TERCIARIA_ABAJO,
    TERCIARIA_ARRIBA,
    VIDA,
    Guardado,
    Objetivo,
    candidato_de,
    comparables_de,
    cosecha,
    cuenta_para_el_numero,
    estimar,
    frontera_semanal,
    hay_que_buscar,
    le_toca,
    objetivo_de,
    peso_de,
    plan_de_busqueda,
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
    semanas: float = 0,
    firme: bool = True,
    puja: int | None = None,
    intentos: int = 0,
    especialidad: int = 0,
    edad: int = EDAD,
    **niveles: int,
) -> Guardado:
    """Una venta del fondo. Por defecto es clavada al objetivo, o sea 100%."""
    tres = terna(_hab(**niveles) if niveles else SKILLS)
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
    al que se parece y 85% para otro con un nivel menos de anotacion, sin
    gastar una sola llamada."""
    venta = _guardado(1)
    assert _medidos(venta)[0].peso == 100
    otro = _objetivo(scoring=17, passing=13, playmaking=7)
    assert _medidos(venta, objetivo=otro)[0].peso == 85


def test_una_venta_que_no_se_parece_a_quien_pregunta_no_entra() -> None:
    portero = _guardado(1, keeper=18, defending=13, scoring=7)
    assert _medidos(portero) == ()


def test_el_peso_manda_por_encima_de_la_frescura() -> None:
    """El usuario dijo que un comparable nunca se reemplaza por algo de menor
    peso, asi que una venta caducada al 100% va por delante de una recien
    encontrada al 85%."""
    vieja = _guardado(1, semanas=20)
    reciente = _guardado(2, semanas=0, scoring=17, passing=13, playmaking=7)
    elegidos = _medidos(reciente, vieja)
    assert [c.venta.ht_player_id for c in elegidos] == [1, 2]
    assert [c.peso for c in elegidos] == [100, 85]
    assert elegidos[0].viejo is True


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
    buenos = [_guardado(i) for i in range(1, 7)]
    flojo = _guardado(99, scoring=17, passing=13, playmaking=7)
    elegidos = _medidos(*buenos, flojo)
    assert 99 not in [c.venta.ht_player_id for c in elegidos]
    assert len(elegidos) == OBJETIVO


def test_con_seis_vivos_su_turno_no_gasta_ni_una_llamada() -> None:
    assert hay_que_buscar(_medidos(*(_guardado(i, semanas=1) for i in range(1, 7)))) is False


def test_si_falta_alguno_o_hay_caducados_si_se_busca() -> None:
    assert hay_que_buscar(_medidos(*(_guardado(i) for i in range(1, 6)))) is True
    con_uno_viejo = [_guardado(1, semanas=9), *(_guardado(i, semanas=1) for i in range(2, 7))]
    assert hay_que_buscar(_medidos(*con_uno_viejo)) is True


# --------------------------------------------------------------------------
# El numero
# --------------------------------------------------------------------------


def test_con_menos_de_seis_no_hay_numero_pero_si_lista() -> None:
    e = estimar(_medidos(*(_guardado(i) for i in range(1, OBJETIVO))))
    assert e.media is None and e.mediana is None
    assert e.suficiente is False
    assert e.n == OBJETIVO - 1


def test_con_seis_al_mismo_peso_la_media_es_la_de_siempre() -> None:
    precios = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000]
    e = estimar(_medidos(*(_guardado(i, precio=p) for i, p in enumerate(precios, start=1))))
    assert e.suficiente is True
    assert e.media == 3_500_000
    assert e.mediana == 3_500_000


def test_los_pesos_mueven_la_media_y_se_comprueba_a_mano() -> None:
    flojo = {"scoring": 17, "passing": 13, "playmaking": 7}
    e = estimar(
        _medidos(
            _guardado(1, precio=10_000_000),
            _guardado(2, precio=10_000_000),
            _guardado(3, precio=20_000_000, **flojo),
            _guardado(4, precio=20_000_000, **flojo),
            _guardado(5, precio=20_000_000, **flojo),
            _guardado(6, precio=20_000_000, **flojo),
        )
    )
    # (2*100*10M + 4*85*20M) / (2*100 + 4*85) = 8.800M / 540 = 16.296.296
    assert e.media == 16_296_296
    assert e.peso_minimo == 85


def test_la_mediana_tambien_va_ponderada() -> None:
    """Con pesos iguales coincide con la de toda la vida; en cuanto difieren,
    el punto que parte la muestra por la mitad se mueve."""
    flojo = {"scoring": 17, "passing": 13, "playmaking": 7}
    pesados = _medidos(
        _guardado(1, precio=10),
        _guardado(2, precio=20),
        _guardado(3, precio=30),
        _guardado(4, precio=40),
        _guardado(5, precio=50),
        _guardado(6, precio=60, **flojo),
    )
    # Peso total 585, mitad 292,5. Acumulando por precio: 100, 200, 300 pasa de
    # la mitad en el tercero, asi que la mediana es 30 y no 35.
    assert estimar(pesados).mediana == 30
    assert estimar(pesados).media != 30


def test_se_dice_cuantas_son_todavia_provisionales() -> None:
    """Una puja se queda corta: Valerio tenia 65 millones y cerro en 77,7, un
    16% mas. La pantalla tiene que poder avisar."""
    e = estimar(
        _medidos(
            *(_guardado(i) for i in range(1, 5)),
            _guardado(5, firme=False),
            _guardado(6, firme=False),
        )
    )
    assert e.provisionales == 2
    assert e.suficiente is True


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


def test_un_provisional_con_intentos_de_sobra_sigue_contando() -> None:
    """Mientras le queden intentos su puja es un suelo que va a corregirse."""
    venta = _guardado(1, firme=False, intentos=REINTENTOS_DE_RESOLUCION)
    assert cuenta_para_el_numero(venta) is True


def test_un_provisional_sin_intentos_deja_de_contar() -> None:
    """Agotados los intentos, su precio se queda congelado en una puja que
    sabemos corta: se enseña, pero no se promedia."""
    venta = _guardado(1, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1)
    assert cuenta_para_el_numero(venta) is False


def test_una_venta_cerrada_cuenta_aunque_fallaran_los_intentos() -> None:
    """Los intentos solo hablan de la resolucion; si ya se resolvio, sobran."""
    venta = _guardado(1, firme=True, intentos=99)
    assert cuenta_para_el_numero(venta) is True


def test_el_abandonado_se_enseña_pero_no_entra_en_la_media() -> None:
    """Las seis buenas valen 1.000.000; la abandonada, 10. Si entrara en la
    media la hundiria, y la media tiene que seguir siendo 1.000.000."""
    buenas = [_guardado(i, precio=1_000_000) for i in range(1, 7)]
    tirada = _guardado(
        99, precio=10, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1
    )
    medidos = _medidos(*buenas, tirada)

    estimacion = estimar(medidos)
    assert estimacion.media == 1_000_000
    assert estimacion.n == 6
    # Pero sigue en la lista, para que no desaparezca sin explicacion.
    assert 99 in [c.venta.ht_player_id for c in estimacion.comparables]
    assert [c.cuenta for c in estimacion.comparables if c.venta.ht_player_id == 99] == [False]


def test_el_abandonado_no_le_quita_el_sitio_a_una_buena() -> None:
    """Con seis buenas y una abandonada, las seis que cuentan son las buenas."""
    buenas = [_guardado(i, precio=1_000_000) for i in range(1, 7)]
    tirada = _guardado(
        99, precio=9_000_000, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1
    )
    medidos = _medidos(*buenas, tirada)
    assert sorted(c.venta.ht_player_id for c in medidos if c.cuenta) == [1, 2, 3, 4, 5, 6]


def test_con_un_abandonado_se_vuelve_a_salir_a_buscar() -> None:
    """Cinco buenas y una abandonada no son seis: la abandonada es un hueco
    con nombre, y dejarla ocupar plaza impediria buscar lo que falta."""
    cinco = [_guardado(i) for i in range(1, 6)]
    tirada = _guardado(99, firme=False, intentos=REINTENTOS_DE_RESOLUCION + 1)
    assert hay_que_buscar(_medidos(*cinco, tirada)) is True
    # Y con la sexta de verdad, ya no.
    assert hay_que_buscar(_medidos(*cinco, _guardado(6))) is False
