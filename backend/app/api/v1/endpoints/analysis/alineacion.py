"""Alineacion, incluida la de a posteriori.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.analysis.plantilla import roster
from app.domain.engines.lineup_optimizer import (
    FORMATIONS,
    ORDER_VARIANTS,
    TEAM_SPIRIT_ATTITUDE_MULTIPLIER,
    best_formation,
    best_lineup,
    variantes_de_casilla,
)
from app.domain.engines.position_engine import positions as _positions
from app.domain.engines.team_rating_engine import (
    SECTOR_LABELS,
    SECTORS,
    compute_sector_ratings,
)
from app.domain.value_objects.formations import (
    DEFAULT_FORMATION,
    central_defender_options,
    inner_midfielder_options,
    resolve_split,
    slots_for,
)
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

LINEUP_REQUIRED_COUNT = 11

LINEUP_SECTOR_NOTE = (
    "Fórmula exacta de contribución posicional (Manual no Escrito), sobre "
    "habilidades crudas: sin forma ni resistencia. No reemplaza el ranking "
    "de arriba, que sí está contrastado contra datos reales."
)


def _lineup_sector_payload(
    assignments: list[tuple[dict[str, Any], str, str]],
) -> dict[str, Any]:
    """Serializa los sectores igual para un once resuelto y para uno vacío."""
    sector = compute_sector_ratings(assignments)
    return {
        "ratings": [
            {
                "sector": name,
                "label": SECTOR_LABELS[name],
                "value": sector.ratings[name],
                "topContributors": [
                    {
                        "player": contribution.player_name,
                        "position": contribution.position_label,
                        "amount": contribution.amount,
                    }
                    for contribution in sector.top_contributors[name]
                ],
            }
            for name in SECTORS
        ],
        "note": LINEUP_SECTOR_NOTE,
    }


def _lineup_optimization_objective(value: float) -> dict[str, Any]:
    """Objetivo que ya maximiza el húngaro, hecho explícito en el contrato."""
    return {
        "key": "max_total_positional_contribution",
        "label": "Maximizar la suma del índice de aporte posicional",
        "value": value,
    }


@router.get(
    "/teams/{team_id}/lineup",
    summary="Mejor once posible (HL-121)",
    dependencies=[Depends(require_team_owner)],
)
async def lineup(
    team_id: int,
    formation: str | None = Query(None, description="Si se omite, prueba todas las del catálogo"),
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
    orders: str | None = Query(
        None,
        description=(
            "Órdenes individuales fijadas a mano, como «3:central_defender_offensive» "
            "separadas por coma. Las casillas que no se nombren las elige el motor."
        ),
    ),
    exclude: str | None = Query(
        None,
        description=(
            "Identificadores de Hattrick separados por coma que NO entran en el "
            "reparto. Sirve para lesionados, sancionados o para probar el once sin "
            "alguien: el motor resuelve con el resto."
        ),
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """El mejor once, calculado una vez por sync y por combinación de mandos
    (2026-09-14): la plantilla sólo cambia al sincronizar."""
    from app.api.cache_por_sync import por_sync

    return await por_sync(
        session,
        team_id,
        "mejor-once",
        (formation, central_defenders, inner_midfielders, orders, exclude),
        lambda: _lineup_sin_cache(
            team_id, formation, central_defenders, inner_midfielders, orders, exclude, session
        ),
    )


async def _lineup_sin_cache(
    team_id: int,
    formation: str | None = Query(None, description="Si se omite, prueba todas las del catálogo"),
    # El reparto de cada línea: cuántos juegan por dentro. El resto va a las
    # bandas. Solo tiene sentido con una formación concreta; sin ella se usa
    # el reparto por defecto de cada una para poder compararlas.
    central_defenders: int | None = None,
    inner_midfielders: int | None = None,
    orders: str | None = Query(
        None,
        description=(
            "Órdenes individuales fijadas a mano, como «3:central_defender_offensive» "
            "separadas por coma. Las casillas que no se nombren las elige el motor."
        ),
    ),
    exclude: str | None = Query(
        None,
        description=(
            "Identificadores de Hattrick separados por coma que NO entran en el "
            "reparto. Sirve para lesionados, sancionados o para probar el once sin "
            "alguien: el motor resuelve con el resto."
        ),
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    players, _ = await roster(session, team_id)

    if formation and formation not in FORMATIONS:
        raise HTTPException(400, f"formación desconocida: {formation}")

    # Fuera del reparto ANTES de optimizar, no después: quitar a alguien del
    # resultado dejaría su casilla vacía, y lo que se quiere es que el motor
    # vuelva a resolver el once entero sin él.
    fuera: set[int] = set()
    for trozo in (exclude or "").split(","):
        trozo = trozo.strip()
        if not trozo:
            continue
        if not trozo.isdigit():
            raise HTTPException(400, f"jugador excluido mal escrito: «{trozo}»")
        fuera.add(int(trozo))
    if fuera:
        players = [p for p in players if p["ht_player_id"] not in fuera]
    fijadas: dict[int, str] = {}
    for trozo in (orders or "").split(","):
        if not trozo.strip():
            continue
        casilla, _, variante = trozo.partition(":")
        if not variante.strip() or not casilla.strip().isdigit():
            raise HTTPException(400, f"orden mal escrita: «{trozo}» (se espera «casilla:posición»)")
        fijadas[int(casilla)] = variante.strip()

    # ``best_lineup`` descarta las bajas de una semana o más. Contar aquí
    # con exactamente la misma regla evita el viejo caso de 11 fichas pero
    # solo 10 jugadores utilizables, que acababa convertido en un 422. Una
    # plantilla corta (de origen o por una URL con demasiadas exclusiones) es
    # un estado válido para consultar: no hay once que optimizar, pero la API
    # conserva su forma para que la pantalla pueda avisar sin caerse.
    available_count = sum(p.get("injury_level", -1) < 1 for p in players)
    if available_count < LINEUP_REQUIRED_COUNT:
        response_formation = formation or DEFAULT_FORMATION
        centrales, interiores = resolve_split(
            response_formation,
            central_defenders,
            inner_midfielders,
        )
        return {
            "formation": response_formation,
            "centralDefenders": centrales,
            "innerMidfielders": interiores,
            "centralDefenderOptions": central_defender_options(response_formation),
            "innerMidfielderOptions": inner_midfielder_options(response_formation),
            "totalRating": 0.0,
            "manualShare": 0.0,
            "formationRanking": {},
            "lineup": [],
            "bench": [],
            "sectorRatings": _lineup_sector_payload([]),
            "availableCount": available_count,
            "requiredCount": LINEUP_REQUIRED_COUNT,
            "warning": (
                f"Solo hay {available_count} jugadores disponibles y hacen falta "
                f"{LINEUP_REQUIRED_COUNT} para armar una alineación."
            ),
            "optimizationObjective": _lineup_optimization_objective(0.0),
        }
    try:
        if formation:
            lu = best_lineup(
                players,
                formation,
                None,
                central_defenders,
                inner_midfielders,
                orders=fijadas,
            )
            ranking = {formation: lu.total_rating}
        else:
            lu, ranking = best_formation(players)
            # Las órdenes fijadas se refieren a las casillas de la formación
            # que se está viendo. Sin formación elegida esa es la ganadora, así
            # que se aplican sobre ella en una segunda pasada. Si alguna no
            # cabe (porque la ganadora cambió y esa casilla ya es otra cosa),
            # se descarta en silencio en vez de dejar la pantalla en un error:
            # el usuario no pidió ninguna formación concreta.
            if fijadas:
                slots_ganadores = FORMATIONS[lu.formation]
                aplicables = {
                    indice: variante
                    for indice, variante in fijadas.items()
                    if 0 <= indice < len(slots_ganadores)
                    and variante in variantes_de_casilla(slots_ganadores, indice)
                }
                if aplicables:
                    lu = best_lineup(players, lu.formation, None, orders=aplicables)
                    ranking[lu.formation] = lu.total_rating
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    centrales, interiores = resolve_split(lu.formation, central_defenders, inner_midfielders)
    # Las casillas REALES de este once, con su reparto: hacen falta para saber
    # cual de los tres del carril es el del medio, que es el unico que no
    # puede salir «hacia el lateral».
    casillas = slots_for(lu.formation, centrales, interiores)
    return {
        "formation": lu.formation,
        "centralDefenders": centrales,
        "innerMidfielders": interiores,
        # Los repartos legales de ESTA formación, que son los que el selector
        # puede ofrecer.
        "centralDefenderOptions": central_defender_options(lu.formation),
        "innerMidfielderOptions": inner_midfielder_options(lu.formation),
        "totalRating": lu.total_rating,
        "manualShare": round(lu.manual_share, 2),
        "formationRanking": ranking,
        "availableCount": available_count,
        "requiredCount": LINEUP_REQUIRED_COUNT,
        "warning": None,
        "optimizationObjective": _lineup_optimization_objective(lu.total_rating),
        "lineup": [
            {
                "slot": a.slot,
                "position": a.position,
                "label": a.label,
                "player": a.player["name"],
                "htPlayerId": a.player["ht_player_id"],
                "rating": a.rating,
                "confidence": a.confidence,
                # La orden también queda separada de la posición completa:
                # ningún cliente tiene que deducir "Ofensivo" partiendo
                # ``wingback_offensive``.
                "behaviour": a.behaviour,
                "behaviourLabel": a.behaviour_label,
                # La casilla sin la orden, y qué órdenes caben en ella: es lo
                # que necesita la pantalla para dejar fijarla a mano.
                "basePosition": a.base_position,
                "orderPinned": a.order_pinned,
                "orderOptions": [
                    {"position": v, "label": _positions()[v]}
                    for v in (
                        variantes_de_casilla(casillas, a.slot)
                        if 0 <= a.slot < len(casillas)
                        else ORDER_VARIANTS.get(a.base_position, (a.base_position,))
                    )
                ],
            }
            for a in lu.assignments
        ],
        # El banquillo ya no son «los siete de más TSI que sobraron»: son las
        # seis plazas de Hattrick, cada una con quien mejor la juega.
        "bench": [
            {
                "player": b.player["name"],
                "htPlayerId": b.player["ht_player_id"],
                "tsi": b.player["tsi"],
                "slot": b.slot,
                "slotLabel": b.label,
                "rating": b.rating,
            }
            for b in lu.bench
        ],
        # HL-143: segunda opinión sobre el MISMO once que ya eligió el
        # optimizador húngaro, con habilidades crudas. No decide por sí sola.
        "sectorRatings": _lineup_sector_payload(
            [(a.player, a.position, a.label) for a in lu.assignments]
        ),
    }


@router.get(
    "/teams/{team_id}/lineup/hindsight",
    summary="Alineación real del último partido contra la que propone el optimizador",
    dependencies=[Depends(require_team_owner)],
)
async def lineup_hindsight(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Tu alineación enviada contra la que pondría el optimizador.

    2026-08-22, cambiado a pedido del usuario: antes comparaba contra el
    ÚLTIMO PARTIDO JUGADO, y eso no medía nada útil. Un partido de hace dos
    semanas se jugó con otra formación, o con alguien dentro porque necesitaba
    entrenar; compararse contra eso es compararse contra decisiones que ya no
    son las de hoy.

    Ahora mira la alineación que ya enviaste para tu próximo partido --la que
    Hattrick guarda y esta aplicación refresca en cada sincronización mientras
    el partido siga abierto-- y la contrasta con el once de hoy. Si cambias la
    alineación, la comparación cambia contigo.

    LÍMITE que viaja en la respuesta: el optimizador razona por familia (tres
    plazas de defensa central, sin lado), así que compara CONJUNTOS de
    jugadores por línea, no puesto contra puesto.
    """
    from app.domain.value_objects.ht_constants import (
        MATCH_ROLE_CENTRAL_DEFENDER,
        MATCH_ROLE_FORWARD,
        MATCH_ROLE_INNER_MIDFIELDER,
        MATCH_ROLE_KEEPER,
        MATCH_ROLE_NAMES,
        MATCH_ROLE_WINGBACK,
        MATCH_ROLE_WINGER,
    )

    # El partido usa puestos concretos (Defensa Central derecho/medio/izquierdo)
    # y el optimizador razona por FAMILIA (tres plazas de defensa central, sin
    # lado). Comparar puesto contra puesto daba "no usa este puesto" en 10 de
    # 11 casos, comparación inútil. Se agrupa por familia y se contrastan los
    # conjuntos de jugadores, que es la decisión real: a quién pusiste en
    # defensa, no en qué lado exacto.
    # En mayuscula porque es una CONSTANTE, aunque viva dentro de la
    # funcion: no cambia nunca y se lee como tabla.
    FAMILIES: list[tuple[str, str, frozenset[int], str]] = [  # noqa: N806
        ("keeper", "Portería", MATCH_ROLE_KEEPER, "keeper"),
        ("wingback", "Defensas Laterales", MATCH_ROLE_WINGBACK, "wingback"),
        (
            "central_defender",
            "Defensas Centrales",
            MATCH_ROLE_CENTRAL_DEFENDER,
            "central_defender",
        ),
        ("winger", "Extremos", MATCH_ROLE_WINGER, "winger"),
        ("inner_midfield", "Mediocentros", MATCH_ROLE_INNER_MIDFIELDER, "inner_midfield"),
        ("forward", "Delanteros", MATCH_ROLE_FORWARD, "forward"),
    ]

    equipo = await session.get(m.Team, team_id)
    if equipo is None:
        raise HTTPException(404, f"team {team_id} not found")

    # El PRÓXIMO partido para el que ya enviaste alineación. No el último
    # jugado: comparar contra un partido viejo mide decisiones que ya no son
    # las de hoy (otra formación, alguien dentro porque le tocaba entrenar).
    partido = await session.scalar(
        select(m.Match)
        .where(
            (m.Match.home_team_ht_id == equipo.ht_team_id)
            | (m.Match.away_team_ht_id == equipo.ht_team_id),
            m.Match.submitted_lineup_json.is_not(None),
            m.Match.status.ilike("upcoming"),
        )
        .order_by(m.Match.played_at)
        .limit(1)
    )
    if partido is None:
        return {
            "matchId": None,
            "matchLabel": None,
            "playedAt": None,
            "proposedFormation": None,
            "agreementCount": 0,
            "comparableCount": 0,
            "lines": [],
            "notes": [
                "No has enviado alineación para ningún partido próximo. En "
                "cuanto la mandes en Hattrick y sincronices, aquí verás en qué "
                "coincide con la que propone la aplicación."
            ],
        }

    try:
        enviada = json.loads(partido.submitted_lineup_json or "[]")
    except ValueError:
        enviada = []

    rows = []
    if enviada:
        por_id = {
            p.ht_player_id: p
            for p in (
                await session.execute(
                    select(m.Player).where(
                        m.Player.ht_player_id.in_([int(x.get("ht_player_id", 0)) for x in enviada])
                    )
                )
            )
            .scalars()
            .all()
        }
        for puesto in enviada:
            jugador = por_id.get(int(puesto.get("ht_player_id", 0)))
            if jugador is not None:
                rows.append((int(puesto.get("role_id", 0)), jugador))

    # El once que propondría HOY el optimizador, en su mejor formación.
    players, _ = await roster(session, team_id)
    proposed_by_family: dict[str, list[dict[str, Any]]] = {}
    formation: str | None = None
    try:
        lu, _ranking = best_formation(players)
        formation = lu.formation
        for a in lu.assignments:
            for key, _label, _codes, prefix in FAMILIES:
                if a.position.startswith(prefix):
                    proposed_by_family.setdefault(key, []).append(
                        {
                            "player": a.player["name"],
                            "htPlayerId": a.player["ht_player_id"],
                            "rating": round(a.rating, 2),
                        }
                    )
                    break
    except ValueError:
        pass  # plantilla insuficiente: se muestra sólo lo que pasó de verdad

    played_by_family: dict[str, list[dict[str, Any]]] = {}
    for role_id, player in rows:
        for key, _label, codes, _prefix in FAMILIES:
            if role_id in codes:
                played_by_family.setdefault(key, []).append(
                    {
                        "player": f"{player.first_name} {player.last_name}".strip(),
                        "htPlayerId": player.ht_player_id,
                        "positionLabel": MATCH_ROLE_NAMES.get(role_id, f"código {role_id}"),
                        # La alineación aún no se ha jugado: no hay minutos ni
                        # nota que enseñar, y la pantalla los oculta con esto.
                        "playedMinutes": 90,
                        "rating": None,
                    }
                )
                break

    lines: list[dict[str, Any]] = []
    kept = 0
    total_slots = 0
    for key, label, _codes, _prefix in FAMILIES:
        used = played_by_family.get(key, [])
        proposed = proposed_by_family.get(key, [])
        if not used and not proposed:
            continue
        used_ids = {p["htPlayerId"] for p in used}
        proposed_ids = {p["htPlayerId"] for p in proposed}
        agreed_ids = used_ids & proposed_ids
        kept += len(agreed_ids)
        total_slots += len(used)
        lines.append(
            {
                "key": key,
                "label": label,
                "used": [{**p, "alsoProposed": p["htPlayerId"] in proposed_ids} for p in used],
                # Quien el optimizador pondría en esta línea y tú no usaste ahí.
                "proposedInstead": [p for p in proposed if p["htPlayerId"] not in used_ids],
                "usedCount": len(used),
                "agreedCount": len(agreed_ids),
            }
        )

    return {
        "matchId": partido.ht_match_id,
        "matchLabel": f"{partido.home_team_name} vs {partido.away_team_name}",
        "playedAt": partido.played_at.isoformat() if partido.played_at else None,
        "proposedFormation": formation,
        "agreementCount": kept,
        "comparableCount": total_slots,
        "lines": lines,
        "notes": ["Comparado contra la alineación que ya enviaste para este partido."],
    }


@router.get(
    "/teams/{team_id}/lineup/team-spirit",
    summary="Multiplicador de mediocampo por Espíritu de Equipo × Actitud (HL-142)",
    dependencies=[Depends(require_team_owner)],
)
async def team_spirit_multiplier(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Tabla de referencia, no ligada al Espíritu real de este equipo: los
    nombres del Manual no Escrito no coinciden con los niveles que usa CHPP,
    así que no hay forma honesta de marcar "esta es tu fila", se explora."""
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")
    return {
        "rows": [
            {"spirit": name, "pic": pic, "normal": normal, "mots": mots}
            for name, pic, normal, mots in TEAM_SPIRIT_ATTITUDE_MULTIPLIER
        ],
        "note": (
            "Fuente: Manual no Escrito de la comunidad, los nombres de esta tabla no "
            "coinciden con los niveles de Espíritu que reporta Hattrick, así que no se puede "
            "marcar cuál es tu fila actual: es una tabla explorable, no una lectura de tu "
            "equipo."
        ),
    }
