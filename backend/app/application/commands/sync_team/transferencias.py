"""Transferencias: compras, ventas, pujas y comisiones.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    VERSION_DEL_LIBRO,
    ProgressReporter,
    SyncPlayerEnrichmentCommand,
    SyncResult,
    SyncTransfersHistoryCommand,
    SyncTransfersPlayerCommand,
    _as_change_row,
    _nombre_legible,
    _report,
    _tras_fallo,
)
from app.domain.engines import caza_de_comisiones as caza
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_constants import MATCH_TYPE_CUP
from app.domain.value_objects.ht_time import ht_to_utc, ht_to_utc_naive


class TransferenciasMixin(BaseDeSync):
    """Transferencias: compras, ventas, pujas y comisiones."""

    async def execute_transfers_player(self, cmd: SyncTransfersPlayerCommand) -> SyncResult:
        """HL-161: precio de compra real para un jugador que `_persist_transfers`
        (transfersteam.xml, historial del EQUIPO) no pudo resolver, porque
        llegó antes de sincronizar con esta app, o porque su compra quedó
        fuera de la única página que CHPP entrega por defecto.

        Solo escribe si CHPP trae una transferencia donde el comprador
        somos nosotros; si el jugador nunca aparece comprándose (p. ej.
        vino de la propia cantera), no se toca `purchase_price`, el
        motivo NO es un error, es que no hay compra que registrar, y el
        dominio ya sabe tratar un canterano como precio 0 por separado."""
        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind=f"transfersplayer:{cmd.ht_player_id}"
            )
            result = SyncResult(sync_id=sync_id, status="completed")

            try:
                wrote = await self._apply_transfers_player_purchase(
                    uow, cmd.team_id, cmd.ht_player_id
                )
                if wrote:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001, mismo patrón que execute_match_details
                result.errors.append(f"{_nombre_legible('transfersplayer')}: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def execute_transfers_history(self, cmd: SyncTransfersHistoryCommand) -> SyncResult:
        """HL-161, 2026-08-04, botón "Actualizar transferencias": pagina
        transfersteam.xml completo (`pageIndex` 1..Pages, verificado en vivo
        que sí funciona, ver `parse_transfersteam`), más allá de la única
        página que trae el sync normal. Para cada compra/venta de este
        equipo, crea una identidad de jugador mínima si nunca se vio en
        `players.xml` (`_split_player_name` + `upsert_identity`), así
        "Detalle" puede mostrar ~1000 transferencias reales, con huecos
        ("?") donde de verdad no hay forma de conocer skills/edad, en vez
        de descartar en silencio todo lo anterior a la última página.

        Idempotente y barato en re-ejecuciones: las páginas llegan de más
        reciente a más vieja, así que en cuanto una página no aporta ningún
        TransferID nuevo respecto a `Team.last_transfer_id_seen`, se para
        no hace falta re-pedir las ~40 páginas cada vez que el usuario
        pulsa el botón, solo la primera vez (o si de verdad hay huecos)."""

        from app.infrastructure.db import models as m

        async with self._uow as uow:
            sync_id = await uow.syncs.create(cmd.user_id, cmd.team_id, kind="transfers_history")
            result = SyncResult(sync_id=sync_id, status="completed")

            team = await uow.session.get(m.Team, cmd.team_id)
            if team is not None:
                await self._recorrer_historial(uow, cmd.user_id, cmd.team_id, team, result)

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _persist_transfers(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        payload: dict[str, Any],
        result: SyncResult,
    ) -> None:
        """Precio real de compra Y venta (HL-15x fase C, HL-161), de
        `transfersteam.xml` (historial del EQUIPO). Parte del sync normal:
        solo procesa la página más reciente (pageIndex=1, la que devuelve
        CHPP sin pedir página explícita), jugadores que ya se fueron ANTES
        de que esta app empezara a sincronizar, o cuya transacción quedó
        más atrás en el historial, se resuelven con el backfill paginado
        completo del botón "Actualizar transferencias", ver
        `execute_transfers_history`. Compras propias (`TransferType ==
        "B"`, comprador == este equipo) de jugadores que siguen en la
        plantilla; ventas propias (`TransferType == "S"`, vendedor == este
        equipo) de jugadores que ya se fueron pero cuya fila sigue
        existiendo (append-only, nunca se borra).

        También refresca `Team.transfer_total_*`/`transfer_number_*`, el
        `<Stats>` de este fichero es un agregado de TODA la historia del
        equipo (verificado en vivo, idéntico en cualquier página), así que
        una sola llamada del sync normal ya mantiene esos KPI al día."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        stats = payload.get("stats") or {}
        if stats:
            team = await uow.session.get(m.Team, team_id)
            if team is not None:
                team.transfer_total_buys = stats.get("total_sum_of_buys", 0)
                team.transfer_total_sales = stats.get("total_sum_of_sales", 0)
                team.transfer_number_buys = stats.get("number_of_buys", 0)
                team.transfer_number_sales = stats.get("number_of_sales", 0)

        transfers = payload.get("transfers", [])
        buys = [
            t
            for t in transfers
            if t.get("transfer_type") == "B" and t.get("buyer_team_id") == ht_team_id
        ]
        sells = [
            t
            for t in transfers
            if t.get("transfer_type") == "S" and t.get("seller_team_id") == ht_team_id
        ]
        if not buys and not sells:
            return
        ids = {t["ht_player_id"] for t in buys} | {t["ht_player_id"] for t in sells}
        players = {
            p.ht_player_id: p
            for p in (
                await uow.session.execute(select(m.Player).where(m.Player.ht_player_id.in_(ids)))
            ).scalars()
        }
        for t in buys:
            player = players.get(t["ht_player_id"])
            if player is None:
                continue
            self._apply_buy_transfer(player, t, result)
        for t in sells:
            player = players.get(t["ht_player_id"])
            if player is None:
                continue
            self._apply_sell_transfer(player, t, result)

    async def _guardar_transferencia(
        self, uow: UnitOfWork, team_id: int, ht_team_id: int, t: dict[str, Any]
    ) -> None:
        """Anota un movimiento del libro, si no estaba ya.

        Guardarlos es lo que permite reconstruir las etapas hacia atras sin
        volver a pedirle nada a Hattrick: antes se leian y se tiraban, y de
        cada jugador quedaba solo su ultima compra encima de su ultima venta.

        Dos casos que el libro trae y que hay que tratar aparte:

        - Movimientos SIN identificador de jugador (54 ventas reales de esta
          cuenta, todas anteriores a abril de 2022). Se les da el numero de la
          transferencia, que es unico, asi que cada uno queda en su propia
          ficha. Antes se descartaban, y con ellos 42 millones de ventas.
        - Movimientos donde el club esta en LOS DOS lados. La venta es tan real
          como la compra --con su salario y su comision-- asi que se anotan las
          dos filas, igual que Hattrick, que las cuenta en sus dos totales.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        ht_transfer_id = t.get("ht_transfer_id")
        if not ht_transfer_id:
            return
        deadline = ht_to_utc_naive(t.get("deadline") or "")
        if deadline is None:
            return

        ht_player_id = t.get("ht_player_id") or 0
        sin_identificador = not ht_player_id
        if sin_identificador:
            ht_player_id = await self._identificador_prestado(uow, ht_transfer_id)
            if ht_player_id is None:
                return

        # Compra o venta se decide por QUIEN estaba en cada lado, no por la
        # letra de `TransferType`: en 32 movimientos reales de esta cuenta esa
        # letra no dice "B" aunque el comprador seamos nosotros -promociones y
        # traspasos sin dinero, entre otros-, y clasificarlos por ella dejaba
        # esas 32 compras contadas como ventas. Con los identificadores no hay
        # ambiguedad, y el total cuadra con el que publica Hattrick.
        lados = []
        if t.get("buyer_team_id") == ht_team_id:
            lados.append(True)
        if t.get("seller_team_id") == ht_team_id:
            lados.append(False)
        if not lados:
            # Ni comprador ni vendedor: no es un movimiento de este club.
            return

        for es_compra in lados:
            ya = await uow.session.scalar(
                select(m.TeamTransfer.id).where(
                    m.TeamTransfer.ht_transfer_id == ht_transfer_id,
                    m.TeamTransfer.is_buy == es_compra,
                )
            )
            if ya is not None:
                continue
            uow.session.add(
                m.TeamTransfer(
                    team_id=team_id,
                    ht_transfer_id=ht_transfer_id,
                    ht_player_id=ht_player_id,
                    player_name=t.get("player_name", "") or "",
                    deadline=deadline,
                    price=t.get("price", 0) or 0,
                    is_buy=es_compra,
                    counterpart_team_id=(
                        t.get("seller_team_id") if es_compra else t.get("buyer_team_id")
                    ),
                    tsi=t.get("tsi"),
                )
            )

    def _apply_buy_transfer(self, player: Any, t: dict[str, Any], result: SyncResult) -> None:
        """Núcleo de una compra, compartido por `_persist_transfers` (página
        más reciente, parte del sync normal) y `execute_transfers_history`
        (backfill paginado completo, HL-161 2026-08-04), para no mantener la
        misma lógica de "qué campo se pisa y cuál no" duplicada dos veces."""
        deadline = t.get("deadline") or ""
        # SQLite no conserva tzinfo en el viaje de ida y vuelta:
        # player.purchased_at leído de la BD siempre llega naive, así
        # que lo que se compara aquí debe serlo también, un valor
        # aware chocaría con un TypeError al comparar (visto en vivo
        # 2026-08-03, justo al arreglar el bug de parseo de más
        # arriba, que hasta entonces dejaba `buys`/`sells` siempre
        # vacíos y nunca llegaba a esta comparación).
        purchased_at = ht_to_utc_naive(deadline)
        # Un jugador puede aparecer varias veces si se compró más de una
        # vez (vendido y recomprado): se queda la fecha más reciente. Si
        # es la MISMA transacción que ya conocíamos (fecha igual o más
        # vieja), no se pisa precio/fecha, pero SÍ se rellena el TSI si
        # todavía faltaba (HL-161, 2026-08-04: antes este `continue`
        # también se saltaba el TSI para cualquier venta/compra ya
        # registrada ANTES de que este campo existiera, dejándolo en "?"
        # para siempre, visto en vivo contra la cuenta real).
        is_new_transaction = (
            player.purchased_at is None
            or purchased_at is None
            or purchased_at > player.purchased_at
        )
        if is_new_transaction:
            player.purchase_price = t.get("price", 0)
            player.purchased_at = purchased_at
        # HL-161: TSI de esta transacción exacta, para "Delta TSI" y
        # "Ganancia/TSI" en la tabla Detalle, nunca el de playerdetails
        # (ese es el de HOY, no el de la compra).
        if player.tsi_at_purchase is None and t.get("tsi"):
            player.tsi_at_purchase = t["tsi"]
        if is_new_transaction:
            result.snapshots_written += 1

    def _apply_sell_transfer(self, player: Any, t: dict[str, Any], result: SyncResult) -> None:
        """Núcleo de una venta, ver `_apply_buy_transfer`."""
        deadline = t.get("deadline") or ""
        sold_at = ht_to_utc_naive(deadline)
        is_new_transaction = player.sold_at is None or sold_at is None or sold_at > player.sold_at
        if is_new_transaction:
            player.sale_price = t.get("price", 0)
            player.sold_at = sold_at
        if player.tsi_at_sale is None and t.get("tsi"):
            player.tsi_at_sale = t["tsi"]
        # HL-161: equipo comprador, hace falta para resolver el país
        # destino después (ver `_backfill_sold_player_details`).
        if player.buyer_team_id is None and t.get("buyer_team_id"):
            player.buyer_team_id = t["buyer_team_id"]
        if is_new_transaction:
            result.snapshots_written += 1

    async def _apply_transfers_player_purchase(
        self, uow: UnitOfWork, team_id: int, ht_player_id: int
    ) -> bool:
        """Núcleo de `execute_transfers_player`, recibe el `uow` ya abierto
        (mismo motivo que `_apply_player_enrichment`: reutilizable también
        desde `_backfill_sold_player_details`, solo para el TSI, en
        jugadores cuyo `purchase_price` YA se resolvió antes de que
        existiera esta captura de TSI, sin esto, `tsi_at_purchase` se
        quedaría en "?" para siempre, porque el endpoint de precio de
        compra ya no vuelve a llamarlos)."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        payload = await self._chpp.fetch(
            "transfersplayer",
            version=FILE_VERSIONS["transfersplayer"],
            playerID=ht_player_id,
        )
        team = await uow.session.get(m.Team, team_id)
        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if team is None or player is None:
            return False
        own_purchase = next(
            (t for t in payload.get("transfers", []) if t.get("buyer_team_id") == team.ht_team_id),
            None,
        )
        if own_purchase is None:
            # 2026-08-05, pedido explícitamente: "backfill de un jugador
            # máximo una vez", transfersplayer.xml ya trae TODA la
            # historia del jugador; si no aparecemos como comprador ahora,
            # nunca vamos a aparecer (el historial no cambia hacia atrás),
            # así que no tiene sentido volver a pedirlo en cada sync.
            player.tsi_at_purchase_attempted = True
            return True
        if player.purchase_price is None:
            date_str = own_purchase.get("deadline", "")
            if date_str:
                player.purchased_at = ht_to_utc(date_str)
            player.purchase_price = own_purchase.get("price", 0)
        if player.tsi_at_purchase is None and own_purchase.get("tsi"):
            player.tsi_at_purchase = own_purchase["tsi"]
        player.tsi_at_purchase_attempted = True
        return True

    async def _recorrer_historial(
        self,
        uow: UnitOfWork,
        user_id: int,
        team_id: int,
        team: Any,
        result: SyncResult,
    ) -> None:
        """Recorre transfersteam.xml pagina a pagina y anota lo nuevo.

        Vive aparte porque lo usan dos sitios: el boton de Transferencias,
        que lo hace una vez antes de ponerse con los jugadores, y el
        recorrido suelto que aun existe para reintentarlo a mano.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        # La marca de agua solo vale si alguna vez se recorrió la historia
        # ENTERA. Si el primer intento se quedó a medias, la marca apunta a
        # lo más reciente y haría creer que ya está todo, dejando fuera
        # para siempre lo anterior. En ese caso se ignora y se empieza de
        # cero, que es lo único que rellena el hueco.
        # El libro de movimientos es nuevo (2026-08-22): quien ya tenía el
        # historial "completo" de antes lo tiene vacío, y sin él no hay etapas
        # que reconstruir. Mientras esté vacío se ignora la marca y se recorre
        # todo otra vez, así la corrección alcanza también al pasado, sin que
        # nadie tenga que pedirlo.
        hay_libro = (
            await uow.session.scalar(
                select(m.TeamTransfer.id).where(m.TeamTransfer.team_id == team_id).limit(1)
            )
        ) is not None
        completa = bool(
            team is not None
            and team.transfers_history_complete
            and hay_libro
            # Leido con reglas viejas = no esta completo, por mucho que la
            # marca lo diga. Se relee entero una vez y se vuelve a sellar.
            and team.transfers_import_version >= VERSION_DEL_LIBRO
        )
        watermark = team.last_transfer_id_seen if (team is not None and completa) else None
        highest_seen = watermark or 0
        recorrido_entero = False

        try:
            page = 1
            total_pages = 1
            while page <= total_pages:
                payload = await self._chpp.fetch(
                    "transfersteam",
                    version=FILE_VERSIONS["transfersteam"],
                    teamID=team.ht_team_id,
                    pageIndex=page,
                )
                result.pages_fetched += 1
                total_pages = max(payload.get("pages", 1), 1)

                stats = payload.get("stats") or {}
                if stats and team is not None:
                    team.transfer_total_buys = stats.get("total_sum_of_buys", 0)
                    team.transfer_total_sales = stats.get("total_sum_of_sales", 0)
                    team.transfer_number_buys = stats.get("number_of_buys", 0)
                    team.transfer_number_sales = stats.get("number_of_sales", 0)

                page_transfers = payload.get("transfers", [])
                if not page_transfers:
                    # Página vacía más allá del final real (visto en vivo):
                    # también es haber llegado al final de la historia.
                    recorrido_entero = True
                    break

                own_transfers = [
                    t
                    for t in page_transfers
                    if t.get("buyer_team_id") == team.ht_team_id
                    or t.get("seller_team_id") == team.ht_team_id
                ]
                # Las páginas van de más reciente a más vieja: en cuanto
                # se ve un TransferID ya conocido, TODO lo que sigue (en
                # esta página y en las siguientes) también lo es.
                new_transfers = []
                reached_known = False
                for t in own_transfers:
                    tid = t.get("ht_transfer_id", 0)
                    if watermark is not None and tid <= watermark:
                        reached_known = True
                        break
                    new_transfers.append(t)
                result.transfers_seen += len(own_transfers)
                result.transfers_new += len(new_transfers)

                if new_transfers:
                    ids = {t["ht_player_id"] for t in new_transfers}
                    players = {
                        p.ht_player_id: p
                        for p in (
                            await uow.session.execute(
                                select(m.Player).where(m.Player.ht_player_id.in_(ids))
                            )
                        ).scalars()
                    }
                    for t in new_transfers:
                        await self._guardar_transferencia(uow, team_id, team.ht_team_id, t)
                    for t in new_transfers:
                        ht_player_id = t["ht_player_id"]
                        player = players.get(ht_player_id)
                        if player is None:
                            first, last = self._split_player_name(t.get("player_name", ""))
                            player_id = await uow.players.upsert_identity(
                                ht_player_id, team_id, first, last
                            )
                            player = await uow.session.get(m.Player, player_id)
                            players[ht_player_id] = player
                        if t.get("transfer_type") == "B":
                            self._apply_buy_transfer(player, t, result)
                        elif t.get("transfer_type") == "S":
                            self._apply_sell_transfer(player, t, result)
                        highest_seen = max(highest_seen, t.get("ht_transfer_id", 0))

                if reached_known:
                    recorrido_entero = True
                    break
                page += 1
            else:
                # Se acabaron las páginas sin encontrar nada conocido:
                # también es haber llegado al final de la historia.
                recorrido_entero = True
        except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
            result.errors.append(f"{_nombre_legible('transfers_history')}: {exc}")
            result.status = "partial"

        # La marca solo avanza si el recorrido llegó de verdad al final y
        # sin errores. Un intento que se cortó a la mitad no puede decir
        # "ya lo he visto todo hasta aquí": eso fue lo que dejó a los
        # primeros usuarios con Transferencias vacía y sin forma de
        # recuperarla, porque cada clic siguiente se paraba en la primera
        # página creyendo estar al día.
        # Las etapas se reconstruyen a partir del libro, asi que solo hay que
        # rehacerlas si el libro CAMBIO. 2026-08-25: desde que "Sincronizar
        # ahora" recorre el libro en cada pulsacion, rehacerlas siempre era
        # trabajo inutil en la inmensa mayoria de los syncs --y, peor, volvia
        # a escribir sobre etapas que ya estaban bien--.
        if result.transfers_new:
            await self._marcar_salidas_de_vendidos(uow, team_id)
            await self._reconstruir_etapas(uow, team_id)

        if team is not None and recorrido_entero and not result.errors:
            if highest_seen > (team.last_transfer_id_seen or 0):
                team.last_transfer_id_seen = highest_seen
            team.transfers_history_complete = True
            team.transfers_import_version = VERSION_DEL_LIBRO

    async def _persist_currentbids(
        self,
        uow: UnitOfWork,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """HL-161: cuenta intentos de venta hacia adelante. CHPP solo da
        una foto del momento (quién está en el mercado AHORA), nunca un
        historial, así que una aparición nueva (no estaba listado en el
        sync anterior, ahora sí) se cuenta como un intento más. Si el
        jugador sigue listado desde el sync pasado, no se repite.

        2026-08-08, pedido explícitamente: además de incrementar el
        contador, cada aparición nueva se guarda como fila propia en
        `player_listing_attempts` (con la puja más alta del momento) para
        poder ENUMERAR los intentos en la ficha de ex-jugador, no solo
        contarlos. Empieza a llenarse desde hoy, subestima lo anterior,
        igual que `listing_count`."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        listed_now = {
            p["ht_player_id"]: {
                "highest_bid": p.get("highest_bid"),
                "deadline": ht_to_utc_naive(p.get("deadline") or ""),
            }
            for p in payload.get("listed_players", [])
        }
        roster = list(
            (
                await uow.session.execute(select(m.Player).where(m.Player.team_id == team_id))
            ).scalars()
        )
        ahora = datetime.now(UTC).replace(tzinfo=None)

        # La marca de "en venta" se refresca AQUI, antes de decidir nada.
        #
        # 2026-08-24. Este bloque leia `player.currently_listed` tal como
        # habia quedado del sync ANTERIOR, porque el refresco vive en el
        # post-proceso y `currentbids` se despacha durante la descarga. Iba un
        # sync por detras: un jugador que volvia al mercado no abria intento
        # hasta la siguiente pulsacion, y uno que perdia la marca por error
        # veia su puja cerrada antes de que nadie la corrigiera.
        await self._marcar_quien_esta_en_venta(uow, team_id, captured_at)
        await self._reabrir_pujas_cerradas_por_error(uow, team_id, ahora, result)

        for player in roster:
            en_mercado = listed_now.get(player.ht_player_id)
            # Quien esta en venta lo dice players.xml (`TransferListed`), no
            # este fichero: `currentbids.xml` es la lista de PUJAS, y usarlo
            # como censo de transferibles es justo la forma de equivocarse.
            # Aqui solo sirve para enriquecer lo que ya se sabe: el plazo de
            # cierre y la puja mas alta.
            is_listed = player.currently_listed

            abierto = await uow.session.scalar(
                select(m.PlayerListingAttempt)
                .where(
                    m.PlayerListingAttempt.player_id == player.id,
                    m.PlayerListingAttempt.ended_at.is_(None),
                )
                .order_by(m.PlayerListingAttempt.detected_at.desc())
                .limit(1)
            )

            # Solo intentos en los que el vendedor somos NOSOTROS. Un
            # ex-jugador puede aparecer en `currentbids.xml` porque estamos
            # pujando por recomprarlo: ese fichero es la lista de pujas en las
            # que andamos metidos, no la de lo que vendemos.
            sigue_siendo_nuestro = player.left_team_at is None
            if is_listed and abierto is None and sigue_siendo_nuestro:
                player.listing_count += 1
                result.snapshots_written += 1
                etapa = await uow.session.scalar(
                    select(m.PlayerStint.id)
                    .where(
                        m.PlayerStint.player_id == player.id,
                        m.PlayerStint.left_at.is_(None),
                    )
                    .limit(1)
                )
                uow.session.add(
                    m.PlayerListingAttempt(
                        player_id=player.id,
                        ht_player_id=player.ht_player_id,
                        stint_id=etapa,
                        highest_bid=(en_mercado or {}).get("highest_bid"),
                        last_highest_bid=(en_mercado or {}).get("highest_bid"),
                        deadline=(en_mercado or {}).get("deadline"),
                        detected_at=ahora,
                    )
                )
            elif is_listed and abierto is not None:
                # Sigue en el mercado: se refresca lo que puede cambiar.
                abierto.last_highest_bid = (en_mercado or {}).get("highest_bid")
                abierto.deadline = (en_mercado or {}).get("deadline") or abierto.deadline
                result.unchanged += 1
            elif not is_listed and abierto is not None:
                # Se acabo la puja. Que siga en la plantilla es la señal de
                # que NO se vendio: una venta lo saca del equipo.
                abierto.ended_at = ahora
                abierto.sold = player.left_team_at is not None or player.sold_at is not None
                result.snapshots_written += 1
            else:
                result.unchanged += 1

        # Y se recogen los que quedaron abiertos de antes de esta regla.
        en_venta_ahora = {p.ht_player_id for p in roster if p.currently_listed}
        result.snapshots_written += await self._reparar_intentos_abiertos(
            uow, team_id, en_venta_ahora
        )

    async def _marcar_quien_esta_en_venta(
        self, uow: UnitOfWork, team_id: int, captured_at: datetime
    ) -> None:
        """Quien esta en el mercado, segun players.xml.

        2026-08-22, pedido explicitamente: no usar `currentbids.xml` para
        decidir quien ya NO esta en venta. Ese fichero es la lista de PUJAS y
        tomarlo por un censo de transferibles es la forma de equivocarse.
        `TransferListed` viene con la plantilla, jugador por jugador, y es la
        respuesta directa a la pregunta.
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy import select, update

        from app.infrastructure.db import models as m

        # Primero nadie: quien no aparece en la plantilla de HOY no puede
        # estar en venta por nosotros. Sin este borron, un jugador que ya no
        # es nuestro se queda marcado para siempre con lo ultimo que se supo
        # de el. Caso real: Gabriel Cecilio Acasusso, vendido en julio, seguia
        # figurando "en venta" en agosto.
        await uow.session.execute(
            update(m.Player)
            .where(m.Player.team_id == team_id, m.Player.currently_listed)
            .values(currently_listed=False)
        )
        # Y luego, la ULTIMA foto de cada uno, no la de este sync.
        #
        # 2026-08-24. `player_snapshots` escribe fila solo cuando algo cambia,
        # y `is_transfer_listed` entra en la huella --asi que si la marca
        # cambiara, habria foto--. Exigir `captured_at == <este sync>` dejaba
        # fuera a todo el que no hubiera cambiado NADA desde el sync anterior:
        # se le borraba la marca, su intento de venta se cerraba como "ya no
        # esta en el mercado" y la pantalla pasaba a preguntarle las cosas de
        # una venta cerrada. Caso real: Enyo Kasaliyski, en el mercado con
        # plazo hasta las 15:11, cerrado a las 12:08 del mismo dia.
        #
        # Quien ya no es nuestro no entra: para ese caso --Gabriel Cecilio
        # Acasusso, vendido en julio y aun marcado en agosto-- el borron de
        # arriba es lo correcto, y su ultima foto no debe resucitarlo.
        ultima = (
            select(
                m.PlayerSnapshot.player_id,
                sa_func.max(m.PlayerSnapshot.captured_at).label("cuando"),
            )
            .where(m.PlayerSnapshot.captured_at <= captured_at)
            .group_by(m.PlayerSnapshot.player_id)
            .subquery()
        )
        filas = (
            await uow.session.execute(
                select(m.Player, m.PlayerSnapshot.is_transfer_listed)
                .join(ultima, ultima.c.player_id == m.Player.id)
                .join(
                    m.PlayerSnapshot,
                    (m.PlayerSnapshot.player_id == ultima.c.player_id)
                    & (m.PlayerSnapshot.captured_at == ultima.c.cuando),
                )
                .where(
                    m.Player.team_id == team_id,
                    m.Player.left_team_at.is_(None),
                    m.Player.sold_at.is_(None),
                )
            )
        ).all()
        for jugador, en_venta in filas:
            jugador.currently_listed = bool(en_venta)

    async def _marcar_salidas_de_vendidos(self, uow: UnitOfWork, team_id: int) -> int:
        """Un jugador vendido ya no esta en la plantilla: marcarlo.

        `left_team_at` lo pone `mark_departed` cuando alguien DESAPARECE de
        players.xml. Los cientos de jugadores que crea el historial de
        transferencias nunca aparecieron ahi, asi que nunca desaparecen y se
        quedaban con `left_team_at` en NULL, es decir, contados como plantilla
        activa. En una cuenta con historia larga eso convertia cada
        sincronizacion normal en ~950 llamadas a Hattrick (una ficha y un
        entrenamiento por cada uno de los 479 "activos"), que en un plan
        gratuito no termina nunca. Medido en produccion: 479 activos donde
        debia haber 24.

        Solo se marcan los que no tienen ningun snapshot POSTERIOR a la venta:
        si volvio a fichar por el club, sus lecturas nuevas lo demuestran y no
        se toca.
        """
        from sqlalchemy import select, update

        from app.infrastructure.db import models as m

        posterior_a_la_venta = (
            select(m.PlayerSnapshot.id)
            .where(
                m.PlayerSnapshot.player_id == m.Player.id,
                m.PlayerSnapshot.captured_at > m.Player.sold_at,
            )
            .exists()
        )
        resultado = await uow.session.execute(
            update(m.Player)
            .where(
                m.Player.team_id == team_id,
                m.Player.sold_at.is_not(None),
                m.Player.left_team_at.is_(None),
                ~posterior_a_la_venta,
            )
            .values(left_team_at=m.Player.sold_at)
        )
        return resultado.rowcount or 0

    async def _vigilar_reventa(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_player_id: int,
    ) -> bool:
        """¿Sigue pudiendo darnos dinero este ex-jugador?

        Una llamada mira su historial de transferencias, que es la que
        contesta la pregunta del dinero. Solo si NO hay reventa hace falta la
        segunda, la de su ficha, para saber si sigue existiendo: un despido o
        un retiro lo cierran para siempre, y comprobado en vivo, Hattrick
        responde a esa ficha con el error 56 cuando el jugador ya no está.
        """
        from sqlalchemy import select

        from app.domain.engines import ex_player_watch as vigilancia
        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        jugador = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if equipo is None or jugador is None:
            return False

        canterano = vigilancia.es_canterano(jugador.mother_club_team_id, equipo.ht_team_id)
        salio_sin_comprador = jugador.sold_at is None and jugador.left_team_at is not None

        if jugador.sold_at is not None:
            await self._check_previous_club_bonus(uow, team_id, ht_player_id)

        # "Revendido" es que EXISTA la reventa, no que se acabe de escribir.
        # `_check_previous_club_bonus` devuelve False cuando la comisión ya
        # estaba anotada de antes, y tomarlo por "no lo han revendido" dejaba
        # abierto para siempre a quien ya había cobrado: caso real de
        # Adrian-Ioan Burlac, con su comisión de 234.090 guardada desde 2020 y
        # aun así revisado en cada pulsación.
        revendido = (
            await uow.session.scalar(
                select(m.PreviousClubBonus.id).where(
                    m.PreviousClubBonus.ht_player_id == ht_player_id
                )
            )
        ) is not None

        desaparecido = False
        # Sin ficha no se sabe nada de el: ni que desaparecio, ni que se hizo
        # entrenador. Vacia y no `None` para poder preguntarle igual.
        ficha: dict[str, Any] = {}
        # Solo se pregunta por su ficha cuando la reventa no ha zanjado nada:
        # es la única forma de dejar de vigilar a quien ya no existe, y una
        # llamada de más solo para los que siguen ahí fuera sin venderse.
        if not salio_sin_comprador and not (revendido and not canterano):
            try:
                ficha = await self._chpp.fetch(
                    "playerdetails",
                    version=FILE_VERSIONS["playerdetails"],
                    playerID=ht_player_id,
                )
            except Exception:  # noqa: BLE001, best effort, se reintenta en otro lote
                ficha = {}
            desaparecido = vigilancia.desaparecio_de_hattrick(ficha.get("chpp_error_code"))

        motivo = vigilancia.motivo_de_cierre(
            canterano=canterano,
            revendido=revendido,
            desaparecido=desaparecido,
            salio_sin_comprador=salio_sin_comprador,
            # El dato viene en la MISMA ficha que ya se pidio para saber si
            # desaparecio: no cuesta ni una llamada mas.
            entrenador=vigilancia.es_entrenador(ficha),
            # Si acaba de irse, su venta puede estar todavia en camino.
            recien_salido=vigilancia.salio_hace_poco(
                jugador.left_team_at,
                datetime.now(UTC).replace(tzinfo=None),
            ),
        )
        jugador.previous_club_bonus_checked_at = datetime.now(UTC).replace(tzinfo=None)
        if motivo is not None:
            jugador.resale_closed = True
            jugador.resale_closed_reason = motivo
        return revendido

    async def _reabrir_pujas_cerradas_por_error(
        self,
        uow: UnitOfWork,
        team_id: int,
        ahora: datetime,
        result: SyncResult,
    ) -> int:
        """Una puja con el plazo por vencer no puede estar cerrada.

        2026-08-24. Mientras la marca de "en venta" se borraba sola, algunos
        intentos se cerraron con la subasta todavia abierta, y la pantalla
        pasaba a pedir los datos de una venta hecha --cuantas veces lo
        miraron, a que precio-- por algo que no habia pasado. Reabrirlos aqui
        arregla lo ya guardado sin migracion: si el jugador sigue siendo
        nuestro, sigue en el mercado y su plazo aun no ha vencido, el cierre
        fue un error nuestro.

        Un re-listado legitimo NO entra: al volver a poner a alguien en venta
        Hattrick le da un plazo nuevo, y el que se guardo con el cierre ya
        habia vencido.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        candidatos = (
            (
                await uow.session.execute(
                    select(m.PlayerListingAttempt)
                    .join(m.Player, m.Player.id == m.PlayerListingAttempt.player_id)
                    .where(
                        m.Player.team_id == team_id,
                        m.Player.currently_listed.is_(True),
                        m.Player.left_team_at.is_(None),
                        m.Player.sold_at.is_(None),
                        m.PlayerListingAttempt.ended_at.is_not(None),
                        m.PlayerListingAttempt.sold.is_(False),
                        m.PlayerListingAttempt.deadline.is_not(None),
                        m.PlayerListingAttempt.deadline > ahora,
                    )
                )
            )
            .scalars()
            .all()
        )
        for intento in candidatos:
            intento.ended_at = None
            result.snapshots_written += 1
        return len(candidatos)

    async def _reabrir_cierres_por_error(
        self,
        uow: UnitOfWork,
        team_id: int,
    ) -> int:
        """Quien tiene venta registrada no se fue "sin comprador".

        2026-08-25. Se cierra un expediente con lo que se sabe en ese momento,
        y a veces lo que se sabe llega tarde: Enyo Kasaliyski quedo cerrado
        como `sin_comprador` cuando de hecho se habia vendido por 4.880.000.
        Su comision no se habria vigilado nunca.

        Se cura sola, sin migracion: si hay venta, el motivo era falso.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        malos = (
            (
                await uow.session.execute(
                    select(m.Player).where(
                        m.Player.team_id == team_id,
                        m.Player.resale_closed.is_(True),
                        m.Player.resale_closed_reason == "sin_comprador",
                        m.Player.sold_at.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for jugador in malos:
            jugador.resale_closed = False
            jugador.resale_closed_reason = None
            # Que lo vuelva a mirar: el motivo anterior no valia.
            jugador.previous_club_bonus_checked_at = None
        return len(malos)

    async def _reparar_intentos_abiertos(
        self, uow: UnitOfWork, team_id: int, listados_ahora: set[int]
    ) -> int:
        """Cierra intentos de venta que se quedaron abiertos para siempre.

        La regla normal de cierre se dispara en la TRANSICION -estaba listado,
        ya no lo esta-. Los intentos anteriores a esa regla se perdieron la
        transicion y quedaron abiertos: en la cuenta del usuario, 15 intentos
        figuraban "en el mercado" cuando solo 4 jugadores lo estaban.

        La fecha de cierre se toma de lo mejor que se sepa, sin inventar:

        - si el jugador salio del club despues de salir al mercado, la puja
          termino como muy tarde ese dia, y termino en venta si hubo precio;
        - si volvio a listarse mas tarde, el intento anterior ya habia
          terminado antes de esa nueva salida al mercado;
        - y si no, lo unico seguro es que a dia de hoy ya no esta listado.

        `deadline` se queda vacio a proposito: el plazo real de esas pujas
        nunca se llego a ver.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        abiertos = (
            await uow.session.execute(
                select(m.PlayerListingAttempt, m.Player)
                .join(m.Player, m.Player.id == m.PlayerListingAttempt.player_id)
                .where(
                    m.Player.team_id == team_id,
                    m.PlayerListingAttempt.ended_at.is_(None),
                )
                .order_by(m.PlayerListingAttempt.detected_at)
            )
        ).all()

        ahora = datetime.now(UTC).replace(tzinfo=None)
        siguientes: dict[int, datetime] = {}
        for intento, _ in reversed(abiertos):
            anterior = siguientes.get(intento.player_id)
            siguientes[intento.player_id] = intento.detected_at
            intento._siguiente = anterior

        # De un jugador que HOY esta listado, solo su ultimo intento sigue
        # vivo: si tiene otros mas viejos es que aquellos ya terminaron.
        ultimo_de: dict[int, int] = {}
        for intento, jugador in abiertos:
            ultimo_de[jugador.ht_player_id] = intento.id

        cerrados = 0
        for intento, jugador in abiertos:
            if (
                jugador.ht_player_id in listados_ahora
                and ultimo_de.get(jugador.ht_player_id) == intento.id
            ):
                continue  # este si sigue de verdad en el mercado

            # La salida buena es la de SU etapa, no la del jugador: alguien que
            # se vendio y volvio tiene una venta vieja escrita en su ficha que
            # no tiene nada que ver con este intento. Caso real: Acasusso,
            # vendido en julio, de vuelta en el club y listado otra vez ahora.
            etapa = await uow.session.scalar(
                select(m.PlayerStint)
                .where(
                    m.PlayerStint.player_id == intento.player_id,
                    m.PlayerStint.left_at.is_not(None),
                    m.PlayerStint.left_at >= intento.detected_at,
                )
                .order_by(m.PlayerStint.left_at)
                .limit(1)
            )
            siguiente = getattr(intento, "_siguiente", None)
            if etapa is not None:
                intento.ended_at = etapa.left_at
                intento.sold = etapa.sale_price is not None
                intento.stint_id = intento.stint_id or etapa.id
            elif siguiente is not None:
                intento.ended_at = siguiente
            else:
                intento.ended_at = ahora
            cerrados += 1

        return cerrados

    async def _mirar_si_entro_comision(
        self,
        uow: UnitOfWork,
        team_id: int,
    ) -> bool:
        """El dinero dice CUANDO buscar una reventa, aunque no diga quien.

        2026-08-24. `IncomeSoldPlayersCommission` viene en linea propia en
        `economy.xml` --separada de las ventas del club-- y ya se descargaba
        en cada sync. Si sube, alguien revendio a un ex-jugador nuestro.

        Sin esto la vigilancia era ciega: 218 en cola y casi todas las
        llamadas gastadas en semanas donde no habia nada que encontrar.

        Se lee de la economia YA GUARDADA, no de una descarga: el boton de
        arriba la trae en cada sincronizacion y aqui basta con mirarla. Asi
        este boton no le pide nada a Hattrick que no sea para atribuir una
        comision.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        if equipo is None:
            return False
        economia = await uow.session.scalar(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at.desc())
            .limit(1)
        )
        if economia is None:
            return False
        decision = caza.revisar_el_dinero(
            caza.Vigilancia(
                vista_en_curso=equipo.commission_seen or 0,
                vista_cerrada=equipo.commission_seen_closed or 0,
                cazando=bool(equipo.commission_hunting),
            ),
            caza.Comisiones(
                en_curso=economia.income_sold_players_commission or 0,
                semana_cerrada=economia.last_income_sold_players_commission or 0,
            ),
        )
        equipo.commission_seen = decision.vista_en_curso
        equipo.commission_seen_closed = decision.vista_cerrada
        equipo.commission_hunting = decision.cazando
        if decision.empieza:
            # Cacería nueva, lista limpia: si no, la parte aleatoria se
            # habría agotado en el primer barrido y no volvería a mirar.
            equipo.commission_tried_json = "[]"
        return decision.empieza

    async def _a_quien_le_subio_el_contador(
        self,
        uow: UnitOfWork,
        team_id: int,
    ) -> list[tuple[Any, datetime]]:
        """Jugadores cuyo contador de partidos internacionales crecio.

        Devuelve tambien desde cuando mirar: la marca de la foto anterior, la
        que todavia tenia el contador viejo.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        jugadores = (
            (
                await uow.session.execute(
                    select(m.Player).where(
                        m.Player.team_id == team_id, m.Player.left_team_at.is_(None)
                    )
                )
            )
            .scalars()
            .all()
        )
        candidatos: list[tuple[Any, datetime]] = []
        for jugador in jugadores:
            fotos = (
                await uow.session.execute(
                    select(
                        m.PlayerSnapshot.captured_at,
                        m.PlayerSnapshot.career_caps,
                        m.PlayerSnapshot.career_caps_u20,
                    )
                    .where(m.PlayerSnapshot.player_id == jugador.id)
                    .order_by(m.PlayerSnapshot.captured_at.desc())
                    .limit(2)
                )
            ).all()
            if len(fotos) < 2:
                continue
            ahora = (fotos[0].career_caps or 0) + (fotos[0].career_caps_u20 or 0)
            antes = (fotos[1].career_caps or 0) + (fotos[1].career_caps_u20 or 0)
            if ahora > antes:
                candidatos.append((jugador, fotos[1].captured_at))
        return candidatos

    async def _backfill_mandatory_listing_count(
        self, uow: UnitOfWork, team_id: int, result: SyncResult
    ) -> None:
        """HL-161, 2026-08-04, corrección pedida explícitamente por el
        usuario: vender un jugador en Hattrick EXIGE listarlo primero (el
        solo hecho de ponerlo transferible cuesta 1.000, aparte de si
        alguien puja o no), así que CUALQUIER jugador VENDIDO tuvo, como
        mínimo, un intento de venta, aunque `currentbids.xml` (una foto del
        mercado en el instante del sync) nunca lo haya pillado listado a
        tiempo, que es el caso normal para casi cualquier venta ya cerrada
        antes de sincronizar, y SIEMPRE el caso para los ~410 jugadores del
        backfill histórico de `execute_transfers_history` (transfersteam.xml
        no dice nada de si un jugador pasó por el mercado, solo que se
        vendió). No pisa un `listing_count` ya mayor que 0, ese sí viene de
        una detección real vía `_persist_currentbids`, y puede ser más de 1
        si se relistó."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        players = (
            (
                await uow.session.execute(
                    select(m.Player).where(
                        m.Player.team_id == team_id,
                        m.Player.sold_at.is_not(None),
                        m.Player.listing_count == 0,
                    )
                )
            )
            .scalars()
            .all()
        )
        for player in players:
            player.listing_count = 1
            result.snapshots_written += 1

    async def _sync_rival_purchases(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Fichajes de los clubes contra los que vas a jugar, 2026-08-19.

        Se vigilan los de tu serie y los rivales de Copa, Masters o Promoción
        que te queden por delante. El historial de transferencias de cualquier
        club es público (`transfersteam.xml` responde para cualquier teamID,
        verificado en vivo), así que esto no trackea nada privado.

        Solo se anuncia lo comprado DESDE el sync anterior: sin esa marca, cada
        sincronización repetiría los mismos fichajes para siempre. La nota del
        fichado sale de las alineaciones de los últimos partidos de SU club,
        también públicas; si todavía no ha jugado, se dice.
        """
        from sqlalchemy import or_, select

        from app.domain.engines.sync_diff import diff_rival_purchase
        from app.domain.value_objects.ht_constants import (
            MATCH_TYPE_LEAGUE,
            MATCH_TYPE_MASTERS,
            MATCH_TYPE_QUALIFICATION,
            match_type_name,
        )
        from app.domain.value_objects.ht_time import ht_to_utc
        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        if equipo is None:
            return

        anterior = await uow.session.scalar(
            select(m.Sync)
            .where(
                m.Sync.team_id == team_id,
                m.Sync.status.in_(("completed", "partial")),
            )
            .order_by(m.Sync.started_at.desc())
            .offset(1)
            .limit(1)
        )
        desde = (anterior.started_at if anterior else None) or (captured_at - timedelta(days=7))
        if desde.tzinfo is None:
            desde = desde.replace(tzinfo=UTC)

        vigilados: dict[int, str] = {}
        if equipo.series_ht_id is not None:
            filas = (
                await uow.session.execute(
                    select(m.Standing.team_ht_id)
                    .where(m.Standing.series_ht_id == equipo.series_ht_id)
                    .distinct()
                )
            ).all()
            for fila in filas:
                if fila.team_ht_id != ht_team_id:
                    vigilados[fila.team_ht_id] = "tu liga"

        competiciones = {
            MATCH_TYPE_CUP,
            MATCH_TYPE_MASTERS,
            MATCH_TYPE_QUALIFICATION,
            MATCH_TYPE_LEAGUE,
        }
        proximos = (
            await uow.session.execute(
                select(m.Match).where(
                    or_(
                        m.Match.home_team_ht_id == ht_team_id,
                        m.Match.away_team_ht_id == ht_team_id,
                    ),
                    m.Match.status.ilike("upcoming"),
                    m.Match.match_type.in_(competiciones),
                )
            )
        ).scalars()
        for partido in proximos:
            es_local = partido.home_team_ht_id == ht_team_id
            rival_id = partido.away_team_ht_id if es_local else partido.home_team_ht_id
            if rival_id and rival_id != ht_team_id:
                vigilados[rival_id] = match_type_name(partido.match_type)

        if not vigilados:
            return

        await _report(on_progress, "Revisando fichajes de tus rivales...")
        moneda = equipo.currency_name or ""
        tasa = equipo.currency_rate or 1.0
        for rival_id, competicion in vigilados.items():
            try:
                payload = await self._chpp.fetch(
                    "transfersteam",
                    version=FILE_VERSIONS["transfersteam"],
                    teamID=rival_id,
                    pageIndex=1,
                )
            except Exception as exc:  # noqa: BLE001 - un rival caído no tumba el sync
                result.errors.append(f"{_nombre_legible('transfersteam')} ({rival_id}): {exc}")
                await _tras_fallo(uow, exc)
                continue
            nombre_club = payload.get("team_name") or str(rival_id)
            for compra in payload.get("transfers", []):
                if compra.get("buyer_team_id") != rival_id:
                    continue
                cuando = ht_to_utc(compra.get("deadline", ""))
                if cuando is None or cuando <= desde:
                    continue
                nota = await self._best_recent_rating(rival_id, compra.get("ht_player_id") or 0)
                cambio = diff_rival_purchase(
                    team_name=nombre_club,
                    player_name=compra.get("player_name", ""),
                    tsi=compra.get("tsi", 0),
                    price=int(round((compra.get("price") or 0) / tasa)),
                    competition=competicion,
                    best_rating=nota,
                    currency=moneda,
                )
                result.changes.append(_as_change_row(cambio))

    async def _apply_destination_country(self, uow: UnitOfWork, ht_player_id: int) -> bool:
        """Núcleo de `execute_destination_country_backfill`, mismo motivo
        que `_apply_player_enrichment`: recibe el `uow` ya abierto."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if player is None or player.buyer_team_id is None:
            return False

        payload = await self._chpp.fetch(
            "teamdetails",
            version=FILE_VERSIONS["teamdetails"],
            teamID=player.buyer_team_id,
        )
        # Preguntado queda preguntado, salga o no salga el pais: si no se
        # marcara, un comprador que Hattrick no resuelve volveria a la cola en
        # cada lote y el relleno no terminaria jamas.
        player.destination_attempted = True
        team = next(iter(payload.get("teams", [])), None)
        country_name = team.get("country_name") if team else None
        if not country_name:
            return False
        player.destination_country = country_name
        return True

    async def execute_destination_country_backfill(
        self, cmd: SyncPlayerEnrichmentCommand
    ) -> SyncResult:
        """HL-161: país del equipo COMPRADOR, columna "País Destino" del
        Excel del usuario. `playerdetails.xml` no lo trae (solo un
        `LeagueID` numérico, sin nombre), hace falta `teamdetails.xml` del
        equipo comprador (`buyer_team_id`, guardado por `_persist_transfers`
        al detectar la venta), que sí funciona para equipos ajenos y trae
        `Country/CountryName` directo, verificado en vivo 2026-08-04."""
        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind=f"destination_country:{cmd.ht_player_id}"
            )
            result = SyncResult(sync_id=sync_id, status="completed")

            try:
                wrote = await self._apply_destination_country(uow, cmd.ht_player_id)
                if wrote:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001, mismo patrón que execute_transfers_player
                result.errors.append(f"{_nombre_legible('destination_country')}: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result
