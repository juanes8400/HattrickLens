"""El buscador de comparables: a quién se parece un jugador y qué se paga por él.

Lo que se vigila aquí no son los campos sino las maneras en que este motor
podría MENTIR SIN FALLAR, que son cinco y todas silenciosas:

  · contar como «el mercado ofrece cero» a quien nadie pujó;
  · contar una subasta recién abierta, cuya puja habla de por dónde va la
    escalada y no de lo que vale el jugador;
  · dar por comparable a quien tiene esos niveles en otras habilidades, es
    decir a quien juega a otra cosa;
  · cobrarle a alguien un peso distinto del que le toca;
  · dar un precio con menos de seis, o repetir a alguien para llegar a seis.

Y la escalera misma: si un peso se repitiera o un escalón pidiera algo
imposible, el motor seguiría devolviendo un número y el número sería otro. Por
eso sus invariantes se comprueban como código, no se leen.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.engines.mercado_comparable import (
    EDAD_MINIMA,
    ESCALERA,
    ESCALON_DE_PESO,
    HORAS_PARA_QUE_CUENTE,
    MINIMO_DE_COMPARABLES,
    ORDEN_DE_DESEMPATE,
    SUELO_DE_PESO,
    Comparable,
    Objetivo,
    candidato_de,
    cierra_pronto,
    estimar,
    frontera_semanal,
    objetivo_de,
    peso_de,
    plan_de_busqueda,
    recolectar,
    terna,
    toca_buscar,
)
from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).parent / "fixtures"

EDAD = 31
#: Un instante fijo, para que las pruebas no dependan de cuándo se corran.
AHORA = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)
#: Hora de Hattrick, que es como viene el plazo en el fichero.
CIERRA_YA = "2026-10-05 20:00:00"
CIERRA_TARDE = "2026-10-08 20:00:00"


def _hab(**niveles: int) -> dict[str, int]:
    """Las seis habilidades que cuentan, con el resto a 1 (lo más bajo real)."""
    base = dict.fromkeys(ORDEN_DE_DESEMPATE, 1)
    base.update(niveles)
    return base


#: Alberto, el delantero con el que se probó contra el mercado de verdad:
#: anotación 18 primaria, pases 13 secundaria.
SKILLS = _hab(scoring=18, passing=13, playmaking=7)


def _objetivo(ht_player_id: int = 777, edad: int = EDAD, **niveles: int) -> Objetivo:
    hecho = objetivo_de(ht_player_id, edad, _hab(**niveles) if niveles else SKILLS)
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
        "deadline": CIERRA_YA,
        "tsi": 150_000,
        "specialty": 0,
        "seller_team_name": "Equipo Ajeno",
        "seller_league_id": 92,
        "skills": dict(SKILLS) if skills is None else skills,
    }
    fila.update(extra)
    return fila


def _candidato(edad: int = EDAD, **niveles: int) -> Any:
    hecho = candidato_de(_fila(1, edad=edad, skills=_hab(**niveles) if niveles else SKILLS))
    assert hecho is not None
    return hecho


def _reune(objetivo: Objetivo, filas: Any, acumulado: Any = None) -> dict[int, Comparable]:
    return recolectar(objetivo, filas, acumulado, ahora=AHORA)


# --------------------------------------------------------------------------
# La terna
# --------------------------------------------------------------------------


def test_la_terna_sale_de_seis_habilidades_y_la_resistencia_no_es_una() -> None:
    """La resistencia y el balón parado no entran aunque sean las más altas.

    Con Alberto esto no es teoría: su balón parado es 9 y su tercera
    habilidad real es creación 7, así que si contara le cambiaría la terna y
    se le compararía contra otra gente.
    """
    tres = terna(_hab(scoring=18, passing=13, playmaking=7, set_pieces=20, stamina=20))
    assert tres is not None
    assert [rasgo.habilidad for rasgo in tres] == ["scoring", "passing", "playmaking"]
    assert [rasgo.nivel for rasgo in tres] == [18, 13, 7]


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


def test_el_objetivo_solo_guarda_las_dos_que_deciden() -> None:
    """La terciaria se calcula y se enseña, pero no compara."""
    objetivo = _objetivo()
    assert (objetivo.primaria.habilidad, objetivo.primaria.nivel) == ("scoring", 18)
    assert (objetivo.secundaria.habilidad, objetivo.secundaria.nivel) == ("passing", 13)
    assert not hasattr(objetivo, "terciaria")


def test_sin_terna_o_sin_edad_no_hay_objetivo() -> None:
    assert objetivo_de(1, EDAD, dict.fromkeys(ORDEN_DE_DESEMPATE, 0)) is None
    assert objetivo_de(1, 0, SKILLS) is None
    assert objetivo_de(1, -3, SKILLS) is None


# --------------------------------------------------------------------------
# La escalera
# --------------------------------------------------------------------------


def test_la_escalera_es_la_que_dicto_el_usuario() -> None:
    """Los cinco primeros escalones, uno a uno.

    Esta prueba existe para que nadie «mejore» el orden sin hablar con él.
    """
    cinco = [(d.primaria, d.secundaria, d.edad, d.peso) for d in ESCALERA[:5]]
    assert cinco == [
        (0, 0, 0, 100),
        (0, -1, 0, 95),
        (-1, 0, 0, 90),
        (0, 0, 1, 85),
        (0, 0, -1, 80),
    ]


def test_cada_vuelta_repite_las_cuatro_aperturas_un_nivel_mas_hondo() -> None:
    segunda = [(d.primaria, d.secundaria, d.edad, d.peso) for d in ESCALERA[5:9]]
    assert segunda == [
        (0, -2, 0, 75),
        (-2, 0, 0, 70),
        (0, 0, 2, 65),
        (0, 0, -2, 60),
    ]


def test_los_pesos_bajan_de_cinco_en_cinco_y_paran_en_el_suelo() -> None:
    pesos = [d.peso for d in ESCALERA]
    assert pesos[0] == 100
    assert pesos[-1] == SUELO_DE_PESO == 30
    assert all(a - b == ESCALON_DE_PESO for a, b in zip(pesos, pesos[1:], strict=False))
    assert len(set(pesos)) == len(pesos)


def test_cada_escalon_mueve_un_solo_eje() -> None:
    """Es la idea entera del rediseño: el peso dice en qué se aparta, y si un
    escalón moviera dos cosas dejaría de decirlo."""
    for desvio in ESCALERA[1:]:
        movidos = [x for x in (desvio.primaria, desvio.secundaria, desvio.edad) if x != 0]
        assert len(movidos) == 1, desvio


def test_ningun_escalon_se_repite() -> None:
    """Dos escalones con el mismo desvío serían una búsqueda gastada dos veces
    y un peso que depende de cuál se mire primero."""
    desvios = [(d.primaria, d.secundaria, d.edad) for d in ESCALERA]
    assert len(set(desvios)) == len(desvios)


def test_las_habilidades_solo_bajan_y_la_edad_va_en_los_dos_sentidos() -> None:
    """Deliberado, y con consecuencia: los comparables son algo más flojos que
    el jugador, así que el precio sale por el lado prudente."""
    assert all(d.primaria <= 0 and d.secundaria <= 0 for d in ESCALERA)
    assert any(d.edad > 0 for d in ESCALERA)
    assert any(d.edad < 0 for d in ESCALERA)


# --------------------------------------------------------------------------
# Las ventanas
# --------------------------------------------------------------------------


def test_cada_escalon_pide_niveles_exactos_no_un_tramo() -> None:
    plan = plan_de_busqueda(_objetivo())
    primera = plan[0]
    assert primera.edad_minima == primera.edad_maxima == EDAD
    assert primera.primaria.minimo == primera.primaria.maximo == 18
    assert primera.secundaria.minimo == primera.secundaria.maximo == 13
    for ventana in plan:
        assert ventana.edad_minima == ventana.edad_maxima
        assert ventana.primaria.minimo == ventana.primaria.maximo
        assert ventana.secundaria.minimo == ventana.secundaria.maximo


def test_el_plan_recorre_la_escalera_entera_de_mejor_a_peor() -> None:
    plan = plan_de_busqueda(_objetivo())
    assert len(plan) == len(ESCALERA)
    assert [v.peso for v in plan] == [d.peso for d in ESCALERA]


def test_un_escalon_imposible_no_se_pide() -> None:
    """Un chaval de 17 años no tiene escalón de «un año menos»: pedirlo
    gastaría una llamada en un tramo vacío, y recortarlo a 17 sería repetir
    una búsqueda ya hecha dándole un peso peor."""
    plan = plan_de_busqueda(_objetivo(edad=EDAD_MINIMA))
    assert all(v.edad_minima >= EDAD_MINIMA for v in plan)
    assert len(plan) < len(ESCALERA)
    # Y los que sí se piden conservan su peso: no se renumeran.
    assert plan[0].peso == 100


def test_una_habilidad_baja_tampoco_se_pide_en_negativo() -> None:
    plan = plan_de_busqueda(_objetivo(scoring=18, passing=2, playmaking=1))
    assert all(v.secundaria.minimo >= 0 for v in plan)
    assert len(plan) < len(ESCALERA)


# --------------------------------------------------------------------------
# El peso de un candidato
# --------------------------------------------------------------------------


def test_el_exacto_vale_cien() -> None:
    assert peso_de(_candidato(), _objetivo()) == 100


def test_cada_desvio_cobra_lo_que_el_usuario_dijo() -> None:
    objetivo = _objetivo()
    assert peso_de(_candidato(scoring=18, passing=12, playmaking=7), objetivo) == 95
    assert peso_de(_candidato(scoring=17, passing=13, playmaking=7), objetivo) == 90
    assert peso_de(_candidato(edad=32), objetivo) == 85
    assert peso_de(_candidato(edad=30), objetivo) == 80
    assert peso_de(_candidato(scoring=18, passing=11, playmaking=7), objetivo) == 75
    assert peso_de(_candidato(scoring=16, passing=13, playmaking=7), objetivo) == 70
    assert peso_de(_candidato(edad=33), objetivo) == 65
    assert peso_de(_candidato(edad=29), objetivo) == 60


def test_lo_que_queda_fuera_del_suelo_no_devuelve_peso() -> None:
    objetivo = _objetivo()
    assert peso_de(_candidato(edad=35), objetivo) is None
    assert peso_de(_candidato(scoring=13, passing=13, playmaking=7), objetivo) is None
    assert peso_de(_candidato(scoring=18, passing=8, playmaking=7), objetivo) is None


def test_subir_una_habilidad_no_vale_aunque_bajarla_si() -> None:
    """La escalera sólo baja habilidades. Uno mejor que el tuyo no es
    comparable, y que el precio salga prudente es la consecuencia buscada."""
    assert peso_de(_candidato(scoring=19, passing=13, playmaking=7), _objetivo()) is None
    assert peso_de(_candidato(scoring=18, passing=14, playmaking=7), _objetivo()) is None


def test_moverse_en_dos_ejes_a_la_vez_no_encaja_en_ningun_escalon() -> None:
    """El hueco que el usuario aceptó a sabiendas: cada escalón clava los
    otros dos ejes, así que quien se aparta en dos cosas no aparece en
    ninguno, ni en la primera vuelta ni en la última."""
    objetivo = _objetivo()
    assert peso_de(_candidato(edad=32, scoring=18, passing=12, playmaking=7), objetivo) is None
    assert peso_de(_candidato(edad=32, scoring=17, passing=13, playmaking=7), objetivo) is None


def test_un_candidato_encaja_como_mucho_en_un_escalon() -> None:
    """Sostiene que no haya que elegir entre pesos: si dos escalones pudieran
    admitir al mismo, el peso dependería de cuál se mirase primero."""
    objetivo = _objetivo()
    for desvio in ESCALERA:
        cand = _candidato(
            edad=EDAD + desvio.edad,
            scoring=18 + desvio.primaria,
            passing=13 + desvio.secundaria,
            playmaking=7,
        )
        encajan = [
            d.peso
            for d in ESCALERA
            if (d.primaria, d.secundaria, d.edad)
            == (
                cand.primaria.nivel - objetivo.primaria.nivel,
                cand.secundaria.nivel - objetivo.secundaria.nivel,
                cand.edad - objetivo.edad,
            )
        ]
        assert len(encajan) == 1
        assert peso_de(cand, objetivo) == desvio.peso


def test_los_mismos_numeros_en_otras_habilidades_son_otro_jugador() -> None:
    """Un creador de juego con 18 y 13 de creación y pases tiene los números
    de Alberto, pero su 18 no es de anotación: lo que se paga por él no dice
    nada de lo que se paga por un delantero. Sin comparar el nombre valdría
    100%, que es el error más caro posible aquí.
    """
    otro = _candidato(scoring=1, playmaking=18, passing=13)
    assert otro.primaria.habilidad == "playmaking"
    assert peso_de(otro, _objetivo()) is None


def test_un_segundo_rasgo_distinto_con_los_mismos_numeros_no_sirve() -> None:
    """Misma primaria, mismo número en la segunda, pero la segunda es otra
    habilidad: un delantero que crea juego contra uno que pasa."""
    otro = _candidato(scoring=18, passing=1, playmaking=13)
    assert otro.secundaria.habilidad == "playmaking"
    assert peso_de(otro, _objetivo()) is None


# --------------------------------------------------------------------------
# Las 24 horas
# --------------------------------------------------------------------------


def test_una_subasta_que_cierra_pronto_cuenta_y_una_recien_abierta_no() -> None:
    """La regla que salva el número.

    En el mercado real aparecieron pujas de 50.000 junto a pujas de 18 M para
    jugadores casi iguales: no era el jugador, eran subastas sin precio mínimo
    recién abiertas. Cuanto más cerca del cierre, más se parece la puja a lo
    que se va a pagar.
    """
    assert cierra_pronto(_candidato_con_plazo(CIERRA_YA), AHORA) is True
    assert cierra_pronto(_candidato_con_plazo(CIERRA_TARDE), AHORA) is False


def test_el_corte_esta_donde_dijo_el_usuario() -> None:
    justo_dentro = AHORA + timedelta(hours=HORAS_PARA_QUE_CUENTE) - timedelta(minutes=1)
    justo_fuera = AHORA + timedelta(hours=HORAS_PARA_QUE_CUENTE) + timedelta(minutes=1)
    assert cierra_pronto(_candidato_con_plazo(_en_hora_ht(justo_dentro)), AHORA) is True
    assert cierra_pronto(_candidato_con_plazo(_en_hora_ht(justo_fuera)), AHORA) is False


def test_un_plazo_ya_vencido_cuenta_porque_es_lo_mas_parecido_a_una_venta() -> None:
    """El fichero avisa de que el plazo puede venir unas horas pasado. Esa
    puja es la última que alguien hizo de verdad: tirarla sería tirar el mejor
    dato que hay aquí."""
    assert cierra_pronto(_candidato_con_plazo("2026-10-04 08:00:00"), AHORA) is True


def test_un_plazo_que_no_se_entiende_no_cuenta() -> None:
    """En la duda, fuera: colar una subasta recién abierta hunde la media, y
    dejar fuera a uno bueno sólo cuesta seguir buscando."""
    assert cierra_pronto(_candidato_con_plazo(""), AHORA) is False
    assert cierra_pronto(_candidato_con_plazo("mañana"), AHORA) is False


def _candidato_con_plazo(plazo: str) -> Any:
    hecho = candidato_de(_fila(1, deadline=plazo))
    assert hecho is not None
    return hecho


def _en_hora_ht(momento: datetime) -> str:
    return momento.astimezone(ZoneInfo("Europe/Stockholm")).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# Leer una fila del mercado
# --------------------------------------------------------------------------


def test_una_fila_sin_jugador_o_sin_habilidades_no_es_un_candidato() -> None:
    assert candidato_de(_fila(0)) is None
    assert candidato_de({"skills": dict(SKILLS)}) is None
    assert candidato_de(_fila(1, ht_player_id=None)) is None
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
    a_mano = _fila(1, puja=1_000)
    del a_mano["has_bids"]
    deducido = candidato_de(a_mano)
    assert deducido is not None
    assert deducido.tiene_puja is True


def test_una_puja_negativa_se_lee_como_cero_y_no_cuenta() -> None:
    candidato = candidato_de(_fila(1, highest_bid=-5, has_bids=True))
    assert candidato is not None
    assert candidato.puja == 0
    assert _reune(_objetivo(), [_fila(1, highest_bid=-5, has_bids=True)]) == {}


def test_la_tercera_habilidad_viaja_aunque_no_compare() -> None:
    """Se enseña, para que se vea a quién se está comparando."""
    candidato = _candidato()
    assert candidato.terciaria.habilidad == "playmaking"
    assert candidato.terciaria.nivel == 7


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
    assert _reune(_objetivo(ht_player_id=4242), [_fila(4242)]) == {}


def test_el_que_nadie_pujo_no_cuenta() -> None:
    """Su precio pedido es una opinión del vendedor, no un dato del mercado."""
    objetivo = _objetivo()
    assert _reune(objetivo, [_fila(1, puja=0)]) == {}
    assert _reune(objetivo, [_fila(1, highest_bid=0, has_bids=False)]) == {}


def test_el_que_cierra_tarde_no_cuenta_por_mucho_que_se_parezca() -> None:
    reunidos = _reune(
        _objetivo(),
        [_fila(1, deadline=CIERRA_YA), _fila(2, deadline=CIERRA_TARDE)],
    )
    assert sorted(reunidos) == [1]


def test_el_lesionado_queda_fuera_pero_el_magullado_y_el_sano_entran() -> None:
    reunidos = _reune(
        _objetivo(),
        [
            _fila(1, injury_level=-1),
            _fila(2, injury_level=0),
            _fila(3, injury_level=1),
            _fila(4, injury_level=8),
        ],
    )
    assert sorted(reunidos) == [1, 2]


def test_el_que_no_se_parece_no_entra_aunque_la_busqueda_lo_devuelva() -> None:
    """La búsqueda del juego no sabe pedir «esta habilidad la más alta»: el
    filtro final es local."""
    portero = _fila(1, skills=_hab(keeper=18, defending=13, scoring=2))
    assert _reune(_objetivo(), [portero]) == {}


def test_cada_jugador_cuenta_una_vez() -> None:
    """Seis repeticiones de uno no son seis comparables."""
    reunidos = _reune(_objetivo(), [_fila(1), _fila(1), _fila(1)])
    assert len(reunidos) == 1
    assert reunidos[1].peso == 100


def test_el_orden_de_llegada_no_cambia_el_peso_de_nadie() -> None:
    objetivo = _objetivo()
    exacto = _fila(1)
    lejano = _fila(1, skills=_hab(scoring=18, passing=11, playmaking=7))
    assert _reune(objetivo, [exacto, lejano])[1].peso == 100
    assert _reune(objetivo, [lejano, exacto])[1].peso == 100


def test_lo_reunido_se_acumula_entre_busquedas_sin_tocar_lo_anterior() -> None:
    objetivo = _objetivo()
    primera = _reune(objetivo, [_fila(1)])
    segunda = _reune(objetivo, [_fila(2)], primera)
    assert sorted(segunda) == [1, 2]
    assert sorted(primera) == [1]


def test_una_lista_vacia_no_rompe_nada() -> None:
    assert _reune(_objetivo(), []) == {}


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
    semana» y enseñar los cinco: callarlos sería esconder el trabajo hecho."""
    cinco = estimar(_reunidos(*[(100, 4_000_000)] * (MINIMO_DE_COMPARABLES - 1)))
    assert cinco.precio is None
    assert cinco.suficiente is False
    assert len(cinco.comparables) == MINIMO_DE_COMPARABLES - 1


def test_con_seis_al_cien_la_ponderada_es_la_media_simple() -> None:
    pujas = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000, 6_000_000]
    seis = estimar(_reunidos(*[(100, puja) for puja in pujas]))
    assert seis.suficiente is True
    assert seis.precio == 3_500_000
    assert seis.peso_minimo == 100


def test_los_pesos_mueven_el_precio_y_se_puede_comprobar_a_mano() -> None:
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


def test_el_recorrido_entero_de_una_busqueda_que_junta_seis() -> None:
    """De punta a punta, con todo lo que se cae por el camino."""
    objetivo = _objetivo()
    reunidos = _reune(
        objetivo,
        [
            _fila(1, puja=4_500_000),
            _fila(2, puja=4_100_000),
            _fila(3, puja=9_000_000, highest_bid=0, has_bids=False),
            _fila(4, puja=9_000_000, injury_level=3),
            _fila(5, puja=9_000_000, deadline=CIERRA_TARDE),
        ],
    )
    assert estimar(reunidos).n == 2

    secundaria_abajo = _hab(scoring=18, passing=12, playmaking=7)
    reunidos = _reune(
        objetivo,
        [
            _fila(1, puja=4_500_000),  # el exacto, que ya estaba
            _fila(6, puja=3_900_000, skills=secundaria_abajo),
            _fila(7, puja=4_800_000, skills=secundaria_abajo),
            _fila(8, puja=9_900_000, skills=_hab(keeper=18, defending=13)),
        ],
        reunidos,
    )
    assert estimar(reunidos).n == 4

    reunidos = _reune(
        objetivo,
        [
            _fila(9, puja=4_300_000, skills=secundaria_abajo),
            _fila(10, puja=5_200_000, edad=32),
        ],
        reunidos,
    )
    estimacion = estimar(reunidos)
    assert estimacion.n == MINIMO_DE_COMPARABLES
    assert [c.peso for c in estimacion.comparables] == [100, 100, 95, 95, 95, 85]
    # 2.537.000.000 / 570, comprobable a mano.
    assert estimacion.precio == 4_450_877


# --------------------------------------------------------------------------
# Contra el parser de verdad
# --------------------------------------------------------------------------


def test_el_motor_habla_el_mismo_idioma_que_el_parser() -> None:
    """Sin esto, un cambio de nombre de campo en el parser dejaría el motor
    devolviendo cero comparables para siempre y sin fallar."""
    datos = get_parser("transfersearch")((FIXTURES / "transfersearch.xml").read_bytes())
    objetivo = objetivo_de(999, 24, _hab(passing=11, playmaking=9, winger=6))
    assert objetivo is not None
    # El fixture cierra el 2026-10-06 a las 21:30; se mira desde el mismo día.
    reunidos = recolectar(
        objetivo, datos["results"], ahora=datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
    )
    assert sorted(reunidos) == [491002001]
    comparable = reunidos[491002001]
    assert comparable.peso == 100
    assert comparable.candidato.nombre == "Aurelio Barrantes"
    assert comparable.candidato.puja == 4_500_000
    assert comparable.candidato.liga_del_vendedor == 92
    assert estimar(reunidos).suficiente is False


def test_el_mismo_fixture_dos_dias_antes_no_cuenta_a_nadie() -> None:
    """Mismo mercado, otro momento: a la subasta le quedan más de un día."""
    datos = get_parser("transfersearch")((FIXTURES / "transfersearch.xml").read_bytes())
    objetivo = objetivo_de(999, 24, _hab(passing=11, playmaking=9, winger=6))
    assert objetivo is not None
    temprano = recolectar(
        objetivo, datos["results"], ahora=datetime(2026, 10, 4, 10, 0, tzinfo=UTC)
    )
    assert temprano == {}


def test_una_busqueda_sin_resultados_no_reune_a_nadie() -> None:
    datos = get_parser("transfersearch")((FIXTURES / "chpperror.xml").read_bytes())
    assert _reune(_objetivo(), datos["results"]) == {}


# --------------------------------------------------------------------------
# Cuándo se corre
# --------------------------------------------------------------------------

HT = ZoneInfo("Europe/Stockholm")
BOGOTA = ZoneInfo("America/Bogota")


def _ht(texto: str) -> datetime:
    return datetime.fromisoformat(texto).replace(tzinfo=HT)


def test_el_viernes_antes_de_las_ocho_la_frontera_es_la_de_hace_una_semana() -> None:
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
    """El desfase sale de la base de zonas, no de una constante."""
    assert frontera_semanal(_ht("2026-01-09 21:00:00")).hour == 19
    assert frontera_semanal(_ht("2026-07-10 21:00:00")).hour == 18


def test_la_zona_entra_por_parametro() -> None:
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
    sabado = _ht("2026-10-10 09:00:00")
    assert toca_buscar(None, sabado) is True
    hecha = sabado
    assert toca_buscar(hecha, _ht("2026-10-11 10:00:00")) is False
    assert toca_buscar(hecha, _ht("2026-10-14 23:59:00")) is False
    assert toca_buscar(hecha, _ht("2026-10-16 19:59:00")) is False
    assert toca_buscar(hecha, _ht("2026-10-16 20:00:00")) is True
