"""Clases de Jugador (reglas del usuario, 2026-11-16)."""

from typing import Any

from app.domain.engines.clases_de_jugador import (
    CAROS,
    ECONOMICOS,
    ESTRELLAS,
    GANGAS,
    LADO_SUPLENTE,
    LADO_TITULAR,
    RESERVA,
    SUPLENCIA,
    TITULAR,
    formaciones_mas_entrenadas,
    partir_etapas,
    rentabilidad,
    repartir,
)
from app.domain.engines.lineup_optimizer import Assignment, Lineup, best_lineup

# ---------------------------------------------------------------- formaciones


def test_las_tres_con_mas_experiencia():
    xp = {"550": 10, "532": 7, "442": 5, "433": 3, "451": 2}
    assert formaciones_mas_entrenadas(xp) == ("5-5-0", "5-3-2", "4-4-2")


def test_si_la_tercera_empata_con_la_cuarta_se_usan_solo_dos():
    # El caso del usuario: 10, 7 y ocho formaciones empatadas a 3.
    xp = {"442": 3, "433": 3, "451": 3, "352": 3, "532": 7, "343": 3, "550": 10}
    assert formaciones_mas_entrenadas(xp) == ("5-5-0", "5-3-2")


def test_el_empate_que_arrastra_a_la_segunda_deja_solo_una():
    xp = {"550": 10, "532": 7, "442": 7, "433": 7}
    assert formaciones_mas_entrenadas(xp) == ("5-5-0",)


def test_sin_lectura_de_experiencia_no_hay_formaciones():
    assert formaciones_mas_entrenadas({}) == ()


def test_si_todas_empatan_se_usa_el_4_4_2():
    # Equipo nuevo: las diez formaciones al mismo nivel.
    xp = {k: 4 for k in ("550", "541", "532", "523", "451", "442", "433", "352", "343", "253")}
    assert formaciones_mas_entrenadas(xp) == ("4-4-2",)


def test_si_el_empate_de_arriba_se_las_lleva_todas_tambien_el_4_4_2():
    # Cuatro empatadas arriba y una por debajo: el corte no deja ninguna.
    xp = {"550": 6, "532": 6, "433": 6, "352": 6, "442": 2}
    assert formaciones_mas_entrenadas(xp) == ("4-4-2",)


# ---------------------------------------------------------------- titularidad


def _jugador(pid: int, valor: int, lesion: int = -1) -> dict[str, Any]:
    return {"ht_player_id": pid, "name": f"J{pid}", "valor": valor, "injury_level": lesion}


def _once_por_valor(tamano: int = 2):
    """Un motor de juguete: el «mejor once» son los `tamano` de más valor, y en
    la formación 5-3-2 juega además el de menos valor (para que las dos
    formaciones no saquen a los mismos). Con menos de `tamano`, deja huecos."""

    def once(jugadores: list[dict[str, Any]], formacion: str) -> Lineup:
        sanos = [j for j in jugadores if j["injury_level"] < 1]
        orden = sorted(sanos, key=lambda j: -j["valor"])
        elegidos = orden[:tamano]
        if formacion == "5-3-2" and len(orden) >= tamano:
            elegidos = orden[: tamano - 1] + [orden[-1]]
        return Lineup(
            formation=formacion,
            assignments=[
                Assignment(
                    slot=i,
                    position="x",
                    label=f"P{i}",
                    player=j,
                    rating=1.0,
                    confidence="",
                    base_position="x",
                )
                for i, j in enumerate(elegidos)
            ],
            total_rating=0.0,
            holes=[(i, "x") for i in range(len(elegidos), tamano)],
        )

    return once


def _quien(reparto, clase: str) -> set[int]:
    return {pid for pid, c in reparto.titularidad.items() if c == clase}


def test_titular_es_quien_entra_en_cualquiera_y_la_suplencia_sale_sin_ellos():
    jugadores = [_jugador(i, v) for i, v in enumerate([90, 80, 70, 60, 50, 40, 10], start=1)]
    reparto = repartir(jugadores, {"550": 10, "532": 7, "442": 1}, once=_once_por_valor())
    # 5-5-0: 1 y 2. 5-3-2: 1 y el 7 (el de menos valor). 4-4-2: 1 y 2.
    assert _quien(reparto, TITULAR) == {1, 2, 7}
    # Sin titulares: 5-5-0 → 3 y 4; 5-3-2 → 3 y 6; 4-4-2 → 3 y 4.
    assert _quien(reparto, SUPLENCIA) == {3, 4, 6}
    assert _quien(reparto, RESERVA) == {5}
    assert [o.formation for o in reparto.onces_titular] == ["5-5-0", "5-3-2", "4-4-2"]


def test_el_lesionado_cuenta_como_sano():
    jugadores = [_jugador(1, 90, lesion=3), _jugador(2, 80), _jugador(3, 70)]
    reparto = repartir(jugadores, {"550": 10}, once=_once_por_valor())
    assert _quien(reparto, TITULAR) == {1, 2}


def test_si_no_llegan_a_un_once_la_suplencia_deja_huecos():
    """«El Equipo B es el mejor once incompleto con esos 7: los pone en sus
    mejores puestos y deja huecos.»"""
    jugadores = [_jugador(1, 90), _jugador(2, 80), _jugador(3, 70)]
    reparto = repartir(jugadores, {"550": 10}, once=_once_por_valor())
    assert _quien(reparto, SUPLENCIA) == {3}
    assert _quien(reparto, RESERVA) == set()
    casillas = reparto.onces_suplencia[0].casillas
    assert [c.ht_player_id for c in casillas] == [3, None]


def test_sin_nadie_despues_de_los_titulares_no_hay_once_de_suplencia():
    jugadores = [_jugador(1, 90), _jugador(2, 80)]
    reparto = repartir(jugadores, {"550": 10}, once=_once_por_valor())
    assert reparto.onces_suplencia == ()
    assert _quien(reparto, TITULAR) == {1, 2}


def _de_campo(pid: int, nivel: int) -> dict[str, Any]:
    habilidades = dict.fromkeys(
        ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"), nivel
    )
    return {
        "ht_player_id": pid,
        "name": f"J{pid}",
        "age_years": 25,
        "age_days": 0,
        "form": 6,
        "stamina": 7,
        "experience": 5,
        "loyalty": 5,
        "leadership": 5,
        "specialty": 0,
        "injury_level": -1,
        "skills": habilidades,
    }


def test_alineacion_con_huecos_coloca_a_los_que_hay_y_marca_el_resto():
    lu = best_lineup([_de_campo(i, 8) for i in range(7)], "4-4-2", con_huecos=True)
    assert len(lu.assignments) == 7
    assert len(lu.holes) == 4
    assert {a.slot for a in lu.assignments}.isdisjoint({j for j, _ in lu.holes})


def test_alineacion_sin_huecos_sigue_negandose_si_no_llegan():
    import pytest

    with pytest.raises(ValueError):
        best_lineup([_de_campo(i, 8) for i in range(7)], "4-4-2")


# ---------------------------------------------------------------- rentabilidad


def test_rentabilidad_corta_en_la_mediana_y_la_mediana_cuenta_arriba():
    # (HTMS28, sueldo)
    valores = {
        1: (1700, 40000),
        2: (1500, 20000),
        3: (1650, 5000),
        4: (1000, 3000),
        5: (1200, 60000),
    }
    corte = rentabilidad(valores)
    assert corte is not None
    assert (corte.mediana_htms28, corte.mediana_sueldo) == (1500, 20000)
    assert corte.grupos == {
        1: ESTRELLAS,
        2: ESTRELLAS,  # justo en las dos medianas: futuro alto y caro
        3: GANGAS,
        4: ECONOMICOS,
        5: CAROS,
    }


def test_el_htms28_negativo_cuenta_para_la_mediana():
    con = rentabilidad({1: (1600, 100), 2: (1500, 100), 3: (-1500, 100)})
    assert con is not None and con.mediana_htms28 == 1500


def test_sin_jugadores_no_hay_corte():
    assert rentabilidad({}) is None


# ---------------------------------------------------------------- etapas


def test_una_etapa_de_mas_de_once_se_parte_en_titulares_y_suplentes():
    etapas = {i: "veterano" for i in range(1, 13)} | {20: "promesa"}
    lados = partir_etapas(etapas, titulares={1, 2, 3, 20})
    assert lados[1] == LADO_TITULAR
    assert lados[12] == LADO_SUPLENTE
    assert lados[20] is None  # la promesa está sola: no se parte


def test_once_o_menos_no_se_parte():
    lados = partir_etapas({i: "veterano" for i in range(11)}, titulares={0})
    assert set(lados.values()) == {None}


def test_si_un_lado_queda_vacio_no_se_parte():
    """El caso de su plantilla el 2026-11-16: 12 veteranos, los 12 titulares."""
    lados = partir_etapas({i: "veterano" for i in range(12)}, titulares=set(range(12)))
    assert set(lados.values()) == {None}


def test_con_huecos_el_castigo_por_amontonar_cuenta_solo_a_los_que_juegan():
    """Un mediocentro solo en una línea de tres casillas no se estorba con
    nadie: su valoración es la de un mediocentro sin compañía, no la de uno
    de tres (caso Granada en la Suplencia del 2026-11-16)."""
    from app.domain.engines.lineup_optimizer import _player_rating

    medio = _de_campo(1, 3)
    medio["skills"] = {**medio["skills"], "playmaking": 15}
    lu = best_lineup([medio], "5-5-0", con_huecos=True)
    (a,) = lu.assignments
    assert a.base_position == "inner_midfield"
    assert a.rating == round(_player_rating(medio, a.position, {}), 2)
    assert a.rating > round(_player_rating(medio, a.position, {"inner_midfield": 0.825}), 2)


def test_todas_empatadas_dan_un_reparto_con_titulares():
    xp = {k: 4 for k in ("550", "541", "532", "523", "451", "442", "433", "352", "343", "253")}
    reparto = repartir([_jugador(i, 10 + i) for i in range(1, 6)], xp, once=_once_por_valor())
    assert reparto.formations == ("4-4-2",)
    # Antes del 4-4-2 salían todos en Reserva; ahora el motor de juguete pone a dos.
    assert _quien(reparto, TITULAR) == {4, 5}
