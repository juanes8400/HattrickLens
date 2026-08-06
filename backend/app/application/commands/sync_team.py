"""Use case: sincronizar un equipo desde CHPP (iniciado por el usuario).

Pipeline por file: fetch → parse → diff (content_hash) → persist (append-only).
Descargas SECUENCIALES (requisito CHPP). Sync parcial si un file falla.
"""
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.domain.engines.sync_diff import (
    MatchState,
    diff_economy,
    diff_match,
    diff_player_skills,
    diff_standing,
    diff_training,
)
from app.domain.ports.chpp_gateway import CHPPGateway
from app.domain.ports.repositories import UnitOfWork

# 2026-08-05, pedido explícitamente: "la conexión" de Hattrick Control
# muestra en vivo qué está descargando — un sync aquí ya no es una caja
# negra de 15-20s. `on_progress`, si se pasa, recibe un mensaje legible por
# cada paso real (un fichero, un jugador, un partido); `None` en cualquier
# otro caller (tests, comandos que no necesitan progreso) lo deja mudo, sin
# tocar el resto del flujo.
ProgressReporter = Callable[[str], Awaitable[None]]


async def _report(on_progress: ProgressReporter | None, message: str) -> None:
    if on_progress is not None:
        await on_progress(message)


FILE_LABELS: dict[str, str] = {
    "players": "plantilla (jugadores)",
    "training": "entrenamiento",
    "economy": "economía",
    "teamdetails": "datos del club",
    "leaguedetails": "clasificación de liga",
    "leaguefixtures": "calendario de la serie",
    "matches": "calendario y resultados",
    "transfersteam": "historial de transferencias",
    "currentbids": "jugadores en el mercado",
    "worlddetails": "temporada y copas del mundo",
    "club": "club",
    "stafflist": "cuerpo técnico",
    "trainingevents": "subidas de entrenamiento confirmadas",
}

#  HL-140: un sync normal debe poder mostrar el diff completo — posición en
# liga y resultados incluidos, no solo plantilla/economía. `teamdetails` va
# antes que `leaguedetails` porque este último necesita `series_ht_id`.
# `transfersteam` es una única llamada por equipo (no por jugador, a
# diferencia de `playerdetails` — ver `execute_player_details`), así que
# entra en el sync por defecto sin multiplicar las peticiones a CHPP.
DEFAULT_FILES = [
    "players", "training", "economy", "teamdetails", "leaguedetails", "leaguefixtures",
    "matches", "transfersteam", "currentbids", "worlddetails",
]
# worlddetails, 2026-08-04: única fuente de la temporada ACTUAL de Hattrick
# (leaguedetails.xml no la trae). Antes no estaba en el sync por defecto, así
# que `WorldContext.season` se quedaba congelada en lo que fuera que un
# script de desarrollo hubiera sincronizado a mano una vez — el desglose
# "por Temporada" del saldo por jugador (`season_at`, player_balance.py)
# depende de que esté fresca para calcular la temporada de CUALQUIER fecha
# por aritmética pura (112 días/temporada, igual que la edad), no solo de
# fechas con un Standing sincronizado cerca.
# club, stafflist, worlddetails, trainingevents cierran la fórmula de
# entrenamiento: aportan los valores que antes se ponían a mano.
# playerdetails: 2.6 se probó en vivo y NO trae `MotherClub`/`LastMatch`
# poblados (solo el booleano `MotherClubBonus`); 3.2, confirmado con un XML
# real de la cuenta de desarrollo, sí los trae — la versión importa más de
# lo que sugiere la documentación de campos por sí sola.
# CORRECCIÓN 2026-08-03: `transfersteam` (equipo) se usa para precio de
# compra Y venta por defecto. Un comentario anterior decía que
# `transferplayer.xml` (por jugador) devolvía 401 por scope OAuth — era un
# nombre de fichero mal escrito (falta la "s": es `transfersplayer.xml`),
# no una restricción real. Verificado en vivo con este mismo token: funciona
# y trae el historial completo de transferencias de un jugador — ver
# `parse_transfersplayer` en `app/infrastructure/chpp/parsers/__init__.py`.
#
# CORRECCIÓN 2026-08-03 (bis): `"latest"` NO es la versión más reciente de
# `transfersteam.xml` — es un esquema/ventana viejo y distinto. Comparado en
# vivo contra la cuenta real: pedir `version=latest` devolvía una página de
# 25 transferencias que terminaba justo donde `version=1.2` EMPIEZA (es
# decir, "latest" se queda ~25 transferencias atrás de lo real). Una venta
# hecha el mismo día de la prueba (Lander Fripont, 495018863) solo aparecía
# pidiendo "1.2" explícito — con "latest" nunca se habría visto. Fijado a
# "1.2" para que las ventas/compras recientes sí lleguen.
FILE_VERSIONS = {
    # 2.8 mantiene los campos de 2.6 y, validado contra players.xml de un
    # rival, expone PlayerForm y StaminaSkill que alimentan el análisis previo.
    # economy 1.4, no 1.5: 1.5 no está confirmada y degradaba el fichero al
    # esquema viejo (todo agregado en Income/CostsTemporary). 1.4 es la que
    # trae IncomeSoldPlayers/Commission, IncomeSponsorBonuses y
    # Costs{BoughtPlayers,ArenaBuilding} por separado — verificado contra
    # `docs/chpp-reference/economy.txt`, un fichero real de esta cuenta.
    "players": "2.8", "teamdetails": "3.6", "training": "2.2", "economy": "1.4",
    "club": "1.0", "stafflist": "1.0", "worlddetails": "1.8", "trainingevents": "1.0",
    "matches": "2.9", "matchdetails": "3.1", "leaguedetails": "1.6",
    # 1.2 verificado en vivo: trae el calendario COMPLETO de la serie (los
    # 28 pares posibles, ida y vuelta) con MatchRound real — a diferencia de
    # matches.xml, que solo trae los partidos del equipo pedido.
    "leaguefixtures": "1.2",
    # 1.1 verificado en vivo (HL-161): historial completo de transferencias
    # de UN jugador, con "s" en el nombre del fichero (transfersplayer, no
    # transferplayer) — ver corrección 2026-08-03 más arriba.
    "transfersplayer": "1.1",
    # 1.0 verificado en vivo (HL-161): jugadores propios actualmente en el
    # mercado — se usa para contar intentos de venta hacia adelante, CHPP
    # no da un historial de esto.
    "currentbids": "1.0",
    "playerdetails": "3.2", "transfersteam": "1.2", "arenadetails": "latest",
}

# Campos que definen "cambio real" (excluye derivados/ruido)
HASH_FIELDS = (
    "age_years", "age_days", "tsi", "form", "stamina", "experience",
    "salary", "specialty", "injury_level", "is_transfer_listed", "skills",
    "loyalty", "leadership", "agreeability", "aggressiveness", "honesty",
    "mother_club_bonus", "country_id", "league_goals", "cup_goals",
    "friendlies_goals", "career_goals", "career_hattricks",
    "player_trainer_skill_level", "player_trainer_type",
)


def content_hash(player: dict[str, Any]) -> bytes:
    canonical = {k: player.get(k) for k in HASH_FIELDS}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).digest()


def dict_hash(data: dict[str, Any]) -> bytes:
    """Hash canónico de un payload por-equipo (economy, training)."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).digest()


@dataclass(frozen=True)
class SyncTeamCommand:
    user_id: int
    team_id: int          # id interno
    ht_team_id: int       # id Hattrick
    files: list[str] | None = None


@dataclass(frozen=True)
class SyncMatchDetailsCommand:
    """matchdetails se pide por partido (matchID), no por equipo — de ahí un
    comando aparte en vez de meterlo en `files` de SyncTeamCommand."""
    user_id: int
    team_id: int
    ht_match_id: int
    # Se pide una vez por lote y se reutiliza para los detalles de partido.
    # matchdetails da ventas; arenadetails, el aforo actual por sector.
    arena_capacity: dict[str, int] | None = None


@dataclass(frozen=True)
class SyncPlayerDetailsCommand:
    """playerdetails se pide por jugador (playerID) — igual que
    matchdetails, aparte de `files`: son N llamadas CHPP, una por jugador
    de la plantilla, no una sola por equipo."""
    user_id: int
    team_id: int
    ht_player_id: int


@dataclass(frozen=True)
class SyncTransfersPlayerCommand:
    """transfersplayer.xml, HL-161: historial completo de UN jugador —
    igual que playerdetails/matchdetails, una llamada por jugador, acción
    aparte que dispara el usuario (no forma parte del sync por defecto)."""
    user_id: int
    team_id: int
    ht_player_id: int


@dataclass(frozen=True)
class SyncTransfersHistoryCommand:
    """HL-161, 2026-08-04: botón "Actualizar transferencias" — pagina
    transfersteam.xml completo (no solo la página más reciente) para traer
    TODA la historia de compraventas del equipo, así el jugador ya no esté
    en la plantilla ni haya sido visto nunca por `players.xml`. La primera
    vez recorre las ~40 páginas (casi 1000 transferencias); las siguientes
    paran en cuanto encuentran un TransferID ya conocido — ver
    `execute_transfers_history`."""
    user_id: int
    team_id: int
    ht_team_id: int


@dataclass(frozen=True)
class SyncPlayerEnrichmentCommand:
    """HL-161: una llamada a playerdetails.xml por jugador VENDIDO que
    rellena de un tirón edad-en-la-venta, país de origen, carácter y
    especialidad. CORRECCIÓN 2026-08-04: antes era un botón aparte
    ("Calcular edad al vender") — el usuario pidió explícitamente quitarlo,
    porque una vez calculado para un jugador nunca vuelve a hacer falta, así
    que ahora se dispara solo, automático, dentro de `execute()` (ver
    `_backfill_player_enrichment`)."""
    user_id: int
    team_id: int
    ht_player_id: int


@dataclass
class SyncResult:
    sync_id: int
    status: str
    snapshots_written: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    # HL-140: qué cambió respecto al sync anterior — {"category", "summary"}
    changes: list[dict[str, str]] = field(default_factory=list)
    # HL-161, 2026-08-04: solo los usa `execute_transfers_history` — cuántas
    # páginas de transfersteam.xml se pidieron y cuántas transferencias se
    # vieron en total vs. cuántas eran nuevas de verdad.
    pages_fetched: int = 0
    transfers_seen: int = 0
    transfers_new: int = 0


class SyncTeamHandler:
    def __init__(self, uow: UnitOfWork, chpp: CHPPGateway) -> None:
        self._uow = uow
        self._chpp = chpp

    async def execute(
        self, cmd: SyncTeamCommand, on_progress: ProgressReporter | None = None
    ) -> SyncResult:
        files = cmd.files or DEFAULT_FILES
        async with self._uow as uow:
            sync_id = await uow.syncs.create(cmd.user_id, cmd.team_id, kind=",".join(files))
            result = SyncResult(sync_id=sync_id, status="completed")
            captured_at = datetime.now(UTC)

            for file in files:  # secuencial: requisito CHPP
                await _report(on_progress, f"Descargando {FILE_LABELS.get(file, file)}...")
                try:
                    params: dict[str, Any] = {"teamID": cmd.ht_team_id}
                    if file in ("leaguedetails", "leaguefixtures"):
                        params = {"leagueLevelUnitID": await self._series_ht_id(uow, cmd.team_id)}
                    payload = await self._chpp.fetch(
                        file, version=FILE_VERSIONS.get(file, "latest"), **params
                    )
                    await self._persist(
                        uow, sync_id, cmd.team_id, cmd.ht_team_id, file, payload,
                        captured_at, result,
                    )
                except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                    result.errors.append(f"{file}: {exc}")
                    result.status = "partial"

            from app.infrastructure.db import models as m

            for c in result.changes:
                uow.session.add(m.SyncChange(
                    sync_id=sync_id, team_id=cmd.team_id, category=c["category"],
                    summary=c["summary"], created_at=captured_at,
                ))

            # HL-161: enriquecimiento de jugadores vendidos (edad en la
            # venta, país, carácter, especialidad, país destino) — pedido
            # explícitamente 2026-08-04 SIN botón: se dispara solo aquí,
            # dentro del sync normal, porque una vez resuelto para un
            # jugador nunca hace falta repetirlo. Solo cuando `transfersteam`
            # es parte de este sync (donde se detectan ventas) — evita
            # llamadas CHPP de más en syncs restringidos a otros ficheros
            # (p. ej. los de test que sólo piden players/training/economy).
            if "transfersteam" in files:
                # `captured_at` (arriba) es aware (UTC) — sirve para Match y
                # otras tablas, pero `sold_at` leído de SQLite siempre llega
                # naive (no conserva tzinfo en el viaje de ida y vuelta), así
                # que la resta de fechas en `_apply_player_enrichment`
                # necesita su propio "ahora" naive, no el mismo de arriba.
                fetched_at = datetime.now(UTC).replace(tzinfo=None)
                await self._backfill_sold_player_details(
                    uow, cmd.team_id, fetched_at, result, on_progress
                )
                await self._backfill_mandatory_listing_count(uow, cmd.team_id, result)

            # 2026-08-05, pedido explícitamente: "tienes que sincronizar
            # todos los xml que importen cada vez que sincronizamos" — hasta
            # ahora LastMatch/Caps/CareerAssists (playerdetails.xml) y
            # HatStats/sectores (matchdetails.xml) se quedaban obsoletos
            # esperando un botón aparte ("Actualizar detalles de jugadores",
            # "Sincronizar detalles"). Ambos entran aquí, siempre que su
            # fichero base haya sido parte de este sync — cada uno sigue
            # siendo tantas llamadas CHPP como jugadores/partidos pendientes
            # haya, pero ya no depende de que el usuario recuerde pedirlo.
            if "players" in files:
                await self._sync_active_roster_player_details(
                    uow, cmd.team_id, captured_at, result, on_progress
                )
            if "matches" in files:
                await self._backfill_missing_match_details(
                    uow, cmd.team_id, cmd.ht_team_id, result, on_progress
                )

            await uow.syncs.finalize(
                sync_id, status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _backfill_sold_player_details(
        self,
        uow: UnitOfWork,
        team_id: int,
        fetched_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Automático, sin botón (HL-161, 2026-08-04): recorre los
        jugadores VENDIDOS a los que aún les falta algo — edad en la venta
        (sin snapshot previo), país, carácter, especialidad, TSI en la
        compra, o país destino — y lo rellena con una llamada CHPP cada
        uno. Una vez resuelto, esa columna nunca vuelve a pedirse para ese
        jugador."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        has_pre_sale_snapshot = (
            select(m.PlayerSnapshot.id)
            .where(
                m.PlayerSnapshot.player_id == m.Player.id,
                m.PlayerSnapshot.captured_at <= m.Player.sold_at,
            )
            .exists()
        )
        # 2026-08-05: mismo principio, ancla en `purchased_at` — "Edad de
        # compra" en Detalle necesita esto para TODO jugador con compra
        # conocida, esté vendido o siga en la plantilla, no solo los
        # vendidos (a diferencia del resto de este backfill).
        has_post_purchase_snapshot = (
            select(m.PlayerSnapshot.id)
            .where(
                m.PlayerSnapshot.player_id == m.Player.id,
                m.PlayerSnapshot.captured_at >= m.Player.purchased_at,
            )
            .exists()
        )
        needs_enrichment = (
            await uow.session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id,
                    ~m.Player.enrichment_attempted,
                    (
                        (
                            m.Player.sold_at.is_not(None)
                            & (
                                m.Player.native_country.is_(None)
                                | m.Player.agreeability.is_(None)
                                | m.Player.specialty.is_(None)
                                | m.Player.mother_club_team_id.is_(None)
                                | (m.Player.age_years_at_sale.is_(None) & ~has_pre_sale_snapshot)
                            )
                        )
                        | (
                            m.Player.purchased_at.is_not(None)
                            & m.Player.age_years_at_purchase.is_(None)
                            & ~has_post_purchase_snapshot
                        )
                    ),
                )
            )
        ).scalars().all()
        for ht_player_id in needs_enrichment:
            await _report(on_progress, f"Descargando ficha de ex-jugador {ht_player_id}...")
            try:
                wrote = await self._apply_player_enrichment(uow, ht_player_id, fetched_at)
                result.snapshots_written += 1 if wrote else 0
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"player_enrichment:{ht_player_id}: {exc}")
                result.status = "partial"

        # HL-161: precio de compra + TSI en la compra vía transfersplayer.xml.
        # 2026-08-05, pedido explícitamente ("sincroniza todos los xml que
        # importen"): unificada con lo que antes solo cubría el botón manual
        # "Actualizar transferencias" (`trigger_purchase_price_sync`) — CUALQUIER
        # jugador (vendido o activo) sin `purchase_price` conocido (real o
        # manual), MÁS los vendidos cuyo `purchase_price` ya se resolvió ANTES
        # de que existiera esta captura de TSI (sin este segundo caso,
        # `tsi_at_purchase` se quedaría en "?" para siempre — visto en vivo
        # contra la cuenta real). Sigue siendo "una vez por jugador, para
        # siempre": `tsi_at_purchase_attempted` es el mismo flag en ambos casos.
        needs_tsi_at_purchase = (
            await uow.session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id,
                    ~m.Player.tsi_at_purchase_attempted,
                    (
                        (
                            m.Player.purchase_price.is_(None)
                            & m.Player.purchase_price_manual.is_(None)
                        )
                        | (
                            m.Player.sold_at.is_not(None)
                            & m.Player.tsi_at_purchase.is_(None)
                        )
                    ),
                )
            )
        ).scalars().all()
        for ht_player_id in needs_tsi_at_purchase:
            await _report(
                on_progress, f"Descargando transferencias de jugador {ht_player_id}..."
            )
            try:
                wrote = await self._apply_transfers_player_purchase(
                    uow, team_id, ht_player_id
                )
                result.snapshots_written += 1 if wrote else 0
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"tsi_at_purchase:{ht_player_id}: {exc}")
                result.status = "partial"

        needs_destination = (
            await uow.session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id,
                    m.Player.buyer_team_id.is_not(None),
                    m.Player.destination_country.is_(None),
                )
            )
        ).scalars().all()
        for ht_player_id in needs_destination:
            await _report(on_progress, f"Descargando país destino de jugador {ht_player_id}...")
            try:
                wrote = await self._apply_destination_country(uow, ht_player_id)
                result.snapshots_written += 1 if wrote else 0
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"destination_country:{ht_player_id}: {exc}")
                result.status = "partial"

    async def _backfill_mandatory_listing_count(
        self, uow: UnitOfWork, team_id: int, result: SyncResult
    ) -> None:
        """HL-161, 2026-08-04 — corrección pedida explícitamente por el
        usuario: vender un jugador en Hattrick EXIGE listarlo primero (el
        solo hecho de ponerlo transferible cuesta 1.000, aparte de si
        alguien puja o no), así que CUALQUIER jugador VENDIDO tuvo, como
        mínimo, un intento de venta — aunque `currentbids.xml` (una foto del
        mercado en el instante del sync) nunca lo haya pillado listado a
        tiempo, que es el caso normal para casi cualquier venta ya cerrada
        antes de sincronizar, y SIEMPRE el caso para los ~410 jugadores del
        backfill histórico de `execute_transfers_history` (transfersteam.xml
        no dice nada de si un jugador pasó por el mercado, solo que se
        vendió). No pisa un `listing_count` ya mayor que 0 — ese sí viene de
        una detección real vía `_persist_currentbids`, y puede ser más de 1
        si se relistó."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        players = (
            await uow.session.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id,
                    m.Player.sold_at.is_not(None),
                    m.Player.listing_count == 0,
                )
            )
        ).scalars().all()
        for player in players:
            player.listing_count = 1
            result.snapshots_written += 1

    async def _backfill_missing_match_details(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """2026-08-05, pedido explícitamente: "sincroniza todos los xml que
        importen cada vez que sincronizamos" — HatStats y el desglose por
        sector ya no se quedan en "—" esperando el botón "Sincronizar
        detalles" de Partidos. `matches.xml` solo trae calendario y
        resultado; `matchdetails.xml` se pide por partido, así que se
        recorre aquí cualquier partido TERMINADO del propio club al que le
        falten ratings, o (si fue de local) el aforo del partido — mismo
        criterio que ya usaba ese botón (`trigger_match_details_sync`).
        Un resultado ya jugado no cambia, así que esto es "una vez por
        partido, para siempre": la propia ausencia de la fila es el gate,
        sin necesitar un flag "attempted" aparte."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        ratings_missing = ~m.Match.ht_match_id.in_(select(m.MatchRating.ht_match_id))
        stadium_missing_on_home = (
            (m.Match.home_team_ht_id == ht_team_id)
            & ~m.Match.ht_match_id.in_(select(m.StadiumHistory.ht_match_id))
        )
        pending = (
            await uow.session.execute(
                select(m.Match.ht_match_id).where(
                    (m.Match.home_team_ht_id == ht_team_id)
                    | (m.Match.away_team_ht_id == ht_team_id),
                    m.Match.status.ilike("finished"),
                    (ratings_missing | stadium_missing_on_home),
                )
            )
        ).scalars().all()
        if not pending:
            return

        arena_capacity: dict[str, int] | None = None
        try:
            arena = await self._chpp.fetch(
                "arenadetails", version=FILE_VERSIONS["arenadetails"], teamID=ht_team_id,
            )
            arena_capacity = arena.get("current_capacity")
        except Exception as exc:  # noqa: BLE001 — no invalida ratings si falla solo el aforo
            result.errors.append(f"arenadetails: {exc}")

        for ht_match_id in pending:
            await _report(on_progress, f"Descargando detalles de partido {ht_match_id}...")
            try:
                already_ratings = await uow.session.scalar(
                    select(m.MatchRating.id).where(m.MatchRating.ht_match_id == ht_match_id)
                )
                match = await uow.session.scalar(
                    select(m.Match).where(m.Match.ht_match_id == ht_match_id)
                )
                is_own_home_match = bool(
                    match is not None and match.home_team_ht_id == ht_team_id
                )
                already_stadium = await uow.session.scalar(
                    select(m.StadiumHistory.id).where(m.StadiumHistory.ht_match_id == ht_match_id)
                )
                payload = await self._chpp.fetch(
                    "matchdetails", version=FILE_VERSIONS["matchdetails"], matchID=ht_match_id,
                )
                # Defensivo: `_persist_match_details` confía en
                # `payload["ht_match_id"]`, no en el ID pedido — nunca debería
                # discrepar contra CHPP real (cada matchID pedido trae SU
                # propio partido), pero este método es el primero que pide
                # varios matchID distintos en el mismo lote, así que una
                # respuesta que no correspondiera al partido pedido no debe
                # escribirse contra la fila de OTRO partido.
                if payload.get("ht_match_id") != ht_match_id:
                    continue
                self._persist_match_details(
                    uow, payload, result,
                    team_id=team_id, match=match,
                    write_ratings=not bool(already_ratings),
                    write_stadium=is_own_home_match and not bool(already_stadium),
                    arena_capacity=arena_capacity,
                )
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"matchdetails:{ht_match_id}: {exc}")
                result.status = "partial"

    async def execute_match_details(self, cmd: SyncMatchDetailsCommand) -> SyncResult:
        """Ratings por sector y eventos de un partido terminado. HL-071/072.

        Idempotente por ht_match_id: si ya hay ratings para este partido, no
        se vuelve a pedir ni a escribir — el resultado de un partido jugado no
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
                    "matchdetails", version=FILE_VERSIONS["matchdetails"],
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
            except Exception as exc:  # noqa: BLE001 — mismo patrón que execute()
                result.errors.append(f"matchdetails: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

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
                uow.session.add(m.MatchRating(
                    ht_match_id=ht_match_id, team_ht_id=team.get("team_id", 0),
                    is_home=(side == "home"),
                    midfield=ratings.get("midfield", 0),
                    right_def=ratings.get("right_def", 0),
                    central_def=ratings.get("central_def", 0),
                    left_def=ratings.get("left_def", 0),
                    right_att=ratings.get("right_att", 0),
                    central_att=ratings.get("central_att", 0),
                    left_att=ratings.get("left_att", 0),
                    tactic_type=team.get("tactic_type", 0),
                    tactic_skill=team.get("tactic_skill", 0),
                    # CHPP nunca trae <TeamAttitude> para el lado que no es
                    # el del usuario (verificado en vivo) — sin la bandera
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
                ))
                result.snapshots_written += 1

            for ev in payload.get("events", []):
                uow.session.add(m.MatchEvent(
                    ht_match_id=ht_match_id, minute=ev.get("minute", 0),
                    event_type_id=ev.get("type_id", 0),
                    subject_team_ht_id=ev.get("subject_team_id", 0),
                    text=ev.get("text", ""),
                ))
                result.snapshots_written += 1

        if write_stadium and match is not None:
            arena = payload.get("arena") or {}
            capacity = arena_capacity or {}
            sold_total = arena.get("spectators", 0)
            uow.session.add(m.StadiumHistory(
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
                sold_terraces=arena.get("sold_terraces", 0),
                sold_basic=arena.get("sold_basic", 0),
                sold_roof=arena.get("sold_roof", 0),
                sold_vip=arena.get("sold_vip", 0),
            ))
            result.snapshots_written += 1

    async def _backfill_foreign_match_type(self, uow: UnitOfWork, ht_match_id: int) -> None:
        """Crea la fila `Match` de un partido AJENO (selección nacional,
        Masters, juvenil...) que `playerdetails.xml` expuso vía `LastMatch`
        pero que `matches.xml`/`leaguefixtures.xml` nunca traen — esos solo
        ven los partidos del propio club. Sin esta fila, `experience_progress`
        (INNER JOIN contra `matches`) descarta el partido en silencio y ese
        tipo de experiencia (Masters, amistoso de selección, juvenil) nunca
        se cuenta, aunque LastMatch SÍ lo muestre.

        `matchdetails.xml` funciona para cualquier `matchID`, no solo los del
        equipo propio (mismo patrón que `playerdetails.xml` por `playerID`).
        Se pide una única vez por partido: si la fila ya existe, no se
        vuelve a pedir — un partido jugado no cambia de tipo ni de resultado.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        exists = await uow.session.scalar(
            select(m.Match.id).where(m.Match.ht_match_id == ht_match_id)
        )
        if exists is not None:
            return
        payload = await self._chpp.fetch(
            "matchdetails", version=FILE_VERSIONS["matchdetails"], matchID=ht_match_id,
        )
        if not payload.get("ht_match_id"):
            return  # chpp error / partido sin datos: nada que crear todavía
        date_str = payload.get("match_date", "")
        played_at = (
            datetime.fromisoformat(date_str).replace(tzinfo=UTC)
            if date_str else datetime.now(UTC)
        )
        home = payload.get("home") or {}
        away = payload.get("away") or {}
        uow.session.add(m.Match(
            ht_match_id=ht_match_id,
            played_at=played_at,
            match_type=payload.get("match_type", 0),
            status="FINISHED",
            home_team_ht_id=home.get("team_id", 0),
            away_team_ht_id=away.get("team_id", 0),
            home_team_name=home.get("name", ""),
            away_team_name=away.get("name", ""),
            home_goals=home.get("goals", -1),
            away_goals=away.get("goals", -1),
        ))

    async def _apply_player_details(
        self, uow: UnitOfWork, ht_player_id: int, captured_at: datetime
    ) -> bool:
        """Núcleo reutilizable de `execute_player_details` (comando aparte,
        un jugador) y del paso automático dentro de `execute()` (2026-08-05,
        pedido explícitamente: "sincroniza todos los xml que importen cada
        vez que sincronizamos" — un sync ya no deja `LastMatch`/Caps/HatStats
        obsoletos esperando un botón separado).

        Club de origen y última posición/rating jugado de UN jugador (HL-15x
        fase B). No es append-only: se escribe sobre el snapshot más reciente
        del jugador en vez de crear uno nuevo, porque `LastMatch` no es un
        cambio de habilidades — crear una fila nueva por cada semana solo por
        esto duplicaría snapshots sin motivo.

        `LastMatch` no viene por defecto: hace falta pedirlo explícitamente
        con `includeMatchInfo=true` (confirmado en vivo — sin ese parámetro
        CHPP sirve el resto de campos pero omite el bloque entero, no es
        que expire ni que dependa del momento en que se sincroniza).

        Devuelve si algo REALMENTE cambió, no si se hizo la llamada CHPP —
        2026-08-05: al pasar a pedirse en cada sync (antes, solo a demanda),
        un sync repetido sin novedades debía seguir pudiendo reportar
        "sin cambios" en vez de sumar 24 escrituras fantasma cada vez.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        payload = await self._chpp.fetch(
            "playerdetails", version=FILE_VERSIONS["playerdetails"],
            playerID=ht_player_id, includeMatchInfo="true",
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
            # HL-15x #21: player_snapshots.last_match_* se pisa cada vez
            # (arriba). Para tener una serie en el tiempo (sparkline) hace
            # falta ir acumulando cada partido distinto visto en una tabla
            # append-only aparte — dedup por ht_match_id para no repetir
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
            # ajeno nunca tiene fila en `matches` — sin esto, el JOIN de
            # `experience_progress` lo descartaba en silencio. matchdetails.xml
            # funciona para CUALQUIER matchID (verificado, mismo patrón que
            # playerdetails), así que se rellena una vez y queda para
            # siempre (un partido jugado no cambia).
            ht_match_id = last_match.get("ht_match_id", 0)
            if ht_match_id:
                await self._backfill_foreign_match_type(uow, ht_match_id)
        # CareerAssists no está en players.xml (ver parsers) — solo aquí,
        # en playerdetails.
        if "career_assists" in payload and snap.career_assists != payload["career_assists"]:
            snap.career_assists = payload["career_assists"]
            changed = True
        # Caps/CapsU20: totales de carrera con la selección nacional —
        # única forma barata de saber "sí, este jugador ha jugado con la
        # selección" (HL-15x, pedido 2026-08-05).
        if "caps" in payload and snap.career_caps != payload["caps"]:
            snap.career_caps = payload["caps"]
            changed = True
        if "caps_u20" in payload and snap.career_caps_u20 != payload["caps_u20"]:
            snap.career_caps_u20 = payload["caps_u20"]
            changed = True
        return changed

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
        "Actualizar detalles de jugadores" — se pide para TODA la plantilla
        activa en cada sync normal, una llamada CHPP por jugador. A
        diferencia del backfill de vendidos (una vez y listo), esto SÍ se
        repite cada sync porque LastMatch/Caps cambian semana a semana
        mientras el jugador sigue jugando."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        ht_player_ids = (
            await uow.session.execute(
                select(m.Player.ht_player_id).where(
                    m.Player.team_id == team_id, m.Player.left_team_at.is_(None),
                )
            )
        ).scalars().all()
        for ht_player_id in ht_player_ids:
            await _report(on_progress, f"Descargando ficha de jugador {ht_player_id}...")
            try:
                wrote = await self._apply_player_details(uow, ht_player_id, captured_at)
                result.snapshots_written += 1 if wrote else 0
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"playerdetails:{ht_player_id}: {exc}")
                result.status = "partial"

    async def execute_player_details(self, cmd: SyncPlayerDetailsCommand) -> SyncResult:
        """Comando aparte para refrescar UN jugador a demanda (p. ej. desde
        la ficha del jugador) — reusa `_apply_player_details`, el mismo
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
            except Exception as exc:  # noqa: BLE001 — mismo patrón que execute_match_details
                result.errors.append(f"playerdetails: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _apply_transfers_player_purchase(
        self, uow: UnitOfWork, team_id: int, ht_player_id: int
    ) -> bool:
        """Núcleo de `execute_transfers_player` — recibe el `uow` ya abierto
        (mismo motivo que `_apply_player_enrichment`: reutilizable también
        desde `_backfill_sold_player_details`, solo para el TSI, en
        jugadores cuyo `purchase_price` YA se resolvió antes de que
        existiera esta captura de TSI — sin esto, `tsi_at_purchase` se
        quedaría en "?" para siempre, porque el endpoint de precio de
        compra ya no vuelve a llamarlos)."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        payload = await self._chpp.fetch(
            "transfersplayer", version=FILE_VERSIONS["transfersplayer"],
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
            # máximo una vez" — transfersplayer.xml ya trae TODA la
            # historia del jugador; si no aparecemos como comprador ahora,
            # nunca vamos a aparecer (el historial no cambia hacia atrás),
            # así que no tiene sentido volver a pedirlo en cada sync.
            player.tsi_at_purchase_attempted = True
            return True
        if player.purchase_price is None:
            date_str = own_purchase.get("deadline", "")
            if date_str:
                player.purchased_at = datetime.fromisoformat(date_str).replace(tzinfo=UTC)
            player.purchase_price = own_purchase.get("price", 0)
        if player.tsi_at_purchase is None and own_purchase.get("tsi"):
            player.tsi_at_purchase = own_purchase["tsi"]
        player.tsi_at_purchase_attempted = True
        return True

    async def execute_transfers_player(self, cmd: SyncTransfersPlayerCommand) -> SyncResult:
        """HL-161: precio de compra real para un jugador que `_persist_transfers`
        (transfersteam.xml, historial del EQUIPO) no pudo resolver — porque
        llegó antes de sincronizar con esta app, o porque su compra quedó
        fuera de la única página que CHPP entrega por defecto.

        Solo escribe si CHPP trae una transferencia donde el comprador
        somos nosotros; si el jugador nunca aparece comprándose (p. ej.
        vino de la propia cantera), no se toca `purchase_price` — el
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
            except Exception as exc:  # noqa: BLE001 — mismo patrón que execute_match_details
                result.errors.append(f"transfersplayer: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _apply_player_enrichment(
        self, uow: UnitOfWork, ht_player_id: int, fetched_at: datetime
    ) -> bool:
        """Núcleo de `execute_player_enrichment_backfill` — recibe un `uow`
        YA ABIERTO en vez de abrir el suyo, para poder llamarse tanto desde
        ahí como desde `execute()` (el `async with self._uow` de
        `SqlAlchemyUnitOfWork` no es reentrante: abrir uno anidado
        reemplazaría/cerraría la sesión del de fuera a medio sync)."""
        from sqlalchemy import select

        from app.domain.value_objects.skill import Age
        from app.infrastructure.db import models as m

        payload = await self._chpp.fetch(
            "playerdetails", version=FILE_VERSIONS["playerdetails"],
            playerID=ht_player_id,
        )
        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if player is None:
            return False

        if payload.get("chpp_error"):
            # ID que ya no resuelve en Hattrick (ver `_is_chpp_error`) — no
            # es un fallo transitorio, así que se marca para no volver a
            # pedirlo nunca (ver `enrichment_attempted` en models.py).
            player.enrichment_attempted = True
            return True

        wrote_anything = False
        age_years = payload.get("age_years")
        age_days = payload.get("age_days")
        if (
            player.sold_at is not None and player.age_years_at_sale is None
            and age_years is not None and age_days is not None
        ):
            elapsed_days = (fetched_at - player.sold_at).days
            try:
                at_sale = Age(age_years, age_days).add_days(-elapsed_days)
            except ValueError:
                # Nunca se inventa una edad — si la resta da negativo se
                # deja tal cual, no se fuerza un número.
                pass
            else:
                player.age_years_at_sale = at_sale.years
                player.age_days_at_sale = at_sale.days
                wrote_anything = True
        # 2026-08-05: misma reconstrucción, ancla en `purchased_at` en vez
        # de `sold_at` — para TODO jugador con compra conocida, esté o no
        # vendido (pedida para "Edad de compra" en Detalle).
        if (
            player.purchased_at is not None and player.age_years_at_purchase is None
            and age_years is not None and age_days is not None
        ):
            elapsed_days = (fetched_at - player.purchased_at).days
            try:
                at_purchase = Age(age_years, age_days).add_days(-elapsed_days)
            except ValueError:
                pass
            else:
                player.age_years_at_purchase = at_purchase.years
                player.age_days_at_purchase = at_purchase.days
                wrote_anything = True

        native_league_name = payload.get("native_league_name")
        if player.native_country is None and native_league_name:
            player.native_country = native_league_name
            wrote_anything = True
        if player.agreeability is None and payload.get("agreeability") is not None:
            player.agreeability = payload["agreeability"]
            wrote_anything = True
        if player.specialty is None and payload.get("specialty") is not None:
            player.specialty = payload["specialty"]
            wrote_anything = True
        # 2026-08-04: MotherClub/TeamID — "canterano" real (ver corrección en
        # parse_playerdetails). 0 = sin MotherClub en el XML, se guarda tal
        # cual (nunca coincide con un ht_team_id real, así que no hace falta
        # tratarlo distinto de "no es canterano de nadie").
        if player.mother_club_team_id is None and payload.get("mother_club_team_id") is not None:
            player.mother_club_team_id = payload["mother_club_team_id"]
            wrote_anything = True

        # 2026-08-05, pedido explícitamente: "backfill de un jugador máximo
        # una vez" — si algún campo sigue sin poder rellenarse tras ESTE
        # intento (típicamente la edad reconstruida hacia atrás: si dio
        # negativo una vez, va a dar negativo siempre — es una resta contra
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
        entrenamiento ni azar) — se resta a la edad de HOY los días reales
        desde `sold_at`. Solo se toca si no hay ya un `player_snapshots` de
        antes de la venta (ese dato real siempre gana). País/carácter/
        especialidad casi no cambian con el tiempo, así que el valor de HOY
        sirve de base razonable aunque el jugador ya no esté en el equipo —
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
            except Exception as exc:  # noqa: BLE001 — mismo patrón que execute_transfers_player
                result.errors.append(f"player_enrichment: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _apply_destination_country(self, uow: UnitOfWork, ht_player_id: int) -> bool:
        """Núcleo de `execute_destination_country_backfill` — mismo motivo
        que `_apply_player_enrichment`: recibe el `uow` ya abierto."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        player = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if player is None or player.buyer_team_id is None:
            return False

        payload = await self._chpp.fetch(
            "teamdetails", version=FILE_VERSIONS["teamdetails"],
            teamID=player.buyer_team_id,
        )
        team = next(iter(payload.get("teams", [])), None)
        country_name = team.get("country_name") if team else None
        if not country_name:
            return False
        player.destination_country = country_name
        return True

    async def execute_destination_country_backfill(
        self, cmd: SyncPlayerEnrichmentCommand
    ) -> SyncResult:
        """HL-161: país del equipo COMPRADOR — columna "País Destino" del
        Excel del usuario. `playerdetails.xml` no lo trae (solo un
        `LeagueID` numérico, sin nombre) — hace falta `teamdetails.xml` del
        equipo comprador (`buyer_team_id`, guardado por `_persist_transfers`
        al detectar la venta), que sí funciona para equipos ajenos y trae
        `Country/CountryName` directo — verificado en vivo 2026-08-04."""
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
            except Exception as exc:  # noqa: BLE001 — mismo patrón que execute_transfers_player
                result.errors.append(f"destination_country: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def _series_ht_id(self, uow: UnitOfWork, team_id: int) -> int:
        """leaguedetails se pide por serie (LeagueLevelUnitID), no por equipo.
        Requiere haber sincronizado teamdetails antes en el mismo sync."""
        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)
        if team is None or not team.series_ht_id:
            raise ValueError(
                "no se conoce la serie del equipo: sincroniza 'teamdetails' antes "
                "que 'leaguedetails'"
            )
        return int(team.series_ht_id)

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
            new_hash = dict_hash(payload)
            if await repo.get_last_hash(team_id) == new_hash:
                result.unchanged += 1
                return
            old_values = await repo.get_last_values(team_id)
            await repo.append(sync_id, team_id, payload, new_hash, captured_at)
            result.snapshots_written += 1
            if file == "economy":
                from app.infrastructure.db import models as m

                team = await uow.session.get(m.Team, team_id)
                currency = team.currency_name if team else ""
                rate = (team.currency_rate or 1.0) if team else 1.0
                changes = diff_economy(old_values, payload, currency, rate)
                category = "economía"
            else:
                changes = diff_training(old_values, payload)
                category = "entrenamiento"
            result.changes.extend({"category": category, "summary": c} for c in changes)
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
            await self._persist_currentbids(uow, team_id, payload, result)
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
        if file != "players":
            return  # TODO: handler para arena…
        roster = payload.get("players", [])
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
            changes = diff_player_skills(old_values, p, name)
            result.changes.extend({"category": "jugadores", "summary": c} for c in changes)

        if roster:
            # Quien no vino en este players.xml ya no está en el club — se
            # marca left_team_at (nunca se borra). Un roster vacío no dispara
            # esto: sería marcar a toda la plantilla como salida por un fetch
            # vacío/roto, exactamente el tipo de bug que esta guarda evita.
            current_ids = {p["ht_player_id"] for p in roster}
            await uow.players.mark_departed(team_id, current_ids, captured_at)

    async def _staff_row(
        self, uow: UnitOfWork, sync_id: int, team_id: int, captured_at: datetime
    ) -> Any:
        """La misma fila de staff para este sync: club y stafflist son ficheros
        distintos que rellenan campos distintos de un único snapshot."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        row = await uow.session.scalar(
            select(m.StaffSnapshot).where(
                m.StaffSnapshot.sync_id == sync_id, m.StaffSnapshot.team_id == team_id
            )
        )
        if row is None:
            row = m.StaffSnapshot(
                sync_id=sync_id, team_id=team_id, captured_at=captured_at,
                content_hash=b"\x00" * 32,
            )
            uow.session.add(row)
        return row

    async def _persist_staff(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        file: str,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        row = await self._staff_row(uow, sync_id, team_id, captured_at)
        if file == "club":
            row.assistant_trainer_levels = payload.get("assistant_trainer_levels", 0)
            row.form_coach_levels = payload.get("form_coach_levels", 0)
            row.medic_levels = payload.get("medic_levels", 0)
            row.sport_psychologist_levels = payload.get("sport_psychologist_levels", 0)
            row.tactical_assistant_levels = payload.get("tactical_assistant_levels", 0)
            row.financial_director_levels = payload.get("financial_director_levels", 0)
            row.spokesperson_levels = payload.get("spokesperson_levels", 0)
            row.youth_investment = payload.get("youth_investment", 0)
            row.youth_level = payload.get("youth_level", 0)
        else:  # stafflist
            tr = payload.get("trainer", {})
            row.trainer_skill_level = tr.get("skill_level", 0)
            row.trainer_type = tr.get("trainer_type", 2)
            row.trainer_leadership = tr.get("leadership", 0)
        row.content_hash = dict_hash({
            "a": row.assistant_trainer_levels, "t": row.trainer_skill_level,
            "tt": row.trainer_type, "fc": row.form_coach_levels, "md": row.medic_levels,
        })
        result.snapshots_written += 1

    async def _persist_world(
        self,
        uow: UnitOfWork,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """worlddetails.xml, 2026-08-04 — trae TODOS los países en
        `<LeagueList>`, no uno: se guarda una fila de `WorldContext` (+ sus
        `WorldCup`) por cada país, y se refresca `Team.currency_rate`/
        `currency_name` para el país del EQUIPO propio (cruzando por
        `Team.ht_league_id`, de teamdetails.xml) — antes esos dos campos no
        los ponía nada en el flujo real, solo un script de desarrollo los
        había escrito a mano una vez."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)

        for league in payload.get("leagues", []):
            lid = league.get("ht_league_id", 0)
            row = await uow.session.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == lid)
            )
            if row is None:
                row = m.WorldContext(ht_league_id=lid)
                uow.session.add(row)
            row.league_name = league.get("league_name", "")
            row.country_name = league.get("country_name", "")
            row.season = league.get("season", 0)
            row.season_offset = league.get("season_offset", 0)
            row.match_round = league.get("match_round", 0)
            row.match_rounds_left = league.get("match_rounds_left", 0)
            row.number_of_levels = league.get("number_of_levels", 0)
            row.league_system_id = league.get("league_system_id", 1)
            row.currency_name = league.get("currency_name", "")
            row.currency_rate = league.get("currency_rate", 1.0)
            for field, key in (
                ("training_date", "training_date"),
                ("cup_match_date", "cup_match_date"),
                ("series_match_date", "series_match_date"),
            ):
                raw = league.get(key) or ""
                try:
                    parsed = datetime.fromisoformat(raw).replace(tzinfo=UTC) if raw else None
                except ValueError:
                    parsed = None
                setattr(row, field, parsed)
            row.refreshed_at = captured_at
            result.snapshots_written += 1

            for cup in league.get("cups", []):
                cup_row = await uow.session.scalar(
                    select(m.WorldCup).where(
                        m.WorldCup.ht_league_id == lid,
                        m.WorldCup.cup_league_level == cup.get("cup_league_level", 0),
                        m.WorldCup.cup_level == cup.get("cup_level", 0),
                        m.WorldCup.cup_level_index == cup.get("cup_level_index", 0),
                    )
                )
                if cup_row is None:
                    cup_row = m.WorldCup(
                        ht_league_id=lid,
                        cup_level=cup.get("cup_level", 0),
                        cup_level_index=cup.get("cup_level_index", 0),
                    )
                    uow.session.add(cup_row)
                cup_row.ht_cup_id = cup.get("ht_cup_id", 0)
                cup_row.cup_name = cup.get("cup_name", "")
                cup_row.cup_league_level = cup.get("cup_league_level", 0)
                cup_row.match_round = cup.get("match_round", -1)
                cup_row.match_rounds_left = cup.get("match_rounds_left", 0)

            if team is not None and team.ht_league_id == lid:
                team.currency_name = row.currency_name
                team.currency_rate = row.currency_rate

    async def _persist_skill_ups(
        self,
        uow: UnitOfWork,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """Idempotente: un mismo pop (jugador, habilidad, nivel nuevo) no se
        cuenta dos veces aunque el fichero se sincronice varias veces."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        for ev in payload.get("skill_ups", []):
            exists = await uow.session.scalar(
                select(m.SkillUp.id).where(
                    m.SkillUp.ht_player_id == ev["ht_player_id"],
                    m.SkillUp.skill_id == ev["skill_id"],
                    m.SkillUp.new_level == ev["new_level"],
                )
            )
            if exists:
                result.unchanged += 1
                continue
            uow.session.add(m.SkillUp(
                team_id=team_id, ht_player_id=ev["ht_player_id"],
                skill_id=ev["skill_id"], old_level=ev["old_level"],
                new_level=ev["new_level"], season=ev["season"],
                match_round=ev["match_round"], day_number=ev.get("day_number", 0),
                recorded_at=captured_at,
            ))
            result.snapshots_written += 1

    async def _persist_matches(
        self, uow: UnitOfWork, ht_team_id: int, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """Calendario y resultados: HL-070. Un partido no es un snapshot — es un
        hecho que se actualiza in-place (upcoming → finished) y se identifica
        por `ht_match_id`, único en CHPP."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        for mt in payload.get("matches", []):
            ht_match_id = mt["ht_match_id"]
            row = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == ht_match_id)
            )
            date_str = mt.get("match_date", "")
            played_at = (
                datetime.fromisoformat(date_str).replace(tzinfo=UTC)
                if date_str else datetime.now(UTC)
            )
            before = (
                MatchState(row.status, row.home_goals, row.away_goals)
                if row is not None else None
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

            is_home = row.home_team_ht_id == ht_team_id
            opponent = row.away_team_name if is_home else row.home_team_name
            after = MatchState(row.status, row.home_goals, row.away_goals)
            change = diff_match(before, after, is_home, opponent)
            if change:
                result.changes.append({"category": "partidos", "summary": change})

    async def _persist_league_fixtures(
        self, uow: UnitOfWork, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """Calendario completo de la serie — HL-090 fix.

        A diferencia de `_persist_matches` (que solo ve los partidos del
        equipo sincronizado), aquí llegan también los cruces entre dos
        rivales. Si el partido ya existe (porque `matches` ya lo trajo, o
        de un sync anterior), solo se rellenan `series_ht_id`/`match_round`
        — no se pisan campos que la otra fuente conoce mejor (`match_type`,
        `status`, goles ya confirmados). Si no existe, se crea con lo que
        trae este fichero, marcado como de liga."""
        from sqlalchemy import select

        from app.domain.value_objects.ht_constants import MATCH_TYPE_LEAGUE
        from app.infrastructure.db import models as m

        series_ht_id = payload.get("series_ht_id")
        for mt in payload.get("matches", []):
            ht_match_id = mt["ht_match_id"]
            row = await uow.session.scalar(
                select(m.Match).where(m.Match.ht_match_id == ht_match_id)
            )
            date_str = mt.get("match_date", "")
            played_at = (
                datetime.fromisoformat(date_str).replace(tzinfo=UTC)
                if date_str else datetime.now(UTC)
            )
            if row is None:
                home_goals = mt.get("home_goals")
                away_goals = mt.get("away_goals")
                row = m.Match(
                    ht_match_id=ht_match_id, played_at=played_at,
                    match_type=MATCH_TYPE_LEAGUE,
                    status="FINISHED" if home_goals is not None else "UPCOMING",
                    home_team_ht_id=mt.get("home_team_id", 0),
                    away_team_ht_id=mt.get("away_team_id", 0),
                    home_team_name=mt.get("home_team_name", ""),
                    away_team_name=mt.get("away_team_name", ""),
                    home_goals=home_goals if home_goals is not None else -1,
                    away_goals=away_goals if away_goals is not None else -1,
                )
                uow.session.add(row)
                result.snapshots_written += 1
            elif row.series_ht_id == series_ht_id and row.match_round == mt.get("match_round"):
                result.unchanged += 1
                continue
            else:
                result.snapshots_written += 1
            row.series_ht_id = series_ht_id
            row.match_round = mt.get("match_round")

    async def _persist_currentbids(
        self, uow: UnitOfWork, team_id: int, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """HL-161: cuenta intentos de venta hacia adelante. CHPP solo da
        una foto del momento (quién está en el mercado AHORA), nunca un
        historial — así que una aparición nueva (no estaba listado en el
        sync anterior, ahora sí) se cuenta como un intento más. Si el
        jugador sigue listado desde el sync pasado, no se repite."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        listed_now = {p["ht_player_id"] for p in payload.get("listed_players", [])}
        roster = list(
            (
                await uow.session.execute(
                    select(m.Player).where(m.Player.team_id == team_id)
                )
            ).scalars()
        )
        for player in roster:
            is_listed = player.ht_player_id in listed_now
            if is_listed and not player.currently_listed:
                player.listing_count += 1
                result.snapshots_written += 1
            elif is_listed == player.currently_listed:
                result.unchanged += 1
            player.currently_listed = is_listed

    async def _persist_teamdetails(
        self,
        uow: UnitOfWork,
        team_id: int,
        ht_team_id: int,
        payload: dict[str, Any],
        result: SyncResult,
    ) -> None:
        """Nombre, liga y serie del equipo — y sobre todo `series_ht_id`
        (LeagueLevelUnitID), sin el cual no se puede pedir leaguedetails: ese
        fichero se sincroniza por serie, no por equipo."""
        team = next(
            (t for t in payload.get("teams", []) if t.get("ht_team_id") == ht_team_id),
            None,
        )
        if team is None:
            return
        from app.infrastructure.db import models as m

        row = await uow.session.get(m.Team, team_id)
        if row is None:
            return
        before = (
            row.name, row.league_name, row.series_name, row.series_ht_id, row.ht_league_id,
            row.still_in_cup, row.current_cup_id, row.current_cup_match_round,
            row.current_cup_match_rounds_left,
        )
        row.name = team.get("name") or row.name
        row.league_name = team.get("league_name") or row.league_name
        row.series_name = team.get("series_name") or row.series_name
        row.series_ht_id = team.get("series_ht_id") or row.series_ht_id
        row.ht_league_id = team.get("ht_league_id") or row.ht_league_id
        still_in_cup = team.get("still_in_cup")
        if still_in_cup is not None:
            row.still_in_cup = bool(still_in_cup)
            cup = team.get("current_cup") if still_in_cup else None
            row.current_cup_id = cup.get("ht_cup_id") if cup else None
            row.current_cup_name = (cup.get("cup_name") or None) if cup else None
            row.current_cup_league_level = cup.get("cup_league_level") if cup else None
            row.current_cup_level = cup.get("cup_level") if cup else None
            row.current_cup_level_index = cup.get("cup_level_index") if cup else None
            row.current_cup_match_round = (
                cup.get("match_round") if cup and cup.get("match_round", -1) >= 0 else None
            )
            row.current_cup_match_rounds_left = (
                cup.get("match_rounds_left")
                if cup and cup.get("match_rounds_left", -1) >= 0 else None
            )
        after = (
            row.name, row.league_name, row.series_name, row.series_ht_id, row.ht_league_id,
            row.still_in_cup, row.current_cup_id, row.current_cup_match_round,
            row.current_cup_match_rounds_left,
        )
        if before == after:
            result.unchanged += 1
        else:
            result.snapshots_written += 1

    async def _persist_standings(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        ht_team_id: int,
        captured_at: datetime,
        payload: dict[str, Any],
        result: SyncResult,
    ) -> None:
        """Clasificación de la serie: HL-080. Una jornada ya registrada no se
        repite — la tabla completa de una jornada es la unidad append-only,
        no la fila de un equipo."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        # LeagueLevel/MaxLevel (HL-145) son del EQUIPO, no de una jornada —
        # se refrescan siempre, aunque esta jornada ya estuviera guardada.
        team = await uow.session.get(m.Team, team_id)
        if team is not None:
            team.league_level = payload.get("league_level", -1)
            team.max_level = payload.get("max_level", -1)

        series_ht_id = payload.get("series_ht_id", 0)
        # CurrentMatchRound de leaguedetails.xml es la jornada que está EN
        # CURSO (o a punto de arrancar), no la última jugada — verificado en
        # vivo: un sync hecho antes de que se juegue ningún partido reporta
        # CurrentMatchRound=1 con `Matches=0` para todos los equipos, y solo
        # tras jugarse esa jornada el valor sube a 2. Guardar el crudo
        # etiquetaría esa foto "sin jugar nada" como si fuera la jornada 1
        # real, y desplazaría todo lo demás un puesto. Restar 1 (con suelo en
        # 0) da "jornadas realmente completadas", que es lo que el resto del
        # sistema espera de `match_round`.
        match_round = max(payload.get("match_round", 0) - 1, 0)
        # leaguedetails.xml no trae la temporada; worlddetails sí. Sin
        # sincronizarlo aún, season=0 — honesto, no un dato inventado.
        world = await uow.session.scalar(
            select(m.WorldContext).order_by(m.WorldContext.refreshed_at.desc()).limit(1)
        )
        season = world.season if world is not None else 0
        exists = await uow.session.scalar(
            select(m.Standing.id).where(
                m.Standing.series_ht_id == series_ht_id,
                m.Standing.season == season,
                m.Standing.match_round == match_round,
            )
        )
        if exists:
            result.unchanged += 1
            return

        old_standing = await uow.session.scalar(
            select(m.Standing)
            .where(
                m.Standing.series_ht_id == series_ht_id,
                m.Standing.season == season,
                m.Standing.team_ht_id == ht_team_id,
            )
            .order_by(m.Standing.match_round.desc())
            .limit(1)
        )
        old_position = old_standing.position if old_standing is not None else None

        for t in payload.get("teams", []):
            uow.session.add(m.Standing(
                sync_id=sync_id, series_ht_id=series_ht_id, season=season,
                match_round=match_round, captured_at=captured_at,
                team_ht_id=t.get("ht_team_id", 0), team_name=t.get("name", ""),
                position=t.get("position", 0), played=t.get("matches", 0),
                won=t.get("won", 0), draws=t.get("draws", 0), lost=t.get("lost", 0),
                goals_for=t.get("goals_for", 0), goals_against=t.get("goals_against", 0),
                points=t.get("points", 0),
            ))
        result.snapshots_written += 1

        own = next(
            (t for t in payload.get("teams", []) if t.get("ht_team_id") == ht_team_id), None
        )
        if own is not None:
            change = diff_standing(old_position, own.get("position", 0), own.get("name", ""))
            if change:
                result.changes.append({"category": "liga", "summary": change})

    def _apply_buy_transfer(self, player: Any, t: dict[str, Any], result: SyncResult) -> None:
        """Núcleo de una compra — compartido por `_persist_transfers` (página
        más reciente, parte del sync normal) y `execute_transfers_history`
        (backfill paginado completo, HL-161 2026-08-04), para no mantener la
        misma lógica de "qué campo se pisa y cuál no" duplicada dos veces."""
        deadline = t.get("deadline") or ""
        # SQLite no conserva tzinfo en el viaje de ida y vuelta:
        # player.purchased_at leído de la BD siempre llega naive, así
        # que lo que se compara aquí debe serlo también — un valor
        # aware chocaría con un TypeError al comparar (visto en vivo
        # 2026-08-03, justo al arreglar el bug de parseo de más
        # arriba, que hasta entonces dejaba `buys`/`sells` siempre
        # vacíos y nunca llegaba a esta comparación).
        purchased_at = datetime.fromisoformat(deadline) if deadline else None
        # Un jugador puede aparecer varias veces si se compró más de una
        # vez (vendido y recomprado): se queda la fecha más reciente. Si
        # es la MISMA transacción que ya conocíamos (fecha igual o más
        # vieja), no se pisa precio/fecha — pero SÍ se rellena el TSI si
        # todavía faltaba (HL-161, 2026-08-04: antes este `continue`
        # también se saltaba el TSI para cualquier venta/compra ya
        # registrada ANTES de que este campo existiera, dejándolo en "?"
        # para siempre — visto en vivo contra la cuenta real).
        is_new_transaction = (
            player.purchased_at is None or purchased_at is None
            or purchased_at > player.purchased_at
        )
        if is_new_transaction:
            player.purchase_price = t.get("price", 0)
            player.purchased_at = purchased_at
        # HL-161: TSI de esta transacción exacta, para "Delta TSI" y
        # "Ganancia/TSI" en la tabla Detalle — nunca el de playerdetails
        # (ese es el de HOY, no el de la compra).
        if player.tsi_at_purchase is None and t.get("tsi"):
            player.tsi_at_purchase = t["tsi"]
        if is_new_transaction:
            result.snapshots_written += 1

    def _apply_sell_transfer(self, player: Any, t: dict[str, Any], result: SyncResult) -> None:
        """Núcleo de una venta — ver `_apply_buy_transfer`."""
        deadline = t.get("deadline") or ""
        sold_at = datetime.fromisoformat(deadline) if deadline else None
        is_new_transaction = (
            player.sold_at is None or sold_at is None or sold_at > player.sold_at
        )
        if is_new_transaction:
            player.sale_price = t.get("price", 0)
            player.sold_at = sold_at
        if player.tsi_at_sale is None and t.get("tsi"):
            player.tsi_at_sale = t["tsi"]
        # HL-161: equipo comprador — hace falta para resolver el país
        # destino después (ver `_backfill_sold_player_details`).
        if player.buyer_team_id is None and t.get("buyer_team_id"):
            player.buyer_team_id = t["buyer_team_id"]
        if is_new_transaction:
            result.snapshots_written += 1

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
        CHPP sin pedir página explícita) — jugadores que ya se fueron ANTES
        de que esta app empezara a sincronizar, o cuya transacción quedó
        más atrás en el historial, se resuelven con el backfill paginado
        completo del botón "Actualizar transferencias" — ver
        `execute_transfers_history`. Compras propias (`TransferType ==
        "B"`, comprador == este equipo) de jugadores que siguen en la
        plantilla; ventas propias (`TransferType == "S"`, vendedor == este
        equipo) de jugadores que ya se fueron pero cuya fila sigue
        existiendo (append-only, nunca se borra).

        También refresca `Team.transfer_total_*`/`transfer_number_*` — el
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
            t for t in transfers
            if t.get("transfer_type") == "B" and t.get("buyer_team_id") == ht_team_id
        ]
        sells = [
            t for t in transfers
            if t.get("transfer_type") == "S" and t.get("seller_team_id") == ht_team_id
        ]
        if not buys and not sells:
            return
        ids = {t["ht_player_id"] for t in buys} | {t["ht_player_id"] for t in sells}
        players = {
            p.ht_player_id: p
            for p in (
                await uow.session.execute(
                    select(m.Player).where(m.Player.ht_player_id.in_(ids))
                )
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

    def _split_player_name(self, full_name: str) -> tuple[str, str]:
        """`transfersteam.xml` solo trae un `PlayerName` combinado (a
        diferencia de `players.xml`, que separa Nombre/Apellido) — heurística
        de "última palabra = apellido" para crear una identidad mínima de un
        jugador que esta app nunca vio en la plantilla (ver
        `execute_transfers_history`). Cosmético: solo afecta cómo se separa
        el nombre para volver a unirlo igual (`f"{first} {last}"`) en la
        tabla Detalle — no a ningún cálculo de saldo."""
        parts = full_name.strip().rsplit(" ", 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return "", full_name.strip()

    async def execute_transfers_history(
        self, cmd: SyncTransfersHistoryCommand
    ) -> SyncResult:
        """HL-161, 2026-08-04 — botón "Actualizar transferencias": pagina
        transfersteam.xml completo (`pageIndex` 1..Pages, verificado en vivo
        que sí funciona — ver `parse_transfersteam`), más allá de la única
        página que trae el sync normal. Para cada compra/venta de este
        equipo, crea una identidad de jugador mínima si nunca se vio en
        `players.xml` (`_split_player_name` + `upsert_identity`) — así
        "Detalle" puede mostrar ~1000 transferencias reales, con huecos
        ("?") donde de verdad no hay forma de conocer skills/edad, en vez
        de descartar en silencio todo lo anterior a la última página.

        Idempotente y barato en re-ejecuciones: las páginas llegan de más
        reciente a más vieja, así que en cuanto una página no aporta ningún
        TransferID nuevo respecto a `Team.last_transfer_id_seen`, se para —
        no hace falta re-pedir las ~40 páginas cada vez que el usuario
        pulsa el botón, solo la primera vez (o si de verdad hay huecos)."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        async with self._uow as uow:
            sync_id = await uow.syncs.create(
                cmd.user_id, cmd.team_id, kind="transfers_history"
            )
            result = SyncResult(sync_id=sync_id, status="completed")

            team = await uow.session.get(m.Team, cmd.team_id)
            watermark = team.last_transfer_id_seen if team is not None else None
            highest_seen = watermark or 0

            try:
                page = 1
                total_pages = 1
                while page <= total_pages:
                    payload = await self._chpp.fetch(
                        "transfersteam", version=FILE_VERSIONS["transfersteam"],
                        teamID=cmd.ht_team_id, pageIndex=page,
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
                        break  # página vacía más allá del final real (visto en vivo)

                    own_transfers = [
                        t for t in page_transfers
                        if t.get("buyer_team_id") == cmd.ht_team_id
                        or t.get("seller_team_id") == cmd.ht_team_id
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
                            ht_player_id = t["ht_player_id"]
                            player = players.get(ht_player_id)
                            if player is None:
                                first, last = self._split_player_name(
                                    t.get("player_name", "")
                                )
                                player_id = await uow.players.upsert_identity(
                                    ht_player_id, cmd.team_id, first, last
                                )
                                player = await uow.session.get(m.Player, player_id)
                                players[ht_player_id] = player
                            if t.get("transfer_type") == "B":
                                self._apply_buy_transfer(player, t, result)
                            elif t.get("transfer_type") == "S":
                                self._apply_sell_transfer(player, t, result)
                            highest_seen = max(highest_seen, t.get("ht_transfer_id", 0))

                    if reached_known:
                        break
                    page += 1
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"transfers_history: {exc}")
                result.status = "partial"

            if team is not None and highest_seen > (watermark or 0):
                team.last_transfer_id_seen = highest_seen

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result
