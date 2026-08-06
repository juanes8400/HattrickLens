"""is_competitive_match_type / is_friendly_match_type — HL-2xx, módulo de
rivales. Liga/Copa/Promoción se define por EXCLUSIÓN a propósito: no se
conoce el MatchType real de Promoción (nunca visto en la cuenta de
desarrollo), así que debe caer en "competitivo" por defecto en vez de
quedar fuera de ambos grupos."""
from app.domain.value_objects.ht_constants import (
    MATCH_TYPE_CUP,
    MATCH_TYPE_FRIENDLY,
    MATCH_TYPE_LEAGUE,
    NON_OFFICIAL_MATCH_TYPES,
    is_competitive_match_type,
    is_friendly_match_type,
)


def test_league_and_cup_are_competitive() -> None:
    assert is_competitive_match_type(MATCH_TYPE_LEAGUE) is True
    assert is_competitive_match_type(MATCH_TYPE_CUP) is True
    assert is_friendly_match_type(MATCH_TYPE_LEAGUE) is False
    assert is_friendly_match_type(MATCH_TYPE_CUP) is False


def test_friendly_is_friendly_not_competitive() -> None:
    assert is_friendly_match_type(MATCH_TYPE_FRIENDLY) is True
    assert is_competitive_match_type(MATCH_TYPE_FRIENDLY) is False


def test_unknown_match_type_defaults_to_competitive() -> None:
    """P.ej. Promoción — nunca visto en la cuenta de desarrollo, no se
    conoce su valor real. Un MatchType desconocido cualquiera (aquí, 4,
    elegido solo por no estar en ninguna lista conocida) debe caer en
    competitivo por defecto, no perderse."""
    unknown = 999
    assert unknown not in NON_OFFICIAL_MATCH_TYPES
    assert unknown != MATCH_TYPE_FRIENDLY
    assert is_competitive_match_type(unknown) is True
    assert is_friendly_match_type(unknown) is False


def test_non_official_types_are_neither() -> None:
    for non_official in NON_OFFICIAL_MATCH_TYPES:
        assert is_competitive_match_type(non_official) is False
        assert is_friendly_match_type(non_official) is False
