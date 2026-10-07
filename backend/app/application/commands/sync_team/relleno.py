"""Rellenar hacia atras lo que un sync viejo no trajo.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

import json
from datetime import UTC, datetime

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    GOTEO_DE_VIGILANCIA,
    ProgressReporter,
    SyncBackfillBatchCommand,
    SyncPreviousClubBonusCommand,
    SyncResult,
    _as_change_row,
    _full_player_name,
    _nombre_legible,
    _report,
    _tras_fallo,
)
from app.domain.engines import caza_de_comisiones as caza
from app.domain.engines import mapa_del_barrido
from app.domain.engines import sync_diff as diff_sync
from app.domain.engines.sync_diff import diff_expedientes_cerrados, diff_previous_club_bonus
from app.domain.engines.youth_arrival import cuando_cumplio_diecisiete
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_time import ht_to_utc


class RellenoMixin(BaseDeSync):
    """Rellenar hacia atras lo que un sync viejo no trajo."""

    async def execute_previous_club_bonus(self, cmd: SyncPreviousClubBonusCommand) -> SyncResult:
        """HL-161: bajo demanda, un jugador, reutilizado tanto por el
        backfill masivo (`/players/previous-club-bonus/sync`) como,
        indirectamente, por `_check_previous_club_bonus` desde el
        monitoreo automático dentro de `execute()`."""
        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind=f"previous_club_bonus:{cmd.ht_player_id}"
            )
            result = SyncResult(sync_id=sync_id, status="completed")
            try:
                wrote = await self._check_previous_club_bonus(uow, cmd.team_id, cmd.ht_player_id)
                if wrote:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001, mismo patrón que execute_transfers_player
                result.errors.append(f"{_nombre_legible('previous_club_bonus')}: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _check_previous_club_bonus(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_player_id: int,
    ) -> bool:
        """Núcleo de `execute_previous_club_bonus`, recibe el `uow` ya
        abierto, igual que `_apply_transfers_player_purchase`/
        `_apply_player_enrichment`, para poder llamarse también desde
        `_backfill_previous_club_bonus` (monitoreo automático dentro de
        `execute()`).

        "Club anterior" de una reventa = quien nos compró el jugador A
        NOSOTROS justo antes de esa reventa, nunca una venta más abajo en
        la cadena (esa le toca al club que sí fue "anterior" en ESA venta).
        transfersplayer.xml viene ordenado del más reciente al más antiguo,
        así que esa reventa, si existe, es la que aparece INMEDIATAMENTE
        ANTES de nuestra propia venta en la lista."""
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from app.domain.engines.previous_club_bonus import previous_club_bonus_pct
        from app.infrastructure.db import models as m

        now = datetime.now(UTC)
        team = await uow.session.get(m.Team, team_id)
        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if team is None or player is None or player.sold_at is None:
            return False

        payload = await self._chpp.fetch(
            "transfersplayer",
            version=FILE_VERSIONS["transfersplayer"],
            playerID=ht_player_id,
        )
        transfers = payload.get("transfers", [])
        our_sale_index = next(
            (i for i, t in enumerate(transfers) if t.get("seller_team_id") == team.ht_team_id),
            None,
        )
        if our_sale_index is None:
            player.previous_club_bonus_checked_at = now
            return False
        our_sale = transfers[our_sale_index]

        our_purchase = next(
            (t for t in transfers if t.get("buyer_team_id") == team.ht_team_id),
            None,
        )
        if player.ht_sale_transfer_id is None:
            player.ht_sale_transfer_id = our_sale.get("ht_transfer_id")
        if our_purchase is not None and player.ht_purchase_transfer_id is None:
            player.ht_purchase_transfer_id = our_purchase.get("ht_transfer_id")
        player.previous_club_bonus_checked_at = now

        if our_sale_index == 0:
            return False  # nadie nos ha revendido todavía
        resale = transfers[our_sale_index - 1]
        if resale.get("seller_team_id") != our_sale.get("buyer_team_id"):
            # Cadena rota (defensivo, no debería pasar): la venta previa en
            # la lista no encaja con quien nos compró, no se inventa una
            # comisión sobre una cadena que no se puede confirmar.
            return False

        resale_transfer_id = resale.get("ht_transfer_id")
        already = await uow.session.scalar(
            select(m.PreviousClubBonus.id).where(
                m.PreviousClubBonus.resale_transfer_id == resale_transfer_id
            )
        )
        if already is not None:
            return False

        # Los partidos se cuentan POR ETAPA, no por jugador.
        #
        # 2026-08-25, senalado por el usuario. `PlayerStint` ya tenia sus
        # campos --"se cuenta una vez por etapa, no una vez por jugador"--
        # desde el 22 de agosto, pero este calculo seguia leyendo los del
        # jugador. En la base real hay 38 ex-jugadores con mas de una etapa y
        # ocho con TRES: a todos se les habria aplicado el mismo numero,
        # vinieran de la etapa que vinieran.
        #
        # La reventa cae dentro de UNA etapa: la que estaba abierta cuando lo
        # vendimos. Esa es la que hay que contar.
        etapa = await uow.session.scalar(
            select(m.PlayerStint)
            .where(
                m.PlayerStint.player_id == player.id,
                m.PlayerStint.sale_transfer_id.is_not(None),
            )
            .order_by(m.PlayerStint.left_at.desc())
            .limit(1)
        )
        if etapa is None:
            etapa = await uow.session.scalar(
                select(m.PlayerStint)
                .where(m.PlayerStint.player_id == player.id)
                .order_by(m.PlayerStint.left_at.desc().nullslast())
                .limit(1)
            )

        games = etapa.games_played_for_us if etapa is not None else None

        if games is None and (etapa is None or etapa.arrived_at is None):
            # Sin fecha de llegada no se puede contar ESA etapa, y recontar
            # con las fechas del jugador daria el numero de otra.
            #
            # 2026-08-25. Aqui habia un `return False` y perdia la comision
            # ENTERA: 17 ex-jugadores y 3,4 millones en la cuenta real --Ramiro
            # Pineda 1.050.000, Ciro Moyano 900.000--. Lo introdujo el cambio a
            # contar por etapa, de ese mismo dia, y se descubrio comparando el
            # volcado de comisiones de antes de reabrirlo todo con lo que el
            # barrido volvio a encontrar.
            #
            # El numero del jugador puede venir de otra etapa y caer en un
            # tramo de porcentaje equivocado. Es un riesgo real, pero perder el
            # importe completo --y en silencio-- es peor.
            games = player.games_played_for_us

        if games is None:
            # El respaldo del jugador solo vale para quien tiene UNA etapa: si
            # tiene varias, ese numero es de cualquiera de ellas y usarlo seria
            # peor que volver a contar.
            cuantas = (
                await uow.session.scalar(
                    select(sa_func.count(m.PlayerStint.id)).where(
                        m.PlayerStint.player_id == player.id
                    )
                )
                or 0
            )
            if cuantas <= 1:
                games = player.games_played_for_us

        if games is None:
            desde = etapa.arrived_at if etapa is not None else None
            salida = player.sold_at or player.left_team_at
            if desde is None and salida is not None:
                # El MISMO suelo que usa el censo: nadie llega al primer
                # equipo antes de los 17 años. Un canterano no se compró, así
                # que no tiene fecha de llegada; contar desde el día que los
                # cumplió cubre de más, nunca de menos.
                edad = self._edad_en_la_salida(player)
                if edad is not None:
                    desde = cuando_cumplio_diecisiete(edad, salida)
            if desde is None:
                desde = player.purchased_at
            hasta = (etapa.left_at if etapa is not None else None) or salida
            if desde is not None:
                games = await self._games_played_for_us(
                    team.ht_team_id,
                    ht_player_id,
                    desde,
                    hasta,
                )

        if games is None:
            return False

        if etapa is not None and etapa.games_played_for_us is None:
            etapa.games_played_for_us = games
            etapa.games_computed_at = now
        if player.games_played_for_us is None:
            player.games_played_for_us = games
            player.games_played_for_us_computed_at = now

        pct = previous_club_bonus_pct(games)
        price = resale.get("price", 0)
        deadline_str = resale.get("deadline", "")
        resale_deadline = ht_to_utc(deadline_str) or now

        uow.session.add(
            m.PreviousClubBonus(
                player_id=player.id,
                ht_player_id=ht_player_id,
                resale_transfer_id=resale_transfer_id,
                resale_price=price,
                resale_deadline=resale_deadline,
                buyer_team_id=resale.get("buyer_team_id", 0),
                seller_team_id=resale.get("seller_team_id", 0),
                games_played_with_us=games,
                pct_applied=pct,
                amount=round(price * pct),
                computed_at=now,
            )
        )
        return True

    async def _backfill_previous_club_bonus(
        self,
        uow: UnitOfWork,
        team_id: int,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Monitoreo automático, sin botón (HL-161, 2026-08-14, pedido
        explícitamente): en cada sync que incluya transfersteam, revisa
        hasta 25 ex-jugadores, los nunca revisados primero, luego los más
        desactualizados (orden por `previous_club_bonus_checked_at`
        ascendente, NULL primero), por si alguno fue revendido por el
        club al que le vendimos. Acotado a propósito: a diferencia del
        backfill masivo (sin límite, bajo demanda), esto corre solo en
        cada sync, así que no puede convertir un sync normal en cientos de
        llamadas a CHPP. El conteo de partidos (caro: matchesarchive +
        matchlineup por partido) solo se dispara cuando de verdad hay una
        reventa nueva que pagar, la inmensa mayoría de estos 25 no la
        tendrán."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        cazando = bool(equipo is not None and equipo.commission_hunting)

        if cazando:
            # Hay dinero por atribuir: se persigue. Uno reciente, uno al azar
            # --2026-08-24, disenado por el usuario--: lo reciente rinde mas,
            # y el azar impide que la cola larga muera de hambre.
            por_recencia = list(
                (
                    await uow.session.execute(
                        select(m.Player.ht_player_id)
                        .where(
                            m.Player.team_id == team_id,
                            m.Player.sold_at.is_not(None),
                            ~m.Player.resale_closed,
                        )
                        .order_by(m.Player.sold_at.desc())
                    )
                )
                .scalars()
                .all()
            )
            try:
                probados = set(json.loads(equipo.commission_tried_json or "[]"))
            except ValueError:
                probados = set()
            candidates = caza.orden_de_busqueda(por_recencia, probados, 25)
            if not candidates:
                # Se probaron todos y no aparecio: se cierra la caceria en vez
                # de repetirla eternamente. Si el dinero vuelve a subir, se
                # abre otra con la lista limpia.
                equipo.commission_hunting = False
                equipo.commission_tried_json = "[]"
        else:
            # Sin dinero nuevo no hay nada que encontrar. El goteo sigue, pero
            # solo como red: que nadie quede sin mirar nunca.
            candidates = list(
                (
                    await uow.session.execute(
                        select(m.Player.ht_player_id)
                        .where(m.Player.team_id == team_id, m.Player.sold_at.is_not(None))
                        .order_by(
                            m.Player.previous_club_bonus_checked_at.is_not(None),
                            m.Player.previous_club_bonus_checked_at,
                        )
                        .limit(GOTEO_DE_VIGILANCIA)
                    )
                )
                .scalars()
                .all()
            )

        encontrado = False
        for ht_player_id in candidates:
            identidad = (
                await uow.session.execute(
                    select(m.Player.first_name, m.Player.last_name).where(
                        m.Player.ht_player_id == ht_player_id
                    )
                )
            ).one()
            nombre = _full_player_name(identidad.first_name, identidad.last_name)
            await _report(
                on_progress,
                f"Revisando comisión de club anterior de {nombre}...",
            )
            try:
                wrote = await self._check_previous_club_bonus(uow, team_id, ht_player_id)
                if wrote:
                    result.snapshots_written += 1
                    encontrado = True
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001, best effort, ver _backfill_sold_player_details
                result.errors.append(
                    f"{_nombre_legible('previous_club_bonus')} ({ht_player_id}): {exc}"
                )
            if cazando:
                probados.add(ht_player_id)

        if cazando and equipo is not None:
            equipo.commission_tried_json = json.dumps(sorted(probados))
            if encontrado:
                # Apareció: se cierra hasta que vuelva a entrar dinero.
                equipo.commission_hunting = False
                equipo.commission_tried_json = "[]"

    async def execute_backfill_batch(
        self,
        cmd: SyncBackfillBatchCommand,
        on_progress: ProgressReporter | None = None,
    ) -> SyncResult:
        """Un lote del relleno; si revienta, su fila queda cerrada con el motivo."""
        self._fila_en_curso = None
        try:
            return await self._execute_backfill_batch(cmd, on_progress)
        except Exception as exc:
            await self._cerrar_como_fallida(exc)
            raise

    async def _execute_backfill_batch(
        self,
        cmd: SyncBackfillBatchCommand,
        on_progress: ProgressReporter | None = None,
    ) -> SyncResult:
        """Un lote del relleno del pasado, con cuenta de lo que queda.

        Nace de un reporte de usuario: la copia publicada tenía 60 precios y
        416 nacionalidades sin resolver, y no avanzaban nunca porque el intento
        se hacía entero dentro de la sincronización normal y se cortaba por
        tiempo. Troceado y con su propio botón, cada pulsación termina lo que
        empieza y se ve cuánto falta.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        async with self._uow as uow:
            # UNA fila por pulsación, no por jugador. Con un jugador por
            # petición esto creaba cientos de filas vacías que no cuentan nada
            # y solo ensucian el histórico. El instante del clic, que ya viaja
            # para acotar la vigilancia, sirve también para reconocer la fila
            # de esta misma pulsación y reutilizarla.
            sync_id = None
            if cmd.revisar_desde is not None and cmd.reutilizar_fila:
                sync_id = await uow.session.scalar(
                    select(m.Sync.id)
                    .where(
                        m.Sync.team_id == cmd.team_id,
                        m.Sync.kind == "backfill_batch",
                        m.Sync.started_at >= cmd.revisar_desde,
                    )
                    .order_by(m.Sync.id.desc())
                    .limit(1)
                )
            if sync_id is None:
                sync_id = await uow.syncs.create(cmd.user_id, cmd.team_id, kind="backfill_batch")
                await uow.commit()
            self._fila_en_curso = sync_id
            result = SyncResult(sync_id=sync_id, status="completed")
            fetched_at = datetime.now(UTC).replace(tzinfo=None)

            # El libro de compraventas ya NO se lee aqui: son TUS movimientos
            # y los trae "Sincronizar ahora" (2026-08-25). Este boton es solo
            # para la vigilancia y la caza de comisiones de reventa.
            result.players_done = await self._backfill_sold_player_details(
                uow,
                cmd.team_id,
                fetched_at,
                result,
                on_progress,
                limite=cmd.limite,
                revisar_desde=cmd.revisar_desde,
            )
            quedan = await self.pendientes_de_ficha(uow, cmd.team_id, cmd.revisar_desde)
            # La union de TODAS las colas, sin nombrarlas una a una: nombrarlas
            # ya costo un fallo -al anadir el censo y la vigilancia, esta
            # cuenta se quedo mirando solo las tres viejas y devolvia 0, con lo
            # que la pantalla paraba tras el primer lote creyendo haber
            # terminado.
            pendientes_unicos: set[int] = set()
            for cola in quedan.values():
                pendientes_unicos |= set(cola)
            result.players_pending = len(pendientes_unicos)

            # Las comisiones encontradas van tambien a "Cambios": el progreso
            # se pierde en cuanto se cierra la pantalla, y esto es dinero.
            for c in result.changes:
                detail = c.get("detail")
                uow.session.add(
                    m.SyncChange(
                        sync_id=sync_id,
                        team_id=cmd.team_id,
                        category=c["category"],
                        summary=c["summary"],
                        detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
                        created_at=fetched_at,
                    )
                )

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _backfill_native_countries_from_snapshots(
        self, uow: UnitOfWork, team_id: int, result: SyncResult
    ) -> None:
        """Completa la nacionalidad con dos datos oficiales ya sincronizados.

        `players.xml/CountryID` vive en PlayerSnapshot y
        `worlddetails.xml/Country/CountryID` resuelve su nombre. No se
        infiere nada por nombre, bandera o club. Esto cubre toda la plantilla
        actual y cualquier exjugador del que HT Lens sí haya conservado al
        menos un snapshot real.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        countries = {
            row.country_id: row.country_name
            for row in (
                await uow.session.execute(
                    select(m.WorldContext).where(
                        m.WorldContext.country_id > 0,
                        m.WorldContext.country_name != "",
                    )
                )
            ).scalars()
        }
        if not countries:
            return

        latest_snapshot_id = (
            select(m.PlayerSnapshot.id)
            .where(m.PlayerSnapshot.player_id == m.Player.id)
            .order_by(
                m.PlayerSnapshot.captured_at.desc(),
                m.PlayerSnapshot.id.desc(),
            )
            .limit(1)
            .correlate(m.Player)
            .scalar_subquery()
        )
        rows = (
            await uow.session.execute(
                select(m.Player, m.PlayerSnapshot.country_id)
                .join(m.PlayerSnapshot, m.PlayerSnapshot.id == latest_snapshot_id)
                .where(
                    m.Player.team_id == team_id,
                    (m.Player.native_country.is_(None) | (m.Player.native_country == "")),
                    m.PlayerSnapshot.country_id > 0,
                )
            )
        ).all()
        for player, country_id in rows:
            country_name = countries.get(country_id)
            if country_name:
                player.native_country = country_name
                result.snapshots_written += 1

    async def _backfill_sold_player_details(
        self,
        uow: UnitOfWork,
        team_id: int,
        fetched_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
        limite: int | None = None,
        revisar_desde: datetime | None = None,
    ) -> int:
        """Rellena lo que le falta a cada jugador, de a un lote.

        2026-08-21, por reportes de usuarios: esto vivía dentro de la
        sincronización normal y sin tope, así que una cuenta con historia
        larga intentaba casi novecientas llamadas a Hattrick de una sentada y
        se cortaba por tiempo antes de terminar ninguna. Ahora va por lotes,
        desde su propio botón, y devuelve cuántos jugadores atendió para que
        la pantalla pueda decir cuánto falta.

        `limite` es en JUGADORES, no en llamadas: de cada uno se descarga TODO
        lo que le falte antes de pasar al siguiente, para que nunca quede una
        ficha a medias.
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        pendientes = await self.pendientes_de_ficha(uow, team_id, revisar_desde)
        ficha = set(pendientes["ficha"])
        precio = set(pendientes["precio"])
        destino = set(pendientes["destino"])
        censo = set(pendientes["censo"])
        reventa = set(pendientes["reventa"])

        # Lo mas reciente primero, y estable: el mismo lote se repetiria igual
        # si algo fallara.
        #
        # 2026-08-24. Aqui ponia `sorted(...)` sobre la union de conjuntos, y
        # eso ordena por NUMERO DE JUGADOR, que sube con la antiguedad: el
        # lote empezaba siempre por los mas viejos. Ordenar las consultas de
        # `pendientes_de_ficha` no bastaba, porque este consumidor tiraba ese
        # orden. Se vuelve a pedir el orden aqui, sobre la union.
        # Primero, deshacer los cierres que el tiempo demostro falsos.
        reabiertos = await self._reabrir_cierres_por_error(uow, team_id)
        if reabiertos:
            await _report(
                on_progress,
                f"{reabiertos} expediente(s) se habian cerrado sin venta y si la tenian",
            )
            pendientes = await self.pendientes_de_ficha(uow, team_id, revisar_desde)
            ficha = set(pendientes["ficha"])
            precio = set(pendientes["precio"])
            destino = set(pendientes["destino"])
            censo = set(pendientes["censo"])
            reventa = set(pendientes["reventa"])

        #  ¿Hay dinero por atribuir? Lo dice la economia que ya esta
        #  guardada, y decide en que orden se busca.
        cazando = False
        equipo = await uow.session.get(m.Team, team_id)
        if equipo is not None:
            await self._mirar_si_entro_comision(uow, team_id)
            cazando = bool(equipo.commission_hunting)
            try:
                probados: set[int] = set(json.loads(equipo.commission_tried_json or "[]"))
            except ValueError:
                probados = set()

            # ── Barrido nuevo: se congela el eje y se limpia la memoria ─────
            #
            # El eje se guarda tal como esta AHORA. Recalculandolo en cada
            # pulsacion contra la tabla viva, cada expediente cerrado borraba
            # una casilla, las posiciones se corrian y las marcas ya pintadas
            # saltaban de sitio.
            #
            # Y la lista de probados se vacia con el, porque tiene que decir
            # lo MISMO que el eje. Si sobrevive al barrido anterior, la
            # busqueda salta jugadores que el eje sigue contando: sus casillas
            # quedan muertas y, si estan al principio, el frente no arranca
            # nunca --se vio con las casillas 0, 1 y 2 ocupadas por tres
            # ex-jugadores ya apuntados--. Dentro de un mismo barrido nadie se
            # repite igualmente, porque `revisar_desde` los saca de la cola en
            # cuanto se les mira.
            if revisar_desde is not None and equipo.sweep_started_at != revisar_desde:
                eje_nuevo = list(
                    (
                        await uow.session.execute(
                            select(m.Player.ht_player_id)
                            .where(
                                m.Player.team_id == team_id,
                                # La MISMA salvaguardia que usan las colas: quien
                                # lleva prestado el numero de su transferencia no
                                # tiene ficha y no se le pregunta jamas. Sin ella
                                # ocupaba casilla --67 de 266 en la cuenta real, y
                                # dieciseis de ellas las primeras--.
                                ~m.Player.ht_player_id_is_transfer,
                                ~m.Player.resale_closed,
                                m.Player.sold_at.is_not(None) | m.Player.left_team_at.is_not(None),
                            )
                            .order_by(
                                sa_func.coalesce(
                                    m.Player.sold_at,
                                    m.Player.left_team_at,
                                )
                                .desc()
                                .nullslast(),
                                m.Player.ht_player_id.desc(),
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                equipo.sweep_axis_json = json.dumps(eje_nuevo)
                equipo.sweep_started_at = revisar_desde
                probados = set()
                equipo.commission_tried_json = "[]"
        else:
            probados = set()

        union = ficha | precio | destino | censo | reventa
        todos = (
            list(
                (
                    await uow.session.execute(
                        select(m.Player.ht_player_id)
                        .where(m.Player.ht_player_id.in_(union))
                        .order_by(
                            sa_func.coalesce(
                                m.Player.sold_at,
                                m.Player.left_team_at,
                                m.Player.purchased_at,
                            )
                            .desc()
                            .nullslast(),
                            m.Player.ht_player_id.desc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
            if union
            else []
        )

        # Cuántos historiales se llegan a construir en ESTA pasada. Ver
        # `Balance.historiales`: hasta el 2026-09-10 este trabajo no dejaba
        # rastro en ningún sitio y se leía como que no había pasado nada.
        historiales_construidos = 0

        if reventa:
            # Uno reciente, uno al azar, uno reciente… sobre la cola de
            # reventas, y el resto detras por recencia. La alternancia
            # sobrevive entre pulsaciones porque el turno se deduce de cuantos
            # se llevan probados, no de una variable de esta llamada.
            #
            # 2026-08-25: la alternancia corre SIEMPRE, no solo persiguiendo
            # una comision. Lo reciente es lo que paga --una reventa se cobra
            # sobre la ultima venta-- pero lo viejo es lo que CIERRA
            # expedientes: los entrenadores estan entre las ventas de hace
            # años, y con recencia pura el unico que se localizo estaba en el
            # puesto 210 de 218. Las dos cosas valen, y alternando se hacen
            # las dos con las mismas llamadas.
            cola = [x for x in todos if x in reventa]
            perseguidos = caza.orden_de_busqueda(
                cola,
                probados,
                len(cola),
                empezar_por_reciente=(len(probados) % 2 == 0),
            )
            resto = [x for x in todos if x not in set(perseguidos)]
            todos = perseguidos + resto

        if limite is not None:
            todos = todos[:limite]

        # Cuantas comisiones habia antes, y desde cuando: lo primero dice si
        # esta tanda atribuyo alguna NUEVA --`_check_previous_club_bonus`
        # devuelve cierto tambien para las ya anotadas-- y lo segundo permite
        # recuperarlas al final para anunciarlas.
        comisiones_antes = (
            await uow.session.scalar(select(sa_func.count(m.PreviousClubBonus.id))) or 0
        )
        arranque = datetime.now(UTC).replace(tzinfo=None)

        for ht_player_id in todos:
            identidad = (
                await uow.session.execute(
                    select(m.Player.first_name, m.Player.last_name).where(
                        m.Player.ht_player_id == ht_player_id
                    )
                )
            ).one()
            nombre = _full_player_name(identidad.first_name, identidad.last_name)
            result.players_named.append(nombre)
            if ht_player_id in ficha:
                await _report(on_progress, f"Descargando ficha de ex-jugador {nombre}...")
                try:
                    wrote = await self._apply_player_enrichment(uow, ht_player_id, fetched_at)
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                    result.errors.append(
                        f"{_nombre_legible('player_enrichment')} ({ht_player_id}): {exc}"
                    )
                    await _tras_fallo(uow, exc)
                    result.status = "partial"
            if ht_player_id in precio:
                await _report(
                    on_progress,
                    f"Descargando transferencias de {nombre}...",
                )
                try:
                    wrote = await self._apply_transfers_player_purchase(uow, team_id, ht_player_id)
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                    result.errors.append(
                        f"{_nombre_legible('tsi_at_purchase')} ({ht_player_id}): {exc}"
                    )
                    await _tras_fallo(uow, exc)
                    result.status = "partial"
            if ht_player_id in destino:
                await _report(on_progress, f"Descargando país destino de {nombre}...")
                try:
                    wrote = await self._apply_destination_country(uow, ht_player_id)
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                    result.errors.append(
                        f"{_nombre_legible('destination_country')} ({ht_player_id}): {exc}"
                    )
                    await _tras_fallo(uow, exc)
                    result.status = "partial"
            if ht_player_id in censo:
                await _report(
                    on_progress,
                    f"Contando partidos con nosotros de {nombre}...",
                )
                try:
                    wrote = await self._censar_partidos_del_stint(uow, team_id, ht_player_id)
                    result.snapshots_written += 1 if wrote else 0
                    # Se cuenta para poder DECIRLO. Ver `Balance.historiales`.
                    historiales_construidos += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                    result.errors.append(
                        f"{_nombre_legible('censo_partidos')} ({ht_player_id}): {exc}"
                    )
                    await _tras_fallo(uow, exc)
                    result.status = "partial"
            if ht_player_id in reventa:
                await _report(on_progress, f"Revisando reventas de {nombre}...")
                try:
                    wrote = await self._vigilar_reventa(uow, team_id, ht_player_id)
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                    result.errors.append(f"{_nombre_legible('reventa')} ({ht_player_id}): {exc}")
                    await _tras_fallo(uow, exc)
                    result.status = "partial"

        # Los expedientes que se cerraron en ESTA tanda. Un jugador cerrado
        # sale de la cola y ya no se le vuelve a mirar, asi que "cerrado y
        # revisado desde que arranco" es exactamente eso.
        cerrados = list(
            (
                await uow.session.execute(
                    select(
                        m.Player.first_name,
                        m.Player.last_name,
                        m.Player.resale_closed_reason,
                    ).where(
                        m.Player.team_id == team_id,
                        m.Player.resale_closed.is_(True),
                        m.Player.previous_club_bonus_checked_at >= arranque,
                    )
                )
            ).all()
        )
        if cerrados:
            conteo: dict[str, int] = {}
            for nombre, apellido, motivo in cerrados:
                clave = motivo or "sin_comprador"
                conteo[clave] = conteo.get(clave, 0) + 1
                # El detalle, en el progreso: ahi si cabe uno por uno.
                legible = diff_sync.MOTIVOS_DE_CIERRE.get(clave, (clave, clave))[0]
                await _report(
                    on_progress,
                    f"{nombre} {apellido}: expediente cerrado, {legible}",
                )
            resumen = diff_expedientes_cerrados(conteo)
            if resumen is not None:
                result.changes.append(_as_change_row(resumen))

        # Lo encontrado se ANUNCIA. 2026-08-25, pedido explicitamente: la
        # herramienta calculaba la comision al peso y la guardaba sin decir
        # nada; era dinero del usuario apareciendo en silencio.
        #
        # No se corta la tanda al encontrarla --tambien pedido asi--: el resto
        # de la cola sigue necesitando ficha, precio o censo, que no tienen
        # que ver con la caceria.
        nuevas = list(
            (
                await uow.session.execute(
                    select(m.PreviousClubBonus, m.Player.first_name, m.Player.last_name)
                    .join(m.Player, m.Player.id == m.PreviousClubBonus.player_id)
                    .where(m.PreviousClubBonus.computed_at >= arranque)
                )
            ).all()
        )
        if nuevas:
            equipo_moneda = await uow.session.get(m.Team, team_id)
            moneda = equipo_moneda.currency_name if equipo_moneda else ""
            tasa = (equipo_moneda.currency_rate or 1.0) if equipo_moneda else 1.0
            for bono, nombre, apellido in nuevas:
                cambio = diff_previous_club_bonus(
                    player_name=f"{nombre} {apellido}".strip(),
                    # `amount` y `resale_price` viajan en la moneda base del
                    # juego, igual que los precios de compra y venta.
                    resale_price=round(bono.resale_price / tasa),
                    amount=round(bono.amount / tasa),
                    games=bono.games_played_with_us,
                    pct=bono.pct_applied,
                    currency=moneda,
                )
                result.changes.append(_as_change_row(cambio))
                await _report(on_progress, cambio.summary)

        if equipo is not None:
            # A quien se probo, para no repetirlo en la siguiente pulsacion.
            probados |= {x for x in todos if x in reventa}

            comisiones_ahora = (
                await uow.session.scalar(select(sa_func.count(m.PreviousClubBonus.id))) or 0
            )
            aparecio = comisiones_ahora > comisiones_antes
            barrido_completo = not [x for x in reventa if x not in probados]
            if cazando and (aparecio or barrido_completo):
                # Aparecio, o se miraron todos sin encontrarla: en los dos
                # casos la caceria termina hasta que vuelva a entrar dinero.
                equipo.commission_hunting = False
            if barrido_completo or (cazando and aparecio):
                # Barrido completo, o caceria resuelta: se empieza otro con la
                # lista limpia. Sin esto la mitad aleatoria se quedaria sin
                # candidatos y dejaria de explorar.
                probados = set()
            equipo.commission_tried_json = json.dumps(sorted(probados))

        # El mapa, ya con todo escrito. Se manda entero en cada respuesta: el
        # navegador solo pinta, no acumula --acumular era lo que dejaba fuera
        # lo atendido en pulsaciones anteriores a un refresco--.
        #
        # Solo con `revisar_desde`: sin el no hay barrido que mapear y lo
        # guardado seria el de otra vez.
        if (
            equipo is not None
            and revisar_desde is not None
            and equipo.sweep_axis_json
            and equipo.sweep_started_at is not None
        ):
            try:
                eje = json.loads(equipo.sweep_axis_json)
            except ValueError:
                eje = []
            if eje:
                # Se pide por equipo y se cruza en Python a proposito. Un
                # `IN (...)` gasta una variable por jugador y SQLite corta a
                # las 999: hoy el eje son 191, pero un historial mas largo
                # reventaria la peticion en mitad del barrido.
                atendidos = set(
                    (
                        await uow.session.execute(
                            select(m.Player.ht_player_id).where(
                                m.Player.team_id == team_id,
                                m.Player.previous_club_bonus_checked_at.is_not(None),
                                m.Player.previous_club_bonus_checked_at >= equipo.sweep_started_at,
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                result.queue_map = mapa_del_barrido.mapa_de(eje, atendidos)

                # El resumen para cuando el barrido pare --lo pare el usuario
                # o se acabe la cola--. Todo se mide DESDE QUE ARRANCO el
                # barrido, no desde este lote: el usuario ve el resultado del
                # recorrido entero, que es lo que ha estado esperando.
                abiertos = (
                    await uow.session.scalar(
                        select(sa_func.count(m.Player.id)).where(
                            m.Player.team_id == team_id,
                            ~m.Player.ht_player_id_is_transfer,
                            ~m.Player.resale_closed,
                            m.Player.sold_at.is_not(None) | m.Player.left_team_at.is_not(None),
                        )
                    )
                    or 0
                )
                # `group_by` quiere la expresion, no el numero de columna.
                motivo = sa_func.coalesce(
                    m.Player.resale_closed_reason,
                    "sin_comprador",
                )
                cerrados_del_barrido = dict(
                    (
                        await uow.session.execute(
                            select(motivo, sa_func.count(m.Player.id))
                            .where(
                                m.Player.team_id == team_id,
                                m.Player.resale_closed.is_(True),
                                m.Player.previous_club_bonus_checked_at >= equipo.sweep_started_at,
                            )
                            .group_by(motivo)
                        )
                    ).all()
                )
                comisiones_del_barrido = (
                    await uow.session.scalar(
                        select(sa_func.count(m.PreviousClubBonus.id)).where(
                            m.PreviousClubBonus.computed_at >= equipo.sweep_started_at
                        )
                    )
                    or 0
                )
                result.queue_balance = mapa_del_barrido.balance_de(
                    result.queue_map,
                    abiertos=abiertos,
                    cerrados=cerrados_del_barrido,
                    comisiones=comisiones_del_barrido,
                    historiales=historiales_construidos,
                )

        return len(todos)
