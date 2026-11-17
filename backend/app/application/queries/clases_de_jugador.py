"""Clases de Jugador: las cuatro formas de partir la plantilla, juntas.

Las reglas están en `domain/engines/clases_de_jugador.py`; aquí sólo se
reúnen los datos que piden: la última foto de cada jugador, la experiencia
del equipo en cada formación, la etapa de carrera de cada uno (la misma de su
ficha) y los grupos que el usuario creó a mano.

No va en la caché por sincronización del Resumen: la etapa confirmada a mano
y los grupos propios cambian sin sincronizar, y se verían viejos.
"""

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_history import PlayerHistoryQueryService
from app.application.queries.squad import SKILL_COLS, SquadQueryService, jugador_para_el_motor
from app.domain.engines import htms as htms_motor
from app.domain.engines.career_stage_engine import (
    classify_career_stage,
    tendencia_de_habilidades,
)
from app.domain.engines.clases_de_jugador import (
    TITULAR,
    CorteDeRentabilidad,
    Once,
    partir_etapas,
    rentabilidad,
    repartir,
)
from app.infrastructure.db import models as m


@dataclass(frozen=True)
class EtapaDelJugador:
    #: La que manda: la confirmada a mano en la ficha o, si no hay, la sugerida.
    stage: str
    confirmed: bool
    percentile: float | None
    rising: int
    falling: int
    has_sufficient_history: bool
    #: «titular» o «suplente» si su etapa se partió; None si no.
    lado: str | None


@dataclass(frozen=True)
class JugadorDeClases:
    ht_player_id: int
    name: str
    #: El apellido, para rotular puntos y casillas sin que se pisen.
    short_name: str
    age_years: int
    age_days: int
    htms: int
    htms28: int
    #: Sueldo semanal en la moneda del equipo.
    salary: int
    titularidad: str
    rentabilidad: str
    etapa: EtapaDelJugador
    group_id: int | None


@dataclass(frozen=True)
class GrupoPropio:
    id: int
    name: str
    color: str


@dataclass(frozen=True)
class ClasesDeJugador:
    formations: tuple[str, ...]
    #: Experiencia del equipo en cada una de `formations`, de 0 a 10.
    experience: dict[str, int]
    onces_titular: tuple[Once, ...]
    onces_suplencia: tuple[Once, ...]
    corte: CorteDeRentabilidad | None
    #: La moneda en que va `salary` («US$», «€»…).
    currency: str
    players: tuple[JugadorDeClases, ...]
    groups: tuple[GrupoPropio, ...]


async def grupos_del_equipo(session: AsyncSession, team_id: int) -> list[m.PlayerGroup]:
    return list(
        (
            await session.execute(
                select(m.PlayerGroup)
                .where(m.PlayerGroup.team_id == team_id)
                .order_by(m.PlayerGroup.id)
            )
        )
        .scalars()
        .all()
    )


class ClasesDeJugadorQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _experiencia(self, team_id: int) -> dict[str, int]:
        lectura = (
            await self._s.execute(
                select(m.TrainingSnapshot.formation_xp_json)
                .where(m.TrainingSnapshot.team_id == team_id)
                .where(m.TrainingSnapshot.formation_xp_json.is_not(None))
                .order_by(m.TrainingSnapshot.captured_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        crudo = json.loads(lectura) if lectura else {}
        return {str(k): int(v) for k, v in crudo.items()}

    async def get(self, team_id: int) -> ClasesDeJugador:
        equipo = await self._s.get(m.Team, team_id)
        tasa = (equipo.currency_rate if equipo else None) or 1.0
        moneda = (equipo.currency_name if equipo else None) or ""
        filas = await SquadQueryService(self._s)._latest(team_id)
        experiencia = await self._experiencia(team_id)
        reparto = repartir(
            [jugador_para_el_motor(snap, ident) for snap, ident in filas], experiencia
        )

        valores = {}
        sueldos: dict[int, int] = {}
        for snap, ident in filas:
            h = htms_motor.de_habilidades(
                snap.age_years, snap.age_days, **{c: getattr(snap, c) or 0 for c in SKILL_COLS}
            )
            valores[ident.ht_player_id] = (h.ability, h.potential)
            sueldos[ident.ht_player_id] = int(round((snap.salary or 0) / tasa))
        # En la moneda del equipo, la misma que lee la pantalla: así la
        # mediana que se ve es exactamente la que corta.
        corte = rentabilidad({pid: (valores[pid][1], sueldos[pid]) for pid in valores})

        # LA ETAPA, IGUAL QUE EN LA FICHA: historial real, percentil en la
        # plantilla y, si el usuario la confirmó a mano, la suya.
        historia = PlayerHistoryQueryService(self._s)
        percentiles = await historia.dominant_skill_percentiles(team_id)
        crudas: dict[int, tuple[str, bool, float | None, int, int, bool]] = {}
        for snap, ident in filas:
            pid = ident.ht_player_id
            historial = await historia.snapshot_history(pid)
            tendencia = tendencia_de_habilidades([s.skills for s in historial], SKILL_COLS)
            pct = percentiles.get(pid)
            percentil = pct["percentile"] if pct else None
            sugerida = classify_career_stage(
                age_years=snap.age_years,
                age_days=snap.age_days,
                skills_rising=tendencia.rising,
                skills_falling=tendencia.falling,
                skills_stable=tendencia.stable,
                has_sufficient_history=tendencia.has_sufficient_history,
                squad_percentile=percentil,
                leadership=snap.leadership or 0,
                loyalty=snap.loyalty or 0,
            ).stage
            confirmada = ident.confirmed_career_stage
            crudas[pid] = (
                confirmada or sugerida,
                confirmada is not None,
                percentil,
                tendencia.rising,
                tendencia.falling,
                tendencia.has_sufficient_history,
            )
        titulares = {pid for pid, t in reparto.titularidad.items() if t == TITULAR}
        lados = partir_etapas({pid: c[0] for pid, c in crudas.items()}, titulares)

        grupos = await grupos_del_equipo(self._s, team_id)
        existentes = {g.id for g in grupos}

        jugadores = []
        for snap, ident in filas:
            pid = ident.ht_player_id
            stage, confirmada_, percentil, subir, bajar, suficiente = crudas[pid]
            jugadores.append(
                JugadorDeClases(
                    ht_player_id=pid,
                    name=f"{ident.first_name} {ident.last_name}",
                    short_name=ident.last_name or ident.first_name,
                    age_years=snap.age_years,
                    age_days=snap.age_days,
                    htms=valores[pid][0],
                    htms28=valores[pid][1],
                    salary=sueldos[pid],
                    titularidad=reparto.titularidad[pid],
                    rentabilidad=corte.grupos[pid] if corte else "",
                    etapa=EtapaDelJugador(
                        stage=stage,
                        confirmed=confirmada_,
                        percentile=percentil,
                        rising=subir,
                        falling=bajar,
                        has_sufficient_history=suficiente,
                        lado=lados.get(pid),
                    ),
                    # Un grupo borrado deja de contar aunque quede la marca.
                    group_id=(
                        ident.player_group_id if ident.player_group_id in existentes else None
                    ),
                )
            )

        return ClasesDeJugador(
            formations=reparto.formations,
            experience={
                f: next((v for k, v in experiencia.items() if "-".join(k) == f or k == f), 0)
                for f in reparto.formations
            },
            onces_titular=reparto.onces_titular,
            onces_suplencia=reparto.onces_suplencia,
            corte=corte,
            currency=moneda,
            players=tuple(jugadores),
            groups=tuple(GrupoPropio(id=g.id, name=g.name, color=g.color) for g in grupos),
        )
