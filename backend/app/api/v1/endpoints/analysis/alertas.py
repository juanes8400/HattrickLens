"""Alertas: las que se derivan y las que el usuario archiva.

Sale de partir `analysis.py`, que tenia 2309 lineas y se abria
entera para tocar cualquiera de sus rutas. El `__init__.py` del paquete
monta `router` con todos estos, asi que las URL no cambian.
"""

import hashlib
from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_team_owner
from app.api.v1.endpoints.analysis.plantilla import roster
from app.application.queries.academy import AcademyQueryService
from app.application.queries.arena import ArenaQueryService
from app.application.queries.economy import (
    VENTANA_POR_DEFECTO,
    _closed_sponsor_income,
    balances_de_autonomia,
    estructura_semanal,
    weekly_closes,
)
from app.application.queries.training_context import TrainingContextService
from app.application.queries.weekly import season_week_for_datetime
from app.domain.engines import insights as ins
from app.domain.engines.lineup_optimizer import (
    best_formation,
)
from app.domain.engines.position_engine import rate_all
from app.domain.engines.training_engine import (
    TrainingSetup,
    weeks_to_next_level,
)
from app.domain.engines.training_engine import (
    default_setup as default_training_setup,
)
from app.domain.value_objects.ht_constants import (
    NON_OFFICIAL_MATCH_TYPES,
    training_target,
)
from app.domain.value_objects.ht_time import ht_day
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session

router = APIRouter()


async def _next_match_weather_insights(session: AsyncSession, team: m.Team) -> list[ins.Insight]:
    """El clima del próximo partido, si el pronóstico guardado sigue vigente.

    Hattrick solo publica hoy y mañana, así que el aviso vive de que el último
    sync sea reciente: el pronóstico guardado dice de qué día era su "hoy"
    (`forecast_taken_at`, reloj del servidor sueco) y desde ahí se sitúa el
    partido. Si el sync es de anteayer, no se avisa nada, enseñar el clima de
    anteayer como si fuera el de esta tarde sería peor que no decir nada.
    """
    # El mismo filtro que usa el sync al pedir el pronóstico: escaleras,
    # duelos y torneos no cuentan como "el próximo partido" en esta app.
    match = await session.scalar(
        select(m.Match)
        .where(
            or_(
                m.Match.home_team_ht_id == team.ht_team_id,
                m.Match.away_team_ht_id == team.ht_team_id,
            ),
            m.Match.status.ilike("upcoming"),
            m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES),
        )
        .order_by(m.Match.played_at)
        .limit(1)
    )
    if match is None:
        return []
    row = await session.scalar(
        select(m.MatchWeather).where(m.MatchWeather.ht_match_id == match.ht_match_id)
    )
    if row is None:
        return []

    dia_partido = ht_day(match.played_at)
    dia_pronostico = ht_day(row.forecast_taken_at)
    if dia_partido is None or dia_pronostico is None:
        return []
    faltan = (dia_partido - dia_pronostico).days
    # Solo hoy (0) y mañana (1): son los dos únicos días que trae el fichero.
    if faltan == 0:
        weather_id = row.weather_today
    elif faltan == 1:
        weather_id = row.weather_tomorrow
    else:
        return []

    is_home = match.home_team_ht_id == team.ht_team_id
    return ins.next_match_weather(
        match.ht_match_id,
        match.away_team_name if is_home else match.home_team_name,
        is_home,
        row.region_name,
        weather_id,
        tomorrow=faltan == 1,
    )


#: Cuántas semanas cerradas mira la alerta de concentración de ingresos. Cuatro
#: dejan pasar al menos un partido en casa aunque la liga vaya en pausa.
SEMANAS_DE_INGRESOS = 4

#: Hasta cuándo cuenta un partido para «juega». La liga es semanal: quien no
#: jugó ni la última jornada no es alguien de cuya forma haya que avisar. Con
#: 21 días seguía saliendo un veterano que jugó un amistoso once días antes.
DIAS_JUGANDO = 10


def _quienes_juegan(
    players: list[dict[str, Any]], lu: Any, entrenador_ht_id: int | None
) -> list[dict[str, Any]]:
    """Los jugadores de los que tiene sentido avisar por su forma.

    2026-09-13: la alerta salía para el entrenador y para veteranos con todas
    las habilidades a cero, que no van a jugar nunca. Queda quien está en el
    mejor once o jugó en los últimos `DIAS_JUGANDO` días --lo segundo
    recoge al titular que el optimizador saca justo POR su mala forma--, y
    nunca el entrenador.
    """
    en_el_once = {a.player["ht_player_id"] for a in lu.assignments} if lu is not None else set()
    limite = datetime.now(UTC) - timedelta(days=DIAS_JUGANDO)

    def jugo_hace_poco(p: dict[str, Any]) -> bool:
        cuando = p.get("last_match_played_at")
        if cuando is None:
            return False
        if cuando.tzinfo is None:
            cuando = cuando.replace(tzinfo=UTC)
        return bool(cuando >= limite)

    return [
        p
        for p in players
        if p["ht_player_id"] != entrenador_ht_id
        and (p["ht_player_id"] in en_el_once or jugo_hace_poco(p))
    ]


async def _derive_insights(session: AsyncSession, team_id: int) -> list[ins.Insight]:
    """Evalúa TODO el catálogo de reglas contra los datos ya sincronizados.

    Vive aparte del endpoint porque archivar una alerta también necesita
    derivarlas: el texto que se guarda en el buzón se toma de aquí, del
    servidor, y no de lo que mande el cliente.

    Devuelve sólo las que dependen de los DATOS. Las dos que dependen de la
    hora están en `_insights_del_reloj`, y quien quiera la lista entera llama
    a `_derive_todas`.
    """
    players, team = await roster(session, team_id)
    rate_ = team.currency_rate or 1.0
    currency = team.currency_name or ""

    econ_rows = list(
        (
            await session.execute(
                select(m.EconomySnapshot)
                .where(m.EconomySnapshot.team_id == team_id)
                .order_by(m.EconomySnapshot.captured_at.desc())
                .limit(2)
            )
        ).scalars()
    )
    econ = econ_rows[0] if econ_rows else None
    econ_prev = econ_rows[1] if len(econ_rows) > 1 else None

    # El balance sin transferencias sale de las semanas CERRADAS, igual que en
    # Economia y en el Panel. Leerlo de la semana en curso --que es lo que se
    # hacia hasta el 2026-08-30-- dejaba fuera la taquilla, que va en 0 hasta
    # que se juega el partido en casa, y los 20.000 semanales de la academia.
    # Esta alerta le dice al usuario cuantas semanas de caja le quedan: es el
    # ultimo sitio donde vale la pena ahorrarse una consulta.
    cierres_economicos = weekly_closes(
        list(
            (
                await session.execute(
                    select(m.EconomySnapshot)
                    .where(m.EconomySnapshot.team_id == team_id)
                    .order_by(m.EconomySnapshot.captured_at)
                )
            ).scalars()
        )
    )
    estructura = estructura_semanal(
        [
            c.snapshot
            for c in weekly_closes(
                list(
                    (
                        await session.execute(
                            select(m.EconomySnapshot)
                            .where(m.EconomySnapshot.team_id == team_id)
                            .order_by(m.EconomySnapshot.captured_at)
                        )
                    ).scalars()
                )
            )
        ],
        rate_,
    )

    tr = await session.scalar(
        select(m.TrainingSnapshot)
        .where(m.TrainingSnapshot.team_id == team_id)
        .order_by(m.TrainingSnapshot.captured_at.desc())
        .limit(1)
    )
    staff = await session.scalar(
        select(m.StaffSnapshot)
        .where(m.StaffSnapshot.team_id == team_id)
        .order_by(m.StaffSnapshot.captured_at.desc())
        .limit(1)
    )
    groups: list[list[ins.Insight]] = [
        ins.injuries(players),
        ins.ageing_squad(players),
    ]

    # ── Entrenamiento ───────────────────────────────────────────────────
    ctx = await TrainingContextService(session).get(team_id)
    trained_skill: str | None = None
    setup: TrainingSetup | None = None
    if tr:
        trained_skill = ctx.trained_skill if ctx else training_target(tr.training_type)
        if trained_skill:
            # El propio entrenador (identificado por TrainerID en training.xml,
            # no por heurísticas como TSI) no es una decisión de entrenamiento
            # de nadie: se excluye de las alertas de entrenamiento.
            # `tr` ya está confirmado no-None por el `if tr:` de arriba, el
            # supuesto debe leer su intensidad/condición reales, no caer en
            # 100/0 en silencio (bug real corregido 2026-08-14: antes las
            # ignoraba aunque ya las tenía).
            setup = (
                ctx.setup
                if ctx
                else default_training_setup(
                    trained_skill,
                    training_type=tr.training_type,
                    intensity=tr.training_level,
                    stamina_share=tr.stamina_part,
                )
            )
            trainees = [
                {
                    "name": p["name"],
                    "age_years": p["age_years"],
                    "weeks_to_pop": weeks_to_next_level(
                        trained_skill,
                        p["skills"].get(trained_skill, 0),
                        p["age_years"],
                        p["age_days"],
                        setup=setup,
                    ).weeks_to_next_level,
                }
                for p in players
                if p["ht_player_id"] != tr.trainer_ht_id
            ]
            groups.append(ins.inefficient_training(trainees))

    # ── Plantilla: posición natural, sueldo de mercado ──
    for p in players:
        p["best_position"] = rate_all(p)[0].position
    groups.append(ins.thin_keeper_depth(players))

    wage_players: list[dict[str, Any]] = []
    total_salary_local = 0
    for p in players:
        salary_local = int(round(p["salary"] / rate_))
        total_salary_local += salary_local
        wage_players.append(
            {
                "ht_player_id": p["ht_player_id"],
                "name": p["name"],
                "salary_local": salary_local,
            }
        )

    groups.append(ins.wage_concentration(wage_players, total_salary_local, currency))

    # ── Alineación óptima: titulares lesionados, aportadores por sector ──
    try:
        lu, _ = best_formation(players)
    except ValueError:
        lu = None
    # Aquí iba «X es tu principal aportador en …». Se retiró el 2026-09-13: no
    # pedía ninguna decisión, y ocupaba siete huecos del buzón cada semana.
    groups.append(ins.low_form(_quienes_juegan(players, lu, tr.trainer_ht_id if tr else None)))

    # ── Economía ────────────────────────────────────────────────────────
    if econ:
        # El MISMO número que enseña Economía en «Autonomía sin
        # transferencias», y por el mismo camino. Hasta el 2026-09-04 esta
        # alerta usaba `structural_balance`, que se calcula distinto --mezcla
        # tarifas de la semana en curso con la taquilla de las cerradas-- así
        # que las dos pantallas decían la misma frase con dos cifras: -27.195
        # y 345 semanas aquí, -39.860 y 236 allí. Con la ventana por defecto
        # el aviso sigue callado igual que antes, así que esto no cambia a
        # quién avisa hoy: unifica de dónde sale el número.
        autonomia = balances_de_autonomia(cierres_economicos, rate_, VENTANA_POR_DEFECTO)
        structural = autonomia.sin_transferencias if autonomia else None
        # La temporada-semana de la lectura económica entra en la alerta para
        # que sea una por semana: mismo filtro por `ht_league_id` que el resto
        # de la app, no "el WorldContext más reciente".
        econ_world = (
            await session.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None
            else None
        )
        # Sin ni un cierre guardado no hay balance semanal que juzgar, y una
        # alerta de «te quedan N semanas» calculada sobre nada es peor que no
        # avisar.
        if structural is not None:
            groups.append(
                ins.structural_deficit(
                    structural,
                    int(econ.cash / rate_),
                    currency,
                    season_week=season_week_for_datetime(econ_world, econ.captured_at),
                    # Lo que entra de forma recurrente, para poder juzgar si
                    # el déficit es grande o es el redondeo del equilibrio.
                    weekly_income=(
                        estructura.sponsors + estructura.gate_per_week if estructura else None
                    ),
                )
            )

        # SOBRE SEMANAS CERRADAS, no la semana en curso (2026-09-13). La
        # taquilla va en 0 hasta que se juega en casa, así que en una semana
        # sin partido de local salía «100 % de tus ingresos vienen de
        # patrocinadores», que es verdad ese martes y mentira como estructura.
        cerradas = [c.snapshot for c in cierres_economicos[-SEMANAS_DE_INGRESOS:]]
        if cerradas:
            income_items = [
                (
                    "Espectadores",
                    int(sum(s.last_income_spectators or 0 for s in cerradas) / rate_),
                ),
                (
                    "Patrocinadores",
                    int(sum(_closed_sponsor_income(s) or 0 for s in cerradas) / rate_),
                ),
                ("Financieros", int(sum(s.last_income_financial or 0 for s in cerradas) / rate_)),
                ("Temporales", int(sum(s.last_income_temporary or 0 for s in cerradas) / rate_)),
            ]
            groups.append(ins.income_concentration(income_items, currency, semanas=len(cerradas)))
        groups.append(
            ins.cash_vs_expected_mismatch(
                int(econ.cash / rate_), int(econ.expected_cash / rate_), currency
            )
        )

        if econ_prev:
            groups.append(ins.fan_club_trend(econ_prev.fan_club_size, econ.fan_club_size))

    # ── Liga ────────────────────────────────────────────────────────────
    # runs reducido frente al endpoint dedicado (10000): aquí solo hacen
    # falta umbrales gruesos (25-40%), no la precisión completa.
    #
    # EL MISMO MODELO QUE LA PANTALLA DE LIGA (2026-09-13). Sin las lecturas
    # esto corría la Poisson de la temporada a secas, y la alerta decía «59 %
    # de terminar campeón» mientras Liga enseñaba 88,4 % para el mismo equipo.
    # Import local: `league` ya importa `roster` de este módulo.
    #
    # Y EL MISMO CÁLCULO (2026-09-14): antes lo rehacía entero en cada visita
    # --simulaciones, lecturas y órdenes--, y era la petición más lenta del
    # Dashboard. Ahora comparte el de la pantalla de Liga.
    from app.api.v1.endpoints.league import liga_calculada

    league = await liga_calculada(session, team_id, 2000)
    if league and league.own_outlook:
        own = league.own_outlook
        own_dict = {
            "name": own.name,
            "expected_position": own.expected_position,
            "expected_points": own.expected_points,
            "relegation_probability": own.relegation_probability,
            "relegation_playoff_probability": own.relegation_playoff_probability,
            "promotion_probability": own.promotion_probability,
            "title_probability": own.title_probability,
            "attack_strength": own.attack_strength,
            "defence_strength": own.defence_strength,
        }
        groups += [
            ins.relegation_danger(own_dict),
            ins.relegation_playoff_risk(own_dict),
            ins.title_race(own_dict),
            ins.weak_attack(own_dict),
            ins.weak_defence(own_dict),
        ]
        if league.next_match:
            groups.append(ins.next_match_forecast(league.next_match))

    # ── Copa ────────────────────────────────────────────────────────────
    # ── Estadio ─────────────────────────────────────────────────────────
    arena = await ArenaQueryService(session).get(team_id)
    if arena:
        # Aquí iba la alerta de sectores agotados. Se retiró con el desglose
        # por sector (2026-09-01): era demanda censurada POR SECTOR y eso es
        # función de HT Supporter.
        options = [
            {
                "label": o.label,
                "netPerSeason": o.net_per_season,
                "paybackSeasons": o.payback_seasons,
            }
            for o in arena.expansion_options
        ]
        groups.append(ins.arena_expansion_opportunity(options, arena.currency))

    # ── Academia ────────────────────────────────────────────────────────
    academy = await AcademyQueryService(session).get(team_id)
    if academy:
        # NO SE JUZGA ANTES DE TIEMPO (2026-09-13). Mientras ningún canterano
        # pueda subir todavía, «no ha recuperado la inversión» es la única
        # respuesta posible y no pide ninguna decisión: el dinero va dentro y
        # nada puede haber vuelto. Salta cuando alguno ya puede subir, o si
        # la academia ya ingresó algo.
        alguno_puede_subir = academy.earned > 0 or any(
            y.can_be_promoted_in is not None and y.can_be_promoted_in <= 0 for y in academy.players
        )
        if alguno_puede_subir:
            groups.append(ins.academy_roi(academy.invested, academy.earned, academy.currency))
        youth_dicts = [
            {
                "ht_youth_player_id": y.ht_youth_player_id,
                "name": y.name,
                "days_until_deadline": y.days_until_deadline,
                "category": y.category,
                "best_skill": y.best_skill,
                "best_skill_max": y.best_skill_max,
                "verdict_is_provisional": y.verdict_is_provisional,
                "promote_advice": y.promote_advice,
            }
            for y in academy.players
        ]
        groups.append(ins.youth_deadline(youth_dicts))
        groups.append(ins.youth_star_prospect(youth_dicts))

    # ── Cuerpo técnico ──────────────────────────────────────────────────
    if staff:
        staff_dict = {
            "medic_levels": staff.medic_levels,
            "sport_psychologist_levels": staff.sport_psychologist_levels,
            "assistant_trainer_levels": staff.assistant_trainer_levels,
        }
        groups += [
            ins.missing_medic_or_psych(staff_dict),
            ins.assistant_trainers_below_reference(staff_dict),
        ]

    return ins.collect(*groups)


async def _insights_del_reloj(session: AsyncSession, team_id: int) -> list[ins.Insight]:
    """Las dos alertas que no dependen del sync sino de la hora que sea.

    El clima del próximo partido --que cambia de «hoy» a «mañana» sin que
    nadie sincronice-- y el aviso de datos viejos, que cuenta las horas desde
    la última sincronización.

    Viven aparte desde el 2026-10-03 por lo que costaban las otras. La lista
    entera se guardaba con un tope de QUINCE MINUTOS justamente por estas
    dos, así que cada cuarto de hora la siguiente visita al Panel volvía a
    derivarlo TODO: liga, academia, saldo de cada jugador, mejor once. Medido:
    siete segundos. Ahora lo caro se guarda por sync, como el resto de la
    aplicación, y esto --dos consultas pequeñas-- se calcula en cada
    petición.
    """
    team = await session.get(m.Team, team_id)
    if team is None:
        return []
    groups: list[list[ins.Insight]] = [await _next_match_weather_insights(session, team)]
    last_sync = await session.scalar(
        select(m.Sync)
        .where(m.Sync.team_id == team_id, m.Sync.status.in_(("completed", "partial")))
        .order_by(m.Sync.started_at.desc())
        .limit(1)
    )
    if last_sync:
        synced_at = last_sync.finished_at or last_sync.started_at
        ref = synced_at if synced_at.tzinfo else synced_at.replace(tzinfo=UTC)
        hours = (datetime.now(UTC) - ref).total_seconds() / 3600
        groups.append(ins.stale_data(hours))
    return ins.collect(*groups)


async def _insights_guardadas(session: AsyncSession, team_id: int) -> list[ins.Insight]:
    """Las alertas, calculadas una vez por sync (2026-09-14).

    Medido en producción: derivarlas tardaba 8 segundos en CADA visita al
    Dashboard, con los datos sin cambiar. Se guardan con el sync en la clave.
    Lo archivado en el buzón NO entra en la caché: se filtra después, en cada
    petición, así que archivar se ve al instante. La lista es compartida:
    quien la reciba no la modifica.

    2026-10-03: EL TOPE DE QUINCE MINUTOS SE FUE. Estaba por dos reglas que
    miran el reloj --el clima del próximo partido y los datos viejos-- y
    arrastraba a las otras treinta: cada cuarto de hora, la siguiente visita
    al Panel volvía a derivarlo todo, siete segundos medidos. Esas dos viven
    ahora en `_insights_del_reloj` y se calculan en cada petición, que son dos
    consultas pequeñas; lo caro se guarda con el sync, como el resto de la
    aplicación.
    """
    from app.api.cache_por_sync import por_sync

    de_datos: list[ins.Insight] = await por_sync(
        session,
        team_id,
        "alertas",
        (),
        lambda: _derive_insights(session, team_id),
    )
    return ins.collect(de_datos, await _insights_del_reloj(session, team_id))


def _fingerprint(insight: ins.Insight) -> str:
    """Identidad del CONTENIDO de una alerta, no de su regla.

    Dos alertas con la misma `key` pero distinto texto son, para el usuario,
    dos avisos distintos: "pierdes 300.000 por semana" y "pierdes 900.000 por
    semana" no se archivan con el mismo clic. Por eso la huella entra en el
    filtro del buzón, archivar es acusar recibo de un hecho concreto, no
    apagar la regla que lo detecta.
    """
    raw = "|".join(
        (
            insight.severity.value,
            insight.title,
            insight.detail,
            insight.action,
        )
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _serialize(insight: ins.Insight) -> dict[str, Any]:
    return {
        "key": insight.key,
        "severity": insight.severity.value,
        "title": insight.title,
        "detail": insight.detail,
        "action": insight.action,
        "module": insight.module,
        "evidence": insight.evidence,
    }


async def _dismissals(
    session: AsyncSession,
    team_id: int,
    live_keys: Collection[str],
) -> dict[str, m.DismissedInsight]:
    """Las archivadas de este equipo, sin las que ya no pueden volver.

    Se caen dos clases de fila, y las dos por lo mismo, nada las va a
    regenerar, así que enseñarlas sería prometer un aviso que no llega:

    - Las huérfanas. Una fila archivada sobrevive a su regla, de modo que al
      borrar una regla, o al cambiarle la clave, su archivada se queda suelta
      en la base.
    - Las de una semana pasada. Las claves de `WEEK_SCOPED_KEY_ROOTS` llevan la
      semana pegada; si esa clave exacta no está entre las que se derivan hoy,
      su semana ya pasó.

    `live_keys` son las claves derivadas ahora mismo, ANTES de descontar el
    buzón: una alerta archivada de la semana en curso sigue estando ahí, que es
    justo lo que la distingue de una caducada.
    """
    rows = (
        await session.execute(
            select(m.DismissedInsight)
            .where(m.DismissedInsight.team_id == team_id)
            .order_by(m.DismissedInsight.dismissed_at.desc())
        )
    ).scalars()
    return {
        row.key: row
        for row in rows
        if ins.is_known_key(row.key)
        and (ins.week_scoped_root(row.key) is None or row.key in live_keys)
    }


@router.get(
    "/teams/{team_id}/insights",
    summary="Alertas accionables (HL-130)",
    dependencies=[Depends(require_team_owner)],
)
async def team_insights(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Catálogo de reglas de negocio, evaluadas contra los datos reales ya
    sincronizados de este equipo, entrenamiento, plantilla, mercado,
    economía, liga, copa, estadio, academia y cuerpo técnico.

    Es un motor de reglas, no un modelo de IA: cada función de
    `domain.engines.insights` es una condición explícita y auditable sobre
    datos reales (algunas, jugador a jugador). Solo se muestran las que
    disparan de verdad con el estado actual, el catálogo completo es mucho
    más grande que la lista de abajo, que es la intersección con tu equipo
    hoy.

    Las archivadas en el buzón se descuelgan de aquí mientras su contenido no
    cambie; si cambia, vuelven.
    """
    live = await _insights_guardadas(session, team_id)
    archived = await _dismissals(session, team_id, [i.key for i in live])
    return [
        _serialize(i)
        for i in live
        if not (i.key in archived and archived[i.key].fingerprint == _fingerprint(i))
    ]


@router.get(
    "/teams/{team_id}/insights/archived",
    summary="Buzón de alertas archivadas",
    dependencies=[Depends(require_team_owner)],
)
async def team_insights_archived(
    team_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Lo que el usuario archivó, más reciente primero.

    Guarda el texto tal como estaba al archivarlo, así que sigue siendo
    legible aunque la condición ya no se cumpla, y `stillActive` dice
    justamente eso: si la alerta se sigue generando hoy, idéntica.
    """
    live = {i.key: _fingerprint(i) for i in await _insights_guardadas(session, team_id)}
    archived = await _dismissals(session, team_id, live)
    if not archived:
        return []
    return [
        {
            "key": row.key,
            "severity": row.severity,
            "title": row.title,
            "detail": row.detail,
            "action": row.action,
            "module": row.module,
            "evidence": {},
            "dismissedAt": row.dismissed_at.isoformat(),
            "stillActive": live.get(row.key) == row.fingerprint,
        }
        for row in archived.values()
    ]


@router.post(
    "/teams/{team_id}/insights/{key}/archive",
    summary="Archivar una alerta",
    dependencies=[Depends(require_team_owner)],
)
async def archive_insight(
    team_id: int,
    key: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Manda una alerta al buzón. El texto archivado se toma de la alerta
    recién derivada en el servidor, no del cliente."""
    match = next((i for i in await _insights_guardadas(session, team_id) if i.key == key), None)
    if match is None:
        raise HTTPException(status_code=404, detail=f"La alerta '{key}' ya no está activa")

    # Si esta alerta lleva la semana en la clave, las de semanas anteriores ya
    # no valen para nada: su semana no vuelve. Se borran de la base al archivar
    # la nueva, que si no el buzón acumularía una fila por semana durante toda
    # la temporada.
    root = ins.week_scoped_root(key)
    if root is not None:
        for vieja in (
            (
                await session.execute(
                    select(m.DismissedInsight).where(
                        m.DismissedInsight.team_id == team_id,
                        m.DismissedInsight.key != key,
                        or_(
                            m.DismissedInsight.key == root,
                            m.DismissedInsight.key.startswith(f"{root}."),
                        ),
                    )
                )
            )
            .scalars()
            .all()
        ):
            await session.delete(vieja)

    row = await session.scalar(
        select(m.DismissedInsight).where(
            m.DismissedInsight.team_id == team_id, m.DismissedInsight.key == key
        )
    )
    if row is None:
        row = m.DismissedInsight(team_id=team_id, key=key)
        session.add(row)
    row.fingerprint = _fingerprint(match)
    row.severity = match.severity.value
    row.title = match.title
    row.detail = match.detail
    row.action = match.action
    row.module = match.module
    row.dismissed_at = datetime.now(UTC)
    await session.commit()
    return {"key": key, "archived": True}


@router.delete(
    "/teams/{team_id}/insights/{key}/archive",
    summary="Sacar del buzón",
    dependencies=[Depends(require_team_owner)],
)
async def restore_insight(
    team_id: int,
    key: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Devuelve la alerta a la lista activa, si la condición sigue viva.
    Si ya no se cumple, simplemente desaparece del buzón."""
    row = await session.scalar(
        select(m.DismissedInsight).where(
            m.DismissedInsight.team_id == team_id, m.DismissedInsight.key == key
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"La alerta '{key}' no está archivada")
    await session.delete(row)
    await session.commit()
    return {"key": key, "archived": False}
