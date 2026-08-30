"""El método 7: cada hueco mira su posición del ranking, y solo esa.

Firmado el 2026-08-26. Lo que se fija aquí es la regla que el usuario eligió
expresamente y que es fácil de "arreglar" por error: **no se baja por el
ranking**. Si la segunda está descartada entra Individual aunque la tercera
esté viva.
"""

from app.domain.engines.metodo_siete import (
    INDIVIDUAL,
    UMBRAL_DE_DESCARTE,
    Habilidad,
    decidir,
)


def hab(
    skill: str,
    puntaje: float,
    *,
    no_respaldo: float,
    bonus: float = 0.0,
    label: str | None = None,
) -> Habilidad:
    """Una fila de «Puntaje» con la proporción de no-respaldo que se pida."""
    sin_evidencia = puntaje * no_respaldo
    return Habilidad(
        skill=skill,
        label=label or skill,
        respaldo=puntaje - sin_evidencia,
        desconocido=max(0.0, sin_evidencia - bonus),
        bonus=min(bonus, sin_evidencia),
    )


#: La academia del usuario el 2026-08-26, con el bonus ya sembrado.
REAL = [
    hab("winger", 1.951, no_respaldo=0.14, bonus=0.028, label="Lateral"),
    hab("set_pieces", 0.356, no_respaldo=1.00, bonus=0.076, label="Balón parado"),
    hab("passing", 0.331, no_respaldo=0.81, bonus=0.056, label="Pases"),
    hab("playmaking", 0.315, no_respaldo=1.00, bonus=0.035, label="Jugadas"),
    hab("defending", 0.273, no_respaldo=1.00, bonus=0.035, label="Defensa"),
    hab("keeper", 0.266, no_respaldo=1.00, bonus=0.007, label="Portería"),
    hab("scoring", 0.259, no_respaldo=1.00, bonus=0.021, label="Anotación"),
]


def test_el_caso_real_da_lateral_mas_individual():
    v = decidir(REAL)
    assert v is not None
    assert v.principal == "winger"
    assert v.secundaria == INDIVIDUAL
    assert v.descubre


def test_no_se_baja_por_el_ranking():
    """La regla que el usuario eligió expresamente.

    «Pases» está VIVA (81 %) y es la tercera, pero la segunda --«Balón
    parado»-- está descartada, así que entra Individual. Bajar hasta Pases
    sería otro método, y da otro resultado.
    """
    v = decidir(REAL)
    assert v is not None
    assert v.secundaria == INDIVIDUAL
    assert v.secundaria != "passing"


def test_si_la_segunda_tiene_respaldo_se_entrena():
    v = decidir(
        [
            hab("winger", 2.0, no_respaldo=0.10),
            hab("passing", 1.5, no_respaldo=0.20),
            hab("keeper", 0.2, no_respaldo=1.0),
        ]
    )
    assert v is not None
    assert (v.principal, v.secundaria) == ("winger", "passing")
    assert not v.descubre


def test_si_la_primera_esta_descartada_el_principal_descubre():
    """Y la segunda, si tiene respaldo, se queda con el secundario. Los dos
    huecos son independientes: cada uno mira su propia posición."""
    v = decidir(
        [
            hab("winger", 2.0, no_respaldo=1.0),
            hab("passing", 1.5, no_respaldo=0.10),
        ]
    )
    assert v is not None
    assert v.principal == INDIVIDUAL
    assert v.secundaria == "passing"


def test_con_las_dos_descartadas_se_descubre_por_partida_doble():
    v = decidir([hab("winger", 0.3, no_respaldo=1.0), hab("passing", 0.28, no_respaldo=1.0)])
    assert v is not None
    assert v.principal == v.secundaria == INDIVIDUAL


def test_el_bonus_cuenta_como_no_respaldo():
    """Es la aportación del usuario al método: una habilidad que sube por el
    bonus te devuelve tu propia opinión disfrazada de dato."""
    sin_bonus = Habilidad("x", "x", respaldo=0.5, desconocido=0.4, bonus=0.0)
    con_bonus = Habilidad("x", "x", respaldo=0.5, desconocido=0.4, bonus=5.0)
    assert not sin_bonus.descartada
    assert con_bonus.descartada


def test_el_umbral_es_inclusivo():
    """Exactamente 90 % descarta. Con la separación real del usuario --81 % y
    luego 100 %-- da igual, pero el borde tiene que estar decidido."""
    justo = Habilidad("x", "x", respaldo=0.10, desconocido=0.90, bonus=0.0)
    assert justo.no_respaldo == UMBRAL_DE_DESCARTE
    assert justo.descartada


def test_puntaje_cero_no_respalda_nada():
    vacia = Habilidad("x", "x", respaldo=0.0, desconocido=0.0, bonus=0.0)
    assert vacia.no_respaldo == 1.0
    assert vacia.descartada


def test_una_sola_habilidad():
    v = decidir([hab("winger", 2.0, no_respaldo=0.1)])
    assert v is not None
    assert v.principal == "winger"
    assert v.secundaria == INDIVIDUAL
    assert v.no_respaldo_secundaria is None


def test_sin_habilidades_no_hay_veredicto():
    assert decidir([]) is None


def test_el_motivo_nombra_a_la_culpable():
    v = decidir(REAL)
    assert v is not None
    assert "Balón parado" in v.motivo
    assert "descubrir" in v.motivo
