"""Centro de decisión de Copa.

Los hechos (estado, ronda, calendario, asistencia e historial) se mantienen
separados de las proyecciones (probabilidad, taquilla futura y escenarios).
La clasificación usa las dos dimensiones oficiales: CupLeagueLevel distingue
Nacional/Divisional y CupLevel distingue Principal/Desafío/Consuelo.
"""

import json
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.arena import _camel
from app.application.queries.weekly import season_for_datetime
from app.domain.engines.match_analysis import hatstats
from app.domain.engines.rival_scouting import PitchZoneMethod
from app.domain.engines.taquilla import taquilla_de_varios
from app.domain.value_objects.ht_constants import MATCH_TYPE_LEAGUE
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()

CUP_MATCH_TYPE = 3
CHALLENGE_NAMES = {1: "Esmeralda", 2: "Rubí", 3: "Zafiro"}

# Importes canónicos en SEK. El manual los presenta convertidos a la moneda
# del usuario; Team.currency_rate hace la misma conversión que Economía.
# rounds_from_title: 1=Final, 2=Semifinal, 3=Cuartos, etc.
CUP_PRIZES_SEK: dict[str, list[tuple[str, int, int]]] = {
    "national_main": [
        ("Ronda de 512", 1_200_000, 9),
        ("Ronda de 256", 1_400_000, 8),
        ("Ronda de 128", 1_600_000, 7),
        ("Ronda de 64", 1_800_000, 6),
        ("Ronda de 32", 2_000_000, 5),
        ("Octavos", 2_500_000, 4),
        ("Cuartos", 5_000_000, 3),
        ("Semifinal", 7_500_000, 2),
        ("Subcampeón", 10_000_000, 1),
        ("Campeón", 15_000_000, 0),
    ],
    "national_challenge": [
        ("Octavos", 250_000, 4),
        ("Cuartos", 500_000, 3),
        ("Semifinal", 1_000_000, 2),
        ("Subcampeón", 1_500_000, 1),
        ("Campeón", 3_000_000, 0),
    ],
    "divisional_main": [
        ("Octavos", 250_000, 4),
        ("Cuartos", 500_000, 3),
        ("Semifinal", 1_000_000, 2),
        ("Subcampeón", 1_500_000, 1),
        ("Campeón", 3_000_000, 0),
    ],
    "divisional_challenge": [
        ("Cuartos", 250_000, 3),
        ("Semifinal", 500_000, 2),
        ("Subcampeón", 1_000_000, 1),
        ("Campeón", 1_500_000, 0),
    ],
}


def _classification(
    cup_league_level: int | None,
    cup_level: int | None,
    cup_level_index: int | None,
) -> dict[str, str | None]:
    if cup_level is None:
        return {
            "scope": None,
            "scope_label": "Sin clasificar",
            "tier": None,
            "tier_label": "Sin clasificar",
            "prize_key": None,
        }
    scope = "national" if (cup_league_level or 0) == 0 else "divisional"
    scope_label = "Nacional" if scope == "national" else f"Divisional · nivel {cup_league_level}"
    if cup_level == 1:
        tier, tier_label = "main", "Principal"
    elif cup_level == 2:
        tier = "challenge"
        tier_label = f"Desafío {CHALLENGE_NAMES.get(cup_level_index or 0, '')}".strip()
    elif cup_level == 3:
        tier, tier_label = "consolation", "Consuelo"
    else:
        tier, tier_label = "other", f"Nivel {cup_level}"
    prize_key = f"{scope}_{tier}" if tier in {"main", "challenge"} else None
    return {
        "scope": scope,
        "scope_label": scope_label,
        "tier": tier,
        "tier_label": tier_label,
        "prize_key": prize_key,
    }


def _stage_label(rounds_left: int | None) -> str | None:
    if rounds_left is None or rounds_left < 0:
        return None
    labels = {0: "Campeón", 1: "Final", 2: "Semifinal", 3: "Cuartos", 4: "Octavos"}
    return labels.get(rounds_left, f"Ronda de {2**rounds_left}")


def _prize_goal(
    prize_key: str | None,
    rounds_left: int | None,
    rate: float,
    league_system_id: int,
    is_consolation: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    femme_factor = 0.75 if league_system_id == 2 else 1.0

    def conv(amount_sek: int) -> int:
        return int(round(amount_sek * femme_factor / (rate or 1.0)))

    source = CUP_PRIZES_SEK.get(prize_key or "", [])
    table = []
    for stage, amount_sek, from_title in source:
        if rounds_left is None:
            status = "future"
            wins_needed = None
        elif from_title > rounds_left:
            status = "passed"
            wins_needed = 0
        elif from_title == rounds_left:
            status = "current"
            wins_needed = 0
        else:
            status = "future"
            wins_needed = rounds_left - from_title
        table.append(
            {
                "stage": stage,
                "amount": conv(amount_sek),
                "rounds_from_title": from_title,
                "status": status,
                "wins_needed": wins_needed,
                "trophy_only": False,
            }
        )

    if is_consolation:
        table = [
            {
                "stage": "Campeón",
                "amount": 0,
                "rounds_from_title": 0,
                "status": "current" if rounds_left == 0 else "future",
                "wins_needed": rounds_left,
                "trophy_only": True,
            }
        ]

    current = next((row for row in table if row["status"] == "current"), None)
    future = [row for row in table if row["status"] == "future"]
    next_milestone = max(future, key=lambda row: row["rounds_from_title"], default=None)
    champion = next((row for row in table if row["rounds_from_title"] == 0), None)
    goal = {
        "stage": _stage_label(rounds_left),
        "rounds_left": rounds_left,
        "wins_to_title": rounds_left,
        "secured_amount": current["amount"] if current else 0,
        "next_milestone": next_milestone,
        "title_amount": champion["amount"] if champion else 0,
        "trophy_only": is_consolation,
    }
    return table, goal


def _loss_destination(
    classification: dict[str, str | None],
    cup_league_level: int,
    cup_level_index: int,
    match_round: int | None,
    cups: list[m.WorldCup],
) -> tuple[bool | None, str | None, str]:
    tier = classification["tier"]
    destination_level: int | None = None
    destination_index = 1
    if tier == "main" and match_round in {1, 2, 3, 4, 5, 6}:
        destination_level = 2
        destination_index = 1 if match_round in {1, 6} else 2 if match_round in {2, 5} else 3
    elif tier == "challenge" and match_round == 1 and cup_level_index in {1, 2}:
        destination_level = 3
    elif match_round is None:
        return (
            None,
            None,
            "La ruta tras una derrota se conocerá cuando Hattrick entregue la ronda oficial.",
        )

    if destination_level is None:
        return False, None, "La derrota cerraría la participación de Copa esta temporada."

    row = next(
        (
            cup
            for cup in cups
            if cup.cup_league_level == cup_league_level
            and cup.cup_level == destination_level
            and cup.cup_level_index == destination_index
        ),
        None,
    )
    fallback = (
        f"Copa Desafío {CHALLENGE_NAMES[destination_index]}"
        if destination_level == 2
        else "Copa de Consuelo"
    )
    name = row.cup_name if row else fallback
    return (
        True,
        name,
        f"La derrota trasladaría al equipo a {name}; la temporada de Copa continuaría.",
    )


async def _readiness(
    session: AsyncSession,
    team_id: int,
    team_ht_id: int,
    cup_matches: list[m.Match],
    cup_matches_played_this_season: int,
) -> dict[str, Any]:
    latest = (
        select(
            m.PlayerSnapshot.player_id.label("pid"),
            func.max(m.PlayerSnapshot.captured_at).label("mx"),
        )
        .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
        .group_by(m.PlayerSnapshot.player_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(m.PlayerSnapshot, m.Player)
            .join(
                latest,
                (m.PlayerSnapshot.player_id == latest.c.pid)
                & (m.PlayerSnapshot.captured_at == latest.c.mx),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
        )
    ).all()
    roster = [(snap, player) for snap, player in rows]
    by_ht_player_id = {player.ht_player_id: (snap, player) for snap, player in roster}

    def lineup_xi(lineup_json: str | None) -> list[tuple[m.PlayerSnapshot, m.Player]] | None:
        if not lineup_json:
            return None
        try:
            submitted = json.loads(lineup_json)
            ids = [
                int(row["ht_player_id"])
                for row in submitted
                if isinstance(row, dict) and row.get("ht_player_id")
            ]
        except (TypeError, ValueError, KeyError):
            return None
        xi = [by_ht_player_id[pid] for pid in ids if pid in by_ht_player_id]
        return xi if len(xi) >= 9 else None

    def opponent_of(mt: m.Match) -> str:
        return mt.away_team_name if mt.home_team_ht_id == team_ht_id else mt.home_team_name

    def penalty_order(xi: list[tuple[m.PlayerSnapshot, m.Player]]) -> list[dict[str, Any]]:
        """Los tiradores de ese once, del primero al último.

        2026-08-19, pedido explícito: el orden depende del once que estés
        mirando. Antes salía de TODA la plantilla, así que podía proponer de
        tirador a alguien que ni siquiera está en el campo cuando llegan los
        penaltis.
        """
        filas = []
        for snap, player in xi:
            # Índice transparente para ordenar, no una probabilidad de marcar.
            indice = (
                (snap.set_pieces or 0) * 0.45
                + (snap.scoring or 0) * 0.30
                + snap.experience * 0.20
                + (1.0 if snap.specialty == 1 else 0.0)
            )
            filas.append(
                {
                    "ht_player_id": player.ht_player_id,
                    "name": f"{player.first_name} {player.last_name}",
                    "set_pieces": snap.set_pieces or 0,
                    "scoring": snap.scoring or 0,
                    "experience": snap.experience,
                    "technical": snap.specialty == 1,
                    "readiness_index": round(indice, 2),
                }
            )
        filas.sort(key=lambda fila: (-fila["readiness_index"], fila["name"]))
        return filas

    def stamina_summary(xi: list[tuple[m.PlayerSnapshot, m.Player]]) -> dict[str, Any]:
        average_stamina = round(sum(snap.stamina for snap, _ in xi) / len(xi), 1) if xi else None
        # Resistencia (Stamina skill) va de 0 a 9, no de 0 a 20, esa era la
        # escala equivocada que también arrastraba el "/20" mostrado en el
        # frontend (bug real reportado 2026-08-13).
        stamina_bands = [
            {
                "label": "Frágil para 120'",
                "min": 0,
                "max": 5,
                "count": sum(1 for snap, _ in xi if snap.stamina <= 5),
            },
            {
                "label": "Intermedia",
                "min": 6,
                "max": 7,
                "count": sum(1 for snap, _ in xi if 6 <= snap.stamina <= 7),
            },
            {
                "label": "Preparada",
                "min": 8,
                "max": 9,
                "count": sum(1 for snap, _ in xi if snap.stamina >= 8),
            },
        ]
        return {
            "average_stamina": average_stamina,
            "stamina_bands": stamina_bands,
            "starters_count": len(xi),
            # Los once que patearían si el partido llega a penaltis con ESTE
            # once en el campo.
            "penalty_candidates": penalty_order(xi),
        }

    top_tsi_xi = sorted(roster, key=lambda row: row[0].tsi, reverse=True)[:11]
    variants: list[dict[str, Any]] = [
        {
            "mode": "top_tsi",
            "label": "11 jugadores activos con mayor TSI",
            "source_match_id": None,
            "source_opponent": None,
            "source_date": None,
            **stamina_summary(top_tsi_xi),
        }
    ]

    # La alineación que el manager ya envió para el próximo partido es la
    # referencia más fiel para evaluar la resistencia del equipo. El sync la
    # lee de `matchorders.xml` únicamente cuando `matches.xml` confirma
    # OrdersGiven=true; por eso no se muestra este modo si todavía no hay una
    # formación enviada y nunca se sustituye por una alineación inventada.
    for mt in sorted(
        (x for x in cup_matches if x.status.upper() != "FINISHED"),
        key=lambda x: x.played_at,
    ):
        xi = lineup_xi(mt.submitted_lineup_json)
        if xi:
            variants.append(
                {
                    "mode": "submitted",
                    "label": "Formación enviada",
                    "source_match_id": mt.ht_match_id,
                    "source_opponent": opponent_of(mt),
                    "source_date": mt.played_at.date().isoformat(),
                    **stamina_summary(xi),
                }
            )
            break

    # "Última formación en Copa" solo se ofrece si ya se jugó más de un
    # partido de Copa esta temporada, pedido explícito 2026-08-13: con un
    # solo partido no hay nada distinto que mostrar frente al historial.
    if cup_matches_played_this_season > 1:
        for mt in sorted(
            (x for x in cup_matches if x.status.upper() == "FINISHED"),
            key=lambda x: x.played_at,
            reverse=True,
        ):
            xi = lineup_xi(mt.submitted_lineup_json)
            if xi:
                variants.append(
                    {
                        "mode": "last_cup",
                        "label": "Última formación en Copa",
                        "source_match_id": mt.ht_match_id,
                        "source_opponent": opponent_of(mt),
                        "source_date": mt.played_at.date().isoformat(),
                        **stamina_summary(xi),
                    }
                )
                break

    league_candidates = (
        (
            await session.execute(
                select(m.Match)
                .where(
                    (
                        (m.Match.home_team_ht_id == team_ht_id)
                        | (m.Match.away_team_ht_id == team_ht_id)
                    ),
                    m.Match.match_type == MATCH_TYPE_LEAGUE,
                    m.Match.status == "FINISHED",
                    m.Match.submitted_lineup_json.is_not(None),
                )
                .order_by(m.Match.played_at.desc())
                .limit(5)
            )
        )
        .scalars()
        .all()
    )
    for mt in league_candidates:
        xi = lineup_xi(mt.submitted_lineup_json)
        if xi:
            variants.append(
                {
                    "mode": "last_league",
                    "label": "Última formación en Liga",
                    "source_match_id": mt.ht_match_id,
                    "source_opponent": opponent_of(mt),
                    "source_date": mt.played_at.date().isoformat(),
                    **stamina_summary(xi),
                }
            )
            break

    if any(v["mode"] == "submitted" for v in variants):
        default_mode = "submitted"
    elif any(v["mode"] == "last_cup" for v in variants):
        default_mode = "last_cup"
    else:
        default_mode = "top_tsi"

    best_keeper = max(roster, key=lambda row: row[0].keeper or 0, default=None)
    return {
        "reference_variants": variants,
        "default_mode": default_mode,
        # El orden del once por defecto. Cada variante trae el suyo, y la
        # pantalla usa el de la que esté seleccionada.
        "penalty_candidates": next(
            (v["penalty_candidates"] for v in variants if v["mode"] == default_mode),
            [],
        ),
        "goalkeeper": (
            {
                "ht_player_id": best_keeper[1].ht_player_id,
                "name": f"{best_keeper[1].first_name} {best_keeper[1].last_name}",
                "keeper": best_keeper[0].keeper or 0,
            }
            if best_keeper
            else None
        ),
        "penalty_method": (
            "Orden orientativo: 45% balón parado, 30% anotación, 20% experiencia "
            "y bonificación técnica. Es un índice comparativo, no una probabilidad."
        ),
    }


#: Lo que se queda el equipo LOCAL de la taquilla de un partido de Copa; el
#: 33 % restante va para el visitante. Estaba puesto a mano en dos sitios, con
#: un 67 escrito en un texto y otro en una cuenta.
CUOTA_LOCAL_DE_COPA = 0.67


async def _cup_economy(
    session: AsyncSession,
    team: m.Team,
    next_match: m.Match | None,
    rounds_left: int | None,
    world: m.WorldContext | None,
) -> dict[str, Any]:
    todos = (
        await session.execute(
            select(m.StadiumHistory, m.Match)
            .join(m.Match, m.Match.ht_match_id == m.StadiumHistory.ht_match_id)
            .where(m.StadiumHistory.team_id == team.id, m.Match.match_type == CUP_MATCH_TYPE)
            .order_by(m.StadiumHistory.played_at)
        )
    ).all()
    # SOLO LA TEMPORADA EN CURSO (2026-09-28, instruccion del usuario: «la
    # seccion Copa solo debe hablar de las copas de la temporada actual»).
    #
    # Esta pantalla es de LA copa que se esta jugando, no del palmares: sin el
    # corte, la taquilla sumaba sesenta y seis partidos de varias temporadas y
    # se leia como si fueran los de esta. La misma regla de temporada que usan
    # Partidos y Estadio, para que una fecha no caiga en temporadas distintas
    # segun la pantalla.
    #
    # Sin `world` no hay ancla para saber de que temporada es una fecha, y
    # entonces se prefiere no recortar a recortar mal: se cuentan todos y la
    # pantalla lo dice por el numero de partidos.
    temporada = world.season if world is not None else None
    rows = (
        [
            (foto, partido)
            for foto, partido in todos
            if season_for_datetime(world, partido.played_at) == temporada
        ]
        if temporada is not None
        else todos
    )
    # PUBLICO Y TAQUILLA, los dos reales (2026-09-28).
    #
    # El publico sale de `sold_total`, que Hattrick enseña en la pagina del
    # partido. La taquilla sale de las entradas de cada sector por su precio,
    # que es la unica forma de tenerla por partido: Hattrick la publica por
    # semana y sumada, y los partidos de Copa comparten semana con los de liga
    # casi siempre, asi que atribuirla por cierres no funciona (probado con los
    # datos del usuario: de nueve cierres, uno solo tenia un unico partido en
    # casa, y no era de Copa).
    #
    # EL DESGLOSE NO SALE DE AQUI. Se usa para sumar y se queda dentro: lo que
    # viaja es el total. Decision del usuario, y lo fija
    # `test_el_desglose_por_sector_no_sale_nunca`.
    #
    # Los partidos sincronizados entre el 2026-09-01 y hoy no tienen desglose y
    # se quedan FUERA del dinero hasta que el sync lo complete. Siguen contando
    # para el publico, que ese si esta guardado.
    # EN CASA Y FUERA (2026-09-28, lo dijo el usuario: «los partidos de
    # visitante de Copa tambien me dan taquilla»). El reparto de Copa es 67/33,
    # asi que de un partido fuera te llega el 33 % de la taquilla de ESE
    # estadio. El publico, en cambio, solo se cuenta en casa: es el de tu
    # estadio, y mezclarlo con el del rival no describe nada.
    en_casa = [foto for foto, _p in rows if foto.own_venue]
    asistencias: list[int] = [int(f.sold_total) for f in en_casa if f.sold_total]
    total_publico = sum(asistencias)

    brutos_casa = taquilla_de_varios(en_casa)
    brutos_fuera = taquilla_de_varios([foto for foto, _p in rows if not foto.own_venue])
    taquillas = brutos_casa + brutos_fuera
    bruto = sum(taquillas)
    tuyo = sum(brutos_casa) * CUOTA_LOCAL_DE_COPA + sum(brutos_fuera) * (1 - CUOTA_LOCAL_DE_COPA)

    return {
        "currency": team.currency_name or "",
        "observed_home_matches": len(asistencias),
        "observed_attendance": total_publico,
        "best_attendance": max(asistencias) if asistencias else 0,
        "average_attendance": int(round(total_publico / len(asistencias))) if asistencias else 0,
        #: Cuantos de esos partidos tienen taquilla calculada. Menos que los
        #: medidos = faltan desgloses por completar, y la pantalla lo dice.
        "matches_with_gate": len(taquillas),
        # LA SUMA DE TODOS, y despues el reparto (2026-09-28, pedido del
        # usuario con estas palabras: «la suma de los partidos de Copa teniendo
        # en cuenta el 67-33% de la suma de entradas por cada tipo de asiento»).
        #
        # SIN DIVIDIR POR LA TASA. Los cuatro precios ya estan en la moneda del
        # club --se derivaron de los ingresos que Hattrick ENSEÑA, no de su
        # moneda base-- igual que los usa el simulador de ampliacion, que
        # tampoco convierte. Dividir aqui daria un 10 % de lo real en Colombia,
        # que es justo el fallo que reporto un usuario con otro equipo.
        "observed_gross_gate": bruto,
        #: Tu parte: el 67 % de lo que se recaudo en tu estadio y el 33 % de lo
        #: que se recaudo en el del rival.
        "observed_share": int(round(tuyo)),
        "share_percent": int(round(CUOTA_LOCAL_DE_COPA * 100)),
        #: Cuantos de los partidos con taquilla se jugaron fuera, para que la
        #: pantalla no diga «67 %» de una suma que lleva partidos al 33 %.
        "away_matches_with_gate": len(brutos_fuera),
    }


def _en_utc(momento: datetime) -> datetime:
    """Las fechas de la base viajan en UTC sin zona; aquí se les pone."""
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)


def solo_de_la_temporada(
    partidos: Iterable[m.Match],
    temporada: int | None,
    temporada_de: Callable[[m.Match], int | None],
) -> list[m.Match]:
    """Los partidos de la temporada en curso, y nada más.

    EXISTE PARA QUE HAYA UN SOLO CORTE. Lo había en el historial y no en los
    próximos, y esa asimetría es justo lo que el usuario vio el 2026-11-05 en
    Rivales: «todavía siguen en la lista aquellos rivales de Copa de temporadas
    pasadas».

    Una llave vieja que nunca llegó a `FINISHED` --abandonada, o sincronizada a
    medias el día que el equipo quedó eliminado-- se quedaba en «próximos» para
    siempre, y su rival volvía a salir en Elegir rival marcado «programado»,
    temporada tras temporada. Una copa es de su temporada por definición: la
    del año pasado no tiene próximos.

    SIN MUNDO NO SE CORTA. Sin `worlddetails` no hay ancla para saber de qué
    temporada es una fecha, y tirar partidos a ciegas sería peor que
    enseñarlos: se devuelven todos y la pantalla dice lo que sabe.
    """
    if temporada is None:
        return list(partidos)
    return [p for p in partidos if temporada_de(p) == temporada]


async def _prediccion_de_rivales(
    session: AsyncSession,
    team: m.Team,
    rival_ht_id: int,
    metodo_propio: str = PitchZoneMethod.SUBMITTED,
    metodo_rival: str = PitchZoneMethod.AVERAGE,
) -> dict[str, Any] | None:
    """La predicción del próximo cruce: LA MISMA que enseña la ficha de rival.

    2026-11-09, pedido del usuario: la de Copa «debe ser la misma de si me voy
    a Rivales». No se recalcula aquí con otra muestra: se le pide a la ficha
    de ese rival, con los mismos dos selectores, y se pinta lo que diga. Dos
    pantallas contestando la misma pregunta con dos números distintos era
    justo lo que no podía pasar.

    AQUÍ VIVÍA `_prediccion_del_cruce`, que resumía sólo partidos de Copa (con
    la Liga de respaldo), aplicaba la sede y miraba hacia atrás las semanas ya
    jugadas de la temporada. Eso último la dejaba muda en la semana 1: una
    sola semana de ventana, sin un oficial dentro. La ficha mira siempre
    dieciséis.

    LO QUE SE HEREDA DE LA FICHA, dicho para que no sorprenda: resume los
    últimos oficiales de cada lado --Liga y Copa juntas-- y no aplica la sede
    en un cruce de copa, porque desde allí no se sabe qué rondas son neutrales.

    EN OTRA SESIÓN DE BASE, a propósito. La ficha guarda los partidos del
    rival que descarga y, si ese guardado falla, deshace su transacción; hecho
    sobre la sesión de esta pantalla, dejaría caducados el equipo y los
    partidos que el resto de la respuesta todavía tiene que leer.

    DEVUELVE `None` Y NO REVIENTA cuando no hay con qué: sin dueño, sin sesión
    de Hattrick, si Hattrick no contesta, o si la ficha no llega a tener
    ratings de los dos lados. La pantalla dice entonces «sin datos».
    """
    if team.owner_user_id is None or not rival_ht_id:
        return None
    # Importado aquí: la ficha de rival es un módulo de 1.800 líneas con sus
    # propias dependencias, y Copa sólo la necesita en este punto.
    from app.api.v1.endpoints.rivals import rival_scouting

    try:
        async with AsyncSession(session.bind, expire_on_commit=False) as aparte:
            usuario = await aparte.get(m.User, team.owner_user_id)
            if usuario is None:
                return None
            ficha = await rival_scouting(
                team.id,
                rival_ht_id,
                log_tsi=False,
                top11=False,
                include_competitive=True,
                include_friendlies=False,
                pitch_zone_method_own=metodo_propio,
                pitch_zone_method_rival=metodo_rival,
                session=aparte,
                user=usuario,
            )
    except HTTPException:
        # Sin token, acceso revocado o Hattrick caído: la ficha lo dice con un
        # error porque es su pantalla; aquí es un panel más y se queda vacío.
        return None
    dicho = ficha.get("prediction")
    if not dicho:
        return None
    return {
        "own_probability": dicho["ownProbability"],
        "rival_probability": dicho["rivalProbability"],
        "expected_own_goals": dicho["expectedOwnGoals"],
        "expected_rival_goals": dicho["expectedRivalGoals"],
        "most_likely_score": dicho["mostLikelyScore"],
        "own_matches": dicho["ownMatches"],
        "rival_matches": dicho["rivalMatches"],
        # El método que de verdad se usó, no el pedido: si se pidió «alineación
        # enviada» y todavía no hay ninguna, la ficha cae al historial y lo dice.
        "metodo_propio": ficha.get("pitchZoneMethodOwn") or dicho["metodoPropio"],
        "metodo_rival": ficha.get("pitchZoneMethodRival") or dicho["metodoRival"],
        "indirectas_prestadas": dicho["indirectasPrestadas"],
    }


@router.get(
    "/teams/{team_id}/cup",
    summary="Copa: estado, meta y decisiones",
    dependencies=[Depends(require_team_owner)],
)
async def cup(
    team_id: int,
    pitch_zone_method_own: str = PitchZoneMethod.SUBMITTED,
    pitch_zone_method_rival: str = PitchZoneMethod.AVERAGE,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """La Copa, calculada una vez por sync (2026-09-14), pero con vida corta:
    el pronóstico usa tus órdenes enviadas, y esas se cambian hasta el pitido."""
    from app.api.cache_por_sync import por_sync

    return await por_sync(
        session,
        team_id,
        "copa",
        (pitch_zone_method_own, pitch_zone_method_rival),
        lambda: _cup_sin_cache(team_id, pitch_zone_method_own, pitch_zone_method_rival, session),
        ttl=300,
    )


async def _cup_sin_cache(
    team_id: int,
    # LOS MISMOS SELECTORES QUE LA FICHA DE RIVAL (2026-09-09, pedido del
    # usuario: «hereda también esos selectores»). Uno por lado, porque lo que
    # se quiere saber de uno mismo no es lo mismo que del rival, y del lado
    # propio existe además la alineación ya enviada, que de él nunca se ve.
    pitch_zone_method_own: str = PitchZoneMethod.SUBMITTED,
    pitch_zone_method_rival: str = PitchZoneMethod.AVERAGE,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    team = await session.get(m.Team, team_id)
    if team is None:
        raise HTTPException(404, f"team {team_id} not found")

    world = None
    cups: list[m.WorldCup] = []
    if team.ht_league_id is not None:
        world = await session.scalar(
            select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
        )
        cups = list(
            (
                await session.execute(
                    select(m.WorldCup).where(m.WorldCup.ht_league_id == team.ht_league_id)
                )
            ).scalars()
        )
    cup_by_id = {row.ht_cup_id: row for row in cups if row.ht_cup_id}
    current_season = world.season if world is not None else None

    def match_season(mt: m.Match) -> int | None:
        if world is None:
            return None
        return season_for_datetime(world, mt.played_at)

    def cup_row_of(mt: m.Match) -> m.WorldCup | None:
        candidates = [
            row
            for row in cups
            if row.cup_level == mt.cup_level and row.cup_level_index == mt.cup_level_index
        ]
        if team.current_cup_id:
            active = cup_by_id.get(team.current_cup_id)
            if active in candidates:
                return active
        expected_league_level = team.league_level if team.league_level > 6 else 0
        return next(
            (row for row in candidates if row.cup_league_level == expected_league_level),
            candidates[0] if candidates else None,
        )

    matches = list(
        (
            await session.execute(
                select(m.Match)
                .where(
                    (
                        (m.Match.home_team_ht_id == team.ht_team_id)
                        | (m.Match.away_team_ht_id == team.ht_team_id)
                    ),
                    m.Match.match_type == CUP_MATCH_TYPE,
                )
                .order_by(m.Match.played_at)
            )
        ).scalars()
    )
    played = [mt for mt in matches if mt.status.upper() == "FINISHED"]
    # LOS PRÓXIMOS, SÓLO DE ESTA TEMPORADA (2026-11-05, lo vio el usuario en
    # Rivales: «todavía siguen en la lista aquellos rivales de Copa de
    # temporadas pasadas»).
    #
    # `upcoming` salía de `matches`, que son TODAS las temporadas, mientras que
    # el historial sí se recortaba. Una llave vieja que nunca llegó a
    # `FINISHED` --abandonada, o sincronizada a medias el día que el equipo
    # quedó eliminado-- se quedaba en «próximos» para siempre: temporada tras
    # temporada, su rival volvía a aparecer en Elegir rival marcado como
    # «programado». Una copa es de su temporada por definición; la del año
    # pasado no tiene próximos.
    #
    # Arrastra con él a `still_in_cup` y a `next_match`, y es lo correcto en
    # los tres: seguir en la copa es seguir en la de ESTE año.
    # Los próximos, SÓLO de esta temporada. Arrastra con él a `still_in_cup` y
    # a `next_match`, y es lo correcto en los tres: seguir en la copa es seguir
    # en la de ESTE año.
    upcoming = solo_de_la_temporada(
        [mt for mt in matches if mt.status.upper() != "FINISHED"],
        current_season,
        match_season,
    )
    next_match = min(upcoming, key=lambda mt: mt.played_at, default=None)
    latest_match = next_match or max(played, key=lambda mt: mt.played_at, default=None)

    active_world_cup = cup_by_id.get(team.current_cup_id or 0)
    fallback_world_cup = cup_row_of(latest_match) if latest_match else None
    current_world_cup = active_world_cup or fallback_world_cup
    # LA BANDERA O UN CRUCE PROGRAMADO (2026-11-09). `still_in_cup` de Hattrick
    # sigue diciendo «no» desde la eliminación de la temporada pasada hasta que
    # se juega el primer partido de la copa nueva, y durante esos días el
    # cruce ya está en el calendario. Fiándose sólo de la bandera, esta
    # pantalla enseñaba la tarjeta de eliminado y no predecía nada con un
    # partido de copa a la vista. Es la misma regla que la 6.1.3 puso en el
    # aviso del amistoso.
    #
    # PROGRAMADO ES CON FECHA POR DELANTE: un partido viejo de esta temporada
    # que se quedó sin cerrar no resucita a un eliminado.
    ahora = datetime.now(UTC)
    hay_cruce_programado = any(_en_utc(mt.played_at) > ahora for mt in upcoming)
    bandera_vale = team.still_in_cup is not None and not (
        team.still_in_cup is False and hay_cruce_programado
    )
    still_in_cup = bool(team.still_in_cup) if bandera_vale else bool(upcoming)
    status_source = "teamdetails" if bandera_vale else "calendario"

    cup_league_level = (
        team.current_cup_league_level
        if team.still_in_cup and team.current_cup_league_level is not None
        else current_world_cup.cup_league_level
        if current_world_cup
        else None
    )
    cup_level = (
        team.current_cup_level
        if team.still_in_cup and team.current_cup_level is not None
        else current_world_cup.cup_level
        if current_world_cup
        else latest_match.cup_level
        if latest_match
        else None
    )
    cup_level_index = (
        team.current_cup_level_index
        if team.still_in_cup and team.current_cup_level_index is not None
        else current_world_cup.cup_level_index
        if current_world_cup
        else latest_match.cup_level_index
        if latest_match
        else None
    )
    current_name = (
        team.current_cup_name
        if team.still_in_cup and team.current_cup_name
        else current_world_cup.cup_name
        if current_world_cup
        else None
    )
    official_round = (
        team.current_cup_match_round
        if team.still_in_cup and team.current_cup_match_round is not None
        else current_world_cup.match_round
        if still_in_cup and current_world_cup and current_world_cup.match_round >= 0
        else None
    )
    # Rows created before migration 0035 carry the database defaults
    # MatchRound=-1/MatchRoundsLeft=0. Zero is meaningful only when CHPP also
    # supplied a valid round; by itself it must never be read as "champion".
    rounds_left = (
        team.current_cup_match_rounds_left
        if (
            team.still_in_cup
            and team.current_cup_match_round is not None
            and team.current_cup_match_rounds_left is not None
        )
        else current_world_cup.match_rounds_left
        if (still_in_cup and current_world_cup and current_world_cup.match_round >= 0)
        else None
    )
    classification = _classification(cup_league_level, cup_level, cup_level_index)
    prize_table, goal = _prize_goal(
        cast(str | None, classification["prize_key"]),
        rounds_left,
        team.currency_rate or 1.0,
        world.league_system_id if world else 1,
        classification["tier"] == "consolation",
    )

    # Historial: solo la temporada actual (pedido explícito 2026-08-13), sin
    # aviso, el usuario ya sabe que es así.
    matches_this_season = solo_de_la_temporada(matches, current_season, match_season)
    played_this_season = [mt for mt in matches_this_season if mt.status.upper() == "FINISHED"]

    ratings_by_match = {
        row.ht_match_id: row
        for row in (
            await session.execute(
                select(m.MatchRating).where(
                    m.MatchRating.ht_match_id.in_(
                        [mt.ht_match_id for mt in played_this_season] or [-1]
                    ),
                    m.MatchRating.team_ht_id == team.ht_team_id,
                )
            )
        ).scalars()
    }

    def side(mt: m.Match) -> tuple[bool, str, int]:
        is_home = mt.home_team_ht_id == team.ht_team_id
        return (
            is_home,
            mt.away_team_name if is_home else mt.home_team_name,
            mt.away_team_ht_id if is_home else mt.home_team_ht_id,
        )

    # La ronda de cada partido NO es una estimación: cada vez que el equipo
    # entra a una llave concreta (cup_level, cup_level_index) esa llave
    # arranca en ronda 1 y avanza de uno en uno mientras se gana, verificado
    # en vivo 2026-08-13 contando los partidos de "Copa Cocuy Rubí" (2
    # jugados + el próximo) contra `current_cup_match_round`=3, que CHPP
    # confirma como oficial. Contar posición dentro de la llave DA el número
    # real. Se agrupa solo dentro de la temporada actual porque el índice de
    # llave (p. ej. Desafío Rubí) se reutiliza cada temporada.
    round_by_match_id: dict[int, int] = {}
    by_cup_key: dict[tuple[int, int], list[m.Match]] = {}
    for mt in matches_this_season:
        if mt.cup_level >= 0 and mt.cup_level_index >= 0:
            by_cup_key.setdefault((mt.cup_level, mt.cup_level_index), []).append(mt)
    for group in by_cup_key.values():
        for index, mt in enumerate(sorted(group, key=lambda item: item.played_at), start=1):
            round_by_match_id[mt.ht_match_id] = index

    won = drawn = lost = goals_for = goals_against = 0
    history = []
    for mt in played_this_season:
        is_home, opponent, opponent_ht_id = side(mt)
        own_goals = mt.home_goals if is_home else mt.away_goals
        opp_goals = mt.away_goals if is_home else mt.home_goals
        goals_for += own_goals
        goals_against += opp_goals
        if own_goals > opp_goals:
            won += 1
            result = "V"
        elif own_goals == opp_goals:
            drawn += 1
            result = "E"
        else:
            lost += 1
            result = "D"
        rating = ratings_by_match.get(mt.ht_match_id)
        hs = (
            hatstats(
                {
                    "midfield": rating.midfield,
                    "right_def": rating.right_def,
                    "central_def": rating.central_def,
                    "left_def": rating.left_def,
                    "right_att": rating.right_att,
                    "central_att": rating.central_att,
                    "left_att": rating.left_att,
                }
            )
            if rating
            else None
        )
        row = cup_row_of(mt)
        history.append(
            {
                "ht_match_id": mt.ht_match_id,
                "date": mt.played_at.date().isoformat(),
                "opponent": opponent,
                "opponent_ht_team_id": opponent_ht_id,
                "is_home": is_home,
                "goals_for": own_goals,
                "goals_against": opp_goals,
                "result": result,
                "hatstats": hs,
                "round": round_by_match_id.get(mt.ht_match_id),
                "cup_name": row.cup_name if row else None,
            }
        )

    streak_count = 0
    streak_result: str | None = None
    for row in reversed(history):
        if streak_result is None:
            streak_result = cast(str, row["result"])
            streak_count = 1
        elif row["result"] == streak_result:
            streak_count += 1
        else:
            break
    current_streak = {"count": streak_count, "result": streak_result} if streak_result else None

    # La trayectoria se arma sobre `by_cup_key`, el MISMO agrupamiento que ya
    # numera las rondas: si el panel contara los partidos por su cuenta,
    # podría decir «1 partido» y numerar dos rondas en la tabla de al lado.
    #
    # Dos cosas que antes hacía y no debía. Recorría `matches` ENTERO, de
    # todas las temporadas, con el panel titulado «Trayectoria de la
    # temporada», un índice de llave se reutiliza cada temporada, así que la
    # copa del año pasado se colaba. Y agrupaba por TRAMOS SEGUIDOS: bastaba
    # una fila fuera de orden para partir una copa en dos escalones de un
    # partido cada uno. Agrupar por la llave misma no depende del orden en
    # que lleguen las filas.
    ladder: list[dict[str, Any]] = []
    for key, group in sorted(
        by_cup_key.items(), key=lambda item: min(mt.played_at for mt in item[1])
    ):
        ordenados = sorted(group, key=lambda item: item.played_at)
        row = cup_row_of(ordenados[0])
        ladder.append(
            {
                "cup_level": key[0],
                "cup_level_index": key[1],
                "cup_name": row.cup_name if row else None,
                "from_date": ordenados[0].played_at.date().isoformat(),
                "to_date": ordenados[-1].played_at.date().isoformat(),
                "matches": len(ordenados),
            }
        )

    is_neutral = rounds_left is not None and 0 < rounds_left <= 6
    next_matches = []
    for mt in sorted(upcoming, key=lambda item: item.played_at):
        row = cup_row_of(mt)
        next_matches.append(
            {
                "ht_match_id": mt.ht_match_id,
                "date": mt.played_at.date().isoformat(),
                "opponent": side(mt)[1],
                "opponent_ht_team_id": side(mt)[2],
                "is_home": side(mt)[0],
                "is_neutral": is_neutral,
                "venue_label": "Sede neutral"
                if is_neutral
                else "Local"
                if side(mt)[0]
                else "Visitante",
                "round_estimate": round_by_match_id.get(mt.ht_match_id),
                "official_round": official_round,
                "cup_name": row.cup_name if row else None,
            }
        )

    scenarios = None
    if still_in_cup and cup_level is not None:
        if rounds_left == 1:
            win_text = f"Victoria: campeón de {current_name or 'esta Copa'}."
        elif rounds_left is None:
            win_text = (
                "Victoria: avanza; la siguiente instancia se confirmará con la ronda oficial."
            )
        else:
            win_text = (
                f"Victoria: avanza a {_stage_label(rounds_left - 1) or 'la siguiente ronda'}."
            )
        continues, destination, loss_text = _loss_destination(
            classification,
            cup_league_level or 0,
            cup_level_index or 1,
            official_round,
            cups,
        )
        scenarios = {
            "win": {
                "continues": True,
                "destination": current_name,
                "description": win_text,
                "next_stage": (
                    _stage_label(rounds_left - 1)
                    if rounds_left is not None and rounds_left > 0
                    else None
                ),
                "prize_amount": goal["next_milestone"]["amount"]
                if goal["next_milestone"]
                else goal["title_amount"],
            },
            "loss": {
                "continues": continues,
                "destination": destination,
                "description": loss_text,
                "next_stage": None,
                "prize_amount": goal["secured_amount"],
            },
        }

    readiness = await _readiness(
        session,
        team_id,
        team.ht_team_id,
        matches,
        len(played_this_season),
    )
    # La predicción del cruce: sólo si queda uno por jugar. Cuesta llamadas a
    # Hattrick (la ficha del rival), así que no se paga cuando ya no hay nada
    # que predecir.
    prediccion = None
    if next_match is not None and still_in_cup:
        prediccion = await _prediccion_de_rivales(
            session,
            team,
            side(next_match)[2],
            metodo_propio=pitch_zone_method_own,
            metodo_rival=pitch_zone_method_rival,
        )

    economy = await _cup_economy(session, team, next_match, rounds_left, world)
    experience_multiplier = 2.0 if classification["tier"] == "main" else 0.5
    impact = {
        "experience_multiplier_vs_league": experience_multiplier,
        "experience_points_per_90": 3.5 * experience_multiplier,
        "affects_club_mood": classification["tier"] == "main",
        "injury_effect": "Riesgo completo de partido competitivo",
    }

    # ── La salvaguardia: contar y preguntar dan el mismo número, o se dice ──
    #
    # La ronda de cada partido se CUENTA (posición dentro de su llave) y CHPP
    # la DICE (`current_cup_match_round`, de teamdetails). Mientras las dos
    # cuentas coincidan, la de aquí está completa. Cuando no coinciden, faltan
    # partidos, y ese es justo el hueco que se vio el 2026-09-07: la Copa
    # Colombia de esta temporada salía con un partido en vez de dos, porque
    # el calendario de Hattrick sólo alcanza un mes hacia atrás y esta base
    # empezó después. Callarlo era lo peor: el panel se dibujaba entero y
    # nada avisaba de que le faltaba media trayectoria.
    #
    # Sólo se puede comprobar la copa en la que se sigue vivo: de una ya
    # eliminada CHPP no dice ninguna ronda contra la que contrastar.
    rondas_contadas: int | None = None
    if still_in_cup and cup_level is not None and cup_level_index is not None:
        grupo_activo = by_cup_key.get((cup_level, cup_level_index))
        if grupo_activo:
            rondas_contadas = len(grupo_activo)

    notes = []
    if not matches:
        notes.append("Todavía no hay partidos de Copa sincronizados.")
    if (
        official_round is not None
        and rondas_contadas is not None
        and rondas_contadas != official_round
    ):
        notes.append(
            f"Faltan partidos por sincronizar: vas por la ronda {official_round} "
            f"y aquí sólo hay {rondas_contadas}. La trayectoria y las rondas del "
            "historial se quedan cortas hasta que la próxima sincronización los "
            "rescate."
        )
    if team.still_in_cup is None:
        notes.append("Sincroniza para leer si sigues en Copa: por ahora se deduce del calendario.")
    if official_round is None and still_in_cup:
        notes.append("Sincroniza para leer la ronda oficial.")

    # Los rivales del Hattrick Masters, para la pestaña de Elegir rival
    # (2026-09-13). No es copa --otro torneo, otras reglas de clasificación--
    # así que no entra en nada de lo de arriba; sólo viaja en esta respuesta
    # porque es la que ya pide esa pantalla. Misma temporada que la copa.
    from app.domain.value_objects.ht_constants import MATCH_TYPE_MASTERS

    partidos_masters = [
        mt
        for mt in (
            await session.execute(
                select(m.Match)
                .where(
                    (m.Match.home_team_ht_id == team.ht_team_id)
                    | (m.Match.away_team_ht_id == team.ht_team_id),
                    m.Match.match_type == MATCH_TYPE_MASTERS,
                )
                .order_by(m.Match.played_at)
            )
        ).scalars()
        if current_season is None or match_season(mt) == current_season
    ]
    masters_rivals = []
    for mt in partidos_masters:
        en_casa, rival, rival_id = side(mt)
        jugado = mt.status.upper() == "FINISHED" and mt.home_goals >= 0
        masters_rivals.append(
            {
                "ht_match_id": mt.ht_match_id,
                "date": mt.played_at.date().isoformat(),
                "opponent": rival,
                "opponent_ht_team_id": rival_id,
                "played": jugado,
                "goals_for": (mt.home_goals if en_casa else mt.away_goals) if jugado else None,
                "goals_against": (mt.away_goals if en_casa else mt.home_goals) if jugado else None,
            }
        )

    return cast(
        dict[str, Any],
        _camel(
            {
                "team_name": team.name,
                "currency": team.currency_name or "",
                "matches_played": len(played),
                "record": f"{won}-{drawn}-{lost}",
                "goals_for": goals_for,
                "goals_against": goals_against,
                "current_cup_name": current_name,
                "current_streak": current_streak,
                "status": {
                    "still_in_cup": still_in_cup,
                    "source": status_source,
                    "cup_id": team.current_cup_id
                    if team.still_in_cup
                    else current_world_cup.ht_cup_id
                    if current_world_cup
                    else None,
                    "cup_name": current_name,
                    "scope": classification["scope"],
                    "scope_label": classification["scope_label"],
                    "tier": classification["tier"],
                    "tier_label": classification["tier_label"],
                    "official_round": official_round,
                    "counted_rounds": rondas_contadas,
                    "rounds_left": rounds_left,
                    "stage_label": _stage_label(rounds_left),
                    "next_cup_match_date": world.cup_match_date.isoformat()
                    if world and world.cup_match_date
                    else None,
                },
                "goal": goal,
                "scenarios": scenarios,
                "prediction": prediccion,
                "impact": impact,
                "economy": economy,
                "readiness": readiness,
                "ladder": ladder,
                "history": history,
                "next_matches": next_matches,
                "masters_rivals": masters_rivals,
                "prize_table": prize_table,
                "notes": notes,
            }
        ),
    )
