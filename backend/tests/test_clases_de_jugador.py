"""Clases de Jugador (reglas del usuario, 2026-11-16)."""

from typing import Any

from app.domain.engines.clases_de_jugador import (
    CONSOLIDADOS,
    LADO_SUPLENTE,
    LADO_TITULAR,
    PROMESAS,
    RELLENO,
    RESERVA,
    SUPLENCIA,
    TITULAR,
    VETERANOS,
    formaciones_mas_entrenadas,
    partir_etapas,
    potencial,
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


# ---------------------------------------------------------------- potencial


def test_potencial_corta_en_la_mediana_y_la_mediana_cuenta_arriba():
    valores = {1: (2000, 1700), 2: (1500, 1500), 3: (800, 1650), 4: (900, 1000), 5: (1900, 1200)}
    corte = potencial(valores)
    assert corte is not None
    assert (corte.mediana_htms, corte.mediana_htms28) == (1500, 1500)
    assert corte.grupos == {
        1: CONSOLIDADOS,
        2: CONSOLIDADOS,  # justo en las dos medianas: arriba
        3: PROMESAS,
        4: RELLENO,
        5: VETERANOS,
    }


def test_el_htms28_negativo_cuenta_para_la_mediana():
    con = potencial({1: (100, 1600), 2: (100, 1500), 3: (100, -1500)})
    assert con is not None and con.mediana_htms28 == 1500


def test_sin_jugadores_no_hay_corte():
    assert potencial({}) is None


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
