"""youthplayerlist.xml — 2026-08-15.

El módulo de Juveniles llevaba tiempo completo (categorías, potencial, plazos,
ROI) leyendo de una tabla que nadie llenaba: nunca se descargaba el fichero.
La fixture es un recorte del XML real de la cuenta.
"""
from pathlib import Path

from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).parent / "fixtures"


def _parse() -> list[dict]:
    xml = (FIXTURES / "youthplayerlist.xml").read_bytes()
    return get_parser("youthplayerlist")(xml)["youth_players"]


def test_reads_every_youth_player() -> None:
    players = _parse()
    assert [p["ht_youth_player_id"] for p in players] == [424402061, 432538331]
    assert players[0]["first_name"] == "Alirio"
    assert players[0]["last_name"] == "Asprilla"


def test_reads_age_and_promotion_deadline() -> None:
    alirio = _parse()[0]
    assert (alirio["age_years"], alirio["age_days"]) == (16, 55)
    assert alirio["can_be_promoted_in"] == 105
    assert alirio["arrival_date"] == "2026-08-09 05:05:00"


def test_unrevealed_skill_is_none_not_zero() -> None:
    """El punto entero del módulo: un techo que el ojeador no ha revelado no
    es un techo bajo. CHPP lo marca con IsAvailable="False" y el elemento
    vacío — si esto devolviera 0, el motor descartaría canteranos por
    ignorancia en vez de por evidencia."""
    alirio = _parse()[0]
    assert alirio["keeper"] is None
    assert alirio["keeper_max"] is None
    assert alirio["scoring"] is None


def test_reads_revealed_levels_and_ceilings() -> None:
    alirio = _parse()[0]
    assert alirio["passing"] == 5
    assert alirio["passing_max"] == 6
    # Un techo puede estar revelado aunque el nivel actual no lo esté.
    assert alirio["winger"] is None
    assert alirio["winger_max"] == 5


def test_maps_chpp_skill_names_to_app_names() -> None:
    """CHPP dice Defender/Playmaker/Scorer; el resto de la app dice
    defending/playmaking/scoring. La traducción vive en el parser."""
    alvaro = _parse()[1]
    assert alvaro["defending"] == 7
    assert alvaro["defending_max"] == 7


def test_minutes_of_last_match_default_to_zero_without_one() -> None:
    players = _parse()
    assert players[0]["minutes_last_match"] == 90
    # El segundo juvenil no tiene <LastMatch> — nunca jugó.
    assert players[1]["minutes_last_match"] == 0
