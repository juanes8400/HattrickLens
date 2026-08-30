"""El método 5: los cuatro caminos y los bordes de sus dos parámetros.

2026-08-26. Lo que se fija aquí es el ORDEN de preferencia --segunda
habilidad, doblar, descubrir-- y que los dos umbrales sean movibles sin tocar
código, porque la pantalla los expone con una barrita.
"""

from app.domain.engines.metodo_cinco import (
    DESCUBRIR,
    DOBLAR,
    INDIVIDUAL,
    SEGUNDA_HABILIDAD,
    TODO_NIEBLA,
    Habilidad,
    decidir,
)


def hab(
    skill: str,
    puntaje: float,
    *,
    niebla: float = 1.0,
    valen: int = 0,
    label: str | None = None,
) -> Habilidad:
    """Una fila de «Puntaje», partida en las dos mitades que pide el método."""
    return Habilidad(
        skill=skill,
        label=label or skill,
        puntaje=puntaje,
        de_saber=puntaje * (1 - niebla),
        de_no_saber=puntaje * niebla,
        cuantos_valen=valen,
    )


#: La academia del usuario el 2026-08-26: un extremo bueno y seis habilidades
#: que son pura ignorancia. Es el caso que originó el método.
REAL = [
    hab("winger", 1.924, niebla=0.12, valen=1, label="Lateral"),
    hab("playmaking", 0.280, niebla=1.00, valen=0, label="Jugadas"),
    hab("set_pieces", 0.280, niebla=1.00, valen=0, label="Balón parado"),
    hab("passing", 0.275, niebla=0.77, valen=1, label="Pases"),
    hab("keeper", 0.259, niebla=1.00, valen=0, label="Portería"),
    hab("defending", 0.238, niebla=1.00, valen=0, label="Defensa"),
    hab("scoring", 0.238, niebla=1.00, valen=0, label="Anotación"),
]


def test_el_caso_real_acaba_en_descubrir():
    """Lateral tiene respaldo, ninguna segunda lo tiene, y sólo un canterano
    vale en Lateral: no hay a quién concentrar."""
    v = decidir(REAL)
    assert v is not None
    assert v.camino == DESCUBRIR
    assert v.principal == "winger"
    assert v.secundario == INDIVIDUAL
    assert v.valen_principal == 1
    assert "1 canterano" in v.motivo


def test_si_la_segunda_tiene_respaldo_se_entrena():
    """El camino preferido: la segunda plaza compra rendimiento de verdad."""
    v = decidir(
        [
            hab("winger", 2.0, niebla=0.10, valen=4),
            hab("passing", 1.5, niebla=0.20, valen=3),
            hab("keeper", 0.2, niebla=1.0),
        ]
    )
    assert v is not None
    assert v.camino == SEGUNDA_HABILIDAD
    assert (v.principal, v.secundario) == ("winger", "passing")
    assert not v.descubre


def test_sin_segunda_pero_con_grupo_se_dobla():
    """Nadie de fiar detrás, pero hay a quién concentrar la segunda dosis."""
    v = decidir([hab("winger", 2.0, niebla=0.10, valen=5), hab("passing", 0.3, niebla=1.0)])
    assert v is not None
    assert v.camino == DOBLAR
    assert v.principal == v.secundario == "winger"
    assert not v.descubre


def test_si_ni_la_mejor_tiene_respaldo_se_descubre_con_los_dos():
    """Academia recién abierta: elegir cualquier cosa sería elegir a ciegas."""
    v = decidir([hab("winger", 0.3, niebla=1.0), hab("passing", 0.28, niebla=1.0)])
    assert v is not None
    assert v.camino == TODO_NIEBLA
    assert v.principal == v.secundario == INDIVIDUAL


def test_doblar_pierde_contra_la_segunda_habilidad():
    """El orden importa: con las dos condiciones cumplidas manda la segunda,
    porque entrenar dos cosas siempre alcanza a más gente que doblar una."""
    v = decidir(
        [
            hab("winger", 2.0, niebla=0.10, valen=9),
            hab("passing", 1.0, niebla=0.10, valen=4),
        ]
    )
    assert v is not None
    assert v.camino == SEGUNDA_HABILIDAD


def test_los_dos_parametros_mueven_el_veredicto():
    """Son opiniones del usuario, no hechos, y por eso van por argumento."""
    caso = [hab("winger", 2.0, niebla=0.10, valen=2), hab("passing", 1.0, niebla=0.60, valen=3)]

    # Con la niebla por defecto (50%), «Pases» al 60% no pasa y sólo hay 2
    # buenos en Lateral: se descubre.
    assert decidir(caso).camino == DESCUBRIR  # type: ignore[union-attr]

    # Si se afloja la niebla, «Pases» entra.
    assert decidir(caso, niebla_maxima=0.70).camino == SEGUNDA_HABILIDAD  # type: ignore[union-attr]

    # Y si basta con dos para doblar, se dobla.
    assert decidir(caso, minimo_para_doblar=2).camino == DOBLAR  # type: ignore[union-attr]


def test_un_puntaje_de_cero_es_todo_niebla():
    """Cero no respalda nada. Sin esto habria una division por cero."""
    v = decidir([hab("winger", 0.0), hab("passing", 0.0)])
    assert v is not None
    assert v.camino == TODO_NIEBLA
    assert REAL[0].niebla < 0.5  # y el respaldado sigue respaldado


def test_sin_habilidades_no_hay_veredicto():
    assert decidir([]) is None


def test_una_sola_habilidad_no_rompe():
    """No hay segunda que mirar; se decide entre doblar y descubrir."""
    v = decidir([hab("winger", 2.0, niebla=0.1, valen=1)])
    assert v is not None
    assert v.camino == DESCUBRIR
    assert v.niebla_segunda is None
