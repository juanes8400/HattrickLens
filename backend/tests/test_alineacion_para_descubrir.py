"""El reparto de «Individual» elige también los puestos, y descubrir es saber el techo.

2026-09-14, pedido por el usuario: Antonio Zaraín jugaba de Mediocentro con el
techo de Jugadas ya sabido, y no se proponía ir de Delantero. Dos cambios:
la habilidad cuenta como descubierta cuando se sabe su techo, y las sillas de
Individual pueden cambiar de puesto dentro de una formación legal.
"""

from collections import Counter
from dataclasses import replace
from types import SimpleNamespace

from app.api.v1.endpoints.academy import _alineaciones_posibles, _recoloca_para_descubrir
from app.domain.engines.youth_training_plan import (
    REGION_AMBOS,
    REGION_SIN_ENTRENAMIENTO,
    REGION_SOLO_PRINCIPAL,
    REGION_SOLO_SECUNDARIA,
    Asignacion,
    PlanDeEntrenamiento,
)
from app.domain.value_objects.formations import LINE_COUNTS

HABILIDADES = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")
LATERAL = ["winger", "winger", "wingback", "wingback"]
INDIVIDUAL = [
    "keeper",
    "central_defender",
    "central_defender",
    "central_defender",
    "inner_midfield",
    "inner_midfield",
    "inner_midfield",
]


def _lineas(puestos: list[str]) -> tuple[int, int, int]:
    c = Counter(puestos)
    return (
        c["central_defender"] + c["wingback"],
        c["inner_midfield"] + c["winger"],
        c["forward"],
    )


def test_con_lateral_las_sillas_de_individual_pueden_ser_delanteros() -> None:
    formas = _alineaciones_posibles(LATERAL, INDIVIDUAL, {"winger", "wingback"})

    assert INDIVIDUAL in formas, "la de siempre sigue siendo una opción"
    assert any("forward" in f for f in formas)
    for forma in formas:
        once = LATERAL + forma
        assert once.count("keeper") == 1
        assert _lineas(once) in set(LINE_COUNTS.values())
        assert "winger" not in forma and "wingback" not in forma, "lo de Lateral no crece"


def _lectura(techo_sabido: bool) -> SimpleNamespace:
    # El nivel actual no se sabe en ningún caso: solo cuenta el techo.
    return SimpleNamespace(current=None, maximum=5 if techo_sabido else None, max_reached=False)


def _plan_lateral_individual() -> PlanDeEntrenamiento:
    plan = PlanDeEntrenamiento(principal="winger", secundaria="individual")
    plan.asignaciones = [
        Asignacion(
            player=f"L{i}",
            puesto=p,
            region=REGION_AMBOS,
            racion_principal=100.0,
            racion_secundaria=66.7,
        )
        for i, p in enumerate(LATERAL)
    ] + [
        Asignacion(
            player=f"J{i}",
            puesto=p,
            region=REGION_SOLO_SECUNDARIA,
            racion_principal=0.0,
            racion_secundaria=66.7,
        )
        for i, p in enumerate(INDIVIDUAL)
    ]
    plan.asignaciones[-1] = replace(plan.asignaciones[-1], player="Zaraín")
    return plan


def test_quien_ya_tiene_sabidos_los_techos_de_medio_va_de_delantero() -> None:
    plan = _plan_lateral_individual()
    lecturas = {f"J{i}": {sk: _lectura(False) for sk in HABILIDADES} for i in range(6)}
    # Zaraín: todos los techos sabidos menos Pases y Anotación. De Mediocentro
    # destaparía 23; de Delantero, 26 + 38 = 64.
    lecturas["Zaraín"] = {sk: _lectura(sk not in ("passing", "scoring")) for sk in HABILIDADES}

    _recoloca_para_descubrir(plan, "winger", "individual", lecturas)

    puestos = {a.player: a.puesto for a in plan.asignaciones}
    assert puestos["Zaraín"] == "forward"
    assert [a.puesto for a in plan.asignaciones[:4]] == LATERAL, "lo de Lateral no se toca"
    assert _lineas([a.puesto for a in plan.asignaciones]) in set(LINE_COUNTS.values())


def test_sin_ganancia_no_se_cambia_la_formacion() -> None:
    plan = _plan_lateral_individual()
    lecturas = {
        a.player: {sk: _lectura(False) for sk in HABILIDADES} for a in plan.asignaciones[4:]
    }

    _recoloca_para_descubrir(plan, "winger", "individual", lecturas)

    assert [a.puesto for a in plan.asignaciones[4:]] == INDIVIDUAL


#: Individual de principal con Pases: Pases entrena Mediocentros, Extremos y
#: Delanteros, que quedan en «ambos»; lo demás es solo de Individual.
PASES_AMBOS = ["inner_midfield"] * 3 + ["winger"] * 2 + ["forward"] * 3
SOLO_INDIVIDUAL = ["keeper", "central_defender", "central_defender"]


def _plan_individual_pases(banquillo: list[str]) -> PlanDeEntrenamiento:
    plan = PlanDeEntrenamiento(principal="individual", secundaria="passing")
    plan.asignaciones = [
        Asignacion(
            player=f"A{i}",
            puesto=p,
            region=REGION_AMBOS,
            racion_principal=100.0,
            racion_secundaria=66.7,
        )
        for i, p in enumerate(PASES_AMBOS)
    ] + [
        Asignacion(
            player=f"P{i}",
            puesto=p,
            region=REGION_SOLO_PRINCIPAL,
            racion_principal=100.0,
            racion_secundaria=0.0,
        )
        for i, p in enumerate(SOLO_INDIVIDUAL)
    ]
    plan.fuera = [
        Asignacion(
            player=n,
            puesto="",
            region=REGION_SIN_ENTRENAMIENTO,
            racion_principal=0.0,
            racion_secundaria=0.0,
        )
        for n in banquillo
    ]
    return plan


def test_con_individual_de_principal_tambien_se_reparte_ambos() -> None:
    # Todos los del once con los techos sabidos; en el banquillo, uno sin
    # ninguno. Antes no había sillas en juego y se quedaba fuera.
    plan = _plan_individual_pases(["Nuevo"])
    lecturas = {a.player: {sk: _lectura(True) for sk in HABILIDADES} for a in plan.asignaciones}
    lecturas["Nuevo"] = {sk: _lectura(False) for sk in HABILIDADES}

    _recoloca_para_descubrir(plan, "individual", "passing", lecturas)

    assert "Nuevo" in {a.player for a in plan.asignaciones}
    en_ambos = sorted(a.puesto for a in plan.asignaciones if a.region == REGION_AMBOS)
    assert en_ambos == sorted(PASES_AMBOS), "los puestos que reciben Pases no cambian"


def test_con_individual_de_principal_los_centrales_pueden_pasar_a_laterales() -> None:
    # Sin Pases, un Defensa Central destapa como mucho 74 y un Defensa Lateral
    # 83: con todo por descubrir, 2-5-3 con dos laterales gana.
    plan = _plan_individual_pases([])
    lecturas = {a.player: {sk: _lectura(False) for sk in HABILIDADES} for a in plan.asignaciones}

    _recoloca_para_descubrir(plan, "individual", "passing", lecturas)

    solo = sorted(a.puesto for a in plan.asignaciones if a.region == REGION_SOLO_PRINCIPAL)
    assert solo == ["keeper", "wingback", "wingback"]
