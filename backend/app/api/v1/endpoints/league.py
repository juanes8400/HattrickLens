"""Liga y predicciones. HL-080, HL-083, HL-090, HL-091, HL-094."""

import asyncio
import time
from dataclasses import asdict
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_team_owner
from app.api.rate_limit import limite
from app.api.v1.endpoints.analysis import roster
from app.api.v1.endpoints.arena import _camel
from app.application.commands.sync_team import FILE_VERSIONS, MATCHLINEUP_ROLE_VERSION
from app.application.queries.alineacion_enviada import (
    AlineacionEnviada,
    alineacion_enviada_de,
)
from app.application.queries.league import LEAGUE_MATCH_TYPE, LeagueQueryService
from app.application.queries.prediccion_liga import lecturas_de_la_serie
from app.domain.engines.lineup_optimizer import best_formation
from app.domain.engines.position_engine import best_position
from app.domain.engines.rival_scouting import PitchZoneMethod, tsi_kde_comparison
from app.domain.engines.season_simulator import model_info
from app.domain.engines.team_of_the_week import (
    FORMATIONS,
    MAX_CENTRAL_DEFENDERS,
    MAX_INNER_MIDFIELDERS,
    SLOT_LABELS,
    LineupPlayer,
    best_team,
    line_splits,
    resolve_split,
)
from app.domain.value_objects.ht_constants import match_role_name
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

# 2026-08-05, pedido explícitamente: abrir la Comparativa de liga (o mover
# cualquiera de sus 3 toggles) pedía las plantillas de los 7-8 rivales de la
# serie a CHPP, en secuencia, cada vez, aunque ninguno de los toggles
# (log_tsi, top11) necesite un dato nuevo de Hattrick: son
# post-proceso puro sobre el mismo TSI ya descargado. Cache en memoria (sin
# Redis en desarrollo, mismo patrón que `_pending` en auth_chpp.py) de la
# plantilla propia + rivales, keyed por la jornada realmente sincronizada
# (cambia sola cuando hay clasificación nueva). TTL corto: es "no repitas
# la llamada mientras el usuario juega con los controles", no un caché de
# verdad, datos más viejos que esto se sienten desactualizados.
#
# 2026-09-14: tres horas y atada al último sync. Con cinco minutos, entrar al
# Dashboard un rato después volvía a pedir las siete plantillas a Hattrick.
_ROSTER_CACHE_TTL_SECONDS = 3 * 3600
_roster_cache: dict[tuple[Any, ...], tuple[float, list[Any]]] = {}

# "Última posición en partido oficial" del jugador de mayor TSI de cada
# equipo, pedido explícitamente 2026-08-08. Es una llamada CHPP nueva
# (playerdetails.xml) por equipo, no cubierta por `_roster_cache` (que solo
# trae TSI vía players.xml), TTL más largo porque LastMatch de un jugador
# cambia como mucho una vez por semana, no cada vez que se abre la página.
_LAST_POSITION_CACHE_TTL_SECONDS = 1800
_last_position_cache: dict[int, tuple[float, str | None]] = {}

# Alineaciones reales (matchlineup.xml) por partido, pedido explícitamente
# 2026-08-08 para "Mejor alineación". Un partido ya finalizado es un hecho
# público permanente (nunca cambia), así que el TTL es largo: no hace falta
# volver a pedirlo salvo que el proceso se reinicie.
#
# 2026-09-14: un mes. Una alineación de un partido terminado no cambia jamás,
# y una hora obligaba a pedir otra vez las ocho de la jornada al volver.
_LINEUP_CACHE_TTL_SECONDS = 30 * 24 * 3600
# MATCHLINEUP_ROLE_VERSION vive en sync_team.py (compartida con el
# refresco de "Última semana" en Posiciones), ver su comentario ahí para
# por qué es una versión distinta a MATCHLINEUP_POSITION_CODE_VERSION de
# rivals.py, para el mismo fichero.
_lineup_cache: dict[tuple[int, int], tuple[float, list[dict[str, Any]]]] = {}

# La respuesta entera de Liga ya no tiene caché propia: ver `liga_calculada`.


@router.get(
    "/teams/{team_id}/league",
    summary="Clasificación, calendario y simulación",
    dependencies=[Depends(require_team_owner)],
)
async def league(
    team_id: int,
    runs: int = Query(10_000, ge=1000, le=200_000, description="Simulaciones de Monte Carlo"),
    # UN SOLO MÉTODO PARA LOS OCHO EQUIPOS (2026-09-09, pedido del usuario).
    # Vive en la pestaña de Proyección y mueve todo lo que se proyecta. El
    # próximo partido del Resumen NO lo sigue desde el 2026-09-12: ahí cada
    # lado va con una alineación concreta. Ver `_proximo_con_alineaciones`.
    #
    # Sin «alineación enviada» como método: de siete de los ocho equipos no se
    # pueden ver las órdenes. La tuya sí se usa, pero sólo en ese partido.
    pitch_zone_method: str = PitchZoneMethod.AVERAGE,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """En qué puesto se acaba, como distribución y no como número.

    Dieciséis jornadas son pocas para que el mejor equipo gane siempre, así que
    la respuesta útil es una distribución de posiciones finales. Las fuerzas de
    ataque y defensa se encogen hacia la media de la liga con un peso que
    depende de las jornadas jugadas: el modelo empieza humilde y se vuelve
    específico según llegan los datos, en vez de fabricar certezas en la
    jornada 3.
    """
    metodo = _metodo_de_la_pantalla(pitch_zone_method)
    data = await liga_calculada(session, team_id, runs, metodo)
    if data is None:
        raise HTTPException(404, f"no standings for team {team_id}")
    return cast(dict[str, Any], _camel(asdict(data)))


async def liga_calculada(
    session: AsyncSession,
    team_id: int,
    runs: int,
    metodo: str = PitchZoneMethod.AVERAGE,
) -> Any:
    """La Liga entera, calculada una vez por sync (2026-09-14).

    La usan la pantalla de Liga, el Dashboard y las alertas: con las mismas
    simulaciones y el mismo resumen, las tres reciben el MISMO cálculo en vez
    de rehacerlo cada una.

    El orden es lo que la hace rápida. Antes se preguntaba a Hattrick por las
    lecturas de la serie y por tus órdenes y SÓLO DESPUÉS se miraba la caché,
    así que cada visita pagaba esas llamadas aunque el resultado ya estuviera
    guardado. Ahora las lecturas se guardan por sync, y las órdenes tienen su
    propia memoria de un minuto (`_TTL_ENVIADA`): se pueden cambiar hasta el
    pitido y por eso van en la clave."""
    from app.api.cache_por_sync import por_sync

    lecturas = await por_sync(
        session,
        team_id,
        "lecturas-de-la-serie",
        (),
        lambda: _lecturas_de_la_serie(session, team_id),
    )
    # Sin lecturas el próximo partido cae a la Poisson de la temporada y unas
    # órdenes no servirían de nada: ni se pregunta a Hattrick por ellas.
    enviada = await _alineacion_enviada_propia(session, team_id) if lecturas else None
    return await por_sync(
        session,
        team_id,
        "liga",
        (runs, metodo, repr(enviada)),
        lambda: LeagueQueryService(session).get(
            team_id, runs=runs, lecturas=lecturas, metodo=metodo, enviada=enviada
        ),
    )


#: Los cuatro resúmenes que ofrece Liga. `SUBMITTED` queda fuera a propósito:
#: la alineación enviada sólo existe para el equipo propio, y aquí se
#: describen ocho.
METODOS_DE_LIGA: frozenset[str] = frozenset(
    {
        PitchZoneMethod.AVERAGE,
        PitchZoneMethod.MAX,
        PitchZoneMethod.MAX_PARALLEL,
        PitchZoneMethod.LAST,
    }
)


def _metodo_de_la_pantalla(pedido: str) -> str:
    """Lo pedido si es de los cuatro; el promedio si no.

    No lanza un 422: quien escriba mal la URL a mano prefiere ver la pantalla
    con el resumen de siempre antes que un error, y la respuesta le dice en
    `pitchZoneMethod` cuál acabó usándose. Es también lo que absorbe la mediana
    retirada el 2026-09-13: una URL vieja con "median" sale en promedio.
    """
    return pedido if pedido in METODOS_DE_LIGA else PitchZoneMethod.AVERAGE


#: Cuánto dura la memoria de tus órdenes. Corta a propósito: se pueden cambiar
#: hasta el pitido. Existe porque tocar el selector de Proyección vuelve a pedir
#: la pantalla entera, y sin esto cada clic repetiría la llamada a Hattrick.
#: Guarda también el «no hay órdenes», que es el caso de casi toda la semana y
#: el que más llamadas ahorra.
_TTL_ENVIADA = 60
_memoria_enviada: dict[int, tuple[float, AlineacionEnviada | None]] = {}


async def _alineacion_enviada_propia(
    session: AsyncSession, team_id: int
) -> AlineacionEnviada | None:
    """Tus órdenes para el próximo partido de liga, o nada.

    Busca el partido con el MISMO criterio con el que la consulta elige el
    próximo --liga de la serie, sin marcador, por jornada y fecha-- y aun así
    la consulta compara los `ht_match_id`: si los dos criterios discreparan,
    las órdenes se ignoran en vez de colarse en otro partido.

    NUNCA TUMBA LA PANTALLA: sin partido pendiente, sin sesión o si Hattrick
    no contesta, devuelve `None` y tu lado va con tu último partido.
    """
    team = await session.get(m.Team, team_id)
    if team is None or not team.series_ht_id:
        return None
    proximo = await session.scalar(
        select(m.Match)
        .where(
            m.Match.series_ht_id == team.series_ht_id,
            m.Match.match_type == LEAGUE_MATCH_TYPE,
            or_(
                m.Match.home_team_ht_id == team.ht_team_id,
                m.Match.away_team_ht_id == team.ht_team_id,
            ),
            m.Match.home_goals < 0,
        )
        .order_by(m.Match.match_round, m.Match.played_at)
        .limit(1)
    )
    if proximo is None:
        return None
    guardado = _memoria_enviada.get(proximo.ht_match_id)
    if guardado is not None and time.monotonic() - guardado[0] < _TTL_ENVIADA:
        return guardado[1]
    token = (
        await session.scalar(
            select(m.CHPPToken).where(
                m.CHPPToken.user_id == team.owner_user_id, m.CHPPToken.status == "active"
            )
        )
        if team.owner_user_id is not None
        else None
    )
    if token is None:
        # Sin sesión todavía vale la que ya está sincronizada.
        return await alineacion_enviada_de(None, proximo)
    client = CHPPClient(decrypt_token(token.oauth_token_enc), decrypt_token(token.oauth_secret_enc))
    try:
        enviada = await alineacion_enviada_de(client, proximo)
    finally:
        await client.aclose()
    _memoria_enviada[proximo.ht_match_id] = (time.monotonic(), enviada)
    return enviada


async def _lecturas_de_la_serie(
    session: AsyncSession, team_id: int
) -> dict[int, list[dict[str, float]]]:
    """Los ratings por zona de los ocho equipos de la serie, o nada.

    Vive aquí y no en la consulta porque es aquí donde está el cliente de
    Hattrick, igual que en la ficha de rival.

    NUNCA TUMBA LA PANTALLA. Si no hay sesión con Hattrick, si el permiso se
    cayó o si Hattrick no contesta, se devuelve vacío y Liga enseña lo de
    siempre con la Poisson sola. Quedarse sin la mitad nueva es un
    inconveniente; quedarse sin clasificación por eso sería un fallo.
    """
    team = await session.get(m.Team, team_id)
    if team is None or not team.series_ht_id:
        return {}
    # SÓLO LIGA, y es la regla, no una casualidad de esta consulta: el resumen
    # de un equipo se saca de UNA competición (`TIPOS_POR_COMPETICION` en
    # `prediccion.py`). Mezclar liga y copa describía mal a los dos --un equipo
    # no juega igual en cada una-- y hasta el 2026-09-08 estaba de las dos
    # maneras a la vez, aquí de una y en `promedios()` de la otra. Si algún día
    # se cablea la pantalla de Copa, va con `TIPOS_DE_COPA`, no con esto.
    jugados = list(
        (
            await session.execute(
                select(m.Match).where(
                    m.Match.series_ht_id == team.series_ht_id,
                    m.Match.match_type == LEAGUE_MATCH_TYPE,
                    m.Match.status.ilike("finished"),
                )
            )
        ).scalars()
    )
    if not jugados:
        return {}
    if team.owner_user_id is None:
        return {}
    token = await session.scalar(
        select(m.CHPPToken).where(
            m.CHPPToken.user_id == team.owner_user_id, m.CHPPToken.status == "active"
        )
    )
    if token is None:
        return {}
    client = CHPPClient(decrypt_token(token.oauth_token_enc), decrypt_token(token.oauth_secret_enc))
    try:
        return await lecturas_de_la_serie(
            session,
            client,
            FILE_VERSIONS["matchdetails"],
            team.series_ht_id,
            jugados,
        )
    except (CHPPAuthError, CHPPDeniedError, CHPPUnavailableError):
        return {}
    finally:
        await client.aclose()


@router.get("/league/model", summary="Qué modela la simulación y qué no")
async def league_model() -> dict[str, Any]:
    return model_info()


@router.get(
    "/teams/{team_id}/league/sectores-recientes",
    summary="Medio campo, defensa y ataque de cada equipo de la serie",
    dependencies=[Depends(require_team_owner)],
)
async def league_sectores_recientes(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """La media de los últimos cinco partidos oficiales de cada equipo, para
    la flor del Dashboard (2026-09-13). Sólo lee la base: nada de Hattrick."""
    from app.application.queries.flor_de_fuerza import (
        PARTIDOS,
        sectores_de_la_serie,
        sectores_del_rival_de_copa,
    )

    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    from app.api.cache_por_sync import por_sync

    async def calcular() -> list[Any]:
        # La serie y, detrás, el próximo rival de Copa si sigues en ella
        # (2026-09-15, pedido del usuario).
        filas = await sectores_de_la_serie(session, team)
        copa = await sectores_del_rival_de_copa(session, team, {f.ht_team_id for f in filas})
        return filas + ([copa] if copa is not None else [])

    equipos = await por_sync(session, team_id, "sectores-recientes", (), calcular)
    return {
        "partidosPorEquipo": PARTIDOS,
        "equipos": [
            {
                "htTeamId": e.ht_team_id,
                "nombre": e.nombre,
                "esPropio": e.es_propio,
                "partidos": e.partidos,
                "medio": e.medio,
                "defensa": e.defensa,
                "ataque": e.ataque,
                "esCopa": e.es_copa,
                "copa": e.copa,
            }
            for e in equipos
        ],
    }


@router.get(
    "/teams/{team_id}/league/comparison",
    summary="Comparativa de TSI contra toda la serie",
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("rivales", 30)),
    ],
)
async def league_comparison(
    team_id: int,
    log_tsi: bool = False,
    top11: bool = False,
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
    incluir_copa: bool = False,
) -> dict[str, Any]:
    """La comparativa entera, calculada una vez por sync y por mandos
    (2026-09-14). Abrir la pestaña rehacía los rankings, la última posición
    del mejor de cada equipo y las curvas de densidad aunque nada hubiera
    cambiado.

    `incluir_copa` lo pide sólo la flor del Dashboard (2026-09-15): añade la
    plantilla del próximo rival de Copa en `cupRival`, FUERA del ranking, el
    histograma y tu puesto, que siguen siendo de la serie."""
    from app.api.cache_por_sync import por_sync

    return await por_sync(
        session,
        team_id,
        "comparativa-de-liga",
        (log_tsi, top11, user.id, incluir_copa),
        lambda: _league_comparison_sin_cache(
            team_id, log_tsi, top11, session, user, incluir_copa=incluir_copa
        ),
    )


async def _league_comparison_sin_cache(
    team_id: int,
    log_tsi: bool,
    top11: bool,
    session: AsyncSession,
    user: m.User,
    incluir_copa: bool = False,
) -> dict[str, Any]:
    """No solo el próximo rival: dónde queda tu plantilla frente a TODA la
    serie. Mismo límite que la ficha de un rival, TSI real vía `players.xml`
    de cada equipo, nombres y skills exactas ocultos por CHPP para quien no
    es tuyo, pero agregado a las 7-8 escuadras de la liga en vez de una.
    Nada de esto se guarda en la base de datos: se pide a CHPP la primera
    vez y se cachea en memoria un rato corto (`_ROSTER_CACHE_TTL_SECONDS`)
    para que mover los controles (Log/TSI, excluir portero, top11) no
    vuelva a consultar a los 7-8 clubes, esos tres son post-proceso puro
    sobre el mismo TSI ya descargado."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    own_standing = await session.scalar(
        select(m.Standing)
        .where(m.Standing.team_ht_id == team.ht_team_id)
        .order_by(m.Standing.captured_at.desc(), m.Standing.match_round.desc())
        .limit(1)
    )
    if own_standing is None:
        raise HTTPException(409, "sincroniza la clasificación de tu liga primero")

    series_teams = (
        (
            await session.execute(
                select(m.Standing).where(
                    m.Standing.series_ht_id == own_standing.series_ht_id,
                    m.Standing.season == own_standing.season,
                    m.Standing.match_round == own_standing.match_round,
                )
            )
        )
        .scalars()
        .all()
    )
    rivals = [s for s in series_teams if s.team_ht_id != team.ht_team_id]

    # El próximo rival de Copa, sólo si lo pide la flor. Si es de tu misma
    # serie ya está entre los de arriba y no se pide dos veces.
    copa = None
    if incluir_copa:
        from app.application.queries.flor_de_fuerza import rival_de_copa

        copa = await rival_de_copa(session, team)
        if copa is not None and copa.ht_team_id in {s.team_ht_id for s in series_teams}:
            copa = None

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    # own_players es una consulta local (DB, sin CHPP), barata, se pide
    # fresca siempre. Lo caro son las plantillas rivales: eso sí se cachea.
    own_players, _ = await roster(session, team_id)

    from app.api.cache_por_sync import ultimo_sync_terminado

    cache_key = (
        team_id,
        own_standing.series_ht_id,
        own_standing.season,
        own_standing.match_round,
        await ultimo_sync_terminado(session, team_id),
        copa.ht_team_id if copa is not None else None,
    )
    cached = _roster_cache.get(cache_key)
    now = time.monotonic()
    cup_players: list[dict[str, Any]] | None = None
    if cached is not None and now - cached[0] < _ROSTER_CACHE_TTL_SECONDS:
        league_rosters: list[tuple[str, int, list[dict[str, Any]]]] = cached[1][0]
        cup_players = cached[1][1]
    else:
        client = CHPPClient(
            decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
        )
        try:
            # Las siete a la vez (2026-09-14): de una en una eran siete esperas
            # seguidas a Hattrick, lo más lento de abrir la Comparativa.
            respuestas = await asyncio.gather(
                *(
                    client.fetch("players", version=FILE_VERSIONS["players"], teamID=st.team_ht_id)
                    for st in rivals
                )
            )
            league_rosters = [
                (st.team_name, st.team_ht_id, payload["players"])
                for st, payload in zip(rivals, respuestas, strict=True)
            ]
            if copa is not None:
                # Aparte de los de la serie: si Hattrick no deja ver a este
                # equipo, la flor sigue con la serie y nada más.
                try:
                    cup_players = (
                        await client.fetch(
                            "players", version=FILE_VERSIONS["players"], teamID=copa.ht_team_id
                        )
                    )["players"]
                except (CHPPDeniedError, CHPPUnavailableError):
                    cup_players = None
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
        _roster_cache[cache_key] = (now, (league_rosters, cup_players))

    own_for_metrics = own_players
    if top11:
        try:
            best_xi_ids = {
                a.player["ht_player_id"] for a in best_formation(own_players)[0].assignments
            }
            own_for_metrics = [p for p in own_players if p["ht_player_id"] in best_xi_ids]
        except ValueError:
            pass  # plantilla insuficiente para armar un once: se compara la plantilla completa

    def top_n(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(players, key=lambda p: -p["tsi"])[:11] if top11 else players

    def summarize(
        name: str, ht_id: int, players: list[dict[str, Any]], is_own: bool
    ) -> dict[str, Any]:
        ps = top_n(players)
        total = sum(p["tsi"] for p in ps)
        # Jugador de mayor TSI, forma y resistencia medias, pedido
        # explícitamente 2026-08-08. Forma/resistencia solo promedian
        # jugadores donde CHPP de verdad las mostró (`*_is_read`): para un
        # rival, un dato ausente no es un 0 real, es "no se sabe".
        top_player = max(ps, key=lambda p: p["tsi"]) if ps else None
        # Las marcas `*_is_read` sólo vienen en las plantillas de los rivales.
        # La tuya sale de la base, donde forma y resistencia siempre se leen:
        # sin el valor por defecto tu fila quedaba en «, » (2026-09-13).
        readable_form = [p["form"] for p in ps if p.get("form_is_read", is_own)]
        readable_stamina = [p["stamina"] for p in ps if p.get("stamina_is_read", is_own)]
        # Experiencia, con la misma regla (2026-09-13, para la flor del
        # Dashboard): sólo cuenta quien Hattrick muestra.
        readable_experience = [
            p["experience"]
            for p in ps
            if p.get("experience_is_read", is_own) and p.get("experience") is not None
        ]
        return {
            "teamHtId": ht_id,
            "teamName": name,
            "totalTsi": total,
            "avgTsi": round(total / len(ps), 1) if ps else 0.0,
            "playerCount": len(ps),
            "isOwn": is_own,
            "topPlayerId": top_player["ht_player_id"] if top_player else None,
            "topPlayerName": (
                f"{top_player['first_name']} {top_player['last_name']}".strip()
                if top_player
                else None
            ),
            "topPlayerTsi": top_player["tsi"] if top_player else None,
            "avgForm": round(sum(readable_form) / len(readable_form), 1) if readable_form else None,
            "avgStamina": (
                round(sum(readable_stamina) / len(readable_stamina), 1)
                if readable_stamina
                else None
            ),
            "avgExperience": (
                round(sum(readable_experience) / len(readable_experience), 1)
                if readable_experience
                else None
            ),
        }

    summaries = [summarize(team.name, team.ht_team_id, own_for_metrics, True)]
    summaries += [summarize(name, ht_id, players, False) for name, ht_id, players in league_rosters]
    summaries.sort(key=lambda s: -s["totalTsi"])
    for i, s in enumerate(summaries):
        s["rank"] = i + 1
    own_rank = next(s["rank"] for s in summaries if s["isOwn"])

    # El rival de Copa, con el mismo resumen pero sin puesto en la serie ni
    # «última posición» de su mejor jugador, que la flor no usa.
    cup_rival = None
    if copa is not None and cup_players:
        cup_rival = summarize(copa.nombre, copa.ht_team_id, cup_players, False)
        cup_rival.pop("topPlayerId", None)
        cup_rival["topPlayerLastPosition"] = None
        cup_rival["rank"] = None
        cup_rival["cupName"] = copa.copa

    # "Última posición en partido oficial" del jugador de mayor TSI de cada
    # equipo, una llamada playerdetails.xml aparte, solo para ese jugador
    # (no toda la plantilla). Cliente propio: el de arriba puede no existir
    # si `league_rosters` vino del caché.
    position_client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )

    async def ultima_posicion(pid: int | None) -> str | None:
        if pid is None:
            return None
        cached_pos = _last_position_cache.get(pid)
        now2 = time.monotonic()
        if cached_pos is not None and now2 - cached_pos[0] < _LAST_POSITION_CACHE_TTL_SECONDS:
            return cached_pos[1]
        try:
            # includeMatchInfo=true es obligatorio para que CHPP rellene
            # `LastMatch`, verificado en vivo 2026-08-09: la misma
            # versión (3.2) sin este parámetro nunca lo trae, con
            # cualquier jugador. Sin esto, "Última posición" salía
            # siempre vacía para todos los rivales.
            payload = await position_client.fetch(
                "playerdetails",
                version=FILE_VERSIONS["playerdetails"],
                playerID=pid,
                includeMatchInfo="true",
            )
            last_match = payload.get("last_match")
            pos_name = match_role_name(last_match["position_code"]) if last_match else None
        except (CHPPAuthError, CHPPUnavailableError):
            pos_name = None
        _last_position_cache[pid] = (now2, pos_name)
        return pos_name

    try:
        # Los ocho a la vez (2026-09-14), por lo mismo que las plantillas.
        posiciones = await asyncio.gather(
            *(ultima_posicion(s.pop("topPlayerId")) for s in summaries)
        )
        for s, pos in zip(summaries, posiciones, strict=True):
            s["topPlayerLastPosition"] = pos
    finally:
        await position_client.aclose()

    # Para el propio equipo sabemos si es portero (skills reales); para el
    # resto de la liga no hay forma de saberlo sin adivinar, así que el
    # toggle solo actúa sobre lo que sí se puede verificar.
    own_for_tsi = [
        {
            "tsi": p["tsi"],
            "position_code": 1 if best_position(p).position == "keeper" else 2,
        }
        for p in own_for_metrics
    ]
    league_for_tsi = [
        {"tsi": p["tsi"], "position_code": None}
        for _, _, players in league_rosters
        for p in top_n(players)
    ]
    histogram = tsi_kde_comparison(own_for_tsi, league_for_tsi, log_transform=log_tsi)

    return cast(
        dict[str, Any],
        _camel(
            {
                "series_name": team.series_name or "",
                "teams_in_series": len(summaries),
                "own_rank": own_rank,
                "ranking": summaries,
                "cup_rival": cup_rival,
                "tsi_histogram": {
                    "grid": histogram.grid,
                    "own_density": histogram.own_density,
                    "rival_density": histogram.rival_density,
                    "own_values": histogram.own_values,
                    "rival_values": histogram.rival_values,
                    "log_transform": histogram.log_transform,
                    "top11": top11,
                },
                "caveats": [
                    "El TSI de cada rival es real, pero sus habilidades y su alineación no se "
                    "publican: «excluir nuestro arquero» solo se aplica con certeza a tu "
                    "plantilla, nunca a la de ellos.",
                    "Nada de esto se guarda en la base: se pide a Hattrick y se reutiliza hasta "
                    "la próxima sincronización.",
                ],
            }
        ),
    )


@router.get(
    "/teams/{team_id}/league/team-of-the-week",
    summary="Mejor alineación real de la jornada o de la temporada",
    dependencies=[
        Depends(require_team_owner),
        Depends(limite("rivales", 30)),
    ],
)
async def team_of_the_week(
    team_id: int,
    scope: Literal["week", "season"] = "week",
    formation: str = "4-4-2",
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
    match_round_param: int | None = Query(default=None, alias="round"),
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """La mejor alineación, calculada una vez por sync y por mandos
    (2026-09-14). Ver `_team_of_the_week_sin_cache` para qué calcula."""
    from app.api.cache_por_sync import por_sync

    return await por_sync(
        session,
        team_id,
        "mejor-alineacion-de-la-serie",
        (scope, formation, central_defenders, inner_midfielders, match_round_param, user.id),
        lambda: _team_of_the_week_sin_cache(
            team_id,
            scope,
            formation,
            central_defenders,
            inner_midfielders,
            match_round_param,
            session,
            user,
        ),
    )


async def _team_of_the_week_sin_cache(
    team_id: int,
    scope: Literal["week", "season"] = "week",
    # `str` y no un `Literal` con las formaciones escritas a mano: esa lista
    # se quedó atrás al añadir 5-5-0, 5-2-3 y 2-5-3 al catálogo (2026-08-19) y
    # el selector ofrecía formaciones que la API rechazaba con un 422. La
    # validación buena es contra la tabla, que es la única fuente.
    formation: str = "4-4-2",
    # Los dos repartos de Hattrick Control: cuántos de la línea juegan por
    # dentro. El resto va a las bandas. `None` = el reparto propio de la
    # formación.
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
    match_round_param: int | None = Query(default=None, alias="round"),
    session: AsyncSession = Depends(get_session),
    user: m.User = Depends(get_current_user),
) -> dict[str, Any]:
    """Equipo ideal calculado con el rating REAL de cada titular
    (`matchlineup.xml`, público incluso para un rival: un partido ya
    finalizado es un hecho permanente, no el histórico de una cuenta ajena).
    "week" = una jornada concreta (la que pida `round`, o la última con
    TODOS sus partidos ya jugados si se omite, igual que el selector de
    Jornada de Hattrick Control); "season" = todas las jornadas completas
    sincronizadas hasta hoy, ignora `round`. `formation` solo cambia
    cuántos cupos de defensa/medio/delantero se muestran, no altera qué
    partidos se leen. Nunca se guarda: se recalcula cada vez, con caché en
    memoria por partido (los resultados de un partido terminado no
    cambian)."""
    if formation not in FORMATIONS:
        raise HTTPException(
            422,
            f"formación desconocida: {formation}. Las disponibles son {', '.join(FORMATIONS)}",
        )

    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    if team.owner_user_id != user.id:
        raise HTTPException(403, "este equipo no está conectado a tu sesión")

    own_standing = await session.scalar(
        select(m.Standing)
        .where(m.Standing.team_ht_id == team.ht_team_id)
        .order_by(m.Standing.captured_at.desc(), m.Standing.match_round.desc())
        .limit(1)
    )
    if own_standing is None:
        raise HTTPException(409, "sincroniza la clasificación de tu liga primero")

    teams_in_series = len(
        (
            await session.execute(
                select(m.Standing.team_ht_id).where(
                    m.Standing.series_ht_id == own_standing.series_ht_id,
                    m.Standing.season == own_standing.season,
                    m.Standing.match_round == own_standing.match_round,
                )
            )
        ).all()
    )

    matches = list(
        (
            await session.execute(
                select(m.Match).where(
                    m.Match.match_type == LEAGUE_MATCH_TYPE,
                    m.Match.series_ht_id == own_standing.series_ht_id,
                    m.Match.home_goals >= 0,
                    m.Match.away_goals >= 0,
                )
            )
        ).scalars()
    )

    # Solo cuentan jornadas TERMINADAS (todos sus partidos jugados), igual
    # que `_history_from_matches`: una jornada a medias no es un rango
    # comparable de "mejor alineación".
    by_round: dict[int, list[m.Match]] = {}
    for mt in matches:
        if mt.match_round is not None:
            by_round.setdefault(mt.match_round, []).append(mt)
    complete_rounds = sorted(
        rnd for rnd, mts in by_round.items() if teams_in_series and len(mts) >= teams_in_series // 2
    )

    if scope == "week":
        target_round = (
            match_round_param
            if match_round_param in complete_rounds
            else (complete_rounds[-1] if complete_rounds else None)
        )
        scoped_matches = by_round.get(target_round, []) if target_round is not None else []
        rounds_covered = 1 if target_round is not None else 0
    else:
        target_round = None
        scoped_matches = [mt for rnd in complete_rounds for mt in by_round[rnd]]
        rounds_covered = len(complete_rounds)

    token_row = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.user_id == user.id))
    if token_row is None or token_row.status != "active":
        raise HTTPException(409, "reconecta con Hattrick: no hay un token activo")

    client = CHPPClient(
        decrypt_token(token_row.oauth_token_enc), decrypt_token(token_row.oauth_secret_enc)
    )
    lineup_players: list[LineupPlayer] = []
    lineups_found = 0
    lineups_expected = len(scoped_matches) * 2
    lados = [
        (match, team_ht_id, team_name)
        for match in scoped_matches
        for team_ht_id, team_name in (
            (match.home_team_ht_id, match.home_team_name),
            (match.away_team_ht_id, match.away_team_name),
        )
    ]

    async def alineacion(ht_match_id: int, team_ht_id: int) -> list[dict[str, Any]]:
        cache_key = (ht_match_id, team_ht_id)
        cached_lineup = _lineup_cache.get(cache_key)
        now = time.monotonic()
        if cached_lineup is not None and now - cached_lineup[0] < _LINEUP_CACHE_TTL_SECONDS:
            return cached_lineup[1]
        try:
            # version=2.1 explícito (ver docstring de team_of_the_week.py y
            # del parser): sin esto, RoleID es un índice sin significado y
            # ningún suplente que entrara a mitad de partido tiene posición
            # fiable, confirmado en vivo 2026-08-09.
            payload = await client.fetch(
                "matchlineup",
                version=MATCHLINEUP_ROLE_VERSION,
                matchID=ht_match_id,
                teamID=team_ht_id,
            )
            players_payload = payload.get("players", [])
        except (CHPPAuthError, CHPPUnavailableError):
            # Un fallo no se guarda: la próxima vez se vuelve a pedir.
            return []
        _lineup_cache[cache_key] = (now, players_payload)
        return players_payload

    try:
        # Todas las alineaciones a la vez (2026-09-14): una jornada son ocho,
        # la temporada entera más de cien, y de una en una era esperar cada
        # respuesta de Hattrick antes de pedir la siguiente.
        cargas = await asyncio.gather(*(alineacion(mt.ht_match_id, tid) for mt, tid, _ in lados))
        for (match, team_ht_id, team_name), players_payload in zip(lados, cargas, strict=True):
            if players_payload:
                lineups_found += 1
            # matchlineup.xml repite entradas especiales del mismo titular
            # (capitán, balón parado), siempre DESPUÉS de su fila real en el
            # XML, así que quedarse con la primera aparición por jugador basta
            # (como máximo una fila por partido y jugador).
            seen: set[int] = set()
            for p in players_payload:
                if p["ht_player_id"] in seen:
                    continue
                seen.add(p["ht_player_id"])
                lineup_players.append(
                    LineupPlayer(
                        ht_player_id=p["ht_player_id"],
                        name=p["name"],
                        team_ht_id=team_ht_id,
                        team_name=team_name,
                        role_id=p["role_id"],
                        rating_stars=p["rating_stars"],
                        ht_match_id=match.ht_match_id,
                    )
                )
    finally:
        await client.aclose()

    centrales, interiores = resolve_split(formation, central_defenders, inner_midfielders)
    slots = best_team(
        lineup_players,
        formation=formation,
        central_defenders=centrales,
        inner_midfielders=interiores,
    )
    total_stars = round(sum(p.rating_stars for group in slots.values() for p in group), 1)

    return cast(
        dict[str, Any],
        _camel(
            {
                "scope": scope,
                "formation": formation,
                "formations": list(FORMATIONS.keys()),
                "central_defenders": centrales,
                "inner_midfielders": interiores,
                # Las opciones legales de cada selector para ESTA formación: una línea
                # de cinco solo admite 3 por dentro, y ahí el radio sale único.
                "central_defender_options": line_splits(
                    FORMATIONS[formation][0], MAX_CENTRAL_DEFENDERS
                ),
                "inner_midfielder_options": line_splits(
                    FORMATIONS[formation][1], MAX_INNER_MIDFIELDERS
                ),
                "match_round": target_round,
                "available_rounds": complete_rounds,
                "rounds_covered": rounds_covered,
                "lineups_found": lineups_found,
                "lineups_expected": lineups_expected,
                "slot_labels": SLOT_LABELS,
                "positions": {key: [asdict(p) for p in players] for key, players in slots.items()},
                "total_stars": total_stars,
                "caveats": [
                    "Rating real de cada titular, público para cualquier partido ya terminado "
                    "un mismo jugador solo cuenta con su mejor actuación del rango.",
                    '"De la temporada" pesa cada jornada terminada por igual, sin importar cuándo se '  # noqa: E501
                    "sincronizó el calendario, puede tardar en reflejar la última jornada si "
                    "el calendario todavía no trae su marcador.",
                ],
            }
        ),
    )
