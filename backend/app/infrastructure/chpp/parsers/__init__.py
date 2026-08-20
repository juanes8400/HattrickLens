"""Parsers XML por file CHPP. Tolerantes: campo faltante = default, nunca crash.

Entrada en BYTES (el XML declara su propio encoding; decodificar antes corrompe
caracteres no-ASCII — bug real observado con nombres como 'Raúl').
"""
from collections.abc import Callable
from typing import Any
from xml.etree.ElementTree import Element  # noqa: S405 — type only, parsing uses defusedxml

from defusedxml import ElementTree

Parser = Callable[[bytes], dict[str, Any]]

_REGISTRY: dict[str, Parser] = {}


def register(file: str) -> Callable[[Parser], Parser]:
    def deco(fn: Parser) -> Parser:
        _REGISTRY[file] = fn
        return fn
    return deco


def get_parser(file: str) -> Parser:
    if file not in _REGISTRY:
        raise KeyError(f"no parser registered for CHPP file '{file}'")
    return _REGISTRY[file]


def _txt(node: Element, tag: str, default: str = "0") -> str:
    el = node.find(tag)
    return el.text if el is not None and el.text else default


def _int(node: Element, tag: str, default: int = 0) -> int:
    try:
        return int(_txt(node, tag, str(default)))
    except ValueError:
        return default


def _is_chpp_error(root: Element) -> bool:
    """CHPP responde HTTP 200 con un `chpperror.xml` (root `<HattrickData>`
    con `<Error>`/`<ErrorCode>`) para un `playerID` que ya no resuelve
    (verificado en vivo 2026-08-05: ErrorCode 56 y 64 contra jugadores
    vendidos hace muchas temporadas) — nunca lanza un error HTTP real, así
    que sin esta detección el parser simplemente no encontraba `<Player>`
    y devolvía `{}` en silencio, indistinguible de "aún no hay dato"."""
    return root.find("ErrorCode") is not None


def _float(node: Element, tag: str, default: float = 0.0) -> float:
    # CHPP sirve algunos campos (p. ej. CurrencyRate de worlddetails.xml,
    # confirmado en vivo 2026-08-04 con India: "0,25") en formato europeo
    # con coma decimal en vez de punto — sin este reemplazo, float() lanzaba
    # ValueError y el campo se perdía en silencio con el default (0.0, una
    # tasa de cambio inválida, no "sin dato").
    try:
        return float(_txt(node, tag, str(default)).replace(",", "."))
    except ValueError:
        return default


@register("teamdetails")
def parse_teamdetails(xml: bytes) -> dict[str, Any]:
    root = ElementTree.fromstring(xml)
    user = root.find(".//User")
    teams = []
    for t in root.iterfind(".//Team"):
        league = t.find(".//League")
        series = t.find(".//LeagueLevelUnit")
        cup = t.find("Cup")
        # HL-161: país real (columna "País Destino" del Excel del usuario)
        # — `Country/CountryName`, no `League/LeagueName` (casi siempre
        # coinciden, pero no es lo mismo semánticamente). Funciona para
        # equipos ajenos, no solo el propio — verificado en vivo 2026-08-04.
        country = t.find(".//Country")
        # La región del club — 2026-08-18. Hattrick decide el clima por
        # región, y esta es la única fuente que la da de un equipo AJENO:
        # `arenadetails.xml?teamID=` responde error 59 salvo para equipos
        # propios, verificado en vivo. Hace falta para el partido de
        # visitante, donde manda la región del rival.
        region = t.find(".//Region")
        teams.append({
            "ht_team_id": _int(t, "TeamID"),
            "name": _txt(t, "TeamName", ""),
            "short_name": _txt(t, "ShortTeamName", ""),
            "league_name": _txt(league, "LeagueName", "") if league is not None else "",
            # 2026-08-04: LeagueID del PAÍS (distinto de series_ht_id, que es
            # la SERIE dentro del país) — clave para cruzar contra
            # worlddetails.xml y saber la temporada/moneda/copas reales de
            # este equipo en vez de asumir un país fijo — ver
            # `parse_worlddetails`.
            "ht_league_id": _int(league, "LeagueID") if league is not None else 0,
            "series_name": _txt(series, "LeagueLevelUnitName", "") if series is not None else "",
            "series_ht_id": _int(series, "LeagueLevelUnitID") if series is not None else 0,
            "country_name": _txt(country, "CountryName", "") if country is not None else "",
            "ht_region_id": _int(region, "RegionID") if region is not None else 0,
            "region_name": _txt(region, "RegionName", "") if region is not None else "",
            # Estado oficial de la Copa actual. Si StillInCup=False, los
            # demás campos pueden venir vacíos y deben limpiarse al persistir.
            "still_in_cup": _bool(cup, "StillInCup") if cup is not None else None,
            "current_cup": (
                {
                    "ht_cup_id": _int(cup, "CupID"),
                    "cup_name": _txt(cup, "CupName", ""),
                    "cup_league_level": _int(cup, "CupLeagueLevel"),
                    "cup_level": _int(cup, "CupLevel"),
                    "cup_level_index": _int(cup, "CupLevelIndex"),
                    "match_round": _int(cup, "MatchRound", -1),
                    "match_rounds_left": _int(cup, "MatchRoundsLeft", -1),
                }
                if cup is not None and _bool(cup, "StillInCup") else None
            ),
        })
    return {
        "ht_user_id": _int(user, "UserID") if user is not None else 0,
        "login_name": _txt(user, "Loginname", "") if user is not None else "",
        "teams": teams,
    }


@register("managercompendium")
def parse_managercompendium(xml: bytes) -> dict[str, Any]:
    """Identidad y conexiones recientes de un manager.

    `managercompendium.xml` usa la grafía ``UserId``/``TeamId`` mientras
    otros ficheros CHPP usan ``UserID``/``TeamID``. Aceptamos ambas para que
    un cambio de versión no convierta silenciosamente un manager real en 0.
    Los horarios se conservan tal como los entrega Hattrick; el consumidor
    decide cómo convertirlos en una antigüedad.
    """
    root = ElementTree.fromstring(xml)
    if _is_chpp_error(root):
        return {}

    manager = root.find(".//Manager")
    if manager is None:
        return {}

    # La respuesta real concatena una IP enmascarada al horario
    # ("YYYY-MM-DD HH:MM:SS : 191.156.***.***"). La IP no hace falta para
    # calcular actividad y no debe circular por la aplicación: conservamos
    # exclusivamente el timestamp.
    login_times = [
        node.text.split(" : ", 1)[0].strip()
        for node in manager.iterfind(".//LastLogins/LoginTime")
        if node.text
    ]
    teams = []
    for team in manager.iterfind(".//Teams/Team"):
        teams.append({
            "ht_team_id": _int(team, "TeamId") or _int(team, "TeamID"),
            "name": _txt(team, "TeamName", ""),
        })

    return {
        "ht_user_id": _int(manager, "UserId") or _int(manager, "UserID"),
        "login_name": _txt(manager, "Loginname", ""),
        "last_logins": login_times,
        "fetched_at": _txt(root, "FetchedDate", ""),
        "teams": teams,
    }


def _bool(node: Element, tag: str, default: bool = False) -> bool:
    return _txt(node, tag, str(default)).lower() in ("true", "1")


def _optional_bool(node: Element, tag: str) -> bool | None:
    """Boolean* de CHPP: diferencia `false` de campo no suministrado."""
    el = node.find(tag)
    if el is None or el.text is None or not el.text.strip():
        return None
    return el.text.strip().lower() in ("true", "1")


@register("players")
def parse_players(xml: bytes) -> dict[str, Any]:
    """players.xml (2.8) trae bastante más de lo que se usó históricamente:
    Loyalty, Leadership, Agreeability, Aggressiveness, Honesty,
    MotherClubBonus, CountryID, goles por competición/carrera y el
    entrenador-jugador (TrainerData) vienen en la MISMA respuesta que ya se
    pedía — no es un fichero ni una llamada nueva, solo campos que se
    descartaban al parsear. HL-15x."""
    root = ElementTree.fromstring(xml)
    players = []
    for node in root.iterfind(".//Player"):
        trainer = node.find("TrainerData")
        players.append({
            "ht_player_id": _int(node, "PlayerID"),
            "first_name": _txt(node, "FirstName", ""),
            "last_name": _txt(node, "LastName", ""),
            "age_years": _int(node, "Age"),
            "age_days": _int(node, "AgeDays"),
            "tsi": _int(node, "TSI"),
            "form": _int(node, "PlayerForm"),
            "form_is_read": node.find("PlayerForm") is not None,
            "stamina": _int(node, "StaminaSkill"),
            # Un 0 es un nivel válido. Esta bandera separa ese caso del XML
            # que simplemente no expone StaminaSkill para una plantilla rival.
            "stamina_is_read": node.find("StaminaSkill") is not None,
            "experience": _int(node, "Experience"),
            "experience_is_read": node.find("Experience") is not None,
            "salary": _int(node, "Salary"),
            "specialty": _int(node, "Specialty"),
            "injury_level": _int(node, "InjuryLevel", -1),
            "is_transfer_listed": _bool(node, "TransferListed"),
            "loyalty": _int(node, "Loyalty"),
            "leadership": _int(node, "Leadership"),
            "agreeability": _int(node, "Agreeability"),
            "aggressiveness": _int(node, "Aggressiveness"),
            "honesty": _int(node, "Honesty"),
            "mother_club_bonus": _bool(node, "MotherClubBonus"),
            "country_id": _int(node, "CountryID"),
            "league_goals": _int(node, "LeagueGoals"),
            "cup_goals": _int(node, "CupGoals"),
            "friendlies_goals": _int(node, "FriendliesGoals"),
            "career_goals": _int(node, "CareerGoals"),
            "career_hattricks": _int(node, "CareerHattricks"),
            # CareerAssists NO está en players.xml (comprobado contra el
            # fixture real: tras CareerHattricks salta directo a
            # MatchesCurrentTeam) — solo en playerdetails.xml, ver abajo.
            # Un supuesto sin verificar aquí habría dejado a todo el mundo
            # en 0 en vez de "sin sincronizar".
            "player_trainer_skill_level": (
                _int(trainer, "TrainerSkillLevel") if trainer is not None else 0
            ),
            "player_trainer_type": (
                _int(trainer, "TrainerType") if trainer is not None else 0
            ),
            "skills": {
                "keeper": _int(node, "KeeperSkill"),
                "defending": _int(node, "DefenderSkill"),
                "playmaking": _int(node, "PlaymakerSkill"),
                "winger": _int(node, "WingerSkill"),
                "passing": _int(node, "PassingSkill"),
                "scoring": _int(node, "ScorerSkill"),
                "set_pieces": _int(node, "SetPiecesSkill"),
            },
        })
    return {"players": players}


@register("playerdetails")
def parse_playerdetails(xml: bytes) -> dict[str, Any]:
    """playerdetails.xml — se pide UNA vez por jugador (`playerID`), nunca en
    el sync normal por equipo: es la única fuente de `LastMatch` (posición y
    rating de la última semana), del nombre del club madre y de
    `CareerAssists` (ese campo NO existe en players.xml, comprobado contra
    un XML real — HL-15x fase B). Se pide aparte porque son N llamadas
    CHPP, no una."""
    root = ElementTree.fromstring(xml)
    if _is_chpp_error(root):
        # No borrar el diagnóstico de CHPP. El servidor responde estos
        # errores con HTTP 200, por lo que el código y el texto son la única
        # forma de distinguir un jugador eliminado de un dato simplemente
        # ausente o de un problema transitorio.
        return {
            "chpp_error": True,
            "chpp_error_code": _int(root, "ErrorCode"),
            "chpp_error_message": _txt(root, "Error", "").strip(),
        }
    node = root.find(".//Player")
    if node is None:
        return {}
    mother_club = node.find("MotherClub")
    last_match = node.find("LastMatch")
    out: dict[str, Any] = {
        "ht_player_id": _int(node, "PlayerID"),
        "mother_club_team_name": (
            _txt(mother_club, "TeamName", "") if mother_club is not None else ""
        ),
        # 2026-08-04, pedido explícitamente: "canterano" = MotherClub/TeamID
        # igual al ID de este club — funciona para CUALQUIER jugador (igual
        # que el resto de este fichero), a diferencia del `is_academy_graduate`
        # anterior (solo cubría jugadores vistos por el escaneo de cantera de
        # esta app, así que se perdían los del backfill histórico de
        # transferencias). 0 si no hay `MotherClub` — nunca coincide con un
        # TeamID real de Hattrick.
        "mother_club_team_id": (
            _int(mother_club, "TeamID") if mother_club is not None else 0
        ),
        # HL-15x: Nacionalidad real — NativeLeagueName ya viene como texto en
        # playerdetails.xml, sin necesitar una tabla ID→país propia.
        "native_league_name": _txt(node, "NativeLeagueName", ""),
        # Conservar también los IDs oficiales. Algunas respuestas válidas
        # omiten el texto pero sí traen NativeLeagueID/NativeCountryID; el
        # sync puede entonces resolver el nombre exacto contra worlddetails.
        "native_country_id": _int(node, "NativeCountryID"),
        "native_league_id": _int(node, "NativeLeagueID"),
        # HL-161: edad ACTUAL — playerdetails.xml funciona para cualquier
        # jugador por ID, aunque ya no esté en el equipo (verificado en vivo
        # 2026-08-04 con un jugador ya vendido). Sirve para reconstruir hacia
        # atrás la edad en el momento de una venta pasada — ver
        # `_backfill_age_at_sale` en `application/commands/sync_team.py`.
        "age_years": _int(node, "Age"),
        "age_days": _int(node, "AgeDays"),
        # HL-161: Carácter y Especialidad — casi no cambian con el tiempo,
        # así que el valor de HOY sirve como base razonable para un
        # jugador ya vendido, a diferencia de la edad o las habilidades.
        "agreeability": _int(node, "Agreeability"),
        "specialty": _int(node, "Specialty"),
    }
    if node.find("CareerAssists") is not None:
        out["career_assists"] = _int(node, "CareerAssists")
    # 2026-08-05: Caps/CapsU20 — totales de carrera con la selección
    # nacional (mayor y sub-20). Única forma barata de saber "sí, este
    # jugador ha jugado con la selección": no hay llamada CHPP nueva, viene
    # en la misma respuesta que ya se pedía para MotherClub/LastMatch.
    if node.find("Caps") is not None:
        out["caps"] = _int(node, "Caps")
    if node.find("CapsU20") is not None:
        out["caps_u20"] = _int(node, "CapsU20")
    # 2026-08-09, bug real: cuando CHPP no tiene un último partido real que
    # contar, `<LastMatch>` SIGUE presente pero con todo en cero/vacío
    # (`MatchId=0`, `Date=0001-01-01`, `PositionCode=0`...) — un sentinel
    # "sin dato", no una posición real. `if last_match is not None` solo
    # comprueba que el ELEMENTO existe, así que ese cero se colaba como si
    # `PositionCode=0` fuera real: `match_role_name(0)` cae al fallback
    # "posicion 0 (sin traducir)" y ESO es lo que se mostraba (Comparativa
    # de liga y, para cualquier jugador propio en la misma situación,
    # "Última semana" en Posiciones). `MatchId == 0` es la señal fiable de
    # sentinel — un matchID real de Hattrick nunca es 0.
    if last_match is not None and _int(last_match, "MatchId") != 0:
        out["last_match"] = {
            "ht_match_id": _int(last_match, "MatchId"),
            "position_code": _int(last_match, "PositionCode"),
            "played_minutes": _int(last_match, "PlayedMinutes"),
            "rating": _float(last_match, "Rating"),
            # 2026-08-09, pedido explícitamente: "Última semana"/"Último
            # partido" solo debe mostrar dato si el partido fue de verdad
            # reciente — `LastMatch` es literalmente "el último partido con
            # datos de este jugador", que para uno que casi no juega puede
            # ser de hace más de un año (caso real: Volodymyr Manakin,
            # 2025-04-02). Sin esta fecha no hay forma de distinguir "jugó
            # la semana pasada" de "no juega hace mucho".
            "played_at": _txt(last_match, "Date", ""),
        }
    return out


@register("transfersteam")
def parse_transfersteam(xml: bytes) -> dict[str, Any]:
    """transfersteam.xml — historial de compraventas del propio equipo.

    CORRECCIÓN 2026-08-04: "solo se ve la página más reciente" YA NO es
    cierto — verificado en vivo contra la cuenta real que `pageIndex`
    (1-indexado, 1 = más reciente) SÍ pagina de verdad: `pageIndex=2`
    devuelve una ventana de fechas más vieja que `pageIndex=1`, y
    `<Transfers><Pages>` da el total real (40 páginas ≈ 995 transferencias
    para esta cuenta, consistente con `<Stats><NumberOfBuys>+<NumberOfSales>`
    y con que la página más allá de `Pages` viene vacía). Otros nombres de
    parámetro probados en vivo y descartados por no hacer nada:
    `page`/`Page`/`endDate`/`toDate`/`beforeDate`/`firstTransferIndex`/
    `startIndex`/`offset` — todos devolvían siempre la página 1. Ver
    `_apply_transfers_history` (sync_team.py) para el paginado real.

    `<Stats>` (TotalSumOfBuys/TotalSumOfSales/NumberOfBuys/NumberOfSales) es
    un agregado de TODA la historia del equipo, no de la página pedida —
    verificado en vivo (el mismo bloque aparece idéntico en cualquier
    página) — así que basta UNA llamada para los KPI de "Resumen".

    CORRECCIÓN 2026-08-03: un comentario anterior decía que
    `transferplayer.xml` (historial de UN jugador) devolvía 401 por scope
    OAuth — era un error de nombre de fichero (`transferplayer`, sin la
    "s"), no una restricción real. El fichero correcto es
    `transfersplayer.xml` (ver `docs/chpp-reference/transfersplayer.txt`)
    y sí funciona con el token de esta app — verificado en vivo, trae el
    historial completo de transferencias de un jugador concreto, comprador
    y vendedor incluidos.

    CORRECCIÓN 2026-08-03 (bis): `TransferType`, `Price`, `Buyer` y `Seller`
    son hermanos de `Player` dentro de `Transfer` — NO están anidados
    dentro de `Player`. Confirmado en vivo contra la cuenta real (venta de
    Lander Fripont, 495018863): la versión anterior de este parser los
    buscaba dentro de `Player`, así que siempre venían vacíos/0 y
    `_persist_transfers` nunca detectó ni una compra ni una venta en
    producción — el fixture de pruebas tenía la misma anidación
    equivocada, por eso el test unitario nunca lo pilló."""
    root = ElementTree.fromstring(xml)
    stats = root.find(".//Stats")
    transfers_node = root.find(".//Transfers")
    transfers = []
    for node in root.iterfind(".//Transfer"):
        player = node.find("Player")
        if player is None:
            continue
        buyer = node.find("Buyer")
        seller = node.find("Seller")
        transfers.append({
            "ht_transfer_id": _int(node, "TransferID"),
            "ht_player_id": _int(player, "PlayerID"),
            "player_name": _txt(player, "PlayerName", ""),
            "transfer_type": _txt(node, "TransferType", ""),
            "buyer_team_id": _int(buyer, "BuyerTeamID") if buyer is not None else 0,
            "seller_team_id": _int(seller, "SellerTeamID") if seller is not None else 0,
            "price": _int(node, "Price"),
            "deadline": _txt(node, "Deadline", ""),
            # HL-161: TSI en el momento EXACTO de esta transacción — la
            # única fuente real de "TSI en la compra"/"TSI en la venta"
            # (playerdetails.xml solo da el de HOY, que ya cambió).
            "tsi": _int(player, "TSI"),
        })
    return {
        "transfers": transfers,
        "page_index": _int(transfers_node, "PageIndex") if transfers_node is not None else 1,
        "pages": _int(transfers_node, "Pages") if transfers_node is not None else 1,
        "stats": {
            "total_sum_of_buys": _int(stats, "TotalSumOfBuys") if stats is not None else 0,
            "total_sum_of_sales": _int(stats, "TotalSumOfSales") if stats is not None else 0,
            "number_of_buys": _int(stats, "NumberOfBuys") if stats is not None else 0,
            "number_of_sales": _int(stats, "NumberOfSales") if stats is not None else 0,
        },
    }


@register("transfersplayer")
def parse_transfersplayer(xml: bytes) -> dict[str, Any]:
    """transfersplayer.xml — historial COMPLETO de transferencias de UN
    jugador concreto (todas las veces que ha cambiado de club, no solo
    mientras estuvo con nosotros). HL-161: la única forma de recuperar el
    precio de compra real de un jugador que ya estaba en el equipo antes de
    empezar a sincronizar con esta app — `transfersteam.xml` solo ve la
    página más reciente del historial DEL EQUIPO, que no llega tan atrás.

    Verificado en vivo con el token de esta app (antes se creía, por un
    error de nombre de fichero, que devolvía 401 — ver
    `parse_transfersteam`)."""
    root = ElementTree.fromstring(xml)
    player = root.find(".//Player")
    transfers = []
    for node in root.iterfind(".//Transfer"):
        buyer = node.find("Buyer")
        seller = node.find("Seller")
        transfers.append({
            "ht_transfer_id": _int(node, "TransferID"),
            "deadline": _txt(node, "Deadline", ""),
            "buyer_team_id": _int(buyer, "BuyerTeamID") if buyer is not None else 0,
            "buyer_team_name": _txt(buyer, "BuyerTeamName", "") if buyer is not None else "",
            "seller_team_id": _int(seller, "SellerTeamID") if seller is not None else 0,
            "seller_team_name": _txt(seller, "SellerTeamName", "") if seller is not None else "",
            "price": _int(node, "Price"),
            "tsi": _int(node, "TSI"),
        })
    return {
        "ht_player_id": _int(player, "PlayerID") if player is not None else 0,
        "player_name": _txt(player, "PlayerName", "") if player is not None else "",
        # Ordenados por CHPP del más reciente al más antiguo.
        "transfers": transfers,
    }


@register("currentbids")
def parse_currentbids(xml: bytes) -> dict[str, Any]:
    """currentbids.xml — jugadores propios ACTUALMENTE en el mercado.

    HL-161: CHPP no da un historial de cuántas veces se ha listado un
    jugador (solo esta foto del momento), así que `listing_count` se
    cuenta hacia adelante: cada sync compara contra la foto anterior y
    cuenta una aparición nueva como un intento de venta más — ver
    `_persist_currentbids`. Subestima jugadores listados antes de que
    existiera esta columna."""
    root = ElementTree.fromstring(xml)
    listed = []
    for node in root.iterfind(".//BidItem"):
        listed.append({
            "ht_player_id": _int(node, "PlayerId"),
            "player_name": _txt(node, "PlayerName", ""),
            "deadline": _txt(node, "Deadline", ""),
            # 2026-08-08: precio de la puja más alta en el momento de la
            # detección — `None` si CHPP todavía no reporta ninguna puja
            # (nodo `HighestBid` ausente, no 0 real).
            "highest_bid": (
                _int(node, "HighestBid/Amount") if node.find("HighestBid") is not None else None
            ),
        })
    return {"listed_players": listed}


@register("training")
def parse_training(xml: bytes) -> dict[str, Any]:
    root = ElementTree.fromstring(xml)
    team = root.find(".//Team")
    if team is None:
        return {}
    trainer = team.find("Trainer")
    formation_xp = {
        el.tag.removeprefix("Experience"): int(el.text or 0)
        for el in team
        if el.tag.startswith("Experience") and el.text
    }
    return {
        "ht_team_id": _int(team, "TeamID"),
        "training_type": _int(team, "TrainingType"),
        "training_level": _int(team, "TrainingLevel"),
        "new_training_level": _int(team, "NewTrainingLevel"),
        "stamina_part": _int(team, "StaminaTrainingPart"),
        "last_training_type": _int(team, "LastTrainingTrainingType"),
        "last_training_level": _int(team, "LastTrainingTrainingLevel"),
        "last_stamina_part": _int(team, "LastTrainingStaminaTrainingPart"),
        "trainer_ht_id": _int(trainer, "TrainerID") if trainer is not None else 0,
        "trainer_name": _txt(trainer, "TrainerName", "") if trainer is not None else "",
        "morale": _int(team, "Morale", -1),
        "self_confidence": _int(team, "SelfConfidence", -1),
        "formation_xp": formation_xp,
    }


@register("matches")
def parse_matches(xml: bytes) -> dict[str, Any]:
    """Calendario y resultados del equipo. HL-070.

    `CupLevel`/`CupLevelIndex` (pedidos con `version=2.9`) identifican qué
    copa concreta es cada partido — hay varias en paralelo (la principal y,
    tras caer eliminado, las de consolación) y CHPP no numera la ronda
    directamente. Contando los partidos que comparten el mismo par se puede
    ESTIMAR la ronda (HL-116); no vienen en todas las versiones del fichero,
    así que quedan a -1 cuando faltan."""
    root = ElementTree.fromstring(xml)
    out = []
    for mt in root.iterfind(".//Match"):
        home = mt.find("HomeTeam")
        away = mt.find("AwayTeam")
        out.append({
            "ht_match_id": _int(mt, "MatchID"),
            "home_team_id": _int(home, "HomeTeamID") if home is not None else 0,
            "home_team_name": _txt(home, "HomeTeamName", "") if home is not None else "",
            "away_team_id": _int(away, "AwayTeamID") if away is not None else 0,
            "away_team_name": _txt(away, "AwayTeamName", "") if away is not None else "",
            "match_date": _txt(mt, "MatchDate", ""),
            "match_type": _int(mt, "MatchType"),
            "status": _txt(mt, "Status", ""),
            "home_goals": _int(mt, "HomeGoals", -1),
            "away_goals": _int(mt, "AwayGoals", -1),
            "cup_level": _int(mt, "CupLevel", -1),
            "cup_level_index": _int(mt, "CupLevelIndex", -1),
            "source_system": _txt(mt, "SourceSystem", "").lower() or None,
            "orders_given": _optional_bool(mt, "OrdersGiven"),
        })
    return {"matches": out}


@register("matchesarchive")
def parse_matchesarchive(xml: bytes) -> dict[str, Any]:
    """matchesarchive.xml — HL-161, 2026-08-14: lista de partidos de UN
    equipo entre dos fechas (`FirstMatchDate`/`LastMatchDate`), sin importar
    cuándo se sincronizó por primera vez esta app. Verificado en vivo contra
    el equipo real (teamID, ventana 2025-07-28→2025-09-28): a diferencia de
    `matches.xml` (que solo da lo reciente/próximo), esta acción sí retrocede
    a temporadas ya cerradas — es la pieza que faltaba para reconstruir
    cuántos partidos jugó con nosotros un jugador que ya se fue.

    Trae menos campos que `matches.xml`: sin `Status`, `CupLevel(Index)`,
    `SourceSystem` ni `OrdersGiven` — ninguno existe en este fichero, así
    que no se inventan aquí con un default."""
    root = ElementTree.fromstring(xml)
    out = []
    for mt in root.iterfind(".//Match"):
        home = mt.find("HomeTeam")
        away = mt.find("AwayTeam")
        out.append({
            "ht_match_id": _int(mt, "MatchID"),
            "home_team_id": _int(home, "HomeTeamID") if home is not None else 0,
            "home_team_name": _txt(home, "HomeTeamName", "") if home is not None else "",
            "away_team_id": _int(away, "AwayTeamID") if away is not None else 0,
            "away_team_name": _txt(away, "AwayTeamName", "") if away is not None else "",
            "match_date": _txt(mt, "MatchDate", ""),
            "match_type": _int(mt, "MatchType"),
            "home_goals": _int(mt, "HomeGoals", -1),
            "away_goals": _int(mt, "AwayGoals", -1),
        })
    return {"matches": out}


@register("matchorders")
def parse_matchorders(xml: bytes) -> dict[str, Any]:
    """Órdenes enviadas o predicción oficial (`matchorders.xml` 3.0).

    `MatchData Available=false` no es un error: significa que el partido no
    pertenece al usuario o que las órdenes ya no están disponibles. La
    alineación titular vive en `Lineup/Positions`, separada del banco y de los
    lanzadores; solo esa lista debe alimentar cálculos del once inicial.

    Con `actionType=predictratings`, en cambio, CHPP devuelve otro contrato:
    `MatchData` no lleva el atributo `Available` y contiene directamente la
    táctica, su nivel y los siete ratings. Se detecta por los tags de rating,
    no por el atributo, para no confundir una predicción válida con órdenes
    privadas/no disponibles.
    """
    root = ElementTree.fromstring(xml)
    # 2026-08-15, verificado en vivo: `actionType=predictratings` puede devolver
    # HTTP 200 con `chpperror.xml` ("Sequence contains no matching element").
    # Sin esta rama el parser devolvía un dict con `ht_match_id=0`, el sync lo
    # descartaba en silencio por no coincidir el ID y los ratings VIEJOS se
    # quedaban en la base pareados con una alineación nueva.
    if _is_chpp_error(root):
        return {
            "ht_match_id": 0,
            "available": False,
            "positions": [],
            "prediction": None,
            "chpp_error": _txt(root, "Error", ""),
            "chpp_error_code": _int(root, "ErrorCode"),
        }
    match_data = root.find("MatchData")
    if match_data is None:
        match_data = root.find(".//MatchData")
    is_rating_prediction = bool(
        match_data is not None and match_data.find("RatingMidfield") is not None
    )
    available = bool(
        match_data is not None
        and match_data.attrib.get("Available", "").strip().lower() in ("true", "1")
    )

    positions: list[dict[str, Any]] = []
    if available and match_data is not None:
        for player in match_data.iterfind("./Lineup/Positions/Player"):
            player_id = _int(player, "PlayerID")
            if player_id <= 0:
                continue
            positions.append({
                "ht_player_id": player_id,
                "role_id": _int(player, "RoleID"),
                "behaviour": _int(player, "Behaviour"),
            })

    coach_modifier: int | None = None
    if match_data is not None:
        coach = match_data.find("CoachModifier")
        if coach is not None and coach.text and coach.text.strip():
            coach_modifier = int(coach.text)

    prediction: dict[str, Any] | None = None
    if is_rating_prediction and match_data is not None:
        prediction = {
            "tactic_type": _int(match_data, "TacticType"),
            "tactic_skill": _int(match_data, "TacticSkill"),
            "ratings": {
                "midfield": _int(match_data, "RatingMidfield"),
                "right_def": _int(match_data, "RatingRightDef"),
                "central_def": _int(match_data, "RatingMidDef"),
                "left_def": _int(match_data, "RatingLeftDef"),
                "right_att": _int(match_data, "RatingRightAtt"),
                "central_att": _int(match_data, "RatingMidAtt"),
                "left_att": _int(match_data, "RatingLeftAtt"),
            },
        }

    return {
        "ht_match_id": _int(root, "MatchID"),
        "source_system": (
            _txt(root, "SourceSystem", "") or _txt(root, "sourceSystem", "")
        ).lower() or None,
        "available": available,
        "match_date": _txt(match_data, "MatchDate", "") if match_data is not None else "",
        "match_type": _int(match_data, "MatchType") if match_data is not None else 0,
        "attitude": _int(match_data, "Attitude") if match_data is not None else None,
        "tactic_type": _int(match_data, "TacticType") if match_data is not None else None,
        "coach_modifier": coach_modifier,
        "positions": positions,
        "prediction": prediction,
    }


@register("matchdetails")
def parse_matchdetails(xml: bytes) -> dict[str, Any]:
    """Ratings por sector, posesión, táctica y eventos. HL-071, HL-072."""
    root = ElementTree.fromstring(xml)
    mt = root.find(".//Match")
    if mt is None:
        return {}

    def side(tag: str) -> dict[str, Any]:
        t = mt.find(tag)
        if t is None:
            return {}
        return {
            "team_id": _int(t, "HomeTeamID" if tag == "HomeTeam" else "AwayTeamID"),
            "name": _txt(t, "HomeTeamName" if tag == "HomeTeam" else "AwayTeamName", "")
                    or _txt(t, "TeamName", ""),
            "goals": _int(t, "HomeGoals" if tag == "HomeTeam" else "AwayGoals"),
            "ratings": {
                "midfield": _int(t, "RatingMidfield"),
                "right_def": _int(t, "RatingRightDef"),
                "central_def": _int(t, "RatingMidDef"),
                "left_def": _int(t, "RatingLeftDef"),
                "right_att": _int(t, "RatingRightAtt"),
                "central_att": _int(t, "RatingMidAtt"),
                "left_att": _int(t, "RatingLeftAtt"),
            },
            # Formation y TacticSkill son públicos para AMBOS lados (verificado
            # en vivo) — a diferencia de TeamAttitude, que solo viene para el
            # tuyo. TacticSkill=0 coincide con TacticType=0 ("Normal"): no es
            # un valor oculto, es que ese partido no usó una táctica especial.
            "formation": _txt(t, "Formation", ""),
            "tactic_type": _int(t, "TacticType"),
            "tactic_skill": _int(t, "TacticSkill"),
            # -1 es un TeamAttitude real ("Jugar relajados"), no un valor
            # ausente — CHPP simplemente no incluye la etiqueta <TeamAttitude>
            # para el lado que no es el del usuario (verificado en vivo: el
            # propio equipo la trae siempre, un rival nunca). Sin esta
            # bandera, ese "tag ausente" se confundía con el código real -1.
            "attitude": _int(t, "TeamAttitude", -1),
            "attitude_is_read": t.find("TeamAttitude") is not None,
            # HL-2xx, 2026-08-12: se asumía un `<Event>`/EventTypeID por
            # ocasión (nunca existió en la v3.1 real, verificado en vivo).
            # Lo real es un conteo por zona, sin desglose de goles por zona.
            "chances": {
                "left": _int(t, "NrOfChancesLeft"),
                "center": _int(t, "NrOfChancesCenter"),
                "right": _int(t, "NrOfChancesRight"),
                "special": _int(t, "NrOfChancesSpecialEvents"),
                "other": _int(t, "NrOfChancesOther"),
            },
        }

    arena_el = mt.find("Arena")

    return {
        "ht_match_id": _int(mt, "MatchID"),
        "match_type": _int(mt, "MatchType"),
        "match_date": _txt(mt, "MatchDate", ""),
        "home": side("HomeTeam"),
        "away": side("AwayTeam"),
        "possession": {
            "first_half_home": _int(mt, "PossessionFirstHalfHome"),
            "first_half_away": _int(mt, "PossessionFirstHalfAway"),
            "second_half_home": _int(mt, "PossessionSecondHalfHome"),
            "second_half_away": _int(mt, "PossessionSecondHalfAway"),
        },
        "arena": {
            "name": _txt(arena_el if arena_el is not None else mt, "ArenaName", ""),
            "spectators": _int(arena_el if arena_el is not None else mt, "SoldTotal"),
            "weather": _int(arena_el if arena_el is not None else mt, "WeatherID", -1),
            # `matchdetails` no trae el aforo: sólo cuántas entradas se
            # vendieron por sector. El aforo actual llega una vez por equipo
            # en `arenadetails`; se combina al persistir el historial.
            "sold_terraces": _int(arena_el if arena_el is not None else mt, "SoldTerraces"),
            "sold_basic": _int(arena_el if arena_el is not None else mt, "SoldBasic"),
            "sold_roof": _int(arena_el if arena_el is not None else mt, "SoldRoof"),
            "sold_vip": _int(arena_el if arena_el is not None else mt, "SoldVIP"),
        },
    }


@register("arenadetails")
def parse_arenadetails(xml: bytes) -> dict[str, Any]:
    """Aforo actual por sector.

    Hattrick no publica una serie histórica de aforos por partido: este es
    el estado actual del estadio. Se guarda junto a cada reporte de asistencia
    con esa limitación declarada por la consulta del estadio.
    """
    root = ElementTree.fromstring(xml)
    arena = root.find(".//Arena")
    if arena is None:
        return {}
    capacity = arena.find("CurrentCapacity")
    if capacity is None:
        return {"current_capacity": None}
    available = capacity.get("Available", "true").lower() in ("true", "1")
    current = {
        "terraces": _int(capacity, "Terraces"),
        "basic": _int(capacity, "Basic"),
        "roof": _int(capacity, "Roof"),
        "vip": _int(capacity, "VIP"),
        "total": _int(capacity, "Total"),
    }
    team = arena.find("Team")
    return {
        "ht_team_id": _int(team if team is not None else arena, "TeamID"),
        "current_capacity": current if available and current["total"] > 0 else None,
    }


#  1 Portero            6 Lateral izq.      11 Extremo izq.
#  2 Lateral der.        7 Extremo der.      12 Delantero der.
#  3 Def. central der.   8 Interior der.     13 Delantero medio
#  4 Def. central medio  9 Interior medio    14 Delantero izq.
#  5 Def. central izq.  10 Interior izq.
# Roles especiales (no de campo): 17 balón parado, 18 capitán,
# 19-21 "reemplazó al titular N" (suplente que entró).
MATCHLINEUP_KEEPER_CODE = 1
MATCHLINEUP_SPECIAL_ROLES = {17, 18, 19, 20, 21}


@register("matchlineup")
def parse_matchlineup(xml: bytes) -> dict[str, Any]:
    """Alineación real (nombre + posición jugada) de un equipo en un partido ya
    finalizado. Requiere `teamID` explícito en la request: sin él, CHPP solo
    da la alineación del equipo dueño del token, nunca la del rival.

    Un partido ya finalizado es un hecho público permanente — no choca con la
    regla CHPP de "nunca histórico de un rival" (esa regla es sobre trackear
    el estado de una cuenta ajena a lo largo del tiempo, no sobre leer el
    reporte público de un partido que ya se jugó).

    2026-08-09, corregido tras un caso real: `RoleID` cambia de significado
    según la versión pedida (verificado en vivo, matchID 770453114). Sin
    `version` explícito (lo que hace este parser desde siempre) CHPP sirve
    ~1.2: ahí `RoleID` es solo un índice secuencial (1, 2, 3... orden de
    aparición, sin significado táctico) y la posición real está en
    `PositionCode` (1-16, MATCH_POSITION_* en ht_constants.py) — así sigue
    llamándolo `rivals.py` para el marcaje al hombre, y así debe seguir. A
    partir de v1.4, `RoleID` pasa a usar el esquema 100+ real
    (MATCH_ROLE_*, MATCH_ROLE_NAMES) y `PositionCode` deja de aportar nada
    nuevo; desde v1.5 `PositionCode` directamente desaparece del XML. A
    partir de v2.1 además: `PlayerName` se parte en `FirstName`+`LastName`
    (se reconstruye aquí para no romper a los llamadores existentes), y
    aparece `<StartingLineup>` (el once ORIGINAL, antes de cualquier
    cambio) junto al `<Lineup>` de siempre (que en 2.1 ya refleja el
    estado FINAL tras cada `<Substitution>` — con el RoleID real que
    ocupó cada suplente al entrar, algo que ninguna versión anterior
    daba). Por eso este parser solo lee `<Lineup>`, nunca
    `<StartingLineup>` — leer ambos duplicaría a todo titular que no fue
    sustituido."""
    root = ElementTree.fromstring(xml)
    team = root.find(".//Team")
    if team is None:
        return {}
    lineup = team.find("Lineup")
    players = [
        {
            "ht_player_id": _int(p, "PlayerID"),
            "name": (
                _txt(p, "PlayerName", "")
                or f"{_txt(p, 'FirstName', '')} {_txt(p, 'LastName', '')}".strip()
            ),
            "role_id": _int(p, "RoleID"),
            "position_code": _int(p, "PositionCode", -1),
            "rating_stars": _float(p, "RatingStars"),
            # Lectura al pitazo final: permite contrastar una eventual caída
            # dentro de un partido ya jugado, sin inventar una curva de fatiga.
            "rating_stars_end": _float(p, "RatingStarsEndOfMatch"),
            "behaviour": _int(p, "Behaviour"),
        }
        for p in (lineup.iterfind("Player") if lineup is not None else [])
    ]
    return {
        "ht_match_id": _int(root, "MatchID"),
        "ht_team_id": _int(team, "TeamID"),
        "team_name": _txt(team, "TeamName", ""),
        "players": players,
    }


@register("leaguedetails")
def parse_leaguedetails(xml: bytes) -> dict[str, Any]:
    """Clasificación de la serie. HL-080."""
    root = ElementTree.fromstring(xml)
    teams = []
    for t in root.iterfind(".//Team"):
        teams.append({
            "ht_team_id": _int(t, "TeamID"),
            "name": _txt(t, "TeamName", ""),
            "position": _int(t, "Position"),
            "matches": _int(t, "Matches"),
            "won": _int(t, "Won"),
            "draws": _int(t, "Draws"),
            "lost": _int(t, "Lost"),
            "goals_for": _int(t, "GoalsFor"),
            "goals_against": _int(t, "GoalsAgainst"),
            "points": _int(t, "Points"),
        })
    return {
        "series_ht_id": _int(root, "LeagueLevelUnitID"),
        "series_name": _txt(root, "LeagueLevelUnitName", ""),
        # leaguedetails.xml no trae temporada: solo la trae worlddetails. La
        # jornada real es CurrentMatchRound — MatchRound no existe en este
        # fichero y siempre habría dado 0, dejando la jornada sin actualizar.
        "match_round": _int(root, "CurrentMatchRound"),
        # LeagueLevel: división de esta serie (1 = la más alta del país).
        # MaxLevel: cuántas divisiones tiene el país en total. Ambas hacen
        # falta para saber si esta serie es la cúspide (nadie asciende más)
        # o el fondo (nadie desciende más) — HL-145. -1 = no vino en el XML.
        "league_level": _int(root, "LeagueLevel", -1),
        "max_level": _int(root, "MaxLevel", -1),
        "teams": sorted(teams, key=lambda x: x["position"]),
    }


@register("leaguefixtures")
def parse_leaguefixtures(xml: bytes) -> dict[str, Any]:
    """Calendario COMPLETO de la serie — HL-090 fix.

    A diferencia de matches.xml (que solo trae los partidos del equipo
    pedido con teamID), este fichero devuelve los 56 cruces de una liga de
    8 equipos (los 28 pares posibles, ida y vuelta), identificados por
    jornada real (MatchRound) — verificado en vivo. Sin esto, el simulador
    de temporada no tenía forma de saber qué pasa en un cruce entre dos
    rivales (ninguno el equipo propio) y los daba por congelados.

    HomeGoals/AwayGoals simplemente no vienen en el XML para partidos aún
    no jugados — None, no 0 ni -1, para no fabricar un resultado."""
    root = ElementTree.fromstring(xml)
    matches = []
    for mt in root.iterfind(".//Match"):
        home = mt.find("HomeTeam")
        away = mt.find("AwayTeam")
        home_goals_el = mt.find("HomeGoals")
        away_goals_el = mt.find("AwayGoals")
        matches.append({
            "ht_match_id": _int(mt, "MatchID"),
            "match_round": _int(mt, "MatchRound"),
            "home_team_id": _int(home, "HomeTeamID") if home is not None else 0,
            "home_team_name": _txt(home, "HomeTeamName", "") if home is not None else "",
            "away_team_id": _int(away, "AwayTeamID") if away is not None else 0,
            "away_team_name": _txt(away, "AwayTeamName", "") if away is not None else "",
            "match_date": _txt(mt, "MatchDate", ""),
            "home_goals": (
                int(home_goals_el.text)
                if home_goals_el is not None and home_goals_el.text else None
            ),
            "away_goals": (
                int(away_goals_el.text)
                if away_goals_el is not None and away_goals_el.text else None
            ),
        })
    return {
        "series_ht_id": _int(root, "LeagueLevelUnitID"),
        "series_name": _txt(root, "LeagueLevelUnitName", ""),
        "season": _int(root, "Season"),
        "matches": matches,
    }


@register("economy")
def parse_economy(xml: bytes) -> dict[str, Any]:
    root = ElementTree.fromstring(xml)
    team = root.find(".//Team")
    if team is None:
        return {}
    fields = (
        "Cash", "ExpectedCash", "SponsorsPopularity", "SupportersPopularity",
        "FanClubSize", "IncomeSpectators", "IncomeSponsors", "IncomeFinancial",
        "IncomeTemporary", "IncomeSum", "CostsArena", "CostsFinancial",
        "CostsStaff", "CostsTemporary", "CostsYouth", "CostsSum",
        "ExpectedWeeksTotal", "LastIncomeSum", "LastCostsSum", "LastWeeksTotal",
    )
    snake = {
        f: "".join("_" + c.lower() if c.isupper() else c for c in f).lstrip("_")
        for f in fields
    }

    def optional_money(*names: str) -> int | None:
        for name in names:
            node = team.find(name)
            if node is not None:
                return _int(team, name)
        return None

    # Las versiones recientes separan estas partidas. No se suman a
    # IncomeTemporary/CostsTemporary: cada campo se guarda como CHPP lo dio.
    # Todos opcionales (`None` si el XML no los trae) para no fingir un cero
    # donde en realidad no se sabe — sobre todo importante para los Last*, que
    # alimentan el desglose por categoría de semanas ya cerradas y que fichas
    # sincronizadas antes de este cambio simplemente no tienen. Sólo la
    # semana en curso trae el desglose de patrocinio (Bonuses); la semana ya
    # cerrada (Last*) nunca lo expuso en ninguna versión vista.
    detailed = {
        "income_sponsor_bonuses": optional_money("IncomeSponsorBonuses"),
        "income_sold_players": optional_money("IncomeSoldPlayers"),
        "income_sold_players_commission": optional_money("IncomeSoldPlayersCommission"),
        "costs_bought_players": optional_money("CostsBoughtPlayers"),
        "costs_arena_building": optional_money("CostsArenaBuilding"),
        "last_income_spectators": optional_money("LastIncomeSpectators"),
        "last_income_sponsors": optional_money("LastIncomeSponsors"),
        "last_income_financial": optional_money("LastIncomeFinancial"),
        "last_income_sold_players": optional_money("LastIncomeSoldPlayers"),
        "last_income_sold_players_commission": optional_money(
            "LastIncomeSoldPlayersCommission"
        ),
        "last_income_temporary": optional_money("LastIncomeTemporary"),
        "last_costs_arena": optional_money("LastCostsArena"),
        "last_costs_financial": optional_money("LastCostsFinancial"),
        "last_costs_staff": optional_money("LastCostsStaff"),
        "last_costs_youth": optional_money("LastCostsYouth"),
        "last_costs_bought_players": optional_money("LastCostsBoughtPlayers"),
        "last_costs_arena_building": optional_money("LastCostsArenaBuilding"),
        "last_costs_temporary": optional_money("LastCostsTemporary"),
        "last_costs_players": optional_money("LastCostsPlayer", "LastCostsPlayers"),
    }
    return {
        "ht_team_id": _int(team, "TeamID"),
        **{snake[f]: _int(team, f) for f in fields},
        # CostsPlayer es el nombre actual; CostsPlayers el de economy.xml 1.1.
        "costs_players": optional_money("CostsPlayer", "CostsPlayers") or 0,
        "income_temporary": optional_money("IncomeTemporary"),
        "costs_temporary": optional_money("CostsTemporary"),
        **detailed,
    }


@register("club")
def parse_club(xml: bytes) -> dict[str, Any]:
    """Inversión juvenil real. HL-2xx, 2026-08-12: `club.xml` v1.1 (verificado
    en vivo) YA NO trae `<Staff>` ni los niveles agregados por puesto
    (`AssistantTrainerLevels` y hermanos) — solo `<Specialists>` (booleanos
    de si hay o no un especialista de cada tipo) y `<YouthSquad>`. El
    desglose real de staff (persona por persona, con su nivel de verdad)
    siempre vivió en `stafflist.xml` — ver `parse_stafflist` y
    `STAFF_TYPE_TO_FIELD` en ht_constants.py.

    OJO con `youth_investment`: se sigue guardando porque es lo que trae el
    fichero, pero **no sirve para mostrar el gasto de la academia**. Fetch en
    vivo 2026-08-15: Hattrick devuelve `<Investment>0</Investment>` con el
    club invirtiendo de verdad 200.000 SEK/semana. El gasto real es
    `CostsYouth` de economy.xml — así lo leen ya `academy.py` y `club.py`."""
    root = ElementTree.fromstring(xml)
    team = root.find(".//Team")
    if team is None:
        return {}
    youth = team.find("YouthSquad")
    return {
        "ht_team_id": _int(team, "TeamID"),
        "youth_investment": _int(youth, "Investment") if youth is not None else 0,
        "youth_level": _int(youth, "YouthLevel") if youth is not None else 0,
        "youth_has_promoted": _txt(youth, "HasPromoted", "False").lower() in ("true", "1")
        if youth is not None else False,
    }


# youthplayerlist.xml: nombre del tag CHPP -> campo de YouthSnapshot. El
# fichero usa "Defender/Playmaker/Scorer" donde el resto de la app dice
# "defending/playmaking/scoring" (players.xml usa otros nombres todavía), así
# que la traducción vive aquí y no se propaga al dominio.
YOUTH_SKILL_TAGS: dict[str, str] = {
    "Keeper": "keeper",
    "Defender": "defending",
    "Playmaker": "playmaking",
    "Winger": "winger",
    "Passing": "passing",
    "Scorer": "scoring",
    "SetPieces": "set_pieces",
}


def _youth_skill(skills: Element | None, tag: str) -> int | None:
    """Nivel de una skill juvenil, o `None` si el ojeador aún no la reveló.

    Distinguir "no revelado" de "cero" es el punto entero del módulo: un techo
    desconocido no es un techo bajo (ver `academy_engine`). CHPP lo marca con
    `IsAvailable="False"` y el elemento vacío — nunca con un 0.
    """
    if skills is None:
        return None
    node = skills.find(tag)
    if node is None or (node.get("IsAvailable", "False").lower() != "true"):
        return None
    text = (node.text or "").strip()
    return int(text) if text.isdigit() else None


def _youth_max_reached(skills: Element | None, tag: str) -> bool:
    """¿Esta habilidad ya tocó su techo?

    CHPP lo publica como atributo `IsMaxReached` del nivel actual, y se sabe
    aunque el techo en sí siga oculto. Importa para decidir a quién entrenar:
    una habilidad topada no va a subir más por mucho que se entrene, así que
    no puntúa aunque su nivel sea alto.
    """
    if skills is None:
        return False
    node = skills.find(tag)
    if node is None:
        return False
    return node.get("IsMaxReached", "False").lower() == "true"


@register("youthteamdetails")
def parse_youthteamdetails(xml: bytes) -> dict[str, Any]:
    """Identidad y FECHA DE CREACIÓN de la academia juvenil actual.

    2026-08-15, pedido explícitamente: una academia se puede cerrar y volver a
    abrir, y cada apertura es una academia distinta con su propio `YouthTeamID`
    y su `CreatedDate`. Sin ese dato, el ROI de la cantera sumaba canteranos de
    academias anteriores contra la inversión de la actual — cifras de dos cosas
    distintas mezcladas. Verificado contra el fichero real de la cuenta.
    """
    root = ElementTree.fromstring(xml)
    team = root.find(".//YouthTeam")
    if team is None:
        return {}
    return {
        "ht_youth_team_id": _int(team, "YouthTeamID"),
        "youth_team_name": _txt(team, "YouthTeamName", ""),
        "created_date": _txt(team, "CreatedDate", ""),
    }


@register("youthplayerlist")
def parse_youthplayerlist(xml: bytes) -> dict[str, Any]:
    """Plantilla juvenil con nivel actual y techo por habilidad.

    Verificado contra el fichero real 2026-08-15. Se pide con
    `actionType=details` para que venga `<PlayerSkills>`; sin eso el fichero
    trae sólo identidades y el módulo de academia se queda sin nada que
    evaluar.
    """
    root = ElementTree.fromstring(xml)
    players: list[dict[str, Any]] = []
    for p in root.findall(".//YouthPlayer"):
        skills = p.find("PlayerSkills")
        last_match = p.find("LastMatch")
        row: dict[str, Any] = {
            "ht_youth_player_id": _int(p, "YouthPlayerID"),
            "first_name": _txt(p, "FirstName", ""),
            "last_name": _txt(p, "LastName", ""),
            "age_years": _int(p, "Age"),
            "age_days": _int(p, "AgeDays"),
            "arrival_date": _txt(p, "ArrivalDate", ""),
            # Días que faltan para poder promocionarlo al primer equipo: es el
            # plazo que la pantalla muestra en rojo cuando se acaba.
            "can_be_promoted_in": _int(p, "CanBePromotedIn"),
            "minutes_last_match": (
                _int(last_match, "PlayedMinutes") if last_match is not None else 0
            ),
        }
        for tag, field_name in YOUTH_SKILL_TAGS.items():
            row[field_name] = _youth_skill(skills, f"{tag}Skill")
            row[f"{field_name}_max"] = _youth_skill(skills, f"{tag}SkillMax")
            row[f"{field_name}_max_reached"] = _youth_max_reached(skills, f"{tag}Skill")
        players.append(row)
    return {"youth_players": players}


# TrainerType (stafflist): 0 defensivo, 1 ofensivo, 2 equilibrado.
TRAINER_TYPE = {0: "defensivo", 1: "ofensivo", 2: "equilibrado"}
# TrainerStatus: 1 jugador-entrenador, 2 solo entrenador, 3 entrenador del HoF.
TRAINER_STATUS = {1: "jugador-entrenador", 2: "entrenador", 3: "entrenador HoF"}


@register("stafflist")
def parse_stafflist(xml: bytes) -> dict[str, Any]:
    """Entrenador principal (con su nivel real 1–5 y tipo) y resto del staff.
    Junto a `training` y `club`, el nivel del entrenador deja de ser un supuesto."""
    root = ElementTree.fromstring(xml)
    sl = root.find(".//StaffList")
    if sl is None:
        return {}
    tr = sl.find("Trainer")
    trainer = {}
    if tr is not None:
        tt = _int(tr, "TrainerType")
        ts = _int(tr, "TrainerStatus")
        trainer = {
            "ht_trainer_id": _int(tr, "TrainerId"),
            "name": _txt(tr, "Name", ""),
            "age_years": _int(tr, "Age"),
            "age_days": _int(tr, "AgeDays"),
            "cost": _int(tr, "Cost"),
            "trainer_type": tt,
            "trainer_type_name": TRAINER_TYPE.get(tt, "desconocido"),
            "leadership": _int(tr, "Leadership"),
            "skill_level": _int(tr, "TrainerSkillLevel"),
            "status": ts,
            "status_name": TRAINER_STATUS.get(ts, "desconocido"),
        }
    members = [
        {
            "ht_staff_id": _int(st, "StaffId"),
            "name": _txt(st, "Name", ""),
            "staff_type": _int(st, "StaffType"),
            "level": _int(st, "StaffLevel"),
            "cost": _int(st, "Cost"),
        }
        for st in sl.iterfind(".//Staff")
    ]
    return {
        "trainer": trainer,
        "staff_members": members,
        "total_staff": _int(sl, "TotalStaffMembers"),
        "total_cost": _int(sl, "TotalCost"),
    }


@register("regiondetails")
def parse_regiondetails(xml: bytes) -> dict[str, Any]:
    """regiondetails.xml — el clima de una región, hoy y mañana.

    Hattrick solo publica el pronóstico a un día vista: `WeatherID` es el de
    HOY y `TomorrowWeatherID` el de mañana, ambos referidos al reloj del
    servidor. Por eso se guarda también `FetchedDate`: sin saber qué día era
    "hoy" cuando se pidió, los dos números no se pueden situar en el
    calendario y un pronóstico de anteayer se leería como el de esta tarde.
    """
    root = ElementTree.fromstring(xml)
    region = root.find(".//Region")
    if region is None:
        return {}
    return {
        "ht_region_id": _int(region, "RegionID"),
        "region_name": _txt(region, "RegionName", ""),
        "ht_league_id": _int(root.find(".//League"), "LeagueID")
        if root.find(".//League") is not None else 0,
        "weather_today": _int(region, "WeatherID", -1),
        "weather_tomorrow": _int(region, "TomorrowWeatherID", -1),
        "fetched_at": _txt(root, "FetchedDate", ""),
    }


@register("worlddetails")
def parse_worlddetails(xml: bytes) -> dict[str, Any]:
    """Contexto del mundo: tasa de moneda, temporada, jornada, copas y fechas
    reales — de TODOS los países en `<LeagueList>`, no solo uno.

    CORRECCIÓN 2026-08-04: la versión anterior hacía `root.find(".//League")`
    (el PRIMER `<League>` del documento) y lo trataba como "el" contexto del
    mundo — en la práctica, cualquier país menos el del equipo real (se
    verificó en vivo que el registro guardado, LeagueID=50, es Grecia, no
    Colombia — el LeagueID real de Colombia es 19). Cada país tiene su
    PROPIA temporada (Suecia 95, Colombia 83, Grecia 80 — verificado en
    vivo), así que hace falta guardarlos TODOS y cruzar por
    `Team.ht_league_id` (de teamdetails.xml) para saber cuál es el del
    equipo — ver `_persist_world`. También trae `<Cups><Cup>` con el nombre
    real de cada copa del país, para reemplazar el `CUP_LEVEL_NAMES`
    hardcodeado de `cup.py`."""
    root = ElementTree.fromstring(xml)
    leagues = []
    for league in root.iterfind(".//LeagueList/League"):
        country = league.find("Country")
        cups = [
            {
                "ht_cup_id": _int(cup, "CupID"),
                "cup_name": _txt(cup, "CupName", ""),
                "cup_league_level": _int(cup, "CupLeagueLevel"),
                "cup_level": _int(cup, "CupLevel"),
                "cup_level_index": _int(cup, "CupLevelIndex"),
                "match_round": _int(cup, "MatchRound", -1),
                "match_rounds_left": _int(cup, "MatchRoundsLeft"),
            }
            for cup in league.iterfind(".//Cups/Cup")
        ]
        leagues.append({
            "ht_league_id": _int(league, "LeagueID"),
            "league_name": _txt(league, "LeagueName", ""),
            "country_id": _int(country, "CountryID") if country is not None else 0,
            "country_code": _txt(country, "CountryCode", "") if country is not None else "",
            "country_name": _txt(country, "CountryName", "") if country is not None else "",
            "season": _int(league, "Season"),
            "season_offset": _int(league, "SeasonOffset"),
            "match_round": _int(league, "MatchRound"),
            "match_rounds_left": _int(league, "MatchRoundsLeft"),
            "number_of_levels": _int(league, "NumberOfLevels"),
            "league_system_id": _int(league, "LeagueSystemID", 1),
            "currency_name": _txt(country, "CurrencyName", "") if country is not None else "",
            "currency_rate": _float(country, "CurrencyRate", 1.0) if country is not None else 1.0,
            "training_date": _txt(league, "TrainingDate", ""),
            "cup_match_date": _txt(league, "CupMatchDate", ""),
            "series_match_date": _txt(league, "SeriesMatchDate", ""),
            "economy_date": _txt(league, "EconomyDate", ""),
            "cups": cups,
        })
    return {"leagues": leagues}


@register("trainingevents")
def parse_trainingevents(xml: bytes) -> dict[str, Any]:
    """Subidas de habilidad CONFIRMADAS por Hattrick, con fecha (temporada +
    jornada + día). Es la evidencia con la que se calibra la experiencia sin
    inferir pops de snapshots.

    `SkillID` no venía en las tablas de traducción, así que se devuelve en crudo
    y el mapeo a nombre de habilidad vive en configuración marcado como
    provisional (ver training.yaml → skill_id_map)."""
    root = ElementTree.fromstring(xml)
    events = []
    for player in root.iterfind(".//Player"):
        pid = _int(player, "PlayerID")
        for ev in player.iterfind(".//TrainingEvent"):
            events.append({
                "ht_player_id": pid,
                "skill_id": _int(ev, "SkillID"),
                "old_level": _int(ev, "OldLevel"),
                "new_level": _int(ev, "NewLevel"),
                "season": _int(ev, "Season"),
                "match_round": _int(ev, "MatchRound"),
                "day_number": _int(ev, "DayNumber"),
            })
    return {"skill_ups": events}
