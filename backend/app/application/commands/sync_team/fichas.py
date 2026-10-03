"""La ficha de cada jugador.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from datetime import UTC, datetime
from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    FILE_VERSIONS,
    ProgressReporter,
    SyncPlayerDetailsCommand,
    SyncPlayerEnrichmentCommand,
    SyncResult,
    _full_player_name,
    _nombre_legible,
    _report,
    _tras_fallo,
)
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_time import ht_to_utc
from app.domain.value_objects.skill import Age


class FichasMixin(BaseDeSync):
    """La ficha de cada jugador."""

    async def execute_player_details(self, cmd: SyncPlayerDetailsCommand) -> SyncResult:
        """Comando aparte para refrescar UN jugador a demanda (p. ej. desde
        la ficha del jugador), reusa `_apply_player_details`, el mismo
        núcleo que corre automáticamente para toda la plantilla dentro de
        `execute()`."""
        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind=f"playerdetails:{cmd.ht_player_id}"
            )
            result = SyncResult(sync_id=sync_id, status="completed")
            captured_at = datetime.now(UTC)

            try:
                wrote = await self._apply_player_details(uow, cmd.ht_player_id, captured_at)
                result.snapshots_written += 1 if wrote else 0
            except Exception as exc:  # noqa: BLE001, mismo patrón que execute_match_details
                result.errors.append(f"{_nombre_legible('playerdetails')}: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _apply_player_details(
        self, uow: UnitOfWork, ht_player_id: int, captured_at: datetime
    ) -> bool:
        """Núcleo reutilizable de `execute_player_details` (comando aparte,
        un jugador) y del paso automático dentro de `execute()` (2026-08-05,
        pedido explícitamente: "sincroniza todos los xml que importen cada
        vez que sincronizamos", un sync ya no deja `LastMatch`/Caps/HatStats
        obsoletos esperando un botón separado).

        Club de origen y última posición/rating jugado de UN jugador (HL-15x
        fase B). No es append-only: se escribe sobre el snapshot más reciente
        del jugador en vez de crear uno nuevo, porque `LastMatch` no es un
        cambio de habilidades, crear una fila nueva por cada semana solo por
        esto duplicaría snapshots sin motivo.

        `LastMatch` no viene por defecto: hace falta pedirlo explícitamente
        con `includeMatchInfo=true` (confirmado en vivo, sin ese parámetro
        CHPP sirve el resto de campos pero omite el bloque entero, no es
        que expire ni que dependa del momento en que se sincroniza).

        Devuelve si algo REALMENTE cambió, no si se hizo la llamada CHPP
        2026-08-05: al pasar a pedirse en cada sync (antes, solo a demanda),
        un sync repetido sin novedades debía seguir pudiendo reportar
        "sin cambios" en vez de sumar 24 escrituras fantasma cada vez.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        payload = await self._chpp.fetch(
            "playerdetails",
            version=FILE_VERSIONS["playerdetails"],
            playerID=ht_player_id,
            includeMatchInfo="true",
        )
        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if player is None:
            return False

        changed = False

        name = payload.get("mother_club_team_name", "")
        if name and player.mother_club_team_name != name:
            player.mother_club_team_name = name
            changed = True
        league_name = payload.get("native_league_name", "")
        if league_name and player.native_league_name != league_name:
            player.native_league_name = league_name
            changed = True

        # El salario se guarda en el propio jugador, ANTES de mirar si tiene
        # snapshots. Quien entro y salio entre dos sincronizaciones no tiene
        # ninguno, y es justo de quien no se sabia nada: sin esto su coste de
        # salarios figuraba como 0 y su saldo salia mejor de lo que fue.
        salario = payload.get("salary") or 0
        if salario and player.last_known_salary != salario:
            player.last_known_salary = salario
            changed = True

        snap = await uow.session.scalar(
            select(m.PlayerSnapshot)
            .where(m.PlayerSnapshot.player_id == player.id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        if snap is None:
            return changed

        last_match = payload.get("last_match")
        if last_match:
            snap.last_match_ht_id = last_match.get("ht_match_id")
            snap.last_match_position_code = last_match.get("position_code")
            snap.last_match_played_minutes = last_match.get("played_minutes")
            snap.last_match_rating = last_match.get("rating")
            # 2026-08-09, pedido explícitamente: sin esta fecha no hay forma
            # de saber si `LastMatch` es realmente reciente (ver
            # SquadQueryService, que la usa para decidir si mostrar el dato).
            played_at_str = last_match.get("played_at", "")
            snap.last_match_played_at = ht_to_utc(played_at_str)
            snap.last_match_behaviour_code = await self._fetch_last_match_behaviour(
                uow,
                ht_player_id,
                last_match.get("ht_match_id"),
                player.team_id,
            )
            # HL-15x #21: player_snapshots.last_match_* se pisa cada vez
            # (arriba). Para tener una serie en el tiempo (sparkline) hace
            # falta ir acumulando cada partido distinto visto en una tabla
            # append-only aparte, dedup por ht_match_id para no repetir
            # fila si el sync se vuelve a correr antes de que se juegue un
            # partido nuevo. Esa misma dedup ES la señal de "cambió de
            # verdad": un LastMatch repetido no aporta una fila nueva.
            wrote_new_rating = await uow.players.append_match_rating_if_new(
                player.id,
                ht_match_id=last_match.get("ht_match_id", 0),
                position_code=last_match.get("position_code", 0),
                played_minutes=last_match.get("played_minutes", 0),
                rating=last_match.get("rating") or 0.0,
                captured_at=captured_at,
            )
            changed = changed or wrote_new_rating
            # 2026-08-05, pedido explícitamente: saber si LastMatch fue un
            # partido de selección nacional (o Masters/juvenil). matches.xml
            # solo trae los partidos del propio club, así que un ht_match_id
            # ajeno nunca tiene fila en `matches`, sin esto, el JOIN de
            # `experience_progress` lo descartaba en silencio. matchdetails.xml
            # funciona para CUALQUIER matchID (verificado, mismo patrón que
            # playerdetails), así que se rellena una vez y queda para
            # siempre (un partido jugado no cambia).
            ht_match_id = last_match.get("ht_match_id", 0)
            if ht_match_id:
                await self._backfill_foreign_match_type(
                    uow,
                    ht_match_id,
                    jugado_el=snap.last_match_played_at,
                )
        # CareerAssists no está en players.xml (ver parsers), solo aquí,
        # en playerdetails.
        if "career_assists" in payload and snap.career_assists != payload["career_assists"]:
            snap.career_assists = payload["career_assists"]
            changed = True
        # Caps/CapsU20: totales de carrera con la selección nacional
        # única forma barata de saber "sí, este jugador ha jugado con la
        # selección" (HL-15x, pedido 2026-08-05).
        if "caps" in payload and snap.career_caps != payload["caps"]:
            snap.career_caps = payload["caps"]
            changed = True
        if "caps_u20" in payload and snap.career_caps_u20 != payload["caps_u20"]:
            snap.career_caps_u20 = payload["caps_u20"]
            changed = True
        return changed

    async def pendientes_de_ficha(
        self,
        uow: UnitOfWork,
        team_id: int,
        revisar_desde: datetime | None = None,
    ) -> dict[str, list[int]]:
        """Qué le falta por descargar a cada jugador, agrupado por tipo.

        Son tres huecos distintos, todos de una llamada por jugador y todos
        de una sola vez en la vida: el precio de compra antiguo, la ficha
        (nacionalidad, carácter, especialidad, edad reconstruida) y el país
        al que se fue. Se consultan juntos porque, para quien mira la
        pantalla, es una sola cosa: "que la ficha esté completa".
        """
        from sqlalchemy import func as sa_func
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        hay_snapshot_antes_de_la_venta = (
            select(m.PlayerSnapshot.id)
            .where(
                m.PlayerSnapshot.player_id == m.Player.id,
                m.PlayerSnapshot.captured_at <= m.Player.sold_at,
            )
            .exists()
        )
        # 2026-08-05: mismo principio, ancla en `purchased_at`, "Edad de
        # compra" en Detalle lo necesita para TODO jugador con compra
        # conocida, esté vendido o siga en la plantilla.
        hay_snapshot_tras_la_compra = (
            select(m.PlayerSnapshot.id)
            .where(
                m.PlayerSnapshot.player_id == m.Player.id,
                m.PlayerSnapshot.captured_at >= m.Player.purchased_at,
            )
            .exists()
        )

        # Lo mas reciente primero.
        #
        # 2026-08-24, pedido asi: estas colas se recorren por lotes, y sin
        # orden salian por el orden en que estaban en la tabla --o sea, los
        # mas viejos--. Un jugador que te acaban de revender quedaba en el
        # puesto 27 de 285, a veintisiete pulsaciones de distancia, cuando es
        # justo el que puede darte comision esta semana. Caso real: Gabriel
        # Cecilio Acasusso.
        #
        # `nullslast` no es un adorno: en SQLite un NULL ordena por debajo de
        # todo y en Postgres por encima, asi que sin decirlo el orden seria
        # distinto en tu maquina y en produccion.
        ultimo_movimiento = sa_func.coalesce(
            m.Player.sold_at, m.Player.left_team_at, m.Player.purchased_at
        )

        async def ids(condicion: Any) -> list[int]:
            filas = await uow.session.execute(
                select(m.Player.ht_player_id)
                .where(
                    m.Player.team_id == team_id,
                    # Salvaguardia: quien lleva prestado el numero de su
                    # transferencia no tiene ficha en CHPP. Pedirla gastaria
                    # una llamada para traer el jugador equivocado, o un error,
                    # y ademas lo dejaria en la cola para siempre.
                    ~m.Player.ht_player_id_is_transfer,
                    condicion,
                )
                .order_by(ultimo_movimiento.desc().nullslast())
            )
            return list(filas.scalars().all())

        ficha = await ids(
            (~m.Player.enrichment_attempted)
            & (
                (
                    m.Player.sold_at.is_not(None)
                    & (
                        m.Player.native_country.is_(None)
                        | m.Player.agreeability.is_(None)
                        | m.Player.specialty.is_(None)
                        | m.Player.mother_club_team_id.is_(None)
                        | (m.Player.age_years_at_sale.is_(None) & ~hay_snapshot_antes_de_la_venta)
                    )
                )
                | (
                    m.Player.purchased_at.is_not(None)
                    & m.Player.age_years_at_purchase.is_(None)
                    & ~hay_snapshot_tras_la_compra
                )
            )
        )
        # 2026-08-05: "una vez por jugador, para siempre"
        # `tsi_at_purchase_attempted` es el mismo flag en los dos casos.
        precio = await ids(
            (~m.Player.tsi_at_purchase_attempted)
            & (
                (m.Player.purchase_price.is_(None) & m.Player.purchase_price_manual.is_(None))
                | (m.Player.sold_at.is_not(None) & m.Player.tsi_at_purchase.is_(None))
            )
        )
        destino = await ids(
            m.Player.buyer_team_id.is_not(None)
            & m.Player.destination_country.is_(None)
            & (~m.Player.destination_attempted)
        )
        # El censo de partidos se hace por ETAPA, aunque la cola siga
        # devolviendo un PlayerID para no romper el contrato del backfill.
        #
        # 2026-08-28: desde que existe `PlayerStint`, mirar la marca legada
        # del jugador dejaba fuera para siempre cualquier etapa nueva. El
        # caso que destapo el fallo fue Jose Vicente Alvargonzalez: el censo
        # habia encontrado 1 partido y lo habia guardado en `Player`, pero su
        # unica etapa seguia en NULL y Transferencias mostraba "?".
        #
        # Solo se encolan etapas con una ventana que realmente se puede
        # reconstruir. Una compra da `arrived_at`; para la unica etapa de un
        # jugador tambien sirven la fecha legada de compra, el conteo legado
        # inequívoco o la edad de venta (suelo de los 17 anos). Las etapas
        # antiguas sin ninguna de esas evidencias permanecen desconocidas:
        # no se inventa un cero ni se bloquea cada lote reintentandolas.
        cuantas_etapas = (
            select(sa_func.count(m.PlayerStint.id))
            .where(m.PlayerStint.player_id == m.Player.id)
            .correlate(m.Player)
            .scalar_subquery()
        )
        hay_etapa_censable = (
            select(m.PlayerStint.id)
            .where(
                m.PlayerStint.player_id == m.Player.id,
                m.PlayerStint.team_id == team_id,
                m.PlayerStint.left_at.is_not(None),
                m.PlayerStint.games_played_for_us.is_(None),
                m.PlayerStint.arrived_at.is_not(None)
                | (
                    m.PlayerStint.from_academy.is_(True)
                    & m.Player.age_years_at_sale.is_not(None)
                    & m.Player.age_days_at_sale.is_not(None)
                    & (m.Player.sold_at.is_not(None) | m.Player.left_team_at.is_not(None))
                )
                | (
                    (cuantas_etapas == 1)
                    & (
                        m.Player.games_played_for_us.is_not(None)
                        | m.Player.purchased_at.is_not(None)
                        | (
                            m.Player.age_years_at_sale.is_not(None)
                            & m.Player.age_days_at_sale.is_not(None)
                        )
                    )
                ),
            )
            .exists()
        )
        censo = await ids(hay_etapa_censable)
        # La vigilancia de reventas: se repite hasta que el jugador queda
        # cerrado, y entonces desaparece de la cola para siempre.
        vigilancia = (m.Player.sold_at.is_not(None) | m.Player.left_team_at.is_not(None)) & (
            ~m.Player.resale_closed
        )
        if revisar_desde is not None:
            # Ya revisado en esta misma pasada: fuera de la cola hasta la
            # siguiente pulsacion.
            vigilancia = vigilancia & (
                m.Player.previous_club_bonus_checked_at.is_(None)
                | (m.Player.previous_club_bonus_checked_at < revisar_desde)
            )
        reventa = await ids(vigilancia)
        return {
            "ficha": ficha,
            "precio": precio,
            "destino": destino,
            "censo": censo,
            "reventa": reventa,
        }

    async def _sync_active_roster_player_details(
        self,
        uow: UnitOfWork,
        team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """2026-08-05, pedido explícitamente: `playerdetails.xml` (LastMatch,
        Caps/CapsU20, CareerAssists) ya no se queda esperando el botón
        "Actualizar detalles de jugadores", se pide para TODA la plantilla
        activa en cada sync normal, una llamada CHPP por jugador. A
        diferencia del backfill de vendidos (una vez y listo), esto SÍ se
        repite cada sync porque LastMatch/Caps cambian semana a semana
        mientras el jugador sigue jugando."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        jugadores = (
            await uow.session.execute(
                select(
                    m.Player.ht_player_id,
                    m.Player.first_name,
                    m.Player.last_name,
                ).where(
                    m.Player.team_id == team_id,
                    m.Player.left_team_at.is_(None),
                    ~m.Player.ht_player_id_is_transfer,
                )
            )
        ).all()
        for ht_player_id, first_name, last_name in jugadores:
            nombre = _full_player_name(first_name, last_name)
            await _report(on_progress, f"Descargando ficha de jugador {nombre}...")
            try:
                wrote = await self._apply_player_details(uow, ht_player_id, captured_at)
                result.snapshots_written += 1 if wrote else 0
            except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                result.errors.append(f"{_nombre_legible('playerdetails')} ({ht_player_id}): {exc}")
                await _tras_fallo(uow, exc)
                result.status = "partial"

    async def _apply_player_enrichment(
        self, uow: UnitOfWork, ht_player_id: int, fetched_at: datetime
    ) -> bool:
        """Núcleo de `execute_player_enrichment_backfill`, recibe un `uow`
        YA ABIERTO en vez de abrir el suyo, para poder llamarse tanto desde
        ahí como desde `execute()` (el `async with self._uow` de
        `SqlAlchemyUnitOfWork` no es reentrante: abrir uno anidado
        reemplazaría/cerraría la sesión del de fuera a medio sync)."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        payload = await self._chpp.fetch(
            "playerdetails",
            version=FILE_VERSIONS["playerdetails"],
            playerID=ht_player_id,
        )
        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if player is None:
            return False

        if payload.get("chpp_error"):
            # ID que ya no resuelve en Hattrick (ver `_is_chpp_error`), no
            # es un fallo transitorio, así que se marca para no volver a
            # pedirlo nunca (ver `enrichment_attempted` en models.py).
            player.enrichment_attempted = True
            return True

        # El salario, incluso de alguien que ya juega en otro club: Hattrick lo
        # sigue devolviendo. Para un jugador que entro y salio entre dos
        # sincronizaciones esta es la UNICA fuente, porque no dejo snapshots.
        salario = payload.get("salary") or 0
        if salario and player.last_known_salary != salario:
            player.last_known_salary = salario

        age_years = payload.get("age_years")
        age_days = payload.get("age_days")
        if (
            player.sold_at is not None
            and player.age_years_at_sale is None
            and age_years is not None
            and age_days is not None
        ):
            elapsed_days = (fetched_at - player.sold_at).days
            try:
                at_sale = Age(age_years, age_days).add_days(-elapsed_days)
            except ValueError:
                # Nunca se inventa una edad, si la resta da negativo se
                # deja tal cual, no se fuerza un número.
                pass
            else:
                player.age_years_at_sale = at_sale.years
                player.age_days_at_sale = at_sale.days
        # 2026-08-05: misma reconstrucción, ancla en `purchased_at` en vez
        # de `sold_at`, para TODO jugador con compra conocida, esté o no
        # vendido (pedida para "Edad de compra" en Detalle).
        if (
            player.purchased_at is not None
            and player.age_years_at_purchase is None
            and age_years is not None
            and age_days is not None
        ):
            elapsed_days = (fetched_at - player.purchased_at).days
            try:
                at_purchase = Age(age_years, age_days).add_days(-elapsed_days)
            except ValueError:
                pass
            else:
                player.age_years_at_purchase = at_purchase.years
                player.age_days_at_purchase = at_purchase.days

        native_league_name = payload.get("native_league_name")
        if not native_league_name:
            native_league_id = payload.get("native_league_id")
            native_country_id = payload.get("native_country_id")
            world = None
            if native_league_id:
                world = await uow.session.scalar(
                    select(m.WorldContext).where(m.WorldContext.ht_league_id == native_league_id)
                )
            if world is None and native_country_id:
                world = await uow.session.scalar(
                    select(m.WorldContext).where(m.WorldContext.country_id == native_country_id)
                )
            native_league_name = world.country_name if world is not None else None
        if player.native_country is None and native_league_name:
            player.native_country = native_league_name
        if player.agreeability is None and payload.get("agreeability") is not None:
            player.agreeability = payload["agreeability"]
        if player.specialty is None and payload.get("specialty") is not None:
            player.specialty = payload["specialty"]
        # 2026-08-04: MotherClub/TeamID, "canterano" real (ver corrección en
        # parse_playerdetails). 0 = sin MotherClub en el XML, se guarda tal
        # cual (nunca coincide con un ht_team_id real, así que no hace falta
        # tratarlo distinto de "no es canterano de nadie").
        if player.mother_club_team_id is None and payload.get("mother_club_team_id") is not None:
            player.mother_club_team_id = payload["mother_club_team_id"]

        # 2026-08-05, pedido explícitamente: "backfill de un jugador máximo
        # una vez", si algún campo sigue sin poder rellenarse tras ESTE
        # intento (típicamente la edad reconstruida hacia atrás: si dio
        # negativo una vez, va a dar negativo siempre, es una resta contra
        # "hoy" cuyo margen no cambia con el tiempo, porque tanto la edad
        # actual como los días transcurridos avanzan al mismo ritmo), no
        # tiene sentido volver a pedir playerdetails.xml para este jugador
        # nunca más.
        player.enrichment_attempted = True
        return True

    async def execute_player_enrichment_backfill(
        self, cmd: SyncPlayerEnrichmentCommand
    ) -> SyncResult:
        """HL-161: UNA llamada a playerdetails.xml por jugador vendido que
        rellena edad-en-la-venta (si hace falta), país de origen, carácter
        y especialidad.

        Edad: función pura del tiempo transcurrido (112 días por "año", sin
        entrenamiento ni azar), se resta a la edad de HOY los días reales
        desde `sold_at`. Solo se toca si no hay ya un `player_snapshots` de
        antes de la venta (ese dato real siempre gana). País/carácter/
        especialidad casi no cambian con el tiempo, así que el valor de HOY
        sirve de base razonable aunque el jugador ya no esté en el equipo
        se rellenan siempre que falten, sin importar si hay snapshot previo.
        `playerdetails.xml` funciona para cualquier `playerID` aunque ya no
        esté en nuestro equipo (verificado en vivo 2026-08-04)."""
        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind=f"player_enrichment:{cmd.ht_player_id}"
            )
            result = SyncResult(sync_id=sync_id, status="completed")
            fetched_at = datetime.now(UTC).replace(tzinfo=None)

            try:
                wrote = await self._apply_player_enrichment(uow, cmd.ht_player_id, fetched_at)
                if wrote:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001, mismo patrón que execute_transfers_player
                result.errors.append(f"{_nombre_legible('player_enrichment')}: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _fichas_de_los_sin_identificador(
        self,
        uow: UnitOfWork,
        team_id: int,
        movimientos: list[Any],
        jugadores: dict[int, Any],
    ) -> dict[int, int]:
        """Una ficha por PERSONA entre los movimientos sin identificador.

        Emparejar por nombre es el ultimo recurso y solo se usa aqui, entre
        huerfanos: a un jugador con identificador propio no se le toca nunca,
        aunque se llame igual. Sin esto, la compra y la venta de la misma
        persona son dos transferencias distintas, cada una con su numero
        prestado, y salen como dos medias filas --una que parece perdida total
        y otra que no suma nada-- en vez de una etapa con su saldo.

        Un nombre vacio no agrupa a nadie: se queda solo, que es lo prudente.

        Devuelve, por cada movimiento huerfano, a que ficha pertenece.
        """
        from app.infrastructure.db import models as m

        por_nombre: dict[str, int] = {}
        de_quien: dict[int, int] = {}
        nuevos = False
        for mov in sorted(movimientos, key=lambda x: (x.deadline, x.ht_transfer_id)):
            if not self._es_huerfano(mov):
                continue
            nombre = self._nombre_para_agrupar(mov)
            # El identificador de la persona es el de su PRIMER movimiento.
            clave = por_nombre.get(nombre) if nombre else None
            if clave is None:
                clave = mov.ht_player_id
                if nombre:
                    por_nombre[nombre] = clave
            de_quien[mov.ht_transfer_id] = clave
            if clave in jugadores:
                continue
            apellido = nombre.rsplit(" ", 1)[-1] if " " in nombre else nombre
            jugador = m.Player(
                ht_player_id=clave,
                ht_player_id_is_transfer=True,
                team_id=team_id,
                first_name=nombre[: -len(apellido) - 1] if apellido != nombre else "",
                last_name=apellido or "?",
            )
            uow.session.add(jugador)
            jugadores[clave] = jugador
            nuevos = True
        if nuevos:
            await uow.session.flush()
        return de_quien

    async def _misma_ficha_o_la_de_seleccion(
        self,
        payload: dict[str, Any],
        ht_match_id: int,
        jugado_el: datetime | None,
    ) -> dict[str, Any]:
        """Comprueba que la ficha sea de ESTE partido, y si no, la pide bien.

        Los partidos de seleccion viven en otro espacio de identificadores, el
        que CHPP llama `HTOIntegrated`. Pedir uno de ellos sin decirlo no da un
        error: da OTRO partido, uno de club con el mismo numero. Verificado en
        vivo con el 41943634 --seleccion, 2026-- que sin la marca devuelve un
        partido de liga de 2005.

        Como la casilla "ultimo partido" del jugador ya trae la fecha real, se
        compara: si la ficha que llego es de otro dia, no es este partido, y se
        vuelve a pedir en el otro espacio. Sin fecha con que comparar no se
        puede saber, y se deja lo que vino.
        """
        if jugado_el is None:
            return payload
        # La fecha puede llegar con huso (recien parseada) o sin el (leida de
        # la base): las dos formas conviven en el mismo campo.
        if jugado_el.tzinfo is not None:
            jugado_el = jugado_el.astimezone(UTC).replace(tzinfo=None)

        def _mismo_dia(crudo: str) -> bool:
            # `ht_to_utc` devuelve con huso y la base guarda sin el: se comparan
            # los dos en UTC ingenuo, como el resto de la aplicacion.
            cuando = ht_to_utc(crudo or "")
            if cuando is None:
                return False
            if cuando.tzinfo is not None:
                cuando = cuando.astimezone(UTC).replace(tzinfo=None)
            return abs((cuando - jugado_el).days) <= 1

        if _mismo_dia(payload.get("match_date", "")):
            return payload
        try:
            otra = await self._chpp.fetch(
                "matchdetails",
                version=FILE_VERSIONS["matchdetails"],
                matchID=ht_match_id,
                sourceSystem="htointegrated",
            )
        except Exception:  # noqa: BLE001, best effort, ver docstring
            return payload
        if not otra.get("ht_match_id"):
            return payload
        return otra if _mismo_dia(otra.get("match_date", "")) else payload

    async def _cuadrar_fichas_prestadas(
        self,
        uow: UnitOfWork,
        team_id: int,
        etapas: list[Any],
        jugadores: dict[int, Any],
    ) -> None:
        """Deja las fichas prestadas coherentes con las etapas que quedaron.

        Dos salvaguardias:

        - Se marcan como IDAS. Ninguna tiene foto ni ficha en CHPP, asi que una
          que se quedara sin fecha de salida seria un jugador de la plantilla
          que no existe, y cualquier pantalla que liste "los que siguen" lo
          enseñaria.
        - Se borra la que no acabo en ninguna etapa. Al emparejar por nombre,
          varios movimientos pasan a compartir ficha y las sobrantes quedan
          huerfanas: sin esto se acumularian una relectura tras otra.
        """
        from sqlalchemy import delete

        from app.infrastructure.db import models as m

        ultima_salida: dict[int, Any] = {}
        for etapa in etapas:
            if etapa.left_at is None:
                continue
            previa = ultima_salida.get(etapa.ht_player_id)
            if previa is None or etapa.left_at > previa.left_at:
                ultima_salida[etapa.ht_player_id] = etapa

        con_etapa = {e.ht_player_id for e in etapas}
        sobrantes: list[int] = []
        for ht_player_id, jugador in jugadores.items():
            if not jugador.ht_player_id_is_transfer:
                continue
            if ht_player_id not in con_etapa:
                sobrantes.append(jugador.id)
                continue
            salida = ultima_salida.get(ht_player_id)
            if salida is not None:
                jugador.left_team_at = salida.left_at
                jugador.sold_at = salida.left_at
                jugador.sale_price = salida.sale_price

        if sobrantes:
            await uow.session.execute(delete(m.Player).where(m.Player.id.in_(sobrantes)))
