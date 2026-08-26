"""Scouting de rivales — HL-099 a HL-110, ampliado en HL-2xx.

Combina lo poco que CHPP deja ver de un equipo ajeno (TSI real vía
`players.xml`, nombre y posición reales vía `matchlineup.xml` de partidos ya
jugados, táctica/nivel/formación/rotación vía `matchdetails.xml`) con los
motores puros de `rival_scouting`. Todo lo del rival se pide en vivo en cada
request — nada se persiste — para no acabar trackeando el estado de una
cuenta que no es la del usuario.

HL-2xx: el análisis del rival (roster, marcaje, táctica, rotación) se basa
en sus ÚLTIMOS PARTIDOS OFICIALES REALES contra CUALQUIER equipo — ya no
exige que hayan sido contra el equipo propio. Antes, un rival con el que
nunca se hubiera jugado (o solo Duelos/Escaleras) no daba ninguna señal
salvo TSI; ahora se usa lo que el rival jugó de verdad, sea contra quien
sea, igual que haría un ojeador real. Duelos, Escaleras y partidos de
Selección nacional NUNCA cuentan para esto — no hay combinación de toggles
que los traiga de vuelta — porque no se consideran representativos de cómo
juega el CLUB rival normalmente (Selección: otro cuerpo técnico, a veces
otro país; decisión de producto confirmada con el usuario). Preparación
(pretemporada) sí puede contar, pero solo bajo el toggle de Amistosos: a
diferencia de Duelos/Escaleras, es contra un rival real con su plantilla
real.
"""
import json
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_team_owner
from app.api.rate_limit import limite
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.application.commands.sync_team import FILE_VERSIONS
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.next_match_analysis import probable_starters
from app.domain.engines.rival_scouting import (
    PitchZoneMethod,
    analyse_side_rotation,
    estimate_win_probability,
    pitch_zone_duels,
    pitch_zone_values,
    suggest_man_marking,
    summarise_tactics,
    tsi_kde_comparison,
)
from app.domain.value_objects.ht_constants import (
    FRIENDLY_MATCH_TYPES,
    MATCH_TYPE_DUEL,
    MATCH_TYPE_LADDER,
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE,
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES,
    MATCH_TYPE_NATIONAL_TEAM_FRIENDLY,
    MATCH_TYPE_PREPARATION,
    MATCH_TYPE_TOURNAMENT_LEAGUE,
    MATCH_TYPE_TOURNAMENT_PLAYOFF,
    match_position_name,
    match_type_name,
)
from app.domain.value_objects.ht_time import ht_to_utc
from app.infrastructure.chpp.client import CHPPAuthError, CHPPClient, CHPPUnavailableError
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import decrypt_token

router = APIRouter()

# 10 y no 5, 2026-08-19 a petición del usuario: con cinco partidos un rival
# que alterna dos planteamientos deja tres y dos, y cualquier resumen sale a
# medio camino de los dos. Cuesta una llamada de alineación por partido.
MAX_MATCHES_ANALYSED = 10

# Memoria corta sobre CHPP para esta ficha. Una ficha de rival son ~20
# peticiones a Hattrick (plantilla, calendario, y una alineación y un
# matchdetails por partido visto), y eso son 8 segundos medidos el 2026-08-19.
# El problema no era la primera carga sino los mandos: método de zonas, TSI
# logarítmico, once/plantilla… todos son post-proceso puro sobre los MISMOS
# XML, y cada clic los volvía a pedir enteros.
#
# Un partido terminado no cambia nunca y una plantilla cambia de semana en
# semana, así que repetir la consulta dentro de la misma sesión de trabajo no
# aporta nada. Mismo criterio que `_roster_cache` en league.py.
_CHPP_CACHE_TTL_SECONDS = 300
_MAX_CACHE_ENTRIES = 400
_chpp_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}


class _CachedCHPP:
    """Envuelve al cliente real y no repite una consulta ya hecha hace poco.

    Cachea por (fichero, versión, parámetros), que es exactamente lo que
    identifica una respuesta de CHPP. No guarda errores: si Hattrick falla, la
    siguiente petición lo vuelve a intentar.
    """

    def __init__(self, inner: CHPPClient, user_id: int) -> None:
        self._inner = inner
        self._user_id = user_id

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict[str, Any]:
        # El usuario forma parte de la clave. Sin él, `matchorders` —que
        # devuelve TU alineación enviada y solo la ve su dueño— se serviría
        # desde la caché a cualquiera que pidiera el mismo matchID dentro de
        # los cinco minutos. Con dos managers que se enfrentan, eso es
        # enseñarle al rival tu once antes del partido.
        #
        # El precio es cachear por separado lo que sí es público (la plantilla
        # o los partidos de un rival). Compartir esas respuestas ahorraría
        # llamadas, pero exigiría clasificar fichero por fichero cuál depende
        # del token, y equivocarse una sola vez vuelve a abrir la fuga.
        clave = (self._user_id, file, version, tuple(sorted(params.items())))
        ahora = time.monotonic()
        guardado = _chpp_cache.get(clave)
        if guardado is not None and ahora - guardado[0] < _CHPP_CACHE_TTL_SECONDS:
            return guardado[1]
        datos = await self._inner.fetch(file, version=version, **params)
        if len(_chpp_cache) >= _MAX_CACHE_ENTRIES:
            for vieja in [
                k for k, (t, _) in _chpp_cache.items()
                if ahora - t >= _CHPP_CACHE_TTL_SECONDS
            ]:
                _chpp_cache.pop(vieja, None)
            if len(_chpp_cache) >= _MAX_CACHE_ENTRIES:
                _chpp_cache.clear()
        _chpp_cache[clave] = (ahora, datos)
        return datos

    async def aclose(self) -> None:
        await self._inner.aclose()

# Decisión de producto confirmada con el usuario (HL-2xx): la ficha de rival
# usa una clasificación PROPIA de tipo de partido, distinta de la genérica
# de ht_constants (esa la siguen usando arena/matches tal cual,
# sin tocar). Selección nacional nunca cuenta aquí — se juega con otro
# cuerpo técnico, a veces otro país, y no dice nada de cómo juega el CLUB
# rival.
#
# 2026-08-11, pedido explícito y más reciente: Preparación (pretemporada)
# se excluye siempre, junto con Torneo liga/playoff, Duelo y Escalera — los
# 5 son partidos de mentiras y deben ignorarse en TODA la herramienta, sin
# excepción. Reemplaza la regla anterior ("Preparación sí cuenta como
# amistoso porque es contra una plantilla real") — se deja este comentario
# como historial, no como regla vigente.
_NATIONAL_TEAM_MATCH_TYPES = frozenset({
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE,
    MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES,
    MATCH_TYPE_NATIONAL_TEAM_FRIENDLY,
})
_RIVAL_ALWAYS_EXCLUDED_MATCH_TYPES = frozenset({
    MATCH_TYPE_TOURNAMENT_LEAGUE, MATCH_TYPE_TOURNAMENT_PLAYOFF,
    MATCH_TYPE_DUEL, MATCH_TYPE_LADDER, MATCH_TYPE_PREPARATION,
}) | _NATIONAL_TEAM_MATCH_TYPES
_RIVAL_FRIENDLY_MATCH_TYPES = FRIENDLY_MATCH_TYPES - {MATCH_TYPE_NATIONAL_TEAM_FRIENDLY}

# stafflist.xml versión 1.0/"latest" (FILE_VERSIONS["stafflist"], usada para el
# propio equipo) deniega para un equipo ajeno — verificado en vivo:
# chpperror.xml, ErrorCode 1 "Access to specified parameters or file was
# denied". La versión 1.2, en cambio, SÍ expone al entrenador principal
# (Name, Leadership, TrainerSkillLevel) como dato público para cualquier
# equipo — también verificado en vivo contra un rival real. No confundir
# ambas versiones: son el mismo fichero con reglas de acceso distintas.
RIVAL_STAFFLIST_VERSION = "1.2"
MANAGER_COMPENDIUM_VERSION = "1.5"
# matchlineup.xml SIN versión explícita ya resolvía a esto (verificado en
# vivo 2026-08-09) — se fija aquí para que quede auditable, no implícito.
# Esta es la versión VIEJA: `PositionCode` (1-16, MATCH_POSITION_* en
# ht_constants.py) es la casilla de formación del arranque, la que usa el
# marcaje al hombre de esta página. NO confundir con la versión que pide
# `team_of_the_week.py` (2.1) para "Mejor alineación" — ese usa `RoleID`
# (100+, MATCH_ROLE_*), un campo con esquema distinto que en esta versión
# vieja es solo un índice secuencial sin significado. Ver docstring de
# `parse_matchlineup` en app/infrastructure/chpp/parsers/__init__.py.
MATCHLINEUP_POSITION_CODE_VERSION = "1.2"


def _days_since_last_login(payload: dict[str, Any]) -> int | None:
    """Días calendario desde la conexión más reciente del manager.

    Hattrick entrega `FetchedDate` y `LoginTime` en la misma zona horaria, sin
    offset. Comparar sus fechas evita que una conexión de anoche aparezca
    como "hoy" solo porque todavía no han transcurrido 24 horas completas.
    """
    parsed_logins: list[datetime] = []
    for raw in payload.get("last_logins", []):
        try:
            parsed_logins.append(datetime.fromisoformat(raw))
        except (TypeError, ValueError):
            continue
    if not parsed_logins:
        return None

    try:
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
    except (KeyError, TypeError, ValueError):
        return None

    days = (fetched_at.date() - max(parsed_logins).date()).days
    return max(days, 0)


def _type_filter_clause(include_competitive: bool, include_friendlies: bool) -> Any:
    """Cláusula SQL para `Match.match_type` según los dos toggles del
    usuario. Nunca incluye Duelos/Escaleras/Torneo ni Selección nacional:
    no están en ninguna de las dos listas, así que ninguna combinación de
    toggles los alcanza."""
    clauses = []
    if include_competitive:
        clauses.append(
            m.Match.match_type.not_in(
                _RIVAL_FRIENDLY_MATCH_TYPES | _RIVAL_ALWAYS_EXCLUDED_MATCH_TYPES
            )
        )
    if include_friendlies:
        clauses.append(m.Match.match_type.in_(_RIVAL_FRIENDLY_MATCH_TYPES))
    return or_(*clauses) if clauses else m.Match.match_type.in_([])


def _match_type_allowed(
    match_type: int, include_competitive: bool, include_friendlies: bool
) -> bool:
    """Misma regla que `_type_filter_clause`, para filtrar en Python los
    partidos del rival que se piden en vivo (no vienen de una query SQL)."""
    if match_type in _RIVAL_ALWAYS_EXCLUDED_MATCH_TYPES:
        return False
    if match_type in _RIVAL_FRIENDLY_MATCH_TYPES:
        return include_friendlies
    return include_competitive


def _avg(values: Any) -> float | None:
    """Promedio redondeado a 1 decimal, o `None` si no hay ni un valor —
    nunca 0 disfrazado de medida."""
    vals = list(values)
    return round(sum(vals) / len(vals), 1) if vals else None


def _submitted_players(
    match: m.Match | None, players: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resuelve el once enviado contra el roster actual conservando el orden.

    Nueve es el mínimo legal para iniciar. Si faltan más jugadores en el
    roster actual (por venta, migración incompleta o JSON corrupto), se descarta
    la referencia completa en vez de presentar un promedio parcial engañoso.
    """
    if match is None or not match.submitted_lineup_json:
        return []
    try:
        rows = json.loads(match.submitted_lineup_json)
        player_ids = [
            int(row["ht_player_id"])
            for row in rows
            if isinstance(row, dict) and row.get("ht_player_id")
        ]
    except (TypeError, ValueError, KeyError):
        return []
    by_id = {int(player["ht_player_id"]): player for player in players}
    resolved = [by_id[player_id] for player_id in player_ids if player_id in by_id]
    return resolved if 9 <= len(resolved) <= 11 else []


def _submitted_rating_prediction(match: m.Match | None) -> dict[str, int] | None:
    """Los siete ratings CHPP de minuto 0, o nada si falta un solo sector."""
    if match is None:
        return None
    values = {
        "midfield": match.submitted_rating_midfield,
        "right_def": match.submitted_rating_right_def,
        "central_def": match.submitted_rating_central_def,
        "left_def": match.submitted_rating_left_def,
        "right_att": match.submitted_rating_right_att,
        "central_att": match.submitted_rating_central_att,
        "left_att": match.submitted_rating_left_att,
    }
    if any(value is None for value in values.values()):
        return None
    return {key: int(value) for key, value in values.items() if value is not None}


async def _last_purchase(client: Any, ht_team_id: int) -> dict[str, Any] | None:
    """La última compra de un equipo: quién, por cuánto y con qué TSI.

    `transfersteam.xml` responde para CUALQUIER equipo, no solo el propio
    (verificado en vivo el 2026-08-19 contra el 277186): el historial de
    fichajes de un club es público en Hattrick. La primera página basta,
    porque llega de la transferencia más reciente hacia atrás.

    El TSI es el del MOMENTO de la compra, no el de hoy: si el club lo ha
    entrenado desde entonces, ya no vale eso. Se devuelve la fecha justamente
    para que la pantalla pueda decirlo.
    """
    try:
        payload = await client.fetch(
            "transfersteam",
            version=FILE_VERSIONS["transfersteam"],
            teamID=ht_team_id,
            pageIndex=1,
        )
    except Exception:  # noqa: BLE001 — sin este dato la ficha sigue entera
        return None
    compras = [
        t for t in payload.get("transfers", [])
        if t.get("buyer_team_id") == ht_team_id and t.get("deadline")
    ]
    if not compras:
        return None
    ultima = max(compras, key=lambda t: t["deadline"])
    comprado_hace = None
    fecha = ht_to_utc(ultima.get("deadline", ""))
    if fecha is not None:
        comprado_hace = max(0, (datetime.now(UTC) - fecha).days)
    return {
        "player_name": ultima.get("player_name", ""),
        "ht_player_id": ultima.get("ht_player_id"),
        "tsi": ultima.get("tsi", 0),
        "price": ultima.get("price", 0),
        "deadline": ultima.get("deadline", ""),
        # Días desde la compra. La pantalla llena la barra con esto: reciente
        # = llena, una temporada entera = nada que mostrar.
        "days_ago": comprado_hace,
    }


def _with_last_position(
    compra: dict[str, Any] | None, positions: dict[int, int]
) -> dict[str, Any] | None:
    """Le añade a la compra el puesto en el que se ha visto jugar al fichado.

    Sale de las alineaciones ya leídas, así que no cuesta ninguna llamada
    más. `None` si ese jugador no ha aparecido en ninguno de los partidos
    vistos: de un fichaje reciente puede no haber todavía ni un minuto.
    """
    if compra is None:
        return None
    codigo = positions.get(compra.get("ht_player_id") or 0)
    return {
        **compra,
        "last_position": match_position_name(codigo) if codigo else None,
    }


async def _live_rating_prediction(
    client: Any, match: m.Match
) -> dict[str, int] | None:
    """Pide a Hattrick la predicción de minuto 0 de las órdenes ya enviadas.

    `actionType=predictratings` es de solo lectura: Hattrick calcula los siete
    ratings para la alineación que YA está guardada, no envía ni modifica
    nada. Devuelve `None` si todavía no hay órdenes, y también si falla: no
    tener predicción no puede tumbar la ficha del rival.
    """
    sistema = (match.source_system or "hattrick").strip().lower()
    if sistema not in {"hattrick", "youth", "htointegrated"}:
        sistema = "hattrick"
    try:
        payload = await client.fetch(
            "matchorders",
            version=FILE_VERSIONS["matchorders"],
            matchID=match.ht_match_id,
            sourceSystem=sistema,
            actionType="predictratings",
        )
    except Exception:  # noqa: BLE001 — sin predicción, la ficha sigue entera
        return None
    prediccion = payload.get("prediction")
    if not isinstance(prediccion, dict):
        return None
    ratings = prediccion.get("ratings") or {}
    sectores = (
        "midfield", "right_def", "central_def", "left_def",
        "right_att", "central_att", "left_att",
    )
    if any(ratings.get(nombre) is None for nombre in sectores):
        return None
    return {nombre: int(ratings[nombre]) for nombre in sectores}


async def _submitted_match_against(
    session: AsyncSession, own_ht_team_id: int, rival_ht_team_id: int,
) -> m.Match | None:
    """El próximo partido contra ese rival, haya o no órdenes sincronizadas.

    Hasta 2026-08-19 exigía `orders_given=True`, que es un dato del ÚLTIMO
    sync: si mandabas la alineación después de sincronizar, la ficha no se
    enteraba hasta el siguiente sync. La predicción se pide ahora en vivo con
    `actionType=predictratings`, y esa llamada ya responde por sí sola si hay
    órdenes o no.
    """
    return await session.scalar(
        select(m.Match)
        .where(
            or_(
                and_(
                    m.Match.home_team_ht_id == own_ht_team_id,
                    m.Match.away_team_ht_id == rival_ht_team_id,
                ),
                and_(
                    m.Match.away_team_ht_id == own_ht_team_id,
                    m.Match.home_team_ht_id == rival_ht_team_id,
                ),
            ),
            ~m.Match.status.ilike("finished"),
        )
        .order_by(m.Match.played_at.asc())
        .limit(1)
    )


def _most_recent_by_date(
    items: list[dict[str, Any]], date_key: str, limit: int
) -> list[dict[str, Any]]:
    """Los `limit` más recientes según `date_key` (string ISO — el orden
    lexicográfico ya es cronológico), en orden ascendente. Extraído a
    función pura para poder probar la lógica de "más recientes, no más
    antiguos" directamente, sin CHPP ni sesión de por medio."""
    return sorted(items, key=lambda it: it[date_key])[-limit:] if limit > 0 else []


def _pitch_scope_toggles(scope: str, include_competitive: bool, include_friendlies: bool) -> tuple[bool, bool]:
    """El selector local del panel de Duelos por zona (`pitch_zone_scope`)
    puede pedir un recorte de partidos DISTINTO al de los toggles globales
    de la página (Liga/Copa/Promoción, Amistosos) — "mixed" hereda esos
    toggles tal cual, "official"/"friendly" los ignoran."""
    if scope == "official":
        return True, False
    if scope == "friendly":
        return False, True
    return include_competitive, include_friendlies


async def _own_pitch_ratings(
    session: AsyncSession, team: m.Team, include_competitive: bool, include_friendlies: bool,
) -> list[dict[str, int]]:
    """Ratings de sector del propio equipo, de sus últimos MAX_MATCHES_ANALYSED
    partidos de los tipos pedidos — de MatchRating ya sincronizado con el
    sync habitual, sin llamada nueva a CHPP."""
    match_query = (
        select(m.Match)
        .where(
            (m.Match.home_team_ht_id == team.ht_team_id)
            | (m.Match.away_team_ht_id == team.ht_team_id),
            m.Match.status.ilike("finished"),
            _type_filter_clause(include_competitive, include_friendlies),
        )
        .order_by(m.Match.played_at.desc())
        .limit(MAX_MATCHES_ANALYSED)
    )
    matches = list(reversed((await session.execute(match_query)).scalars().all()))
    if not matches:
        return []
    ratings_rows = await session.execute(
        select(m.MatchRating).where(
            m.MatchRating.ht_match_id.in_([mt.ht_match_id for mt in matches])
        )
    )
    ratings_by_side = {(r.ht_match_id, r.is_home): r for r in ratings_rows.scalars()}
    out: list[dict[str, int]] = []
    for mt in matches:
        row = ratings_by_side.get((mt.ht_match_id, mt.home_team_ht_id == team.ht_team_id))
        if row is not None:
            out.append({
                "left_def": row.left_def, "central_def": row.central_def,
                "right_def": row.right_def, "midfield": row.midfield,
                "left_att": row.left_att, "central_att": row.central_att,
                "right_att": row.right_att,
            })
    return out


async def _rival_pitch_ratings(
    client: CHPPClient, rival_ht_team_id: int, matches: list[dict[str, Any]],
) -> list[dict[str, int]]:
    """Ratings de sector del rival para una lista concreta de sus partidos —
    pedidos en vivo, uno por uno (matchdetails.xml no acepta varios matchID
    a la vez)."""
    out: list[dict[str, int]] = []
    for rmt in matches:
        details = await client.fetch(
            "matchdetails", version=FILE_VERSIONS["matchdetails"], matchID=rmt["ht_match_id"],
        )
        for side in ("home", "away"):
            side_data = details.get(side) or {}
            if side_data.get("team_id") != rival_ht_team_id:
                continue
            ratings = side_data.get("ratings", {})
            out.append({
                "left_def": ratings.get("left_def", 0), "central_def": ratings.get("central_def", 0),
                "right_def": ratings.get("right_def", 0), "midfield": ratings.get("midfield", 0),
                "left_att": ratings.get("left_att", 0), "central_att": ratings.get("central_att", 0),
                "right_att": ratings.get("right_att", 0),
            })
    return out


@dataclass
class RivalMatchesAndLineups:
    """Lo que `players.xml` + `matches.xml` + `matchlineup.xml` de un equipo
    ajeno dejan ver — compartido entre la ficha de rival completa
    (`rival_scouting`) y el análisis de próximo partido (`next_match.py`),
    para no duplicar las mismas llamadas a CHPP ni el mismo filtro de tipo
    de partido en dos sitios distintos (antes next_match tenía su propio
    pipeline en vivo, con su propia — y más vieja — regla de qué cuenta como
    "oficial", que todavía dejaba pasar partidos de Selección nacional)."""
    players_raw: list[dict[str, Any]]
    matches_raw: list[dict[str, Any]]      # sin filtrar — para recortes alternativos (ver pitch_zone_scope)
    matches: list[dict[str, Any]]          # elegibles, tope `limit`, orden ascendente
    name: str | None                        # del partido elegible más reciente, o None sin ninguno
    position_by_id: dict[int, int]
    name_by_id: dict[int, str]
    appearances: list[dict[str, Any]]       # una fila por (partido, jugador) de matchlineup


async def fetch_rival_matches_and_lineups(
    client: CHPPClient,
    rival_ht_team_id: int,
    include_competitive: bool,
    include_friendlies: bool,
    limit: int = MAX_MATCHES_ANALYSED,
) -> RivalMatchesAndLineups:
    players_raw = (
        await client.fetch("players", version=FILE_VERSIONS["players"], teamID=rival_ht_team_id)
    )["players"]
    # matches.xml acepta el teamID de cualquier equipo (igual que players.xml),
    # y un partido ya finalizado es un hecho público permanente sin importar
    # quién lo pida.
    matches_raw = (
        await client.fetch("matches", version=FILE_VERSIONS["matches"], teamID=rival_ht_team_id)
    )["matches"]
    eligible = [
        mt for mt in matches_raw
        if mt["status"].upper() == "FINISHED"
        and _match_type_allowed(mt["match_type"], include_competitive, include_friendlies)
    ]
    matches = _most_recent_by_date(eligible, "match_date", limit)

    name: str | None = None
    if matches:
        # `matches` va de más viejo a más nuevo: el nombre se toma del ÚLTIMO.
        # Con el tope en 5 daba igual, pero al ampliarlo a 10 el más viejo de
        # la ventana podía ser un partido contra otro equipo y la ficha
        # acababa titulada con el nombre equivocado.
        ultimo = matches[-1]
        name = (
            ultimo["home_team_name"] if ultimo["home_team_id"] == rival_ht_team_id
            else ultimo["away_team_name"]
        )

    position_by_id: dict[int, int] = {}
    name_by_id: dict[int, str] = {}
    appearances: list[dict[str, Any]] = []
    for mt in matches:
        lineup = (
            await client.fetch(
                "matchlineup", version=MATCHLINEUP_POSITION_CODE_VERSION,
                matchID=mt["ht_match_id"], matchType=mt["match_type"],
                teamID=rival_ht_team_id,
            )
        )["players"]
        # Algunos XML incluyen referencias especiales del mismo jugador
        # (capitán, balón parado) además de su entrada real de titular — cada
        # partido cuenta como máximo una vez por jugador en `appearances`.
        seen_in_match: set[int] = set()
        for p in lineup:
            if p["position_code"] > 0:
                position_by_id[p["ht_player_id"]] = p["position_code"]
            if p["name"]:
                name_by_id[p["ht_player_id"]] = p["name"]
            player_id = p["ht_player_id"]
            if player_id in seen_in_match:
                continue
            seen_in_match.add(player_id)
            appearances.append({"match_id": mt["ht_match_id"], "match_date": mt["match_date"], **p})

    return RivalMatchesAndLineups(
        players_raw=players_raw, matches_raw=matches_raw, matches=matches, name=name,
        position_by_id=position_by_id, name_by_id=name_by_id, appearances=appearances,
    )


@router.get(
    "/teams/{team_id}/rivals/{rival_ht_team_id}/scouting",
    summary="Ficha de rival (HL-099)",
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("rivales", 30)),
    ],
)
async def rival_scouting(
    team_id: int,
    rival_ht_team_id: int,
    log_tsi: bool = False,
    top11: bool = False,
    include_competitive: bool = True,
    include_friendlies: bool = True,
    pitch_zone_scope: str = "mixed",
    # Un método por lado: lo que quieres saber de ti no tiene por qué ser lo
    # mismo que quieres saber del rival. De tu lado, además, existe la
    # alineación ya enviada, que del rival nunca se puede ver.
    pitch_zone_method_own: str = PitchZoneMethod.SUBMITTED,
    pitch_zone_method_rival: str = PitchZoneMethod.AVERAGE,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Todo lo que CHPP permite ver de un rival, en una sola ficha: TSI real
    (comparado con el KDE de tu propia plantilla), nombre+posición reales de
    sus últimos partidos oficiales (contra cualquiera, no solo contra ti),
    sugerencia de marcaje al hombre, táctica/nivel/formación habituales y si
    su ataque rota de lado o siempre pega por el mismo."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    own_players, _ = await roster(session, team_id)
    submitted_match = await _submitted_match_against(
        session, team.ht_team_id, rival_ht_team_id
    )
    submitted_own_players = _submitted_players(submitted_match, own_players)
    submitted_prediction = _submitted_rating_prediction(submitted_match)

    # Mis últimos partidos reales ya sincronizados, de los tipos permitidos
    # — para saber en qué posición jugó cada uno de MIS jugadores
    # recientemente (necesario para elegibilidad de marcaje). HL-2xx: ya no
    # exige que hayan sido contra este rival en particular.
    own_match_query = (
        select(m.Match)
        .where(
            (m.Match.home_team_ht_id == team.ht_team_id)
            | (m.Match.away_team_ht_id == team.ht_team_id),
            m.Match.status.ilike("finished"),
            _type_filter_clause(include_competitive, include_friendlies),
        )
        .order_by(m.Match.played_at.desc())
        .limit(MAX_MATCHES_ANALYSED)
    )
    own_matches = list(reversed((await session.execute(own_match_query)).scalars().all()))

    # Zonas de la cancha del propio equipo — de MatchRating ya sincronizado
    # con el sync habitual, sin llamada nueva a CHPP (a diferencia del
    # rival, que hay que pedirlo en vivo más abajo). El panel de Duelos por
    # zona tiene su PROPIO selector (`pitch_zone_scope`), independiente de
    # los toggles globales de la página — "mixed" (por defecto) los hereda
    # tal cual, sin volver a consultar nada.
    own_sector_ratings = await _own_pitch_ratings(
        session, team, include_competitive, include_friendlies
    )
    pitch_own_include_competitive, pitch_own_include_friendlies = _pitch_scope_toggles(
        pitch_zone_scope, include_competitive, include_friendlies
    )
    historical_pitch_own_sector_ratings = (
        own_sector_ratings if pitch_zone_scope == "mixed"
        else await _own_pitch_ratings(
            session, team, pitch_own_include_competitive, pitch_own_include_friendlies
        )
    )
    # Lo elige el usuario, con la predicción de las órdenes enviadas por
    # defecto cuando existe. Si no existe (todavía no has mandado alineación),
    # ese modo cae al historial en vez de dejar el panel vacío.
    usa_enviada = (
        pitch_zone_method_own == PitchZoneMethod.SUBMITTED and submitted_prediction is not None
    )
    pitch_own_sector_ratings = (
        [submitted_prediction] if usa_enviada else historical_pitch_own_sector_ratings
    )

    client = _CachedCHPP(
        CHPPClient(
            decrypt_token(token_row.oauth_token_enc),
            decrypt_token(token_row.oauth_secret_enc),
        ),
        user_id=user.id,
    )
    # Cada uno de estos hechos también se explica en el panel donde aparece
    # (Comparación de plantilla, TSI, Táctica habitual, Duelos por zona) —
    # esta lista es solo para lo que NO tiene un panel propio donde decirlo.
    caveats = [
        "Nombre y posición del rival solo se conocen para jugadores que aparecieron en uno de "
        "sus últimos partidos oficiales, nunca se trackea su plantilla fuera de eso.",
        "Duelos, Escaleras y partidos de Selección nacional nunca cuentan para esta ficha, sin "
        "importar los toggles de arriba: ni son representativos de cómo juega el club rival "
        "(Duelos/Escaleras) ni reflejan al club en absoluto (Selección: otro cuerpo técnico, a "
        "veces otro país). Los de pretemporada sí cuentan, pero solo bajo el toggle de "
        "Amistosos.",
    ]
    own_position_by_id: dict[int, int] = {}
    rival_position_by_id: dict[int, int] = {}
    rival_name_by_id: dict[int, str] = {}
    rival_tactic_types: list[int] = []
    rival_tactic_skills: list[int] = []
    rival_formations: list[str] = []
    rival_ratings_for_rotation: list[dict[str, Any]] = []
    rival_name: str | None = None
    rival_matches: list[dict[str, Any]] = []
    rival_staff_raw: dict[str, Any] = {}
    own_manager_raw: dict[str, Any] = {}
    rival_manager_raw: dict[str, Any] = {}
    pitch_rival_ratings: list[dict[str, int]] = []
    # Se declaran fuera del try: si CHPP falla a mitad, la respuesta se arma
    # igual y estos quedan en None en vez de reventar por nombre no definido.
    ultima_compra_propia: dict[str, Any] | None = None
    ultima_compra_rival: dict[str, Any] | None = None

    try:
        # La predicción oficial de minuto 0 para las órdenes que estén
        # enviadas AHORA. Se pide antes que nada porque de ella depende que el
        # lado propio pueda ofrecer el modo "alineación enviada".
        if submitted_match is not None and submitted_prediction is None:
            submitted_prediction = await _live_rating_prediction(client, submitted_match)
            usa_enviada = (
                pitch_zone_method_own == PitchZoneMethod.SUBMITTED
                and submitted_prediction is not None
            )
            if usa_enviada:
                pitch_own_sector_ratings = [submitted_prediction]

        # El último fichaje de cada lado: dice a qué nivel está comprando el
        # club, que es una lectura distinta de la plantilla que ya tiene.
        ultima_compra_propia = await _last_purchase(client, team.ht_team_id)
        ultima_compra_rival = await _last_purchase(client, rival_ht_team_id)

        rival_data = await fetch_rival_matches_and_lineups(
            client, rival_ht_team_id, include_competitive, include_friendlies,
        )
        rival_players_raw = rival_data.players_raw
        rival_matches_raw = rival_data.matches_raw
        rival_matches = rival_data.matches
        rival_name = rival_data.name
        rival_position_by_id = rival_data.position_by_id
        rival_name_by_id = rival_data.name_by_id

        rival_staff_raw = await client.fetch(
            "stafflist", version=RIVAL_STAFFLIST_VERSION, teamID=rival_ht_team_id
        )

        # managercompendium.xml se consulta por UserID, no por TeamID. El
        # teamdetails público del rival resuelve ese identificador; el dato de
        # actividad en sí siempre sale de managercompendium, como corresponde.
        rival_team_details = await client.fetch(
            "teamdetails", version=FILE_VERSIONS["teamdetails"], teamID=rival_ht_team_id
        )
        own_manager_raw = await client.fetch(
            "managercompendium", version=MANAGER_COMPENDIUM_VERSION, userID=user.ht_user_id
        )
        rival_manager_user_id = rival_team_details.get("ht_user_id", 0)
        if rival_manager_user_id:
            rival_manager_raw = await client.fetch(
                "managercompendium",
                version=MANAGER_COMPENDIUM_VERSION,
                userID=rival_manager_user_id,
            )

        for mt in own_matches:
            lineup = (
                await client.fetch(
                    "matchlineup", version=MATCHLINEUP_POSITION_CODE_VERSION,
                    matchID=mt.ht_match_id, matchType=mt.match_type,
                    teamID=team.ht_team_id,
                )
            )["players"]
            for p in lineup:
                if p["position_code"] > 0:
                    own_position_by_id[p["ht_player_id"]] = p["position_code"]

        for rmt in rival_matches:
            details = await client.fetch(
                "matchdetails", version=FILE_VERSIONS["matchdetails"],
                matchID=rmt["ht_match_id"],
            )
            for side in ("home", "away"):
                side_data = details.get(side) or {}
                if side_data.get("team_id") != rival_ht_team_id:
                    continue
                rival_tactic_types.append(side_data.get("tactic_type", 0))
                rival_tactic_skills.append(side_data.get("tactic_skill", 0))
                rival_formations.append(side_data.get("formation", ""))
                ratings = side_data.get("ratings", {})
                rival_ratings_for_rotation.append({
                    # Contexto del partido: sin él, la secuencia por carriles
                    # sería una fila de barras sin decir contra quién ni cuándo.
                    "match_date": rmt.get("match_date", ""),
                    "opponent": (
                        rmt["away_team_name"] if rmt["home_team_id"] == rival_ht_team_id
                        else rmt["home_team_name"]
                    ),
                    "left_def": ratings.get("left_def", 0),
                    "central_def": ratings.get("central_def", 0),
                    "right_def": ratings.get("right_def", 0),
                    "midfield": ratings.get("midfield", 0),
                    "left_att": ratings.get("left_att", 0),
                    "central_att": ratings.get("central_att", 0),
                    "right_att": ratings.get("right_att", 0),
                })

        # El selector local del panel de Duelos por zona puede pedir un
        # recorte de partidos del RIVAL distinto al de los toggles globales
        # — en ese caso, y solo en ese caso, se piden en vivo los matchdetails
        # de OTRO conjunto de hasta 5 partidos (matches.xml ya lo trajo todo
        # arriba, no hace falta pedirlo de nuevo). "mixed" reusa lo ya
        # calculado, sin ninguna llamada adicional.
        if pitch_zone_scope == "mixed":
            pitch_rival_ratings = rival_ratings_for_rotation
        else:
            pitch_rival_include_competitive, pitch_rival_include_friendlies = _pitch_scope_toggles(
                pitch_zone_scope, include_competitive, include_friendlies
            )
            pitch_rival_matches_eligible = [
                mt for mt in rival_matches_raw
                if mt["status"].upper() == "FINISHED"
                and _match_type_allowed(
                    mt["match_type"], pitch_rival_include_competitive, pitch_rival_include_friendlies
                )
            ]
            pitch_rival_matches = _most_recent_by_date(
                pitch_rival_matches_eligible, "match_date", MAX_MATCHES_ANALYSED
            )
            pitch_rival_ratings = await _rival_pitch_ratings(
                client, rival_ht_team_id, pitch_rival_matches
            )
    except CHPPAuthError as exc:
        raise HTTPException(401, "Hattrick revocó el acceso: reconecta tu cuenta") from exc
    except CHPPUnavailableError as exc:
        raise HTTPException(503, f"Hattrick no responde: {exc}") from exc
    finally:
        await client.aclose()

    tactic_history = summarise_tactics(rival_tactic_types, rival_tactic_skills, rival_formations)
    rotation = analyse_side_rotation(rival_ratings_for_rotation)
    def metodo_valido(valor: str, por_defecto: str) -> str:
        return valor if valor in set(PitchZoneMethod) else por_defecto

    metodo_propio = metodo_valido(pitch_zone_method_own, PitchZoneMethod.SUBMITTED)
    metodo_rival = metodo_valido(pitch_zone_method_rival, PitchZoneMethod.AVERAGE)
    # Con la alineación enviada solo hay una lectura, así que resumirla es
    # devolverla tal cual: da igual el resumen que se pida.
    own_pitch_zones = pitch_zone_values(
        pitch_own_sector_ratings,
        PitchZoneMethod.LAST if usa_enviada
        else (
            PitchZoneMethod.AVERAGE if metodo_propio == PitchZoneMethod.SUBMITTED
            else metodo_propio
        ),
    )
    rival_pitch_zones = pitch_zone_values(pitch_rival_ratings, metodo_rival)
    pitch_duels = (
        None if own_pitch_zones is None or rival_pitch_zones is None
        else pitch_zone_duels(own_pitch_zones, rival_pitch_zones)
    )
    own_pitch_source = (
        {
            "kind": "submitted_chpp_prediction",
            "label": "CHPP · alineación enviada · minuto 0",
            "match_id": submitted_match.ht_match_id if submitted_match else None,
            "observations": 1,
            "captured_at": (
                submitted_match.submitted_ratings_captured_at if submitted_match else None
            ),
            "tactic_type": submitted_match.submitted_tactic_type if submitted_match else None,
            "tactic_skill": submitted_match.submitted_tactic_skill if submitted_match else None,
        }
        if usa_enviada
        else {
            "kind": "historical_observed",
            "label": "Histórico propio observado",
            "match_id": None,
            "observations": (
                None if own_pitch_zones is None else own_pitch_zones.matches_analysed
            ),
            "captured_at": None,
            "tactic_type": None,
            "tactic_skill": None,
        }
    )
    rival_pitch_source = {
        "kind": "historical_observed",
        "label": "Histórico rival observado",
        "match_id": None,
        "observations": None if rival_pitch_zones is None else rival_pitch_zones.matches_analysed,
        "captured_at": None,
        "tactic_type": None,
        "tactic_skill": None,
    }

    rival_probable_rows = probable_starters(rival_players_raw, rival_data.appearances)
    rival_by_id = {int(player["ht_player_id"]): player for player in rival_players_raw}
    rival_probable_players = [
        rival_by_id[int(row["ht_player_id"])]
        for row in rival_probable_rows
        if int(row["ht_player_id"]) in rival_by_id
    ]
    # Cuando existen órdenes enviadas para ESTE rival, todos los indicadores
    # deportivos comparan ese once real contra el once rival probable. Sin
    # órdenes se conserva el comportamiento anterior de plantilla completa.
    comparison_own_players = submitted_own_players or own_players
    comparison_rival_players = (
        rival_probable_players if submitted_own_players and rival_probable_players
        else rival_players_raw
    )

    own_players_for_tsi = own_players
    rival_players_for_tsi = rival_players_raw
    if top11:
        if submitted_own_players:
            own_players_for_tsi = submitted_own_players
            rival_players_for_tsi = rival_probable_players
        else:
            try:
                best_xi_ids = {
                    a.player["ht_player_id"] for a in best_formation(own_players)[0].assignments
                }
                own_players_for_tsi = [p for p in own_players if p["ht_player_id"] in best_xi_ids]
            except ValueError:
                pass  # plantilla insuficiente para armar un once: se compara la plantilla completa
            # Sin skills del rival no hay "mejor once" real: el TSI más alto es la
            # única aproximación honesta a "sus titulares probables".
            rival_players_for_tsi = sorted(
                rival_players_raw, key=lambda p: -p["tsi"]
            )[:11]

    own_for_tsi = [
        {"tsi": p["tsi"], "position_code": own_position_by_id.get(p["ht_player_id"])}
        for p in own_players_for_tsi
    ]
    rival_for_tsi = [
        {"tsi": p["tsi"], "position_code": rival_position_by_id.get(p["ht_player_id"])}
        for p in rival_players_for_tsi
    ]
    histogram = tsi_kde_comparison(
        own_for_tsi, rival_for_tsi, log_transform=log_tsi
    )

    # HL-144: PROYECCIÓN, no un hecho — siempre sobre los 11 probables de cada
    # lado (independiente del toggle `top11`, que solo afecta al histograma),
    # para no comparar bancas completas de tamaño distinto.
    if submitted_own_players:
        own_best11_tsi = sum(p["tsi"] for p in submitted_own_players)
        rival_best11_tsi = sum(p["tsi"] for p in rival_probable_players)
    else:
        try:
            own_best11_ids = {
                a.player["ht_player_id"] for a in best_formation(own_players)[0].assignments
            }
            own_best11_tsi = sum(
                p["tsi"] for p in own_players if p["ht_player_id"] in own_best11_ids
            )
        except ValueError:
            own_best11_tsi = sum(p["tsi"] for p in own_players)
        rival_best11_tsi = sum(
            p["tsi"] for p in sorted(rival_players_raw, key=lambda p: -p["tsi"])[:11]
        )
    win_probability = estimate_win_probability(own_best11_tsi, rival_best11_tsi)

    own_for_marking = [
        {
            "name": p["name"], "ht_player_id": p["ht_player_id"],
            "position_code": own_position_by_id.get(p["ht_player_id"]),
            "defending": p["skills"]["defending"],
        }
        for p in (submitted_own_players or own_players)
    ]
    rival_for_marking = [
        {
            "name": rival_name_by_id.get(p["ht_player_id"], ""),
            "ht_player_id": p["ht_player_id"],
            "position_code": rival_position_by_id.get(p["ht_player_id"]),
            "tsi": p["tsi"],
        }
        for p in rival_players_raw
        if p["ht_player_id"] in rival_name_by_id
    ]
    marking = suggest_man_marking(own_for_marking, rival_for_marking)

    # Comparación de plantilla — TSI, forma, condición y experiencia son
    # públicas de un rival (verificado en vivo contra players.xml real: solo
    # las 7 skills técnicas vienen en 0). El liderazgo del entrenador rival
    # sale, en orden de preferencia: (1) stafflist.xml versión 1.2, que
    # expone al entrenador principal de CUALQUIER equipo como dato público
    # (Name, Leadership, TrainerSkillLevel) — verificado en vivo, aunque la
    # versión 1.0/"latest" del mismo fichero sí deniega; (2) si por lo que
    # sea eso no trae nada, el jugador-entrenador del rival, si lo tiene:
    # ese jugador trae <TrainerData> dentro del mismo players.xml público, y
    # su Leadership es el del jugador. `player_trainer_skill_level` solo es
    # >0 cuando ese nodo existe (rango real 1–5; 0 es siempre "sin
    # TrainerData"). El detalle de cuál de las dos fuentes se usó va en el
    # Note de ComparisonPanel (frontend), justo donde se ve el número.
    own_trainer_leadership = await session.scalar(
        select(m.StaffSnapshot.trainer_leadership)
        .where(m.StaffSnapshot.team_id == team_id)
        .order_by(m.StaffSnapshot.captured_at.desc())
        .limit(1)
    )
    rival_stafflist_trainer = rival_staff_raw.get("trainer") or {}
    rival_playing_coach = next(
        (p for p in rival_players_raw if p["player_trainer_skill_level"] > 0), None
    )
    rival_trainer_leadership: int | None
    if rival_stafflist_trainer:
        rival_trainer_leadership = rival_stafflist_trainer["leadership"]
    elif rival_playing_coach is not None:
        rival_trainer_leadership = rival_playing_coach["leadership"]
    else:
        rival_trainer_leadership = None
    comparison = {
        "tsi": {
            "own": _avg(p["tsi"] for p in comparison_own_players),
            "rival": _avg(p["tsi"] for p in comparison_rival_players),
        },
        "form": {
            "own": _avg(p["form"] for p in comparison_own_players),
            "rival": _avg(p["form"] for p in comparison_rival_players if p["form_is_read"]),
        },
        "stamina": {
            "own": _avg(p["stamina"] for p in comparison_own_players),
            "rival": _avg(
                p["stamina"] for p in comparison_rival_players if p["stamina_is_read"]
            ),
        },
        "experience": {
            "own": _avg(p["experience"] for p in comparison_own_players),
            "rival": _avg(
                p["experience"]
                for p in comparison_rival_players if p["experience_is_read"]
            ),
        },
        "trainer_leadership": {
            "own": own_trainer_leadership,
            "rival": rival_trainer_leadership,
        },
        "last_login_days": {
            "own": _days_since_last_login(own_manager_raw),
            "rival": _days_since_last_login(rival_manager_raw),
        },
    }

    if not rival_matches:
        caveats.append(
            "Este rival no tiene partidos oficiales recientes de los tipos seleccionados: solo "
            "se puede comparar TSI, sin nombres, posiciones, marcaje, táctica ni rotación."
        )
    if top11:
        if submitted_own_players:
            caveats.append(
                "«Los 11» usa tu alineación realmente enviada contra el once probable del "
                "rival, inferido por recurrencia y recencia en sus partidos públicos."
            )
        else:
            caveats.append(
                "«Los 11 mejores» es tu once real (motor de posiciones) contra los 11 de mayor "
                "TSI del rival, sin sus skills, el TSI es la única aproximación honesta a sus "
                "titulares probables."
            )
    if not (include_competitive and include_friendlies):
        excluded = []
        if not include_competitive:
            excluded.append("Liga/Copa/Promoción")
        if not include_friendlies:
            excluded.append("Amistosos")
        caveats.append(
            f"{' y '.join(excluded)} desactivado(s): actívalo(s) arriba si quieres incluirlo(s) "
            "en el análisis."
        )

    return cast(dict[str, Any], _camel({
        "rival_ht_team_id": rival_ht_team_id,
        "rival_name": rival_name,
        "matches_analysed": len(rival_matches),
        # Cuántos de cada competición entran en ese número: "5 partidos" no
        # dice lo mismo si son cinco de liga que si son tres de liga y dos
        # amistosos, y de eso depende cuánto te fías del resumen.
        "matches_by_competition": [
            {"label": etiqueta, "count": cuantos}
            for etiqueta, cuantos in sorted(
                Counter(
                    match_type_name(mt["match_type"]) for mt in rival_matches
                ).items(),
                key=lambda par: (-par[1], par[0]),
            )
        ],
        "comparison": comparison,
        "last_purchase": {
            "own": _with_last_position(ultima_compra_propia, own_position_by_id),
            "rival": _with_last_position(ultima_compra_rival, rival_position_by_id),
        },
        "comparison_reference": {
            "own_source": (
                "submitted_orders" if submitted_own_players else "full_roster"
            ),
            "own_label": (
                f"Alineación enviada · partido {submitted_match.ht_match_id}"
                if submitted_own_players and submitted_match else "Plantilla actual"
            ),
            "own_players": len(comparison_own_players),
            "rival_source": (
                "probable_recent_starters" if submitted_own_players else "full_roster"
            ),
            "rival_label": (
                "Once probable · recurrencia reciente"
                if submitted_own_players else "Plantilla pública actual"
            ),
            "rival_players": len(comparison_rival_players),
        },
        "tsi_histogram": {
            "grid": histogram.grid,
            "own_density": histogram.own_density,
            "rival_density": histogram.rival_density,
            "own_values": histogram.own_values,
            "rival_values": histogram.rival_values,
            "log_transform": histogram.log_transform,
            "top11": top11,
        },
        "man_marking": None if marking is None else {
            "target_name": marking.target_name,
            "target_position": marking.target_position,
            "target_tsi": marking.target_tsi,
            "marker_name": marking.marker_name,
            "marker_position": marking.marker_position,
            "confidence": marking.confidence,
            "rationale": marking.rationale,
            "efficiency": marking.efficiency,
            "marker_loss_pct": marking.marker_loss_pct,
            "risk_note": marking.risk_note,
            "evidence": marking.evidence,
        },
        "win_probability": {
            "own_probability": win_probability.own_probability,
            "own_tsi_total": win_probability.own_tsi_total,
            "rival_tsi_total": win_probability.rival_tsi_total,
            "confidence": win_probability.confidence,
        },
        "side_rotation": None if rotation is None else {
            "attack_left_avg": rotation.attack_left_avg,
            "attack_central_avg": rotation.attack_central_avg,
            "attack_right_avg": rotation.attack_right_avg,
            "attack_left_std": rotation.attack_left_std,
            "attack_central_std": rotation.attack_central_std,
            "attack_right_std": rotation.attack_right_std,
            "strong_side": rotation.strong_side,
            "dominant_pct": rotation.dominant_pct,
            "dominant_side_by_match": rotation.dominant_side_by_match,
            "attack_by_match": [
                {
                    "label": a.label, "date": a.date,
                    "left": a.left, "central": a.central, "right": a.right, "best": a.best,
                }
                for a in rotation.attack_by_match
            ],
            "rotates": rotation.rotates,
            "matches_analysed": rotation.matches_analysed,
        },
        "pitch_zone_duels": None if pitch_duels is None else [
            {
                "zone": d.zone, "half": d.half,
                "own_value": d.own_value, "rival_value": d.rival_value,
                "own_pct": d.own_pct, "rival_pct": d.rival_pct,
            }
            for d in pitch_duels
        ],
        "pitch_zones_matches_analysed": {
            "own": None if own_pitch_zones is None else own_pitch_zones.matches_analysed,
            "rival": None if rival_pitch_zones is None else rival_pitch_zones.matches_analysed,
        },
        "pitch_zone_sources": {
            "own": own_pitch_source,
            "rival": rival_pitch_source,
        },
        "pitch_zone_scope": pitch_zone_scope,
        # Se devuelve el método REALMENTE aplicado: pedir la alineación
        # enviada sin haberla mandado cae al promedio, y la pantalla tiene que
        # marcar el botón que corresponde a lo que se está viendo.
        "pitch_zone_method_own": (
            PitchZoneMethod.SUBMITTED if usa_enviada
            else (
                PitchZoneMethod.AVERAGE if metodo_propio == PitchZoneMethod.SUBMITTED
                else metodo_propio
            )
        ),
        "pitch_zone_method_rival": metodo_rival,
        # Sin órdenes enviadas para el próximo partido, ese modo no se puede
        # ofrecer: la pantalla lo usa para no pintar un botón muerto.
        "submitted_lineup_available": submitted_prediction is not None,
        "tactic_history": None if tactic_history is None else {
            "matches_analysed": tactic_history.matches_analysed,
            "tactics": [
                {"code": t.code, "label": t.label, "count": t.count, "pct": t.pct}
                for t in tactic_history.tactics
            ],
            "most_common_tactic": None if tactic_history.most_common_tactic is None else {
                "code": tactic_history.most_common_tactic.code,
                "label": tactic_history.most_common_tactic.label,
                "count": tactic_history.most_common_tactic.count,
                "pct": tactic_history.most_common_tactic.pct,
            },
            "avg_tactic_skill": tactic_history.avg_tactic_skill,
            "formations": [
                {"formation": f.formation, "count": f.count, "pct": f.pct}
                for f in tactic_history.formations
            ],
            "most_common_formation": (
                None if tactic_history.most_common_formation is None else {
                    "formation": tactic_history.most_common_formation.formation,
                    "count": tactic_history.most_common_formation.count,
                    "pct": tactic_history.most_common_formation.pct,
                }
            ),
        },
        "rival_roster_sample": sorted(
            (
                {
                    "name": name,
                    "position": (
                        None if rival_position_by_id.get(pid) is None
                        else match_position_name(rival_position_by_id[pid])
                    ),
                    "tsi": next(
                        (p["tsi"] for p in rival_players_raw if p["ht_player_id"] == pid), 0
                    ),
                }
                for pid, name in rival_name_by_id.items()
            ),
            key=lambda r: -r["tsi"],
        )[:5],
        "caveats": caveats,
    }))
