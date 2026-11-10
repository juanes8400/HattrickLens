"""El diagrama de Venn de los dos entrenamientos juveniles.

Modelo dictado por el usuario el 2026-08-23: la interseccion primero --doble
racion, los mejores del principal--, luego lo que solo entrena el principal
siguiendo esa misma cola, luego lo que solo entrena el secundario con los que
sobraron y ordenados por la habilidad secundaria, y al final las plazas que no
entrenan nada.
"""

import pytest

from app.domain.engines.youth_skill_score import SLOT_CUPOS, PlayerNote
from app.domain.engines.youth_training_plan import (
    ENTRENAMIENTOS,
    PUESTOS_DE_UN_BANQUILLO,
    REGION_AMBOS,
    REGION_SIN_ENTRENAMIENTO,
    REGION_SOLO_PRINCIPAL,
    REGION_SOLO_SECUNDARIA,
    _relleno_con_criterio,
    _reparte_por_region,
    cupos_de,
    factor_secundario,
    youth_training_plan,
)


def _cola(*nombres: str) -> list[PlayerNote]:
    return [
        PlayerNote(
            name=n, note=8, bucket="excelente", leaves_soon=False, max_reached=False, priority=1
        )
        for n in nombres
    ]


@pytest.mark.parametrize("skill", sorted(SLOT_CUPOS))
def test_la_forma_normal_cuadra_con_la_tabla_de_plazas(skill: str) -> None:
    """Los puestos de la variante normal y las cuentas no pueden divergir.

    2026-08-26: las dos cifras dejaron de ser la misma. `cupos_de` dice a que
    puestos LLEGA el entrenamiento --catorce posibles-- y `SLOT_CUPOS` a
    cuantos se entrena de verdad, que nunca pasa de once porque once juegan.
    Para todo lo que no llega a los seis puestos siguen coincidiendo.
    """
    enteros, medios = SLOT_CUPOS[skill]
    assert min(len(cupos_de(skill)), 11) == enteros + medios


def test_balon_parado_llega_a_TODOS_los_puestos() -> None:
    """Entrena a los once que juegan, sean quienes sean --dicho por el usuario
    el 2026-08-26--.

    Aqui habia un tope a once dentro de `cupos_de` que recortaba por orden de
    lista, y con raciones iguales el corte caia sobre los ultimos de
    `PUESTOS_DE_UN_ONCE`: «Balón parado» perdia los DOS extremos y uno de los
    dos laterales. La pantalla llegaba a decir "Así 1 recibe las dos cosas"
    cuando eran cuatro.
    """
    for codigo in ("set_pieces", "scoring_set_pieces"):
        puestos = {c.puesto for c in cupos_de(codigo)}
        assert puestos == {
            "keeper",
            "central_defender",
            "wingback",
            "inner_midfield",
            "winger",
            "forward",
        }, codigo


def test_el_once_lo_topa_la_ALINEACION_no_el_entrenamiento() -> None:
    """El tope vive donde debe: por muchos puestos que alcance un
    entrenamiento, al once no entran mas de once."""
    jugadores = _cola(*[f"J{i:02}" for i in range(1, 19)])
    for codigo in ENTRENAMIENTOS:
        plan = youth_training_plan(codigo, codigo, jugadores, list(jugadores))
        assert len(plan.asignaciones) <= 11, codigo


def test_lateral_con_balon_parado_da_CUATRO_dobles() -> None:
    """El caso que lo destapo: «Lateral» son dos extremos y dos laterales, y
    «Anotación y balón parado» llega a todos, asi que los cuatro reciben las
    dos cosas. Antes salia 1."""
    jugadores = _cola(*[f"J{i:02}" for i in range(1, 19)])
    plan = youth_training_plan("winger", "scoring_set_pieces", jugadores, list(jugadores))
    assert plan.con_doble == 4
    assert len(plan.asignaciones) == 11


def test_los_ritmos_son_los_que_dicto_el_usuario() -> None:
    """La tabla del 2026-08-24, comprobada valor a valor."""
    r = lambda c: ENTRENAMIENTOS[c].ritmos  # noqa: E731
    assert r("keeper") == {"keeper": 100}
    assert r("defending") == {"central_defender": 100, "wingback": 100}
    assert r("playmaking") == {"inner_midfield": 100, "winger": 50}
    assert r("scoring") == {"forward": 100}
    assert r("winger") == {"winger": 100, "wingback": 50}
    assert r("winger_forwards") == {"winger": 60, "forward": 60}
    assert set(r("passing")) == {"inner_midfield", "winger", "forward"}
    assert set(r("passing").values()) == {100}
    assert r("passing_defenders") == {
        "central_defender": 80,
        "wingback": 80,
        "inner_midfield": 80,
        "winger": 80,
    }
    assert r("defending_wide") == {
        "keeper": 80,
        "central_defender": 80,
        "wingback": 80,
        "inner_midfield": 80,
        "winger": 80,
    }
    assert r("set_pieces")["keeper"] == 125, "el portero pasa de 100 aposta"
    assert set(r("set_pieces").values()) == {125, 100}
    # En Individual esto es solo COBERTURA. La velocidad real permanece en
    # cada linea de habilidad y nunca se colapsa en un valor esperado.
    assert set(r("individual")) == {
        "keeper",
        "central_defender",
        "wingback",
        "inner_midfield",
        "winger",
        "forward",
    }
    assert set(r("individual").values()) == {100}
    # El unico que sube dos habilidades, a ritmos distintos.
    dos = ENTRENAMIENTOS["scoring_set_pieces"]
    assert dos.tambien_sube == "set_pieces"
    assert set(dos.ritmos.values()) == {60}
    assert set((dos.ritmos_de_la_otra or {}).values()) == {40}
    assert dos.ritmo("keeper") == 60
    assert dos.ritmo("keeper", "set_pieces") == 40


def test_el_secundario_rinde_dos_tercios_y_un_tercio_si_lo_repites() -> None:
    assert factor_secundario("winger", "passing") == pytest.approx(2 / 3)
    # Misma habilidad por dos caminos distintos NO es repetir.
    assert factor_secundario("passing", "passing_defenders") == pytest.approx(2 / 3)
    assert factor_secundario("winger", "winger") == pytest.approx(1 / 3)


def test_los_medios_van_al_final_de_su_cola() -> None:
    raciones = [c.racion for c in cupos_de("winger")]
    assert raciones == [100, 100, 50, 50]


def test_lateral_y_pases_se_cruzan_en_los_extremos() -> None:
    """El ejemplo del usuario, con sus numeros."""
    ambos, solo_a, solo_b = _reparte_por_region("winger", "passing")
    assert [c.puesto for c in ambos] == ["winger", "winger"]
    assert [c.puesto for c in solo_a] == ["wingback", "wingback"]
    assert sorted(c.puesto for c in solo_b) == [
        "forward",
        "forward",
        "forward",
        "inner_midfield",
        "inner_midfield",
        "inner_midfield",
    ]


def test_a_igualdad_los_del_principal_van_a_la_interseccion() -> None:
    """Desde el 2026-11-09 la doble mira las dos colas (ver la prueba de
    Ireneo, más abajo), pero a igualdad completa sigue mandando el principal."""
    principal = _cola("A", "B", "C", "D")
    plan = youth_training_plan("winger", "passing", principal, _cola("Z"))
    dobles = [a.player for a in plan.asignaciones if a.recibe_doble]
    assert dobles == ["A", "B"], "la doble racion no fue para los dos primeros"
    assert plan.con_doble == 2


def _nota_de(
    nombre: str, *, techo: int | None, nivel: int | None, dias: int, prioridad: int
) -> PlayerNote:
    return PlayerNote(
        name=nombre,
        note=techo,
        bucket="",
        leaves_soon=False,
        max_reached=False,
        priority=prioridad,
        age_days_total=dias,
        current=nivel,
        maximum=techo,
    )


def test_en_la_doble_cuenta_TAMBIEN_lo_que_necesita_del_secundario() -> None:
    """El caso del usuario, 2026-11-09, con Pases + Lateral (extremos y
    delanteros): «me puso a Adolfo Velásquez en vez de Ireneo Rodríguez como
    Lateral, a pesar de que el Lateral de Ireneo le falta por completarse».

    Las plazas que reciben los dos entrenamientos se llenaban con la cola de
    Pases y nada más. Los dos tenían tope 5 en Pases, empataban, y desempataba
    la edad: Adolfo es más joven. El Lateral de Ireneo --7/7 sin la marca de
    terminado-- no pesaba nada. Decisión del usuario: «cuentan los dos por
    igual», cada chico vale por su mejor peldaño entre los dos.
    """
    # Pases: los dos con tope 5, peldaño «insuficiente». Adolfo, más joven.
    pases = [
        _nota_de("Adolfo Velásquez", techo=5, nivel=None, dias=15 * 112 + 105, prioridad=8),
        _nota_de("Ireneo Rodríguez", techo=5, nivel=None, dias=16 * 112 + 111, prioridad=8),
    ]
    # Lateral: Ireneo 7/7 sin terminar, peldaño «bueno»; Adolfo 5/?, sin nota.
    lateral = [
        _nota_de("Ireneo Rodríguez", techo=7, nivel=7, dias=16 * 112 + 111, prioridad=3),
        _nota_de("Adolfo Velásquez", techo=None, nivel=5, dias=15 * 112 + 105, prioridad=7),
    ]
    plan = youth_training_plan("passing", "winger_forwards", pases, lateral, plazas=1)

    (unica,) = plan.asignaciones
    assert unica.region == REGION_AMBOS
    assert unica.player == "Ireneo Rodríguez"
    # Y se dice por qué entró: por su Lateral, no por su Pases.
    assert unica.elegido_por == "winger_forwards"
    assert (unica.current, unica.maximum, unica.max_reached) == (7, 7, False)


@pytest.mark.parametrize(
    ("principal", "secundaria"),
    [
        ("playmaking", "winger"),
        ("defending", "passing_defenders"),
        ("scoring", "passing"),
        ("winger", "passing"),
    ],
)
def test_la_doble_mira_las_dos_colas_en_CUALQUIER_par(principal: str, secundaria: str) -> None:
    """No es una regla de Pases + Lateral: vale para todo par que tenga
    plazas dobles. Quien sólo destaca en el secundario entra antes que quien
    sólo es flojo en el primario."""
    flojo = [_nota_de("Flojo", techo=5, nivel=None, dias=1000, prioridad=8)]
    necesita = [_nota_de("Necesita", techo=7, nivel=7, dias=1800, prioridad=3)]
    plan = youth_training_plan(principal, secundaria, flojo, necesita, plazas=1)
    (unica,) = plan.asignaciones
    assert unica.region == REGION_AMBOS
    assert unica.player == "Necesita"


def test_con_INDIVIDUAL_la_doble_sigue_la_cola_de_descubrimiento() -> None:
    """La cola de «Individual» va por topes ocultos, no por peldaños, y el
    peldaño de sus notas no significa nada: no se mezcla."""
    descubrimiento = [
        _nota_de("Tapado", techo=None, nivel=None, dias=1800, prioridad=9),
        _nota_de("Leido", techo=8, nivel=6, dias=1000, prioridad=1),
    ]
    otra = [_nota_de("Leido", techo=8, nivel=6, dias=1000, prioridad=1)]
    plan = youth_training_plan("individual", "winger", descubrimiento, otra, plazas=1)
    assert [a.player for a in plan.asignaciones] == ["Tapado"]


def test_en_la_doble_tocar_techo_en_UNA_no_basta_para_quedarse_fuera() -> None:
    """La plaza doble le sigue dando la otra. Antes bastaba con tocar techo en
    cualquiera de las dos para no poder entrar."""
    lateral = [_nota_de("Ireneo Rodríguez", techo=7, nivel=7, dias=1900, prioridad=3)]
    plan = youth_training_plan(
        "passing",
        "winger_forwards",
        [],
        lateral,
        tope_principal={"Ireneo Rodríguez"},
        plazas=1,
    )
    assert [a.player for a in plan.asignaciones] == ["Ireneo Rodríguez"]
    assert plan.asignaciones[0].region == REGION_AMBOS


def test_solo_principal_sigue_bajando_por_la_misma_cola() -> None:
    principal = _cola("A", "B", "C", "D")
    plan = youth_training_plan("winger", "passing", principal, _cola("Z"))
    solo_p = [a.player for a in plan.asignaciones if a.region == REGION_SOLO_PRINCIPAL]
    assert solo_p == ["C", "D"], "no continuo por la cola del principal"


def test_solo_secundaria_usa_su_propia_cola_con_los_que_sobraron() -> None:
    """Quien no valia para lo principal puede valer para lo otro."""
    principal = _cola("A", "B", "C", "D")
    # En la cola de la secundaria mandan otros, y los cuatro de arriba van al
    # final: ya estan colocados, asi que no deben repetirse.
    secundaria = _cola("E", "F", "G", "A", "B", "C", "D")
    plan = youth_training_plan("winger", "passing", principal, secundaria)
    solo_s = [a.player for a in plan.asignaciones if a.region == REGION_SOLO_SECUNDARIA]
    assert solo_s[:3] == ["E", "F", "G"]
    assert len(set(a.player for a in plan.asignaciones)) == len(plan.asignaciones), (
        "alguien quedo repetido en dos plazas"
    )


def test_un_puesto_entero_en_uno_y_medio_en_otro_guarda_las_dos_raciones() -> None:
    """«Lateral» pone los laterales a media; «Defensa» los pone enteros."""
    plan = youth_training_plan(
        "winger",
        "defending",
        _cola("A", "B", "C", "D"),
        _cola("Z"),
    )
    laterales = [a for a in plan.asignaciones if a.puesto == "wingback"]
    assert laterales, "los laterales tenian que cruzarse"
    # 50 de Lateral por ser lateral, y de Defensa 100 rebajado a dos tercios
    # por ir en el hueco secundario: 66,7.
    assert all(a.racion_principal == 50 for a in laterales)
    assert all(a.racion_secundaria == pytest.approx(66.7) for a in laterales)


def test_no_se_reparten_mas_de_once_plazas() -> None:
    todos = [f"J{i}" for i in range(1, 20)]
    plan = youth_training_plan("set_pieces", "passing", _cola(*todos), _cola("Z"))
    assert len(plan.asignaciones) == 11
    assert all(a.player for a in plan.fuera), "el banquillo necesita los mismos datos"

    # Nadie en dos sitios a la vez, y nadie perdido por el camino.
    nombres = [a.player for a in plan.asignaciones + plan.fuera]
    assert len(nombres) == len(set(nombres))
    assert set(todos) <= set(nombres)

    # El banquillo tiene tantas plazas como puestos, ni una mas.
    con_puesto = [a for a in plan.fuera if a.puesto]
    assert len(con_puesto) <= len(PUESTOS_DE_UN_BANQUILLO)


def test_los_que_sobran_ocupan_plazas_sin_entrenamiento() -> None:
    todos = _cola(*[f"J{i}" for i in range(1, 12)])
    plan = youth_training_plan("keeper", "scoring", todos, todos)
    sin = [a for a in plan.asignaciones if a.region == REGION_SIN_ENTRENAMIENTO]
    assert len(sin) == 11 - 1 - 3, "portero + tres delanteros entrenan; el resto no"
    assert all(a.racion_principal == 0 and a.racion_secundaria == 0 for a in sin)


def test_una_plaza_que_entrena_no_se_queda_vacia_habiendo_gente() -> None:
    """Si la cola de esa region se agota, entra quien quede libre."""
    plan = youth_training_plan(
        "keeper",
        "scoring",
        _cola("A", "B", "C", "D"),
        _cola("A"),
    )
    delanteros = [a for a in plan.asignaciones if a.puesto == "forward"]
    assert len(delanteros) == 3, "quedaron plazas de anotacion sin repartir"


def test_el_mismo_entrenamiento_dos_veces_es_todo_interseccion() -> None:
    plan = youth_training_plan(
        "scoring",
        "scoring",
        _cola("A", "B", "C", "D"),
        _cola("A", "B", "C", "D"),
    )
    dobles = [a for a in plan.asignaciones if a.region == REGION_AMBOS]
    assert len(dobles) == 3
    assert all(a.recibe_doble for a in dobles)


def test_nadie_ocupa_dos_plazas() -> None:
    plan = youth_training_plan(
        "playmaking",
        "passing",
        _cola(*[f"J{i}" for i in range(1, 15)]),
        _cola(*[f"J{i}" for i in range(14, 0, -1)]),
    )
    nombres = [a.player for a in plan.asignaciones]
    assert len(nombres) == len(set(nombres))


def test_el_que_toco_techo_no_ocupa_una_plaza_de_esa_habilidad() -> None:
    """La trampa era el repuesto: al tirar de la reserva para no dejar una
    plaza vacia se colaba alguien tapado justo en esa habilidad."""
    principal = _cola("A", "B")  # cola corta a proposito
    secundaria = _cola("Tapado", "C", "D", "E", "F", "G", "H")
    plan = youth_training_plan(
        "winger",
        "passing",
        principal,
        secundaria,
        tope_principal={"Tapado"},
    )
    en_principal = [
        a.player for a in plan.asignaciones if a.region in (REGION_AMBOS, REGION_SOLO_PRINCIPAL)
    ]
    assert "Tapado" not in en_principal, "un tapado entro a entrenar lo que ya tiene lleno"
    # Y si puede recibir la secundaria, que la reciba: no esta castigado.
    en_secundaria = [a.player for a in plan.asignaciones if a.region == REGION_SOLO_SECUNDARIA]
    assert "Tapado" in en_secundaria


def test_tapado_en_las_dos_no_entra_en_ninguna_plaza_que_entrene() -> None:
    plan = youth_training_plan(
        "winger",
        "passing",
        _cola("A"),
        _cola("Tapado", "B", "C", "D"),
        tope_principal={"Tapado"},
        tope_secundaria={"Tapado"},
    )
    entrenan = [a.player for a in plan.asignaciones if a.region != REGION_SIN_ENTRENAMIENTO]
    assert "Tapado" not in entrenan


# ── La variante de la secundaria se elige por el solape ────────────────────


def test_el_caso_del_usuario_pases_a_secas_no_toca_a_ningun_defensa() -> None:
    """Defensa arriba: «Pases» deja la interseccion VACIA."""
    from app.domain.engines.youth_training_plan import _reparte_por_region

    ambos, _, _ = _reparte_por_region("defending", "passing")
    assert ambos == [], "Pases no deberia tocar a ningun defensa"


def test_con_defensa_arriba_se_sugiere_la_variante_de_defensas() -> None:
    from app.domain.engines.youth_training_plan import mejor_variante

    assert mejor_variante("defending", "passing") == "passing_defenders"


def test_esa_variante_deja_cinco_recibiendo_las_dos_cosas() -> None:
    from app.domain.engines.youth_training_plan import _reparte_por_region

    ambos, _, _ = _reparte_por_region("defending", "passing_defenders")
    assert len(ambos) == 5, "los cinco defensas tenian que recibir doble"


def test_a_igualdad_de_solape_gana_la_forma_normal() -> None:
    """Sin motivo para complicarse, no se complica."""
    from app.domain.engines.youth_training_plan import mejor_variante

    assert mejor_variante("playmaking", "passing") == "passing"


def test_la_habilidad_a_secas_sigue_valiendo_como_clave() -> None:
    """Quien pida «passing» recibe la forma normal, no un error."""
    assert len(cupos_de("passing")) == len(cupos_de("passing"))
    assert [c.puesto for c in cupos_de("winger")] == [
        "winger",
        "winger",
        "wingback",
        "wingback",
    ]


def test_cuantos_de_los_que_reciben_doble_van_a_ciegas() -> None:
    """En esta academia casi todo esta sin revelar; la cancha debe decirlo."""

    def note(nombre: str, current, maximum, tope=False) -> PlayerNote:
        return PlayerNote(
            name=nombre,
            note=8,
            bucket="excelente",
            leaves_soon=False,
            max_reached=tope,
            priority=1,
            current=current,
            maximum=maximum,
        )

    cola = [
        note("Ana", None, None),  # en blanco
        note("Bea", None, None),  # en blanco
        note("Cid", 5, None),  # sabe el nivel: no es a ciegas
        note("Dan", None, 7),  # sabe el techo: tampoco
        note("Eva", None, None, tope=True),  # se sabe que no sube
    ]
    plan = youth_training_plan(
        "defending",
        "passing_defenders",
        cola,
        cola,
        tope_principal=set(),
        tope_secundaria=set(),
    )
    dobles = [a.player for a in plan.asignaciones if a.recibe_doble]
    esperado = sum(1 for n in ("Ana", "Bea") if n in dobles)
    assert plan.doble_a_ciegas == esperado


def test_la_cobertura_del_ojeador_cuenta_las_tres_formas_de_saber() -> None:
    """Nivel, techo o «ya no sube»: las tres son informacion, el hueco no."""
    from types import SimpleNamespace

    from app.api.v1.endpoints.academy import _cobertura_del_ojeador
    from app.domain.engines.youth_skill_score import SKILLS

    def note(nombre, current=None, maximum=None, tope=False):
        return PlayerNote(
            name=nombre,
            note=None,
            bucket="",
            leaves_soon=False,
            max_reached=tope,
            current=current,
            maximum=maximum,
        )

    # Un jugador en blanco en las siete, y otro con una sola lectura.
    filas = [
        SimpleNamespace(
            players=[note("Blanco"), note("Algo", current=5 if s == "keeper" else None)],
            at_max=[],
        )
        for s in SKILLS
    ]
    cobertura = _cobertura_del_ojeador(filas)
    assert cobertura["total"] == 2 * len(SKILLS)
    assert cobertura["known"] == 1
    assert cobertura["blankPlayers"] == ["Blanco"], "«Algo» tiene una lectura"


def test_el_banquillo_se_llena_con_el_mismo_criterio_que_el_once() -> None:
    """Pedido el 2026-08-24: primero los puestos que reciben los dos, luego
    los del principal, luego los del secundario, y al final los que nada.

    Un suplente que entra recibe lo que toque su puesto, asi que elegirlos
    por otro orden desperdicia esa entrada.
    """
    todos = _cola(*[f"J{i}" for i in range(1, 20)])
    plan = youth_training_plan("defending", "passing_defenders", todos, todos)

    ORDEN = [REGION_AMBOS, REGION_SOLO_PRINCIPAL, REGION_SOLO_SECUNDARIA, REGION_SIN_ENTRENAMIENTO]
    suplentes = [a for a in plan.fuera if a.puesto]
    puestos = [ORDEN.index(a.region) for a in suplentes]
    assert puestos == sorted(puestos), "el banquillo salio desordenado"
    assert any(a.region == REGION_AMBOS for a in suplentes), (
        "con estos dos entrenamientos hay puestos que reciben los dos"
    )


def test_un_suplente_lleva_la_racion_de_su_puesto() -> None:
    """No es adorno: es lo que recibiria si entra al partido."""
    todos = _cola(*[f"J{i}" for i in range(1, 20)])
    plan = youth_training_plan("defending", "passing_defenders", todos, todos)
    for a in plan.fuera:
        if a.region == REGION_AMBOS:
            assert a.racion_principal > 0 and a.racion_secundaria > 0
        elif a.region == REGION_SIN_ENTRENAMIENTO:
            assert a.racion_principal == 0 and a.racion_secundaria == 0


def test_la_celda_secundaria_ensena_el_producto() -> None:
    """El ejemplo del usuario: Portería de principal, Jugadas de secundario.

    A un extremo, Jugadas le da 50; por ir en el hueco secundario se queda en
    dos tercios de eso. 67% x 50% = 33,3.
    """
    todos = _cola(*[f"J{i}" for i in range(1, 20)])
    plan = youth_training_plan("keeper", "playmaking", todos, todos)
    extremos = [a for a in plan.asignaciones if a.puesto == "winger"]
    assert extremos, "Jugadas alcanza a los extremos"
    assert all(a.racion_secundaria == pytest.approx(33.3) for a in extremos)

    medios = [a for a in plan.asignaciones if a.puesto == "inner_midfield"]
    assert all(a.racion_secundaria == pytest.approx(66.7) for a in medios)

    # El principal NO se rebaja.
    porteros = [a for a in plan.asignaciones if a.puesto == "keeper"]
    assert all(a.racion_principal == 100 for a in porteros)


def test_repetir_el_mismo_entrenamiento_deja_un_total_de_133_3() -> None:
    todos = _cola(*[f"J{i}" for i in range(1, 20)])
    repetido = youth_training_plan("passing", "passing", todos, todos)
    medios = [a for a in repetido.asignaciones if a.puesto == "inner_midfield"]
    assert all(a.racion_secundaria == pytest.approx(33.3) for a in medios)
    assert all(a.racion_principal + a.racion_secundaria == pytest.approx(133.3) for a in medios)

    # Dos caminos distintos a la misma habilidad NO son repetir.
    distinto = youth_training_plan("passing", "passing_defenders", todos, todos)
    medios = [a for a in distinto.asignaciones if a.puesto == "inner_midfield"]
    assert all(a.racion_secundaria == pytest.approx(53.3) for a in medios), "80 x 2/3"


def test_individual_repetido_tambien_deja_un_total_de_133_3() -> None:
    todos = _cola(*[f"J{i}" for i in range(1, 20)])
    repetido = youth_training_plan("individual", "individual", todos, todos)

    assert repetido.asignaciones
    assert all(a.racion_principal == 100 for a in repetido.asignaciones)
    assert all(a.racion_secundaria == pytest.approx(33.3) for a in repetido.asignaciones)
    assert all(
        a.racion_principal + a.racion_secundaria == pytest.approx(133.3)
        for a in repetido.asignaciones
    )


def test_al_reubicar_para_descubrir_la_edad_viaja_con_el_chico() -> None:
    """Al cambiar de silla, lo que es del CHICO se va con él.

    2026-09-01, visto por el usuario: «Nicolás Granados aparece con 15 años y
    tiene 16, casi 17». `_recoloca_para_descubrir` reescribía SÓLO el nombre
    de la plaza, con el argumento de que el resto de la fila describe la
    plaza. Eso vale para el puesto, la región y las raciones; no vale para la
    edad, el HTMS28 ni los niveles, que describen a la persona. Cada
    reubicación dejaba un nombre con la edad del ocupante anterior, y como el
    reparto es un emparejamiento óptimo salían ciclos: siete canteranos con la
    edad de otro, encadenados.

    Sólo ocurría con «Individual», que es el único entrenamiento que reubica.
    """
    from dataclasses import replace

    from app.domain.engines.youth_training_plan import Asignacion

    ana = Asignacion(
        player="Ana",
        puesto="keeper",
        region=REGION_AMBOS,
        racion_principal=1.0,
        racion_secundaria=0.0,
        age_days_total=1902,
        htms28_min=1700,
        htms28_max=2800,
    )
    # Lo que hacía antes: cambiar el nombre y quedarse el resto de la silla.
    heredado = replace(ana, player="Beto")
    assert heredado.age_days_total == 1902, "la fila conserva la edad del anterior"

    # Lo que hace ahora el endpoint: mover con el nombre lo que es suyo.
    beto = Asignacion(
        player="Beto",
        puesto="",
        region=REGION_SIN_ENTRENAMIENTO,
        racion_principal=0.0,
        racion_secundaria=0.0,
        age_days_total=1728,
        htms28_min=1600,
        htms28_max=2700,
    )
    suyo = {
        "peldano": beto.peldano,
        "age_days_total": beto.age_days_total,
        "htms28_min": beto.htms28_min,
        "htms28_max": beto.htms28_max,
        "current": beto.current,
        "maximum": beto.maximum,
        "max_reached": beto.max_reached,
    }
    correcto = replace(ana, player="Beto", **suyo)
    assert correcto.age_days_total == 1728, "la edad es la de Beto"
    assert correcto.htms28_max == 2700
    # Y la plaza no se mueve: eso sí es de la silla.
    assert correcto.puesto == "keeper"
    assert correcto.racion_principal == 1.0


# ---------------------------------------------------------------------------
# EL ONCE SE COMPLETA, Y LAS PLAZAS SIN ENTRENAMIENTO TIENEN CRITERIO
# (2026-11-04, pedido del usuario: «la formacion de juveniles que sugiere no
# tiene al menos 11; se sugiere rellenar al menos con jugadores a los que pueda
# descubrirseles la habilidad que, aunque no se este entrenando, sea relevante
# para la posicion. Luego por edad»).
# ---------------------------------------------------------------------------


def _nota(nombre: str, *, dias: int = 1000) -> PlayerNote:
    return PlayerNote(
        name=nombre,
        note=8,
        bucket="excelente",
        leaves_soon=False,
        max_reached=False,
        priority=1,
        age_days_total=dias,
    )


def test_el_once_llega_a_once_tirando_de_la_cantera() -> None:
    """Las colas traen a los de SU habilidad; la cantera es todos.

    Antes el relleno salia de `cola_principal` y de nadie mas, asi que un
    entrenamiento con cuatro candidatos daba un once de cuatro jugadores y
    siete sillas vacias. No faltaban chicos: faltaba mirarlos.
    """
    cola = _cola("A", "B", "C", "D")
    resto = [_nota(f"J{i}") for i in range(10)]

    sin_cantera = youth_training_plan("defending", "winger", cola, list(cola))
    con_cantera = youth_training_plan("defending", "winger", cola, list(cola), cantera=resto)

    assert len(sin_cantera.asignaciones) == 4, "el fallo que se arregla"
    assert len(con_cantera.asignaciones) == 11
    # Y nadie sale dos veces.
    nombres = [a.player for a in con_cantera.asignaciones]
    assert len(set(nombres)) == len(nombres)


TODAS_TAPADAS = frozenset({"keeper", "defending", "playmaking", "winger", "passing", "scoring"})


def _quien_entra(candidatos, sin_revelar, *, plazas=("forward",)):
    """A quien le toca la UNICA plaza libre, que es donde se ve la regla.

    Se prueba contra `_relleno_con_criterio` y no contra el plan entero a
    proposito: el emparejamiento devuelve las parejas EN ORDEN DE PLAZA, no de
    calidad, asi que mirar quien sale primero en el once no dice quien gano
    --dice que silla se dibujo antes--. Con una sola plaza no hay ambiguedad.
    """
    pares = _relleno_con_criterio(list(plazas), candidatos, sin_revelar, "defending", "winger")
    return pares[0][0].name


def test_la_plaza_sin_entrenamiento_va_a_quien_puede_destaparle_algo() -> None:
    """Primero lo que el puesto puede iluminar, y solo despues la edad.

    `Leido` esta entero descubierto, asi que la plaza se desperdiciaria en el.
    Se le pone MAS JOVEN a proposito: si la edad mandara por encima del
    descubrimiento ganaria el, y no debe.
    """
    candidatos = [_nota("Leido", dias=200), _nota("Tapado", dias=1800)]
    quien = _quien_entra(candidatos, {"Tapado": TODAS_TAPADAS, "Leido": frozenset()})
    assert quien == "Tapado"


def test_entre_dos_que_destapan_lo_mismo_manda_la_edad() -> None:
    """La segunda mitad de la regla, con el descubrimiento empatado a proposito."""
    candidatos = [_nota("Viejo", dias=1800), _nota("Joven", dias=300)]
    quien = _quien_entra(candidatos, {"Viejo": TODAS_TAPADAS, "Joven": TODAS_TAPADAS})
    assert quien == "Joven"


def test_lo_que_ya_entrena_el_plan_no_cuenta_como_descubrimiento() -> None:
    """Si el entrenamiento ya va a iluminar esa habilidad, la plaza no aporta.

    `SoloDefensa` tiene tapada justo la que entrena el principal, asi que
    destaparla por puesto no anade nada nuevo; `OtraCosa` tiene tapada una que
    ningun entrenamiento toca y gana la plaza aunque sea mucho mayor.
    """
    candidatos = [_nota("SoloDefensa", dias=300), _nota("OtraCosa", dias=1800)]
    quien = _quien_entra(
        candidatos,
        {
            "SoloDefensa": frozenset({"defending"}),
            "OtraCosa": frozenset({"scoring", "passing"}),
        },
    )
    assert quien == "OtraCosa"


def test_sin_saber_que_esta_tapado_se_reparte_como_siempre() -> None:
    """El respaldo: sin `sin_revelar` no hay con que juzgar, y manda el orden."""
    candidatos = [_nota("Primero"), _nota("Segundo")]
    pares = _relleno_con_criterio(["forward"], candidatos, None, "defending", "winger")
    assert pares[0][0].name == "Primero"
