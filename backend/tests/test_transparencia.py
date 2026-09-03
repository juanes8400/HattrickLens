"""El catálogo tiene que LEER las constantes, no repetirlas.

Es la única promesa que hace la pantalla de Transparencia. Si un catálogo
escrito a mano se desincroniza del motor, la página que existe para dar
confianza pasa a ser la que miente, y encima en silencio.
"""

from __future__ import annotations

from app.application.queries.transparencia import catalogo, como_json
from app.domain.engines import htms, training_engine
from app.domain.engines.economy_engine import HOME_MATCHES_PER_SEASON, SEASON_WEEKS
from app.domain.engines.season_simulator import HOME_ADVANTAGE, SHRINKAGE_K
from app.domain.engines.youth_skill_score import (
    DEFAULT_WEIGHT_BASE,
    SQUAD_NORMALISER,
    weights_for,
)
from app.domain.engines.youth_training_plan import SECUNDARIO_DUPLICADO
from app.domain.value_objects.stamina_reference import (
    STAMINA_FORECAST_TABLE,
    STAMINA_TRAINING_PCT_BUCKETS,
)


def _calculo(calc_id: str):
    for seccion in catalogo():
        for calc in seccion.calcs:
            if calc.id == calc_id:
                return calc
    raise AssertionError(f"no existe el cálculo {calc_id}")


def _constante(calc_id: str, symbol: str) -> str:
    calc = _calculo(calc_id)
    for k in calc.constants:
        if k.symbol == symbol:
            return k.value
    raise AssertionError(f"{calc_id} no publica la constante {symbol}")


def test_las_constantes_salen_de_los_motores() -> None:
    """Cada número publicado coincide con el del motor que lo define.

    Si alguien cambia `SHRINKAGE_K` y la pantalla sigue diciendo 5, este test
    es lo único que lo dice.
    """
    assert _constante("simulacion", "K") == str(int(SHRINKAGE_K))
    assert _constante("simulacion", "ventaja_local") == f"{HOME_ADVANTAGE:.4g}"
    assert _constante("estructural", "semanas por temporada") == str(SEASON_WEEKS)
    assert _constante("estructural", "partidos en casa") == str(HOME_MATCHES_PER_SEASON)
    assert _constante("puntaje", "β") == str(int(DEFAULT_WEIGHT_BASE))
    assert _constante("puntaje", "normalizador") == str(SQUAD_NORMALISER)


def test_cambiar_la_constante_cambia_la_pantalla() -> None:
    """La prueba de verdad de que se LEE y no se repite.

    El test de arriba compara el catálogo con el motor, pero los dos leen la
    misma constante: si alguien sustituyera el valor por un «5» tecleado,
    hoy seguiría coincidiendo. Aquí se mueve la constante de sitio y se exige
    que la pantalla se mueva con ella.
    """
    import importlib

    from app.domain.engines import season_simulator

    original = season_simulator.SHRINKAGE_K
    try:
        season_simulator.SHRINKAGE_K = 42.0
        modulo = importlib.reload(importlib.import_module("app.application.queries.transparencia"))
        publicado = next(
            k.value
            for s in modulo.catalogo()
            for c in s.calcs
            if c.id == "simulacion"
            for k in c.constants
            if k.symbol == "K"
        )
        assert publicado == "42", "el catálogo no siguió a la constante: está tecleada a mano"
    finally:
        season_simulator.SHRINKAGE_K = original
        importlib.reload(importlib.import_module("app.application.queries.transparencia"))


def test_la_escalera_de_juveniles_se_dibuja_con_los_pesos_reales() -> None:
    """Los ocho peldaños, con el peso que el motor calcula para cada uno."""
    formula = _calculo("puntaje").formula
    pesos = weights_for()
    for bucket, peso in pesos.items():
        if peso == 0:
            # El que ya tocó techo no es un peldaño: pesa cero y se dice aparte.
            assert "al_tope" in formula
            continue
        assert str(bucket) in formula, bucket
    assert "81" in formula and "27" in formula, "faltan los peldaños altos"


def test_el_total_del_individual_sale_de_la_penalizacion_real() -> None:
    """133,3 % no es un número tecleado: es 100 % + 2/3 × 1/2."""
    formula = _calculo("individual").formula
    assert f"{1 + SECUNDARIO_DUPLICADO:.1%}" in formula


def test_cada_calculo_declara_hasta_donde_vale() -> None:
    """Una fórmula sin límites declarados es una promesa sin letra pequeña.

    Es la mitad del valor de esta pantalla: saber qué NO cubre el modelo.
    """
    sin_limites = [f"{s.name} → {c.name}" for s in catalogo() for c in s.calcs if not c.limits]
    assert not sin_limites, "cálculos sin límites declarados: " + ", ".join(sin_limites)


def test_cada_calculo_dice_de_donde_salen_sus_datos() -> None:
    """Una formula sin sus fuentes dice como se hace la cuenta pero no de
    donde salen los sumandos, que es la pregunta que trae el usuario.

    2026-08-31, pedido explicito: «faltan las fuentes de los numeros como
    condicion, experiencia, semanas de entrenamiento».
    """
    sin_fuentes = [f"{s.name} → {c.name}" for s in catalogo() for c in s.calcs if not c.sources]
    assert not sin_fuentes, "calculos sin fuentes: " + ", ".join(sin_fuentes)

    # Los tres que el usuario nombro tienen que existir y estar cubiertos.
    for calc_id in ("condicion", "experiencia", "semanas-al-pop"):
        assert _calculo(calc_id).sources


def test_no_se_nombra_la_herramienta_de_la_que_se_porto_el_modelo() -> None:
    """2026-08-31, pedido explicito: «no menciones a Hattrick Control»."""
    assert "Hattrick Control" not in str(como_json())


def test_el_catalogo_no_nombra_la_api() -> None:
    """Misma regla que el resto de la interfaz: esto se pinta entero."""
    plano = str(como_json())
    assert "CHPP" not in plano
    assert ".xml" not in plano


def test_los_paneles_vivos_de_motor_siguen_enganchados() -> None:
    """Motor se absorbió, no se tiró: sus cuatro paneles conservan su sitio."""
    vivos = {c.live for s in catalogo() for c in s.calcs if c.live}
    assert vivos == {
        "trainingFormula",
        "experienceModel",
        "loyaltyModel",
        "positionModel",
    }


def test_el_once_optimo_publica_su_objetivo_y_todas_sus_decisiones() -> None:
    """Transparencia describe el algoritmo real, no un ambiguo «rating total».

    Formación, reparto de jugadores y órdenes individuales se deciden juntos.
    Además debe quedar claro qué pasa al fijar una orden y que los sectores se
    enseñan después: ninguno de esos matices se puede deducir de la fórmula
    vieja, que sólo mostraba jugador por silla.
    """
    calculo = _calculo("once-optimo")
    texto = " ".join(
        [
            calculo.answers,
            calculo.formula,
            *calculo.steps,
            *calculo.limits,
            calculo.note,
        ]
    ).lower()

    assert "formación" in texto
    assert "jugador" in texto and "casilla" in texto
    assert "orden" in texto and "legal" in texto
    assert "positions.yaml" in texto and "manual no escrito" in texto
    assert "restringe sólo su casilla" in texto
    assert "calificación por sector" in texto and "no interviene" in texto
    assert "no es una predicción" in texto


def test_los_coeficientes_salen_con_todos_sus_decimales() -> None:
    """2026-08-31, pedido del usuario: «pon todos los parámetros numéricos».

    El primer intento formateaba con cuatro cifras y publicaba 6,09 donde la
    fórmula usa 6,0896. En una pantalla que se llama Transparencia, redondear
    el coeficiente es contar media verdad: el usuario no puede reproducir la
    cuenta con el número que le enseñas.
    """
    curva = training_engine.parametros()["skill_curve"]
    formula = _calculo("semanas-al-pop").formula
    for clave in ("low_scale", "high_scale", "high_offset"):
        assert repr(float(curva[clave])) in formula, clave


def test_estan_los_catorce_coeficientes_de_entrenamiento() -> None:
    """Ninguno se queda fuera: el que falte es justo el que alguien busca."""
    tablas = {t.title: t for t in _calculo("semanas-al-pop").tables}
    coeficientes = training_engine.parametros()["training_coefficients"]
    tabla = next(t for k, t in tablas.items() if "K_entrenamiento" in k)
    assert len(tabla.rows) == len(coeficientes)
    valores = {fila[-1] for fila in tabla.rows}
    assert valores == {repr(float(v)) for v in coeficientes.values()}


def test_el_reloj_de_edad_sale_entero() -> None:
    reloj = training_engine.parametros()["age_clock"]["values"]
    tabla = next(t for t in _calculo("semanas-al-pop").tables if "Reloj" in t.title)
    assert len(tabla.rows) == len(reloj)
    assert tabla.rows[0][0] == str(training_engine.parametros()["age_clock"]["start_age"])


def test_la_tabla_de_condicion_sale_entera() -> None:
    """Las veinte edades por los cinco tramos, no sólo los extremos."""
    tabla = _calculo("condicion").tables[0]
    assert len(tabla.rows) == len(STAMINA_FORECAST_TABLE)
    assert len(tabla.columns) == len(STAMINA_TRAINING_PCT_BUCKETS) + 1
    assert all(len(fila) == len(tabla.columns) for fila in tabla.rows)


def test_ninguna_tabla_llega_vacia_a_la_pantalla() -> None:
    """Una tabla sin filas se dibuja como un marco vacío y parece un fallo."""
    for seccion in catalogo():
        for calculo in seccion.calcs:
            for tabla in calculo.tables:
                assert tabla.rows, f"{calculo.id} · {tabla.title}"
                assert tabla.columns


def test_el_htms_tiene_su_seccion_con_los_dos_calculos() -> None:
    """2026-08-31, pedido del usuario: HTMS y HTMS28, cada uno en su toggle."""
    seccion = next(s for s in catalogo() if s.id == "htms")
    assert [c.id for c in seccion.calcs] == ["htms-ability", "htms28"]


def test_el_paso_a_paso_del_htms_da_el_mismo_numero_que_el_motor() -> None:
    """El ejemplo no está escrito a mano: lo calcula el propio motor.

    Es la única forma de que siga siendo cierto. Un ejemplo copiado envejece
    en silencio y acaba enseñando una cuenta que la herramienta ya no hace.
    """
    from app.application.queries.transparencia import EJEMPLO_EDAD, EJEMPLO_HTMS

    total = htms.ability(*EJEMPLO_HTMS)
    assert str(total) in _calculo("htms-ability").steps[-1]
    esperado = htms.potential(total, *EJEMPLO_EDAD)
    assert str(esperado) in _calculo("htms28").steps[-1]


def test_la_tabla_de_puntos_del_htms_sale_entera() -> None:
    tabla = _calculo("htms-ability").tables[0]
    assert len(tabla.rows) == len(htms.TABLA)
    assert len(tabla.columns) == 8
    assert tabla.rows[-1][0] == str(htms.NIVEL_MAXIMO)


def test_el_ritmo_por_edad_sale_entero() -> None:
    tabla = _calculo("htms28").tables[0]
    assert len(tabla.rows) == len(htms.PUNTOS_POR_SEMANA)


def test_el_htms_lleva_su_credito() -> None:
    """El usuario lo pidió expreso: la fórmula no es nuestra y se dice."""
    for calc_id in ("htms-ability", "htms28"):
        nota = _calculo(calc_id).note
        assert "Foxtrick" in nota and "Fantamondi" in nota
        assert "no es nuestra" in nota
