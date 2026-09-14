"""Scouting de rivales, HL-099 a HL-110, ampliado en HL-2xx.

Combina lo poco que CHPP deja ver de un equipo ajeno (TSI real vía
`players.xml`, nombre y posición reales vía `matchlineup.xml` de partidos ya
jugados, táctica/nivel/formación/rotación vía `matchdetails.xml`) con los
motores puros de `rival_scouting`. Todo lo del rival se pide en vivo en cada
request, nada se persiste, para no acabar trackeando el estado de una
cuenta que no es la del usuario.

HL-2xx: el análisis del rival (roster, marcaje, táctica, rotación) se basa
en sus ÚLTIMOS PARTIDOS OFICIALES REALES contra CUALQUIER equipo, ya no
exige que hayan sido contra el equipo propio. Antes, un rival con el que
nunca se hubiera jugado (o solo Duelos/Escaleras) no daba ninguna señal
salvo TSI; ahora se usa lo que el rival jugó de verdad, sea contra quien
sea, igual que haría un ojeador real. Duelos, Escaleras y partidos de
Selección nacional NUNCA cuentan para esto, no hay combinación de toggles
que los traiga de vuelta, porque no se consideran representativos de cómo
juega el CLUB rival normalmente (Selección: otro cuerpo técnico, a veces
otro país; decisión de producto confirmada con el usuario). Preparación
(pretemporada) sí puede contar, pero solo bajo el toggle de Amistosos: a
diferencia de Duelos/Escaleras, es contra un rival real con su plantilla
real.
"""

import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_team_owner
from app.api.rate_limit import limite
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.application.commands.partidos_de_rivales import (
    VERSION_ALINEACION,
    alineacion_de,
    guardar_lo_visto,
    partidos_guardados,
    ratings_de,
)
from app.application.commands.sync_team import FILE_VERSIONS
from app.application.queries.alineacion_enviada import (
    once_enviado,
    partido_pendiente_contra,
    prediccion_en_vivo,
    prediccion_guardada,
)
from app.application.queries.prediccion_liga import partidos_de_un_equipo, reparto_de_tacticas
from app.application.queries.weekly import start_of_iso_week
from app.domain.engines.economy_engine import SEASON_WEEKS
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.next_match_analysis import probable_starters
from app.domain.engines.prediccion import (
    CAMPOS,
    TIPOS_CON_SEDE,
    TIPOS_DE_AMISTOSOS,
    TIPOS_DE_COPA,
    TIPOS_OFICIALES,
    corregir_sede,
    factor_de_tactica,
    goles_esperados,
    marcador_mas_probable,
    probabilidades_de_copa,
    probabilidades_del_motor,
)
from app.domain.engines.rival_scouting import (
    PitchZoneMethod,
    analyse_side_rotation,
    estimate_win_probability,
    lecturas_completas,
    pitch_zone_duels,
    pitch_zone_values,
    resumir_ratings,
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
from app.infrastructure.chpp.client import (
    CHPPAuthError,
    CHPPClient,
    CHPPDeniedError,
    CHPPUnavailableError,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.security.tokens import decrypt_token

router = APIRouter()
_log = logging.getLogger(__name__)

# CINCO, 2026-09-09 a petición del usuario, que vio la cuenta de llamadas a
# Hattrick y dijo basta: «limita los llamados a 5 partidos».
#
# Estuvo en 10 desde el 2026-08-19, con un motivo real --un rival que alterna
# dos planteamientos deja tres y dos, y cualquier resumen sale a medio camino
# de los dos--, pero cada partido cuesta UNA alineación y UN detalle, así que
# los diez eran veinte llamadas por ficha. La respuesta a la alternancia no es
# mirar más partidos sino los selectores de resumen: el máximo y el máximo por
# carril enseñan el techo sin necesidad de ampliar la ventana.
MAX_MATCHES_ANALYSED = 5

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
        # El usuario forma parte de la clave. Sin él, `matchorders`, que
        # devuelve TU alineación enviada y solo la ve su dueño, se serviría
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
                k for k, (t, _) in _chpp_cache.items() if ahora - t >= _CHPP_CACHE_TTL_SECONDS
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
# sin tocar). Selección nacional nunca cuenta aquí, se juega con otro
# cuerpo técnico, a veces otro país, y no dice nada de cómo juega el CLUB
# rival.
#
# 2026-08-11, pedido explícito y más reciente: Preparación (pretemporada)
# se excluye siempre, junto con Torneo liga/playoff, Duelo y Escalera, los
# 5 son partidos de mentiras y deben ignorarse en TODA la herramienta, sin
# excepción. Reemplaza la regla anterior ("Preparación sí cuenta como
# amistoso porque es contra una plantilla real"), se deja este comentario
# como historial, no como regla vigente.
_NATIONAL_TEAM_MATCH_TYPES = frozenset(
    {
        MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE,
        MATCH_TYPE_NATIONAL_TEAM_COMPETITIVE_CUP_RULES,
        MATCH_TYPE_NATIONAL_TEAM_FRIENDLY,
    }
)
_RIVAL_ALWAYS_EXCLUDED_MATCH_TYPES = (
    frozenset(
        {
            MATCH_TYPE_TOURNAMENT_LEAGUE,
            MATCH_TYPE_TOURNAMENT_PLAYOFF,
            MATCH_TYPE_DUEL,
            MATCH_TYPE_LADDER,
            MATCH_TYPE_PREPARATION,
        }
    )
    | _NATIONAL_TEAM_MATCH_TYPES
)
_RIVAL_FRIENDLY_MATCH_TYPES = FRIENDLY_MATCH_TYPES - {MATCH_TYPE_NATIONAL_TEAM_FRIENDLY}

# stafflist.xml versión 1.0/"latest" (FILE_VERSIONS["stafflist"], usada para el
# propio equipo) deniega para un equipo ajeno, verificado en vivo:
# chpperror.xml, ErrorCode 1 "Access to specified parameters or file was
# denied". La versión 1.2, en cambio, SÍ expone al entrenador principal
# (Name, Leadership, TrainerSkillLevel) como dato público para cualquier
# equipo, también verificado en vivo contra un rival real. No confundir
# ambas versiones: son el mismo fichero con reglas de acceso distintas.
RIVAL_STAFFLIST_VERSION = "1.2"
MANAGER_COMPENDIUM_VERSION = "1.5"
# La versión del lector de alineaciones vive ahora en el módulo que guarda los
# partidos de los rivales, para que la que se GUARDA y la que se LEE no puedan
# discrepar: un desajuste ahí sería silencioso --posiciones leídas como otra
# cosa, no un error--. El porqué de esa versión concreta, en
# `VERSION_ALINEACION`.
MATCHLINEUP_POSITION_CODE_VERSION = VERSION_ALINEACION


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
    """Promedio redondeado a 1 decimal, o `None` si no hay ni un valor
    nunca 0 disfrazado de medida."""
    vals = list(values)
    return round(sum(vals) / len(vals), 1) if vals else None


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
    except Exception:  # noqa: BLE001, sin este dato la ficha sigue entera
        return None
    compras = [
        t
        for t in payload.get("transfers", [])
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


def _most_recent_by_date(
    items: list[dict[str, Any]], date_key: str, limit: int
) -> list[dict[str, Any]]:
    """Los `limit` más recientes según `date_key` (string ISO, el orden
    lexicográfico ya es cronológico), en orden ascendente. Extraído a
    función pura para poder probar la lógica de "más recientes, no más
    antiguos" directamente, sin CHPP ni sesión de por medio."""
    return sorted(items, key=lambda it: it[date_key])[-limit:] if limit > 0 else []


async def _own_pitch_ratings(
    session: AsyncSession,
    team: m.Team,
    include_competitive: bool,
    include_friendlies: bool,
) -> list[dict[str, int]]:
    """Ratings de sector del propio equipo, de sus últimos MAX_MATCHES_ANALYSED
    partidos de los tipos pedidos, de MatchRating ya sincronizado con el
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
            out.append(
                {
                    "left_def": row.left_def,
                    "central_def": row.central_def,
                    "right_def": row.right_def,
                    "midfield": row.midfield,
                    "left_att": row.left_att,
                    "central_att": row.central_att,
                    "right_att": row.right_att,
                    # Con qué táctica se jugó: la corrección por táctica la
                    # necesita y leerla después costaría otra consulta.
                    "tactic_type": row.tactic_type or 0,
                    # Balon Parado: no lo pintan los Duelos por zona --que son
                    # siete carriles del campo-- pero si lo usa el modelo de
                    # prediccion, que compara nueve. Se lee aqui para no tener
                    # dos caminos distintos hacia los mismos ratings.
                    "sp_def": row.set_pieces_def,
                    "sp_att": row.set_pieces_att,
                    # Dónde se jugó: la corrección de sede del pronóstico.
                    "en_casa": 1.0 if mt.home_team_ht_id == team.ht_team_id else 0.0,
                }
            )
    return out


async def _rival_pitch_ratings(
    client: CHPPClient,
    rival_ht_team_id: int,
    matches: list[dict[str, Any]],
) -> list[dict[str, int]]:
    """Ratings de sector del rival para una lista concreta de sus partidos
    pedidos en vivo, uno por uno (matchdetails.xml no acepta varios matchID
    a la vez)."""
    out: list[dict[str, int]] = []
    for rmt in matches:
        details = await client.fetch(
            "matchdetails",
            version=FILE_VERSIONS["matchdetails"],
            matchID=rmt["ht_match_id"],
        )
        for side in ("home", "away"):
            side_data = details.get(side) or {}
            if side_data.get("team_id") != rival_ht_team_id:
                continue
            ratings = side_data.get("ratings", {})
            out.append(
                {
                    "left_def": ratings.get("left_def", 0),
                    "central_def": ratings.get("central_def", 0),
                    "right_def": ratings.get("right_def", 0),
                    "midfield": ratings.get("midfield", 0),
                    "left_att": ratings.get("left_att", 0),
                    "central_att": ratings.get("central_att", 0),
                    "right_att": ratings.get("right_att", 0),
                    # Sin esto el modelo de prediccion trabajaria con siete de
                    # sus nueve variables y las dos que faltan entrarian
                    # neutras a 0,5, que no es un valor sino no saber.
                    "sp_def": ratings.get("set_pieces_def", 0),
                    "sp_att": ratings.get("set_pieces_att", 0),
                }
            )
    return out


@dataclass
class RivalMatchesAndLineups:
    """Lo que `players.xml` + `matches.xml` + `matchlineup.xml` de un equipo
    ajeno dejan ver, compartido entre la ficha de rival completa
    (`rival_scouting`) y el análisis de próximo partido (`next_match.py`),
    para no duplicar las mismas llamadas a CHPP ni el mismo filtro de tipo
    de partido en dos sitios distintos (antes next_match tenía su propio
    pipeline en vivo, con su propia, y más vieja, regla de qué cuenta como
    "oficial", que todavía dejaba pasar partidos de Selección nacional)."""

    players_raw: list[dict[str, Any]]
    matches_raw: list[dict[str, Any]]  # sin filtrar
    matches: list[dict[str, Any]]  # elegibles, tope `limit`, orden ascendente
    name: str | None  # del partido elegible más reciente, o None sin ninguno
    position_by_id: dict[int, int]
    name_by_id: dict[int, str]
    appearances: list[dict[str, Any]]  # una fila por (partido, jugador) de matchlineup
    #: Qué clases traen algo en la ventana que se miró. La pantalla apaga el
    #: botón de la que viene en `False`: ofrecer un botón que no puede enseñar
    #: nada es prometer una muestra que no existe.
    hay_oficiales: bool = False
    hay_amistosos: bool = False
    #: Las alineaciones pedidas a Hattrick EN ESTA petición, por partido. Las
    #: que salieron de la base no están: ya estaban guardadas. Es la mitad de
    #: lo que la ficha guarda al terminar; la otra mitad es el detalle.
    alineaciones_nuevas: dict[int, list[dict[str, Any]]] | None = None


async def fetch_rival_matches_and_lineups(
    client: CHPPClient,
    rival_ht_team_id: int,
    include_competitive: bool,
    include_friendlies: bool,
    limit: int = MAX_MATCHES_ANALYSED,
    desde: datetime | None = None,
    solo_oficiales: bool = False,
    ya_guardados: dict[int, dict[str, Any]] | None = None,
) -> RivalMatchesAndLineups:
    """Los últimos partidos de un equipo ajeno, con sus alineaciones.

    `solo_oficiales` es para los rivales con los que ya hay un cruce oficial
    pendiente --los de liga y el de copa--: de ésos sólo se miran oficiales,
    porque es lo que se va a jugar contra ellos. De cualquier otro se miran
    los ÚLTIMOS, sean de la competición que sean (2026-09-09, pedido del
    usuario), y son las clases que aparezcan las que deciden qué botones puede
    ofrecer la pantalla.

    `ya_guardados` son las alineaciones que el sync dejó en la base, indexadas
    por `ht_match_id`. Lo que esté ahí no se vuelve a pedir.
    """
    plantilla = await client.fetch(
        "players", version=FILE_VERSIONS["players"], teamID=rival_ht_team_id
    )
    players_raw = plantilla["players"]
    # matches.xml acepta el teamID de cualquier equipo (igual que players.xml),
    # y un partido ya finalizado es un hecho público permanente sin importar
    # quién lo pida.
    matches_raw = (
        await client.fetch("matches", version=FILE_VERSIONS["matches"], teamID=rival_ht_team_id)
    )["matches"]
    # ESTA TEMPORADA Y NO MÁS ATRÁS. 2026-09-09, pedido del usuario: «aclara
    # que es esta temporada, no quiero que busques más allá». Lo de la
    # temporada pasada describe a otro equipo --otra plantilla, otro nivel--
    # y meterlo en el mismo resumen mezcla dos cosas distintas.
    # EL ARCHIVO, además del calendario. El calendario de Hattrick sólo
    # retrocede un mes, y en temporada casi nadie juega amistosos ese mes, así
    # que «sólo Amistosos» salía vacío contra casi cualquiera. El archivo sí
    # retrocede: con él se alcanzan las dieciséis semanas que el usuario pidió
    # el 2026-09-09 («busca al menos 16 semanas atrás un amistoso»).
    #
    # Cuesta UNA llamada más por rival, con caché de media hora compartida. El
    # calendario manda cuando el mismo partido está en los dos: trae el estado
    # y es lo más fresco.
    # EL ARCHIVO SÓLO CUANDO HACE FALTA. Contra un rival oficial el
    # calendario del último mes ya trae de sobra los cinco que se miran, así
    # que la llamada al archivo se ahorra entera.
    archivados: list[dict[str, Any]] = []
    if desde is not None and not solo_oficiales:
        archivados = await partidos_de_un_equipo(
            client,
            FILE_VERSIONS["matchesarchive"],
            rival_ht_team_id,
            desde,
            datetime.now(UTC),
            TIPOS_OFICIALES + TIPOS_DE_AMISTOSOS,
        )
    del_calendario = {mt["ht_match_id"] for mt in matches_raw}
    corte = desde.strftime("%Y-%m-%d %H:%M:%S") if desde is not None else None
    jugados = [
        mt
        for mt in [
            *matches_raw,
            # Del archivo sólo salen partidos ya jugados, así que el estado se
            # da por hecho: la lista de abajo filtra por él.
            *(
                {**mt, "status": "FINISHED"}
                for mt in archivados
                if mt["ht_match_id"] not in del_calendario
            ),
        ]
        if mt["status"].upper() == "FINISHED"
        and (corte is None or mt.get("match_date", "") >= corte)
    ]
    # QUÉ VENTANA SE MIRA. Contra un rival oficial, sus últimos oficiales.
    # Contra cualquier otro, sus últimos a secas: cinco llamadas, no diez, y
    # sin ir a rebuscar en el archivo una clase que a lo mejor no existe.
    if solo_oficiales:
        ventana = [mt for mt in jugados if _match_type_allowed(mt["match_type"], True, False)]
    else:
        ventana = [mt for mt in jugados if _match_type_allowed(mt["match_type"], True, True)]
    ventana = _most_recent_by_date(ventana, "match_date", limit)

    # Y de esa ventana, qué clases traen algo. Se mide sobre la ventana y no
    # sobre todo el historial a propósito: el botón promete lo que se puede
    # enseñar AHORA, no lo que existiría si se pagaran más llamadas.
    hay_oficiales = any(_match_type_allowed(mt["match_type"], True, False) for mt in ventana)
    hay_amistosos = any(_match_type_allowed(mt["match_type"], False, True) for mt in ventana)

    # Lo que se ANALIZA es lo que el selector deje pasar dentro de la ventana.
    matches = [
        mt
        for mt in ventana
        if _match_type_allowed(mt["match_type"], include_competitive, include_friendlies)
    ]

    # EL NOMBRE SALE DE LA PLANTILLA, que se pide siempre y sin filtrar.
    #
    # Antes salía del último partido elegible, y eso ataba la IDENTIDAD del
    # equipo al filtro de tipo de partido: con «sólo amistosos» marcado, un
    # rival que no ha jugado ninguno se quedaba sin nombre, y la pantalla
    # --que usa el nombre para saber si el equipo existe-- respondía «Rival no
    # encontrado. Hattrick no devolvió ningún equipo con ese identificador»
    # sobre un equipo que estaba perfectamente ahí (2026-09-09).
    name: str | None = plantilla.get("team_name") or None
    if name is None and matches:
        # La reserva de siempre, por si la plantilla llegara sin nombre.
        # `matches` va de más viejo a más nuevo: se toma el del ÚLTIMO. Con el
        # tope en 5 daba igual, pero al ampliarlo a 10 el más viejo de la
        # ventana podía ser un partido contra otro equipo y la ficha acababa
        # titulada con el nombre equivocado.
        ultimo = matches[-1]
        name = (
            ultimo["home_team_name"]
            if ultimo["home_team_id"] == rival_ht_team_id
            else ultimo["away_team_name"]
        )

    position_by_id: dict[int, int] = {}
    name_by_id: dict[int, str] = {}
    appearances: list[dict[str, Any]] = []
    # UNA ALINEACIÓN POR PARTIDO ANALIZADO, y sólo si no está ya guardada.
    #
    # Hasta el 2026-09-09 se pedían las diez de la ventana MÁS cinco de la
    # otra clase, se analizaran o no, para que cambiar el toggle saliera
    # gratis. Salía gratis el segundo clic y carísimo el primero: quince
    # alineaciones por ficha, y el usuario lo vio en su cuenta de llamadas.
    guardadas = ya_guardados or {}
    alineaciones_nuevas: dict[int, list[dict[str, Any]]] = {}
    for mt in matches:
        cacheada = guardadas.get(mt["ht_match_id"])
        if cacheada is not None:
            lineup = cacheada["players"]
        else:
            lineup = (
                await client.fetch(
                    "matchlineup",
                    version=MATCHLINEUP_POSITION_CODE_VERSION,
                    matchID=mt["ht_match_id"],
                    matchType=mt["match_type"],
                    teamID=rival_ht_team_id,
                )
            )["players"]
            alineaciones_nuevas[mt["ht_match_id"]] = lineup
        # Algunos XML incluyen referencias especiales del mismo jugador
        # (capitán, balón parado) además de su entrada real de titular, cada
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
        players_raw=players_raw,
        matches_raw=matches_raw,
        matches=matches,
        name=name,
        position_by_id=position_by_id,
        name_by_id=name_by_id,
        appearances=appearances,
        hay_oficiales=hay_oficiales,
        hay_amistosos=hay_amistosos,
        alineaciones_nuevas=alineaciones_nuevas,
    )


#: Los tipos de partido que pueden emparejarte con un rival, oficiales o no.
#: Los amistosos entran desde el 2026-09-08: hasta entonces el cruce sólo se
#: buscaba entre los oficiales, así que un rival de amistoso salía como «no
#: tenéis nada pendiente» y su muestra natural quedaba invisible.
TIPOS_DE_CRUCE = TIPOS_OFICIALES + TIPOS_DE_AMISTOSOS


def _como_se_llama_el_partido(partido: dict[str, Any] | None) -> dict[str, Any] | None:
    """«Equipo A 1 - 0 Equipo B», con la fecha, de un partido del rival.

    Formato pedido por el usuario el 2026-09-09. Se arma aquí y no en la
    pantalla porque los nombres y el marcador ya están en el mismo sitio del
    que sale el partido: mandarlos sueltos obligaría a la pantalla a volver a
    juntarlos, y a equivocarse de lado la primera vez.
    """
    if partido is None:
        return None
    return {
        "home_name": partido.get("home_team_name") or "",
        "away_name": partido.get("away_team_name") or "",
        "home_goals": partido.get("home_goals", -1),
        "away_goals": partido.get("away_goals", -1),
        "played_at": partido.get("match_date") or None,
        "competition": match_type_name(partido["match_type"]),
    }


def _como_se_llama_el_partido_propio(partido: m.Match | None) -> dict[str, Any] | None:
    """Lo mismo, desde una fila de `matches` --los partidos del club--."""
    if partido is None:
        return None
    return {
        "home_name": partido.home_team_name,
        "away_name": partido.away_team_name,
        "home_goals": partido.home_goals,
        "away_goals": partido.away_goals,
        "played_at": partido.played_at.strftime("%Y-%m-%d %H:%M:%S"),
        "competition": match_type_name(partido.match_type),
    }


async def _cruce_pendiente(
    session: AsyncSession, team: m.Team, rival_ht_team_id: int
) -> m.Match | None:
    """El próximo partido sin jugar entre los dos equipos, si lo hay."""
    return await session.scalar(
        select(m.Match)
        .where(
            (
                (m.Match.home_team_ht_id == team.ht_team_id)
                & (m.Match.away_team_ht_id == rival_ht_team_id)
            )
            | (
                (m.Match.home_team_ht_id == rival_ht_team_id)
                & (m.Match.away_team_ht_id == team.ht_team_id)
            ),
            m.Match.match_type.in_(TIPOS_DE_CRUCE),
            ~m.Match.status.ilike("finished"),
        )
        .order_by(m.Match.played_at)
    )


#: Los nueve campos que come el motor, en el orden en que los nombra.
CAMPOS_DEL_MOTOR = CAMPOS


#: Los siete que Hattrick sí prevé para unas órdenes ya enviadas.
ZONAS_DE_CAMPO = tuple(c for c in CAMPOS_DEL_MOTOR if c not in ("sp_def", "sp_att"))

#: Las dos que no prevé: las acciones INDIRECTAS a balón parado. No es «balón
#: parado» a secas --un penalti o un tiro directo no son esto-- sino
#: `RatingIndirectSetPieces`, el peligro que sale de un córner o una falta
#: puesta al área.
INDIRECTAS = ("sp_def", "sp_att")

#: Con qué se rellenan cuando la alineación enviada no las trae. El promedio
#: de lo ya jugado, el mismo resumen que abre en todas las pantallas.
#:
#: Fue la mediana hasta el 2026-09-13. Medido sobre las nueve lecturas de liga
#: del autor, pasar de una al otro cambia la victoria de 20,1 % a 18,2 %, dos
#: puntos. Lo que NO da igual es el rango: moviendo sólo esas dos por sus
#: valores reales observados, la victoria va de 9 % a 27 %. Por eso la
#: pantalla dice que van prestadas: dos novenos del pronóstico son costumbre,
#: no la alineación que se mandó.
METODO_DE_LAS_INDIRECTAS = PitchZoneMethod.AVERAGE


def _ratings_para_el_motor(
    elegidos: list[dict[str, int]],
    historial: list[dict[str, int]],
    metodo: str,
    en_casa: bool | None = None,
) -> tuple[dict[str, float], bool]:
    """Los nueve ratings resumidos, y si las indirectas van prestadas.

    `elegidos` es lo que el usuario mira en el mapa de cancha --el mismo
    resumen, el mismo método-- para que pronóstico y mapa no puedan describir
    partidos distintos.

    UNA LECTURA VIENE ENTERA O NO CUENTA: a la que le falte un rating se
    descarta, no se completa con un cero ni se promedia sobre las que sí lo
    traen. La única excepción es la alineación enviada, que no es una lectura
    de un partido jugado sino la previsión de Hattrick para unas órdenes, y
    Hattrick no prevé las indirectas. Ahí, y sólo ahí, esas dos se toman del
    historial y se avisa.
    """
    completas = lecturas_completas(elegidos, CAMPOS_DEL_MOTOR)
    if completas:
        # Con la sede del partido que viene, si se sabe: ver `corregir_sede`.
        # Sólo el resumen: la alineación enviada de abajo no se corrige.
        valores = resumir_ratings(completas, CAMPOS_DEL_MOTOR, metodo)
        return corregir_sede(valores, completas, en_casa, metodo), False
    solo_zonas = lecturas_completas(elegidos, ZONAS_DE_CAMPO)
    prestables = lecturas_completas(historial, INDIRECTAS)
    if not solo_zonas or not prestables:
        return {}, False
    valores = resumir_ratings(solo_zonas, ZONAS_DE_CAMPO, metodo)
    valores |= resumir_ratings(prestables, INDIRECTAS, METODO_DE_LAS_INDIRECTAS)
    return valores, True


def _prediccion_del_rival(
    mias: dict[str, float],
    suyas: dict[str, float],
    *,
    es_copa: bool,
    hay_cruce: bool,
    indirectas_prestadas: bool,
    metodo_propio: str,
    metodo_rival: str,
    vistos_mios: int,
    vistos_suyos: int,
    factor_mio: float = 1.0,
    factor_suyo: float = 1.0,
) -> dict[str, Any] | None:
    """La predicción del cruce, con los MISMOS ratings que pinta el mapa.

    Ya no busca su propia muestra ni tiene selector propio: desde el
    2026-09-09 come de «Tu fuente» y «Fuente rival», que es lo que el usuario
    está viendo justo encima. Un pronóstico que resumiera los partidos de otra
    manera que el mapa de al lado sería dos respuestas a la misma pregunta.

    Qué partidos entran lo decide el toggle de la esquina (oficiales o
    amistosos); CÓMO se resumen, estos dos selectores.
    """
    if not mias or not suyas:
        return None
    terna = (
        probabilidades_de_copa(mias, suyas, factor_mio, factor_suyo)
        if es_copa
        else probabilidades_del_motor(mias, suyas, factor_mio, factor_suyo)
    )
    goles = (
        goles_esperados(mias, suyas, factor_mio),
        goles_esperados(suyas, mias, factor_suyo),
    )
    marcador = marcador_mas_probable(mias, suyas, factor_mio, factor_suyo)
    return {
        "es_copa": es_copa,
        "hay_cruce": hay_cruce,
        "metodo_propio": metodo_propio,
        "metodo_rival": metodo_rival,
        # Hattrick no prevé las indirectas a balón parado para unas órdenes
        # enviadas, así que van con el promedio de lo ya jugado. Se dice: dos
        # de los nueve duelos son costumbre y no la alineación que mandaste.
        "indirectas_prestadas": indirectas_prestadas,
        "own_probability": round(terna.victoria, 4),
        "draw_probability": None if es_copa else round(terna.empate, 4),
        "rival_probability": round(terna.derrota, 4),
        "expected_own_goals": round(goles[0], 2),
        "expected_rival_goals": round(goles[1], 2),
        "most_likely_score": f"{marcador[0]}-{marcador[1]}",
        "own_matches": vistos_mios,
        "rival_matches": vistos_suyos,
    }


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
    # Excluyentes: uno u otro, nunca los dos ni ninguno. Por defecto abren los
    # oficiales, que es lo que la pantalla enseña al entrar.
    include_competitive: bool = True,
    include_friendlies: bool = False,
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
    submitted_match = await partido_pendiente_contra(session, team.ht_team_id, rival_ht_team_id)
    submitted_own_players = once_enviado(submitted_match, own_players)
    submitted_prediction = prediccion_guardada(submitted_match)

    # Mis últimos partidos reales ya sincronizados, de los tipos permitidos
    # para saber en qué posición jugó cada uno de MIS jugadores
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

    # Zonas de la cancha del propio equipo, de MatchRating ya sincronizado
    # con el sync habitual, sin llamada nueva a CHPP (a diferencia del
    # rival, que hay que pedirlo en vivo más abajo). El panel de Duelos por
    # zona tiene su PROPIO selector (`pitch_zone_scope`), independiente de
    # los toggles globales de la página, "mixed" (por defecto) los hereda
    # tal cual, sin volver a consultar nada.
    # DIECISÉIS SEMANAS HACIA ATRÁS, siempre. 2026-09-09: primero se pidió
    # «esta temporada y no más allá» y a los pocos minutos «busca al menos 16
    # semanas atrás un amistoso». Dieciséis es además lo que dura una
    # temporada, así que la ventana cubre la temporada entera y algo más de la
    # anterior cuando estamos empezando una.
    #
    # OJO: esto es el FILTRO, no la fuente. El calendario que da Hattrick sólo
    # retrocede un mes, así que ampliar el filtro no hace aparecer por sí solo
    # un amistoso de hace tres meses; para eso hace falta el archivo de
    # partidos, que es otra llamada.
    desde_rival = start_of_iso_week(datetime.now(UTC)) - timedelta(weeks=SEASON_WEEKS)

    # QUÉ CLASE DE RIVAL ES ESTE, y se resuelve ANTES de pedir nada porque es
    # lo que decide cuánto se pide (2026-09-09, pedido del usuario).
    #
    #   · Con un cruce OFICIAL pendiente --el de liga del domingo, el de
    #     copa-- sólo se miran sus cinco últimos oficiales. Es lo que se va a
    #     jugar contra él, y sus amistosos describen a un equipo de suplentes
    #     que no va a salir ese día.
    #   · Sin cruce oficial --un rival de amistoso, o un identificador escrito
    #     a mano-- se miran sus cinco últimos, sean de lo que sean. Ir a
    #     rebuscar cinco de cada clase costaba el doble de llamadas para
    #     describir a un equipo del que a lo mejor sólo hay una.
    cruce_pendiente = await _cruce_pendiente(session, team, rival_ht_team_id)
    rival_oficial = cruce_pendiente is not None and cruce_pendiente.match_type in TIPOS_OFICIALES

    # LO QUE EL SYNC YA DEJÓ GUARDADO. Un partido terminado no cambia nunca,
    # así que lo que esté aquí no se vuelve a pedir: ni su alineación ni su
    # detalle. De un contrincante de liga o del de copa, con el sync al día,
    # esta ficha no gasta NINGUNA llamada de partido.
    #
    # De un rival de amistoso no habrá nada, y está bien: se elige a mano
    # entre millones de equipos, así que precargarlo sería adivinar.
    guardados = {
        fila.ht_match_id: fila
        for fila in await partidos_guardados(session, rival_ht_team_id, limite=None)
    }
    alineaciones_guardadas = {
        ht_match_id: {"players": alineacion_de(fila)} for ht_match_id, fila in guardados.items()
    }

    # UNO U OTRO, NUNCA LOS DOS NI NINGUNO. 2026-09-09, pedido del usuario:
    # los dos toggles de la esquina pasan a ser un selector excluyente.
    #
    # Se normaliza aquí y no sólo en la pantalla: el endpoint aceptaba
    # `include_competitive=false&include_friendlies=false` y devolvía una ficha
    # vacía a quien escribiera esa URL a mano. Cualquier combinación que no
    # sea exactamente una cae en oficiales, que es lo que abre por defecto.
    if include_competitive == include_friendlies:
        include_competitive, include_friendlies = True, False

    # Y contra un rival oficial no hay amistosos que enseñar, porque no se
    # piden: pedirlos marcados devolvería una ficha vacía sin explicación.
    if rival_oficial:
        include_competitive, include_friendlies = True, False

    own_sector_ratings = await _own_pitch_ratings(
        session, team, include_competitive, include_friendlies
    )
    # El panel de Duelos por zona ya no tiene recorte propio: mira los mismos
    # partidos que el resto de la ficha. Tenía un `pitch_zone_scope` con su
    # «mixed/official/friendly», y con el selector excluyente de arriba eran
    # dos maneras de elegir lo mismo en la misma pantalla.
    historical_pitch_own_sector_ratings = own_sector_ratings
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
    # (Comparación de plantilla, TSI, Táctica habitual, Duelos por zona)
    # esta lista es solo para lo que NO tiene un panel propio donde decirlo.
    #
    # 2026-08-30, podado con el usuario: eran cinco frases y TRES decían el
    # mismo hecho con otras palabras --que de un rival solo se sabe lo que sus
    # partidos públicos enseñan, y de sus habilidades nada más que el TSI--.
    # Ese hecho se dice UNA vez, aquí arriba, y las otras dos se recortaron a
    # lo que sí añaden. Repetirlo en tres viñetas no lo hacía más cierto: lo
    # hacía más fácil de saltar.
    caveats = [
        "De un rival solo se sabe lo que enseñan sus partidos públicos: nombre y posición "
        "únicamente de quien apareció en uno reciente, y de sus habilidades nada: el TSI es "
        "lo único que Hattrick publica. Su plantilla no se sigue fuera de eso.",
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
            submitted_prediction = await prediccion_en_vivo(client, submitted_match)
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
            client,
            rival_ht_team_id,
            include_competitive,
            include_friendlies,
            desde=desde_rival,
            solo_oficiales=rival_oficial,
            ya_guardados=alineaciones_guardadas,
        )
        rival_players_raw = rival_data.players_raw
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
                    "matchlineup",
                    version=MATCHLINEUP_POSITION_CODE_VERSION,
                    matchID=mt.ht_match_id,
                    matchType=mt.match_type,
                    teamID=team.ht_team_id,
                )
            )["players"]
            for p in lineup:
                if p["position_code"] > 0:
                    own_position_by_id[p["ht_player_id"]] = p["position_code"]

        # Los detalles pedidos EN VIVO, por partido: la otra mitad de lo que
        # se guarda al terminar.
        lados_nuevos: dict[int, dict[str, Any]] = {}
        for rmt in rival_matches:
            # DE LA BASE SI ESTÁ, DE HATTRICK SI NO. La fila guardada trae los
            # nueve ratings, la táctica y la formación del rival en ese
            # partido: exactamente lo que se pedía con `matchdetails`.
            fila = guardados.get(rmt["ht_match_id"])
            de_la_base = ratings_de(fila) if fila is not None else None
            if fila is not None and de_la_base is not None:
                lados: list[dict[str, Any]] = [
                    {
                        "team_id": rival_ht_team_id,
                        "tactic_type": fila.tactic_type,
                        "tactic_skill": fila.tactic_skill,
                        "formation": fila.formation or "",
                        "ratings": {
                            **de_la_base,
                            "set_pieces_def": de_la_base["sp_def"],
                            "set_pieces_att": de_la_base["sp_att"],
                        },
                    }
                ]
            else:
                details = await client.fetch(
                    "matchdetails",
                    version=FILE_VERSIONS["matchdetails"],
                    matchID=rmt["ht_match_id"],
                )
                lados = [details.get("home") or {}, details.get("away") or {}]
                for bloque_del_rival in lados:
                    if bloque_del_rival.get("team_id") == rival_ht_team_id:
                        lados_nuevos[rmt["ht_match_id"]] = bloque_del_rival
            for side_data in lados:
                if side_data.get("team_id") != rival_ht_team_id:
                    continue
                rival_tactic_types.append(side_data.get("tactic_type", 0))
                rival_tactic_skills.append(side_data.get("tactic_skill", 0))
                rival_formations.append(side_data.get("formation", ""))
                ratings = side_data.get("ratings", {})
                rival_ratings_for_rotation.append(
                    {
                        # Contexto del partido: sin él, la secuencia por carriles
                        # sería una fila de barras sin decir contra quién ni cuándo.
                        "match_date": rmt.get("match_date", ""),
                        "opponent": (
                            rmt["away_team_name"]
                            if rmt["home_team_id"] == rival_ht_team_id
                            else rmt["home_team_name"]
                        ),
                        "left_def": ratings.get("left_def", 0),
                        "central_def": ratings.get("central_def", 0),
                        "right_def": ratings.get("right_def", 0),
                        "midfield": ratings.get("midfield", 0),
                        "left_att": ratings.get("left_att", 0),
                        "central_att": ratings.get("central_att", 0),
                        "right_att": ratings.get("right_att", 0),
                        # Las dos que faltaban. Esta lista nació para la
                        # rotación de carriles, que sólo mira los siete de
                        # campo, pero desde el 2026-09-09 es también la que
                        # alimenta los duelos y el pronóstico. Sin ellas la
                        # lectura no llegaba
                        # entera, se descartaba, y NO HABÍA PRONÓSTICO contra
                        # ningún rival. Hattrick las manda en el mismo bloque.
                        "sp_def": ratings.get("set_pieces_def"),
                        "sp_att": ratings.get("set_pieces_att"),
                        # Dónde se jugó: la corrección de sede del pronóstico.
                        "en_casa": 1.0 if rmt["home_team_id"] == rival_ht_team_id else 0.0,
                    }
                )

        # El panel de Duelos por zona mira los MISMOS partidos que el resto
        # de la ficha: su recorte propio se retiró el 2026-09-09. Esta lista
        # ya está calculada arriba, así que no cuesta ninguna llamada.
        pitch_rival_ratings = rival_ratings_for_rotation

    except CHPPAuthError as exc:
        raise HTTPException(401, "Hattrick revocó el acceso: reconecta tu cuenta") from exc
    except CHPPDeniedError as exc:
        # El token vive: sólo esta llamada estaba vedada. Un 401 aquí
        # lo leería el frontend como sesión caducada (2026-09-04).
        raise HTTPException(403, f"Hattrick no permite esta operación: {exc}") from exc
    except CHPPUnavailableError as exc:
        raise HTTPException(503, f"Hattrick no responde: {exc}") from exc
    finally:
        await client.aclose()

    # LO QUE SE ACABA DE PEDIR, SE GUARDA (2026-09-10, pedido del usuario: los
    # partidos de un rival se guardan «a partir del primer llamado y que no se
    # descarguen siempre de nuevo»).
    #
    # El sync sólo precarga a los contrincantes de liga y al de copa. Sin
    # esto, un rival de amistoso, uno traído con su identificador, o una
    # jornada jugada después del último sync se volvían a pedir enteros en
    # cada visita.
    #
    # NUNCA TUMBA LA FICHA. Si no se puede guardar, la visita siguiente lo
    # vuelve a pedir, que es como funcionaba antes: un inconveniente, no un
    # error que enseñar. El commit es seguro aquí porque la sesión no expira
    # sus objetos al confirmar (`expire_on_commit=False`).
    try:
        if await guardar_lo_visto(
            session,
            rival_ht_team_id,
            rival_matches,
            rival_data.alineaciones_nuevas or {},
            lados_nuevos,
        ):
            await session.commit()
    except Exception:  # noqa: BLE001, no guardar es volver a pedir, no un error
        await session.rollback()
        _log.warning("no se pudieron guardar los partidos del rival %s", rival_ht_team_id)

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
        PitchZoneMethod.LAST
        if usa_enviada
        else (
            PitchZoneMethod.AVERAGE if metodo_propio == PitchZoneMethod.SUBMITTED else metodo_propio
        ),
    )
    rival_pitch_zones = pitch_zone_values(pitch_rival_ratings, metodo_rival)
    pitch_duels = (
        None
        if own_pitch_zones is None or rival_pitch_zones is None
        else pitch_zone_duels(own_pitch_zones, rival_pitch_zones)
    )
    own_pitch_source = (
        {
            "kind": "submitted_chpp_prediction",
            "label": "Predicción de Hattrick · alineación enviada · minuto 0",
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
            "observations": (None if own_pitch_zones is None else own_pitch_zones.matches_analysed),
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
        rival_probable_players
        if submitted_own_players and rival_probable_players
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
            rival_players_for_tsi = sorted(rival_players_raw, key=lambda p: -p["tsi"])[:11]

    own_for_tsi = [
        {"tsi": p["tsi"], "position_code": own_position_by_id.get(p["ht_player_id"])}
        for p in own_players_for_tsi
    ]
    rival_for_tsi = [
        {"tsi": p["tsi"], "position_code": rival_position_by_id.get(p["ht_player_id"])}
        for p in rival_players_for_tsi
    ]
    histogram = tsi_kde_comparison(own_for_tsi, rival_for_tsi, log_transform=log_tsi)

    # HL-144: PROYECCIÓN, no un hecho, siempre sobre los 11 probables de cada
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

    # El cruce pendiente, resuelto arriba, solo decide DOS cosas: si es de
    # copa --allí no hay empate-- y si de verdad hay algo pendiente o el
    # pronóstico es hipotético. La muestra ya no sale de aquí: sale de los dos
    # selectores del mapa de cancha, y de qué clase de rival es (2026-09-09).

    # LA SEDE (2026-09-13). La ventaja de campo va dentro de los ratings y un
    # resumen la diluye: ver `corregir_sede`. Sólo con un cruce de liga o de
    # promoción, donde la sede es segura y donde se midió. Sin cruce el
    # partido es hipotético y no tiene sede; en copa las últimas rondas son
    # neutrales, y desde esta ficha no se sabe cuál toca.
    propio_en_casa: bool | None = None
    if cruce_pendiente is not None and cruce_pendiente.match_type in TIPOS_CON_SEDE:
        propio_en_casa = cruce_pendiente.home_team_ht_id == team.ht_team_id
    mias, indirectas_prestadas = _ratings_para_el_motor(
        pitch_own_sector_ratings,
        historical_pitch_own_sector_ratings,
        pitch_zone_method_own,
        en_casa=propio_en_casa,
    )
    suyas, _ = _ratings_para_el_motor(
        pitch_rival_ratings,
        pitch_rival_ratings,
        pitch_zone_method_rival,
        en_casa=None if propio_en_casa is None else not propio_en_casa,
    )
    prediccion = _prediccion_del_rival(
        mias,
        suyas,
        es_copa=cruce_pendiente is not None and cruce_pendiente.match_type in TIPOS_DE_COPA,
        hay_cruce=cruce_pendiente is not None,
        indirectas_prestadas=indirectas_prestadas,
        metodo_propio=pitch_zone_method_own,
        metodo_rival=pitch_zone_method_rival,
        vistos_mios=len(pitch_own_sector_ratings),
        vistos_suyos=len(pitch_rival_ratings),
        # LA TÁCTICA DE CADA LADO (2026-09-12). La tuya no hay que adivinarla
        # si mandaste órdenes: viene con ellas. La del rival se pondera con lo
        # que viene jugando, en vez de apostar por su táctica más frecuente.
        factor_mio=(
            factor_de_tactica(exacta=submitted_match.submitted_tactic_type)
            if usa_enviada
            and submitted_match is not None
            and submitted_match.submitted_tactic_type is not None
            else factor_de_tactica(reparto_de_tacticas(historical_pitch_own_sector_ratings))
        ),
        factor_suyo=factor_de_tactica(dict(Counter(rival_tactic_types))),
    )

    own_for_marking = [
        {
            "name": p["name"],
            "ht_player_id": p["ht_player_id"],
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

    # Comparación de plantilla, TSI, forma, condición y experiencia son
    # públicas de un rival (verificado en vivo contra players.xml real: solo
    # las 7 skills técnicas vienen en 0). El liderazgo del entrenador rival
    # sale, en orden de preferencia: (1) stafflist.xml versión 1.2, que
    # expone al entrenador principal de CUALQUIER equipo como dato público
    # (Name, Leadership, TrainerSkillLevel), verificado en vivo, aunque la
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
            "rival": _avg(p["stamina"] for p in comparison_rival_players if p["stamina_is_read"]),
        },
        "experience": {
            "own": _avg(p["experience"] for p in comparison_own_players),
            "rival": _avg(
                p["experience"] for p in comparison_rival_players if p["experience_is_read"]
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
            "Este rival no tiene partidos recientes de los tipos seleccionados, así que aquí no "
            "hay nombres, posiciones, marcaje, táctica ni rotación: solo la comparación por TSI."
        )
    if top11:
        if submitted_own_players:
            caveats.append(
                "«Los 11» enfrenta tu alineación ya enviada al once probable del rival, "
                "inferido por recurrencia y recencia en sus partidos públicos."
            )
        else:
            caveats.append(
                "«Los 11 mejores» enfrenta tu once real al de los once rivales de mayor TSI, "
                "que es lo más cerca que se puede estar de sus titulares probables."
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

    return cast(
        dict[str, Any],
        _camel(
            {
                "rival_ht_team_id": rival_ht_team_id,
                "rival_name": rival_name,
                "own_team_name": team.name,
                "matches_analysed": len(rival_matches),
                # QUÉ CLASES PUEDE OFRECER ESTA FICHA (2026-09-09, pedido del
                # usuario). La pantalla apaga el botón que viene en `False`:
                # ofrecer un botón que no puede enseñar nada es prometer una
                # muestra que no existe, y quien lo pulsa se queda mirando una
                # ficha vacía sin saber si falla la aplicación.
                #
                # Contra un rival OFICIAL los amistosos vienen siempre en
                # `False`, y no porque no los tenga: es que no se piden. Lo
                # que se va a jugar contra él es oficial, y sus amistosos
                # describen a un equipo de suplentes que no va a salir.
                "clases_disponibles": {
                    "competitive": rival_data.hay_oficiales,
                    "friendly": rival_data.hay_amistosos,
                },
                # EL ÚLTIMO PARTIDO, con nombre y marcador. Lo pide la
                # etiqueta del resumen «Último partido»: enseñar «último
                # partido» sin decir cuál obliga a irse a Hattrick a
                # comprobarlo (2026-09-09, pedido del usuario).
                "ultimo_partido_rival": _como_se_llama_el_partido(
                    rival_matches[-1] if rival_matches else None
                ),
                "ultimo_partido_propio": _como_se_llama_el_partido_propio(
                    own_matches[-1] if own_matches else None
                ),
                # Cuántos de cada competición entran en ese número: "5 partidos" no
                # dice lo mismo si son cinco de liga que si son tres de liga y dos
                # amistosos, y de eso depende cuánto te fías del resumen.
                "matches_by_competition": [
                    {"label": etiqueta, "count": cuantos}
                    for etiqueta, cuantos in sorted(
                        Counter(match_type_name(mt["match_type"]) for mt in rival_matches).items(),
                        key=lambda par: (-par[1], par[0]),
                    )
                ],
                "comparison": comparison,
                "last_purchase": {
                    "own": _with_last_position(ultima_compra_propia, own_position_by_id),
                    "rival": _with_last_position(ultima_compra_rival, rival_position_by_id),
                },
                "comparison_reference": {
                    "own_source": ("submitted_orders" if submitted_own_players else "full_roster"),
                    "own_label": (
                        f"Alineación enviada · partido {submitted_match.ht_match_id}"
                        if submitted_own_players and submitted_match
                        else "Plantilla actual"
                    ),
                    "own_players": len(comparison_own_players),
                    "rival_source": (
                        "probable_recent_starters" if submitted_own_players else "full_roster"
                    ),
                    "rival_label": (
                        "Once probable · recurrencia reciente"
                        if submitted_own_players
                        else "Plantilla pública actual"
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
                "man_marking": None
                if marking is None
                else {
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
                "prediction": prediccion,
                "win_probability": {
                    "own_probability": win_probability.own_probability,
                    "own_tsi_total": win_probability.own_tsi_total,
                    "rival_tsi_total": win_probability.rival_tsi_total,
                    "confidence": win_probability.confidence,
                },
                "side_rotation": None
                if rotation is None
                else {
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
                            "label": a.label,
                            "date": a.date,
                            "left": a.left,
                            "central": a.central,
                            "right": a.right,
                            "best": a.best,
                        }
                        for a in rotation.attack_by_match
                    ],
                    "rotates": rotation.rotates,
                    "matches_analysed": rotation.matches_analysed,
                },
                "pitch_zone_duels": None
                if pitch_duels is None
                else [
                    {
                        "zone": d.zone,
                        "half": d.half,
                        "own_value": d.own_value,
                        "rival_value": d.rival_value,
                        "own_pct": d.own_pct,
                        "rival_pct": d.rival_pct,
                    }
                    for d in pitch_duels
                ],
                "pitch_zones_matches_analysed": {
                    "own": None if own_pitch_zones is None else own_pitch_zones.matches_analysed,
                    "rival": None
                    if rival_pitch_zones is None
                    else rival_pitch_zones.matches_analysed,
                },
                "pitch_zone_sources": {
                    "own": own_pitch_source,
                    "rival": rival_pitch_source,
                },
                # Se devuelve el método REALMENTE aplicado: pedir la alineación
                # enviada sin haberla mandado cae al promedio, y la pantalla tiene que
                # marcar el botón que corresponde a lo que se está viendo.
                "pitch_zone_method_own": (
                    PitchZoneMethod.SUBMITTED
                    if usa_enviada
                    else (
                        PitchZoneMethod.AVERAGE
                        if metodo_propio == PitchZoneMethod.SUBMITTED
                        else metodo_propio
                    )
                ),
                "pitch_zone_method_rival": metodo_rival,
                # Sin órdenes enviadas para el próximo partido, ese modo no se puede
                # ofrecer: la pantalla lo usa para no pintar un botón muerto.
                "submitted_lineup_available": submitted_prediction is not None,
                "tactic_history": None
                if tactic_history is None
                else {
                    "matches_analysed": tactic_history.matches_analysed,
                    "tactics": [
                        {"code": t.code, "label": t.label, "count": t.count, "pct": t.pct}
                        for t in tactic_history.tactics
                    ],
                    "most_common_tactic": None
                    if tactic_history.most_common_tactic is None
                    else {
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
                        None
                        if tactic_history.most_common_formation is None
                        else {
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
                                None
                                if rival_position_by_id.get(pid) is None
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
            }
        ),
    )
