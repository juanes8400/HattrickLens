"""Una silla del banquillo que no se puede llenar no cancela las siguientes.

2026-10-05, visto por el usuario: hay canteranos que no salen ni de suplentes
aunque quepan. El ejemplo que dio fue uno que ya había tocado techo en la
habilidad que se entrena.

Ahí está el fallo. El banquillo se recorre ORDENADO POR REGIÓN: primero las
sillas que reciben los dos entrenamientos, luego las del principal, luego las
del secundario y al final las que no reciben nada. Y cada región veta a quien
ya tocó techo en lo que esa silla entrena. Quien tocó techo en el
entrenamiento principal no puede ocupar las sillas de arriba, pero sí la de
abajo, porque la silla que no entrena nada no veta a nadie.

El reparto cortaba en la PRIMERA silla que no podía llenar, de modo que las
de abajo, que eran justo las que ese jugador sí podía ocupar, no llegaban a
repartirse nunca. Quedaba fuera habiendo sitio.
"""

from app.domain.engines.youth_skill_score import PlayerNote
from app.domain.engines.youth_training_plan import (
    PUESTOS_DE_UN_BANQUILLO,
    REGION_SIN_ENTRENAMIENTO,
    youth_training_plan,
)


def _nota(nombre: str) -> PlayerNote:
    return PlayerNote(
        name=nombre,
        note=8,
        bucket="excelente",
        leaves_soon=False,
        max_reached=False,
        priority=1,
    )


def _plan(tocaron_techo: set[str]):
    """Once titulares libres y tres de sobra que ya tocaron techo en todo."""
    titulares = [f"Titular {n:02}" for n in range(1, 12)]
    sobrantes = ["Ronny", "Otro", "Tercero"]
    cola = [_nota(n) for n in titulares + sobrantes]
    return youth_training_plan(
        "passing",
        "winger",
        cola,
        list(cola),
        tope_principal=tocaron_techo,
        tope_secundaria=tocaron_techo,
    )


def test_sin_nadie_tapado_el_banquillo_se_llena_entero() -> None:
    """El caso de control: con gente libre no falta ninguna silla."""
    plan = _plan(set())
    con_puesto = [a for a in plan.fuera if a.puesto]
    assert len(con_puesto) == min(len(PUESTOS_DE_UN_BANQUILLO), 3)


def test_quien_toco_techo_sigue_cabiendo_en_la_silla_que_no_entrena_nada() -> None:
    """El fallo que vio el usuario.

    Los tres que sobran tocaron techo en las dos habilidades que se entrenan,
    así que no pueden ocupar ninguna silla que entrene. Pero el banquillo
    tiene sillas que no entrenan nada, y ésas no vetan a nadie: tienen que
    acabar ocupadas.

    Con el corte antiguo, la primera silla que entrenaba se quedaba vacía y
    con ella TODAS las de abajo, incluida la que sí les correspondía.
    """
    plan = _plan({"Ronny", "Otro", "Tercero"})
    sillas = [a for a in plan.fuera if a.puesto]
    assert sillas, "el banquillo se quedó entero sin repartir"
    sentados = {a.player for a in sillas}
    assert "Ronny" in sentados
    # Y se sienta donde no se entrena nada, que es lo único que le quedaba.
    suya = next(a for a in sillas if a.player == "Ronny")
    assert suya.region == REGION_SIN_ENTRENAMIENTO
    assert suya.racion_principal == 0.0
    assert suya.racion_secundaria == 0.0


def test_las_sillas_que_no_se_pueden_llenar_no_inventan_a_nadie() -> None:
    """Saltarse una silla no es rellenarla con cualquiera: la que entrena y
    no tiene a quien, se queda vacía."""
    plan = _plan({"Ronny", "Otro", "Tercero"})
    for silla in plan.fuera:
        if silla.puesto and silla.region != REGION_SIN_ENTRENAMIENTO:
            assert silla.player not in {"Ronny", "Otro", "Tercero"}
