"""Las sillas del banquillo que deja la reubicación de «Individual».

2026-09-14, visto por el usuario: con Lateral + Individual no había Extremo
suplente. La reubicación subía al Extremo del banquillo al once y borraba su
silla. Ahora la silla vuelve vacía y se ocupa con el criterio del motor: la
cola de lo que entrena esa silla, sin quien ya tocó techo ahí.
"""

from app.api.v1.endpoints.academy import _rellena_banquillo
from app.domain.engines.youth_skill_score import PlayerNote
from app.domain.engines.youth_training_plan import (
    REGION_AMBOS,
    REGION_SIN_ENTRENAMIENTO,
    REGION_SOLO_SECUNDARIA,
    Asignacion,
    PlanDeEntrenamiento,
)


def _nota(nombre: str, peldano: int = 5, edad: int = 1800) -> PlayerNote:
    return PlayerNote(
        name=nombre,
        note=None,
        bucket="",
        leaves_soon=False,
        max_reached=False,
        age_days_total=edad,
        priority=peldano,
    )


def _silla(puesto: str, region: str, jugador: str = "") -> Asignacion:
    return Asignacion(
        player=jugador,
        puesto=puesto,
        region=region,
        racion_principal=100.0,
        racion_secundaria=0.0,
    )


def _suelto(nombre: str) -> Asignacion:
    return Asignacion(
        player=nombre,
        puesto="",
        region=REGION_SIN_ENTRENAMIENTO,
        racion_principal=0.0,
        racion_secundaria=0.0,
    )


def _plan(once: list[str], fuera: list[Asignacion]) -> PlanDeEntrenamiento:
    plan = PlanDeEntrenamiento(principal="winger", secundaria="individual")
    plan.asignaciones = [_silla("inner_midfield", REGION_SOLO_SECUNDARIA, n) for n in once]
    plan.fuera = fuera
    return plan


def test_la_silla_de_extremo_la_ocupa_el_mejor_de_la_cola_de_lateral() -> None:
    # Bajó «Puzzo» del once, pero en la cola de Lateral va antes «Ochoa».
    plan = _plan(
        once=["Guzmán"],
        fuera=[_silla("wingback", REGION_AMBOS, "Manotas"), _suelto("Puzzo"), _suelto("Ochoa")],
    )
    vacias = [(1, _silla("winger", REGION_AMBOS))]
    cola_lateral = [_nota("Guzmán"), _nota("Ochoa", peldano=2), _nota("Puzzo", peldano=7)]

    _rellena_banquillo(plan, vacias, cola_lateral, [], set(), set())

    assert [(a.puesto, a.player) for a in plan.fuera] == [
        ("wingback", "Manotas"),
        ("winger", "Ochoa"),
        ("", "Puzzo"),
    ]
    # Lo que es del chico viaja con él; la silla conserva su región.
    extremo = plan.fuera[1]
    assert extremo.peldano == 2
    assert extremo.region == REGION_AMBOS


def test_no_sienta_a_quien_ya_toco_techo_en_lo_que_entrena_la_silla() -> None:
    plan = _plan(once=[], fuera=[_suelto("Ochoa"), _suelto("Puzzo")])
    vacias = [(0, _silla("winger", REGION_AMBOS))]

    _rellena_banquillo(plan, vacias, [_nota("Ochoa"), _nota("Puzzo")], [], {"Ochoa"}, set())

    assert plan.fuera[0].player == "Puzzo"


def test_la_silla_del_secundario_tira_de_la_cola_del_secundario() -> None:
    plan = _plan(once=[], fuera=[_suelto("Lateralista"), _suelto("Descubridor")])
    vacias = [(0, _silla("keeper", REGION_SOLO_SECUNDARIA))]

    _rellena_banquillo(plan, vacias, [_nota("Lateralista")], [_nota("Descubridor")], set(), set())

    assert plan.fuera[0].player == "Descubridor"


def test_sin_candidatos_la_silla_se_queda_vacia() -> None:
    plan = _plan(once=["Guzmán"], fuera=[_silla("wingback", REGION_AMBOS, "Manotas")])
    vacias = [(1, _silla("winger", REGION_AMBOS))]

    _rellena_banquillo(plan, vacias, [_nota("Guzmán"), _nota("Manotas")], [], set(), set())

    assert [a.player for a in plan.fuera] == ["Manotas"]
