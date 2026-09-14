"""Habilidades: profundidad, cuello de botella y la subida que más rinde.

Las tres son funciones puras; aquí se prueban sin base de datos."""

from app.application.queries.flor_de_fuerza import SectoresDeEquipo
from app.application.queries.habilidades import (
    Jugador,
    formacion,
    profundidad,
    sectores,
    subidas,
)

CERO = dict.fromkeys(
    ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"), 1
)


MOTOR = {"form": 7, "stamina": 7, "experience": 5, "loyalty": 0}


def _j(
    nombre: str, codigo: int | None, en_el_once: bool = True, lesionado: bool = False, **skills: int
) -> Jugador:
    return Jugador(
        ht_player_id=abs(hash(nombre)) % 10_000,
        name=nombre,
        short_name=nombre,
        age=28,
        tsi=1000,
        skills={**CERO, **skills},
        injured=lesionado,
        position_code=codigo,
        in_lineup=en_el_once,
        motor=MOTOR,
    )


def _profundidad(plantilla: list[Jugador]):
    once = {j.ht_player_id: j.grupo for j in plantilla if j.in_lineup and j.grupo}
    return {p.key: p for p in profundidad(plantilla, once)}


def test_con_otra_formacion_el_central_que_sobra_pasa_al_banquillo() -> None:
    """De 3 a 2 Defensas Centrales: siguen los dos mejores y el tercero pasa a
    ser el recambio."""
    from app.application.queries.habilidades import once_para_formacion

    plantilla = [
        _j("Portero", 100, keeper=15),
        _j("Bordalás", 102, defending=18),
        _j("Teano", 103, defending=16),
        _j("Zulhadi", 104, defending=15),
        _j("Lateral D", 101, defending=14, winger=10),
        _j("Lateral I", 105, defending=14, winger=10),
        _j("Medio", 108, playmaking=12),
        _j("Extremo D", 106, winger=15, playmaking=10),
        _j("Extremo I", 110, winger=15, playmaking=10),
        _j("Delantero 1", 111, scoring=16, passing=12),
        _j("Delantero 2", 113, scoring=15, passing=12),
        _j("Suplente medio", None, en_el_once=False, playmaking=11),
    ]
    once_real = [j for j in plantilla if j.in_lineup]
    once = once_para_formacion(plantilla, once_real, "4-4-2", 2, 2)
    assert sorted(once.values()).count("central_defender") == 2
    assert sorted(once.values()).count("inner_midfield") == 2
    centrales = {p.key: p for p in profundidad(plantilla, once)}["central_defender"]
    assert centrales.starters == 2
    assert centrales.substitute is not None and centrales.substitute.name == "Zulhadi"


def test_con_tres_centrales_entra_el_cuarto_y_no_el_segundo() -> None:
    """El segundo mejor defensa también es titular: si se lesiona el mejor,
    entra el mejor del banquillo."""
    plantilla = [
        _j("Bordalás", 102, defending=18),
        _j("Teano", 103, defending=16),
        _j("Zulhadi", 104, defending=16),
        _j("Guastavino", None, en_el_once=False, defending=12),
        _j("Suplente flojo", None, en_el_once=False, defending=6),
    ]
    centrales = _profundidad(plantilla)["central_defender"]
    assert centrales.label == "Defensas Centrales" and centrales.starters == 3
    assert centrales.best is not None and centrales.best.name == "Bordalás"
    assert centrales.substitute is not None and centrales.substitute.name == "Guastavino"
    assert centrales.drop_pct is not None and centrales.drop_pct > 0


def test_con_dos_delanteros_entra_el_tercero_por_rendimiento_y_no_lesionado() -> None:
    """El recambio se ordena por rendimiento en el puesto, no por Anotación
    sola, y un lesionado no puede entrar."""
    plantilla = [
        _j("Gutiérrez", 111, scoring=18, passing=13),
        _j("Njakanirina", 113, scoring=15, passing=13),
        _j("Lesionado", None, en_el_once=False, lesionado=True, scoring=16, passing=12),
        _j("Solo anota", None, en_el_once=False, scoring=9, passing=1),
        _j("Completo", None, en_el_once=False, scoring=8, passing=14),
    ]
    delanteros = _profundidad(plantilla)["forward"]
    assert delanteros.starters == 2
    assert delanteros.substitute is not None and delanteros.substitute.name == "Completo"
    assert delanteros.tone == "danger"


def test_el_mismo_recambio_de_dos_puestos_se_avisa() -> None:
    plantilla = [
        _j("Central", 103, defending=16),
        _j("Lateral", 101, defending=15, winger=10),
        _j("Comodín", None, en_el_once=False, defending=12, winger=8),
    ]
    filas = _profundidad(plantilla)
    assert filas["central_defender"].also_covers == ["Defensas Laterales"]
    assert filas["wingback"].also_covers == ["Defensas Centrales"]


def test_un_jugador_de_campo_no_es_recambio_de_portero() -> None:
    """Con los datos reales salía Bahlek (Portería 1) de recambio de Ebbesen:
    su Defensa y su forma le daban más rendimiento que al portero veterano.
    Quien no llega a débil (4) en la habilidad del puesto no cuenta."""
    plantilla = [
        _j("Ebbesen", 100, keeper=15),
        _j("Bahlek", None, en_el_once=False, keeper=1, defending=13),
        _j("Horhoi", None, en_el_once=False, keeper=5),
    ]
    porteros = _profundidad(plantilla)["keeper"]
    assert porteros.substitute is not None and porteros.substitute.name == "Horhoi"


def test_si_el_recambio_ya_esta_ocupado_se_dice_quien_viene_despues() -> None:
    plantilla = [
        _j("Delantero", 111, scoring=16, passing=10),
        _j("Primero", None, en_el_once=False, scoring=12, passing=10),
        _j("Segundo", None, en_el_once=False, scoring=9, passing=8),
    ]
    delanteros = _profundidad(plantilla)["forward"]
    assert delanteros.substitute is not None and delanteros.substitute.name == "Primero"
    assert delanteros.next_substitute is not None
    assert delanteros.next_substitute.name == "Segundo"


def test_cada_sector_se_mide_contra_la_serie_y_no_contra_los_otros() -> None:
    """El mediocampo va en otra escala que defensa y ataque: comparado entre
    sectores salía un cuarto de la defensa. Frente a la serie, 20 de medio
    puede ser el mejor de todos."""
    once = [_j("Interior", 108, playmaking=12)]
    serie = [
        SectoresDeEquipo(1, "Propio", True, 5, medio=12.0, defensa=230.0, ataque=90.0),
        SectoresDeEquipo(2, "A", False, 5, medio=20.0, defensa=200.0, ataque=80.0),
        SectoresDeEquipo(3, "B", False, 5, medio=16.0, defensa=180.0, ataque=120.0),
    ]
    salida = {s.key: s for s in sectores(serie, once)}
    assert salida["mediocampo"].series_position == 0.0
    assert salida["mediocampo"].margin_pct == -40.0 and salida["mediocampo"].best_rival == "A"
    assert salida["mediocampo"].best_rival_value == 20.0
    assert salida["mediocampo"].who == "Interior (Jug 12)"
    assert salida["mediocampo"].tone == "danger"
    assert salida["defensa"].series_position == 100.0 and salida["defensa"].tone == "ok"
    assert salida["ataque"].tone == "warning" and salida["ataque"].verdict == "Por detrás"


def test_si_lidera_todo_el_cuello_es_el_sector_con_menos_ventaja() -> None:
    """Liderar los tres sectores dejaba los tres en 100 y sin cuello de
    botella. Empatado en mediocampo con el segundo, ése es el que hay que
    subir."""
    once = [_j("Interior", 108, playmaking=12)]
    serie = [
        SectoresDeEquipo(1, "Propio", True, 5, medio=16.8, defensa=211.0, ataque=90.0),
        SectoresDeEquipo(2, "LosNeithas", False, 5, medio=16.8, defensa=116.0, ataque=55.0),
        SectoresDeEquipo(3, "Otro", False, 5, medio=13.0, defensa=75.0, ataque=44.0),
    ]
    salida = sectores(serie, once)
    assert all(s.series_position == 100.0 for s in salida)
    cuello = min(salida, key=lambda s: s.margin_pct)
    assert cuello.key == "mediocampo" and cuello.margin_pct == 0.0
    assert cuello.verdict == "Sin ventaja"


def test_la_subida_que_mas_rinde_es_la_del_unico_interior() -> None:
    once = [
        _j("Interior", 108, playmaking=12),
        _j("Extremo D", 106, playmaking=11),
        _j("Extremo I", 110, playmaking=11),
    ]
    mejores = subidas(once, "mediocampo")
    assert mejores[0].player == "Interior" and mejores[0].skill == "playmaking"
    assert mejores[0].impact == "Alto"
    # Un extremo aporta a jugadas 0,45 de lo que aporta un interior.
    assert mejores[1].skill == "playmaking" and mejores[1].impact == "Medio"


def test_la_formacion_sale_del_once() -> None:
    once = [_j("P", 100)] + [_j(f"D{i}", c) for i, c in enumerate((101, 102, 103, 104, 105))]
    once += [_j("I", 108), _j("E1", 106), _j("E2", 110), _j("F1", 111), _j("F2", 113)]
    assert formacion(once) == "5-3-2"
