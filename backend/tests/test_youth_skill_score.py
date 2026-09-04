"""Puntaje por habilidad de la academia — portado de `JUvens.xlsx`.

La hoja del usuario ES la especificación, así que estas pruebas reproducen sus
números, no números inventados: los conteos son los de `AuxiJuveniles` del
2026-08-17 y los puntajes esperados son los que la propia hoja tenía
calculados en ese momento.
"""
import pytest

from app.domain.engines import youth_skill_score as ys


def _candidate(name: str, days_at_deadline: int, **skills: ys.YouthSkillReading):
    return ys.YouthCandidate(
        name=name,
        age_years_at_deadline=17,
        age_days_at_deadline=days_at_deadline,
        skills={s: skills.get(s, ys.YouthSkillReading(None, None)) for s in ys.SKILLS},
    )


# ── La nota de una habilidad (`Juveniles!AF`) ────────────────────────────────

def test_la_nota_es_el_techo_y_solo_el_techo() -> None:
    """2026-08-24: antes era `MAX(max, actual)`, y eso mezclaba dos cosas.

    Lo que decide cuanto vale desarrollar a alguien es hasta donde puede
    llegar, no donde esta hoy.
    """
    assert ys.skill_note(ys.YouthSkillReading(current=6, maximum=8)) == 8
    assert ys.skill_note(ys.YouthSkillReading(current=None, maximum=5)) == 5


def test_un_nivel_bajo_con_el_techo_sin_revelar_no_es_un_techo_bajo() -> None:
    """El caso Fabian Ochoa: Pases nivel 2, techo desconocido.

    Con la regla vieja caia al ultimo peldaño como si el 2 fuera su limite.
    Un 2 solo fija un suelo --su techo es 2 o mas-- y podria ser 8, asi que
    va donde van los desconocidos, no al fondo.
    """
    assert ys.skill_note(ys.YouthSkillReading(current=2, maximum=None)) is None
    assert ys.skill_note(ys.YouthSkillReading(current=7, maximum=None)) is None


def test_a_capped_skill_scores_nothing_however_high_it_is() -> None:
    """`(1 - {})`: entrenar algo que ya tocó techo es tiempo tirado. Un 8
    topado no vale más que un desconocido — vale menos, porque del
    desconocido aún se puede esperar algo."""
    topada = ys.YouthSkillReading(current=8, maximum=8, max_reached=True)
    assert ys.skill_note(topada) is None
    assert ys.skill_note(ys.YouthSkillReading(current=8, maximum=8)) == 8


def test_nothing_known_is_none_not_zero() -> None:
    assert ys.skill_note(ys.YouthSkillReading(None, None)) is None


# ── Los cubos (`AuxiJuveniles`) ──────────────────────────────────────────────

def test_excellent_ignores_the_deadline_but_the_rest_does_not() -> None:
    """`B2` es un COUNTIF sin filtro de edad; `D2`/`F2` son COUNTIFS que sí lo
    llevan. Un crack se aprovecha aunque le queden tres semanas; un "bueno" a
    tres semanas no da tiempo a entrenarlo y por eso pesa distinto."""
    assert ys.bucket_of(8, leaves_soon=True) == ys.Bucket.EXCELLENT
    assert ys.bucket_of(8, leaves_soon=False) == ys.Bucket.EXCELLENT
    assert ys.bucket_of(7, leaves_soon=True) == ys.Bucket.GOOD_SOON
    assert ys.bucket_of(7, leaves_soon=False) == ys.Bucket.GOOD_LATER


def test_below_acceptable_tiene_su_cubo_pero_no_puntua() -> None:
    """El 5 y por debajo se CUENTA, y sigue sin valer nada.

    2026-09-04, pedido del usuario. Antes no caía en ningún cubo, y entonces
    revelar un techo bajo restaba uno de «desconocido» sin sumarlo en ninguna
    parte: la fila dejaba de sumar la plantilla y el puntaje bajaba sin que
    nada en pantalla lo explicara. Ahora tiene grupo propio, con peso cero.
    """
    assert ys.bucket_of(5, leaves_soon=True) == ys.Bucket.TOO_LOW
    assert ys.bucket_of(0, leaves_soon=False) == ys.Bucket.TOO_LOW
    assert ys.bucket_of(None, leaves_soon=True) == ys.Bucket.UNKNOWN_SOON
    # Lo que no puede pasar bajo ningún concepto: que aporte puntaje.
    assert ys.weights_for(3.0)[ys.Bucket.TOO_LOW] == 0.0
    assert ys.weights_for(1.0)[ys.Bucket.TOO_LOW] == 0.0


def test_contar_a_los_insuficientes_no_mueve_ningun_puntaje() -> None:
    """La red de seguridad del cambio.

    Añadir un cubo con peso cero no puede alterar una sola cifra: si algún
    puntaje se mueve, es que el cubo se coló en la suma.
    """
    candidatos = [
        _candidate("Bueno", 100, winger=ys.YouthSkillReading(4, 8)),
        _candidate("Justo", 100, winger=ys.YouthSkillReading(3, 6)),
        _candidate("Flojo", 100, winger=ys.YouthSkillReading(2, 5)),
        _candidate("Peor", 100, winger=ys.YouthSkillReading(1, 3)),
    ]
    fila = next(r for r in ys.score_skills(candidatos) if r.skill == "winger")
    # Los dos de techo bajo están contados...
    assert fila.counts[ys.Bucket.TOO_LOW] == 2
    # ...y el puntaje es exactamente el de los otros dos, ni más ni menos.
    solos = [candidatos[0], candidatos[1]]
    sin_ellos = next(r for r in ys.score_skills(solos) if r.skill == "winger")
    assert fila.score == sin_ellos.score


# ── El puntaje completo, contra la hoja real ────────────────────────────────

@pytest.mark.parametrize(
    ("skill", "unknown_soon", "trainable", "unknown_later", "acceptable_later", "expected"),
    [
        # AuxiJuveniles, 2026-08-17. Columnas L (?≤38d), M (Entrenables),
        # N (?>38d) y J (Aceptable >38d); el resto estaban a cero.
        ("keeper", 11, 1, 4, 0, 0.2453703704),
        ("defending", 11, 5, 4, 0, 0.2731481481),
        ("playmaking", 11, 5, 4, 0, 0.2731481481),
        ("winger", 10, 3, 4, 0, 0.2384259259),
        ("passing", 12, 8, 3, 1, 0.3750000000),
        ("scoring", 11, 3, 4, 0, 0.2592592593),
        ("set_pieces", 12, 11, 4, 0, 0.3356481481),
    ],
)
def test_the_score_reproduces_the_spreadsheet(
    skill: str,
    unknown_soon: int,
    trainable: int,
    unknown_later: int,
    acceptable_later: int,
    expected: float,
) -> None:
    """`AuxiJuveniles!O11` al decimal, con los conteos reales de esa fecha."""
    candidates: list[ys.YouthCandidate] = []
    desconocida = ys.YouthSkillReading(None, None)
    # "Aceptable" es un TECHO de 6. Con la regla vieja bastaba con jugar a 6
    # sin techo revelado; desde el 2026-08-24 eso es un desconocido.
    aceptable = ys.YouthSkillReading(current=6, maximum=6)

    for i in range(unknown_soon):
        candidates.append(_candidate(f"pronto{i}", 10, **{skill: desconocida}))
    for i in range(unknown_later):
        candidates.append(_candidate(f"tarde{i}", 90, **{skill: desconocida}))
    for i in range(acceptable_later):
        candidates.append(_candidate(f"aceptable{i}", 90, **{skill: aceptable}))

    scores = {s.skill: s for s in ys.score_skills(candidates, {skill: trainable})}
    assert scores[skill].score == pytest.approx(expected, abs=1e-9)


def test_the_ranking_puts_the_skill_worth_training_first() -> None:
    """El caso real del 2026-08-17: Pases era la habilidad a entrenar, por
    delante de Balón parado, y Lateral la última."""
    candidates: list[ys.YouthCandidate] = []
    desconocida = ys.YouthSkillReading(None, None)
    for i in range(12):
        candidates.append(
            _candidate(
                f"chico{i}", 10,
                passing=ys.YouthSkillReading(current=6, maximum=6) if i == 0 else desconocida,
                set_pieces=desconocida,
                winger=desconocida if i < 10 else ys.YouthSkillReading(None, None),
            )
        )
    ranking = ys.score_skills(candidates, {"passing": 8, "set_pieces": 11, "winger": 3})
    assert [s.skill for s in ranking][:2] == ["passing", "set_pieces"]
    assert ranking[0].score > ranking[1].score


def test_trainable_defaults_to_zero_and_never_to_a_guess() -> None:
    """`Entrenables` se teclea a mano en la hoja. Sin ese dato el sumando no
    participa — lo que NO se hace es estimarlo."""
    c = [_candidate("uno", 10, passing=ys.YouthSkillReading(current=7, maximum=7))]
    sin_dato = {s.skill: s for s in ys.score_skills(c)}["passing"]
    con_dato = {s.skill: s for s in ys.score_skills(c, {"passing": 9})}["passing"]

    assert sin_dato.trainable_count == 0
    assert con_dato.score > sin_dato.score
    assert con_dato.score - sin_dato.score == pytest.approx(
        ys.TRAINABLE_WEIGHT * 9 / ys.SQUAD_NORMALISER
    )


# ── Los mandos: método del usuario, números de cualquiera ────────────────────

def test_base_three_is_exactly_the_spreadsheet_ladder() -> None:
    """La escalera por defecto tiene que dar los pesos tal cual de la hoja."""
    w = ys.weights_for(3.0)
    assert w[ys.Bucket.EXCELLENT] == pytest.approx(81)
    assert w[ys.Bucket.GOOD_SOON] == pytest.approx(27)
    assert w[ys.Bucket.GOOD_LATER] == pytest.approx(9)
    assert w[ys.Bucket.ACCEPTABLE_SOON] == pytest.approx(3)
    assert w[ys.Bucket.ACCEPTABLE_LATER] == pytest.approx(1)
    assert w[ys.Bucket.UNKNOWN_SOON] == pytest.approx(1 / 3)
    assert w[ys.Bucket.UNKNOWN_LATER] == pytest.approx(1 / 27)
    # "Entrenables" es el peldaño -2, entre los dos desconocidos.
    assert ys.trainable_weight_for(3.0) == pytest.approx(1 / 9)


def test_a_flatter_base_stops_one_crack_from_deciding_everything() -> None:
    """Con base alta manda el mejor cubo; con base cerca de 1 todos los
    peldaños se parecen y gana la cantidad. Ése es el mando: cuánto vale
    tener UNO bueno frente a tener MUCHOS regulares."""
    uno_bueno = _candidate("crack", 90, passing=ys.YouthSkillReading(current=7, maximum=7))
    muchos_aceptables = [
        _candidate(f"n{i}", 90, scoring=ys.YouthSkillReading(current=6, maximum=6))
        for i in range(6)
    ]
    equipo = [uno_bueno, *muchos_aceptables]

    empinada = {s.skill: s.score for s in ys.score_skills(equipo, weight_base=5.0)}
    plana = {s.skill: s.score for s in ys.score_skills(equipo, weight_base=1.2)}

    assert empinada["passing"] > empinada["scoring"]
    assert plana["scoring"] > plana["passing"]


def test_moving_the_deadline_cut_moves_players_between_buckets() -> None:
    """El 38 es una opinión sobre cuánto tiempo hace falta para entrenar a
    alguien. Subirlo mete a más gente en el cubo "sale pronto", que pesa
    distinto."""
    equipo = [_candidate("justo", 40, passing=ys.YouthSkillReading(current=7, maximum=7))]

    con_38 = {s.skill: s for s in ys.score_skills(equipo, soon_max_days=38)}["passing"]
    con_50 = {s.skill: s for s in ys.score_skills(equipo, soon_max_days=50)}["passing"]

    assert con_38.counts[ys.Bucket.GOOD_LATER] == 1
    assert con_50.counts[ys.Bucket.GOOD_SOON] == 1
    # Y el puntaje cambia con él: "sale pronto" pesa un peldaño más.
    assert con_50.score > con_38.score


def test_the_block_methods_take_the_max_per_position_not_the_sum() -> None:
    """Métodos 3/4/5: mide cuán determinante es la habilidad ALLÍ DONDE SE USA.

    Con la suma, una habilidad concentrada en un solo puesto quedaba enterrada
    bajo otra repartida entre muchos — la portería salía 2 sobre 16 y entrenar
    portería no se recomendaría jamás. Ése era el artefacto que motivó el
    cambio de criterio el 2026-08-17.
    """
    posiciones = {
        # El arquero usa portería a tope, pero es UNA sola posición.
        "keeper": {"central_defence": {"keeper": 5.0}},
        # Defensa aparece repartida en tres puestos, sumando mucho más.
        "central_defender_a": {"central_defence": {"defending": 2.0}},
        "central_defender_b": {"central_defence": {"defending": 2.0}},
        "wingback": {"central_defence": {"defending": 1.0}, "side_defence": {"defending": 1.0}},
    }
    d = ys.block_trainable(ys.TrainableMethod.DEFENCE, posiciones)

    # Portería gana: 5,0 en su puesto contra los 2,0 del mejor defensa. Con
    # decimales, que es lo que distingue a dos habilidades vecinas.
    assert d["keeper"] == pytest.approx(ys.SQUAD_NORMALISER)
    assert d["defending"] == pytest.approx(2.0 / 5.0 * ys.SQUAD_NORMALISER)
    # Lo que no aparece en ninguna posición da 0, que es un dato, no un hueco.
    assert d["scoring"] == 0


def test_within_one_position_the_blocks_sectors_are_added_up() -> None:
    """Un interior aporta a ataque central y a ataque lateral: las dos cosas
    son ataque SUYO y se suman antes de comparar con las demás posiciones."""
    posiciones = {
        "inner": {"central_attack": {"passing": 0.3}, "side_attack": {"passing": 0.2}},
        "winger": {"side_attack": {"winger": 0.5}},
    }
    a = ys.block_trainable(ys.TrainableMethod.ATTACK, posiciones)
    assert a["passing"] == pytest.approx(ys.SQUAD_NORMALISER)
    assert a["winger"] == pytest.approx(ys.SQUAD_NORMALISER)


def test_a_block_nobody_contributes_to_gives_zeros_not_a_division_by_zero() -> None:
    assert set(ys.block_trainable(ys.TrainableMethod.MIDFIELD, {}).values()) == {0}


def test_the_senior_method_is_all_or_nothing() -> None:
    """Método 6, definido así por el usuario: 16 contra 0. Es la opción de
    quien quiere la cantera alineada con el primer equipo y no se plantea
    matices."""
    con = ys.senior_trainable("passing")
    assert con["passing"] == ys.SQUAD_NORMALISER
    assert all(v == 0 for k, v in con.items() if k != "passing")


def test_without_knowing_the_senior_training_nothing_is_pushed() -> None:
    """Si no se sabe qué entrena el primer equipo no se empuja ninguna
    habilidad — inventar cuál sería peor que no opinar."""
    assert set(ys.senior_trainable(None).values()) == {0}


def test_an_unknown_deadline_never_flips_bucket_with_the_slider() -> None:
    """2026-08-17, fallo real: el respaldo para "no se sabe cuándo se
    promociona" era `SOON_MAX_DAYS + 1`, un día por encima del umbral por
    defecto. Al subir el mando de 38 a 39 TODOS los canteranos sin ese dato
    volteaban de cubo a la vez y la pantalla daba un salto que parecía un
    cálculo y era un artefacto del respaldo.

    Ahora el respaldo queda fuera del alcance del mando (0–112).
    """
    sin_dato = ys.YouthCandidate(
        name="sin fecha",
        age_years_at_deadline=17,
        age_days_at_deadline=ys.UNKNOWN_DEADLINE_DAYS,
        skills={s: ys.YouthSkillReading(None, None) for s in ys.SKILLS},
    )
    for umbral in (0, 38, 39, 112):
        assert not ys.leaves_soon(sin_dato, soon_max_days=umbral)


def test_the_bonus_weight_can_be_moved_away_from_the_suggested_one() -> None:
    """El peso del bonus lo SUGIERE la escalera (peldaño -2), pero se mueve
    aparte: es el único sumando que no describe a la cantera sino cuánto
    quiere pesar el usuario ese criterio."""
    equipo = [_candidate("x", 90, passing=ys.YouthSkillReading(current=7, maximum=None))]
    sugerido = {s.skill: s.score for s in ys.score_skills(equipo, {"passing": 8})}["passing"]
    doble = {
        s.skill: s.score
        for s in ys.score_skills(
            equipo, {"passing": 8}, trainable_weight=ys.trainable_weight_for(3.0) * 2
        )
    }["passing"]
    assert doble > sugerido
    assert doble - sugerido == pytest.approx(ys.TRAINABLE_WEIGHT * 8 / ys.SQUAD_NORMALISER)


def test_the_slot_method_uses_the_real_training_shares() -> None:
    """Cuántas plazas de una alineación recibe cada entrenamiento: el portero
    entrena solo él, el balón parado les llega a los once. No sale de la
    cantera de nadie, así que son fijos."""
    d = ys.slot_trainable()
    assert set(d) == set(ys.SKILLS)
    assert d["keeper"] == 1
    assert d["set_pieces"] == 11
    assert d["passing"] == 8
    # Devuelve una copia: quien lo reciba puede tocarlo sin corromper la tabla.
    d["keeper"] = 99
    assert ys.slot_trainable()["keeper"] == 1
