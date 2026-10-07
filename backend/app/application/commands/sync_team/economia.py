"""Finanzas, moneda y desglose de taquilla.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    ProgressReporter,
    SyncResult,
    _log,
    _report,
)
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_constants import MATCH_TYPE_CUP


class EconomiaMixin(BaseDeSync):
    """Finanzas, moneda y desglose de taquilla."""

    async def _completar_desglose_de_taquilla(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """El publico de cada partido DE COPA, en casa y fuera.

        2026-09-28. De ahi sale la taquilla exacta: entradas de cada sector por
        su precio. En Copa el reparto es 67/33 entre local y visitante, asi que
        un partido fuera tambien deja dinero --el 33 %-- y para calcularlo hace
        falta el publico de ESE estadio, que el detalle del partido trae igual.

        Solo COPA, que es la unica pantalla que usa este dato: pedirlo para los
        de liga seria gastar llamadas en algo que nadie mira.

        Las filas de fuera se marcan con `own_venue=False`. No son historial de
        tu estadio y la pantalla de Estadio las descarta: contarlas falsearia
        la ocupacion, que se mide contra TU aforo.
        """
        from sqlalchemy import or_, select

        from app.infrastructure.db import models as m

        # Los partidos de Copa del club a los que les falta el publico por
        # sector: o no tienen fila de estadio, o la tienen sin desglose.
        pendientes = (
            (
                await uow.session.execute(
                    select(m.Match, m.StadiumHistory)
                    .outerjoin(
                        m.StadiumHistory,
                        m.StadiumHistory.ht_match_id == m.Match.ht_match_id,
                    )
                    .where(
                        or_(
                            m.Match.home_team_ht_id == ht_team_id,
                            m.Match.away_team_ht_id == ht_team_id,
                        ),
                        m.Match.match_type == MATCH_TYPE_CUP,
                        m.Match.status.ilike("finished"),
                        or_(
                            m.StadiumHistory.id.is_(None),
                            m.StadiumHistory.sold_terraces.is_(None),
                        ),
                    )
                    .order_by(m.Match.played_at.desc())
                    .limit(self.DESGLOSES_POR_SYNC)
                )
            )
            .unique()
            .all()
        )
        if not pendientes:
            return

        for partido, foto in pendientes:
            await _report(
                on_progress,
                f"Completando la taquilla del partido {partido.ht_match_id}...",
            )
            try:
                payload = await self._chpp.fetch(
                    "matchdetails",
                    version=FILE_VERSIONS["matchdetails"],
                    matchID=partido.ht_match_id,
                )
            except Exception as exc:  # noqa: BLE001, un partido no tumba el sync
                result.errors.append(f"taquilla del partido {partido.ht_match_id}: {exc}")
                continue
            arena = payload.get("arena") or {}
            # Los cuatro o ninguno: con tres sectores no sale una taquilla,
            # sale un numero mas bajo que parece uno bueno.
            sectores = {
                columna: arena.get(columna)
                for columna in ("sold_terraces", "sold_basic", "sold_roof", "sold_vip")
            }
            if any(v is None for v in sectores.values()):
                continue
            en_casa = partido.home_team_ht_id == ht_team_id
            if foto is None:
                foto = m.StadiumHistory(
                    team_id=team_id,
                    ht_match_id=partido.ht_match_id,
                    played_at=partido.played_at,
                    match_type=partido.match_type,
                    capacity_total=0,
                    sold_total=int(arena.get("spectators") or 0),
                )
                uow.session.add(foto)
            foto.own_venue = en_casa
            for columna, valor in sectores.items():
                setattr(foto, columna, valor)
            result.snapshots_written += 1

    async def _resolver_moneda(self, uow: UnitOfWork, team_id: int) -> None:
        """Deja el equipo con la moneda de su pais, sea cual sea.

        Se hacia solo dentro del paso de `worlddetails`, y solo si el id de
        liga del equipo coincidia con el de la fila que se estaba escribiendo.
        Con eso, tres casos reales se quedaban sin moneda y ensenaban las
        cifras en la moneda base de Hattrick, sin simbolo y multiplicadas por
        la tasa que no era:

        - equipos cuyo `ht_league_id` todavia no se habia rellenado;
        - Hattrick Femme, que es una liga internacional y en `worlddetails`
          no trae pais ni moneda propia: en Hattrick esos equipos manejan la
          moneda del pais de su manager;
        - cualquier equipo cuyo id de liga llegara despues de ese paso.

        Por eso se resuelve al final de cada sync y por tres vias, de la mas
        fiable a la menos.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        if equipo is None:
            return

        async def _contexto(condicion: Any) -> m.WorldContext | None:
            ctx: m.WorldContext | None = await uow.session.scalar(
                select(m.WorldContext).where(condicion)
            )
            return ctx

        candidatos: list[m.WorldContext | None] = []
        if equipo.ht_league_id is not None:
            candidatos.append(await _contexto(m.WorldContext.ht_league_id == equipo.ht_league_id))
        if equipo.league_name:
            candidatos.append(await _contexto(m.WorldContext.league_name == equipo.league_name))
        for fila in candidatos:
            if fila is not None and fila.currency_name:
                equipo.currency_name = fila.currency_name
                equipo.currency_rate = fila.currency_rate or 1.0
                return

        # Ligas internacionales (Hattrick Femme y compañia): no tienen moneda
        # propia, asi que se toma la del PRIMER equipo del manager --su club
        # principal-- que es la de su pais y la que Hattrick le ensena.
        #
        # EL PRIMERO, Y NO «EL PRIMERO QUE SALGA» (2026-09-28, decision del
        # usuario). Hasta hoy esto era un `limit(1)` sin ordenar: con un solo
        # club hermano acertaba de casualidad, y con dos en paises distintos el
        # que saliera dependia del orden de la tabla, asi que el mismo club
        # podia cambiar de moneda entre sincronizaciones. De ahi salen los
        # «×10» que reporto un usuario: entre un pais de tasa 10 y otro de
        # tasa 1 la diferencia es exactamente esa.
        #
        # QUIEN ES EL PRINCIPAL LO DICE HATTRICK (`is_primary_club`), y se
        # sabe desde que se conecta la cuenta: el alta recorre todos los clubes
        # del manager de una vez.
        #
        # Detras van la FECHA DE FUNDACION y el id, para los clubes dados de
        # alta antes de que se guardara ese dato. Ordenar solo por fecha no
        # basta, y ese fue el fallo que señalo la revision de la PR #6: al
        # conectar la cuenta los clubes nacen SIN fecha y solo se rellena al
        # sincronizar cada uno, asi que un secundario ya sincronizado le ganaba
        # al principal por tener fecha cuando el principal no la tenia.
        if equipo.owner_user_id is not None:
            primero = await uow.session.scalar(
                select(m.Team)
                .where(
                    m.Team.owner_user_id == equipo.owner_user_id,
                    m.Team.id != equipo.id,
                    # Nunca copiar un vacio: dejaria al club sin moneda igual,
                    # pero habiendo gastado la ultima via que le quedaba.
                    m.Team.currency_name != "",
                    m.Team.currency_name.is_not(None),
                )
                # El que Hattrick marca como principal, primero; los que no se
                # sabe, antes que los marcados como NO principales. La regla
                # vive en `models` porque la comparte con el pais del mapa de
                # Uso, y escrita dos veces se arreglo una sola (PR #7).
                .order_by(*m.orden_del_club_principal())
                .limit(1)
            )
            if primero is not None:
                equipo.currency_name = primero.currency_name
                equipo.currency_rate = primero.currency_rate or 1.0
                # Dicho, para que un «×10» reportado no haya que adivinarlo.
                _log.info(
                    "moneda de %s copiada del club %s (%s, tasa %s)",
                    equipo.ht_team_id,
                    primero.ht_team_id,
                    primero.currency_name,
                    primero.currency_rate,
                )
