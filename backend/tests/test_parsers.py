"""Tests de contrato de parsers contra XML reales de CHPP (fixtures)."""
from pathlib import Path

from app.infrastructure.chpp.parsers import (
    parse_currentbids,
    parse_economy,
    parse_managercompendium,
    parse_playerdetails,
    parse_players,
    parse_teamdetails,
    parse_training,
    parse_transfersteam,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_teamdetails_real_fixture() -> None:
    data = parse_teamdetails((FIXTURES / "teamdetails.xml").read_bytes())
    assert data["login_name"] == "juanes840"
    assert len(data["teams"]) == 1
    team = data["teams"][0]
    assert team["ht_team_id"] == 537758
    assert team["name"] == "Pulgas Arrechas"
    assert team["series_name"] == "V.92"
    # 2026-08-04: LeagueID del país (19 = Colombia) — clave para cruzar
    # contra worlddetails.xml y saber la temporada/moneda/copas reales.
    assert team["ht_league_id"] == 19
    assert team["still_in_cup"] is True
    assert team["current_cup"] == {
        "ht_cup_id": 18,
        "cup_name": "Copa Colombia",
        "cup_league_level": 0,
        "cup_level": 1,
        "cup_level_index": 1,
        "match_round": 1,
        "match_rounds_left": 11,
    }


def test_parse_managercompendium_keeps_all_login_times() -> None:
    data = parse_managercompendium((FIXTURES / "managercompendium.xml").read_bytes())
    assert data["ht_user_id"] == 445566
    assert data["login_name"] == "manager-rival"
    assert data["fetched_at"] == "2026-08-06 12:00:00"
    assert data["last_logins"] == [
        "2026-08-03 18:30:00",
        "2026-08-06 08:45:00",
    ]
    assert data["teams"] == [{"ht_team_id": 2688899, "name": "etbenianos1"}]


def test_float_helper_parses_comma_decimal_separator() -> None:
    """worlddetails.xml sirve algunas tasas de cambio con coma decimal en
    vez de punto (verificado en vivo 2026-08-04: India "0,25") — sin este
    fix, float() lanzaba ValueError y el campo caía en silencio al default
    0.0, una tasa de cambio inválida en vez de un dato real."""
    from xml.etree.ElementTree import fromstring

    from app.infrastructure.chpp.parsers import _float

    node = fromstring("<Country><CurrencyRate>0,25</CurrencyRate></Country>")
    assert _float(node, "CurrencyRate") == 0.25


def test_parse_players_real_fixture() -> None:
    data = parse_players((FIXTURES / "players.xml").read_bytes())
    players = data["players"]
    assert len(players) == 24

    raul = next(p for p in players if p["last_name"] == "Cobos")
    assert raul["first_name"] == "Raúl"  # encoding UTF-8 correcto (bug histórico)
    assert raul["tsi"] == 206720
    assert raul["skills"]["passing"] == 15
    assert raul["skills"]["defending"] == 11
    assert raul["form_is_read"] is True
    assert raul["stamina_is_read"] is True

    assert all(p["ht_player_id"] > 0 for p in players)
    assert all(0 <= p["age_days"] < 112 for p in players)
    assert all(set(p["skills"]) == {
        "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces"
    } for p in players)

    # HL-15x: campos reales de players.xml (2.6) que antes se descartaban.
    assert raul["loyalty"] == 20
    assert raul["leadership"] == 2
    assert raul["agreeability"] == 1
    assert raul["aggressiveness"] == 2
    assert raul["honesty"] == 1
    assert raul["mother_club_bonus"] is False
    assert raul["country_id"] == 17
    assert raul["career_goals"] == 28
    assert raul["player_trainer_skill_level"] == 0    # sin <TrainerData>: no es entrenador-jugador
    assert raul["player_trainer_type"] == 0
    # CareerAssists NO existe en players.xml (comprobado contra un XML real
    # de la cuenta de desarrollo) — solo en playerdetails.xml. Que el parser
    # no la incluya aquí es correcto, no un olvido: inventar un 0 sería
    # peor que declarar el dato como no disponible desde este fichero.
    assert "career_assists" not in raul


def test_parse_playerdetails_real_fixture() -> None:
    data = parse_playerdetails((FIXTURES / "playerdetails.xml").read_bytes())
    assert data["ht_player_id"] == 468921494
    assert data["mother_club_team_name"] == "Otro Equipo FC"
    assert data["mother_club_team_id"] == 999999
    assert data["career_assists"] == 21
    assert data["caps"] == 0
    assert data["caps_u20"] == 0
    assert data["native_league_name"] == "Colombia"
    assert data["native_country_id"] == 19
    assert data["native_league_id"] == 19
    assert data["last_match"] == {
        "ht_match_id": 123456789, "position_code": 13,
        "played_minutes": 90, "rating": 8.5, "played_at": "2026-07-19 16:00:00",
    }
    assert data["age_years"] == 30
    assert data["age_days"] == 45


def test_parse_playerdetails_ignores_the_all_zero_last_match_sentinel() -> None:
    """Bug real 2026-08-09: cuando CHPP no tiene un último partido real
    para un jugador, `<LastMatch>` sigue presente pero con todo en cero
    (`MatchId=0`, `Date=0001-01-01...`) — nunca un partido real de
    Hattrick, cuyo ID nunca es 0. Antes esto se colaba como si
    PositionCode=0 fuera una posición real: `match_role_name(0)` no
    traduce nada y muestra el feo fallback "posicion 0 (sin traducir)" en
    "Última posición"/"Última semana". Debe leerse como "sin dato", igual
    que cualquier otro sentinel de esta app (-1 en matchlineup, etc.)."""
    data = parse_playerdetails(
        (FIXTURES / "playerdetails_no_last_match.xml").read_bytes()
    )
    assert data["ht_player_id"] == 511319764
    assert "last_match" not in data


def test_parse_playerdetails_detects_chpp_error() -> None:
    """playerdetails.xml devuelve HTTP 200 con un <Error>/<ErrorCode>
    (nunca un error HTTP real) para un playerID que ya no resuelve en
    Hattrick — ver `_is_chpp_error`, verificado en vivo 2026-08-05 contra
    ~105 ventas viejas de esta cuenta."""
    data = parse_playerdetails((FIXTURES / "chpperror.xml").read_bytes())
    assert data == {
        "chpp_error": True,
        "chpp_error_code": 56,
        "chpp_error_message": "(56) Additional Info: null",
    }


def test_parse_transfersteam_real_fixture() -> None:
    """`TransferType`, `Price`, `Buyer` y `Seller` son hermanos de `Player`
    dentro de `Transfer`, no están anidados dentro de `Player` — un parser
    anterior los buscaba en el sitio equivocado y siempre devolvía
    transfer_type="" / price=0 en producción (ver CORRECCIÓN 2026-08-03 bis
    en `parse_transfersteam`). Este fixture cubre una compra Y una venta
    para que ese bug no pueda reaparecer sin que un test lo note."""
    data = parse_transfersteam((FIXTURES / "transfersteam.xml").read_bytes())
    transfers = data["transfers"]
    assert len(transfers) == 2

    buy = next(t for t in transfers if t["transfer_type"] == "B")
    assert buy["ht_player_id"] == 468921494
    assert buy["buyer_team_id"] == 537758
    assert buy["price"] == 1750000

    sell = next(t for t in transfers if t["transfer_type"] == "S")
    assert sell["ht_player_id"] == 900000002
    assert sell["seller_team_id"] == 537758
    assert sell["buyer_team_id"] == 1423828
    assert sell["price"] == 2860000

    # HL-161 2026-08-04: paginado real (pageIndex) + Stats agregado de toda
    # la historia — ver corrección en `parse_transfersteam`.
    assert buy["ht_transfer_id"] == 900001
    assert sell["ht_transfer_id"] == 388548167
    assert data["page_index"] == 0
    assert data["pages"] == 1
    assert data["stats"] == {
        "total_sum_of_buys": 1750000,
        "total_sum_of_sales": 2860000,
        "number_of_buys": 1,
        "number_of_sales": 1,
    }


def test_parse_currentbids_reads_highest_bid_and_handles_no_bids_yet() -> None:
    """`HighestBid/Amount` es un nodo anidado, no un hermano de `PlayerId`
    — pedido explícitamente 2026-08-08 para enumerar intentos de venta con
    su precio. Un jugador recién listado sin pujas todavía no trae el nodo
    `HighestBid`: debe leerse `None`, nunca 0 (0 sería una puja real)."""
    xml = b"""<?xml version="1.0" encoding="utf-8"?>
    <HattrickData>
      <TeamId>537758</TeamId>
      <BidItems TrackingTypeID="1">
        <BidItem>
          <PlayerId>484269024</PlayerId>
          <PlayerName>Jorge Salas</PlayerName>
          <HighestBid>
            <Amount>2000000</Amount>
            <TeamId>1</TeamId>
            <TeamName>Comprador</TeamName>
          </HighestBid>
          <Deadline>2026-08-10 20:00:00</Deadline>
        </BidItem>
        <BidItem>
          <PlayerId>111</PlayerId>
          <PlayerName>Sin pujas</PlayerName>
          <Deadline>2026-08-10 20:00:00</Deadline>
        </BidItem>
      </BidItems>
    </HattrickData>"""
    data = parse_currentbids(xml)
    listed = {p["ht_player_id"]: p for p in data["listed_players"]}
    assert listed[484269024]["highest_bid"] == 2000000
    assert listed[111]["highest_bid"] is None


def test_parse_training_real_fixture() -> None:
    data = parse_training((FIXTURES / "training.xml").read_bytes())
    assert data["ht_team_id"] == 537758
    assert data["training_type"] == 10          # porteros
    assert data["training_level"] == 100
    assert data["stamina_part"] == 25
    assert data["trainer_name"] == "Volodymyr Manakin"
    assert data["morale"] == 4
    assert data["self_confidence"] == 5
    assert data["formation_xp"]["550"] == 10


def test_parse_economy_real_fixture() -> None:
    data = parse_economy((FIXTURES / "economy.xml").read_bytes())
    assert data["ht_team_id"] == 537758
    assert data["cash"] == 210341736
    assert data["expected_cash"] == 223855664
    assert data["costs_players"] == 2324280
    assert data["expected_weeks_total"] == 13513928
    assert data["fan_club_size"] == 2406


def test_parse_economy_keeps_new_official_categories_separate() -> None:
    xml = b"""<HattrickData><Team><TeamID>1</TeamID><Cash>0</Cash>
    <ExpectedCash>0</ExpectedCash><SponsorsPopularity>0</SponsorsPopularity>
    <SupportersPopularity>0</SupportersPopularity><FanClubSize>0</FanClubSize>
    <IncomeSpectators>10</IncomeSpectators><IncomeSponsors>20</IncomeSponsors>
    <IncomeSponsorBonuses>30</IncomeSponsorBonuses><IncomeFinancial>0</IncomeFinancial>
    <IncomeSoldPlayers>40</IncomeSoldPlayers>
    <IncomeSoldPlayersCommission>5</IncomeSoldPlayersCommission><IncomeSum>105</IncomeSum>
    <CostsArena>1</CostsArena><CostsPlayer>2</CostsPlayer><CostsFinancial>0</CostsFinancial>
    <CostsBoughtPlayers>3</CostsBoughtPlayers><CostsArenaBuilding>4</CostsArenaBuilding>
    <CostsStaff>0</CostsStaff><CostsYouth>0</CostsYouth><CostsSum>10</CostsSum>
    <ExpectedWeeksTotal>95</ExpectedWeeksTotal><LastIncomeSum>0</LastIncomeSum>
    <LastCostsSum>0</LastCostsSum><LastWeeksTotal>0</LastWeeksTotal></Team></HattrickData>"""
    data = parse_economy(xml)
    assert data["income_sponsor_bonuses"] == 30
    assert data["income_sold_players"] == 40
    assert data["income_sold_players_commission"] == 5
    assert data["costs_bought_players"] == 3
    assert data["costs_arena_building"] == 4
    assert data["costs_players"] == 2


def test_parser_tolerates_missing_fields() -> None:
    xml = (
        b"<?xml version='1.0'?><HattrickData><Team><PlayerList>"
        b"<Player><PlayerID>1</PlayerID></Player>"
        b"</PlayerList></Team></HattrickData>"
    )
    data = parse_players(xml)
    p = data["players"][0]
    assert p["ht_player_id"] == 1
    assert p["tsi"] == 0 and p["injury_level"] == -1  # defaults, sin crash
