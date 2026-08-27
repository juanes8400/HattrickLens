"""Las dos reglas que deciden si se entrena «Individual».

Dictadas por el usuario el 2026-08-26. Lo que se fija aquí es el
COMPORTAMIENTO en los bordes, que es donde una regla escrita en una frase se
vuelve ambigua: los dos umbrales son estrictos, y B manda sobre A.
"""

from app.domain.engines.decision_individual import (
    DESVIACION_MAXIMA,
    HABILIDADES_DE_PUESTO,
    INDIVIDUAL,
    RAZON_MINIMA,
    cola_de_descubrimiento,
    decidir,
)
from app.domain.engines.youth_skill_score import PlayerNote
from app.domain.engines.youth_training_plan import (
    ENTRENAMIENTOS,
    RITMO_INDIVIDUAL_DUDOSO,
    RITMO_INDIVIDUAL_POR_HABILIDAD,
    SECUNDARIO_NORMAL,
    cupos_de,
    ritmo_individual,
)

#: Los puestos, con el nombre corto del motor.
GK, CD, WB, WI, IM, FW = (
    "keeper",
    "central_defender",
    "wingback",
    "winger",
    "inner_midfield",
    "forward",
)

#: La academia del usuario el 2026-08-26: un extremo bueno y seis habilidades
#: empatadas en pura ignorancia. Es el caso que originó las reglas.
REAL = [
    ("winger", 1.92),
    ("keeper", 0.28),
    ("defending", 0.28),
    ("playmaking", 0.28),
    ("set_pieces", 0.28),
    ("passing", 0.28),
    ("scoring", 0.24),
]


def test_regla_a_con_los_datos_reales():
    d = decidir(REAL)
    assert d is not None
    assert d.regla == "A"
    assert d.principal == "winger"
    assert d.secundario == INDIVIDUAL
    assert round(d.razon or 0, 2) == 6.86
    assert d.descubre


def test_regla_b_cuando_nada_destaca():
    d = decidir([(f"h{i}", 0.30) for i in range(7)])
    assert d is not None
    assert d.regla == "B"
    assert d.principal == INDIVIDUAL
    assert d.secundario == INDIVIDUAL


def test_b_manda_cuando_las_dos_se_disparan():
    """Líder claro sobre un conjunto diminuto: razón 4,5 y desviación 0,245.

    Las dos reglas dicen cosas distintas y el usuario zanjó que mande B: si el
    mejor apenas roza 0,9, ese liderazgo es sobre nada.
    """
    caso = [("lider", 0.9)] + [(f"h{i}", 0.2) for i in range(6)]
    d = decidir(caso)
    assert d is not None
    assert d.razon is not None and d.razon > RAZON_MINIMA
    assert d.desviacion < DESVIACION_MAXIMA
    assert d.regla == "B"
    assert d.principal == INDIVIDUAL


def test_sin_individual_cuando_hay_dos_habilidades_de_verdad():
    d = decidir([("a", 2.0), ("b", 1.5), ("c", 0.9), ("d", 0.4), ("e", 0.3)])
    assert d is not None
    assert d.regla is None
    assert (d.principal, d.secundario) == ("a", "b")
    assert not d.descubre


def test_los_dos_umbrales_son_estrictos():
    """Exactamente 4x y exactamente 0,25 NO disparan: «más de», «menor que»."""
    justo_cuatro = [("a", 4.0), ("b", 1.0), ("c", 1.0)]
    d = decidir(justo_cuatro)
    assert d is not None and d.razon == RAZON_MINIMA and d.regla is None

    # Dos valores a distancia 0,25 del centro dan desviación 0,25 clavada.
    d2 = decidir([("a", 0.5), ("b", 0.0)])
    assert d2 is not None and d2.desviacion == DESVIACION_MAXIMA
    assert d2.regla == "A"  # no dispara B; sí A, porque el segundo es cero


def test_segundo_en_cero_es_lider_infinito():
    d = decidir([("a", 9.0), ("b", 0.0), ("c", 0.0)])
    assert d is not None
    assert d.razon == float("inf")
    assert d.regla == "A"
    assert d.secundario == INDIVIDUAL


def test_todo_a_cero_descubre():
    """Academia recién abierta: no se sabe nada de nadie. Desviación 0."""
    d = decidir([(f"h{i}", 0.0) for i in range(7)])
    assert d is not None
    assert d.regla == "B"
    assert d.razon is None


def test_sin_dos_habilidades_no_hay_veredicto():
    assert decidir([]) is None
    assert decidir([("a", 1.0)]) is None


# --------------------------------------------------------------------------
# «Individual» como entrenamiento normal del motor de siempre.
# --------------------------------------------------------------------------


def test_individual_es_un_entrenamiento_mas():
    """Vive en la misma tabla, así que los selectores lo ofrecen solos."""
    e = ENTRENAMIENTOS[INDIVIDUAL]
    assert e.label == "Individual"
    # Llega a los seis puestos: es lo que le deja tocar cinco habilidades de
    # una pasada en vez de una.
    assert {c.puesto for c in cupos_de(INDIVIDUAL)} == {
        "keeper",
        "central_defender",
        "wingback",
        "inner_midfield",
        "winger",
        "forward",
    }


def test_la_barrita_anuncia_la_mas_probable_que_no_sabemos():
    """Lo que se enseña en la plaza no es «la habilidad del puesto» —no la
    hay— sino la más probable DE LAS QUE FALTAN por descubrir: la plaza está
    ahí para eso, y nombrar una ya revelada no dice nada."""
    e = ENTRENAMIENTOS[INDIVIDUAL]
    # Sin contexto, la más probable a secas del puesto.
    assert e.skill_en(IM) == "playmaking"
    assert e.skill_en(FW) == "scoring"

    # Sabiendo ya Jugadas, un mediocentro pasa a anunciar la siguiente.
    assert e.skill_en(IM, {"defending", "passing", "set_pieces"}) == "defending"
    # Y si no queda nada por descubrir, no se inventa: cae en la más probable.
    assert e.skill_en(IM, set()) == "playmaking"


def test_la_probabilidad_de_descubrir_mide_la_plaza():
    e = ENTRENAMIENTOS[INDIVIDUAL]
    # Un chico del que no se sabe nada: la plaza acierta seguro.
    assert e.probabilidad_de_descubrir(IM, HABILIDADES_DE_PUESTO) == 100
    # Uno con todo revelado: la plaza se desperdicia en él.
    assert e.probabilidad_de_descubrir(IM, set()) == 0
    # Y en medio, la suma de la ruleta sobre lo que falta.
    assert e.probabilidad_de_descubrir(IM, {"playmaking", "set_pieces"}) == 49


def test_un_entrenamiento_normal_ignora_el_puesto():
    """`skill_en` es uniforme: quien pregunta no necesita saber cuál es cual."""
    for codigo in ("keeper", "defending", "passing", "set_pieces"):
        e = ENTRENAMIENTOS[codigo]
        assert e.skill_en("winger") == e.skill_en("forward") == e.skill


def test_individual_alcanza_las_siete():
    """Ninguna habilidad queda fuera. Todos los puestos pueden sacar Balón
    parado y casi todos Pases.

    Esta prueba decía lo contrario hasta el 2026-08-26 —afirmaba que Pases y
    Balón parado eran inalcanzables— y estaba mal. El usuario ya lo había
    dicho («existe una posibilidad de que Hattrick descubra Pases para un
    defensa») y el estudio del hilo 17350846 lo confirma.
    """
    e = ENTRENAMIENTOS[INDIVIDUAL]
    alcanzadas = {s for fila in (e.distribucion_por_puesto or {}).values() for s in fila}
    assert alcanzadas == set(HABILIDADES_DE_PUESTO)
    assert "passing" in alcanzadas
    assert "set_pieces" in alcanzadas


def test_cada_puesto_es_una_ruleta_que_suma_cien():
    for puesto, reparto in (ENTRENAMIENTOS[INDIVIDUAL].distribucion_por_puesto or {}).items():
        assert sum(reparto.values()) == 100, puesto


def test_el_ritmo_depende_de_la_habilidad_no_de_individual():
    """Anotación al 40 % y Pases al 100 %: un único «ritmo de Individual» no
    puede describir eso, y usarlo fue el segundo error del 2026-08-26."""
    assert ritmo_individual(FW, "scoring") == 40.0
    assert ritmo_individual(FW, "passing") == 100.0
    # La defensa del portero es la única excepción por puesto.
    assert ritmo_individual(GK, "defending") == 82.0
    assert ritmo_individual(CD, "defending") == 68.5


def test_reproduce_el_ejemplo_publicado_por_glynzales():
    """La prueba que vale por todas: una fuente AJENA a nosotros.

    Post #13 del hilo 17350846 (2020-07-13). Defensa de principal, Individual
    de secundario, mirando a un defensa central. glynzales publica tanto los
    cuatro casos del sorteo como la media, y el modelo
    `probabilidad × ritmo × 2/3` tiene que reproducir las ocho cifras.

    Si alguien toca la tabla de probabilidades o los ritmos, esto lo caza
    contra un número que no escribimos nosotros.
    """
    reparto = (ENTRENAMIENTOS[INDIVIDUAL].distribucion_por_puesto or {})[CD]
    assert reparto == {"defending": 37, "playmaking": 27, "passing": 26, "set_pieces": 10}

    # Lo que recibe segun que salga en la ruleta, con el principal al 100 %.
    def recibe(skill: str) -> float:
        return ritmo_individual(CD, skill) * SECUNDARIO_NORMAL

    assert round(100 + recibe("defending")) == 146
    assert round(recibe("playmaking")) == 38
    assert round(recibe("passing")) == 67
    assert round(recibe("set_pieces")) == 67

    # Y la media por partido: 117 def + 17 pas + 10 pm + 7 bp = 151.
    medias = {s: reparto[s] / 100 * recibe(s) for s in reparto}
    assert round(100 + medias["defending"]) == 117
    assert round(medias["passing"]) == 17
    assert round(medias["playmaking"]) == 10
    assert round(medias["set_pieces"]) == 7
    assert round(100 + sum(medias.values())) == 151


def test_lo_que_el_estudio_no_midio_queda_marcado():
    """Balón parado es lo único que sigue sin medir: su autor pone «guess!».

    Portería salió de aquí el 2026-08-26: el estudio la dejaba en «?» y el
    usuario la confirmó en 100%, así que ya no es conjetura nuestra. El número
    no cambió —era 100 antes y después—; lo que cambió es de quién es.

    La lista NO dice «este número es dudoso»: dice «este número no se midió».
    Los dos valen 100% y el usuario los da por buenos.
    """
    assert "set_pieces" in RITMO_INDIVIDUAL_DUDOSO
    assert "keeper" not in RITMO_INDIVIDUAL_DUDOSO
    assert len(RITMO_INDIVIDUAL_DUDOSO) == 1
    # El número no cambió al confirmarse: las dos valen 100%.
    assert RITMO_INDIVIDUAL_POR_HABILIDAD["keeper"] == 100.0
    assert RITMO_INDIVIDUAL_POR_HABILIDAD["set_pieces"] == 100.0


def _nota(nombre: str, *, pronto: bool = False, techo: int = 0) -> PlayerNote:
    return PlayerNote(
        name=nombre,
        note=None,
        bucket="desconocido_tarde",
        leaves_soon=pronto,
        max_reached=False,
        htms28_max=techo,
    )


def test_la_cola_pone_delante_a_quien_mas_ilumina():
    notas = [_nota("leido"), _nota("tapado"), _nota("medio")]
    orden = cola_de_descubrimiento(notas, {"leido": 0, "tapado": 5, "medio": 2})
    assert [n.name for n in orden] == ["tapado", "medio", "leido"]


def test_entre_igual_de_tapados_manda_el_que_se_va():
    """O lo miras ahora o no lo miras: el que se queda tendrá su turno."""
    notas = [_nota("se_queda"), _nota("se_va", pronto=True)]
    orden = cola_de_descubrimiento(notas, {"se_queda": 3, "se_va": 3})
    assert [n.name for n in orden] == ["se_va", "se_queda"]


def test_y_luego_el_de_mas_potencial():
    notas = [_nota("flojo", techo=100), _nota("crack", techo=900)]
    orden = cola_de_descubrimiento(notas, {"flojo": 3, "crack": 3})
    assert [n.name for n in orden] == ["crack", "flojo"]
