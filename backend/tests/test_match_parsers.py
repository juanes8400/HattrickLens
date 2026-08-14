"""HL-070, HL-071, HL-080 · Parsers de partidos y liga contra XML reales."""
from pathlib import Path

from app.infrastructure.chpp.parsers import (
    parse_arenadetails,
    parse_leaguedetails,
    parse_matchdetails,
    parse_matchorders,
    parse_matches,
    parse_transfersplayer,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_matches_real_fixture() -> None:
    data = parse_matches((FIXTURES / "matches.xml").read_bytes())
    ms = data["matches"]
    assert len(ms) >= 10
    assert all(m["ht_match_id"] > 0 for m in ms)
    # Todos los partidos involucran a Pulgas Arrechas
    assert all(537758 in (m["home_team_id"], m["away_team_id"]) for m in ms)
    jugados = [m for m in ms if m["status"] == "FINISHED"]
    assert jugados and all(m["home_goals"] >= 0 for m in jugados)
    upcoming = next(m for m in ms if m["ht_match_id"] == 767370369)
    assert upcoming["source_system"] == "hattrick"
    assert upcoming["orders_given"] is True


def test_parse_matchorders_reads_only_the_submitted_starting_lineup() -> None:
    data = parse_matchorders((FIXTURES / "matchorders.xml").read_bytes())
    assert data["available"] is True
    assert data["ht_match_id"] == 767370369
    assert data["source_system"] == "hattrick"
    assert data["tactic_type"] == 2
    assert data["attitude"] == 0
    assert data["coach_modifier"] == 1
    assert len(data["positions"]) == 11
    assert data["positions"][0] == {
        "ht_player_id": 476719421,
        "role_id": 100,
        "behaviour": 0,
    }
    assert data["prediction"] is None


def test_parse_matchorders_predict_ratings_has_a_distinct_contract() -> None:
    data = parse_matchorders((FIXTURES / "matchorders_predictratings.xml").read_bytes())

    assert data["ht_match_id"] == 41877309
    assert data["available"] is False  # predictratings no incluye este atributo
    assert data["positions"] == []
    assert data["prediction"] == {
        "tactic_type": 2,
        "tactic_skill": 19,
        "ratings": {
            "midfield": 18,
            "right_def": 70,
            "central_def": 90,
            "left_def": 65,
            "right_att": 28,
            "central_att": 32,
            "left_att": 56,
        },
    }


def test_parse_matchdetails_real_fixture() -> None:
    d = parse_matchdetails((FIXTURES / "matchdetails.xml").read_bytes())
    assert d["ht_match_id"] == 765274387
    assert d["match_type"] == 1  # liga — usado para rellenar `matches` de partidos ajenos

    home, away = d["home"], d["away"]
    # Ratings observados: defensa central 61 contra ataque central 27
    assert home["ratings"]["central_def"] == 61
    assert home["ratings"]["midfield"] == 14
    assert away["ratings"]["midfield"] == 15
    assert home["ratings"]["central_att"] == 9

    assert d["possession"]["first_half_home"] == 48
    assert d["possession"]["second_half_home"] == 44
    assert d["arena"]["sold_terraces"] == 34130
    assert d["arena"]["sold_vip"] == 1425
    # matchdetails.xml v3.1 real no trae `<Event>`/EventTypeID (verificado en
    # vivo) — solo conteos de ocasiones por zona, por lado.
    assert home["chances"] == {"left": 3, "center": 0, "right": 1, "special": 0, "other": 0}
    assert away["chances"] == {"left": 1, "center": 1, "right": 1, "special": 1, "other": 1}


def test_parse_arenadetails_current_capacity() -> None:
    d = parse_arenadetails((FIXTURES / "arenadetails.xml").read_bytes())
    assert d["ht_team_id"] == 537758
    assert d["current_capacity"] == {
        "terraces": 40000, "basic": 15000, "roof": 6000, "vip": 1500, "total": 62500,
    }


def test_matchdetails_ratings_feed_the_analysis_engine() -> None:
    from app.domain.engines.match_analysis import ChanceTally, analyse

    d = parse_matchdetails((FIXTURES / "matchdetails.xml").read_bytes())
    a = analyse(d["home"]["ratings"], d["away"]["ratings"], ChanceTally(), ChanceTally())
    assert "Defensa central" in a.strengths
    assert any("Ataque" in w for w in a.weaknesses)


def test_parse_leaguedetails_real_fixture() -> None:
    d = parse_leaguedetails((FIXTURES / "leaguedetails.xml").read_bytes())
    assert d["series_name"] == "V.92"
    # CurrentMatchRound, no MatchRound: ese tag no existe en leaguedetails.xml
    # y siempre habría dado 0.
    assert d["match_round"] == 1
    assert "season" not in d  # leaguedetails.xml no trae temporada
    assert len(d["teams"]) == 8
    assert d["teams"][0]["position"] == 1
    assert any(t["ht_team_id"] == 537758 for t in d["teams"])
    # Ordenados por posición
    assert [t["position"] for t in d["teams"]] == list(range(1, 9))
    # HL-145: división de esta serie y total de divisiones del país.
    assert d["league_level"] == 5
    assert d["max_level"] == 5


def test_parsers_tolerate_missing_fields() -> None:
    xml = b"<?xml version='1.0'?><HattrickData><Match><MatchID>1</MatchID></Match></HattrickData>"
    ms = parse_matches(xml)["matches"]
    assert ms[0]["ht_match_id"] == 1
    assert ms[0]["home_goals"] == -1      # sin jugar, no cero


def test_parse_transfersplayer_real_fixture() -> None:
    """HL-161: fichero real de esta cuenta — CORRECCIÓN 2026-08-03, el
    nombre correcto lleva "s" (`transfersplayer`, no `transferplayer`), y
    SÍ funciona con el token de esta app. Trae el historial completo de
    transferencias de un jugador, no solo mientras estuvo con nosotros."""
    d = parse_transfersplayer((FIXTURES / "transfersplayer.xml").read_bytes())
    assert d["ht_player_id"] == 495018863
    assert d["player_name"] == "Lander Fripont"
    assert len(d["transfers"]) == 3
    # Del más reciente al más antiguo, tal como lo entrega CHPP.
    latest = d["transfers"][0]
    assert latest["seller_team_id"] == 537758  # nosotros vendimos
    assert latest["seller_team_name"] == "Pulgas Arrechas"
    assert latest["price"] == 2860000
    oldest = d["transfers"][-1]
    assert oldest["price"] == 500000
    assert oldest["buyer_team_id"] == 1300449
