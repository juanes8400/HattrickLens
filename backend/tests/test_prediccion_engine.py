"""El motor de predicción por zonas.

Lo que se vigila aquí no es la precisión --eso se mide con partidos reales,
no con inventados-- sino las tres cosas que, si se rompen, rompen en silencio:
que las proporciones crucen las bandas como en el campo, que entrenar no mire
la historia de nadie, y que las probabilidades sigan siendo probabilidades.
"""

from dataclasses import dataclass

import numpy as np
import pytest

from app.domain.engines.prediccion import (
    CAMPOS,
    COMPARACIONES,
    MINIMO_HISTORIA,
    ajustar_poisson,
    ajustar_zonas,
    medianas,
    mezclar,
    proporcion,
    ratings_de,
    resultado,
    tabla_de_entrenamiento,
    variables,
)


@dataclass
class P:
    """Un partido de mentira con los campos que el motor lee."""

    ht_match_id: int
    home_team_id: int = 1
    away_team_id: int = 2
    home_goals: int = 0
    away_goals: int = 0
    match_type: int = 1

    def __post_init__(self) -> None:
        for lado, base in (("home", 60.0), ("away", 40.0)):
            for c in CAMPOS:
                setattr(self, f"{lado}_{c}", base)


def test_proporcion_sin_datos_no_favorece_a_nadie():
    assert proporcion(0, 0) == 0.5
    assert proporcion(75, 25) == 0.75


def test_los_cruces_son_los_del_campo():
    """Mi ataque izquierdo se mide contra su defensa DERECHA, no la izquierda.

    Es el error que nadie ve: el modelo entrena igual de contento con las
    bandas cambiadas y sólo se nota en que acierta un poco menos.
    """
    cruces = {n: (mio, suyo) for n, mio, suyo in COMPARACIONES}
    assert cruces["ata_izq"] == ("left_att", "right_def")
    assert cruces["ata_der"] == ("right_att", "left_def")
    assert cruces["def_izq"] == ("left_def", "right_att")
    assert cruces["medio"] == ("midfield", "midfield")


def test_una_variable_por_comparacion():
    p = P(1)
    x = variables(ratings_de(p, "home"), ratings_de(p, "away"))
    assert x.shape == (len(COMPARACIONES),)
    assert np.allclose(x, 0.6)  # 60 / (60 + 40)


def test_entrenar_no_necesita_historia_de_nadie():
    """Un solo partido de dos equipos desconocidos ya es una fila.

    Lo que se aprende es el motor de Hattrick, que es el mismo para todos;
    para medir una función cada observación se basta a sí misma. La versión
    anterior exigía tres partidos previos por equipo y de 22 dejaba 10.
    """
    diseno, y, ids = tabla_de_entrenamiento([P(1, home_goals=2, away_goals=0)])
    assert len(ids) == 1
    assert y.tolist() == [0]
    assert diseno.shape == (1, len(COMPARACIONES))


def test_entrenar_deja_fuera_lo_no_oficial():
    partidos = [P(1), P(2, match_type=4), P(3, match_type=8), P(4, match_type=3)]
    _, _, ids = tabla_de_entrenamiento(partidos)
    assert ids == [1, 4]  # liga y copa; fuera el amistoso y el torneo


def test_una_fila_por_partido_no_dos():
    """La del visitante es `1 − la del local`: duplicaría sin informar."""
    _, _, ids = tabla_de_entrenamiento([P(1), P(2)])
    assert len(ids) == 2


def test_resultado():
    assert resultado(P(1, home_goals=2, away_goals=1)) == 0
    assert resultado(P(1, home_goals=1, away_goals=1)) == 1
    assert resultado(P(1, home_goals=0, away_goals=3)) == 2


def test_medianas_callan_sin_historia_suficiente():
    pocos = [P(i) for i in range(MINIMO_HISTORIA - 1)]
    assert medianas(pocos, 1) is None


def test_medianas_solo_miran_partidos_anteriores():
    """Sin el corte, predecir un partido usaría el partido mismo."""
    partidos = [P(i) for i in range(1, 6)]
    for p in partidos:
        p.home_midfield = float(p.ht_match_id * 10)
    m = medianas(partidos, 1, hasta=4)
    assert m is not None
    assert m["_partidos"] == 3  # los identificadores 1, 2 y 3
    assert m["midfield"] == 20.0


def test_las_probabilidades_suman_uno():
    partidos = [
        P(i, home_goals=2, away_goals=0) if i % 3 else P(i, home_goals=0, away_goals=2)
        for i in range(1, 13)
    ]
    diseno, y, _ = tabla_de_entrenamiento(partidos)
    modelo = ajustar_zonas(diseno, y, vueltas=300)
    p = modelo.probabilidades(diseno[0])
    assert p.victoria + p.empate + p.derrota == pytest.approx(1.0)
    assert all(0.0 <= v <= 1.0 for v in (p.victoria, p.empate, p.derrota))


def test_mezclar_respeta_los_pesos_declarados():
    from app.domain.engines.prediccion import PESO_POISSON, PESO_ZONAS, Probabilidades

    z = Probabilidades(1.0, 0.0, 0.0)
    po = Probabilidades(0.0, 0.0, 1.0)
    m = mezclar(z, po)
    assert m.victoria == pytest.approx(PESO_ZONAS)
    assert m.derrota == pytest.approx(PESO_POISSON)


def test_poisson_da_probabilidades_validas():
    partidos = [P(i, home_goals=i % 4, away_goals=(i + 1) % 3) for i in range(1, 20)]
    modelo = ajustar_poisson(partidos)
    p = modelo.probabilidades(1, 2)
    assert p.victoria + p.empate + p.derrota == pytest.approx(1.0)


def test_poisson_sin_partidos_oficiales_avisa():
    with pytest.raises(ValueError, match="oficiales"):
        ajustar_poisson([P(1, match_type=4)])
