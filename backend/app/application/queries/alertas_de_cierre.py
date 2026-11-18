"""Los datos de las alertas de cierre (2026-11-18): lee lo que ya hay en la base
y se lo pasa a las reglas puras de `alertas_de_grupo` y `alertas_de_plantilla`.

No llama a Hattrick: todo sale de lo sincronizado. Va dentro de la caché por
sincronización de las alertas, así que se calcula una vez por sync.
"""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.academy import AcademyQueryService
from app.application.queries.cambios_de_clase import cambios_de_clase
from app.application.queries.clases_de_jugador import ClasesDeJugadorQueryService
from app.application.queries.player_balance import PlayerBalanceQueryService
from app.application.queries.precio_comparable import precios_de_la_plantilla
from app.application.queries.team_overview import TeamOverviewQueryService
from app.domain.engines import alertas_de_grupo as ag
from app.domain.engines import alertas_de_plantilla as ap
from app.domain.engines.insights import Insight
from app.domain.engines.position_engine import habilidades_que_pesan, rate_all
from app.domain.engines.previous_club_bonus import previous_club_bonus_pct
from app.domain.engines.training_engine import TrainingSetup, weeks_to_next_level
from app.domain.value_objects.ht_constants import SKILL_LABELS, is_competitive_match_type
from app.domain.value_objects.stamina_reference import stamina_forecast_level
from app.infrastructure.db import models as m

HABILIDADES = tuple(SKILL_LABELS)
_PREFIJO_DE_ETAPA = {
    "promesa": "Promesa",
    "pico": "En su pico",
    "rotacion": "Pieza de rotación",
    "veterano": "Veterano estable",
    "declive": "En declive",
}
_TITULARIDAD = {"titular": "Titular", "suplencia": "Suplencia", "reserva": "Reserva"}
_RENTABILIDAD = {
    "estrellas": "Estrellas",
    "gangas": "Gangas",
    "caros": "Caros",
    "economicos": "Económicos",
}


def _naive(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=None) if d is not None and d.tzinfo else d


async def _historial(
    session: AsyncSession, team_id: int, ht_ids: set[int]
) -> dict[int, list[tuple[int, datetime, dict[str, int]]]]:
    """Cada foto de cada jugador de hoy: (sync, cuándo, habilidades)."""
    filas = (
        await session.execute(
            select(
                m.Player.ht_player_id,
                m.PlayerSnapshot.sync_id,
                m.PlayerSnapshot.captured_at,
                *(getattr(m.PlayerSnapshot, s) for s in HABILIDADES),
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id, m.Player.ht_player_id.in_(ht_ids))
            .order_by(m.PlayerSnapshot.captured_at, m.PlayerSnapshot.id)
        )
    ).all()
    out: dict[int, list[tuple[int, datetime, dict[str, int]]]] = defaultdict(list)
    for f in filas:
        out[f[0]].append(
            (f[1], f[2], {s: int(v or 0) for s, v in zip(HABILIDADES, f[3:], strict=True)})
        )
    return out


def _ultima_subida(
    fotos: list[tuple[int, datetime, dict[str, int]]], skill: str
) -> datetime | None:
    for previa, actual in reversed(list(zip(fotos, fotos[1:], strict=False))):
        if actual[2][skill] > previa[2][skill]:
            return actual[1]
    return None


async def alertas_de_cierre(
    session: AsyncSession,
    team_id: int,
    players: list[dict[str, Any]],
    trained_skill: str | None,
    setup: TrainingSetup | None,
) -> list[list[Insight]]:
    """Las 22 alertas de cierre que dependen de los datos. La de la reventa
    mira el reloj y va con las del reloj: `comision_a_la_vista_de`."""
    clases = await ClasesDeJugadorQueryService(session).get(team_id)
    por_id = {p["ht_player_id"]: p for p in players}
    activos = [j for j in clases.players if j.ht_player_id in por_id]
    fotos = await _historial(session, team_id, {j.ht_player_id for j in activos})
    ultimo_sync = max((f[-1][0] for f in fotos.values() if f), default=None)
    ahora = datetime.now(UTC).replace(tzinfo=None)

    jugadores: list[ag.JugadorDelSync] = []
    for j in activos:
        p = por_id[j.ht_player_id]
        historia = fotos.get(j.ht_player_id, [])
        cambio_en_el_ultimo = bool(historia) and historia[-1][0] == ultimo_sync
        antes = historia[-2][2] if cambio_en_el_ultimo and len(historia) > 1 else None
        puesto = rate_all(p)[0].position
        jugadores.append(
            ag.JugadorDelSync(
                ht_player_id=j.ht_player_id,
                name=j.name,
                titularidad=j.titularidad,
                rentabilidad=j.rentabilidad,
                etapa=j.etapa.stage,
                puesto=puesto,
                pesan=habilidades_que_pesan(puesto),
                hoy={s: int(p["skills"].get(s, 0) or 0) for s in HABILIDADES},
                antes=antes,
                bajadas_totales=j.etapa.falling,
                grupos_propios=dict(j.group_ids),
            )
        )

    cambios = await cambios_de_clase(session, team_id)
    de_titular_a_suplencia = {
        c.ht_player_id
        for c in cambios.changes
        if c.clasificacion == "titularidad" and c.antes == "titular" and c.ahora == "suplencia"
    }
    de_rotacion_a_pico = {
        c.ht_player_id
        for c in cambios.changes
        if c.clasificacion == "etapa" and c.antes == "rotacion" and c.ahora == "pico"
    }

    # Estancadas: la semana prevista de la subida ya pasó y no subió.
    atrasos: list[ag.Atraso] = []
    if trained_skill in SKILL_LABELS:
        for j in activos:
            p = por_id[j.ht_player_id]
            if j.etapa.stage != "promesa" and j.titularidad != "titular":
                continue
            # Sólo a quien ese entrenamiento le llega por su puesto: a un
            # portero no se le puede reclamar que no suba Pases (visto en
            # seco con los datos del usuario, 2026-11-18).
            if trained_skill not in habilidades_que_pesan(rate_all(p)[0].position):
                continue
            subida = _ultima_subida(fotos.get(j.ht_player_id, []), trained_skill)
            if subida is None:
                continue
            nivel = int(p["skills"].get(trained_skill, 0) or 0)
            prevision = weeks_to_next_level(
                trained_skill, nivel, p["age_years"], p["age_days"], setup=setup
            ).weeks_to_next_level
            semanas = (ahora - _naive(subida)).days // 7  # type: ignore[operator]
            if prevision is not None and prevision > 0 and semanas > prevision:
                atrasos.append(
                    ag.Atraso(
                        ht_player_id=j.ht_player_id,
                        name=j.name,
                        titularidad=j.titularidad,
                        etapa=j.etapa.stage,
                        skill=trained_skill,
                        semanas_desde_la_subida=semanas,
                        semanas_previstas=prevision,
                    )
                )

    # «El grupo cae»: las medias semanales de cada grupo de la app.
    grupos_de_la_app: dict[str, tuple[str, set[int]]] = {}
    for j in activos:
        for clave, nombre in (
            (f"titularidad-{j.titularidad}", _TITULARIDAD.get(j.titularidad)),
            (f"rentabilidad-{j.rentabilidad}", _RENTABILIDAD.get(j.rentabilidad)),
            (f"etapa-{j.etapa.stage}", _PREFIJO_DE_ETAPA.get(j.etapa.stage)),
        ):
            if nombre:
                grupos_de_la_app.setdefault(clave, (nombre, set()))[1].add(j.ht_player_id)
    resumen = TeamOverviewQueryService(session)
    series: list[ag.SerieDeGrupo] = []
    for clave, (nombre, ids) in grupos_de_la_app.items():
        serie = await resumen.serie_de_un_grupo(team_id, frozenset(ids))
        for s in HABILIDADES:
            series.append(
                ag.SerieDeGrupo(
                    grupo=nombre,
                    clave_del_grupo=clave,
                    skill=s,
                    valores=serie.fields.get(s, []),
                    conteos=serie.counts,
                )
            )

    propios = [
        ag.GrupoPropio(id=g.id, nombre=g.name, clasificacion_id=c.id, clasificacion=c.name)
        for c in clases.classifications
        for g in c.groups
    ]

    grupos: list[list[Insight]] = [
        ag.titular_con_bajada(jugadores),
        ag.la_bajada_le_saca_del_once(jugadores, de_titular_a_suplencia),
        ag.suplente_que_empuja(jugadores),
        ag.reserva_que_despierta(jugadores),
        ag.promesa_estancada(atrasos),
        ag.promesa_que_sube(jugadores),
        ag.rotacion_que_asoma(jugadores, de_rotacion_a_pico),
        ag.primer_aviso_de_declive(jugadores),
        ag.declive_acelerado(jugadores),
        ag.estrella_que_cae(jugadores),
        ag.caro_que_sigue_bajando(jugadores),
        ag.ganga_que_se_revaloriza(jugadores),
        ag.el_grupo_cae(series),
        ag.entrenamiento_que_no_llega_al_once(atrasos),
        ag.tu_grupo_se_movio(jugadores, propios),
    ]

    # ── Generales ──────────────────────────────────────────────────────
    if setup is not None:
        grupos.append(
            ap.resistencia_baja_para_su_edad(
                [
                    ap.Resistencia(
                        ht_player_id=p["ht_player_id"],
                        name=p["name"],
                        nivel=int(p.get("stamina") or 0),
                        esperado=stamina_forecast_level(
                            p["age_years"], setup.effective_stamina_intensity
                        ),
                    )
                    for p in players
                ]
            )
        )

    titulares = [
        ap.Titular(
            ht_player_id=j.ht_player_id,
            name=j.name,
            en_venta=bool(por_id[j.ht_player_id].get("is_transfer_listed")),
            experiencia=int(por_id[j.ht_player_id].get("experience") or 0),
            ultimo_partido=_naive(por_id[j.ht_player_id].get("last_match_played_at")),
        )
        for j in activos
        if j.titularidad == "titular"
    ]
    grupos.append(ap.titular_en_venta(titulares))
    grupos.append(ap.titular_sin_experiencia(titulares))

    equipo = await session.get(m.Team, team_id)
    if equipo is not None:
        oficiales = [
            _naive(mt.played_at)
            for mt in (
                await session.execute(
                    select(m.Match)
                    .where(
                        (m.Match.home_team_ht_id == equipo.ht_team_id)
                        | (m.Match.away_team_ht_id == equipo.ht_team_id),
                        m.Match.played_at <= datetime.now(UTC),
                        m.Match.home_goals >= 0,
                    )
                    .order_by(m.Match.played_at.desc())
                    .limit(20)
                )
            ).scalars()
            if is_competitive_match_type(mt.match_type)
        ]
        grupos.append(ap.titular_que_no_juega(titulares, [d for d in oficiales if d is not None]))

    grupos.append(await _venta_con_ganancia(session, team_id))
    grupos.append(await _precio_que_sube(session, team_id, por_id))
    grupos.append(await _juveniles_listos(session, team_id))
    return grupos


async def _venta_con_ganancia(session: AsyncSession, team_id: int) -> list[Insight]:
    balance = await PlayerBalanceQueryService(session).get(team_id)
    if balance is None:
        return []
    precios = await precios_de_la_plantilla(session, team_id)
    media = {p.ht_player_id: p.media for p in precios.jugadores}
    ventas = [
        ap.Venta(
            ht_player_id=r.ht_player_id,
            name=r.name,
            precio=media.get(r.ht_player_id),
            gastos=float(r.gastos),
            comision_de_la_casa=r.agent_pct_if_sold_now,
            comision_de_reventa=float(r.resale_bonus_share or 0),
        )
        for r in balance.players
        if r.agent_pct_if_sold_now is not None and r.ht_player_id in media
    ]
    return ap.venta_con_ganancia(ventas, precios.moneda)


async def _precio_que_sube(
    session: AsyncSession, team_id: int, por_id: dict[int, dict[str, Any]]
) -> list[Insight]:
    filas = (
        (
            await session.execute(
                select(m.MarketEstimate)
                .where(
                    m.MarketEstimate.team_id == team_id,
                    m.MarketEstimate.mean_price.is_not(None),
                    m.MarketEstimate.ht_player_id.in_(set(por_id)),
                )
                .order_by(m.MarketEstimate.captured_at)
            )
        )
        .scalars()
        .all()
    )
    por_jugador: dict[int, list[m.MarketEstimate]] = defaultdict(list)
    for f in filas:
        por_jugador[f.ht_player_id].append(f)
    precios = []
    for pid, lecturas in por_jugador.items():
        ultima = lecturas[-1]
        tope = _naive(ultima.captured_at) - timedelta(days=7)  # type: ignore[operator]
        antes = [x for x in lecturas if _naive(x.captured_at) <= tope]  # type: ignore[operator]
        if antes and antes[-1].mean_price and ultima.mean_price:
            precios.append(
                ap.PrecioSemanal(
                    ht_player_id=pid,
                    name=por_id[pid]["name"],
                    antes=int(antes[-1].mean_price),
                    ahora=int(ultima.mean_price),
                )
            )
    return ap.precio_que_sube(precios)


async def _juveniles_listos(session: AsyncSession, team_id: int) -> list[Insight]:
    academia = await AcademyQueryService(session).get(team_id)
    if not academia:
        return []
    llegadas = {
        y.ht_youth_player_id: y.arrived_at
        for y in (
            await session.execute(
                select(m.YouthPlayer).where(
                    m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None)
                )
            )
        ).scalars()
    }
    ahora = datetime.now(UTC).replace(tzinfo=None)
    juveniles = []
    for y in academia.players:
        llego = _naive(llegadas.get(y.ht_youth_player_id))
        juveniles.append(
            ap.Juvenil(
                ht_youth_player_id=y.ht_youth_player_id,
                name=y.name,
                age_years=y.age_years,
                age_days=y.age_days,
                dias_en_la_academia=(ahora - llego).days if llego else None,
            )
        )
    return ap.juvenil_listo_para_subir(juveniles)


async def comision_a_la_vista_de(session: AsyncSession, team_id: int) -> list[Insight]:
    """B5, con las del reloj: la subasta cierra a una hora, y pasada esa hora
    la alerta tiene que irse aunque no haya sincronización nueva."""
    ahora = datetime.now(UTC).replace(tzinfo=None)
    filas = (
        (
            await session.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id, m.Player.resale_deadline.is_not(None)
                )
            )
        )
        .scalars()
        .all()
    )
    return ap.comision_a_la_vista(
        [
            ap.Reventa(
                ht_player_id=p.ht_player_id,
                name=f"{p.first_name} {p.last_name}",
                cierra=_naive(p.resale_deadline),  # type: ignore[arg-type]
                porcentaje=(
                    previous_club_bonus_pct(p.games_played_for_us)
                    if p.games_played_for_us is not None
                    else None
                ),
            )
            for p in filas
        ],
        ahora,
    )
