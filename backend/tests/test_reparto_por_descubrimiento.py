"""El reparto para descubrir: la exclusión del compañero y el óptimo.

2026-08-26. Lo que se fija aquí es la regla que el usuario subrayó como CLAVE
--la habilidad del otro entrenamiento no cuenta como descubrimiento-- y que el
emparejamiento sea el óptimo y no el de coger lo mejor por turnos.
"""

from app.domain.engines.reparto_por_descubrimiento import (
    Candidato,
    probabilidad_de_descubrir,
    reparte,
)

#: Las ruletas reales de dos puestos, del estudio de la comunidad.
EXTREMO = {"winger": 34, "passing": 21, "playmaking": 20, "defending": 15, "set_pieces": 10}
PORTERO = {"defending": 42, "keeper": 40, "set_pieces": 18}


def test_todo_por_descubrir_da_cien():
    todas = frozenset(EXTREMO)
    assert probabilidad_de_descubrir(EXTREMO, todas) == 100


def test_todo_revelado_da_cero():
    assert probabilidad_de_descubrir(EXTREMO, frozenset()) == 0


def test_la_habilidad_del_companero_no_cuenta():
    """La regla CLAVE. Con «Lateral» de principal, que a un extremo le salga
    Lateral no descubre nada: esa habilidad ya la entrena el otro hueco."""
    todas = frozenset(EXTREMO)
    sin_excluir = probabilidad_de_descubrir(EXTREMO, todas)
    con_excluir = probabilidad_de_descubrir(EXTREMO, todas, excluidas={"winger"})
    assert sin_excluir == 100
    assert con_excluir == 66  # 100 - 34, que es lo que pesa Lateral en ese puesto


def test_se_excluyen_las_dos_si_el_companero_sube_dos():
    """«Anotación y balón parado» entrena las dos, así que ninguna cuenta."""
    todas = frozenset(EXTREMO)
    v = probabilidad_de_descubrir(EXTREMO, todas, excluidas={"scoring", "set_pieces"})
    assert v == 90  # solo cae Balón parado (10); Anotación no está en ese puesto


def test_lo_que_ya_topo_no_suma():
    """No está en `sin_revelar`, así que no puede contarse. Es aritmética, no
    opinión: entrenar algo que ya no sube no lo va a revelar."""
    sin_pases = frozenset(EXTREMO) - {"passing"}
    assert probabilidad_de_descubrir(EXTREMO, sin_pases) == 79  # 100 - 21


def test_reparte_pone_a_cada_uno_donde_mas_ilumina():
    ruletas = {"winger": EXTREMO, "keeper": PORTERO}
    # Al primero solo le falta Portería; al segundo solo Lateral. Cada uno
    # tiene un puesto en el que vale y otro en el que no vale nada.
    gente = [
        Candidato("solo_porteria", frozenset({"keeper"})),
        Candidato("solo_lateral", frozenset({"winger"})),
    ]
    pares = reparte(["winger", "keeper"], gente, ruletas)
    assert {p: n for n, p in pares} == {
        "winger": "solo_lateral",
        "keeper": "solo_porteria",
    }


def test_el_optimo_le_gana_a_coger_lo_mejor_primero():
    """El caso que obliga al húngaro.

    «acaparador» es el mejor en las DOS plazas, pero solo puede ocupar una.
    Por turnos se le daría la de portero --su mejor-- y la de extremo se la
    quedaría alguien que no aprovecha. El óptimo le da la de extremo.
    """
    ruletas = {"winger": EXTREMO, "keeper": PORTERO}
    gente = [
        # Le falta todo: 100 en extremo, 100 en portero.
        Candidato("acaparador", frozenset(EXTREMO) | frozenset(PORTERO)),
        # Solo le falta Portería: 0 en extremo, 40 en portero.
        Candidato("portero_puro", frozenset({"keeper"})),
    ]
    pares = reparte(["winger", "keeper"], gente, ruletas)
    asignado = {p: n for n, p in pares}
    assert asignado["winger"] == "acaparador"
    assert asignado["keeper"] == "portero_puro"
    # Óptimo 100 + 40 = 140. Por turnos habría sido 100 (portero) + 0 = 100.


def test_varias_plazas_del_mismo_puesto_son_sillas_distintas():
    """Tres centrales son tres sillas, no una."""
    ruletas = {"central": {"defending": 50, "passing": 50}}
    gente = [Candidato(f"c{i}", frozenset({"defending"})) for i in range(5)]
    pares = reparte(["central"] * 3, gente, ruletas)
    assert len(pares) == 3
    assert len({n for n, _ in pares}) == 3  # tres personas distintas


def test_sin_gente_o_sin_plazas():
    assert reparte([], [Candidato("a", frozenset())], {}) == []
    assert reparte(["winger"], [], {"winger": EXTREMO}) == []


def test_menos_candidatos_que_plazas():
    ruletas = {"winger": EXTREMO, "keeper": PORTERO}
    pares = reparte(["winger", "keeper"], [Candidato("uno", frozenset(EXTREMO))], ruletas)
    assert len(pares) == 1
