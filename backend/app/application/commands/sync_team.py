"""Use case: sincronizar un equipo desde CHPP (iniciado por el usuario).

Pipeline por file: fetch → parse → diff (content_hash) → persist (append-only).
Descargas SECUENCIALES (requisito CHPP). Sync parcial si un file falla.
"""
import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.engines.youth_arrival import cuando_cumplio_diecisiete
from app.domain.value_objects.skill import Age
from app.domain.engines.sync_diff import (
    Change,
    MatchState,
    diff_economy,
    diff_match,
    diff_player_departure,
    diff_player_skills,
    diff_standing,
    diff_training,
)
from app.domain.ports.chpp_gateway import CHPPGateway
from app.domain.value_objects.ht_time import ht_to_utc, ht_to_utc_naive
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


def _parse_dt(value: str | None) -> datetime | None:
    """Fecha de CHPP ("2026-08-09 05:05:00") a datetime aware en UTC, o `None`
    si el fichero la trae vacía. CHPP no marca zona porque siempre es la hora
    del servidor sueco — ver `ht_time.ht_to_utc`."""
    return ht_to_utc(value)


def _as_change_row(change: Change) -> dict[str, Any]:
    """`Change` -> la fila que viaja en `SyncResult.changes` y termina en
    `sync_changes`. Se guardan las dos caras: la frase (`summary`, para el
    feed y el CSV) y el dato (`detail`, para que la UI formatee los números
    ella misma en vez de re-parsear el texto)."""
    return {
        "category": change.category,
        "summary": change.summary,
        "detail": change.detail(),
    }


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
    "matchorders": "alineación y órdenes enviadas",
    "youthplayerlist": "plantilla juvenil",
    "youthteamdetails": "academia juvenil",
}

#  HL-140: un sync normal debe poder mostrar el diff completo — posición en
# liga y resultados incluidos, no solo plantilla/economía. `teamdetails` va
# antes que `leaguedetails` porque este último necesita `series_ht_id`.
# `transfersteam` es una única llamada por equipo (no por jugador, a
# diferencia de `playerdetails` — ver `execute_player_details`), así que
# entra en el sync por defecto sin multiplicar las peticiones a CHPP.
DEFAULT_FILES = [
    "players", "training", "economy", "teamdetails", "leaguedetails", "leaguefixtures",
    "matches", "transfersteam", "currentbids", "worlddetails", "club", "stafflist",
    # youthteamdetails va ANTES que youthplayerlist: identifica qué academia es
    # la viva (id + fecha de creación) y con eso el módulo de Juveniles puede
    # acotar el ROI a la cantera actual en vez de sumar academias anteriores.
    "youthteamdetails", "youthplayerlist",
]
# worlddetails, 2026-08-04: única fuente de la temporada ACTUAL de Hattrick
# (leaguedetails.xml no la trae). Antes no estaba en el sync por defecto, así
# que `WorldContext.season` se quedaba congelada en lo que fuera que un
# script de desarrollo hubiera sincronizado a mano una vez — el desglose
# "por Temporada" del saldo por jugador (`season_at`, player_balance.py)
# depende de que esté fresca para calcular la temporada de CUALQUIER fecha
# por aritmética pura (112 días/temporada, igual que la edad), no solo de
# fechas con un Standing sincronizado cerca.
# club, stafflist, worlddetails y trainingevents cierran la fórmula de
# entrenamiento: aportan los valores que antes se ponían a mano. Corrección
# 2026-08-14: trainingevents estaba documentado aquí y tenía parser/handler,
# pero faltaba materialmente en DEFAULT_FILES; el sync normal nunca traía las
# referencias de los pops y "Entrenamiento actual" quedaba entero sin dato.
# CORRECCIÓN 2026-08-12, pedido explícito: club y stafflist NO estaban en
# esta lista pese al comentario de arriba — solo se sincronizaban una vez, a
# mano, al conectar la cuenta. El "Sincronizar" normal nunca los refrescaba,
# así que el staff del club (asistentes, entrenador, inversión juvenil) se
# quedaba congelado semanas, y encima con datos ya obsoletos (club.xml
# cambió de esquema entretanto — ver `parse_club`).
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
    # club 1.1, no 1.0: verificado en vivo 2026-08-12 — Hattrick YA NO honra
    # el pin a 1.0 y devuelve 1.1 igual (`<Specialists>` en vez de
    # `<Staff>`/niveles agregados por puesto). Fijar 1.1 explícito documenta
    # lo que de verdad se recibe en vez de mentir sobre qué versión se pidió.
    "club": "1.1", "stafflist": "1.0",
    # 2.0, no 1.8 (2026-08-09, confirmado por el usuario): a esta versión
    # `MatchRound` de cada `<League>` es la SEMANA real de temporada (1-16,
    # el mismo ciclo semanal de economía/entrenamiento) — no la jornada de
    # liga (ese es un concepto distinto, de leaguedetails.xml/Standing). Se
    # fija explícito para no depender de que un cambio de versión por
    # defecto de CHPP altere el significado del campo en silencio, igual que
    # ya se hace con matchlineup.xml.
    "worlddetails": "2.0",
    "trainingevents": "1.0",
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
    "playerdetails": "3.2", "transfersteam": "1.2",
    "arenadetails": "latest",
    # 1.2 verificado en vivo 2026-08-18: WeatherID (hoy) y TomorrowWeatherID.
    "regiondetails": "1.2",
    # El default del servidor todavía responde 1.3. `sourceSystem` y los roles
    # modernos (100-113) de partidos de torneo requieren 3.0 — verificado en
    # vivo con tournamentmatchid=41877309.
    "matchorders": "3.0",
    # 1.0 verificado en vivo 2026-08-14 (HL-161): a diferencia de
    # matches.xml (solo reciente/próximo), SÍ retrocede a temporadas ya
    # cerradas con FirstMatchDate/LastMatchDate — la pieza que faltaba para
    # contar partidos jugados con nosotros por un ex-jugador.
    "matchesarchive": "1.0",
}

# matchlineup.xml SIN versión explícita resuelve a un esquema viejo (1.2)
# donde `RoleID` es solo un índice secuencial sin significado — verificado
# en vivo 2026-08-09 (matchID 770453114, playerID 468921494: con 2.1
# RoleID=112="Delantero medio", el puesto real; sin versión, ese mismo
# jugador leía PositionCode=10="Interior izquierdo"). 2.1 además ya
# incorpora cada `<Substitution>` en el `<Lineup>` final, así que hasta un
# suplente que entró a mitad de partido queda con su posición real, y trae
# `Behaviour` (orden individual: Ofensivo/Defensivo/Hacia el medio/Hacia
# la banda — usado para "Última semana" en Posiciones). NO usar esta
# versión donde haga falta `PositionCode` (desaparece desde 1.5): el
# marcaje al hombre de rivals.py usa su propia
# `MATCHLINEUP_POSITION_CODE_VERSION = "1.2"`, a propósito distinta. Ver
# docstring de `parse_matchlineup` en
# app/infrastructure/chpp/parsers/__init__.py.
MATCHLINEUP_ROLE_VERSION = "2.1"

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


@dataclass(frozen=True)
class SyncPreviousClubBonusCommand:
    """HL-161, 2026-08-14: para UN jugador ya vendido, revisa
    transfersplayer.xml buscando una reventa nueva del club al que le
    vendimos — si la hay, calcula la comisión exacta de "club anterior"
    (partidos reales jugados con nosotros × tabla oficial) y la guarda.
    Dispara tanto el backfill masivo bajo demanda como, acotado, el
    monitoreo automático dentro de `execute()` (ver
    `_backfill_previous_club_bonus`)."""
    user_id: int
    team_id: int
    ht_player_id: int


@dataclass(frozen=True)
class SyncBackfillBatchCommand:
    """Un lote del relleno del pasado. `limite` es en JUGADORES: de cada uno se
    descarga todo lo que le falte antes de pasar al siguiente."""

    user_id: int
    team_id: int
    limite: int
    # Momento en que el usuario pulso. La vigilancia de reventas no se agota
    # nunca -un ex-jugador sin vender sigue pudiendo darnos dinero manana-, asi
    # que "una pulsacion" se define como UNA pasada: quien ya se reviso despues
    # de esta marca no vuelve a la cola hasta la siguiente.
    revisar_desde: datetime | None = None


@dataclass
class SyncResult:
    sync_id: int
    status: str
    snapshots_written: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    # HL-140: qué cambió respecto al sync anterior — {"category", "summary"}
    changes: list[dict[str, str]] = field(default_factory=list)
    # HL-2xx, 2026-08-12: filas `Player` recién marcadas `left_team_at` en
    # este sync (ver `mark_departed`) — se anuncian en `changes` DESPUÉS de
    # que todos los ficheros terminen, no aquí mismo, porque `transfersteam`
    # (si es parte de este sync) puede rellenar `sale_price` de un jugador
    # que ya salió del roster ANTES de que ese fichero se procese.
    departed_players: list[Any] = field(default_factory=list)
    # HL-161, 2026-08-04: solo los usa `execute_transfers_history` — cuántas
    # páginas de transfersteam.xml se pidieron y cuántas transferencias se
    # vieron en total vs. cuántas eran nuevas de verdad.
    pages_fetched: int = 0
    transfers_seen: int = 0
    transfers_new: int = 0
    # Relleno del pasado por lotes: jugadores atendidos en ESTE lote y los que
    # siguen esperando. Es lo que la pantalla convierte en "van 87 de 515".
    players_done: int = 0
    players_pending: int = 0
    # Nombres de los atendidos en este lote, para que la pantalla pueda decir
    # por quien va en vez de dejar la barra quieta.
    players_named: list[str] = field(default_factory=list)


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
                    elif file == "youthplayerlist":
                        # Sin `actionType=details` el fichero trae sólo las
                        # identidades: ni niveles ni techos, y el motor de
                        # academia se queda sin nada que evaluar. No lleva
                        # teamID — CHPP resuelve el equipo juvenil del usuario.
                        params = {"actionType": "details", "showLastMatch": "true"}
                    elif file == "youthteamdetails":
                        # Igual que el anterior: sin teamID, CHPP devuelve la
                        # academia del usuario autenticado (verificado en vivo).
                        params = {}
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

            # `players.xml` trae CountryID y `worlddetails.xml` trae la
            # identidad oficial de ese país. Como worlddetails se descarga
            # después de players en el flujo normal, el cruce se hace aquí,
            # cuando ambos ya están persistidos. También permite completar
            # snapshots existentes al actualizar desde una versión anterior
            # de HT Lens, sin volver a pedir una ficha por jugador.
            if "players" in files or "worlddetails" in files:
                await self._backfill_native_countries_from_snapshots(
                    uow, cmd.team_id, result
                )

            from app.infrastructure.db import models as m

            if result.departed_players:
                # HL-2xx, 2026-08-12: se anuncia aquí, no dentro de
                # `_persist_squad` — `transfersteam` puede ir DESPUÉS de
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
                    change = diff_player_departure(name, _conv(p.sale_price), currency)
                    result.changes.append(_as_change_row(change))

            for c in result.changes:
                detail = c.get("detail")
                uow.session.add(m.SyncChange(
                    sync_id=sync_id, team_id=cmd.team_id, category=c["category"],
                    summary=c["summary"],
                    detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
                    created_at=captured_at,
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
                await self._sync_training_events(
                    uow, cmd.team_id, captured_at, result, on_progress
                )
            if "matches" in files:
                await self._sync_upcoming_match_orders(
                    uow, cmd.ht_team_id, captured_at, result, on_progress
                )
                await self._backfill_missing_match_details(
                    uow, cmd.team_id, cmd.ht_team_id, result, on_progress
                )
                await self._sync_next_match_weather(
                    uow, cmd.ht_team_id, captured_at, result, on_progress
                )
                await self._sync_rival_purchases(
                    uow, cmd.team_id, cmd.ht_team_id, captured_at, result, on_progress
                )

            await self._marcar_salidas_de_vendidos(uow, cmd.team_id)
            await self._resolver_moneda(uow, cmd.team_id)

            await uow.syncs.finalize(
                sync_id, status=result.status,
                error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def execute_backfill_batch(
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
            if cmd.revisar_desde is not None:
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
                sync_id = await uow.syncs.create(
                    cmd.user_id, cmd.team_id, kind="backfill_batch"
                )
            result = SyncResult(sync_id=sync_id, status="completed")
            fetched_at = datetime.now(UTC).replace(tzinfo=None)

            # El orden lo pone la aplicación, no el usuario: primero el libro
            # de compraventas —que es lo que CREA las fichas de los que la app
            # nunca vio— y solo después el trabajo por jugador. Al revés no
            # habría a quién completar. Se hace en la primera pulsación y
            # nunca más, porque la bandera lo recuerda.
            equipo = await uow.session.get(m.Team, cmd.team_id)
            if equipo is not None and not equipo.transfers_history_complete:
                await _report(on_progress, "Recorriendo el historial de transferencias...")
                await self._recorrer_historial(uow, cmd.user_id, cmd.team_id, equipo, result)

            result.players_done = await self._backfill_sold_player_details(
                uow, cmd.team_id, fetched_at, result, on_progress,
                limite=cmd.limite, revisar_desde=cmd.revisar_desde,
            )
            quedan = await self.pendientes_de_ficha(
                uow, cmd.team_id, cmd.revisar_desde
            )
            # La union de TODAS las colas, sin nombrarlas una a una: nombrarlas
            # ya costo un fallo -al anadir el censo y la vigilancia, esta
            # cuenta se quedo mirando solo las tres viejas y devolvia 0, con lo
            # que la pantalla paraba tras el primer lote creyendo haber
            # terminado.
            pendientes_unicos: set[int] = set()
            for cola in quedan.values():
                pendientes_unicos |= set(cola)
            result.players_pending = len(pendientes_unicos)

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    async def pendientes_de_ficha(
        self, uow: UnitOfWork, team_id: int, revisar_desde: datetime | None = None,
    ) -> dict[str, list[int]]:
        """Qué le falta por descargar a cada jugador, agrupado por tipo.

        Son tres huecos distintos, todos de una llamada por jugador y todos
        de una sola vez en la vida: el precio de compra antiguo, la ficha
        (nacionalidad, carácter, especialidad, edad reconstruida) y el país
        al que se fue. Se consultan juntos porque, para quien mira la
        pantalla, es una sola cosa: "que la ficha esté completa".
        """
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
        # 2026-08-05: mismo principio, ancla en `purchased_at` — "Edad de
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

        async def ids(condicion) -> list[int]:
            filas = await uow.session.execute(
                select(m.Player.ht_player_id).where(m.Player.team_id == team_id, condicion)
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
                        | (
                            m.Player.age_years_at_sale.is_(None)
                            & ~hay_snapshot_antes_de_la_venta
                        )
                    )
                )
                | (
                    m.Player.purchased_at.is_not(None)
                    & m.Player.age_years_at_purchase.is_(None)
                    & ~hay_snapshot_tras_la_compra
                )
            )
        )
        # 2026-08-05: "una vez por jugador, para siempre" —
        # `tsi_at_purchase_attempted` es el mismo flag en los dos casos.
        precio = await ids(
            (~m.Player.tsi_at_purchase_attempted)
            & (
                (
                    m.Player.purchase_price.is_(None)
                    & m.Player.purchase_price_manual.is_(None)
                )
                | (m.Player.sold_at.is_not(None) & m.Player.tsi_at_purchase.is_(None))
            )
        )
        destino = await ids(
            m.Player.buyer_team_id.is_not(None)
            & m.Player.destination_country.is_(None)
            & (~m.Player.destination_attempted)
        )
        # El censo de partidos: una vez por ex-jugador, para siempre.
        censo = await ids(
            (m.Player.sold_at.is_not(None) | m.Player.left_team_at.is_not(None))
            & m.Player.games_played_for_us_computed_at.is_(None)
        )
        # La vigilancia de reventas: se repite hasta que el jugador queda
        # cerrado, y entonces desaparece de la cola para siempre.
        vigilancia = (
            (m.Player.sold_at.is_not(None) | m.Player.left_team_at.is_not(None))
            & (~m.Player.resale_closed)
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
            "ficha": ficha, "precio": precio, "destino": destino,
            "censo": censo, "reventa": reventa,
        }

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
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        pendientes = await self.pendientes_de_ficha(uow, team_id, revisar_desde)
        ficha = set(pendientes["ficha"])
        precio = set(pendientes["precio"])
        destino = set(pendientes["destino"])
        censo = set(pendientes["censo"])
        reventa = set(pendientes["reventa"])

        # Orden estable: el mismo lote se repetiría igual si algo fallara.
        todos = sorted(ficha | precio | destino | censo | reventa)
        if limite is not None:
            todos = todos[:limite]

        for ht_player_id in todos:
            nombre = await uow.session.scalar(
                select(m.Player.last_name).where(m.Player.ht_player_id == ht_player_id)
            )
            if nombre:
                result.players_named.append(nombre)
            if ht_player_id in ficha:
                await _report(
                    on_progress, f"Descargando ficha de ex-jugador {ht_player_id}..."
                )
                try:
                    wrote = await self._apply_player_enrichment(
                        uow, ht_player_id, fetched_at
                    )
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                    result.errors.append(f"player_enrichment:{ht_player_id}: {exc}")
                    result.status = "partial"
            if ht_player_id in precio:
                await _report(
                    on_progress,
                    f"Descargando transferencias de jugador {ht_player_id}...",
                )
                try:
                    wrote = await self._apply_transfers_player_purchase(
                        uow, team_id, ht_player_id
                    )
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                    result.errors.append(f"tsi_at_purchase:{ht_player_id}: {exc}")
                    result.status = "partial"
            if ht_player_id in destino:
                await _report(
                    on_progress, f"Descargando país destino de jugador {ht_player_id}..."
                )
                try:
                    wrote = await self._apply_destination_country(uow, ht_player_id)
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                    result.errors.append(f"destination_country:{ht_player_id}: {exc}")
                    result.status = "partial"
            if ht_player_id in censo:
                await _report(
                    on_progress,
                    f"Contando partidos con nosotros de {ht_player_id}...",
                )
                try:
                    wrote = await self._censar_partidos_del_stint(
                        uow, team_id, ht_player_id
                    )
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                    result.errors.append(f"censo_partidos:{ht_player_id}: {exc}")
                    result.status = "partial"
            if ht_player_id in reventa:
                await _report(
                    on_progress, f"Revisando reventas de {ht_player_id}..."
                )
                try:
                    wrote = await self._vigilar_reventa(uow, team_id, ht_player_id)
                    result.snapshots_written += 1 if wrote else 0
                except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                    result.errors.append(f"reventa:{ht_player_id}: {exc}")
                    result.status = "partial"

        return len(todos)

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
                    (
                        m.Player.native_country.is_(None)
                        | (m.Player.native_country == "")
                    ),
                    m.PlayerSnapshot.country_id > 0,
                )
            )
        ).all()
        for player, country_id in rows:
            country_name = countries.get(country_id)
            if country_name:
                player.native_country = country_name
                result.snapshots_written += 1

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
            MATCH_TYPE_CUP,
            MATCH_TYPE_LEAGUE,
            MATCH_TYPE_MASTERS,
            MATCH_TYPE_QUALIFICATION,
            match_type_name,
        )
        from app.domain.value_objects.ht_time import ht_to_utc
        from sqlalchemy import select

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
        desde = (anterior.started_at if anterior else None) or (
            captured_at - timedelta(days=7)
        )
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
                result.errors.append(f"transfersteam:{rival_id}: {exc}")
                continue
            nombre_club = payload.get("team_name") or str(rival_id)
            for compra in payload.get("transfers", []):
                if compra.get("buyer_team_id") != rival_id:
                    continue
                cuando = ht_to_utc(compra.get("deadline", ""))
                if cuando is None or cuando <= desde:
                    continue
                nota = await self._best_recent_rating(
                    rival_id, compra.get("ht_player_id") or 0
                )
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
                        version=MATCHLINEUP_POSITION_CODE_VERSION,
                        matchID=mt["ht_match_id"],
                        matchType=mt["match_type"],
                        teamID=ht_team_id,
                    )
                )["players"]
            except Exception:  # noqa: BLE001
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
        tiene sentido para el partido inmediato: se piden dos ficheros —el
        estadio donde se juega, para saber su región, y la región, para saber
        su tiempo— y nada más. En un partido de visitante la región es la del
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
            select(m.Match).where(
                or_(
                    m.Match.home_team_ht_id == ht_team_id,
                    m.Match.away_team_ht_id == ht_team_id,
                ),
                m.Match.status.ilike("upcoming"),
                m.Match.match_type.not_in(NON_OFFICIAL_MATCH_TYPES),
            ).order_by(m.Match.played_at).limit(1)
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
                        t for t in detalles.get("teams", [])
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
        except Exception as exc:  # noqa: BLE001 — el clima nunca tumba un sync
            result.errors.append(f"regiondetails: {exc}")

    async def _sync_upcoming_match_orders(
        self,
        uow: UnitOfWork,
        ht_team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Guarda las órdenes realmente enviadas de próximos partidos propios.

        `matches.xml.OrdersGiven` es el gate oficial: solo cuando vale True
        pedimos `matchorders.xml` 3.0. Así nunca confundimos la alineación por
        defecto del formulario con una decisión ya enviada por el manager.
        Mientras el partido siga próximo se vuelve a consultar en cada sync,
        porque Hattrick permite modificar las órdenes antes del cierre.
        """
        from sqlalchemy import or_, select

        from app.infrastructure.db import models as m

        pending = (
            await uow.session.execute(
                select(m.Match).where(
                    or_(
                        m.Match.home_team_ht_id == ht_team_id,
                        m.Match.away_team_ht_id == ht_team_id,
                    ),
                    m.Match.orders_given.is_(True),
                    m.Match.status.ilike("upcoming"),
                ).order_by(m.Match.played_at)
            )
        ).scalars().all()

        for match in pending:
            await _report(
                on_progress,
                f"Descargando alineación enviada del partido {match.ht_match_id}...",
            )
            source_system = (match.source_system or "hattrick").strip().lower()
            if source_system not in {"hattrick", "youth", "htointegrated"}:
                source_system = "hattrick"
            try:
                payload = await self._chpp.fetch(
                    "matchorders",
                    version=FILE_VERSIONS["matchorders"],
                    matchID=match.ht_match_id,
                    sourceSystem=source_system,
                )
                if payload.get("ht_match_id") != match.ht_match_id:
                    continue
                positions = payload.get("positions", []) if payload.get("available") else []
                # Un partido puede empezar con 9-11 jugadores. Menos de 9 no
                # es una alineación válida y no debe desplazar el fallback.
                if len(positions) < 9:
                    continue
                lineup_json = json.dumps(
                    positions, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                before = (
                    match.submitted_lineup_json,
                    match.submitted_tactic_type,
                    match.submitted_attitude,
                    match.submitted_coach_modifier,
                )
                after = (
                    lineup_json,
                    payload.get("tactic_type"),
                    payload.get("attitude"),
                    payload.get("coach_modifier"),
                )
                changed = before != after
                if changed:
                    match.submitted_lineup_json = lineup_json
                    match.submitted_tactic_type = payload.get("tactic_type")
                    match.submitted_attitude = payload.get("attitude")
                    match.submitted_coach_modifier = payload.get("coach_modifier")
                    match.submitted_orders_captured_at = captured_at

                # Esta acción es una consulta GET de solo lectura. Hattrick
                # calcula los ratings de minuto 0 para las órdenes que ya
                # están guardadas; no envía ni modifica la alineación.
                try:
                    await _report(
                        on_progress,
                        f"Calculando ratings CHPP del partido {match.ht_match_id}...",
                    )
                    predicted_payload = await self._chpp.fetch(
                        "matchorders",
                        version=FILE_VERSIONS["matchorders"],
                        matchID=match.ht_match_id,
                        sourceSystem=source_system,
                        actionType="predictratings",
                    )
                    prediction = predicted_payload.get("prediction")
                    if (
                        predicted_payload.get("ht_match_id") == match.ht_match_id
                        and isinstance(prediction, dict)
                    ):
                        ratings = prediction.get("ratings") or {}
                        predicted_before = (
                            match.submitted_tactic_skill,
                            match.submitted_rating_midfield,
                            match.submitted_rating_right_def,
                            match.submitted_rating_central_def,
                            match.submitted_rating_left_def,
                            match.submitted_rating_right_att,
                            match.submitted_rating_central_att,
                            match.submitted_rating_left_att,
                        )
                        predicted_after = (
                            prediction.get("tactic_skill"),
                            ratings.get("midfield"),
                            ratings.get("right_def"),
                            ratings.get("central_def"),
                            ratings.get("left_def"),
                            ratings.get("right_att"),
                            ratings.get("central_att"),
                            ratings.get("left_att"),
                        )
                        if predicted_before != predicted_after:
                            match.submitted_tactic_type = prediction.get("tactic_type")
                            match.submitted_tactic_skill = prediction.get("tactic_skill")
                            match.submitted_rating_midfield = ratings.get("midfield")
                            match.submitted_rating_right_def = ratings.get("right_def")
                            match.submitted_rating_central_def = ratings.get("central_def")
                            match.submitted_rating_left_def = ratings.get("left_def")
                            match.submitted_rating_right_att = ratings.get("right_att")
                            match.submitted_rating_central_att = ratings.get("central_att")
                            match.submitted_rating_left_att = ratings.get("left_att")
                            changed = True
                        # Fuera del `if`: la fecha no dice "cambiaron los
                        # ratings", dice "esta predicción corresponde a la
                        # alineación de ahora". Dentro del `if`, una predicción
                        # idéntica dejaba la fecha vieja y la vista la marcaba
                        # como desfasada sin serlo.
                        match.submitted_ratings_captured_at = captured_at
                    elif predicted_payload.get("chpp_error"):
                        # Hattrick devolvió `chpperror.xml`. Los ratings que ya
                        # están guardados pertenecen a otra alineación: no se
                        # tocan, pero el fallo se registra para que la vista
                        # pueda decir "no hay predicción" en vez de enseñar los
                        # viejos como si fueran los de este once.
                        result.errors.append(
                            f"matchorders:predictratings:{match.ht_match_id}: "
                            f"{predicted_payload['chpp_error']}"
                        )
                        result.status = "partial"
                except Exception as exc:  # noqa: BLE001 — las órdenes siguen siendo útiles
                    result.errors.append(f"matchorders:predictratings:{match.ht_match_id}: {exc}")
                    result.status = "partial"

                if changed:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
                result.errors.append(f"matchorders:{match.ht_match_id}: {exc}")
                result.status = "partial"

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

        async def _contexto(condicion) -> m.WorldContext | None:
            return await uow.session.scalar(select(m.WorldContext).where(condicion))

        candidatos: list[m.WorldContext | None] = []
        if equipo.ht_league_id is not None:
            candidatos.append(
                await _contexto(m.WorldContext.ht_league_id == equipo.ht_league_id)
            )
        if equipo.league_name:
            candidatos.append(
                await _contexto(m.WorldContext.league_name == equipo.league_name)
            )
        for fila in candidatos:
            if fila is not None and fila.currency_name:
                equipo.currency_name = fila.currency_name
                equipo.currency_rate = fila.currency_rate or 1.0
                return

        # Ligas internacionales (Hattrick Femme y compañia): no tienen moneda
        # propia, asi que se toma la de otro equipo del mismo manager, que es
        # la de su pais y la que Hattrick le ensena.
        if equipo.owner_user_id is not None:
            hermano = await uow.session.scalar(
                select(m.Team)
                .where(
                    m.Team.owner_user_id == equipo.owner_user_id,
                    m.Team.id != equipo.id,
                    m.Team.currency_name != "",
                )
                .limit(1)
            )
            if hermano is not None:
                equipo.currency_name = hermano.currency_name
                equipo.currency_rate = hermano.currency_rate or 1.0

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
                chances = team.get("chances", {})
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
                    chances_left=chances.get("left", 0),
                    chances_center=chances.get("center", 0),
                    chances_right=chances.get("right", 0),
                    chances_special=chances.get("special", 0),
                    chances_other=chances.get("other", 0),
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
            ht_to_utc(date_str) or datetime.now(UTC)
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
            snap.last_match_played_at = (
                ht_to_utc(played_at_str)
            )
            snap.last_match_behaviour_code = await self._fetch_last_match_behaviour(
                uow, ht_player_id, last_match.get("ht_match_id"), player.team_id,
            )
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

    async def _fetch_last_match_behaviour(
        self, uow: UnitOfWork, ht_player_id: int, ht_match_id: int | None, team_id: int,
    ) -> int | None:
        """2026-08-09, pedido explícitamente: `LastMatch` de playerdetails.xml
        da el `MatchId`/`PositionCode` pero nunca la orden individual real
        (Ofensivo/Defensivo/Hacia el medio/Hacia la banda) — eso solo lo
        trae `Behaviour` de matchlineup.xml PARA ESE PARTIDO CONCRETO, una
        llamada CHPP aparte. Best effort: si falla (partido de
        selección/torneo fuera de alcance, CHPP caído, jugador no aparece
        en la alineación por lo que sea) se queda en None — nunca bloquea
        el resto de playerdetails, que sigue siendo útil sin esto."""
        if not ht_match_id:
            return None
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        team = await uow.session.get(m.Team, team_id)
        if team is None:
            return None
        try:
            payload = await self._chpp.fetch(
                "matchlineup", version=MATCHLINEUP_ROLE_VERSION,
                matchID=ht_match_id, teamID=team.ht_team_id,
            )
        except Exception:  # noqa: BLE001 — best effort, ver docstring
            return None
        for p in payload.get("players", []):
            if p.get("ht_player_id") == ht_player_id:
                return p.get("behaviour")
        return None

    async def _sync_training_events(
        self,
        uow: UnitOfWork,
        team_id: int,
        captured_at: datetime,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Subidas confirmadas por Hattrick, jugador por jugador.

        CORRECCIÓN 2026-08-19: `trainingevents.xml` estaba en la lista de
        ficheros del sync general, y ahí se pedía SIN `playerID`. Hattrick
        responde a eso con error 56, así que la tabla `skill_ups` llevaba
        vacía desde siempre pese a tener parser, handler y modelo. El fichero
        solo existe por jugador, verificado en vivo: con `playerID` devuelve
        sus eventos con `Season` y `MatchRound`, que es justo el "83-03" que
        pide la columna "Última mejora".

        Es una llamada por jugador de la plantilla activa, igual que
        `playerdetails`. El guardado ya era idempotente: un mismo pop no se
        cuenta dos veces.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        jugadores = (
            await uow.session.execute(
                select(m.Player.ht_player_id)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
            )
        ).scalars().all()
        if not jugadores:
            return
        await _report(on_progress, "Leyendo subidas confirmadas por Hattrick...")
        for ht_player_id in jugadores:
            try:
                payload = await self._chpp.fetch(
                    "trainingevents",
                    version=FILE_VERSIONS["trainingevents"],
                    playerID=ht_player_id,
                )
            except Exception as exc:  # noqa: BLE001 - un jugador no tumba el sync
                result.errors.append(f"trainingevents:{ht_player_id}: {exc}")
                continue
            await self._persist_skill_ups(uow, team_id, payload, captured_at, result)

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
                player.purchased_at = ht_to_utc(date_str)
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

    async def _games_played_for_us(
        self, ht_team_id: int, ht_player_id: int, purchased_at: datetime, sold_at: datetime,
    ) -> int:
        """Recorre matchesarchive.xml (ventana purchased_at→sold_at) +
        matchlineup.xml v2.1 partido por partido — la única forma de contar
        partidos REALES (RatingStars > 0) de un stint ya cerrado que el
        histórico propio de esta app no alcanzó a sincronizar. Un partido
        cuya alineación no se puede leer (best effort, no debería pasar en
        un partido ya finalizado) simplemente no cuenta — no se aborta todo
        el conteo por un fallo puntual, igual que `_backfill_stadium_history`."""
        from app.domain.engines.previous_club_bonus import counts_toward_games_played, did_play

        archive = await self._chpp.fetch(
            "matchesarchive", version=FILE_VERSIONS["matchesarchive"],
            teamID=ht_team_id,
            FirstMatchDate=purchased_at.strftime("%Y-%m-%d %H:%M:%S"),
            LastMatchDate=sold_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        qualifying = [
            mt for mt in archive.get("matches", [])
            if counts_toward_games_played(mt.get("match_type", -1))
        ]
        games = 0
        for mt in qualifying:
            try:
                lineup = await self._chpp.fetch(
                    "matchlineup", version=MATCHLINEUP_ROLE_VERSION,
                    matchID=mt["ht_match_id"], teamID=ht_team_id,
                )
            except Exception:  # noqa: BLE001 — best effort, ver docstring
                continue
            hit = next(
                (p for p in lineup.get("players", []) if p.get("ht_player_id") == ht_player_id),
                None,
            )
            if hit is not None and did_play(hit.get("rating_stars") or 0.0):
                games += 1
        return games

    async def _check_previous_club_bonus(
        self, uow: UnitOfWork, team_id: int, ht_player_id: int,
    ) -> bool:
        """Núcleo de `execute_previous_club_bonus` — recibe el `uow` ya
        abierto, igual que `_apply_transfers_player_purchase`/
        `_apply_player_enrichment`, para poder llamarse también desde
        `_backfill_previous_club_bonus` (monitoreo automático dentro de
        `execute()`).

        "Club anterior" de una reventa = quien nos compró el jugador A
        NOSOTROS justo antes de esa reventa — nunca una venta más abajo en
        la cadena (esa le toca al club que sí fue "anterior" en ESA venta).
        transfersplayer.xml viene ordenado del más reciente al más antiguo,
        así que esa reventa, si existe, es la que aparece INMEDIATAMENTE
        ANTES de nuestra propia venta en la lista."""
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
            "transfersplayer", version=FILE_VERSIONS["transfersplayer"], playerID=ht_player_id,
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
            (t for t in transfers if t.get("buyer_team_id") == team.ht_team_id), None,
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
            # la lista no encaja con quien nos compró — no se inventa una
            # comisión sobre una cadena que no se puede confirmar.
            return False

        resale_transfer_id = resale.get("ht_transfer_id")
        already = await uow.session.scalar(
            select(m.PreviousClubBonus.id)
            .where(m.PreviousClubBonus.resale_transfer_id == resale_transfer_id)
        )
        if already is not None:
            return False

        games = player.games_played_for_us
        if games is None:
            if player.purchased_at is None:
                return False
            games = await self._games_played_for_us(
                team.ht_team_id, ht_player_id, player.purchased_at, player.sold_at,
            )
            player.games_played_for_us = games
            player.games_played_for_us_computed_at = now

        pct = previous_club_bonus_pct(games)
        price = resale.get("price", 0)
        deadline_str = resale.get("deadline", "")
        resale_deadline = (
            ht_to_utc(deadline_str) or now
        )

        uow.session.add(m.PreviousClubBonus(
            player_id=player.id, ht_player_id=ht_player_id,
            resale_transfer_id=resale_transfer_id, resale_price=price,
            resale_deadline=resale_deadline,
            buyer_team_id=resale.get("buyer_team_id", 0),
            seller_team_id=resale.get("seller_team_id", 0),
            games_played_with_us=games, pct_applied=pct, amount=round(price * pct),
            computed_at=now,
        ))
        return True

    async def execute_previous_club_bonus(
        self, cmd: SyncPreviousClubBonusCommand
    ) -> SyncResult:
        """HL-161: bajo demanda, un jugador — reutilizado tanto por el
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
            except Exception as exc:  # noqa: BLE001 — mismo patrón que execute_transfers_player
                result.errors.append(f"previous_club_bonus: {exc}")
                result.status = "partial"

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result

    @staticmethod
    def _edad_en_la_salida(jugador: Any) -> "Age | None":
        """Su edad el día que se fue, si se conoce."""
        if jugador.age_years_at_sale is None or jugador.age_days_at_sale is None:
            return None
        try:
            return Age(jugador.age_years_at_sale, jugador.age_days_at_sale)
        except ValueError:
            return None

    async def _censar_partidos_del_stint(
        self, uow: UnitOfWork, team_id: int, ht_player_id: int,
    ) -> bool:
        """Cuántos partidos jugó de verdad con nosotros. UNA vez por jugador.

        Es el trabajo más caro de toda la aplicación: el archivo de partidos
        de su etapa, y la alineación de cada uno para ver si llegó a jugar.
        Por eso se guarda en su ficha y no se repite jamás — un partido ya
        jugado no cambia.

        "Jugó al menos un minuto" se decide por las estrellas: `matchlineup`
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

        salida = jugador.sold_at or jugador.left_team_at
        inicio = jugador.purchased_at
        if inicio is None and salida is not None:
            # Un canterano no se compró, así que no tiene fecha de compra, y
            # sin principio de etapa este recorrido se saltaba a la mitad de
            # ellos. Como nadie llega al primer equipo antes de los 17 años,
            # el día en que los cumplió es el suelo: buscar desde ahí cubre de
            # más, nunca de menos. No se guarda como su llegada ni se enseña.
            edad = self._edad_en_la_salida(jugador)
            if edad is not None:
                inicio = cuando_cumplio_diecisiete(edad, salida)

        if inicio is None or salida is None:
            # Sin etapa acotada no hay nada que recorrer; se marca censado
            # para no volver a intentarlo en cada lote.
            jugador.games_played_for_us_computed_at = datetime.now(UTC).replace(
                tzinfo=None
            )
            return False

        # La marca se pone pase lo que pase. El recorrido es "una vez por
        # jugador, para siempre", asi que si Hattrick falla a mitad no se
        # vuelve a intentar en el siguiente lote: se quedaria en la cola para
        # siempre y el trabajo no se agotaria nunca. Sin cuenta, la ficha
        # ensena "?" en vez de un cero que parecería contado.
        try:
            jugador.games_played_for_us = await self._games_played_for_us(
                equipo.ht_team_id, ht_player_id, inicio, salida,
            )
            contado = True
        finally:
            jugador.games_played_for_us_computed_at = datetime.now(UTC).replace(
                tzinfo=None
            )
        return contado

    async def _vigilar_reventa(
        self, uow: UnitOfWork, team_id: int, ht_player_id: int,
    ) -> bool:
        """¿Sigue pudiendo darnos dinero este ex-jugador?

        Una llamada mira su historial de transferencias, que es la que
        contesta la pregunta del dinero. Solo si NO hay reventa hace falta la
        segunda, la de su ficha, para saber si sigue existiendo: un despido o
        un retiro lo cierran para siempre, y comprobado en vivo, Hattrick
        responde a esa ficha con el error 56 cuando el jugador ya no está.
        """
        from sqlalchemy import select

        from sqlalchemy import select

        from app.domain.engines import ex_player_watch as vigilancia
        from app.infrastructure.db import models as m

        equipo = await uow.session.get(m.Team, team_id)
        jugador = await uow.session.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if equipo is None or jugador is None:
            return False

        canterano = vigilancia.es_canterano(
            jugador.mother_club_team_id, equipo.ht_team_id
        )
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
        # Solo se pregunta por su ficha cuando la reventa no ha zanjado nada:
        # es la única forma de dejar de vigilar a quien ya no existe, y una
        # llamada de más solo para los que siguen ahí fuera sin venderse.
        if not salio_sin_comprador and not (revendido and not canterano):
            try:
                ficha = await self._chpp.fetch(
                    "playerdetails", version=FILE_VERSIONS["playerdetails"],
                    playerID=ht_player_id,
                )
            except Exception:  # noqa: BLE001 — best effort, se reintenta en otro lote
                ficha = {}
            desaparecido = vigilancia.desaparecio_de_hattrick(
                ficha.get("chpp_error_code")
            )

        motivo = vigilancia.motivo_de_cierre(
            canterano=canterano,
            revendido=revendido,
            desaparecido=desaparecido,
            salio_sin_comprador=salio_sin_comprador,
        )
        jugador.previous_club_bonus_checked_at = datetime.now(UTC).replace(tzinfo=None)
        if motivo is not None:
            jugador.resale_closed = True
            jugador.resale_closed_reason = motivo
        return revendido

    async def _backfill_previous_club_bonus(
        self,
        uow: UnitOfWork,
        team_id: int,
        result: SyncResult,
        on_progress: ProgressReporter | None = None,
    ) -> None:
        """Monitoreo automático, sin botón (HL-161, 2026-08-14, pedido
        explícitamente): en cada sync que incluya transfersteam, revisa
        hasta 25 ex-jugadores — los nunca revisados primero, luego los más
        desactualizados (orden por `previous_club_bonus_checked_at`
        ascendente, NULL primero) — por si alguno fue revendido por el
        club al que le vendimos. Acotado a propósito: a diferencia del
        backfill masivo (sin límite, bajo demanda), esto corre solo en
        cada sync, así que no puede convertir un sync normal en cientos de
        llamadas a CHPP. El conteo de partidos (caro: matchesarchive +
        matchlineup por partido) solo se dispara cuando de verdad hay una
        reventa nueva que pagar — la inmensa mayoría de estos 25 no la
        tendrán."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        candidates = (
            await uow.session.execute(
                select(m.Player.ht_player_id)
                .where(m.Player.team_id == team_id, m.Player.sold_at.is_not(None))
                .order_by(
                    m.Player.previous_club_bonus_checked_at.is_not(None),
                    m.Player.previous_club_bonus_checked_at,
                )
                .limit(25)
            )
        ).scalars().all()
        for ht_player_id in candidates:
            await _report(
                on_progress, f"Revisando comisión de club anterior de {ht_player_id}...",
            )
            try:
                wrote = await self._check_previous_club_bonus(uow, team_id, ht_player_id)
                if wrote:
                    result.snapshots_written += 1
                else:
                    result.unchanged += 1
            except Exception as exc:  # noqa: BLE001 — best effort, ver _backfill_sold_player_details
                result.errors.append(f"previous_club_bonus:{ht_player_id}: {exc}")

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

        # El salario, incluso de alguien que ya juega en otro club: Hattrick lo
        # sigue devolviendo. Para un jugador que entro y salio entre dos
        # sincronizaciones esta es la UNICA fuente, porque no dejo snapshots.
        salario = payload.get("salary") or 0
        if salario and player.last_known_salary != salario:
            player.last_known_salary = salario
            wrote_anything = True

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
        if not native_league_name:
            native_league_id = payload.get("native_league_id")
            native_country_id = payload.get("native_country_id")
            world = None
            if native_league_id:
                world = await uow.session.scalar(
                    select(m.WorldContext).where(
                        m.WorldContext.ht_league_id == native_league_id
                    )
                )
            if world is None and native_country_id:
                world = await uow.session.scalar(
                    select(m.WorldContext).where(
                        m.WorldContext.country_id == native_country_id
                    )
                )
            native_league_name = world.country_name if world is not None else None
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
        if file == "youthplayerlist":
            await self._persist_youth(uow, sync_id, team_id, payload, captured_at, result)
            return
        if file == "youthteamdetails":
            from app.infrastructure.db import models as m

            team = await uow.session.get(m.Team, team_id)
            if team is not None and payload.get("ht_youth_team_id"):
                team.ht_youth_team_id = payload["ht_youth_team_id"]
                team.youth_team_name = payload.get("youth_team_name") or None
                team.youth_academy_created_at = _parse_dt(payload.get("created_date"))
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
            result.changes.extend(_as_change_row(c) for c in changes)

        if roster:
            # Quien no vino en este players.xml ya no está en el club — se
            # marca left_team_at (nunca se borra). Un roster vacío no dispara
            # esto: sería marcar a toda la plantilla como salida por un fetch
            # vacío/roto, exactamente el tipo de bug que esta guarda evita.
            current_ids = {p["ht_player_id"] for p in roster}
            departed = await uow.players.mark_departed(team_id, current_ids, captured_at)
            result.departed_players.extend(departed)

    async def _staff_row(
        self, uow: UnitOfWork, sync_id: int, team_id: int, captured_at: datetime
    ) -> Any:
        """La misma fila de staff para este sync: club y stafflist son ficheros
        distintos que rellenan campos distintos de un único snapshot.

        HL-2xx, 2026-08-12: una fila NUEVA arranca copiando la ÚLTIMA fila
        conocida del equipo, no en blanco — mismo patrón que ya usa
        `append_snapshot` para career_assists/last_match en jugadores. Sin
        esto, un sync que sólo trajera `club` (o un `stafflist` con
        `<Trainer>` ausente, riesgo real verificado en vivo) resetearía a 0
        el staff/entrenador ya conocido, porque cada sync crea su propia
        fila."""
        from sqlalchemy import select

        from app.domain.value_objects.ht_constants import STAFF_TYPE_TO_FIELD
        from app.infrastructure.db import models as m

        row = await uow.session.scalar(
            select(m.StaffSnapshot).where(
                m.StaffSnapshot.sync_id == sync_id, m.StaffSnapshot.team_id == team_id
            )
        )
        if row is None:
            last = await uow.session.scalar(
                select(m.StaffSnapshot)
                .where(m.StaffSnapshot.team_id == team_id)
                .order_by(m.StaffSnapshot.captured_at.desc())
                .limit(1)
            )
            row = m.StaffSnapshot(
                sync_id=sync_id, team_id=team_id, captured_at=captured_at,
                content_hash=b"\x00" * 32,
            )
            if last is not None:
                for field in STAFF_TYPE_TO_FIELD.values():
                    setattr(row, field, getattr(last, field))
                row.trainer_skill_level = last.trainer_skill_level
                row.trainer_type = last.trainer_type
                row.trainer_leadership = last.trainer_leadership
                row.youth_investment = last.youth_investment
                row.youth_level = last.youth_level
                row.staff_members_json = last.staff_members_json
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
        from app.domain.value_objects.ht_constants import STAFF_TYPE_TO_FIELD

        row = await self._staff_row(uow, sync_id, team_id, captured_at)
        if file == "club":
            # HL-2xx, 2026-08-12: club.xml v1.1 ya no trae niveles agregados
            # por puesto (verificado en vivo) — solo la inversión juvenil.
            row.youth_investment = payload.get("youth_investment", 0)
            row.youth_level = payload.get("youth_level", 0)
        else:  # stafflist
            tr = payload.get("trainer", {})
            # Defensivo: CHPP omite <Trainer> por completo en algunas
            # respuestas (verificado en vivo) — sin esta guarda, esa
            # ausencia resetearía silenciosamente nivel/tipo/liderazgo del
            # entrenador a 0 en cada sync, igual que el bug ya conocido y
            # evitado para los campos de playerdetails.
            if tr:
                row.trainer_skill_level = tr.get("skill_level", 0)
                row.trainer_type = tr.get("trainer_type", 2)
                row.trainer_leadership = tr.get("leadership", 0)

            # El desglose real de staff (persona por persona) vive aquí, no
            # en club.xml — se agrupa por StaffType para llenar las mismas 7
            # columnas de antes, ahora con datos reales, y se guarda el
            # roster completo para mostrar "2 asistentes de nivel 5 cada
            # uno" en vez de solo la suma. Igual que con `roster` en
            # players.xml: una lista vacía no dispara un recálculo — sería
            # borrar el staff real conocido por un fetch vacío/roto.
            members = payload.get("staff_members", [])
            if members:
                for field in STAFF_TYPE_TO_FIELD.values():
                    setattr(row, field, 0)
                for member in members:
                    field = STAFF_TYPE_TO_FIELD.get(member.get("staff_type", -1))
                    if field is not None:
                        setattr(row, field, getattr(row, field) + member.get("level", 0))
                row.staff_members_json = json.dumps(members)
        row.content_hash = dict_hash({
            "a": row.assistant_trainer_levels, "t": row.trainer_skill_level,
            "tt": row.trainer_type, "fc": row.form_coach_levels, "md": row.medic_levels,
            "members": row.staff_members_json,
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
            row.country_id = league.get("country_id", 0)
            row.country_code = league.get("country_code", "")
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
                    parsed = ht_to_utc(raw)
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

    YOUTH_SNAPSHOT_FIELDS = (
        "age_years", "age_days", "minutes_last_match", "can_be_promoted_in",
        "keeper", "keeper_max", "keeper_max_reached",
        "defending", "defending_max", "defending_max_reached",
        "playmaking", "playmaking_max", "playmaking_max_reached",
        "winger", "winger_max", "winger_max_reached",
        "passing", "passing_max", "passing_max_reached",
        "scoring", "scoring_max", "scoring_max_reached",
        "set_pieces", "set_pieces_max", "set_pieces_max_reached",
    )

    async def _persist_youth(
        self,
        uow: UnitOfWork,
        sync_id: int,
        team_id: int,
        payload: dict[str, Any],
        captured_at: datetime,
        result: SyncResult,
    ) -> None:
        """Plantilla juvenil — mismo patrón append-only que la plantilla
        principal: identidad estable en `youth_players`, un snapshot nuevo
        sólo cuando algo cambió de verdad (hash del contenido).

        2026-08-15: hasta hoy nadie descargaba `youthplayerlist`, así que la
        pantalla de Juveniles tenía toda la lógica construida (categorías,
        potencial, plazos, ROI) alimentándose de una tabla vacía.
        """
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        roster = payload.get("youth_players", [])
        seen_ids: set[int] = set()

        for row in roster:
            ht_id = row.get("ht_youth_player_id", 0)
            if not ht_id:
                continue
            seen_ids.add(ht_id)

            youth = await uow.session.scalar(
                select(m.YouthPlayer).where(m.YouthPlayer.ht_youth_player_id == ht_id)
            )
            if youth is None:
                youth = m.YouthPlayer(
                    ht_youth_player_id=ht_id,
                    team_id=team_id,
                    first_name=row.get("first_name", ""),
                    last_name=row.get("last_name", ""),
                    arrived_at=_parse_dt(row.get("arrival_date")),
                )
                uow.session.add(youth)
                await uow.session.flush()
            else:
                youth.first_name = row.get("first_name") or youth.first_name
                youth.last_name = row.get("last_name") or youth.last_name
                # Si había salido y vuelve a aparecer, sigue en la academia.
                youth.left_at = None

            values = {f: row.get(f) for f in self.YOUTH_SNAPSHOT_FIELDS}
            new_hash = hashlib.sha256(
                json.dumps(values, sort_keys=True, default=str).encode()
            ).digest()
            last = await uow.session.scalar(
                select(m.YouthSnapshot)
                .where(m.YouthSnapshot.youth_player_id == youth.id)
                .order_by(m.YouthSnapshot.captured_at.desc(), m.YouthSnapshot.id.desc())
                .limit(1)
            )
            if last is not None and last.content_hash == new_hash:
                result.unchanged += 1
                continue

            uow.session.add(m.YouthSnapshot(
                sync_id=sync_id,
                youth_player_id=youth.id,
                captured_at=captured_at,
                content_hash=new_hash,
                **{k: (v if v is not None else None) for k, v in values.items()},
            ))
            result.snapshots_written += 1

        # Quien ya no viene en el fichero salió de la academia (promocionado,
        # vendido o descartado). Mismo criterio que la plantilla principal: un
        # roster vacío NO marca a todos como salidos — sería un fetch roto.
        if roster:
            gone = list((await uow.session.execute(
                select(m.YouthPlayer).where(
                    m.YouthPlayer.team_id == team_id,
                    m.YouthPlayer.left_at.is_(None),
                    m.YouthPlayer.ht_youth_player_id.notin_(seen_ids),
                )
            )).scalars().all())
            for youth in gone:
                youth.left_at = captured_at

    async def _persist_matches(
        self, uow: UnitOfWork, ht_team_id: int, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """Calendario y resultados: HL-070. Un partido no es un snapshot — es un
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
            played_at = (
                ht_to_utc(date_str) or datetime.now(UTC)
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
            # — pedido explícito 2026-08-11: no deben aparecer como "Ganaste/
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

    async def _persist_league_fixtures(
        self, uow: UnitOfWork, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """Calendario completo de la serie — HL-090 fix.

        A diferencia de `_persist_matches` (que solo ve los partidos del
        equipo sincronizado), aquí llegan también los cruces entre dos
        rivales. Si el partido ya existe (porque `matches` ya lo trajo, o
        de un sync anterior), solo se rellenan `series_ht_id`/`match_round`
        y — 2026-08-08 fix (bug real, no un retraso de CHPP) — el marcador
        SI la fila todavía tenía el placeholder "no jugado" (-1): antes,
        una vez creada la fila con -1 la primera vez que se vio el cruce
        sin jugar, un sync posterior nunca volvía a mirar el marcador
        porque `series_ht_id`/`match_round` ya coincidían y el código
        cortaba con `continue` — así un partido entre dos rivales podía
        quedarse "sin jugar" para siempre aunque CHPP ya tuviera el
        resultado real. Un marcador YA confirmado (>= 0) nunca se pisa —
        esa fuente la conoce mejor `matches.xml`/`matchdetails.xml`. Si no
        existe, se crea con lo que trae este fichero, marcado como de
        liga."""
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
                ht_to_utc(date_str) or datetime.now(UTC)
            )
            home_goals = mt.get("home_goals")
            away_goals = mt.get("away_goals")
            if row is None:
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
                continue
            changed = False
            if row.series_ht_id != series_ht_id or row.match_round != mt.get("match_round"):
                row.series_ht_id = series_ht_id
                row.match_round = mt.get("match_round")
                changed = True
            if row.home_goals < 0 and home_goals is not None and away_goals is not None:
                row.home_goals = home_goals
                row.away_goals = away_goals
                row.status = "FINISHED"
                row.played_at = played_at
                changed = True
            if changed:
                result.snapshots_written += 1
            else:
                result.unchanged += 1

    async def _persist_currentbids(
        self, uow: UnitOfWork, team_id: int, payload: dict[str, Any], result: SyncResult
    ) -> None:
        """HL-161: cuenta intentos de venta hacia adelante. CHPP solo da
        una foto del momento (quién está en el mercado AHORA), nunca un
        historial — así que una aparición nueva (no estaba listado en el
        sync anterior, ahora sí) se cuenta como un intento más. Si el
        jugador sigue listado desde el sync pasado, no se repite.

        2026-08-08, pedido explícitamente: además de incrementar el
        contador, cada aparición nueva se guarda como fila propia en
        `player_listing_attempts` (con la puja más alta del momento) para
        poder ENUMERAR los intentos en la ficha de ex-jugador, no solo
        contarlos. Empieza a llenarse desde hoy — subestima lo anterior,
        igual que `listing_count`."""
        from sqlalchemy import select

        from app.infrastructure.db import models as m

        listed_now = {
            p["ht_player_id"]: p.get("highest_bid")
            for p in payload.get("listed_players", [])
        }
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
                uow.session.add(
                    m.PlayerListingAttempt(
                        player_id=player.id,
                        highest_bid=listed_now[player.ht_player_id],
                        detected_at=datetime.now(UTC),
                    )
                )
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
        #
        # 2026-08-09, bug real verificado en vivo: cada país tiene su propio
        # número de temporada (Suecia 95, Colombia 83, Grecia 80 — todos
        # sincronizados el mismo día) y worlddetails.xml trae TODOS los
        # países en una sola respuesta con el mismo `refreshed_at`. Sin
        # filtrar por país, "la fila más reciente" era básicamente al azar
        # entre esos empates — un fetch en vivo confirmó Colombia en
        # temporada 83, pero `Standing.season` había quedado guardado en 80,
        # 84 e incluso 95 (¡la de Suecia!) en syncs anteriores. Mismo bug y
        # misma corrección que `season_at()` en player_balance.py: filtrar
        # por `Team.ht_league_id` (de teamdetails.xml), el país real de
        # ESTE equipo.
        world = (
            await uow.session.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team is not None and team.ht_league_id is not None else None
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
                result.changes.append(_as_change_row(change))

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
        purchased_at = ht_to_utc_naive(deadline)
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

    async def _marcar_salidas_de_vendidos(self, uow: UnitOfWork, team_id: int) -> int:
        """Un jugador vendido ya no esta en la plantilla: marcarlo.

        `left_team_at` lo pone `mark_departed` cuando alguien DESAPARECE de
        players.xml. Los cientos de jugadores que crea el historial de
        transferencias nunca aparecieron ahi, asi que nunca desaparecen y se
        quedaban con `left_team_at` en NULL — es decir, contados como plantilla
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

    def _apply_sell_transfer(self, player: Any, t: dict[str, Any], result: SyncResult) -> None:
        """Núcleo de una venta — ver `_apply_buy_transfer`."""
        deadline = t.get("deadline") or ""
        sold_at = ht_to_utc_naive(deadline)
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
        completa = bool(team is not None and team.transfers_history_complete)
        watermark = team.last_transfer_id_seen if (team is not None and completa) else None
        highest_seen = watermark or 0
        recorrido_entero = False

        try:
            page = 1
            total_pages = 1
            while page <= total_pages:
                payload = await self._chpp.fetch(
                    "transfersteam", version=FILE_VERSIONS["transfersteam"],
                    teamID=team.ht_team_id, pageIndex=page,
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
                    t for t in page_transfers
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
                        ht_player_id = t["ht_player_id"]
                        player = players.get(ht_player_id)
                        if player is None:
                            first, last = self._split_player_name(
                                t.get("player_name", "")
                            )
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
        except Exception as exc:  # noqa: BLE001 — sync parcial, no abortamos el resto
            result.errors.append(f"transfers_history: {exc}")
            result.status = "partial"

        # La marca solo avanza si el recorrido llegó de verdad al final y
        # sin errores. Un intento que se cortó a la mitad no puede decir
        # "ya lo he visto todo hasta aquí": eso fue lo que dejó a los
        # primeros usuarios con Transferencias vacía y sin forma de
        # recuperarla, porque cada clic siguiente se paraba en la primera
        # página creyendo estar al día.
        await self._marcar_salidas_de_vendidos(uow, team_id)

        if team is not None and recorrido_entero and not result.errors:
            if highest_seen > (team.last_transfer_id_seen or 0):
                team.last_transfer_id_seen = highest_seen
            team.transfers_history_complete = True


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
            if team is not None:
                await self._recorrer_historial(
                    uow, cmd.user_id, cmd.team_id, team, result
                )

            await uow.syncs.finalize(
                sync_id, status=result.status, error="; ".join(result.errors) or None,
            )
            await uow.commit()
        return result
