"""Use case: sincronizar un equipo desde CHPP (iniciado por el usuario).

Pipeline por file: fetch → parse → diff (content_hash) → persist (append-only).
Descargas SECUENCIALES (requisito CHPP). Sync parcial si un file falla.
"""

import json
from datetime import UTC, datetime
from typing import Any

from app.application.commands.sync_team.alineacion import AlineacionMixin
from app.application.commands.sync_team.base import BaseDeSync
from app.application.commands.sync_team.club import ClubMixin
from app.application.commands.sync_team.comun import (
    AUTOMATIC_MATCH_DETAILS_WINDOW,
    DEFAULT_FILES,
    DETALLES_HISTORICOS_EN_PARALELO,
    FILE_LABELS,
    FILE_VERSIONS,
    GOTEO_DE_VIGILANCIA,
    HASH_FIELDS,
    MATCH_ARCHIVE_FALLBACK_START,
    MATCH_ARCHIVE_INCREMENTAL_OVERLAP,
    MATCH_ARCHIVE_MIN_WINDOW,
    MATCH_ARCHIVE_RANGE_TOLERANCE,
    MATCH_ARCHIVE_RESPONSE_LIMIT,
    MATCH_ARCHIVE_WINDOW,
    MATCHLINEUP_ROLE_VERSION,
    MENSAJE_BASE_CORTADA,
    PLACEHOLDERS_DE_ANIMO,
    VERSION_DEL_ARCHIVO,
    VERSION_DEL_LIBRO,
    ProgressReporter,
    SyncBackfillBatchCommand,
    SyncMatchDetailsCommand,
    SyncPlayerDetailsCommand,
    SyncPlayerEnrichmentCommand,
    SyncPreviousClubBonusCommand,
    SyncResult,
    SyncTeamCommand,
    SyncTransfersHistoryCommand,
    SyncTransfersPlayerCommand,
    _as_change_row,
    _full_player_name,
    _log,
    _nombre_legible,
    _parse_dt,
    _report,
    _sin_placeholders_de_animo,
    _tras_fallo,
    aforo_del_estadio,
    content_hash,
    dict_hash,
    mensaje_de_error,
    trasladar_equipo_reemplazado,
)
from app.application.commands.sync_team.economia import EconomiaMixin
from app.application.commands.sync_team.entrenamiento import EntrenamientoMixin
from app.application.commands.sync_team.fichas import FichasMixin
from app.application.commands.sync_team.juveniles import JuvenilesMixin
from app.application.commands.sync_team.liga import LigaMixin
from app.application.commands.sync_team.partidos import PartidosMixin
from app.application.commands.sync_team.plantilla import PlantillaMixin
from app.application.commands.sync_team.relleno import RellenoMixin
from app.application.commands.sync_team.transferencias import TransferenciasMixin
from app.domain.engines.sync_diff import (
    diff_economy,
    diff_player_departure,
    diff_player_skills,
    diff_training,
)
from app.domain.ports.chpp_gateway import CHPPGateway
from app.domain.ports.repositories import UnitOfWork


class SyncTeamHandler(  # noqa: D101
    ClubMixin,
    PlantillaMixin,
    FichasMixin,
    PartidosMixin,
    AlineacionMixin,
    TransferenciasMixin,
    JuvenilesMixin,
    LigaMixin,
    EconomiaMixin,
    EntrenamientoMixin,
    RellenoMixin,
    BaseDeSync,
):
    def __init__(self, uow: UnitOfWork, chpp: CHPPGateway) -> None:
        self._uow = uow
        self._chpp = chpp
        #: La fila de la sincronización en marcha, para cerrarla si algo revienta.
        self._fila_en_curso: int | None = None
        # Se levanta si Hattrick contesta con la cantera de otro club: a
        # partir de ahi los ficheros juveniles de ese sync no se tocan.
        self._academia_ajena = False

    async def execute(
        self, cmd: SyncTeamCommand, on_progress: ProgressReporter | None = None
    ) -> SyncResult:
        """La sincronización completa; si revienta, su fila queda cerrada con el motivo."""
        self._fila_en_curso = None
        try:
            return await self._execute(cmd, on_progress)
        except Exception as exc:
            await self._cerrar_como_fallida(exc)
            raise

    async def _execute(
        self, cmd: SyncTeamCommand, on_progress: ProgressReporter | None = None
    ) -> SyncResult:
        files = cmd.files or DEFAULT_FILES
        async with self._uow as uow:
            sync_id = await uow.syncs.create(cmd.user_id, cmd.team_id, kind=",".join(files))
            # La fila se guarda YA (2026-09-15). Antes sólo se confirmaba al final,
            # así que una sincronización que reventaba a mitad desaparecía sin
            # rastro: en producción faltaban siete ids en `syncs`.
            await uow.commit()
            self._fila_en_curso = sync_id
            self._academia_ajena = False
            result = SyncResult(sync_id=sync_id, status="completed")
            captured_at = datetime.now(UTC)

            for file in files:  # secuencial: requisito CHPP
                await _report(on_progress, f"Descargando {FILE_LABELS.get(file, file)}...")
                try:
                    params: dict[str, Any] = {"teamID": cmd.ht_team_id}
                    if file in ("leaguedetails", "leaguefixtures"):
                        params = {"leagueLevelUnitID": await self._series_ht_id(uow, cmd.team_id)}
                    elif file in ("youthteamdetails", "youthplayerlist"):
                        # La cantera se pide POR SU ID. Una cuenta de Hattrick
                        # puede llevar varios clubes y cada uno tiene la suya;
                        # sin `youthTeamId` estos dos ficheros devuelven la del
                        # club principal, y por eso los juveniles del primer
                        # equipo salian tambien como los del segundo (lo
                        # reporto un usuario, 2026-09-19).
                        academia = await self._academia_del_equipo(uow, cmd.team_id)
                        if self._academia_ajena:
                            # La comprobacion de `youthteamdetails` fallo: lo
                            # que contesta Hattrick no es de este club.
                            continue
                        if file == "youthplayerlist":
                            # Sin `actionType=details` el fichero trae sólo las
                            # identidades: ni niveles ni techos, y el motor de
                            # academia se queda sin nada que evaluar.
                            params = {"actionType": "details", "showLastMatch": "true"}
                        else:
                            # `showScouts`: sin el, el fichero NO trae ojeadores
                            # en ninguna version --comprobado de la 1.0 a la
                            # 1.3-- y sin ellos no hay fecha de contratacion,
                            # que es lo que sostiene la cuenta de cada uno.
                            params = {"showScouts": "true"}
                        # TAMPOCO SE PIDE A CIEGAS (2026-09-27). Antes, sin
                        # saber la academia se mandaba igual y Hattrick
                        # contestaba con la del club principal; se guardaba solo
                        # si resultaba ser la buena, asi que el segundo club
                        # nunca llegaba a descubrir la suya y se quedaba sin
                        # cantera para siempre. Ahora el id sale de
                        # `teamdetails`, que se pide POR CLUB y lo trae gratis,
                        # y va antes que estos dos en la lista.
                        if not academia:
                            # 0 es un dato, no una falta: este club no tiene
                            # academia abierta y no hay nada que pedir. `None`
                            # si es una falta: todavia no se ha leido el
                            # `teamdetails` que la nombra.
                            if academia is None:
                                result.errors.append(
                                    f"{_nombre_legible(file)}: todavia no se sabe cual es la "
                                    "academia de este club; sincroniza sus datos de equipo "
                                    "primero y vuelve a intentarlo"
                                )
                            continue
                        params["youthTeamId"] = academia
                        if file == "youthplayerlist":
                            await self._desbloquear_habilidades(result, academia)
                    payload = await self._chpp.fetch(
                        file, version=FILE_VERSIONS.get(file, "latest"), **params
                    )
                    await self._persist(
                        uow,
                        sync_id,
                        cmd.team_id,
                        cmd.ht_team_id,
                        file,
                        payload,
                        captured_at,
                        result,
                    )
                    # Por partes (2026-09-15): un corte de la base a mitad ya no
                    # se lleva por delante los ficheros que ya se guardaron.
                    await uow.commit()
                except Exception as exc:  # noqa: BLE001, sync parcial, no abortamos el resto
                    result.errors.append(f"{_nombre_legible(file)}: {exc}")
                    result.status = "partial"
                    await _tras_fallo(uow, exc)

            # `players.xml` trae CountryID y `worlddetails.xml` trae la
            # identidad oficial de ese país. Como worlddetails se descarga
            # después de players en el flujo normal, el cruce se hace aquí,
            # cuando ambos ya están persistidos. También permite completar
            # snapshots existentes al actualizar desde una versión anterior
            # de HT Lens, sin volver a pedir una ficha por jugador.
            if "players" in files or "worlddetails" in files:
                await self._backfill_native_countries_from_snapshots(uow, cmd.team_id, result)
            if "players" in files:
                # Quien esta en venta sale de la plantilla, no de la lista de
                # pujas. Va antes que `currentbids`, que solo enriquece.
                await self._marcar_quien_esta_en_venta(uow, cmd.team_id, captured_at)

            if "youthteamdetails" in files:
                # Los ex-canteranos: es lo que enlaza la academia con las
                # ventas, y sin ellos la cuenta de cada ojeador no existe.
                await self._sync_antiguos_canteranos(
                    uow, cmd.team_id, cmd.ht_team_id, captured_at, result
                )

            if "youthplayerlist" in files:
                await self._sync_informes_de_ojeador(
                    uow,
                    cmd.team_id,
                    captured_at,
                    result,
                    on_progress,
                )

            from app.infrastructure.db import models as m

            # TUS compras y TUS ventas se traen AQUI. 2026-08-25, corregido a
            # peticion del usuario: el boton de abajo es solo para la
            # vigilancia de comisiones de reventa, no para el movimiento del
            # propio club.
            #
            # El fallo que lo destapo: el libro solo se recorria "si el
            # historial no esta completo", asi que en cuanto termino el primer
            # barrido dejo de leerse. El libro se quedo congelado el 20 de
            # agosto y Jose Rui Gomes, comprado el 24, no tenia ni fecha ni
            # precio de compra.
            #
            # Releerlo es barato: `_recorrer_historial` se detiene en cuanto
            # reconoce un numero de transferencia, asi que cuando no hay nada
            # nuevo cuesta UNA pagina. La maquinaria ya estaba escrita; lo que
            # sobraba era la condicion que impedia usarla.
            # Atado a `players`: el libro cuenta el movimiento de la
            # plantilla, y una sincronizacion restringida a otro fichero no
            # tiene por que gastar una llamada en el.
            equipo_libro = (
                await uow.session.get(m.Team, cmd.team_id) if "players" in files else None
            )
            if equipo_libro is not None:
                await _report(on_progress, "Revisando tus compras y ventas...")
                await self._recorrer_historial(
                    uow,
                    cmd.user_id,
                    cmd.team_id,
                    equipo_libro,
                    result,
                )

            if result.arrived_players:
                # Las altas, con lo que costaron y lo que cuestan. Se hace
                # aquí por lo mismo que las bajas: `transfersteam` puede ir
                # después de `players` y sólo tras procesarlo existe la compra
                # que le pone precio al fichaje de esta misma semana.
                await self._anunciar_altas(uow, cmd.team_id, result)

            if result.departed_players:
                # HL-2xx, 2026-08-12: se anuncia aquí, no dentro de
                # `_persist_squad`, `transfersteam` puede ir DESPUÉS de
                # `players` en `files`, y sólo tras procesarlo
                # `sale_price`/`sold_at` reflejan la venta real de este
                # mismo sync (ver docstring de `SyncResult.departed_players`).
                team = await uow.session.get(m.Team, cmd.team_id)
                rate = (team.currency_rate or 1.0) if team else 1.0
                currency = team.currency_name if team else ""

                def _conv(v: int | None) -> int | None:
                    return None if v is None else int(round(v / rate))

                for p in result.departed_players:
                    name = f"{p.first_name} {p.last_name}".strip()
                    change = diff_player_departure(
                        name, _conv(p.sale_price), currency, p.ht_player_id
                    )
                    result.changes.append(_as_change_row(change))

            for c in result.changes:
                detail = c.get("detail")
                uow.session.add(
                    m.SyncChange(
                        sync_id=sync_id,
                        team_id=cmd.team_id,
                        category=c["category"],
                        summary=c["summary"],
                        detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
                        created_at=captured_at,
                    )
                )

            # HL-161: enriquecimiento de jugadores vendidos (edad en la
            # venta, país, carácter, especialidad, país destino), pedido
            # explícitamente 2026-08-04 SIN botón: se dispara solo aquí,
            # dentro del sync normal, porque una vez resuelto para un
            # jugador nunca hace falta repetirlo. Solo cuando `transfersteam`
            # es parte de este sync (donde se detectan ventas), evita
            # llamadas CHPP de más en syncs restringidos a otros ficheros
            # (p. ej. los de test que sólo piden players/training/economy).
            if "transfersteam" in files:
                # `captured_at` (arriba) es aware (UTC), sirve para Match y
                # otras tablas, pero `sold_at` leído de SQLite siempre llega
                # naive (no conserva tzinfo en el viaje de ida y vuelta), así
                # El relleno del pasado (ficha, precio antiguo y país destino
                # de cada ex-jugador) ya NO vive aquí: era una llamada a
                # Hattrick por jugador y sin tope, así que una cuenta con
                # historia larga convertía cada sincronización en cientos de
                # peticiones que se cortaban por tiempo sin terminar. Ahora va
                # por lotes desde su propio botón, con un contador a la vista
                # (ver `execute_backfill_batch`). Esto de aquí se queda solo
                # con lo que es barato y cambia semana a semana.
                await self._backfill_mandatory_listing_count(uow, cmd.team_id, result)

            # 2026-08-05, pedido explícitamente: "tienes que sincronizar
            # todos los xml que importen cada vez que sincronizamos", hasta
            # ahora LastMatch/Caps/CareerAssists (playerdetails.xml) y
            # HatStats/sectores (matchdetails.xml) se quedaban obsoletos
            # esperando un botón aparte ("Actualizar detalles de jugadores",
            # "Sincronizar detalles"). Ambos entran aquí, siempre que su
            # fichero base haya sido parte de este sync, cada uno sigue
            # siendo tantas llamadas CHPP como jugadores/partidos pendientes
            # haya, pero ya no depende de que el usuario recuerde pedirlo.
            if "players" in files:
                await self._sync_active_roster_player_details(
                    uow, cmd.team_id, captured_at, result, on_progress
                )
                await self._censar_partidos_de_seleccion(uow, cmd.team_id, captured_at, result)
                await self._sync_training_events(uow, cmd.team_id, captured_at, result, on_progress)
                await uow.commit()
            if "matches" in files:
                await self._sync_match_history(
                    uow,
                    cmd.team_id,
                    cmd.ht_team_id,
                    captured_at,
                    result,
                    on_progress,
                )
                await self._sync_upcoming_match_orders(
                    uow, cmd.ht_team_id, captured_at, result, on_progress
                )
                await self._sync_alineaciones_jugadas(
                    uow, cmd.ht_team_id, captured_at, result, on_progress
                )
                await self._completar_desglose_de_taquilla(
                    uow, cmd.team_id, cmd.ht_team_id, result, on_progress
                )
                await self._backfill_missing_match_details(
                    uow, cmd.team_id, cmd.ht_team_id, result, on_progress
                )
                await self._completar_detalles_historicos(
                    uow, cmd.team_id, cmd.ht_team_id, result, on_progress
                )
                await self._sync_next_match_weather(
                    uow, cmd.ht_team_id, captured_at, result, on_progress
                )
                await self._sync_rival_purchases(
                    uow, cmd.team_id, cmd.ht_team_id, captured_at, result, on_progress
                )
                await self._guardar_partidos_de_rivales(
                    uow, cmd.team_id, cmd.ht_team_id, result, on_progress
                )
                await uow.commit()

            await self._marcar_salidas_de_vendidos(uow, cmd.team_id)
            await self._reparar_partidos_ajenos_sin_ficha(uow)
            await self._resolver_moneda(uow, cmd.team_id)

            # La habilidad entrenada de cada exjugador es un derivado
            # dinámico: una venta nueva puede cambiar la moda de su temporada
            # y, con ella, las asignaciones provisionales de ventas antiguas.
            # Se recalcula al final, cuando snapshots, libro y mundo ya están
            # actualizados por este mismo sync.
            from app.application.commands.backfill_sold_training import (
                backfill_sold_training_assignments,
            )

            await backfill_sold_training_assignments(uow.session, cmd.team_id)

            await uow.syncs.finalize(
                sync_id,
                status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _persist(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        ht_team_id: int,
        file: str,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        if file in ("economy", "training"):
            repo = uow.economy if file == "economy" else uow.training
            # Antes del hash, del append y del diff: si se limpiara más tarde,
            # el -1 produciría una foto y un cambio falsos, y cada nueva
            # sincronización durante el partido volvería a hacerlo.
            #
            # Economía perdió aquí su camino barato --antes se saltaba esta
            # consulta cuando el hash coincidía-- y es un precio que vale la
            # pena: es UNA fila por sincronización, y a cambio la afición no
            # puede colarse en la historia con un nivel que Hattrick nunca
            # dijo (2026-09-02).
            old_values = await repo.get_last_values(team_id)
            payload = _sin_placeholders_de_animo(payload, old_values, PLACEHOLDERS_DE_ANIMO[file])
            new_hash = dict_hash(payload)
            if await repo.get_last_hash(team_id) == new_hash:
                result.unchanged += 1
                return
            await repo.append(sync_id, team_id, payload, new_hash, captured_at)
            result.snapshots_written += 1
            if file == "economy":
                from app.infrastructure.db import models as m

                team = await uow.session.get(m.Team, team_id)
                currency = team.currency_name if team else ""
                rate = (team.currency_rate or 1.0) if team else 1.0
                changes = diff_economy(old_values, payload, currency, rate)
            else:
                changes = diff_training(old_values, payload)
            result.changes.extend(_as_change_row(c) for c in changes)
            return
        if file in ("club", "stafflist"):
            await self._persist_staff(uow, sync_id, team_id, file, payload, captured_at, result)
            return
        if file == "worlddetails":
            await self._persist_world(uow, team_id, payload, captured_at, result)
            return
        if file == "trainingevents":
            await self._persist_skill_ups(uow, team_id, payload, captured_at, result)
            return
        if file == "matches":
            await self._persist_matches(uow, ht_team_id, payload, result)
            return
        if file == "leaguefixtures":
            await self._persist_league_fixtures(uow, payload, result)
            return
        if file == "currentbids":
            await self._persist_currentbids(uow, team_id, payload, captured_at, result)
            return
        if file == "teamdetails":
            await self._persist_teamdetails(uow, team_id, ht_team_id, payload, result)
            return
        if file == "leaguedetails":
            await self._persist_standings(
                uow, sync_id, team_id, ht_team_id, captured_at, payload, result
            )
            return
        if file == "transfersteam":
            await self._persist_transfers(uow, team_id, ht_team_id, payload, result)
            return
        if file == "youthplayerlist":
            await self._persist_youth(uow, sync_id, team_id, payload, captured_at, result)
            return
        if file == "youthteamdetails":
            from app.infrastructure.db import models as m

            team = await uow.session.get(m.Team, team_id)
            # De quien es la cantera que contesto Hattrick. Si no es la de
            # este club no se guarda NADA: es justo el cruce que metia los
            # juveniles del equipo principal en el segundo equipo, y vale mas
            # un sync parcial y ruidoso que datos ajenos guardados en silencio.
            madre = payload.get("mother_team_id") or 0
            if madre and ht_team_id and madre != ht_team_id:
                self._academia_ajena = True
                if team is not None and team.ht_youth_team_id == 0:
                    # Este club no tiene cantera y Hattrick contesta con la
                    # del principal. Es lo esperado, no un fallo: se descarta
                    # sin ensuciar el parte de la sincronizacion.
                    return
                # El aviso se escribe aqui, y no lanzando: asi es una frase
                # entera --sin el nombre del fichero delante-- que se puede
                # leer y traducir.
                ajena = payload.get("mother_team_name") or ""
                result.errors.append(
                    "La cantera que contestó Hattrick es la de {}, no la de "
                    "este club: no se guardó nada.".format(ajena or "otro club")
                )
                result.status = "partial"
                return
            if team is not None and payload.get("ht_youth_team_id"):
                team.ht_youth_team_id = payload["ht_youth_team_id"]
                team.youth_team_name = payload.get("youth_team_name") or None
                team.youth_academy_created_at = _parse_dt(payload.get("created_date"))
                team.youth_next_training_match_at = _parse_dt(
                    payload.get("next_training_match_date")
                )
            if payload.get("has_scouts"):
                await self._persist_ojeadores(uow, team_id, payload.get("scouts", []), captured_at)
            return
        if file != "players":
            return  # TODO: handler para arena…
        roster = payload.get("players", [])
        # El import va aquí dentro, como en las demás ramas de este método:
        # `m` no está en el ámbito del módulo y usarlo sin importarlo lanza un
        # NameError que el `except Exception` de arriba se traga --el sync sale
        # "parcial" y la plantilla entera se queda sin escribir, en silencio--.
        from app.infrastructure.db import models as m

        # La tasa del país, para el salario. Sin ella la frase del cambio se
        # escribía con el número crudo de Hattrick --diez veces más grande en
        # Colombia-- y, como el texto se congela en la fila, quedaba mal para
        # siempre (2026-09-01).
        equipo = await uow.session.get(m.Team, team_id)
        tasa = (equipo.currency_rate or 1.0) if equipo else 1.0
        moneda = (equipo.currency_name if equipo else "") or ""
        for p in roster:
            player_id = await uow.players.upsert_identity(
                p["ht_player_id"], team_id, p["first_name"], p["last_name"]
            )
            new_hash = content_hash(p)
            last_hash = await uow.players.get_last_snapshot_hash(p["ht_player_id"])
            if last_hash == new_hash:
                result.unchanged += 1
                continue  # diffing: sin cambio, sin fila
            old_values = await uow.players.get_last_snapshot(p["ht_player_id"])
            await uow.players.append_snapshot(sync_id, player_id, p, new_hash, captured_at)
            result.snapshots_written += 1
            name = f"{p['first_name']} {p['last_name']}".strip()
            if old_values is None:
                # Un alta. Su frase necesita el libro de transferencias, que
                # puede no estar procesado todavía; se escribe al final.
                result.arrived_players.append((name, p))
                continue
            changes = diff_player_skills(old_values, p, name, tasa, moneda)
            result.changes.extend(_as_change_row(c) for c in changes)

        if roster:
            # Quien no vino en este players.xml ya no está en el club, se
            # marca left_team_at (nunca se borra). Un roster vacío no dispara
            # esto: sería marcar a toda la plantilla como salida por un fetch
            # vacío/roto, exactamente el tipo de bug que esta guarda evita.
            current_ids = {p["ht_player_id"] for p in roster}
            departed = await uow.players.mark_departed(team_id, current_ids, captured_at)
            result.departed_players.extend(departed)


__all__ = [
    "SyncTeamHandler",
    "AUTOMATIC_MATCH_DETAILS_WINDOW",
    "DEFAULT_FILES",
    "DETALLES_HISTORICOS_EN_PARALELO",
    "FILE_LABELS",
    "FILE_VERSIONS",
    "GOTEO_DE_VIGILANCIA",
    "HASH_FIELDS",
    "MATCHLINEUP_ROLE_VERSION",
    "MATCH_ARCHIVE_FALLBACK_START",
    "MATCH_ARCHIVE_INCREMENTAL_OVERLAP",
    "MATCH_ARCHIVE_MIN_WINDOW",
    "MATCH_ARCHIVE_RANGE_TOLERANCE",
    "MATCH_ARCHIVE_RESPONSE_LIMIT",
    "MATCH_ARCHIVE_WINDOW",
    "MENSAJE_BASE_CORTADA",
    "PLACEHOLDERS_DE_ANIMO",
    "ProgressReporter",
    "SyncBackfillBatchCommand",
    "SyncMatchDetailsCommand",
    "SyncPlayerDetailsCommand",
    "SyncPlayerEnrichmentCommand",
    "SyncPreviousClubBonusCommand",
    "SyncResult",
    "SyncTeamCommand",
    "SyncTransfersHistoryCommand",
    "SyncTransfersPlayerCommand",
    "VERSION_DEL_ARCHIVO",
    "VERSION_DEL_LIBRO",
    "_as_change_row",
    "_full_player_name",
    "_log",
    "_nombre_legible",
    "_parse_dt",
    "_report",
    "_sin_placeholders_de_animo",
    "_tras_fallo",
    "aforo_del_estadio",
    "content_hash",
    "dict_hash",
    "mensaje_de_error",
    "trasladar_equipo_reemplazado",
]
