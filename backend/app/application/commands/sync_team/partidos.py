"""Partidos: calendario, detalles y censo de minutos.

Sale de partir `sync_team.py`, que tenia 7257 lineas en un
solo fichero, 6567 de ellas una sola clase. `SyncTeamHandler` se monta
con este mixin y los demas, asi que los `self.` siguen valiendo igual.
"""

from datetime import UTC, datetime
from typing import Any

from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.comun import (
    AUTOMATIC_MATCH_DETAILS_WINDOW,
    DETALLES_HISTORICOS_EN_PARALELO,
    FILE_VERSIONS,
    MATCH_ARCHIVE_FALLBACK_START,
    MATCH_ARCHIVE_INCREMENTAL_OVERLAP,
    MATCH_ARCHIVE_MIN_WINDOW,
    MATCH_ARCHIVE_RANGE_TOLERANCE,
    MATCH_ARCHIVE_RESPONSE_LIMIT,
    MATCH_ARCHIVE_WINDOW,
    MATCHLINEUP_ROLE_VERSION,
    VERSION_DEL_ARCHIVO,
    ProgressReporter,
    SyncMatchDetailsCommand,
    SyncResult,
    _as_change_row,
    _nombre_legible,
    _report,
    _tras_fallo,
    aforo_del_estadio,
)
from app.domain.engines.sync_diff import MatchState, diff_match
from app.domain.engines.youth_arrival import cuando_cumplio_diecisiete
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_constants import MATCH_TYPE_CUP
from app.domain.value_objects.ht_time import ht_to_utc


class PartidosMixin(BaseDeSync):
    """Partidos: calendario, detalles y censo de minutos."""

    async def execute_match_details(self, cmd: SyncMatchDetailsCommand) -> SyncResult:
        """Ratings por sector y eventos de un partido terminado. HL-071/072.

        Idempotente por ht_match_id: si ya hay ratings para este partido, no
        se vuelve a pedir ni a escribir, el resultado de un partido jugado no
        cambia."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind=f"matchdetails:{cmd.ht_match_id}"
            )
            result = SyncResult(sync_id=sync_id, status="completed")

            already_ratings = await uow.session.scalar(
                select(m.MatchRating.id).where(m.MatchRating.ht_match_id == cmd.ht_match_id)
            )
            match = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == cmd.ht_match_id)
            )
            team = await uow.session.get(m.Team, cmd.team_id)
            is_own_home_match = bool(
                match is not None and team is not None and match.home_team_ht_id == team.ht_team_id
            )
            already_stadium = await uow.session.scalar(
                select(m.StadiumHistory.id).where(m.StadiumHistory.ht_match_id == cmd.ht_match_id)
            )
            if already_ratings and (not is_own_home_match or already_stadium):
                result.unchanged += 1
                await uow.syncs.finalize(sync_id, status=result.status)
                await uow.commit()
                return result

            try:
                payload = await self._chpp.fetch(
                    "matchdetails",
                    version=FILE_VERSIONS["matchdetails"],
                    matchID=cmd.ht_match_id,
                )
                self._persist_match_details(
                    uow,
                    payload,
                    result,
                    team_id=cmd.team_id,
                    match=match,
                    write_ratings=not bool(already_ratings),
                    write_stadium=is_own_home_match and not bool(already_stadium),
                    arena_capacity=cmd.arena_capacity,
                )
            except Exception as exc:  # noqa: BLE001, mismo patrón que execute()
                result.errors.append(f"{_nombre_legible('matchdetails')}: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _persist_matches(
        self, uow: UnitOfWork, ht_team_id: int, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """Calendario y resultados: HL-070. Un partido no es un snapshot, es un
        hecho que se actualiza in-place (upcoming → finished) y se identifica
        por `ht_match_id`, único en CHPP."""
        from sqlalchemy import select

        from app.domain.value_objects.ht_constants import NON_OFFICIAL_MATCH_TYPES
        from app.infrastructure.db import models as m

        for mt in payload.get("matches", []):
            ht_match_id = mt["ht_match_id"]
            row = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == ht_match_id)
            )
            date_str = mt.get("match_date", "")
            played_at = ht_to_utc(date_str) or datetime.now(UTC)
            before = (
                MatchState(row.status, row.home_goals, row.away_goals) if row is not None else None
            )
            if row is None:
                row = m.Match(ht_match_id=ht_match_id, played_at=played_at)
                uow.session.add(row)
                result.snapshots_written += 1
            elif (
                row.status == mt.get("status", "")
                and row.home_goals == mt.get("home_goals", -1)
                and row.away_goals == mt.get("away_goals", -1)
                and row.cup_level == mt.get("cup_level", -1)
                and row.cup_level_index == mt.get("cup_level_index", -1)
                and row.source_system == mt.get("source_system")
                and row.orders_given == mt.get("orders_given")
            ):
                result.unchanged += 1
                continue
            else:
                result.snapshots_written += 1
            row.played_at = played_at
            row.match_type = mt.get("match_type", 0)
            row.status = mt.get("status", "")
            row.home_team_ht_id = mt.get("home_team_id", 0)
            row.away_team_ht_id = mt.get("away_team_id", 0)
            row.home_team_name = mt.get("home_team_name", "")
            row.away_team_name = mt.get("away_team_name", "")
            row.home_goals = mt.get("home_goals", -1)
            row.away_goals = mt.get("away_goals", -1)
            row.cup_level = mt.get("cup_level", -1)
            row.cup_level_index = mt.get("cup_level_index", -1)
            row.source_system = mt.get("source_system")
            row.orders_given = mt.get("orders_given")

            # Escaleras, Duelos, Torneos y Preparación no son partidos reales
            # pedido explícito 2026-08-11: no deben aparecer como "Ganaste/
            # Perdiste" en el feed de cambios, igual que se ignoran en todos
            # los demás lugares de la herramienta.
            is_home = row.home_team_ht_id == ht_team_id
            opponent = row.away_team_name if is_home else row.home_team_name
            after = MatchState(row.status, row.home_goals, row.away_goals)
            change = (
                diff_match(before, after, is_home, opponent)
                if row.match_type not in NON_OFFICIAL_MATCH_TYPES
                else None
            )
            if change:
                result.changes.append(_as_change_row(change))

    def _persist_match_details(
        self,
        uow: UnitOfWork,
        payload: dict[str, Any],
        result: SyncResult,
        *,
        team_id: int,
        match: Any | None,
        write_ratings: bool,
        write_stadium: bool,
        arena_capacity: dict[str, int] | None,
    ) -> None:
        from app.infrastructure.db import models as m

        ht_match_id = payload.get("ht_match_id", 0)
        if not ht_match_id:
            return

        if write_ratings:
            for side in ("home", "away"):
                team = payload.get(side) or {}
                if not team:
                    continue
                ratings = team.get("ratings", {})
                chances = team.get("chances", {})
                uow.session.add(
                    m.MatchRating(
                        ht_match_id=ht_match_id,
                        team_ht_id=team.get("team_id", 0),
                        is_home=(side == "home"),
                        midfield=ratings.get("midfield", 0),
                        right_def=ratings.get("right_def", 0),
                        central_def=ratings.get("central_def", 0),
                        left_def=ratings.get("left_def", 0),
                        right_att=ratings.get("right_att", 0),
                        central_att=ratings.get("central_att", 0),
                        left_att=ratings.get("left_att", 0),
                        # `None` y no 0 cuando falten: un 0 es un rating real
                        # bajísimo, y el modelo de predicción no puede
                        # distinguir «defendió fatal el balón parado» de «este
                        # partido se guardó antes de que leyéramos el campo».
                        set_pieces_def=ratings.get("set_pieces_def"),
                        set_pieces_att=ratings.get("set_pieces_att"),
                        tactic_type=team.get("tactic_type", 0),
                        tactic_skill=team.get("tactic_skill", 0),
                        # CHPP nunca trae <TeamAttitude> para el lado que no es
                        # el del usuario (verificado en vivo), sin la bandera
                        # `attitude_is_read`, ese "sin dato" se guardaría como el
                        # -1 por defecto del parser, indistinguible del código
                        # real -1 ("Jugar relajados").
                        attitude=team.get("attitude") if team.get("attitude_is_read") else None,
                        possession_first_half=payload.get("possession", {}).get(
                            f"first_half_{side}", 50
                        ),
                        possession_second_half=payload.get("possession", {}).get(
                            f"second_half_{side}", 50
                        ),
                        chances_left=chances.get("left", 0),
                        chances_center=chances.get("center", 0),
                        chances_right=chances.get("right", 0),
                        chances_special=chances.get("special", 0),
                        chances_other=chances.get("other", 0),
                    )
                )
                result.snapshots_written += 1

        if write_stadium and match is not None:
            arena = payload.get("arena") or {}
            capacity = arena_capacity or {}
            sold_total = arena.get("spectators", 0)
            uow.session.add(
                m.StadiumHistory(
                    team_id=team_id,
                    ht_match_id=ht_match_id,
                    played_at=match.played_at,
                    match_type=match.match_type,
                    weather=arena.get("weather", -1),
                    # Si arenadetails no llegó, se conserva el mínimo observable
                    # y la consulta declara que el desglose es derivado.
                    capacity_total=max(capacity.get("total", 0), sold_total),
                    capacity_terraces=capacity.get("terraces") or None,
                    capacity_basic=capacity.get("basic") or None,
                    capacity_roof=capacity.get("roof") or None,
                    capacity_vip=capacity.get("vip") or None,
                    sold_total=sold_total,
                    # El desglose por sector: se guarda para poder calcular la
                    # taquilla exacta, y no sale por ninguna respuesta de la
                    # API (2026-09-28, decision del usuario). `None` cuando el
                    # fichero no lo trae, que no es lo mismo que cero.
                    sold_terraces=arena.get("sold_terraces"),
                    sold_basic=arena.get("sold_basic"),
                    sold_roof=arena.get("sold_roof"),
                    sold_vip=arena.get("sold_vip"),
                )
            )
            result.snapshots_written += 1

    async def _sync_match_history(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None,
    ) -> None:
        """Carga una vez todo el archivo y luego sólo su cola nueva.

        La primera sincronización va desde FoundedDate hasta el instante del
        clic. Sólo cuando recorrió el rango entero se sella
        `matches_history_complete`; un fallo no deja un hueco silencioso. En
        sincronizaciones posteriores se consulta desde la última marca con
        dos días de solape. Las filas existentes nunca se pisan: matches.xml
        conoce mejor el estado reciente y la deduplicación es por MatchID.

        Se guardan todos los tipos que CHPP expone. La pantalla Partidos ya
        decide qué mostrar (competitivos por defecto, amistosos con toggle y
        no oficiales fuera), así que el almacenamiento no destruye datos que
        otra funcionalidad pueda necesitar después.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)
        if team is None:
            return

        until = (
            captured_at.astimezone(UTC) if captured_at.tzinfo else captured_at.replace(tzinfo=UTC)
        )
        cursor = team.matches_history_synced_until
        if cursor is not None:
            cursor = cursor.astimezone(UTC) if cursor.tzinfo else cursor.replace(tzinfo=UTC)
        founded = team.founded_at
        if founded is not None:
            founded = founded.astimezone(UTC) if founded.tzinfo else founded.replace(tzinfo=UTC)
        if founded is None or founded > until:
            founded = MATCH_ARCHIVE_FALLBACK_START

        # Un historial sellado con reglas viejas no está completo, lo diga o no
        # la marca: se relee entero una vez y se vuelve a sellar.
        initial = (
            not team.matches_history_complete
            or cursor is None
            or (team.matches_history_version or 0) < VERSION_DEL_ARCHIVO
        )
        since = founded if initial else max(founded, cursor - MATCH_ARCHIVE_INCREMENTAL_OVERLAP)
        await _report(
            on_progress,
            (
                "Importando por primera vez todos tus partidos anteriores..."
                if initial
                else "Buscando partidos nuevos desde la última sincronización..."
            ),
        )

        try:
            archived = await self._fetch_match_archive_range(ht_team_id, since, until, on_progress)
        except Exception as exc:  # noqa: BLE001, el resto del sync sigue siendo útil
            result.errors.append(f"{_nombre_legible('matchesarchive')}: {exc}")
            result.status = "partial"
            return

        # Una respuesta partida repite bordes; además un proveedor de prueba
        # puede repetir filas. Ninguno debe llegar dos veces al índice UNIQUE.
        # El archivo puede alcanzar el partido que se está jugando: en ese
        # caso no trae goles y no permite distinguir UPCOMING de ONGOING. Lo
        # deja manejar a matches.xml y el solape incremental lo recogerá ya
        # terminado; jamás se fabrica FINISHED -1:-1.
        by_id = {
            mt["ht_match_id"]: mt
            for mt in archived
            if mt.get("ht_match_id")
            and mt.get("home_goals", -1) >= 0
            and mt.get("away_goals", -1) >= 0
        }
        ids = list(by_id)
        existing: set[int] = set()
        if ids:
            existing = set(
                (
                    await uow.session.execute(
                        select(m.Match.ht_match_id).where(m.Match.ht_match_id.in_(ids))
                    )
                )
                .scalars()
                .all()
            )

        detail_cutoff = until - AUTOMATIC_MATCH_DETAILS_WINDOW
        for ht_match_id, mt in by_id.items():
            if ht_match_id in existing:
                continue
            played_at = ht_to_utc(mt.get("match_date", "")) or until
            uow.session.add(
                m.Match(
                    ht_match_id=ht_match_id,
                    played_at=played_at,
                    match_type=mt.get("match_type", 0),
                    status="FINISHED",
                    home_team_ht_id=mt.get("home_team_id", 0),
                    away_team_ht_id=mt.get("away_team_id", 0),
                    home_team_name=mt.get("home_team_name", ""),
                    away_team_name=mt.get("away_team_name", ""),
                    home_goals=mt.get("home_goals", -1),
                    away_goals=mt.get("away_goals", -1),
                    cup_level=mt.get("cup_level", -1),
                    cup_level_index=mt.get("cup_level_index", -1),
                    source_system=mt.get("source_system"),
                    history_summary_only=played_at < detail_cutoff,
                )
            )
            result.snapshots_written += 1
            result.rescued_matches += 1

        team.matches_history_complete = True
        team.matches_history_synced_until = until
        team.matches_history_version = VERSION_DEL_ARCHIVO
        await _report(
            on_progress,
            (
                f"Historial de partidos completo: {result.rescued_matches} nuevos guardados."
                if initial
                else f"Partidos actualizados: {result.rescued_matches} nuevos guardados."
            ),
        )

    async def _backfill_missing_match_details(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """2026-08-05, pedido explícitamente: "sincroniza todos los xml que
        importen cada vez que sincronizamos", HatStats y el desglose por
        sector ya no se quedan en "-" esperando el botón "Sincronizar
        detalles" de Partidos. `matches.xml` solo trae calendario y
        resultado; `matchdetails.xml` se pide por partido, así que se
        recorre aquí cualquier partido TERMINADO reciente del propio club al
        que le falten ratings, o (si fue de local) el aforo del partido
        mismo criterio que ya usaba ese botón (`trigger_match_details_sync`).
        Los resúmenes antiguos importados en bloque se omiten aquí: pedir su
        detalle sigue siendo posible de forma explícita, pero no hace parte
        del alta inicial.
        Un resultado ya jugado no cambia, así que esto es "una vez por
        partido, para siempre": la propia ausencia de la fila es el gate,
        sin necesitar un flag "attempted" aparte."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        ratings_missing = ~m.Match.ht_match_id.in_(select(m.MatchRating.ht_match_id))
        stadium_missing_on_home = (
            m.Match.home_team_ht_id == ht_team_id
        ) & ~m.Match.ht_match_id.in_(select(m.StadiumHistory.ht_match_id))
        pending = (
            (
                await uow.session.execute(
                    select(m.Match.ht_match_id).where(
                        (m.Match.home_team_ht_id == ht_team_id)
                        | (m.Match.away_team_ht_id == ht_team_id),
                        m.Match.status.ilike("finished"),
                        # El alta histórica guarda todos los marcadores, pero
                        # no debe convertirse en cientos de llamadas
                        # matchdetails dentro del mismo clic. Esos detalles
                        # antiguos los completa `_completar_detalles_historicos`
                        # por tandas, una en cada sync.
                        m.Match.history_summary_only.is_(False),
                        (ratings_missing | stadium_missing_on_home),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not pending:
            return

        arena_capacity: dict[str, int] | None = None
        try:
            arena_capacity = await aforo_del_estadio(self._chpp, ht_team_id, result)
        except Exception as exc:  # noqa: BLE001, no invalida ratings si falla solo el aforo
            result.errors.append(f"{_nombre_legible('arenadetails')}: {exc}")

        for ht_match_id in pending:
            await _report(on_progress, f"Descargando detalles de partido {ht_match_id}...")
            try:
                already_ratings = await uow.session.scalar(
                    select(m.MatchRating.id).where(m.MatchRating.ht_match_id == ht_match_id)
                )
                match = await uow.session.scalar(
                    select(m.Match).where(m.Match.ht_match_id == ht_match_id)
                )
                is_own_home_match = bool(match is not None and match.home_team_ht_id == ht_team_id)
                already_stadium = await uow.session.scalar(
                    select(m.StadiumHistory.id).where(m.StadiumHistory.ht_match_id == ht_match_id)
                )
                payload = await self._chpp.fetch(
                    "matchdetails",
                    version=FILE_VERSIONS["matchdetails"],
                    matchID=ht_match_id,
                )
                # Defensivo: `_persist_match_details` confía en
                # `payload["ht_match_id"]`, no en el ID pedido, nunca debería
                # discrepar contra CHPP real (cada matchID pedido trae SU
                # propio partido), pero este método es el primero que pide
                # varios matchID distintos en el mismo lote, así que una
                # respuesta que no correspondiera al partido pedido no debe
                # escribirse contra la fila de OTRO partido.
                if payload.get("ht_match_id") != ht_match_id:
                    continue
                self._persist_match_details(
                    uow,
                    payload,
                    result,
                    team_id=team_id,
                    match=match,
                    write_ratings=not bool(already_ratings),
                    write_stadium=is_own_home_match and not bool(already_stadium),
                    arena_capacity=arena_capacity,
                )
            except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                result.errors.append(f"{_nombre_legible('matchdetails')} ({ht_match_id}): {exc}")
                await _tras_fallo(uow, exc)
                result.status = "partial"

    async def _completar_detalles_historicos(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """La historia completa de Partidos, de una vez (2026-09-14).

        La primera sincronización trae del archivo TODOS los partidos del club
        desde su fundación, pero sólo con marcador; el detalle --ratings por
        sector, ocasiones, asistencia-- cuesta una llamada `matchdetails` por
        partido. Esos partidos quedan marcados `history_summary_only`.

        Aquí se completan TODOS en ese mismo sync, pidiendo
        `DETALLES_HISTORICOS_EN_PARALELO` a la vez y guardándolos en orden, del
        más reciente al más antiguo. Después no queda ninguno y esto no hace
        nada: desde entonces sólo entra lo nuevo, que ya llega con su detalle en
        el sync normal. Nada se pide dos veces: la marca se quita al guardar.

        Sólo oficiales y amistosos. Torneos, escaleras, duelos y preparación no
        se muestran en Partidos, y sólo las escaleras de un club activo son
        decenas por temporada.

        Si Hattrick responde sin el partido, también se quita la marca: pedirlo
        otra vez daría lo mismo. Un fallo de red, en cambio, la deja puesta y
        ese partido se reintenta en el siguiente sync.
        """
        import asyncio

        from sqlalchemy import select

        from app.domain.value_objects.ht_constants import NON_OFFICIAL_MATCH_TYPES
        from app.infrastructure.db import models as m

        pendientes = (
            (
                await uow.session.execute(
                    select(m.Match)
                    .where(
                        (m.Match.home_team_ht_id == ht_team_id)
                        | (m.Match.away_team_ht_id == ht_team_id),
                        m.Match.history_summary_only.is_(True),
                        m.Match.status.ilike("finished"),
                        m.Match.home_goals >= 0,
                        m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES),
                    )
                    .order_by(m.Match.played_at.desc())
                )
            )
            .scalars()
            .all()
        )
        if not pendientes:
            return
        total = len(pendientes)

        arena_capacity: dict[str, int] | None = None
        try:
            arena_capacity = await aforo_del_estadio(self._chpp, ht_team_id, result)
        except Exception as exc:  # noqa: BLE001, no invalida ratings si falla sólo el aforo
            result.errors.append(f"{_nombre_legible('arenadetails')}: {exc}")

        # Las llamadas van en paralelo; la base, en cambio, se toca en orden y
        # desde un solo sitio, porque la sesión no admite escrituras cruzadas.
        semaforo = asyncio.Semaphore(DETALLES_HISTORICOS_EN_PARALELO)
        traidos = 0

        async def pedir(ht_match_id: int) -> dict[str, Any] | Exception:
            nonlocal traidos
            async with semaforo:
                try:
                    payload = await self._chpp.fetch(
                        "matchdetails",
                        version=FILE_VERSIONS["matchdetails"],
                        matchID=ht_match_id,
                    )
                except Exception as exc:  # noqa: BLE001, se reintenta en el siguiente sync
                    return exc
                traidos += 1
                if traidos % 10 == 0 or traidos == total:
                    await _report(
                        on_progress,
                        f"Trayendo tus partidos antiguos: {traidos} de {total}...",
                    )
                return payload

        respuestas = await asyncio.gather(*(pedir(p.ht_match_id) for p in pendientes))

        for match, respuesta in zip(pendientes, respuestas, strict=True):
            try:
                if isinstance(respuesta, Exception):
                    raise respuesta
                payload = respuesta
                # Sin <Match> en la respuesta --un chpperror, o un partido que
                # Hattrick ya no enseña-- el lector devuelve vacío. Es una
                # respuesta, no un fallo de red: reintentarla daría lo mismo.
                if not payload.get("ht_match_id") or payload.get("chpp_error"):
                    match.history_summary_only = False
                    result.errors.append(
                        f"{_nombre_legible('matchdetails')} ({match.ht_match_id}): "
                        "Hattrick no dio el detalle"
                    )
                    continue
                if payload.get("ht_match_id") != match.ht_match_id:
                    continue
                ya_ratings = await uow.session.scalar(
                    select(m.MatchRating.id).where(m.MatchRating.ht_match_id == match.ht_match_id)
                )
                ya_estadio = await uow.session.scalar(
                    select(m.StadiumHistory.id).where(
                        m.StadiumHistory.ht_match_id == match.ht_match_id
                    )
                )
                self._persist_match_details(
                    uow,
                    payload,
                    result,
                    team_id=team_id,
                    match=match,
                    write_ratings=not bool(ya_ratings),
                    write_stadium=match.home_team_ht_id == ht_team_id and not bool(ya_estadio),
                    arena_capacity=arena_capacity,
                )
                match.history_summary_only = False
            except Exception as exc:  # noqa: BLE001, sync parcial, se reintenta en el siguiente
                result.errors.append(
                    f"{_nombre_legible('matchdetails')} ({match.ht_match_id}): {exc}"
                )
                await _tras_fallo(uow, exc)
                result.status = "partial"

    async def _fetch_match_archive_interval(
        self,
        ht_team_id: int,
        since: datetime,
        until: datetime,
        on_progress: ProgressReporter | None,
    ) -> list[dict[str, Any]]:
        """Descarga un intervalo completo pese al límite de 50 de CHPP.

        `matchesarchive` no tiene pageIndex ni cursor. Cuando devuelve 50, el
        intervalo se considera potencialmente truncado y se biseca. Los dos
        lados comparten el instante central a propósito; el solape se elimina
        por MatchID y evita perder un partido exactamente en el borde.
        """
        await _report(
            on_progress,
            f"Descargando historial de partidos ({since:%Y-%m-%d} → {until:%Y-%m-%d})...",
        )
        payload = await self._chpp.fetch(
            "matchesarchive",
            version=FILE_VERSIONS["matchesarchive"],
            teamID=ht_team_id,
            FirstMatchDate=since.strftime("%Y-%m-%d %H:%M:%S"),
            LastMatchDate=until.strftime("%Y-%m-%d %H:%M:%S"),
        )
        if payload.get("chpp_error"):
            code = payload.get("chpp_error_code", 0)
            message = payload.get("chpp_error_message") or "respuesta CHPP inválida"
            raise RuntimeError(f"CHPP {code}: {message}")

        matches = [mt for mt in payload.get("matches", []) if mt.get("ht_match_id")]
        # Si Hattrick ignoró el rango, contesta con otros partidos y sin error.
        # Tomarlos por buenos sellaría un historial con agujeros: se falla.
        for mt in matches:
            jugado = ht_to_utc(mt.get("match_date", ""))
            if jugado is not None and not (
                since - MATCH_ARCHIVE_RANGE_TOLERANCE
                <= jugado
                <= until + MATCH_ARCHIVE_RANGE_TOLERANCE
            ):
                raise RuntimeError(
                    f"Hattrick ignoró el rango {since:%Y-%m-%d} → {until:%Y-%m-%d} "
                    f"(devolvió un partido del {jugado:%Y-%m-%d})"
                )
        if len(matches) < MATCH_ARCHIVE_RESPONSE_LIMIT or until - since <= MATCH_ARCHIVE_MIN_WINDOW:
            return matches

        midpoint = since + (until - since) / 2
        if midpoint <= since or midpoint >= until:
            return matches
        left = await self._fetch_match_archive_interval(ht_team_id, since, midpoint, on_progress)
        right = await self._fetch_match_archive_interval(ht_team_id, midpoint, until, on_progress)
        return list({mt["ht_match_id"]: mt for mt in (*left, *right)}.values())

    async def _fetch_match_archive_range(
        self,
        ht_team_id: int,
        since: datetime,
        until: datetime,
        on_progress: ProgressReporter | None,
    ) -> list[dict[str, Any]]:
        """Un rango de cualquier largo, en ventanas de `MATCH_ARCHIVE_WINDOW`.

        Cada ventana pasa por `_fetch_match_archive_interval`, que además la
        biseca si llega al tope de 50. Las ventanas comparten el borde y el
        solape se elimina por MatchID."""
        vistos: dict[int, dict[str, Any]] = {}
        inicio = since
        while inicio < until:
            fin = min(inicio + MATCH_ARCHIVE_WINDOW, until)
            for mt in await self._fetch_match_archive_interval(
                ht_team_id, inicio, fin, on_progress
            ):
                vistos[mt["ht_match_id"]] = mt
            inicio = fin
        return list(vistos.values())

    async def _backfill_foreign_match_type(
        self,
        uow: UnitOfWork,
        ht_match_id: int,
        jugado_el: datetime | None = None,
    ) -> None:
        """Crea la fila `Match` de un partido AJENO (selección nacional,
        Masters, juvenil...) que `playerdetails.xml` expuso vía `LastMatch`
        pero que `matches.xml`/`leaguefixtures.xml` nunca traen, esos solo
        ven los partidos del propio club. Sin esta fila, `experience_progress`
        (INNER JOIN contra `matches`) descarta el partido en silencio y ese
        tipo de experiencia (Masters, amistoso de selección, juvenil) nunca
        se cuenta, aunque LastMatch SÍ lo muestre.

        `matchdetails.xml` funciona para cualquier `matchID`, no solo los del
        equipo propio (mismo patrón que `playerdetails.xml` por `playerID`).
        Se pide una única vez por partido: si la fila ya existe, no se
        vuelve a pedir, un partido jugado no cambia de tipo ni de resultado.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        exists = await uow.session.scalar(
            select(m.Match.id).where(m.Match.ht_match_id == ht_match_id)
        )
        if exists is not None:
            return
        payload = await self._chpp.fetch(
            "matchdetails",
            version=FILE_VERSIONS["matchdetails"],
            matchID=ht_match_id,
        )
        if not payload.get("ht_match_id"):
            return  # chpp error / partido sin datos: nada que crear todavía
        payload = await self._misma_ficha_o_la_de_seleccion(payload, ht_match_id, jugado_el)
        date_str = payload.get("match_date", "")
        played_at = ht_to_utc(date_str) or datetime.now(UTC)
        home = payload.get("home") or {}
        away = payload.get("away") or {}
        uow.session.add(
            m.Match(
                ht_match_id=ht_match_id,
                played_at=played_at,
                match_type=payload.get("match_type", 0),
                cup_level=payload.get("cup_level", -1),
                cup_level_index=payload.get("cup_level_index", -1),
                status="FINISHED",
                home_team_ht_id=home.get("team_id", 0),
                away_team_ht_id=away.get("team_id", 0),
                home_team_name=home.get("name", ""),
                away_team_name=away.get("name", ""),
                home_goals=home.get("goals", -1),
                away_goals=away.get("goals", -1),
            )
        )

    async def _guardar_partidos_de_rivales(
        self,
        uow: Any,
        team_id: int,
        ht_team_id: int,
        result: Any,
        on_progress: ProgressReporter | None,
    ) -> None:
        """Deja en la base los últimos oficiales de cada contrincante.

        2026-09-09, pedido del usuario: «En Sync, vas a cargar los 5 partidos
        oficiales de cada contrincante de Liga de una, guárdalos para que no
        toque volverlos a llamar».

        POR QUÉ AQUÍ Y NO AL ABRIR LA FICHA. Es el mismo trabajo, pero hecho
        una vez en un momento en que el usuario ya está esperando, en vez de
        cada vez que mira a un rival. Y es incremental: la semana siguiente
        sólo baja la jornada nueva.

        NUNCA TUMBA EL SYNC. Los partidos de un equipo ajeno son una comodidad,
        no estado del club: si Hattrick no contesta se anota y se sigue. La
        ficha de rival volvería a pedirlos en vivo, que es como funcionaba
        antes de esto.
        """
        from sqlalchemy import or_, select

        from app.application.commands.partidos_de_rivales import (
            guardar_partidos_de_rivales,
        )
        from app.domain.value_objects.ht_constants import (
            MATCH_TYPE_LEAGUE,
            MATCH_TYPE_MASTERS,
            MATCH_TYPE_QUALIFICATION,
        )
        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        if equipo is None:
            return

        # LOS MISMOS CONTRINCANTES QUE YA SE VIGILAN para los fichajes: los
        # siete de tu serie y el rival del próximo cruce oficial, copa
        # incluida. Un amistoso no entra, y es lo que pidió el usuario: se
        # elige a mano entre millones de equipos, así que precargarlo sería
        # adivinar contra quién vas a querer mirar.
        rivales: set[int] = set()
        if equipo.series_ht_id is not None:
            filas = (
                await uow.session.execute(
                    select(m.Standing.team_ht_id)
                    .where(m.Standing.series_ht_id == equipo.series_ht_id)
                    .distinct()
                )
            ).all()
            rivales.update(f.team_ht_id for f in filas if f.team_ht_id != ht_team_id)

        proximos = (
            await uow.session.execute(
                select(m.Match).where(
                    or_(
                        m.Match.home_team_ht_id == ht_team_id,
                        m.Match.away_team_ht_id == ht_team_id,
                    ),
                    ~m.Match.status.ilike("finished"),
                    m.Match.match_type.in_(
                        {
                            MATCH_TYPE_CUP,
                            MATCH_TYPE_MASTERS,
                            MATCH_TYPE_QUALIFICATION,
                            MATCH_TYPE_LEAGUE,
                        }
                    ),
                )
            )
        ).scalars()
        for partido in proximos:
            es_local = partido.home_team_ht_id == ht_team_id
            rival_id = partido.away_team_ht_id if es_local else partido.home_team_ht_id
            if rival_id and rival_id != ht_team_id:
                rivales.add(rival_id)

        rivales.discard(0)
        if not rivales:
            return

        await _report(on_progress, "Guardando los últimos partidos de tus rivales...")
        try:
            resumen = await guardar_partidos_de_rivales(
                uow.session,
                self._chpp,
                rivales,
                FILE_VERSIONS["matches"],
                FILE_VERSIONS["matchdetails"],
            )
        except Exception as exc:  # noqa: BLE001, una comodidad no tumba el sync
            result.errors.append(f"partidos de rivales: {exc}")
            await _tras_fallo(uow, exc)
            return
        result.errors.extend(resumen.errores)
        if resumen.partidos_nuevos:
            await _report(
                on_progress,
                f"Guardados {resumen.partidos_nuevos} partidos nuevos "
                f"de {resumen.rivales} rivales.",
            )

    async def _reparar_partidos_ajenos_sin_ficha(self, uow: UnitOfWork) -> int:
        """Partidos con minutos guardados pero sin ficha, que nadie cuenta.

        Los minutos de un jugador salen de la casilla "ultimo partido" de su
        ficha, y esa casilla tambien atrapa partidos que no son de nuestro
        club: el ultimo que jugo en su equipo anterior, un amistoso
        internacional, un partido de seleccion. Para que cuenten hace falta
        ademas la ficha del partido, que dice de que tipo fue.

        `_backfill_foreign_match_type` la pide en el momento, pero solo desde
        que existe: los minutos guardados antes se quedaron sin ficha, y el
        calculo de experiencia los cruza con una union estricta, asi que los
        descartaba en silencio. Esto los recoge, y de paso cubre el caso de
        que aquella llamada fallara.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        huerfanos = (
            (
                await uow.session.execute(
                    select(m.PlayerMatchRating.ht_match_id)
                    .outerjoin(m.Match, m.Match.ht_match_id == m.PlayerMatchRating.ht_match_id)
                    .where(m.Match.id.is_(None), m.PlayerMatchRating.ht_match_id != 0)
                    .distinct()
                    .limit(self.RESCATES_DE_PARTIDO_POR_SYNC)
                )
            )
            .scalars()
            .all()
        )
        rescatados = 0
        for ht_match_id in huerfanos:
            # La fecha real la sabe la foto del jugador que vio ese partido, y
            # sin ella no hay forma de notar que la ficha que llega es de otro
            # partido con el mismo numero (ver `_misma_ficha_o_la_de_seleccion`).
            jugado_el = await uow.session.scalar(
                select(m.PlayerSnapshot.last_match_played_at)
                .where(m.PlayerSnapshot.last_match_ht_id == ht_match_id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
            try:
                await self._backfill_foreign_match_type(uow, ht_match_id, jugado_el=jugado_el)
            # Traga y sigue: un partido ajeno ilegible no puede cortar la
            # reparacion de los demas. Mismo riesgo que en `_best_recent_rating`.
            except Exception:  # noqa: BLE001, S112
                continue
            rescatados += 1
        return rescatados

    async def _censar_partidos_del_stint(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_player_id: int,
    ) -> bool:
        """Cuántos partidos jugó de verdad con nosotros, UNA vez por etapa.

        Es el trabajo más caro de toda la aplicación: el archivo de partidos
        de cada etapa cerrada y la alineación de cada uno para ver si llegó a
        jugar. La cola sigue agrupada por PlayerID, pero una pasada rellena
        todas las etapas pendientes de esa persona.

        "Jugó al menos un minuto" se decide por las estrellas: matchlineup
        no trae los minutos (comprobado: sus campos son PlayerID, RoleID,
        PositionCode, RatingStars, Behaviour), y un suplente que no entró
        trae 0 exacto, verificado en vivo el 2026-08-14.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        jugador = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if equipo is None or jugador is None:
            return False

        etapas = list(
            (
                await uow.session.execute(
                    select(m.PlayerStint)
                    .where(m.PlayerStint.player_id == jugador.id)
                    .order_by(m.PlayerStint.left_at, m.PlayerStint.arrived_at)
                )
            )
            .scalars()
            .all()
        )
        pendientes = [
            etapa
            for etapa in etapas
            if etapa.left_at is not None and etapa.games_played_for_us is None
        ]
        if not pendientes:
            return False

        una_sola_etapa = len(etapas) == 1
        ahora = datetime.now(UTC).replace(tzinfo=None)
        resultados: list[tuple[Any, int, datetime]] = []

        for etapa in pendientes:
            # El conteo legado solo es atribuible sin ambigüedad cuando el
            # jugador tuvo una única etapa. Esta vía repara de inmediato los
            # datos históricos (incluido un cero real) y no gasta CHPP.
            if una_sola_etapa and jugador.games_played_for_us is not None:
                resultados.append(
                    (
                        etapa,
                        jugador.games_played_for_us,
                        jugador.games_played_for_us_computed_at or ahora,
                    )
                )
                continue

            inicio = etapa.arrived_at
            if inicio is None and una_sola_etapa:
                inicio = jugador.purchased_at
            if inicio is None and etapa.from_academy:
                # La edad se midio en la venta legada mas reciente. Desde ese
                # punto se recupera la fecha estable en que cumplio 17, que
                # tambien sirve para su primera etapa aunque luego haya
                # regresado al club. No se guarda como una llegada observada.
                edad = self._edad_en_la_salida(jugador)
                fecha_de_esa_edad = jugador.sold_at or jugador.left_team_at
                if edad is not None and fecha_de_esa_edad is not None:
                    inicio = cuando_cumplio_diecisiete(edad, fecha_de_esa_edad)

            if inicio is None:
                # Etapa antigua sin compra, edad ni otro límite verificable:
                # sigue como desconocida. No se inventa 0 y la cola SQL no la
                # ofrece hasta que aparezca evidencia nueva.
                continue

            games = await self._games_played_for_us(
                equipo.ht_team_id,
                ht_player_id,
                inicio,
                etapa.left_at,
            )
            resultados.append((etapa, games, ahora))

        # No se modifica ninguna etapa hasta que TODAS las llamadas de esta
        # pasada terminan bien. Si falla un matchlineup, el jugador queda
        # intacto y vuelve a la cola en el próximo lote.
        for etapa, games, computed_at in resultados:
            etapa.games_played_for_us = games
            etapa.games_computed_at = computed_at

        # Player queda como espejo de compatibilidad para la ficha antigua.
        # Con varias etapas solo se reemplaza cuando ya conocemos todas las
        # cerradas, y entonces representa el total de todos sus pasos.
        cerradas = [etapa for etapa in etapas if etapa.left_at is not None]
        if cerradas and all(etapa.games_played_for_us is not None for etapa in cerradas):
            jugador.games_played_for_us = sum(etapa.games_played_for_us or 0 for etapa in cerradas)
            jugador.games_played_for_us_computed_at = max(
                (etapa.games_computed_at or ahora) for etapa in cerradas
            )

        return bool(resultados)

    async def _censar_partidos_de_seleccion(
        self,
        uow: UnitOfWork,
        team_id: int,
        captured_at: datetime,
        result: SyncResult,
    ) -> int:
        """Busca los partidos de seleccion que la ficha del jugador no alcanzo.

        El disparador es gratis: el contador de partidos internacionales de
        cada jugador ya se lee en cada sincronizacion. Si a nadie le subio, no
        se gasta ni una llamada. Y no se cuenta por ese contador --contarlo
        seria fiarse de una resta--: solo dice donde mirar. Los partidos se
        buscan de verdad, con su tipo y sus minutos.

        Ojo con lo que NO cubre: el listado de Hattrick solo trae selecciones
        absolutas y una ventana de un mes. Un partido de la sub-21, o uno de
        hace dos meses, no esta ahi; esos siguen contandose como punto ciego.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        candidatos = await self._a_quien_le_subio_el_contador(uow, team_id)
        if not candidatos:
            return 0

        listado = await self._chpp.fetch(
            "nationalteammatches",
            version=FILE_VERSIONS.get("nationalteammatches", "latest"),
        )
        partidos = listado.get("matches", [])
        if not partidos:
            return 0

        nombres: dict[int, str] = {}
        censados = 0
        for jugador, desde in candidatos:
            foto = await uow.session.scalar(
                select(m.PlayerSnapshot)
                .where(m.PlayerSnapshot.player_id == jugador.id)
                .order_by(m.PlayerSnapshot.captured_at.desc())
                .limit(1)
            )
            pais = await uow.session.scalar(
                select(m.WorldContext).where(
                    m.WorldContext.country_id == (foto.country_id if foto else 0)
                )
            )
            if pais is None or not pais.national_team_id:
                continue
            nombre = nombres.get(pais.national_team_id)
            if nombre is None:
                ficha = await self._chpp.fetch(
                    "nationalteamdetails",
                    version=FILE_VERSIONS.get("nationalteamdetails", "latest"),
                    teamId=pais.national_team_id,
                )
                nombre = ficha.get("team_name", "")
                nombres[pais.national_team_id] = nombre
            if not nombre:
                continue

            for partido in partidos:
                if nombre not in (partido["home_team_name"], partido["away_team_name"]):
                    continue
                cuando = ht_to_utc(partido["match_date"] or "")
                if cuando is None:
                    continue
                if cuando.tzinfo is not None:
                    cuando = cuando.astimezone(UTC).replace(tzinfo=None)
                if cuando <= desde or cuando > datetime.now(UTC).replace(tzinfo=None):
                    continue
                if await self._anotar_partido_de_seleccion(
                    uow,
                    jugador,
                    pais.national_team_id,
                    partido["ht_match_id"],
                    cuando,
                    captured_at,
                ):
                    censados += 1
                    result.snapshots_written += 1
        return censados

    async def _anotar_partido_de_seleccion(
        self,
        uow: UnitOfWork,
        jugador: Any,
        ht_team_id: int,
        ht_match_id: int,
        cuando: datetime,
        captured_at: datetime,
    ) -> bool:
        """Si de verdad jugo, se guarda con sus minutos. Si no, no.

        Estar convocado no es jugar: un suplente que no entra tiene cero
        minutos y no suma experiencia, igual que en el club.
        """
        from app.domain.engines.national_team import Cambio, minutos_jugados

        try:
            alineacion = await self._chpp.fetch(
                "matchlineup",
                version=MATCHLINEUP_ROLE_VERSION,
                matchID=ht_match_id,
                teamID=ht_team_id,
                sourceSystem="htointegrated",
            )
        except Exception:  # noqa: BLE001, best effort, como el resto del sync
            return False

        titulares = set(alineacion.get("starting_lineup", []))
        cambios = [Cambio(**c) for c in alineacion.get("substitutions", [])]
        minutos = minutos_jugados(titulares, cambios, jugador.ht_player_id)
        if minutos <= 0:
            return False

        await self._backfill_foreign_match_type(uow, ht_match_id, jugado_el=cuando)
        estrellas = next(
            (
                p.get("rating_stars") or 0.0
                for p in alineacion.get("players", [])
                if p.get("ht_player_id") == jugador.ht_player_id
            ),
            0.0,
        )
        return await uow.players.append_match_rating_if_new(
            jugador.id,
            ht_match_id=ht_match_id,
            position_code=0,
            played_minutes=minutos,
            rating=estrellas,
            captured_at=captured_at,
        )

    async def _games_played_for_us(
        self,
        ht_team_id: int,
        ht_player_id: int,
        purchased_at: datetime,
        sold_at: datetime,
    ) -> int:
        """Recorre matchesarchive.xml (ventana purchased_at→sold_at) +
        matchlineup.xml v2.1 partido por partido, la única forma de contar
        partidos REALES (RatingStars > 0) de un stint ya cerrado que el
        histórico propio de esta app no alcanzó a sincronizar.

        El conteo es atómico: si una sola alineación no se puede leer, se
        propaga el error y NO se guarda un subtotal. Antes se tragaba ese
        fallo y el número incompleto quedaba congelado para siempre como si
        fuera exacto. El siguiente lote vuelve a recorrer la ventana entera."""
        from app.domain.engines.previous_club_bonus import counts_toward_games_played, did_play

        archive = await self._chpp.fetch(
            "matchesarchive",
            version=FILE_VERSIONS["matchesarchive"],
            teamID=ht_team_id,
            FirstMatchDate=purchased_at.strftime("%Y-%m-%d %H:%M:%S"),
            LastMatchDate=sold_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        qualifying = [
            mt
            for mt in archive.get("matches", [])
            if counts_toward_games_played(mt.get("match_type", -1))
        ]
        games = 0
        for mt in qualifying:
            lineup = await self._chpp.fetch(
                "matchlineup",
                version=MATCHLINEUP_ROLE_VERSION,
                matchID=mt["ht_match_id"],
                teamID=ht_team_id,
            )
            hit = next(
                (p for p in lineup.get("players", []) if p.get("ht_player_id") == ht_player_id),
                None,
            )
            if hit is not None and did_play(hit.get("rating_stars") or 0.0):
                games += 1
        return games

    async def _best_recent_rating(
        self, ht_team_id: int, ht_player_id: int, matches_to_check: int = 3
    ) -> float | None:
        """La mejor nota del fichado en los últimos partidos de su club.

        `None` si todavía no ha jugado ninguno: un fichaje de ayer no tiene
        notas, y un 0 lo haría parecer malo en vez de nuevo.
        """
        if not ht_player_id:
            return None
        try:
            partidos = (
                await self._chpp.fetch(
                    "matches", version=FILE_VERSIONS["matches"], teamID=ht_team_id
                )
            )["matches"]
        except Exception:  # noqa: BLE001
            return None
        jugados = sorted(
            (mt for mt in partidos if mt["status"].upper() == "FINISHED"),
            key=lambda mt: mt["match_date"],
        )[-matches_to_check:]
        mejor: float | None = None
        for mt in jugados:
            try:
                alineacion = (
                    await self._chpp.fetch(
                        "matchlineup",
                        # 2026-08-26: aqui ponia
                        # `MATCHLINEUP_POSITION_CODE_VERSION`, que vive en
                        # `rivals.py` y NUNCA se importo aqui. El
                        # `except Exception: continue` de unas lineas mas abajo
                        # se tragaba el NameError, asi que esta funcion
                        # devolvia `None` SIEMPRE y en silencio -- y `None`
                        # significa "aun no ha jugado", con lo que el fichaje
                        # de un rival parecia recien llegado para siempre. Lo
                        # encontro `ruff` (F821) en CI.
                        #
                        # La version correcta es la de este fichero: aqui solo
                        # se lee `rating_stars`, no `PositionCode`, que es para
                        # lo unico que rivals.py necesita la suya.
                        version=MATCHLINEUP_ROLE_VERSION,
                        matchID=mt["ht_match_id"],
                        matchType=mt["match_type"],
                        teamID=ht_team_id,
                    )
                )["players"]
            # Se traga TODO y sigue, a proposito: un partido que Hattrick no
            # sirva no puede tumbar la sincronizacion entera.
            #
            # Pero conste el precio, que se pago el 2026-08-26: este mismo
            # `except` se trago durante meses un `NameError` por una constante
            # sin importar, y la funcion devolvia `None` sin que nada avisara.
            # Aqui no hay `result` donde anotarlo --esta funcion devuelve un
            # numero, no un informe-- y el proyecto no tiene registro de
            # eventos. Ese es el arreglo de fondo pendiente.
            except Exception:  # noqa: BLE001, S112
                continue
            for jugador in alineacion:
                if jugador.get("ht_player_id") != ht_player_id:
                    continue
                nota = jugador.get("rating_stars") or 0.0
                if nota > 0 and (mejor is None or nota > mejor):
                    mejor = nota
        return mejor

    async def _sync_next_match_weather(
        self,
        uow: UnitOfWork,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """El clima de la región donde se juega el próximo partido.

        Hattrick pronostica a un día vista y por región, así que esto solo
        tiene sentido para el partido inmediato: se piden dos ficheros, el
        estadio donde se juega, para saber su región, y la región, para saber
        su tiempo, y nada más. En un partido de visitante la región es la del
        rival, no la propia.

        La región de un estadio no cambia, así que solo se pregunta la primera
        vez por partido; el pronóstico, en cambio, se reescribe en cada sync
        porque cambia de un día para otro.
        """
        from sqlalchemy import or_, select

        from app.domain.value_objects.ht_constants import NON_OFFICIAL_MATCH_TYPES
        from app.domain.value_objects.ht_time import ht_day, ht_to_utc
        from app.infrastructure.db import models as m

        # Escaleras, duelos y torneos quedan fuera, igual que en el resto de la
        # app: si un duelo de mañana tapara al partido de liga, el aviso
        # hablaría del cielo equivocado.
        match = await uow.session.scalar(
            select(m.Match)
            .where(
                or_(
                    m.Match.home_team_ht_id == ht_team_id,
                    m.Match.away_team_ht_id == ht_team_id,
                ),
                m.Match.status.ilike("upcoming"),
                m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES),
            )
            .order_by(m.Match.played_at)
            .limit(1)
        )
        if match is None:
            return

        row = await uow.session.scalar(
            select(m.MatchWeather).where(m.MatchWeather.ht_match_id == match.ht_match_id)
        )
        # El pronóstico solo alcanza a hoy y mañana: para un partido más lejos
        # no hay nada que pedir todavía.
        dias = (ht_day(match.played_at) or captured_at.date()) - (
            ht_day(captured_at) or captured_at.date()
        )
        if dias.days > 1 or dias.days < 0:
            return

        await _report(on_progress, "Consultando el clima de la sede del partido...")
        try:
            region_id = row.ht_region_id if row is not None else 0
            region_name = row.region_name if row is not None else ""
            if not region_id:
                # teamdetails y no arenadetails: el segundo responde error 59
                # para un equipo que no gestionas, y en un partido de
                # visitante la región que manda es la del rival.
                detalles = await self._chpp.fetch(
                    "teamdetails",
                    version=FILE_VERSIONS["teamdetails"],
                    teamID=match.home_team_ht_id,
                )
                local = next(
                    (
                        t
                        for t in detalles.get("teams", [])
                        if t.get("ht_team_id") == match.home_team_ht_id
                    ),
                    None,
                )
                region_id = int((local or {}).get("ht_region_id") or 0)
                region_name = (local or {}).get("region_name", "")
            if not region_id:
                return
            forecast = await self._chpp.fetch(
                "regiondetails",
                version=FILE_VERSIONS["regiondetails"],
                regionID=region_id,
            )
            taken_at = ht_to_utc(forecast.get("fetched_at", "")) or captured_at
            valores = {
                "venue_ht_team_id": match.home_team_ht_id,
                "ht_region_id": region_id,
                "region_name": forecast.get("region_name") or region_name,
                "weather_today": int(forecast.get("weather_today", -1)),
                "weather_tomorrow": int(forecast.get("weather_tomorrow", -1)),
                "forecast_taken_at": taken_at,
                "captured_at": captured_at,
            }
            if row is None:
                uow.session.add(m.MatchWeather(ht_match_id=match.ht_match_id, **valores))
            else:
                for campo, valor in valores.items():
                    setattr(row, campo, valor)
        except Exception as exc:  # noqa: BLE001, el clima nunca tumba un sync
            result.errors.append(f"{_nombre_legible('regiondetails')}: {exc}")
            await _tras_fallo(uow, exc)

    async def _fetch_last_match_behaviour(
        self,
        uow: UnitOfWork,
        ht_player_id: int,
        ht_match_id: int | None,
        team_id: int,
    ) -> int | None:
        """2026-08-09, pedido explícitamente: `LastMatch` de playerdetails.xml
        da el `MatchId`/`PositionCode` pero nunca la orden individual real
        (Ofensivo/Defensivo/Hacia el medio/Hacia la banda), eso solo lo
        trae `Behaviour` de matchlineup.xml PARA ESE PARTIDO CONCRETO, una
        llamada CHPP aparte. Best effort: si falla (partido de
        selección/torneo fuera de alcance, CHPP caído, jugador no aparece
        en la alineación por lo que sea) se queda en None, nunca bloquea
        el resto de playerdetails, que sigue siendo útil sin esto."""
        if not ht_match_id:
            return None

        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)
        if team is None:
            return None
        try:
            payload = await self._chpp.fetch(
                "matchlineup",
                version=MATCHLINEUP_ROLE_VERSION,
                matchID=ht_match_id,
                teamID=team.ht_team_id,
            )
        except Exception:  # noqa: BLE001, best effort, ver docstring
            return None
        for p in payload.get("players", []):
            if p.get("ht_player_id") == ht_player_id:
                behaviour: int | None = p.get("behaviour")
                return behaviour
        return None
