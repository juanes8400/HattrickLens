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
        """Deja el equipo con LA MONEDA DEL MANAGER, no con la de su pais.

        2026-10-25, reporte de un usuario: «I have multiple clubs, but in HT I
        see all money amounts in my home currency C$. In HT Lens however, when
        I look at my other clubs, the amounts are displayed in those countries'
        currency (e.g., Maccabi Oradea shows in NIS)».

        Tiene razon y es un error de DATO, no de presentacion: Hattrick le
        ensena a cada manager todo su dinero en la moneda de su pais, sea cual
        sea el club que mire. Enseñar cada club en la suya no es otra forma de
        decir lo mismo --las cifras dejan de poder compararse entre clubes, y
        no cuadran con las que el juego le enseña al lado--.

        Asi que el orden se invirtio: manda la moneda del CLUB PRINCIPAL, y la
        del pais del propio club queda de respaldo para cuando aun no se sabe
        cual es el principal. Antes era al reves.

        Y CUANDO SE SINCRONIZA EL PRINCIPAL SE ESTAMPAN LOS HERMANOS. Sin eso,
        arreglar la moneda de un club secundario exigiria sincronizar ese club,
        y quien reporto esto veria el NIS hasta que se acordara de hacerlo.

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

        # LA MONEDA DEL MANAGER, que es la de su club principal. Va primero
        # porque es la que Hattrick enseña en todas sus pantallas.
        principal: m.Team | None = None
        if equipo.owner_user_id is not None:
            principal = await uow.session.scalar(
                select(m.Team)
                .where(m.Team.owner_user_id == equipo.owner_user_id)
                # La misma regla que el pais del mapa de Uso; vive en `models`
                # porque escrita dos veces se arreglo una sola (PR #7).
                .order_by(*m.orden_del_club_principal())
                .limit(1)
            )
        if principal is not None and principal.id != equipo.id and principal.currency_name:
            equipo.currency_name = principal.currency_name
            equipo.currency_rate = principal.currency_rate or 1.0
            _log.info(
                "moneda de %s tomada del club principal %s (%s, tasa %s)",
                equipo.ht_team_id,
                principal.ht_team_id,
                principal.currency_name,
                principal.currency_rate,
            )
            return

        candidatos: list[m.WorldContext | None] = []
        if equipo.ht_league_id is not None:
            candidatos.append(await _contexto(m.WorldContext.ht_league_id == equipo.ht_league_id))
        if equipo.league_name:
            candidatos.append(await _contexto(m.WorldContext.league_name == equipo.league_name))
        for fila in candidatos:
            if fila is not None and fila.currency_name:
                equipo.currency_name = fila.currency_name
                equipo.currency_rate = fila.currency_rate or 1.0
                # Si este ES el principal, su moneda es la del manager: se
                # estampa en los hermanos para que no haya que sincronizarlos
                # uno a uno para dejar de ver la moneda equivocada.
                if principal is not None and principal.id == equipo.id:
                    await self._estampar_en_los_hermanos(uow, equipo)
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

    async def _estampar_en_los_hermanos(self, uow: UnitOfWork, principal: Any) -> None:
        """La moneda del club principal, puesta en los demas clubes del manager.

        Es la segunda mitad del reporte del 2026-10-25. La primera --que mande
        la moneda del manager-- se resuelve al sincronizar CADA club, asi que
        sin esto un club secundario seguiria con la suya hasta que a su dueño se
        le ocurriera sincronizarlo. Con esto, una sola sincronizacion del club
        principal arregla todas sus pantallas.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        if not principal.currency_name or principal.owner_user_id is None:
            return
        tasa = principal.currency_rate or 1.0
        hermanos = (
            (
                await uow.session.execute(
                    select(m.Team).where(
                        m.Team.owner_user_id == principal.owner_user_id,
                        m.Team.id != principal.id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for hermano in hermanos:
            if (
                hermano.currency_name == principal.currency_name
                and (hermano.currency_rate or 1.0) == tasa
            ):
                continue
            _log.info(
                "moneda de %s alineada con la del manager: %s -> %s (tasa %s)",
                hermano.ht_team_id,
                hermano.currency_name,
                principal.currency_name,
                tasa,
            )
            hermano.currency_name = principal.currency_name
            hermano.currency_rate = tasa
