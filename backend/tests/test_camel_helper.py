"""`_camel`/`_key` — el conversor snake_case -> camelCase compartido por
arena/matches/academy/league.

No son solo cosméticos: `_key` asumía que toda clave de dict es un string, y
`position_distribution` (posición -> probabilidad, en LeagueResponse) tiene
claves enteras. `/league` siempre había devuelto 404 antes de conectar el
sync de leaguedetails, así que este camino nunca se había ejecutado con datos
reales — el primer 200 real con distribución de posiciones lo tumbó.
"""
from app.api.v1.endpoints.arena import _camel


def test_camel_converts_string_keys() -> None:
    assert _camel({"goals_for": 3, "home_team_name": "x"}) == {
        "goalsFor": 3, "homeTeamName": "x",
    }


def test_camel_leaves_non_string_keys_untouched() -> None:
    """Una distribución posición -> probabilidad no tiene identificadores como
    claves; no debe intentar camelCasearlas, y mucho menos crashear."""
    assert _camel({1: 0.5, 2: 0.3}) == {1: 0.5, 2: 0.3}


def test_camel_recurses_into_nested_structures_with_mixed_keys() -> None:
    data = {"own_outlook": {"position_distribution": {1: 0.6, 2: 0.4}}}
    assert _camel(data) == {"ownOutlook": {"positionDistribution": {1: 0.6, 2: 0.4}}}


def test_camel_recurses_into_lists() -> None:
    assert _camel([{"team_name": "a"}, {"team_name": "b"}]) == [
        {"teamName": "a"}, {"teamName": "b"},
    ]
