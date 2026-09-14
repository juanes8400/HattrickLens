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
    # Desde 2026-08-19 la línea se reparte por sub-rol (3 interiores + 2
    # extremos en un 3-5-2), así que dentro del bloque van primero los de
    # dentro. Los cinco elegidos son los mismos.
    assert set(p.name for p in team["midfield"]) == {
        "Medio A", "Medio B", "Medio C", "Medio D", "Medio E",
    }
    assert [p.name for p in team["inner_midfield"]] == ["Medio C", "Medio D", "Medio E"]
    assert [p.name for p in team["winger"]] == ["Medio A", "Medio B"]
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
    """Escenario "temporada": el mismo jugador aparece en varios partidos
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
    actuación real, no puede ser "el mejor" de nada, aunque sea el único
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
    matchlineup.xml v2.1, que ya incorpora los `<Substitution>`. Antes,
    con la versión sin especificar, ese mismo jugador leía PositionCode=10
    ("Interior izquierdo"), y "Delanteros" salía vacío en la jornada
    entera pese a que sí hubo un delantero real con actuación destacada."""
    players = [
        _p(468921494, "Alberto Gutiérrez Caviedes", 1, 112, 11.5),
        _p(471016867, "Herilala Njakanirina", 1, 111, 10.5),
    ]
    forward = best_team(players, formation="4-4-2")["forward"]
    assert [p.name for p in forward] == ["Alberto Gutiérrez Caviedes", "Herilala Njakanirina"]


def test_the_split_decides_how_many_play_inside() -> None:
    """Los selectores de Hattrick Control: el nombre de la formación no dice
    cuántos de cada línea juegan por dentro.

    2026-08-19: antes se cogían los N mejores de la línea sin mirar el
    sub-rol, así que un once ideal podía salir con cuatro centrales y ningún
    lateral, una alineación que el juego no deja poner.
    """
    players = [
        _p(1, "Central A", 1, 103, 9.0),
        _p(2, "Central B", 2, 102, 8.9),
        _p(3, "Central C", 1, 104, 8.8),
        _p(4, "Lateral A", 2, 101, 6.0),
        _p(5, "Lateral B", 1, 105, 5.9),
        _p(6, "Interior A", 2, 107, 9.0),
        _p(7, "Interior B", 1, 108, 8.9),
        _p(8, "Interior C", 2, 109, 8.8),
        _p(9, "Extremo A", 1, 106, 6.0),
        _p(10, "Extremo B", 2, 110, 5.9),
    ]
    # Un 5-3-2 con 1 interior: dos extremos entran aunque puntúen menos que
    # los interiores que se quedan fuera.
    team = best_team(players, "5-3-2", inner_midfielders=1)
    assert [p.name for p in team["inner_midfield"]] == ["Interior A"]
    assert [p.name for p in team["winger"]] == ["Extremo A", "Extremo B"]
    # Con 3 interiores no hay hueco para ningún extremo.
    team = best_team(players, "5-3-2", inner_midfielders=3)
    assert len(team["inner_midfield"]) == 3
    assert team["winger"] == []
    # Y la defensa de cinco es siempre 3 centrales + 2 laterales, aunque los
    # laterales puntúen mucho menos.
    assert [p.name for p in team["wingback"]] == ["Lateral A", "Lateral B"]


def test_an_impossible_split_falls_back_instead_of_breaking() -> None:
    """El selector solo ofrece repartos legales, pero un número inventado en
    la URL no puede tumbar la pantalla."""
    from app.domain.engines.team_of_the_week import resolve_split

    assert resolve_split("4-4-2", central_defenders=9) == (2, 2)
    assert resolve_split("5-3-2", inner_midfielders=0) == (3, 1)
    # Cinco defensas solo admiten 3 centrales: pedir 2 deja 3 laterales, que
    # no existen.
    assert resolve_split("5-3-2", central_defenders=2) == (3, 1)


def test_a_player_never_takes_two_places_in_the_same_eleven() -> None:
    """El fallo que se vio en vivo en Liga/Comparación: un jugador propio
    salía DOS veces en el mismo once.

    Pasaba cuando el mismo jugador tenía buenas actuaciones en dos puestos
    distintos de dos jornadas distintas, entra de extremo un domingo y de
    interior al siguiente, : la memoria de «este ya salió» era de cada bloque,
    no del once entero. Aquí «Comodín» es el mejor extremo Y el mejor
    interior de la liga; tiene que ocupar UNA plaza, y la otra irse al
    siguiente."""
    players = [
        _p(1, "Portero", 1, 100, 8.0),
        _p(2, "Central A", 1, 102, 8.0),
        _p(3, "Central B", 1, 103, 7.9),
        _p(4, "Lateral A", 1, 101, 7.8),
        _p(5, "Lateral B", 1, 105, 7.7),
        # Dos actuaciones del MISMO jugador, en dos puestos y dos partidos.
        _p(6, "Comodín", 1, 110, 9.8, match=10),
        _p(6, "Comodín", 1, 107, 9.7, match=11),
        _p(7, "Extremo", 1, 106, 9.0),
        _p(8, "Interior A", 1, 108, 8.9),
        _p(9, "Interior B", 1, 109, 8.8),
        _p(10, "Delantero A", 1, 111, 9.5),
        _p(11, "Delantero B", 1, 112, 9.4),
    ]
    team = best_team(players, formation="4-4-2")

    once = team["keeper"] + team["defense"] + team["midfield"] + team["forward"]
    assert len(once) == 11
    ids = [p.ht_player_id for p in once]
    assert len(set(ids)) == 11, "hay un jugador repetido en el once"
    assert ids.count(6) == 1


def test_the_eleven_maximises_the_total_and_not_the_first_pick() -> None:
    """Elegir por turnos no da el mejor equipo, y por eso esto es un húngaro.

    Un 4-4-2 tiene dos plazas de extremo y dos de interior. «Estrella» es el
    mejor extremo de la liga (9,9) y también un buen interior (9,0); «Banda
    A» y «Banda B» sólo saben jugar por fuera, y «Sólo interior» sólo por
    dentro.

    Por turnos: Estrella y Banda A se quedan las bandas, Banda B se queda
    fuera y por dentro sólo hay a quien poner en una de las dos plazas
    9,9 + 9,5 + 7,0 = 26,4, con un hueco.

    Lo óptimo es meter a Estrella por dentro: las bandas para Banda A y
    Banda B, y las dos plazas de interior llenas, 9,5 + 9,4 + 9,0 + 7,0 =
    34,9, sin huecos."""
    players = [
        _p(1, "Estrella", 1, 106, 9.9, match=10),
        _p(1, "Estrella", 1, 108, 9.0, match=11),
        _p(2, "Banda A", 1, 106, 9.5),
        _p(3, "Banda B", 1, 110, 9.4),
        _p(4, "Sólo interior", 1, 108, 7.0),
    ]
    team = best_team(players, formation="4-4-2")
    extremos = {p.ht_player_id for p in team["winger"]}
    interiores = {p.ht_player_id for p in team["inner_midfield"]}
    assert extremos == {2, 3}
    assert interiores == {1, 4}
