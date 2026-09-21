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
    PESO_ORDINAL,
    TIPOS_DE_COPA,
    TIPOS_DE_LIGA,
    TIPOS_OFICIALES,
    TIPOS_POR_COMPETICION,
    UMBRALES,
    ModeloOrdinal,
    Probabilidades,
    modelo_ajustado,
    probabilidades_de_partido,
    promedios,
    proporcion,
    ratings_de,
    resultado,
    resumen_de_lecturas,
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
    """Sin datos no puede salir nada que favorezca a uno de los dos.

    El duelo es `A/(A+B)` y su neutro es 0,5. Se probaron las otras tres
    formas el 2026-09-07 --`A/B`, `log(A/B)`, `log(A/(A+B))`-- y todas
    predicen peor; el porque esta en el docstring de `proporcion`.
    """
    assert proporcion(0, 0) == 0.5
    assert proporcion(50, 50) == 0.5
    assert proporcion(75, 25) == 0.75
    # Simetrica: la misma ventaja pesa igual en los dos sentidos. `A/B` daria
    # 3 y 0,33, que no lo es, y por eso deformaba los duelos defensivos.
    assert proporcion(25, 75) == 0.25


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


def test_entrenar_es_solo_con_liga():
    """La copa juega con otras reglas y enseñaría dos mentiras.

    De 861 partidos de copa recogidos, CERO empates --hay prórroga-- y el
    local marcaba 1,18 por 5,42 del visitante, porque el sorteo cruza
    divisiones y el que recibe suele ser el débil. Con la copa dentro, las
    tres clases salían descalibradas.
    """
    partidos = [P(1), P(2, match_type=4), P(3, match_type=8), P(4, match_type=3)]
    _, _, ids = tabla_de_entrenamiento(partidos)
    assert ids == [1]  # sólo liga: fuera copa, amistoso y torneo


def test_una_fila_por_partido_no_dos():
    """La del visitante es uno menos la del local: duplicaría sin informar."""
    _, _, ids = tabla_de_entrenamiento([P(1), P(2)])
    assert len(ids) == 2


def test_el_orden_es_derrota_empate_victoria():
    """El ajuste ordinal da por hecho este orden: al revés lo invierte todo."""
    assert resultado(P(1, home_goals=0, away_goals=3)) == 0
    assert resultado(P(1, home_goals=1, away_goals=1)) == 1
    assert resultado(P(1, home_goals=2, away_goals=1)) == 2


# ── Promedios ────────────────────────────────────────────────────────────


def test_promedios_callan_si_no_hay_nada():
    assert promedios([], 1, competicion="liga") is None
    assert resumen_de_lecturas([]) is None


def test_con_un_solo_partido_ya_se_puede():
    """MINIMO_HISTORIA bajó de 3 a 1 tras medir que tres no era mejor."""
    assert MINIMO_HISTORIA == 1
    assert promedios([P(1)], 1, competicion="liga") is not None


def test_promedios_solo_miran_partidos_anteriores():
    """Sin el corte, comprobar el modelo usaría el partido que predice."""
    partidos = [P(i) for i in range(1, 6)]
    for p in partidos:
        p.home_midfield = float(p.ht_match_id * 10)
    m = promedios(partidos, 1, competicion="liga", hasta=4)
    assert m is not None
    assert m["_partidos"] == 3  # los identificadores 1, 2 y 3
    assert m["midfield"] == 20.0


def test_el_promedio_no_mezcla_liga_con_copa():
    """Arreglado el 2026-09-08: `promedios()` mezclaba las dos competiciones
    mientras la pantalla de Liga usaba sólo liga. Un equipo no juega igual en
    las dos --medido en el equipo del usuario, el mediocampo de sus partidos
    de copa dobla al de los de liga-- así que un promedio que las mezcle no
    describe ninguna."""
    de_liga = [P(1), P(2)]
    de_copa = [P(3), P(4)]
    for p in de_liga:
        p.match_type = 1
        p.home_midfield = 10.0
    for p in de_copa:
        p.match_type = 3
        p.home_midfield = 30.0
    todos = de_liga + de_copa

    assert promedios(todos, 1, competicion="liga")["midfield"] == 10.0
    assert promedios(todos, 1, competicion="copa")["midfield"] == 30.0
    # Y cada una cuenta sólo los suyos, no los cuatro.
    assert promedios(todos, 1, competicion="liga")["_partidos"] == 2
    assert promedios(todos, 1, competicion="copa")["_partidos"] == 2
    # Sin partidos de esa competición, calla en vez de caer en la otra.
    assert promedios(de_liga, 1, competicion="copa") is None


def test_promocion_y_masters_cuentan_como_liga():
    """Decidido por el usuario el 2026-09-08.

    Lo que agrupa NO es el formato del torneo --el Masters es eliminatoria,
    como la copa-- sino CON QUÉ EQUIPO se juega: al Masters y a la promoción
    se sale con el once titular, y eso es lo que el promedio describe.
    """
    from app.domain.value_objects.ht_constants import (
        MATCH_TYPE_CUP,
        MATCH_TYPE_LEAGUE,
        MATCH_TYPE_MASTERS,
        MATCH_TYPE_QUALIFICATION,
    )

    assert set(TIPOS_DE_LIGA) == {
        MATCH_TYPE_LEAGUE,
        MATCH_TYPE_QUALIFICATION,
        MATCH_TYPE_MASTERS,
    }
    assert set(TIPOS_DE_COPA) == {MATCH_TYPE_CUP}
    # Ninguno cae en las dos, y juntos son exactamente los oficiales.
    assert not set(TIPOS_DE_LIGA) & set(TIPOS_DE_COPA)
    assert set(TIPOS_OFICIALES) == set(TIPOS_DE_LIGA) | set(TIPOS_DE_COPA)


def test_los_amistosos_son_una_muestra_aparte_y_no_son_oficiales():
    """Tercera muestra elegible, pedida el 2026-09-08 para la ficha de rival.

    NO es equivalente a las otras dos y por eso se prueba aparte: un amistoso
    se juega con suplentes, y los coeficientes del motor salieron de 5.232
    partidos de LIGA. La pantalla lo avisa cuando esta muestra está elegida.

    Lo que esta prueba defiende es que un amistoso NUNCA se cuele en un
    promedio de liga o de copa por descuido."""
    from app.domain.engines.prediccion import TIPOS_DE_AMISTOSOS
    from app.domain.value_objects.ht_constants import FRIENDLY_MATCH_TYPES

    assert set(TIPOS_DE_AMISTOSOS) == set(FRIENDLY_MATCH_TYPES)
    assert not set(TIPOS_DE_AMISTOSOS) & set(TIPOS_OFICIALES)
    assert set(TIPOS_POR_COMPETICION) == {"liga", "copa", "amistosos"}

    liga, copa, amistoso = P(1), P(2), P(3)
    liga.match_type, liga.home_midfield = 1, 10.0
    copa.match_type, copa.home_midfield = 3, 30.0
    amistoso.match_type, amistoso.home_midfield = 4, 90.0
    todos = [liga, copa, amistoso]

    assert promedios(todos, 1, competicion="liga")["midfield"] == 10.0
    assert promedios(todos, 1, competicion="copa")["midfield"] == 30.0
    assert promedios(todos, 1, competicion="amistosos")["midfield"] == 90.0
    for cual in ("liga", "copa", "amistosos"):
        assert promedios(todos, 1, competicion=cual)["_partidos"] == 1


def test_un_masters_entra_en_el_promedio_de_liga():
    """La regla, ejercida: un Masters cuenta con la liga, no con la copa."""
    liga, masters, copa = P(1), P(2), P(3)
    liga.match_type, liga.home_midfield = 1, 10.0
    masters.match_type, masters.home_midfield = 7, 20.0
    copa.match_type, copa.home_midfield = 3, 90.0
    todos = [liga, masters, copa]

    assert promedios(todos, 1, competicion="liga")["_partidos"] == 2
    assert promedios(todos, 1, competicion="liga")["midfield"] == 15.0
    assert promedios(todos, 1, competicion="copa")["_partidos"] == 1
    assert promedios(todos, 1, competicion="copa")["midfield"] == 90.0


def test_resumen_de_lecturas_tolera_lo_que_falta():
    """Balón Parado no llega de la pantalla de rivales: cuenta como cero."""
    m = resumen_de_lecturas([{"midfield": 20}, {"midfield": 30}, {"midfield": 40}])
    assert m is not None
    assert m["midfield"] == 30.0
    assert m["sp_att"] == 0.0


def test_resumen_de_lecturas_admite_los_cuatro_metodos():
    """2026-09-09: Liga ofrece los mismos resúmenes que la ficha de rival.
    2026-09-13: la mediana se retira a pedido del usuario y el promedio la
    absorbe.

    Se prueba con una zona que sube partido a partido, porque es donde los
    métodos dan números distintos y ninguno puede colarse por parecerse a
    otro. `max_parallel` contagia el techo a los tres carriles de su mitad, así
    que el ataque central hereda el máximo del ataque.
    """
    lecturas = [
        {"midfield": 10, "left_att": 5},
        {"midfield": 20, "left_att": 50},
        {"midfield": 60, "left_att": 5},
    ]
    promedio = resumen_de_lecturas(lecturas, "average")
    maximo = resumen_de_lecturas(lecturas, "max")
    carril = resumen_de_lecturas(lecturas, "max_parallel")
    ultimo = resumen_de_lecturas(lecturas, "last")
    assert promedio is not None and maximo is not None
    assert carril is not None and ultimo is not None

    assert promedio["midfield"] == 30.0
    assert maximo["midfield"] == 60.0
    assert ultimo["midfield"] == 60.0
    # El medio campo no es un carril: `max_parallel` lo deja en su propio máximo.
    assert carril["midfield"] == 60.0
    # El ataque sí: el techo de la izquierda (50) se contagia al centro.
    assert maximo["central_att"] == 0.0
    assert carril["central_att"] == 50.0
    # El defecto es el promedio...
    assert resumen_de_lecturas(lecturas) == promedio
    # ...y quien pida la mediana retirada recibe el promedio, no otro número:
    # aquí la mediana habría sido 20 y el promedio es 30.
    assert resumen_de_lecturas(lecturas, "median") == promedio


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


def test_la_escala_ya_no_aplana_nada():
    """Estuvo en 1,30 y ahora es 1,0, y eso es una buena noticia.

    Aplanaba porque con 773 partidos el modelo se pasaba de confiado: de 76 a
    los que daba más del 90 % de victoria, prometía 97,7 % y ocurría el
    88,2 %. Con 5.232 el problema desapareció solo, así que aplanar sólo
    empeoraba. Si alguien la vuelve a subir sin reajustar, este test lo dice.
    """
    assert ESCALA == 1.0
    modelo = modelo_ajustado()
    crudo = ModeloOrdinal(beta=np.array(BETA), umbrales=np.array(UMBRALES))
    x = np.full(len(COMPARACIONES), 0.62)
    assert modelo.probabilidades(x).victoria == pytest.approx(
        crudo.probabilidades(x).victoria
    )


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


# ── Puntos ───────────────────────────────────────────────────────────────


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


def test_con_ratings_iguales_la_terna_sale_simetrica():
    """Con ratings IGUALES, victoria y derrota salen exactamente iguales.

    La ventaja de campo de Hattrick ya viene DENTRO de los ratings --el medio
    campo del local es un 19 % más alto-- y el motor no le suma nada encima.

    HASTA EL 2026-09-20 NO ERA ASÍ: quedaba un residuo de unos 5,7 puntos a
    favor del local, que no venía de ningún bono sino de la mitad ORDINAL, de
    que la suma de sus coeficientes no coincidiera con la de sus umbrales. Con
    la mezcla en 100-0 ese residuo se fue con ella, y la Poisson es simétrica
    por construcción: calcula la lambda de cada lado con SUS duelos
    ofensivos, así que con ratings iguales las dos coinciden al último
    decimal.

    La prueba se escribe contra el peso y no contra un número fijo: si alguien
    vuelve a encender la ordinal, esto es lo primero que lo dice.

    Si empieza a fallar hacia arriba con el peso en cero, la ventaja de campo
    se está contando dos veces."""
    iguales = _lecturas(40)
    p = probabilidades_de_partido(iguales, iguales)
    assert p is not None
    if PESO_ORDINAL == 0.0:
        assert p.victoria == pytest.approx(p.derrota, abs=1e-12)
        return
    solo_ordinal = modelo_ajustado().probabilidades(
        variables(resumen_de_lecturas(iguales), resumen_de_lecturas(iguales))
    )
    margen = solo_ordinal.victoria - solo_ordinal.derrota
    assert p.victoria - p.derrota == pytest.approx(PESO_ORDINAL * margen, abs=1e-9)
    assert 0.0 < p.victoria - p.derrota < 0.10


def test_dar_la_vuelta_al_partido_da_la_vuelta_a_la_terna():
    """Cambiar de campo a los dos equipos da la terna espejada.

    Desde el 2026-09-20 es EXACTO, no aproximado: con la mezcla en 100-0 sólo
    queda la Poisson, que es simétrica por construcción. Mientras hubo un 20 %
    de ordinal quedaba un residuo de coma decimal, y ese residuo siempre
    favorecía al local."""
    ida = probabilidades_de_partido(_lecturas(60), _lecturas(20))
    vuelta = probabilidades_de_partido(_lecturas(20), _lecturas(60))
    assert ida is not None and vuelta is not None
    tolerancia = 1e-12 if PESO_ORDINAL == 0.0 else 0.01
    assert ida.victoria == pytest.approx(vuelta.derrota, abs=tolerancia)
    assert ida.empate == pytest.approx(vuelta.empate, abs=tolerancia)
    if PESO_ORDINAL > 0.0:
        assert ida.victoria > vuelta.derrota  # el local, por poco, siempre mejor


def test_sin_historia_de_un_lado_no_se_predice():
    """Decir 50-50 sería inventar; devolver nada deja que la pantalla lo diga."""
    assert probabilidades_de_partido(_lecturas(60), []) is None
    assert probabilidades_de_partido([], _lecturas(60)) is None


def test_de_punta_a_punta_da_tambien_marcador_y_goles():
    """La mitad de goles aporta algo que el ordinal no sabe dar."""
    from app.domain.engines.prediccion import goles_de_partido, marcador_de_partido

    fuerte, flojo = _lecturas(55), _lecturas(20)
    goles = goles_de_partido(fuerte, flojo)
    assert goles is not None
    assert goles[0] > goles[1]
    marcador = marcador_de_partido(fuerte, flojo)
    assert marcador is not None
    assert marcador[0] > marcador[1]


def test_de_punta_a_punta_conoce_la_copa():
    """En copa no puede haber empate, y el camino de la pantalla lo sabe."""
    liga = probabilidades_de_partido(_lecturas(45), _lecturas(35))
    copa = probabilidades_de_partido(_lecturas(45), _lecturas(35), es_copa=True)
    assert liga is not None and copa is not None
    assert liga.empate > 0
    assert copa.empate == 0.0


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


# ── La Poisson sobre los goles ───────────────────────────────────────────


def _r(base: float) -> dict[str, float]:
    return dict.fromkeys(CAMPOS, base)


def test_el_mejor_equipo_marca_mas():
    from app.domain.engines.prediccion import goles_esperados

    assert goles_esperados(_r(50), _r(20)) > goles_esperados(_r(20), _r(50))


def test_los_goles_esperados_caen_en_el_rango_real():
    """Dos equipos parecidos deben dar algo cercano a la media de la liga.

    En los 1.031 partidos recogidos, un lado marca 2,05 de media.
    """
    from app.domain.engines.prediccion import goles_esperados

    assert 1.0 < goles_esperados(_r(40), _r(40)) < 4.0


def test_la_poisson_tiene_tope():
    """La exponencial no frena sola: con los cinco duelos al máximo predice 26
    goles. No pasa con datos reales, pero un rating absurdo por un fallo de
    lectura sí llegaría."""
    from app.domain.engines.prediccion import MAXIMO_GOLES_ESPERADOS, goles_esperados

    assert goles_esperados(_r(99), _r(1)) <= MAXIMO_GOLES_ESPERADOS


def test_la_terna_de_la_poisson_suma_uno():
    from app.domain.engines.prediccion import probabilidades_poisson

    for a, b in ((50, 20), (30, 30), (10, 45)):
        p = probabilidades_poisson(_r(a), _r(b))
        assert p.victoria + p.empate + p.derrota == pytest.approx(1.0)


def test_la_poisson_no_confunde_ganar_con_perder():
    """Invertir la rejilla no falla: da probabilidades válidas y al revés.

    Es el peor tipo de error posible, así que se vigila explícitamente.
    """
    from app.domain.engines.prediccion import probabilidades_poisson

    p = probabilidades_poisson(_r(55), _r(20))
    assert p.victoria > 0.8
    assert p.derrota < 0.1


def test_dos_iguales_dan_el_empate_mas_probable_de_todos():
    """Es la ventaja de la Poisson sobre el ordinal: el empate sale de que las
    dos cuentas den lo mismo, no de una franja estrecha entre dos umbrales."""
    from app.domain.engines.prediccion import probabilidades_poisson

    igualado = probabilidades_poisson(_r(40), _r(40))
    desigual = probabilidades_poisson(_r(55), _r(20))
    assert igualado.empate > desigual.empate
    assert igualado.victoria == pytest.approx(igualado.derrota, abs=0.01)


def test_el_marcador_mas_probable_es_coherente_con_quien_gana():
    from app.domain.engines.prediccion import marcador_mas_probable

    local, visita = marcador_mas_probable(_r(55), _r(20))
    assert local > visita
    iguales = marcador_mas_probable(_r(40), _r(40))
    assert iguales[0] == iguales[1]


def test_en_copa_no_hay_empate():
    """Hay prórroga: alguien tiene que pasar.

    Comprobado en los datos: de 861 partidos de copa recogidos, CERO empates.
    Enseñar ahí una probabilidad de empate sería enseñar algo imposible.
    """
    from app.domain.engines.prediccion import probabilidades_de_copa

    p = probabilidades_de_copa(_r(45), _r(35))
    assert p.empate == 0.0
    assert p.victoria + p.derrota == pytest.approx(1.0)


def test_la_copa_respeta_quien_es_mejor():
    """El empate se reparte entre los dos en la proporción que ya tenían: no
    se reentrena nada, sólo se quita una opción que no existe."""
    from app.domain.engines.prediccion import probabilidades_de_copa, probabilidades_del_motor

    liga = probabilidades_del_motor(_r(45), _r(35))
    copa = probabilidades_de_copa(_r(45), _r(35))
    assert copa.victoria > liga.victoria
    assert copa.victoria / copa.derrota == pytest.approx(liga.victoria / liga.derrota)


def test_el_peso_de_la_mezcla_es_el_elegido():
    """100 % Poisson, elegido por el usuario el 2026-09-20.

    Estuvo en 60/40, en 75/25 y en 80/20. Se va al 100 sobre el barrido
    entero, que dice dos cosas: que del 80 % al 100 % la PUNTERÍA no se mueve
    (log-loss 0,6584 -> 0,6588, acierto y AUC iguales a tres decimales) y que
    el EMPATE sí, porque a 0,90 y a 1,00 su error de calibración se sale de la
    banda del azar. El usuario eligió con las dos cosas delante.

    Si alguien lo cambia sin volver a medir, este test lo dice."""
    from app.domain.engines.prediccion import PESO_GOLES, PESO_ORDINAL

    assert PESO_ORDINAL + PESO_GOLES == 1.0
    assert PESO_ORDINAL == 0.0
    assert PESO_GOLES == 1.0


def test_la_ordinal_sigue_entera_aunque_no_pese():
    """Apagada, no borrada (2026-09-20).

    Volver al 80/20 tiene que seguir siendo cambiar dos números, así que el
    modelo ordinal y su camino de cálculo siguen aquí y siguen dando una terna
    válida. Sin esta prueba, la primera limpieza de código muerto se lo lleva
    por delante y la vuelta atrás deja de ser barata."""
    from app.domain.engines.prediccion import modelo_ajustado, variables

    iguales = _lecturas(40)
    terna = modelo_ajustado().probabilidades(
        variables(resumen_de_lecturas(iguales), resumen_de_lecturas(iguales))
    )
    assert terna.victoria + terna.empate + terna.derrota == pytest.approx(1.0)
    assert terna.victoria > terna.derrota, "el ordinal traía su propia ventaja de local"
