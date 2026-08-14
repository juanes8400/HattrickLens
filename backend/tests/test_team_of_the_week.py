from app.domain.engines.team_of_the_week import LineupPlayer, best_team


def _p(ht_player_id, name, team, role, stars, match=1) -> LineupPlayer:
    return LineupPlayer(
        ht_player_id=ht_player_id, name=name, team_ht_id=team, team_name=f"Team {team}",
        role_id=role, rating_stars=stars, ht_match_id=match,
    )


def test_best_team_fills_every_slot_according_to_the_chosen_formation() -> None:
    # RoleID real de matchlineup.xml pedido con version=2.1 (100+, no el
    # PositionCode de la versión sin especificar): 100=portero,
    # 101/105=lateral, 102/103/104=defensa central (bloque "defensa"),
    # 106/110=extremo, 107/108/109=interior (extremos e interiores
    # comparten el bloque "medios"), 111/112/113=delantero.
    # Formación 3-5-2: 3 defensas, 5 medios, 2 delanteros.
    players = [
        _p(1, "Portero A", 1, 100, 8.0),
        _p(2, "Portero B", 2, 100, 6.0),
        _p(3, "Defensa A", 1, 103, 9.0),
        _p(4, "Defensa B", 2, 102, 8.5),
        _p(5, "Defensa C", 1, 104, 8.0),
        _p(6, "Defensa D (se queda fuera)", 2, 101, 7.5),
        _p(7, "Medio A", 1, 106, 9.5),
        _p(8, "Medio B", 2, 110, 9.0),
        _p(9, "Medio C", 1, 107, 8.5),
        _p(10, "Medio D", 2, 108, 8.0),
        _p(11, "Medio E", 1, 109, 7.5),
        _p(12, "Medio F (se queda fuera)", 2, 106, 7.0),
        _p(13, "Delantero A", 1, 111, 10.0),
        _p(14, "Delantero B", 2, 112, 9.5),
        _p(15, "Delantero C (se queda fuera)", 1, 113, 9.0),
    ]
    team = best_team(players, formation="3-5-2")

    assert [p.name for p in team["keeper"]] == ["Portero A"]
    assert [p.name for p in team["defense"]] == ["Defensa A", "Defensa B", "Defensa C"]
    assert [p.name for p in team["midfield"]] == [
        "Medio A", "Medio B", "Medio C", "Medio D", "Medio E",
    ]
    assert [p.name for p in team["forward"]] == ["Delantero A", "Delantero B"]


def test_best_team_changes_slot_counts_with_a_different_formation() -> None:
    players = [
        _p(1, "Defensa A", 1, 103, 9.0),
        _p(2, "Defensa B", 2, 102, 8.5),
        _p(3, "Delantero A", 1, 111, 9.0),
        _p(4, "Delantero B", 2, 112, 8.5),
        _p(5, "Delantero C", 1, 113, 8.0),
    ]
    team = best_team(players, formation="3-4-3")
    assert [p.name for p in team["defense"]] == ["Defensa A", "Defensa B"]
    assert [p.name for p in team["forward"]] == ["Delantero A", "Delantero B", "Delantero C"]


def test_best_team_defaults_to_4_4_2_when_formation_is_unknown() -> None:
    players = [_p(i, f"Delantero {i}", 1, 111, 5.0 + i) for i in range(1, 5)]
    team = best_team(players, formation="not-a-real-formation")
    assert len(team["forward"]) == 2


def test_best_team_counts_a_repeated_player_only_once_by_their_best_rating() -> None:
    """Escenario "temporada": el mismo jugador aparece en varios partidos —
    cuenta una sola vez, con su mejor actuación, nunca ocupa dos cupos."""
    players = [
        _p(1, "Delantero estrella", 1, 111, 7.0, match=1),
        _p(1, "Delantero estrella", 1, 111, 9.5, match=2),  # su mejor partido
        _p(2, "Delantero B", 2, 112, 8.0, match=1),
        _p(3, "Delantero C", 1, 113, 6.0, match=1),
    ]
    forward = best_team(players, formation="4-3-3")["forward"]
    assert [p.name for p in forward] == ["Delantero estrella", "Delantero B", "Delantero C"]
    assert forward[0].rating_stars == 9.5


def test_best_team_returns_fewer_than_the_slot_count_if_not_enough_candidates() -> None:
    players = [_p(1, "Único portero", 1, 100, 5.0)]
    team = best_team(players)
    assert [p.name for p in team["keeper"]] == ["Único portero"]
    assert team["defense"] == []
    assert team["forward"] == []


def test_best_team_never_picks_a_player_who_did_not_really_play() -> None:
    """2026-08-08, caso real: 0.0 en `rating_stars` es "no jugó de verdad"
    (lesión antes del pitazo, salió sin pisar la cancha), nunca una
    actuación real — no puede ser "el mejor" de nada, aunque sea el único
    candidato del bloque. Mejor un bloque incompleto que un dato inventado."""
    players = [
        _p(1, "Delantero fantasma", 1, 111, 0.0),
        _p(2, "Delantero real", 2, 112, 6.5),
    ]
    forward = best_team(players)["forward"]
    assert [p.name for p in forward] == ["Delantero real"]


def test_best_team_leaves_a_slot_empty_if_every_candidate_has_zero_stars() -> None:
    players = [_p(1, "Único candidato, no jugó", 1, 111, 0.0)]
    assert best_team(players)["forward"] == []


def test_best_team_picks_a_substitute_forward_using_their_real_final_role() -> None:
    """Caso real 2026-08-08/09: Alberto Gutiérrez Caviedes (matchID
    770453114, playerID 468921494) entró de suplente al minuto 32 y quedó
    con RoleID=112 ("Delantero medio") en el `<Lineup>` final de
    matchlineup.xml v2.1 — que ya incorpora los `<Substitution>`. Antes,
    con la versión sin especificar, ese mismo jugador leía PositionCode=10
    ("Interior izquierdo"), y "Delanteros" salía vacío en la jornada
    entera pese a que sí hubo un delantero real con actuación destacada."""
    players = [
        _p(468921494, "Alberto Gutiérrez Caviedes", 1, 112, 11.5),
        _p(471016867, "Herilala Njakanirina", 1, 111, 10.5),
    ]
    forward = best_team(players, formation="4-4-2")["forward"]
    assert [p.name for p in forward] == ["Alberto Gutiérrez Caviedes", "Herilala Njakanirina"]
