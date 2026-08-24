"""El diagrama de Venn de los dos entrenamientos juveniles.

Modelo dictado por el usuario el 2026-08-23: la interseccion primero --doble
racion, los mejores del principal--, luego lo que solo entrena el principal
siguiendo esa misma cola, luego lo que solo entrena el secundario con los que
sobraron y ordenados por la habilidad secundaria, y al final las plazas que no
entrenan nada.
"""
import pytest

from app.domain.engines.youth_skill_score import PlayerNote
from app.domain.engines.youth_training_plan import (
    ENTRENAMIENTOS,
    REGION_AMBOS,
    REGION_SIN_ENTRENAMIENTO,
    REGION_SOLO_PRINCIPAL,
    REGION_SOLO_SECUNDARIA,
    PUESTOS_DE_UN_BANQUILLO,
    _reparte_por_region,
    cupos_de,
    youth_training_plan,
)
from app.domain.engines.youth_skill_score import SLOT_CUPOS


def _cola(*nombres: str) -> list[PlayerNote]:
    return [
        PlayerNote(name=n, note=8, bucket="excelente", leaves_soon=False,
                   max_reached=False, priority=1)
        for n in nombres
    ]


@pytest.mark.parametrize("skill", sorted(SLOT_CUPOS))
def test_la_forma_normal_cuadra_con_la_tabla_de_plazas(skill: str) -> None:
    """Los puestos de la variante normal y las cuentas no pueden divergir."""
    enteros, medios = SLOT_CUPOS[skill]
    e = ENTRENAMIENTOS[skill]
    assert (len(e.enteros), len(e.medios)) == (enteros, medios)
    assert len(cupos_de(skill)) == enteros + medios


def test_los_medios_van_al_final_de_su_cola() -> None:
    raciones = [c.racion for c in cupos_de("winger")]
    assert raciones == [100, 100, 50, 50]


def test_lateral_y_pases_se_cruzan_en_los_extremos() -> None:
    """El ejemplo del usuario, con sus numeros."""
    ambos, solo_a, solo_b = _reparte_por_region("winger", "passing")
    assert [c.puesto for c in ambos] == ["winger", "winger"]
    assert [c.puesto for c in solo_a] == ["wingback", "wingback"]
    assert sorted(c.puesto for c in solo_b) == [
        "forward", "forward", "forward",
        "inner_midfield", "inner_midfield", "inner_midfield",
    ]


def test_los_mejores_del_principal_van_a_la_interseccion() -> None:
    principal = _cola("A", "B", "C", "D")
    plan = youth_training_plan("winger", "passing", principal, _cola("Z"))
    dobles = [a.player for a in plan.asignaciones if a.recibe_doble]
    assert dobles == ["A", "B"], "la doble racion no fue para los dos primeros"
    assert plan.con_doble == 2


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
        "winger", "defending", _cola("A", "B", "C", "D"), _cola("Z"),
    )
    laterales = [a for a in plan.asignaciones if a.puesto == "wingback"]
    assert laterales, "los laterales tenian que cruzarse"
    assert all(a.racion_principal == 50 and a.racion_secundaria == 100 for a in laterales)


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
        "keeper", "scoring", _cola("A", "B", "C", "D"), _cola("A"),
    )
    delanteros = [a for a in plan.asignaciones if a.puesto == "forward"]
    assert len(delanteros) == 3, "quedaron plazas de anotacion sin repartir"


def test_el_mismo_entrenamiento_dos_veces_es_todo_interseccion() -> None:
    plan = youth_training_plan(
        "scoring", "scoring", _cola("A", "B", "C", "D"), _cola("A", "B", "C", "D"),
    )
    dobles = [a for a in plan.asignaciones if a.region == REGION_AMBOS]
    assert len(dobles) == 3
    assert all(a.recibe_doble for a in dobles)


def test_nadie_ocupa_dos_plazas() -> None:
    plan = youth_training_plan(
        "playmaking", "passing",
        _cola(*[f"J{i}" for i in range(1, 15)]),
        _cola(*[f"J{i}" for i in range(14, 0, -1)]),
    )
    nombres = [a.player for a in plan.asignaciones]
    assert len(nombres) == len(set(nombres))


def test_el_que_toco_techo_no_ocupa_una_plaza_de_esa_habilidad() -> None:
    """La trampa era el repuesto: al tirar de la reserva para no dejar una
    plaza vacia se colaba alguien tapado justo en esa habilidad."""
    principal = _cola("A", "B")          # cola corta a proposito
    secundaria = _cola("Tapado", "C", "D", "E", "F", "G", "H")
    plan = youth_training_plan(
        "winger", "passing", principal, secundaria,
        tope_principal={"Tapado"},
    )
    en_principal = [
        a.player for a in plan.asignaciones
        if a.region in (REGION_AMBOS, REGION_SOLO_PRINCIPAL)
    ]
    assert "Tapado" not in en_principal, "un tapado entro a entrenar lo que ya tiene lleno"
    # Y si puede recibir la secundaria, que la reciba: no esta castigado.
    en_secundaria = [
        a.player for a in plan.asignaciones if a.region == REGION_SOLO_SECUNDARIA
    ]
    assert "Tapado" in en_secundaria


def test_tapado_en_las_dos_no_entra_en_ninguna_plaza_que_entrene() -> None:
    plan = youth_training_plan(
        "winger", "passing", _cola("A"), _cola("Tapado", "B", "C", "D"),
        tope_principal={"Tapado"}, tope_secundaria={"Tapado"},
    )
    entrenan = [
        a.player for a in plan.asignaciones
        if a.region != REGION_SIN_ENTRENAMIENTO
    ]
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
        "winger", "winger", "wingback", "wingback",
    ]

def test_cuantos_de_los_que_reciben_doble_van_a_ciegas() -> None:
    """En esta academia casi todo esta sin revelar; la cancha debe decirlo."""
    def note(nombre: str, current, maximum, tope=False) -> PlayerNote:
        return PlayerNote(
            name=nombre, note=8, bucket="excelente", leaves_soon=False,
            max_reached=tope, priority=1, current=current, maximum=maximum,
        )

    cola = [
        note("Ana", None, None),      # en blanco
        note("Bea", None, None),      # en blanco
        note("Cid", 5, None),         # sabe el nivel: no es a ciegas
        note("Dan", None, 7),         # sabe el techo: tampoco
        note("Eva", None, None, tope=True),  # se sabe que no sube
    ]
    plan = youth_training_plan(
        "defending", "passing_defenders", cola, cola,
        tope_principal=set(), tope_secundaria=set(),
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
            name=nombre, note=None, bucket="", leaves_soon=False,
            max_reached=tope, current=current, maximum=maximum,
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

    ORDEN = [REGION_AMBOS, REGION_SOLO_PRINCIPAL, REGION_SOLO_SECUNDARIA,
             REGION_SIN_ENTRENAMIENTO]
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
