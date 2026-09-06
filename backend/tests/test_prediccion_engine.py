"""El motor de predicción por zonas.

Lo que se vigila aquí no es la precisión --eso se mide con partidos reales, no
con inventados-- sino las cosas que, si se rompen, rompen en silencio: que los
duelos crucen las bandas como en el campo, que entrenar no mire la historia de
nadie, que el orden derrota < empate < victoria sea el que el ajuste espera, y
que las probabilidades sigan siendo probabilidades.
"""

from dataclasses import dataclass

import numpy as np
import pytest

from app.domain.engines.prediccion import (
    BETA,
    CAMPOS,
    COMPARACIONES,
    ESCALA,
    ETIQUETAS,
    MINIMO_HISTORIA,
    UMBRALES,
    ModeloOrdinal,
    Probabilidades,
    medianas,
    medianas_de_lecturas,
    mezclar,
    modelo_ajustado,
    probabilidades_de_partido,
    proporcion,
    ratings_de,
    resultado,
    tabla_de_entrenamiento,
    tabla_de_puntos_esperados,
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


def _ordinal_de_juguete() -> ModeloOrdinal:
    """Un modelo cualquiera con umbrales válidos, para probar la aritmética."""
    return ModeloOrdinal(beta=np.ones(len(COMPARACIONES)), umbrales=np.array([3.0, 4.5]))


# ── Las variables ────────────────────────────────────────────────────────


def test_proporcion_sin_datos_no_favorece_a_nadie():
    assert proporcion(0, 0) == 0.5
    assert proporcion(75, 25) == 0.75


def test_los_cruces_son_los_del_campo():
    """Mi ataque izquierdo se mide contra su defensa DERECHA.

    Es el error que nadie ve: el modelo entrena igual de contento con las
    bandas cambiadas y sólo se nota en que acierta un poco menos.
    """
    cruces = {n: (mio, suyo) for n, mio, suyo in COMPARACIONES}
    assert cruces["ata_izq"] == ("left_att", "right_def")
    assert cruces["ata_der"] == ("right_att", "left_def")
    assert cruces["def_izq"] == ("left_def", "right_att")
    assert cruces["medio"] == ("midfield", "midfield")
    assert cruces["bp_ata"] == ("sp_att", "sp_def")


def test_cada_duelo_tiene_nombre_de_pantalla():
    """Sin esto, un duelo nuevo saldría en pantalla con su nombre de campo."""
    assert set(ETIQUETAS) == {n for n, _, _ in COMPARACIONES}
    assert not any("sp_" in v or "_att" in v for v in ETIQUETAS.values())


def test_una_variable_por_duelo():
    p = P(1)
    x = variables(ratings_de(p, "home"), ratings_de(p, "away"))
    assert x.shape == (len(COMPARACIONES),)
    assert np.allclose(x, 0.6)  # 60 / (60 + 40)


# ── Entrenamiento ────────────────────────────────────────────────────────


def test_entrenar_no_necesita_historia_de_nadie():
    """Un solo partido de dos equipos desconocidos ya es una fila.

    Lo que se aprende es el motor de Hattrick, que es el mismo para todos.
    La versión anterior exigía tres partidos previos por equipo y de 22
    recogidos dejaba 10.
    """
    diseno, y, ids = tabla_de_entrenamiento([P(1, home_goals=2, away_goals=0)])
    assert len(ids) == 1
    assert y.tolist() == [2]  # victoria local
    assert diseno.shape == (1, len(COMPARACIONES))


def test_entrenar_deja_fuera_lo_no_oficial():
    partidos = [P(1), P(2, match_type=4), P(3, match_type=8), P(4, match_type=3)]
    _, _, ids = tabla_de_entrenamiento(partidos)
    assert ids == [1, 4]  # liga y copa; fuera el amistoso y el torneo


def test_una_fila_por_partido_no_dos():
    """La del visitante es uno menos la del local: duplicaría sin informar."""
    _, _, ids = tabla_de_entrenamiento([P(1), P(2)])
    assert len(ids) == 2


def test_el_orden_es_derrota_empate_victoria():
    """El ajuste ordinal da por hecho este orden: al revés lo invierte todo."""
    assert resultado(P(1, home_goals=0, away_goals=3)) == 0
    assert resultado(P(1, home_goals=1, away_goals=1)) == 1
    assert resultado(P(1, home_goals=2, away_goals=1)) == 2


# ── Medianas ─────────────────────────────────────────────────────────────


def test_medianas_callan_si_no_hay_nada():
    assert medianas([], 1) is None
    assert medianas_de_lecturas([]) is None


def test_con_un_solo_partido_ya_se_puede():
    """MINIMO_HISTORIA bajó de 3 a 1 tras medir que tres no era mejor."""
    assert MINIMO_HISTORIA == 1
    assert medianas([P(1)], 1) is not None


def test_medianas_solo_miran_partidos_anteriores():
    """Sin el corte, comprobar el modelo usaría el partido que predice."""
    partidos = [P(i) for i in range(1, 6)]
    for p in partidos:
        p.home_midfield = float(p.ht_match_id * 10)
    m = medianas(partidos, 1, hasta=4)
    assert m is not None
    assert m["_partidos"] == 3  # los identificadores 1, 2 y 3
    assert m["midfield"] == 20.0


def test_medianas_de_lecturas_tolera_lo_que_falta():
    """Balón Parado no llega de la pantalla de rivales: cuenta como cero."""
    m = medianas_de_lecturas([{"midfield": 20}, {"midfield": 30}, {"midfield": 40}])
    assert m is not None
    assert m["midfield"] == 30.0
    assert m["sp_att"] == 0.0


# ── El modelo ordinal ────────────────────────────────────────────────────


def test_las_probabilidades_suman_uno():
    modelo = _ordinal_de_juguete()
    p = modelo.probabilidades(np.full(len(COMPARACIONES), 0.5))
    assert p.victoria + p.empate + p.derrota == pytest.approx(1.0)
    assert all(0.0 <= v <= 1.0 for v in (p.victoria, p.empate, p.derrota))


def test_dominar_todos_los_duelos_sube_la_victoria():
    modelo = _ordinal_de_juguete()
    flojo = modelo.probabilidades(np.full(len(COMPARACIONES), 0.2))
    fuerte = modelo.probabilidades(np.full(len(COMPARACIONES), 0.8))
    assert fuerte.victoria > flojo.victoria
    assert fuerte.derrota < flojo.derrota


def test_los_umbrales_del_modelo_no_se_cruzan():
    """Cruzados darían una probabilidad de empate negativa."""
    modelo = modelo_ajustado()
    assert modelo.umbrales[0] < modelo.umbrales[1]


def test_la_escala_aplana_pero_no_reordena():
    """La escala corrige el exceso de confianza, no cambia quién va delante.

    Sin ella, de 76 partidos a los que el modelo daba más del 90 % de
    victoria, prometía 97,7 % y ocurría el 88,2 %.
    """
    assert ESCALA > 1.0
    crudo = ModeloOrdinal(beta=np.array(BETA), umbrales=np.array(UMBRALES))
    escalado = modelo_ajustado()
    fuerte = np.full(len(COMPARACIONES), 0.62)
    flojo = np.full(len(COMPARACIONES), 0.38)
    # El orden se respeta: el fuerte sigue por delante del flojo.
    assert escalado.probabilidades(fuerte).victoria > escalado.probabilidades(flojo).victoria
    # Y la confianza baja: el escalado no se pasa tanto como el crudo.
    assert escalado.probabilidades(fuerte).victoria < crudo.probabilidades(fuerte).victoria


def test_aplicar_los_coeficientes_coincide_con_statsmodels():
    """Producción no ajusta: sólo aplica. Lo que puede desviarse es esa
    aritmética, y es lo que se comprueba aquí.

    La biblioteca guarda el segundo umbral como el LOGARITMO de su distancia
    al primero. Leerlo como si fuera el umbral a secas daría un modelo que
    funciona, no falla y predice mal.
    """
    sm_ordinal = pytest.importorskip("statsmodels.miscmodels.ordinal_model")
    rng = np.random.default_rng(11)
    diseno = rng.uniform(0.25, 0.75, size=(500, len(COMPARACIONES)))
    beta = np.array([6.0, 1.0, 2.5, 1.5, 1.2, 1.8, 0.9, 0.4, 2.0])
    latente = diseno @ beta + rng.logistic(0, 1, 500)
    y = np.digitize(latente, np.quantile(latente, [0.38, 0.55]))

    ref = sm_ordinal.OrderedModel(y, diseno, distr="logit").fit(
        method="bfgs", disp=False, maxiter=800
    )
    primero = float(ref.params[len(beta)])
    mio = ModeloOrdinal(
        beta=np.asarray(ref.params[: len(beta)], dtype=float),
        umbrales=np.array([primero, primero + float(np.exp(ref.params[len(beta) + 1]))]),
    )
    propias = np.array(
        [[p.derrota, p.empate, p.victoria] for p in (mio.probabilidades(x) for x in diseno)]
    )
    assert np.abs(propias - np.asarray(ref.predict(diseno))).max() < 1e-6


# ── Mezcla y puntos ──────────────────────────────────────────────────────


def test_mezclar_respeta_los_pesos_declarados():
    from app.domain.engines.prediccion import PESO_POISSON, PESO_ZONAS

    m = mezclar(Probabilidades(1.0, 0.0, 0.0), Probabilidades(0.0, 0.0, 1.0))
    assert m.victoria == pytest.approx(PESO_ZONAS)
    assert m.derrota == pytest.approx(PESO_POISSON)


def test_sin_poisson_no_se_inventa_la_mitad_que_falta():
    """El rival de copa no está en la tabla de la liga, así que no tiene
    fuerza de ataque ni de defensa que estimar."""
    zonas = Probabilidades(0.5, 0.2, 0.3)
    assert mezclar(zonas, None) == zonas


def test_puntos_esperados_reparten_en_vez_de_decidir():
    """Un partido igualadísimo aporta a los dos, que es la verdad."""
    assert Probabilidades(1.0, 0.0, 0.0).puntos_esperados == pytest.approx(3.0)
    assert Probabilidades(0.0, 1.0, 0.0).puntos_esperados == pytest.approx(1.0)
    assert Probabilidades(0.0, 0.0, 1.0).puntos_esperados == pytest.approx(0.0)
    assert Probabilidades(0.40, 0.20, 0.40).puntos_esperados == pytest.approx(1.4)


def test_las_probabilidades_tienen_que_sumar_uno():
    with pytest.raises(ValueError, match="suman"):
        Probabilidades(0.5, 0.5, 0.5)


# ── De punta a punta ─────────────────────────────────────────────────────


def _lecturas(base: float, cuantas: int = 4) -> list[dict[str, float]]:
    """Lecturas de un equipo, todas iguales, como las devuelven las pantallas."""
    return [dict.fromkeys(CAMPOS, base) for _ in range(cuantas)]


def test_de_punta_a_punta_el_mejor_gana():
    fuerte, flojo = _lecturas(60), _lecturas(20)
    p = probabilidades_de_partido(fuerte, flojo)
    assert p is not None
    assert p.victoria > 0.9


def test_queda_una_ventaja_de_local_pequena_y_constante():
    """Con ratings IGUALES el local sale un poco favorecido: 42,1 % contra 36,4 %.

    Parece poco para el fútbol, y está bien que lo sea: la ventaja de campo de
    Hattrick ya viene DENTRO de los ratings --el medio campo del local es un
    19 % más alto, medido en los 1.031 partidos--. Estos cinco puntos y pico
    son lo que queda por encima de eso, y salen de que la suma de los
    coeficientes no coincide con la de los umbrales.

    Si esta prueba empieza a fallar hacia arriba, es que la ventaja de campo
    se está contando dos veces.
    """
    p = probabilidades_de_partido(_lecturas(40), _lecturas(40))
    assert p is not None
    assert p.victoria - p.derrota == pytest.approx(0.057, abs=0.02)


def test_dar_la_vuelta_al_partido_da_casi_la_vuelta_a_la_terna():
    """Casi, no exacto: lo que sobra es la ventaja de local de arriba."""
    ida = probabilidades_de_partido(_lecturas(60), _lecturas(20))
    vuelta = probabilidades_de_partido(_lecturas(20), _lecturas(60))
    assert ida is not None and vuelta is not None
    assert ida.victoria == pytest.approx(vuelta.derrota, abs=0.01)
    assert ida.empate == pytest.approx(vuelta.empate, abs=0.01)
    assert ida.victoria > vuelta.derrota  # el local, por poco, siempre mejor


def test_sin_historia_de_un_lado_no_se_predice():
    """Decir 50-50 sería inventar; devolver nada deja que la pantalla lo diga."""
    assert probabilidades_de_partido(_lecturas(60), []) is None
    assert probabilidades_de_partido([], _lecturas(60)) is None


def test_la_terna_se_mezcla_con_la_poisson_si_la_hay():
    sin = probabilidades_de_partido(_lecturas(40), _lecturas(38))
    con = probabilidades_de_partido(
        _lecturas(40), _lecturas(38), poisson=Probabilidades(0.0, 0.0, 1.0)
    )
    assert sin is not None and con is not None
    assert con.derrota > sin.derrota  # la Poisson tira hacia la derrota


def test_los_puntos_de_un_partido_nunca_pasan_de_tres():
    """El visitante recibe la terna del revés, así que la suma se cuida sola."""
    p = Probabilidades(0.55, 0.25, 0.20)
    puntos = tabla_de_puntos_esperados([(7, 9, p)])
    assert puntos[7] + puntos[9] <= 3.0
    assert puntos[7] == pytest.approx(3 * 0.55 + 0.25)
    assert puntos[9] == pytest.approx(3 * 0.20 + 0.25)


def test_los_puntos_se_acumulan_por_equipo():
    p = Probabilidades(0.5, 0.3, 0.2)
    puntos = tabla_de_puntos_esperados([(1, 2, p), (3, 1, p)])
    assert set(puntos) == {1, 2, 3}
    # El 1 juega dos: gana puntos como local y como visitante.
    assert puntos[1] == pytest.approx(p.puntos_esperados + (3 * 0.2 + 0.3))
