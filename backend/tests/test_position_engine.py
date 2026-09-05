"""Position Engine — Manual no Escrito contribution matrices."""

from math import log
from pathlib import Path

import pytest

from app.domain.engines.position_engine import (
    best_for_role,
    best_position,
    model_info,
    positions,
    rank_for_position,
    rate,
    rate_all,
    special_roles,
)
from app.infrastructure.chpp.parsers import parse_players

FIXTURES = Path(__file__).parent / "fixtures"


def _roster() -> dict[str, dict]:
    out = {}
    for p in parse_players((FIXTURES / "players.xml").read_bytes())["players"]:
        p["name"] = f"{p['first_name']} {p['last_name']}"
        p["leadership"] = 5  # not exposed by the players file
        out[p["name"]] = p
    return out


ROSTER = _roster()


def test_specification_defines_nineteen_positions_and_three_roles() -> None:
    assert len(positions()) == 19
    assert set(special_roles()) == {"captain", "set_piece_taker", "penalty_taker"}


def test_rate_all_covers_every_position_sorted() -> None:
    out = rate_all(ROSTER["Raúl Cobos"])
    assert len(out) == 19
    assert out == sorted(out, key=lambda r: -r.rating)


def test_special_roles_are_opt_in() -> None:
    assert len(rate_all(ROSTER["Raúl Cobos"])) == 19
    assert len(rate_all(ROSTER["Raúl Cobos"], include_special=True)) == 22


def test_unknown_position_raises() -> None:
    with pytest.raises(KeyError):
        rate(ROSTER["Jorge Salas"], "sweeper")


def test_goalkeeper_uses_the_manual_matrix_and_all_adjustments() -> None:
    player = {
        "skills": {"keeper": 12, "defending": 6},
        "form": 8,
        "stamina": 8,
        "experience": 7,
        "loyalty": 2,
    }
    bonus = log(7) * 4 / 3 + 2 / 19
    matrix = (0.87 + 0.61) * (12 + bonus) + (0.35 + 0.25) * (6 + bonus)
    form = ((8 - 0.5) / 7) ** 0.45
    stamina = ((8 + 6.5) / 14) ** 0.6
    coefficient_total = 0.87 + 0.61 + 0.35 + 0.25
    assert rate(player, "keeper").rating == pytest.approx(
        matrix / coefficient_total * form * stamina, abs=0.01
    )


def test_individual_orders_follow_their_declared_tradeoff() -> None:
    player = {
        "skills": {"defending": 12, "playmaking": 3, "winger": 2},
        "form": 8,
        "stamina": 8,
        "experience": 1,
        "loyalty": 0,
    }
    # Defensive WB retains more central + side defence than the offensive order.
    assert rate(player, "wingback_defensive").rating > rate(player, "wingback_offensive").rating


def test_goalkeeper_belongs_in_goal() -> None:
    assert best_position(ROSTER["Anders Ebbesen"]).position == "keeper"


def test_striker_prefers_an_attacking_role() -> None:
    assert best_position(ROSTER["Alberto Gutiérrez Caviedes"]).position.startswith("forward")


def test_form_and_stamina_improve_the_contribution() -> None:
    p = ROSTER["Jorge Salas"]
    low = rate({**p, "form": 3, "stamina": 3}, "wingback_defensive").rating
    high = rate({**p, "form": 8, "stamina": 8}, "wingback_defensive").rating
    assert high > low


def test_a_player_without_skills_ranks_last() -> None:
    ranked = rank_for_position(list(ROSTER.values()), "wingback_defensive")
    tail = {p["last_name"] for p, _ in ranked[-4:]}
    assert "Manakin" in tail and "Cacheiro" in tail


def test_rating_never_negative() -> None:
    empty = {
        "skills": dict.fromkeys(
            ["keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"], 0
        ),
        "form": 0,
        "stamina": 0,
        "experience": 0,
        "loyalty": 0,
        "leadership": 0,
    }
    assert all(r.rating >= 0 for r in rate_all(empty, include_special=True))


def test_captain_recommendation_uses_manual_selection_formula() -> None:
    squad = [
        {**ROSTER["Florin Tilvar"], "leadership": 1, "experience": 1, "name": "Novato"},
        {**ROSTER["Florin Tilvar"], "leadership": 9, "experience": 12, "name": "Veterano"},
    ]
    best = best_for_role(squad, "captain")
    assert best is not None and best[0]["name"] == "Veterano"
    assert best[1].rating == 51  # 3 × 9 + 2 × 12


def test_set_piece_taker_uses_set_pieces_and_experience_only() -> None:
    player = {"skills": {"set_pieces": 14, "scoring": 20}, "experience": 8}
    assert rate(player, "set_piece_taker").rating == 22


def test_penalty_taker_uses_the_weighted_formula_given_by_the_user() -> None:
    """2026-08-09, pedido explícitamente: el lanzador de PENALTIS (incluye
    penales de tanda) no es el mismo puesto que "Lanzador de faltas" (TLD)
    — en Hattrick real tienen su propio código. Fórmula aportada
    directamente por el usuario:
    (EXP×1.5 + Balón Parado×0.7 + Anotación×0.3) × (1.10 si Técnico)."""
    player = {
        "skills": {"set_pieces": 10, "scoring": 20},
        "experience": 8,
        "specialty": 0,
    }
    # 8×1.5 + 10×0.7 + 20×0.3 = 12 + 7 + 6 = 25, sin bono (no es Técnico).
    assert rate(player, "penalty_taker").rating == 25.0


def test_penalty_taker_applies_the_technical_specialty_bonus() -> None:
    player = {
        "skills": {"set_pieces": 10, "scoring": 20},
        "experience": 8,
        "specialty": 1,
    }
    # Mismo jugador que arriba, pero Técnico: 25 × 1.10 = 27.5.
    assert rate(player, "penalty_taker").rating == 27.5


def test_penalty_taker_ignores_a_non_technical_specialty() -> None:
    player = {
        "skills": {"set_pieces": 10, "scoring": 20},
        "experience": 8,
        "specialty": 2,
    }
    assert rate(player, "penalty_taker").rating == 25.0


def test_engine_reports_manual_provenance() -> None:
    info = model_info()
    assert info["positions"] == 19
    assert info["specialRoles"] == 3
    assert info["source"] == "Manual no Escrito"
    assert info["sourceUrl"].startswith("https://wiki.hattrick.org/")
    assert "form" in info["adjustments"]
    assert info["configPath"].endswith(".yaml")


def test_engine_is_deterministic() -> None:
    p = ROSTER["Klaus Bahlek"]
    assert rate(p, "winger_offensive") == rate(p, "winger_offensive")


def test_la_matriz_sale_entera_y_con_sus_numeros() -> None:
    """Transparencia promete la formula Y sus numeros.

    2026-09-05: la pantalla decia «19 posiciones» y no ensenaba ninguna. El
    endpoint solo devolvia recuentos, asi que la unica pantalla que existe
    para poder comprobar los calculos escondia justo lo comprobable.
    """
    from app.domain.engines.position_engine import matriz, model_info

    filas = matriz()
    assert len(filas) == 19, "los diecinueve puestos del Manual"
    assert model_info()["matrixRows"] == filas, "la pantalla lee lo mismo"

    portero = next(f for f in filas if f["id"] == "keeper")
    assert portero["label"] == "Portero"
    central = next(s for s in portero["sectors"] if s["id"] == "central_defence")
    # Sin redondear: el fichero dice 0.87 y eso es lo que tiene que llegar.
    assert {"skill": "keeper", "coef": 0.87} in central["skills"]

    for f in filas:
        assert f["sectors"], f"{f['label']} no aporta a ningun sector"
        for s in f["sectors"]:
            assert s["skills"], f"{f['label']} / {s['label']} sin habilidades"
            for h in s["skills"]:
                # Un coeficiente 0 seria una fila que ocupa sitio y no dice
                # nada; uno negativo, un puesto que resta al sector.
                assert h["coef"] > 0, f"{f['label']} / {h['skill']}"


def test_los_sectores_van_de_atras_hacia_adelante() -> None:
    """El orden lo fija el motor y no el diccionario de YAML, que no lo
    garantiza. Sin eso, dos filas de la tabla no serian comparables."""
    from app.domain.engines.position_engine import SECTORES, matriz

    orden = [s for s, _ in SECTORES]
    for f in matriz():
        suyos = [s["id"] for s in f["sectors"]]
        assert suyos == sorted(suyos, key=orden.index), f["label"]
