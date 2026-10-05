"""El buscador de comparables: a quién se parece un jugador y qué se paga por él.

Lo que se vigila aquí no son los campos sino las maneras en que este motor
podría MENTIR SIN FALLAR, que son cuatro y todas silenciosas:

  · contar como «el mercado ofrece cero» a quien nadie pujó;
  · dar por comparable a un jugador que tiene los tres niveles pedidos pero
    cuya terna es otra, es decir que juega a otra cosa;
  · cobrarle a alguien un peso distinto del que le toca según en qué búsqueda
    apareciera;
  · dar un precio con menos de seis, o repetir a alguien para llegar a seis.

Y la escalera misma: si una ventana se estrechase al bajar de escalón, o si
dos escalones compartieran peso, el motor seguiría devolviendo un número y el
número sería otro. Por eso sus invariantes se comprueban como código, no se
leen.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.engines.mercado_comparable import (
    EDAD_MINIMA,
    ESCALERA,
    ESCALERA_DUO,
    MINIMO_DE_COMPARABLES,
    ORDEN_DE_DESEMPATE,
    SUELO_DE_PESO,
    Candidato,
    Comparable,
    Objetivo,
    candidato_de,
    escalera_de,
    estimar,
    frontera_semanal,
    objetivo_de,
    peso_de,
    plan_de_busqueda,
    recolectar,
    terna,
    toca_buscar,
    ventana_de,
)
from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).parent / "fixtures"

EDAD = 24


def _hab(**niveles: int) -> dict[str, int]:
    """Las seis habilidades que cuentan, con el resto a 1 (lo más bajo real)."""
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 1)
    base.update(niveles)
    return base


#: El objetivo corriente: un creador de juego de 24 años. Creación 11
#: primaria, pases 9 secundaria, defensa 8 terciaria.
SKILLS = _hab(playmaking=11, passing=9, defending=8)

#: El objetivo de las pruebas de la escalera, con los tres rasgos muy
#: separados y el resto a cero. Hace falta para medir UN eje a la vez: con los
#: niveles pegados, mover la secundaria tres niveles la hunde por debajo de la
#: terciaria y lo que falla es la forma del jugador, no el escalón que se
#: quería medir.
ESPACIADO = {
    "playmaking": 18,
    "passing": 14,
    "defending": 9,
    "keeper": 0,
    "scoring": 0,
    "winger": 0,
}


def _objetivo(ht_player_id: int = 777, edad: int = EDAD, **niveles: int) -> Objetivo:
    hecho = objetivo_de(ht_player_id, edad, _hab(**niveles) if niveles else SKILLS)
    assert hecho is not None
    return hecho


def _espaciado() -> Objetivo:
    hecho = objetivo_de(777, EDAD, ESPACIADO)
    assert hecho is not None
    return hecho


def _fila(
    ident: int,
    *,
    edad: int = EDAD,
    puja: int = 4_000_000,
    skills: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    """Una fila con la forma EXACTA que devuelve el parser del mercado."""
    fila: dict[str, Any] = {
        "ht_player_id": ident,
        "first_name": "Jugador",
        "last_name": str(ident),
        "age_years": edad,
        "age_days": 100,
        "asking_price": puja,
        "highest_bid": puja,
        "has_bids": puja > 0,
        "injury_level": -1,
        "deadline": "2026-10-06 21:30:00",
        "tsi": 150_000,
        "specialty": 0,
        "seller_team_name": "Equipo Ajeno",
        "seller_league_id": 92,
        "skills": dict(SKILLS) if skills is None else skills,
    }
    fila.update(extra)
    return fila


def _candidato(edad: int = EDAD, **niveles: int) -> Candidato:
    """Un candidato sobre el objetivo espaciado, moviendo lo que se le diga."""
    skills = dict(ESPACIADO)
    skills.update(niveles)
    hecho = candidato_de(_fila(1, edad=edad, skills=skills))
    assert hecho is not None
    return hecho


# --------------------------------------------------------------------------
# La terna
# --------------------------------------------------------------------------


def test_la_terna_sale_de_seis_habilidades_y_la_resistencia_no_es_una() -> None:
    """La resistencia y el balón parado no entran aunque sean las más altas.

    El usuario lo decidió el 2026-10-04 y cambia a quién se parece cada
    jugador: con la resistencia dentro, un creador de juego que corre mucho se
    compararía contra gente que juega a otra cosa.
    """
    tres = terna(_hab(playmaking=11, passing=9, defending=8, stamina=20, set_pieces=20))
    assert tres is not None
    assert [rasgo.habilidad for rasgo in tres] == ["playmaking", "passing", "defending"]
    assert [rasgo.nivel for rasgo in tres] == [11, 9, 8]


def test_el_empate_lo_rompe_el_orden_que_dicto_el_usuario() -> None:
    """Sin desempate fijo el mismo jugador daría ternas distintas cada semana
    y dejaría de ser comparable consigo mismo."""
    tres = terna(dict.fromkeys(ORDEN_DE_DESEMPATE, 7))
    assert tres is not None
    assert [rasgo.habilidad for rasgo in tres] == ["playmaking", "keeper", "defending"]


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


def test_sin_ninguna_habilidad_no_hay_terna() -> None:
    """Seis ceros no es un jugador flojo, es un hueco en los datos."""
    assert terna(dict.fromkeys(ORDEN_DE_DESEMPATE, 0)) is None
    assert terna({}) is None
    assert terna({"stamina": 20, "set_pieces": 20}) is None


def test_un_nivel_negativo_cuenta_como_cero() -> None:
    """En Hattrick no existe un nivel negativo: si llega uno, es basura."""
    tres = terna(_hab(playmaking=-5, keeper=3))
    assert tres is not None
    assert tres[0].habilidad == "keeper"
    assert terna(dict.fromkeys(ORDEN_DE_DESEMPATE, -1)) is None


def test_una_habilidad_que_falta_vale_cero_y_las_desconocidas_se_ignoran() -> None:
    tres = terna({"playmaking": 5, "inventada": 99})
    assert tres is not None
    assert tres[0].habilidad == "playmaking"
    # Los dos huecos siguientes se llenan por orden de desempate.
    assert [rasgo.habilidad for rasgo in tres[1:]] == ["keeper", "defending"]
    assert [rasgo.nivel for rasgo in tres[1:]] == [0, 0]


def test_sin_terna_o_sin_edad_no_hay_objetivo() -> None:
    assert objetivo_de(1, EDAD, dict.fromkeys(ORDEN_DE_DESEMPATE, 0)) is None
    assert objetivo_de(1, 0, SKILLS) is None
    assert objetivo_de(1, -3, SKILLS) is None


# --------------------------------------------------------------------------
# La escalera
# --------------------------------------------------------------------------


def test_la_escalera_empieza_exacta_en_cien_y_termina_en_el_suelo() -> None:
    assert ESCALERA[0].peso == 100
    assert (ESCALERA[0].edad, ESCALERA[0].primaria) == (0, 0)
    assert (ESCALERA[0].secundaria, ESCALERA[0].terciaria) == (0, 0)
    assert ESCALERA[-1].peso == SUELO_DE_PESO == 30


def test_los_pesos_bajan_siempre_y_ninguno_se_repite() -> None:
    """Si dos escalones compartieran peso, el más ancho podría adelantar al
    más estrecho y nadie lo notaría en el número final."""
    pesos = [escalon.peso for escalon in ESCALERA]
    assert pesos == sorted(pesos, reverse=True)
    assert len(set(pesos)) == len(pesos)


def test_ninguna_ventana_se_estrecha_al_bajar_de_escalon() -> None:
    """La escalera sólo abre. Si un escalón de menos peso cerrase un rasgo, un
    jugador podría quedar fuera de un escalón ancho estando dentro de uno
    estrecho, y cobraría un peso peor del que le toca."""
    for antes, despues in zip(ESCALERA, ESCALERA[1:], strict=False):
        assert despues.edad >= antes.edad
        assert despues.primaria >= antes.primaria
        assert despues.secundaria >= antes.secundaria
        assert despues.terciaria >= antes.terciaria


def test_la_primera_vuelta_es_literalmente_la_que_dicto_el_usuario() -> None:
    """Terciaria, terciaria, secundaria, edad, primaria, con esos pesos.

    Esta prueba existe para que nadie «mejore» el orden sin hablar con él.
    """
    seis = ESCALERA[:6]
    assert [escalon.peso for escalon in seis] == [100, 90, 85, 80, 75, 70]
    assert [escalon.terciaria for escalon in seis] == [0, 1, 2, 2, 2, 2]
    assert [escalon.secundaria for escalon in seis] == [0, 0, 0, 1, 1, 1]
    assert [escalon.edad for escalon in seis] == [0, 0, 0, 0, 1, 1]
    assert [escalon.primaria for escalon in seis] == [0, 0, 0, 0, 0, 1]


# --------------------------------------------------------------------------
# Las ventanas
# --------------------------------------------------------------------------


def test_el_plan_tiene_una_busqueda_por_escalon_y_va_de_estrecha_a_ancha() -> None:
    plan = plan_de_busqueda(_objetivo())
    assert len(plan) == len(ESCALERA)
    assert [ventana.peso for ventana in plan] == [escalon.peso for escalon in ESCALERA]
    primera = plan[0]
    assert primera.edad_minima == primera.edad_maxima == EDAD
    assert primera.primaria.minimo == primera.primaria.maximo == 11
    assert primera.terciaria.minimo == primera.terciaria.maximo == 8


def test_la_ventana_de_edad_no_baja_de_diecisiete() -> None:
    """No hay jugadores de 15 años en el primer equipo: pedirlos sería gastar
    una llamada en un tramo vacío."""
    ventana = ventana_de(_objetivo(edad=17), ESCALERA[-1])
    assert ventana.edad_minima == EDAD_MINIMA == 17
    assert ventana.edad_maxima == 19


def test_la_ventana_de_nivel_no_pide_negativos() -> None:
    ventana = ventana_de(_objetivo(playmaking=11, passing=9, defending=2), ESCALERA[-1])
    assert ventana.terciaria.minimo == 0
    assert ventana.terciaria.maximo == 8


# --------------------------------------------------------------------------
# El peso de un candidato
# --------------------------------------------------------------------------


def test_el_exacto_vale_cien() -> None:
    assert peso_de(_candidato(), _espaciado()) == 100


def test_cada_nivel_que_se_abre_en_la_terciaria_cuesta_lo_suyo() -> None:
    objetivo = _espaciado()
    esperado = {1: 90, 2: 85, 3: 65, 4: 60, 5: 40, 6: 35}
    for distancia, peso in esperado.items():
        assert peso_de(_candidato(defending=9 - distancia), objetivo) == peso, distancia


def test_pasada_la_terciaria_del_ultimo_escalon_ya_no_se_parece() -> None:
    """Siete niveles de distancia: ningún escalón abre tanto."""
    assert peso_de(_candidato(defending=2), _espaciado()) is None


def test_mover_la_secundaria_cuesta_ochenta_cincuenta_y_cinco_y_treinta() -> None:
    objetivo = _espaciado()
    assert peso_de(_candidato(passing=13), objetivo) == 80
    assert peso_de(_candidato(passing=12), objetivo) == 55
    assert peso_de(_candidato(passing=11), objetivo) == 30
    assert peso_de(_candidato(passing=10), objetivo) is None


def test_mover_la_edad_cuesta_setenta_y_cinco_y_cincuenta() -> None:
    objetivo = _espaciado()
    assert peso_de(_candidato(edad=25), objetivo) == 75
    assert peso_de(_candidato(edad=23), objetivo) == 75
    assert peso_de(_candidato(edad=26), objetivo) == 50
    assert peso_de(_candidato(edad=22), objetivo) == 50
    assert peso_de(_candidato(edad=27), objetivo) is None
    assert peso_de(_candidato(edad=21), objetivo) is None


def test_mover_la_primaria_cuesta_setenta_y_cuarenta_y_cinco() -> None:
    objetivo = _espaciado()
    assert peso_de(_candidato(playmaking=19), objetivo) == 70
    assert peso_de(_candidato(playmaking=17), objetivo) == 70
    assert peso_de(_candidato(playmaking=20), objetivo) == 45
    assert peso_de(_candidato(playmaking=21), objetivo) is None


def test_dos_aperturas_a_la_vez_pagan_el_escalon_donde_las_dos_estan_abiertas() -> None:
    objetivo = _espaciado()
    # Edad y primaria: el primer escalón con las dos abiertas es el de 70.
    assert peso_de(_candidato(edad=25, playmaking=19), objetivo) == 70
    # Edad y terciaria: el de 75 ya tiene la terciaria abierta a dos.
    assert peso_de(_candidato(edad=25, defending=8), objetivo) == 75
    # Secundaria y terciaria: el de 80.
    assert peso_de(_candidato(passing=13, defending=7), objetivo) == 80


def test_los_mismos_tres_numeros_en_otras_habilidades_son_otro_jugador() -> None:
    """El caso que obliga a comparar la terna por NOMBRE y no sólo por nivel.

    Este delantero tiene 18, 14 y 9, exactamente los tres niveles del
    objetivo, y hasta coinciden sus huecos segundo y tercero. Pero su 18 es de
    anotación y el del objetivo es de creación: lo que se paga por un
    delantero no dice nada de lo que se paga por un creador de juego. Sin esta
    comprobación valdría 100%, el peso máximo, que es el error más caro que
    puede cometer este motor.
    """
    delantero = _candidato(playmaking=0, scoring=18)
    assert delantero.primaria.habilidad == "scoring"
    assert [rasgo.habilidad for rasgo in (delantero.secundaria, delantero.terciaria)] == [
        "passing",
        "defending",
    ]
    assert peso_de(delantero, _espaciado()) is None


def test_un_segundo_rasgo_distinto_con_los_mismos_numeros_no_sirve() -> None:
    """Los tres niveles idénticos y la primaria y la terciaria con el mismo
    nombre; lo único que cambia es el segundo rasgo, anotación en vez de
    pases. Es un creador que remata contra un creador que pasa: dos jugadores
    que no se venden al mismo precio. Sin comparar el nombre del hueco de en
    medio, éste entraría al 100%."""
    atacante = _candidato(passing=0, scoring=14)
    assert atacante.secundaria.habilidad == "scoring"
    assert atacante.terciaria.habilidad == "defending"
    assert [atacante.primaria.nivel, atacante.secundaria.nivel, atacante.terciaria.nivel] == [
        18,
        14,
        9,
    ]
    assert peso_de(atacante, _espaciado()) is None


def test_los_mismos_niveles_en_otro_orden_tampoco_sirven() -> None:
    """Pases 18 y creación 14 es el jugador espejo, no el mismo jugador."""
    espejo = _candidato(playmaking=14, passing=18)
    assert espejo.primaria.habilidad == "passing"
    assert peso_de(espejo, _espaciado()) is None


def test_una_terciaria_adelantada_por_otra_habilidad_cambia_la_forma() -> None:
    """Defensa 3 está dentro de la ventana más ancha (9 menos 6), pero con
    portería a 4 su terciaria ya no es la defensa: es otro jugador."""
    candidato = _candidato(defending=3, keeper=4)
    assert candidato.terciaria.habilidad == "keeper"
    assert peso_de(candidato, _espaciado()) is None


def test_una_terciaria_que_sube_por_encima_de_la_secundaria_es_otro_jugador() -> None:
    central = _candidato(defending=15)
    assert central.secundaria.habilidad == "defending"
    assert peso_de(central, _espaciado()) is None


# --------------------------------------------------------------------------
# Leer una fila del mercado
# --------------------------------------------------------------------------


def test_una_fila_sin_jugador_no_es_un_candidato() -> None:
    assert candidato_de(_fila(0)) is None
    assert candidato_de({"skills": dict(SKILLS)}) is None
    assert candidato_de(_fila(1, ht_player_id=None)) is None


def test_una_fila_sin_habilidades_no_es_un_candidato() -> None:
    assert candidato_de(_fila(1, skills=dict.fromkeys(ORDEN_DE_DESEMPATE, 0))) is None
    assert candidato_de(_fila(1, skills={})) is None
    # Y si llega algo que no es un diccionario, no se revienta.
    assert candidato_de(_fila(1, skills=[1, 2, 3])) is None


def test_sin_dato_de_lesion_el_candidato_esta_sano() -> None:
    """El fichero del mercado no trae la lesión mientras hay un partido en
    juego, y eso es media tarde de domingo. Su ausencia es sano (-1), nunca
    magullado (0)."""
    sin_campo = _fila(1)
    del sin_campo["injury_level"]
    candidato = candidato_de(sin_campo)
    assert candidato is not None
    assert candidato.lesion == -1
    nulo = candidato_de(_fila(1, injury_level=None))
    assert nulo is not None
    assert nulo.lesion == -1


def test_la_bandera_del_parser_manda_sobre_el_cero_de_la_puja() -> None:
    sin_pujas = candidato_de(_fila(1, puja=0))
    assert sin_pujas is not None
    assert sin_pujas.tiene_puja is False
    # Y sin bandera se deduce de la puja, para que una fila a mano funcione.
    a_mano = _fila(1, puja=1_000)
    del a_mano["has_bids"]
    deducido = candidato_de(a_mano)
    assert deducido is not None
    assert deducido.tiene_puja is True


def test_una_puja_negativa_se_lee_como_cero_y_no_cuenta() -> None:
    candidato = candidato_de(_fila(1, highest_bid=-5, has_bids=True))
    assert candidato is not None
    assert candidato.puja == 0
    assert recolectar(_objetivo(), [_fila(1, highest_bid=-5, has_bids=True)]) == {}


def test_el_nombre_se_arma_con_lo_que_haya_y_sin_espacios_sobrantes() -> None:
    candidato = candidato_de(_fila(1, first_name="", last_name="Peñaranda"))
    assert candidato is not None
    assert candidato.nombre == "Peñaranda"


# --------------------------------------------------------------------------
# Recolectar
# --------------------------------------------------------------------------


def test_el_propio_jugador_no_es_comparable_consigo_mismo() -> None:
    """Si lo tienes puesto en el mercado, su puja es el precio que queremos
    estimar: contarla sería escribir la respuesta en el enunciado."""
    assert recolectar(_objetivo(ht_player_id=4242), [_fila(4242)]) == {}


def test_el_que_nadie_pujo_no_cuenta() -> None:
    """Su precio pedido es una opinión del vendedor, no un dato del mercado."""
    objetivo = _objetivo()
    assert recolectar(objetivo, [_fila(1, puja=0)]) == {}
    assert recolectar(objetivo, [_fila(1, highest_bid=0, has_bids=False)]) == {}


def test_el_lesionado_queda_fuera_pero_el_magullado_y_el_sano_entran() -> None:
    reunidos = recolectar(
        _objetivo(),
        [
            _fila(1, injury_level=-1),
            _fila(2, injury_level=0),
            _fila(3, injury_level=1),
            _fila(4, injury_level=8),
        ],
    )
    assert sorted(reunidos) == [1, 2]


def test_un_plazo_ya_vencido_con_puja_sigue_contando() -> None:
    """El fichero avisa de que el plazo puede venir vencido unas horas. Una
    puja con el plazo cerrado es lo más parecido a una venta que hay aquí: lo
    último que alguien ofreció de verdad. Tirarla sería tirar el mejor dato."""
    reunidos = recolectar(_objetivo(), [_fila(1, deadline="2026-09-01 10:00:00")])
    assert sorted(reunidos) == [1]


def test_el_que_no_se_parece_no_entra_aunque_la_busqueda_lo_devuelva() -> None:
    """Una búsqueda ancha devuelve de más. El filtro final es local, así que
    da igual lo que acepte de verdad la búsqueda del juego."""
    portero = _fila(1, skills=_hab(keeper=15, defending=7, playmaking=3))
    assert recolectar(_objetivo(), [portero]) == {}


def test_cada_jugador_cuenta_una_vez_y_con_su_mejor_peso() -> None:
    """La misma búsqueda repetida, o el mismo jugador en dos páginas, no puede
    contar dos veces: seis repeticiones de uno no son seis comparables."""
    reunidos = recolectar(_objetivo(), [_fila(1), _fila(1), _fila(1)])
    assert len(reunidos) == 1
    assert reunidos[1].peso == 100


def test_el_orden_de_llegada_no_cambia_el_peso_de_nadie() -> None:
    """Si el mercado cambió entre dos páginas y el mismo jugador llega con
    datos distintos, se queda con el mejor peso, venga en el orden que
    venga."""
    objetivo = _objetivo()
    exacto = _fila(1)
    lejano = _fila(1, skills=_hab(playmaking=11, passing=9, defending=6))
    assert recolectar(objetivo, [exacto, lejano])[1].peso == 100
    assert recolectar(objetivo, [lejano, exacto])[1].peso == 100


def test_lo_reunido_se_acumula_entre_busquedas_sin_tocar_lo_anterior() -> None:
    objetivo = _objetivo()
    primera = recolectar(objetivo, [_fila(1)])
    segunda = recolectar(objetivo, [_fila(2)], primera)
    assert sorted(segunda) == [1, 2]
    # El diccionario de entrada no se modifica: quien lo pasó sigue teniendo
    # lo que tenía.
    assert sorted(primera) == [1]


def test_una_lista_vacia_no_rompe_nada() -> None:
    assert recolectar(_objetivo(), []) == {}


# --------------------------------------------------------------------------
# Estimar
# --------------------------------------------------------------------------


def _reunidos(*pares: tuple[int, int]) -> dict[int, Comparable]:
    """Comparables a mano: `(peso, puja)` por cada uno."""
    hechos: dict[int, Comparable] = {}
    for indice, (peso, puja) in enumerate(pares, start=1):
        candidato = candidato_de(_fila(indice, puja=puja))
        assert candidato is not None
        hechos[indice] = Comparable(candidato=candidato, peso=peso)
    return hechos


def test_sin_nadie_no_hay_precio_y_tampoco_es_un_error() -> None:
    vacia = estimar({})
    assert vacia.precio is None
    assert vacia.suficiente is False
    assert vacia.n == 0
    assert vacia.peso_minimo == 0
    assert vacia.comparables == ()


def test_con_cinco_no_hay_precio_pero_si_lista() -> None:
    """La pantalla tiene que poder decir «no hay mercado comparable esta
    semana» y enseñar los cinco: callarse los cinco sería esconder el trabajo
    que sí se hizo."""
    cinco = estimar(_reunidos(*[(100, 4_000_000)] * (MINIMO_DE_COMPARABLES - 1)))
    assert cinco.precio is None
    assert cinco.suficiente is False
    assert cinco.n == MINIMO_DE_COMPARABLES - 1
    assert len(cinco.comparables) == MINIMO_DE_COMPARABLES - 1


def test_con_seis_al_cien_la_ponderada_es_la_media_simple() -> None:
    pujas = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000]
    seis = estimar(_reunidos(*[(100, puja) for puja in pujas]))
    assert seis.suficiente is True
    assert seis.precio == 3_500_000
    assert seis.peso_minimo == 100


def test_los_pesos_mueven_el_precio_y_se_puede_comprobar_a_mano() -> None:
    """El ejemplo que se le enseñó al usuario: dos exactos, tres al 90 y uno
    al 85. Si los pesos no entrasen, saldría 4.466.667."""
    estimacion = estimar(
        _reunidos(
            (100, 4_500_000),
            (100, 4_100_000),
            (90, 3_900_000),
            (90, 4_800_000),
            (90, 4_300_000),
            (85, 5_200_000),
        )
    )
    assert estimacion.n == 6
    assert estimacion.precio == 4_454_054
    assert estimacion.peso_minimo == 85
    assert estimacion.precio != round(26_800_000 / 6)


def test_el_mejor_parecido_se_enseña_primero() -> None:
    estimacion = estimar(_reunidos((70, 1), (100, 2), (85, 3)))
    assert [c.peso for c in estimacion.comparables] == [100, 85, 70]


def test_el_precio_se_redondea_al_par_como_el_resto_de_la_casa() -> None:
    """Para que esta cifra y la simulación de venta del front no discrepen en
    una unidad cuando el reparto cae justo en la mitad."""
    abajo = estimar(_reunidos(*[(100, 1_000_000)] * 5, (100, 1_000_003)))
    assert abajo.precio == 1_000_000
    arriba = estimar(_reunidos(*[(100, 1_000_001)] * 5, (100, 1_000_004)))
    assert arriba.precio == 1_000_002


def test_el_suelo_de_peso_es_treinta_y_se_informa_cual_fue_el_peor() -> None:
    estimacion = estimar(_reunidos(*[(SUELO_DE_PESO, 1_000_000)] * MINIMO_DE_COMPARABLES))
    assert estimacion.suficiente is True
    assert estimacion.peso_minimo == 30


def test_el_recorrido_entero_de_una_busqueda_que_junta_seis() -> None:
    """De punta a punta: tres escalones, con repetidos, sin pujas, lesionados
    y un portero que la búsqueda devolvió de más, hasta dar un precio."""
    objetivo = _objetivo()
    reunidos = recolectar(
        objetivo,
        [
            _fila(1, puja=4_500_000),
            _fila(2, puja=4_100_000),
            _fila(3, puja=9_000_000, highest_bid=0, has_bids=False),
            _fila(4, puja=9_000_000, injury_level=3),
        ],
    )
    assert estimar(reunidos).suficiente is False

    terciaria_abierta = _hab(playmaking=11, passing=9, defending=7)
    reunidos = recolectar(
        objetivo,
        [
            _fila(1, puja=4_500_000),  # el exacto, que ya estaba
            _fila(5, puja=3_900_000, skills=terciaria_abierta),
            _fila(6, puja=4_800_000, skills=terciaria_abierta),
            _fila(7, puja=4_300_000, skills=terciaria_abierta),
            _fila(8, puja=9_900_000, skills=_hab(keeper=14, defending=9)),
        ],
        reunidos,
    )
    assert estimar(reunidos).suficiente is False

    reunidos = recolectar(
        objetivo,
        [_fila(9, puja=5_200_000, skills=_hab(playmaking=11, passing=9, defending=6))],
        reunidos,
    )
    estimacion = estimar(reunidos)
    assert estimacion.n == MINIMO_DE_COMPARABLES
    assert [c.peso for c in estimacion.comparables] == [100, 100, 90, 90, 90, 85]
    assert estimacion.precio == 4_454_054


# --------------------------------------------------------------------------
# Contra el parser de verdad
# --------------------------------------------------------------------------


def test_el_motor_habla_el_mismo_idioma_que_el_parser() -> None:
    """Sin esto, un cambio de nombre de campo en el parser dejaría el motor
    devolviendo cero comparables para siempre y sin fallar.

    De los tres del fichero sólo uno tiene puja, y de paso se ve por qué la
    resistencia no entra: la de Aurelio es 8 y sería su terciaria en lugar del
    lateral 6, con lo que su terna sería otra.
    """
    datos = get_parser("transfersearch")((FIXTURES / "transfersearch.xml").read_bytes())
    objetivo = objetivo_de(999, 24, _hab(passing=11, playmaking=9, winger=6))
    assert objetivo is not None
    reunidos = recolectar(objetivo, datos["results"])
    assert sorted(reunidos) == [491002001]
    comparable = reunidos[491002001]
    assert comparable.peso == 100
    assert comparable.candidato.nombre == "Aurelio Barrantes"
    assert comparable.candidato.puja == 4_500_000
    assert comparable.candidato.terciaria.habilidad == "winger"
    assert comparable.candidato.liga_del_vendedor == 92
    estimacion = estimar(reunidos)
    assert estimacion.suficiente is False
    assert estimacion.precio is None


def test_si_el_del_mercado_eres_tu_no_queda_nadie() -> None:
    datos = get_parser("transfersearch")((FIXTURES / "transfersearch.xml").read_bytes())
    objetivo = objetivo_de(491002001, 24, _hab(passing=11, playmaking=9, winger=6))
    assert objetivo is not None
    assert recolectar(objetivo, datos["results"]) == {}


def test_una_busqueda_sin_resultados_no_reune_a_nadie() -> None:
    datos = get_parser("transfersearch")((FIXTURES / "chpperror.xml").read_bytes())
    assert recolectar(_objetivo(), datos["results"]) == {}


# --------------------------------------------------------------------------
# Cuándo se corre
# --------------------------------------------------------------------------

HT = ZoneInfo("Europe/Stockholm")
BOGOTA = ZoneInfo("America/Bogota")


def _ht(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=HT)


def test_el_viernes_antes_de_las_ocho_la_frontera_es_la_de_hace_una_semana() -> None:
    """A las 19:59 del viernes la semana de mercado todavía no ha empezado."""
    assert frontera_semanal(_ht("2026-10-09 19:59:59")) == _ht("2026-10-02 20:00").astimezone(UTC)


def test_a_las_ocho_en_punto_la_semana_ya_cambio() -> None:
    esperada = _ht("2026-10-09 20:00").astimezone(UTC)
    assert frontera_semanal(_ht("2026-10-09 20:00:00")) == esperada
    assert frontera_semanal(_ht("2026-10-09 20:00:01")) == esperada


def test_el_sabado_de_madrugada_y_el_jueves_de_noche_miran_al_mismo_viernes() -> None:
    sabado = frontera_semanal(_ht("2026-10-10 00:30:00"))
    jueves = frontera_semanal(_ht("2026-10-15 23:00:00"))
    assert sabado == jueves == _ht("2026-10-09 20:00").astimezone(UTC)


def test_las_ocho_de_la_tarde_no_son_la_misma_hora_en_enero_y_en_julio() -> None:
    """El desfase sale de la base de zonas, no de una constante: en invierno
    las 20:00 suecas son las 19:00 UTC y en verano las 18:00."""
    assert frontera_semanal(_ht("2026-01-09 21:00:00")).hour == 19
    assert frontera_semanal(_ht("2026-07-10 21:00:00")).hour == 18


def test_la_zona_entra_por_parametro() -> None:
    """El usuario pidió la hora del país del equipo. Cuando sepamos de dónde
    sacarla, se pasa aquí y nada más cambia."""
    frontera = frontera_semanal(datetime(2026, 10, 10, 12, 0, tzinfo=UTC), BOGOTA)
    assert frontera == datetime(2026, 10, 10, 1, 0, tzinfo=UTC)


def test_una_fecha_sin_zona_se_entiende_en_utc() -> None:
    con_zona = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    assert frontera_semanal(con_zona.replace(tzinfo=None)) == frontera_semanal(con_zona)


def test_la_primera_vez_siempre_toca() -> None:
    assert toca_buscar(None, _ht("2026-10-10 09:00:00")) is True


def test_toca_si_la_ultima_fue_antes_de_la_frontera_y_no_si_fue_despues() -> None:
    ahora = _ht("2026-10-10 09:00:00")
    frontera = frontera_semanal(ahora)
    assert toca_buscar(frontera - timedelta(seconds=1), ahora) is True
    # Justo en la frontera ya cuenta como hecha esta semana.
    assert toca_buscar(frontera, ahora) is False
    assert toca_buscar(frontera + timedelta(seconds=1), ahora) is False


def test_una_ultima_busqueda_sin_zona_se_entiende_en_utc() -> None:
    ahora = _ht("2026-10-10 09:00:00")
    frontera = frontera_semanal(ahora)
    antes = (frontera - timedelta(minutes=1)).replace(tzinfo=None)
    despues = (frontera + timedelta(minutes=1)).replace(tzinfo=None)
    assert toca_buscar(antes, ahora) is True
    assert toca_buscar(despues, ahora) is False


def test_un_reloj_descuadrado_hacia_el_futuro_no_dispara_nada() -> None:
    assert toca_buscar(_ht("2027-01-01 00:00:00"), _ht("2026-10-10 09:00:00")) is False


def test_dos_visitas_de_la_misma_semana_buscan_una_sola_vez() -> None:
    """El caso real: se entra el sábado y se busca, y se vuelve a entrar el
    domingo, el miércoles y el viernes a las ocho menos uno sin que se repita,
    hasta que el viernes dan las ocho."""
    sabado = _ht("2026-10-10 09:00:00")
    assert toca_buscar(None, sabado) is True
    hecha = sabado  # se anota cuándo se buscó
    assert toca_buscar(hecha, _ht("2026-10-11 10:00:00")) is False
    assert toca_buscar(hecha, _ht("2026-10-14 23:59:00")) is False
    assert toca_buscar(hecha, _ht("2026-10-16 19:59:00")) is False
    assert toca_buscar(hecha, _ht("2026-10-16 20:00:00")) is True


# --------------------------------------------------------------------------
# El modo dúo, sin terciaria
# --------------------------------------------------------------------------


def _duo() -> Objetivo:
    hecho = objetivo_de(777, EDAD, ESPACIADO, con_terciaria=False)
    assert hecho is not None
    return hecho


def test_sin_terciaria_el_objetivo_solo_guarda_dos_rasgos() -> None:
    objetivo = _duo()
    assert objetivo.primaria.habilidad == "playmaking"
    assert objetivo.secundaria.habilidad == "passing"
    assert objetivo.terciaria is None


def test_la_escalera_del_duo_tambien_abre_siempre_y_baja_siempre() -> None:
    pesos = [escalon.peso for escalon in ESCALERA_DUO]
    assert pesos[0] == 100
    assert pesos[-1] == SUELO_DE_PESO
    assert pesos == sorted(pesos, reverse=True)
    assert len(set(pesos)) == len(pesos)
    for antes, despues in zip(ESCALERA_DUO, ESCALERA_DUO[1:], strict=False):
        assert despues.edad >= antes.edad
        assert despues.primaria >= antes.primaria
        assert despues.secundaria >= antes.secundaria


def test_la_vuelta_del_duo_tiene_cuatro_aperturas_en_vez_de_cinco() -> None:
    """Los dos escalones que abrían la terciaria pasan a la secundaria, que
    ahora es el rasgo menos importante que queda."""
    cinco = ESCALERA_DUO[:5]
    assert [escalon.peso for escalon in cinco] == [100, 90, 85, 80, 75]
    assert [escalon.secundaria for escalon in cinco] == [0, 1, 2, 2, 2]
    assert [escalon.edad for escalon in cinco] == [0, 0, 0, 1, 1]
    assert [escalon.primaria for escalon in cinco] == [0, 0, 0, 0, 1]
    assert all(escalon.terciaria == 0 for escalon in ESCALERA_DUO)


def test_cada_modo_recorre_su_propia_escalera() -> None:
    assert escalera_de(_espaciado()) is ESCALERA
    assert escalera_de(_duo()) is ESCALERA_DUO
    assert len(plan_de_busqueda(_duo())) == len(ESCALERA_DUO)


def test_sin_terciaria_la_ventana_no_pide_una_tercera_habilidad() -> None:
    """Si la pidiera, la búsqueda de verdad gastaría un filtro en un criterio
    que luego nadie aplica."""
    ventana = ventana_de(_duo(), ESCALERA_DUO[0])
    assert ventana.terciaria is None
    assert ventana.primaria.habilidad == "playmaking"
    assert ventana.secundaria.habilidad == "passing"


def test_sin_terciaria_entra_quien_con_terciaria_quedaba_fuera() -> None:
    """Es justo lo que se compra al quitarla, y lo que se paga.

    Este candidato tiene la primaria y la secundaria exactas, pero su tercera
    habilidad es otra y está lejísimos. Con tres rasgos es otro jugador; con
    dos, es comparable al 100%.
    """
    otro = _candidato(defending=0, scoring=9)
    assert otro.terciaria.habilidad == "scoring"
    assert peso_de(otro, _espaciado()) is None
    assert peso_de(otro, _duo()) == 100


def test_sin_terciaria_los_dos_primeros_rasgos_se_siguen_mirando_por_nombre() -> None:
    """Quitar la terciaria afloja, no abre la puerta: un delantero con los
    mismos dos números sigue siendo otro jugador."""
    delantero = _candidato(playmaking=0, scoring=18)
    assert delantero.primaria.habilidad == "scoring"
    assert peso_de(delantero, _duo()) is None


def test_sin_terciaria_los_niveles_de_los_dos_rasgos_siguen_pesando() -> None:
    objetivo = _duo()
    assert peso_de(_candidato(passing=13), objetivo) == 90
    assert peso_de(_candidato(passing=12), objetivo) == 85
    assert peso_de(_candidato(edad=25), objetivo) == 80
    assert peso_de(_candidato(playmaking=19), objetivo) == 75
    assert peso_de(_candidato(edad=28), objetivo) is None
