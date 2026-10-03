"""Lo que no es la clase: constantes, ordenes y ayudantes del modulo.

Sale de partir `sync_team.py`, que tenia 7257 lineas.
El paquete reexporta todo esto, asi que los imports de fuera no cambian.
"""

import contextlib
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.domain.engines import mapa_del_barrido
from app.domain.engines.sync_diff import Change
from app.domain.ports.chpp_gateway import CHPPGateway
from app.domain.ports.repositories import UnitOfWork
from app.domain.value_objects.ht_time import ht_to_utc

_log = logging.getLogger(__name__)
# 2026-08-05, pedido explícitamente: "la conexión" de Hattrick Control
# muestra en vivo qué está descargando, un sync aquí ya no es una caja
# negra de 15-20s. `on_progress`, si se pasa, recibe un mensaje legible por
# cada paso real (un fichero, un jugador, un partido); `None` en cualquier
# otro caller (tests, comandos que no necesitan progreso) lo deja mudo, sin
# tocar el resto del flujo.
ProgressReporter = Callable[[str], Awaitable[None]]
#: Lo que se le dice al usuario cuando la base corta la conexión a mitad de una
#: sincronización, en vez del texto de SQLAlchemy (2026-09-15, reporte de un
#: usuario: «This Session's transaction has been rolled back...»).
MENSAJE_BASE_CORTADA = (
    "Se cortó la conexión con la base de datos. Vuelve a sincronizar: lo ya descargado se conserva."
)


def mensaje_de_error(exc: BaseException) -> str:
    """El error como se le enseña a quien sincroniza."""
    return MENSAJE_BASE_CORTADA if isinstance(exc, SQLAlchemyError) else str(exc)


async def _tras_fallo(uow: UnitOfWork, exc: BaseException) -> None:
    """Deja la sesión usable si el paso que falló lo hizo por la base.

    2026-09-15, visto en producción. Cada paso de la sincronización atrapa su
    error y sigue con el siguiente, que está bien para Hattrick --un fichero
    caído no tumba el resto-- pero no para la base: tras un corte la sesión
    queda inservible, y todos los pasos siguientes fallaban con «This Session's
    transaction has been rolled back». Deshacer aquí sólo pierde lo que ese
    paso no llegó a guardar; lo anterior ya se confirmó por partes.
    """
    if not isinstance(exc, SQLAlchemyError):
        return
    with contextlib.suppress(Exception):
        await uow.rollback()


#: Cuantos ex-jugadores se miran por sincronizacion cuando NO hay dinero que
#: perseguir. Es la red de seguridad --que nadie quede sin mirar nunca-- por
#: si la senal del dinero se perdio: `economy.xml` recuerda la semana en curso
#: y la anterior, nada mas, asi que dos semanas sin sincronizar la borran.
GOTEO_DE_VIGILANCIA = 5
# `matchesarchive.xml` no pagina: cuando un intervalo contiene más partidos,
# CHPP entrega únicamente los primeros 50. Se parte el rango hasta que cada
# respuesta sea completa y luego se deduplica por MatchID.
MATCH_ARCHIVE_RESPONSE_LIMIT = 50
MATCH_ARCHIVE_MIN_WINDOW = timedelta(minutes=1)
MATCH_ARCHIVE_INCREMENTAL_OVERLAP = timedelta(days=2)
# 2026-09-14, medido contra el equipo real: matchesarchive respeta un rango de
# tres meses (enero→marzo de 2025 devolvió esas fechas), pero con uno de un año
# lo IGNORA sin avisar y devuelve los últimos tres meses. La importación pedía
# fundación→hoy de una vez, recibía menos de 50 partidos y sellaba el historial
# como completo con sólo tres meses dentro. Por eso se pide en ventanas.
MATCH_ARCHIVE_WINDOW = timedelta(weeks=12)
# Margen al comprobar que una respuesta cae dentro de la ventana pedida: la
# fecha de Hattrick es hora sueca y la ventana va en UTC.
MATCH_ARCHIVE_RANGE_TOLERANCE = timedelta(days=2)
# Con qué reglas se leyó el archivo. La 1 es la de una sola consulta, que en la
# práctica sólo trajo tres meses; subirla obliga a releerlo entero UNA vez, como
# `transfers_import_version` con el libro de transferencias.
VERSION_DEL_ARCHIVO = 2
# Respaldo para equipos cuyo teamdetails antiguo todavía no tenga FoundedDate.
# Hattrick nació después de esta fecha, por lo que no puede dejar partidos por
# fuera; en cuanto llegue teamdetails 3.6 se usa la fundación exacta.
MATCH_ARCHIVE_FALLBACK_START = datetime(1997, 1, 1, tzinfo=UTC)
# Los encabezados/resultados viejos son baratos. Sus reportes completos no:
# matchdetails cuesta una llamada adicional por partido. El sync automático
# hidrata el ciclo reciente y deja el resto disponible bajo petición explícita.
AUTOMATIC_MATCH_DETAILS_WINDOW = timedelta(weeks=16)
# El resto --los partidos que el alta histórica guardó sólo con marcador-- se
# completa DE UNA VEZ en la primera sincronización (2026-09-14, pedido del
# usuario: «trae todos los partidos de una la primera vez»). Se piden varios a
# la vez para que cientos de partidos no hagan eterno ese primer sync; cinco a
# la vez es prudente con Hattrick.
DETALLES_HISTORICOS_EN_PARALELO = 5


async def _report(on_progress: ProgressReporter | None, message: str) -> None:
    if on_progress is not None:
        await on_progress(message)


def _full_player_name(first_name: str | None, last_name: str | None) -> str:
    """Nombre legible para cualquier progreso de sincronización.

    Los identificadores de Hattrick siguen viviendo en errores y parámetros
    técnicos, pero nunca son la etiqueta visible con la que la pantalla le
    cuenta al usuario por qué jugador va.
    """
    return (
        " ".join(part.strip() for part in (first_name, last_name) if part and part.strip())
        or "Jugador sin nombre"
    )


def _parse_dt(value: str | None) -> datetime | None:
    """Fecha de CHPP ("2026-08-09 05:05:00") a datetime aware en UTC, o `None`
    si el fichero la trae vacía. CHPP no marca zona porque siempre es la hora
    del servidor sueco, ver `ht_time.ht_to_utc`."""
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
    # Los que se piden uno a uno. No salen en la barra de progreso, pero sí en
    # el aviso de un sync a medias, que es donde se colaba la jerga.
    "matchdetails": "detalle de un partido",
    "matchesarchive": "archivo de partidos",
    "playerdetails": "ficha de un jugador",
    "transfersplayer": "transferencias de un jugador",
    "arenadetails": "estadio",
    "regiondetails": "clima de la región",
    "youthplayerdetails": "ficha de un canterano",
    "viewOldies": "antiguos canteranos",
    # Y los trabajos que no son un fichero suelto sino un encargo entero.
    "player_enrichment": "datos de jugadores vendidos",
    "tsi_at_purchase": "TSI en el momento de la compra",
    "destination_country": "país de destino de una venta",
    "censo_partidos": "partidos jugados en cada etapa",
    "reventa": "comisiones por reventa",
    "previous_club_bonus": "comisiones de club de origen",
    "transfers_history": "libro de transferencias",
}


def _nombre_legible(file: str) -> str:
    """El nombre de una fuente tal como se le puede enseñar a alguien.

    2026-09-20: el aviso de un sync a medias era lo último que enseñaba los
    nombres internos de Hattrick («players: ...», «matchdetails:38291: ...»).
    La regla de la casa es que la fuente se nombra por la pantalla de Hattrick
    de la que sale, nunca por su fichero.

    Lo que venga con un identificador detrás --«matchdetails:38291»-- conserva
    el número: identifica CUÁL de todos falló, y eso sí es útil.
    """
    nombre, _, sufijo = file.partition(":")
    legible = FILE_LABELS.get(nombre, nombre)
    return f"{legible} {sufijo}".strip() if sufijo else legible


#  HL-140: un sync normal debe poder mostrar el diff completo, posición en
# liga y resultados incluidos, no solo plantilla/economía. `teamdetails` va
# antes que `leaguedetails` porque este último necesita `series_ht_id`.
# `transfersteam` YA NO entra aquí (2026-08-22, pedido explícitamente): las
# transferencias son su propio botón. Leer solo la primera página desde el sync
# normal era la razón por la que un jugador que volvía al club pisaba su etapa
# anterior, el libro entero, que es de donde salen las etapas, se recorre en
# `_recorrer_historial`.
DEFAULT_FILES = [
    "players",
    "training",
    "economy",
    "teamdetails",
    "leaguedetails",
    "leaguefixtures",
    "matches",
    "currentbids",
    "worlddetails",
    "club",
    "stafflist",
    # youthteamdetails va ANTES que youthplayerlist: identifica qué academia es
    # la viva (id + fecha de creación) y con eso el módulo de Juveniles puede
    # acotar el ROI a la cantera actual en vez de sumar academias anteriores.
    "youthteamdetails",
    "youthplayerlist",
]
# worlddetails, 2026-08-04: única fuente de la temporada ACTUAL de Hattrick
# (leaguedetails.xml no la trae). Antes no estaba en el sync por defecto, así
# que `WorldContext.season` se quedaba congelada en lo que fuera que un
# script de desarrollo hubiera sincronizado a mano una vez, el desglose
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
# esta lista pese al comentario de arriba, solo se sincronizaban una vez, a
# mano, al conectar la cuenta. El "Sincronizar" normal nunca los refrescaba,
# así que el staff del club (asistentes, entrenador, inversión juvenil) se
# quedaba congelado semanas, y encima con datos ya obsoletos (club.xml
# cambió de esquema entretanto, ver `parse_club`).
# playerdetails: 2.6 se probó en vivo y NO trae `MotherClub`/`LastMatch`
# poblados (solo el booleano `MotherClubBonus`); 3.2, confirmado con un XML
# real de la cuenta de desarrollo, sí los trae, la versión importa más de
# lo que sugiere la documentación de campos por sí sola.
# CORRECCIÓN 2026-08-03: `transfersteam` (equipo) se usa para precio de
# compra Y venta por defecto. Un comentario anterior decía que
# `transferplayer.xml` (por jugador) devolvía 401 por scope OAuth, era un
# nombre de fichero mal escrito (falta la "s": es `transfersplayer.xml`),
# no una restricción real. Verificado en vivo con este mismo token: funciona
# y trae el historial completo de transferencias de un jugador, ver
# `parse_transfersplayer` en `app/infrastructure/chpp/parsers/__init__.py`.
#
# CORRECCIÓN 2026-08-03 (bis): `"latest"` NO es la versión más reciente de
# `transfersteam.xml`, es un esquema/ventana viejo y distinto. Comparado en
# vivo contra la cuenta real: pedir `version=latest` devolvía una página de
# 25 transferencias que terminaba justo donde `version=1.2` EMPIEZA (es
# decir, "latest" se queda ~25 transferencias atrás de lo real). Una venta
# hecha el mismo día de la prueba (Lander Fripont, 495018863) solo aparecía
# pidiendo "1.2" explícito, con "latest" nunca se habría visto. Fijado a
# "1.2" para que las ventas/compras recientes sí lleguen.
FILE_VERSIONS = {
    # 2.8 mantiene los campos de 2.6 y, validado contra players.xml de un
    # rival, expone PlayerForm y StaminaSkill que alimentan el análisis previo.
    # economy 1.4, no 1.5: 1.5 no está confirmada y degradaba el fichero al
    # esquema viejo (todo agregado en Income/CostsTemporary). 1.4 es la que
    # trae IncomeSoldPlayers/Commission, IncomeSponsorBonuses y
    # Costs{BoughtPlayers,ArenaBuilding} por separado, verificado contra
    # `docs/chpp-reference/economy.txt`, un fichero real de esta cuenta.
    "players": "2.8",
    "teamdetails": "3.6",
    "training": "2.2",
    "economy": "1.4",
    # club 1.1, no 1.0: verificado en vivo 2026-08-12, Hattrick YA NO honra
    # el pin a 1.0 y devuelve 1.1 igual (`<Specialists>` en vez de
    # `<Staff>`/niveles agregados por puesto). Fijar 1.1 explícito documenta
    # lo que de verdad se recibe en vez de mentir sobre qué versión se pidió.
    "club": "1.1",
    # 1.2, no 1.0 (2026-09-01, verificado en vivo contra esta cuenta): la 1.0
    # NO trae el nodo `<Trainer>` en absoluto -- sólo `<StaffMembers>` --, y
    # como el guardado tiene una guarda `if tr:` para no borrar al entrenador
    # cuando falta, el nivel, el tipo y el liderazgo del entrenador principal
    # NUNCA llegaron a escribirse: se quedaban en 0 y así salían en Club, en
    # Entrenamiento y en el panel. La 1.2 sí lo trae, con `TrainerSkillLevel`,
    # `Leadership`, `TrainerType` y `TrainerStatus`, y ya se usaba para mirar
    # al entrenador de un rival (ver `RIVAL_STAFFLIST_VERSION`).
    "stafflist": "1.2",
    # 2.0, no 1.8 (2026-08-09, confirmado por el usuario): a esta versión
    # `MatchRound` de cada `<League>` es la SEMANA real de temporada (1-16,
    # el mismo ciclo semanal de economía/entrenamiento), no la jornada de
    # liga (ese es un concepto distinto, de leaguedetails.xml/Standing). Se
    # fija explícito para no depender de que un cambio de versión por
    # defecto de CHPP altere el significado del campo en silencio, igual que
    # ya se hace con matchlineup.xml.
    "worlddetails": "2.0",
    "trainingevents": "1.0",
    "matches": "2.9",
    "matchdetails": "3.1",
    "leaguedetails": "1.6",
    # 1.2 verificado en vivo: trae el calendario COMPLETO de la serie (los
    # 28 pares posibles, ida y vuelta) con MatchRound real, a diferencia de
    # matches.xml, que solo trae los partidos del equipo pedido.
    "leaguefixtures": "1.2",
    # 1.1 verificado en vivo (HL-161): historial completo de transferencias
    # de UN jugador, con "s" en el nombre del fichero (transfersplayer, no
    # transferplayer), ver corrección 2026-08-03 más arriba.
    "transfersplayer": "1.1",
    # 1.0 verificado en vivo (HL-161): jugadores propios actualmente en el
    # mercado, se usa para contar intentos de venta hacia adelante, CHPP
    # no da un historial de esto.
    "currentbids": "1.0",
    "playerdetails": "3.2",
    "transfersteam": "1.2",
    # Los dos ficheros de seleccion. `nationalteammatches` no acepta ningun
    # parametro: siempre la misma ventana de un mes, todas las selecciones.
    "nationalteammatches": "1.2",
    "nationalteamdetails": "1.9",
    "arenadetails": "latest",
    # 1.2 verificado en vivo 2026-08-18: WeatherID (hoy) y TomorrowWeatherID.
    "regiondetails": "1.2",
    # El default del servidor todavía responde 1.3. `sourceSystem` y los roles
    # modernos (100-113) de partidos de torneo requieren 3.0, verificado en
    # vivo con tournamentmatchid=41877309.
    "matchorders": "3.0",
    # A diferencia de matches.xml (que sólo alcanza un mes hacia atrás:
    # medido 2026-09-07, el más viejo que devolvió era del 11 de agosto), este
    # SÍ retrocede a temporadas ya cerradas con FirstMatchDate/LastMatchDate.
    #
    # 1.5 y no 1.0, que es lo que pedía antes: las versiones 1.0 a 1.2 no
    # traen `CupLevel`/`CupLevelIndex`, así que todo partido de copa rescatado
    # del archivo entraba sin saber de qué copa era y la pantalla de Copa no
    # lo veía. Desde la 1.3 llegan los dos; la 1.5 añade `CupId` y
    # `SourceSystem`. Comprobado fichero a fichero contra el equipo real.
    "matchesarchive": "1.5",
}
# matchlineup.xml SIN versión explícita resuelve a un esquema viejo (1.2)
# donde `RoleID` es solo un índice secuencial sin significado, verificado
# en vivo 2026-08-09 (matchID 770453114, playerID 468921494: con 2.1
# RoleID=112="Delantero medio", el puesto real; sin versión, ese mismo
# jugador leía PositionCode=10="Interior izquierdo"). 2.1 además ya
# incorpora cada `<Substitution>` en el `<Lineup>` final, así que hasta un
# suplente que entró a mitad de partido queda con su posición real, y trae
# `Behaviour` (orden individual: Ofensivo/Defensivo/Hacia el medio/Hacia
# la banda, usado para "Última semana" en Posiciones). NO usar esta
# versión donde haga falta `PositionCode` (desaparece desde 1.5): el
# marcaje al hombre de rivals.py usa su propia
# `MATCHLINEUP_POSITION_CODE_VERSION = "1.2"`, a propósito distinta. Ver
# docstring de `parse_matchlineup` en
# app/infrastructure/chpp/parsers/__init__.py.
MATCHLINEUP_ROLE_VERSION = "2.1"
#: Version de las reglas con que se lee el libro de transferencias. Subirla
#: obliga a releerlo entero una vez, para todos. Historial:
#:   1 - compra o venta por los identificadores, no por la letra del tipo.
#:   2 - se guardan los movimientos sin identificador de jugador, y los dos
#:       lados de los que nos tienen de comprador y de vendedor a la vez.
VERSION_DEL_LIBRO = 2
# Campos que definen "cambio real" (excluye derivados/ruido)
HASH_FIELDS = (
    "age_years",
    "age_days",
    "tsi",
    "form",
    "stamina",
    "experience",
    "salary",
    "specialty",
    "injury_level",
    "is_transfer_listed",
    "skills",
    "loyalty",
    "leadership",
    "agreeability",
    "aggressiveness",
    "honesty",
    "mother_club_bonus",
    "country_id",
    "league_goals",
    "cup_goals",
    "friendlies_goals",
    "career_goals",
    "career_hattricks",
    "player_trainer_skill_level",
    "player_trainer_type",
)


def content_hash(player: dict[str, Any]) -> bytes:
    canonical = {k: player.get(k) for k in HASH_FIELDS}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).digest()


def dict_hash(data: dict[str, Any]) -> bytes:
    """Hash canónico de un payload por-equipo (economy, training)."""
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).digest()


#: Los indicadores de estado de ánimo que Hattrick puede devolver como -1.
#:
#: Espíritu y Confianza vienen de training.xml y se ocultan mientras se juega
#: un partido. La popularidad con la afición viene de economy.xml y NO se ha
#: visto nunca en -1 --ni una sola fila en las dos bases, con quince equipos y
#: semanas de historial--, pero se cubre igual (2026-09-02, pedido del
#: usuario): son la misma clase de dato, un nivel en una escala, y el día que
#: aparezca el -1 se guardaría como si la afición te odiara.
PLACEHOLDERS_DE_ANIMO: dict[str, tuple[str, ...]] = {
    "training": ("morale", "self_confidence"),
    "economy": ("supporters_popularity",),
}


def _sin_placeholders_de_animo(
    payload: dict[str, Any], previous: dict[str, Any] | None, campos: tuple[str, ...]
) -> dict[str, Any]:
    """Reemplaza el -1 temporal antes de persistir.

    Hattrick usa -1 mientras un partido está en curso. No significa que el
    Espíritu o la Confianza hayan bajado: significa que ese campo no está
    disponible en ese instante. Cada indicador se resuelve por separado con
    su última lectura válida. Si todavía no existe una, se guarda ``None``
    ausencia de dato, y nunca un nivel inventado.
    """
    limpio = dict(payload)
    for campo in campos:
        if limpio.get(campo) == -1:
            anterior = previous.get(campo) if previous is not None else None
            limpio[campo] = anterior if isinstance(anterior, int) and anterior >= 0 else None
    return limpio


async def trasladar_equipo_reemplazado(
    session: Any, series_ht_id: int, equipos: list[dict[str, Any]]
) -> int:
    """Pasa los partidos pendientes de un equipo reemplazado al que ocupa hoy su sitio.

    2026-09-13, visto en vivo: etbenianos1 fue reemplazado por Kivaré, con otro
    id, justo después de la jornada 8. La clasificación ya traía a Kivaré; el
    calendario guardado seguía con etbenianos1 en las jornadas 9-14, y ninguna
    pantalla encontraba al rival. Si en los pendientes de la serie sobra
    exactamente un id y en la clasificación falta exactamente uno, es el mismo
    sitio. Los partidos ya jugados no se tocan: esos sí los jugó el equipo viejo.
    Devuelve cuántos partidos cambió.
    """
    from sqlalchemy import select

    from app.infrastructure.db import models as m

    actuales = {t.get("ht_team_id"): t.get("name", "") for t in equipos if t.get("ht_team_id")}
    if not series_ht_id or len(actuales) < 2:
        return 0
    pendientes = list(
        (
            await session.execute(
                select(m.Match).where(
                    m.Match.series_ht_id == series_ht_id,
                    m.Match.home_goals < 0,
                )
            )
        ).scalars()
    )
    en_calendario = {p.home_team_ht_id for p in pendientes} | {
        p.away_team_ht_id for p in pendientes
    }
    viejos, nuevos = en_calendario - set(actuales), set(actuales) - en_calendario
    if len(viejos) != 1 or len(nuevos) != 1:
        return 0
    viejo, nuevo = viejos.pop(), nuevos.pop()
    cambiados = 0
    for p in pendientes:
        if p.home_team_ht_id == viejo:
            p.home_team_ht_id, p.home_team_name = nuevo, actuales[nuevo]
            cambiados += 1
        elif p.away_team_ht_id == viejo:
            p.away_team_ht_id, p.away_team_name = nuevo, actuales[nuevo]
            cambiados += 1
    return cambiados


@dataclass(frozen=True)
class SyncTeamCommand:
    user_id: int
    team_id: int  # id interno
    ht_team_id: int  # id Hattrick
    files: list[str] | None = None


@dataclass(frozen=True)
class SyncMatchDetailsCommand:
    """matchdetails se pide por partido (matchID), no por equipo, de ahí un
    comando aparte en vez de meterlo en `files` de SyncTeamCommand."""

    user_id: int
    team_id: int
    ht_match_id: int
    # Se pide una vez por lote y se reutiliza para los detalles de partido.
    # matchdetails da ventas; arenadetails, el aforo actual por sector.
    arena_capacity: dict[str, int] | None = None


@dataclass(frozen=True)
class SyncPlayerDetailsCommand:
    """playerdetails se pide por jugador (playerID), igual que
    matchdetails, aparte de `files`: son N llamadas CHPP, una por jugador
    de la plantilla, no una sola por equipo."""

    user_id: int
    team_id: int
    ht_player_id: int


@dataclass(frozen=True)
class SyncTransfersPlayerCommand:
    """transfersplayer.xml, HL-161: historial completo de UN jugador
    igual que playerdetails/matchdetails, una llamada por jugador, acción
    aparte que dispara el usuario (no forma parte del sync por defecto)."""

    user_id: int
    team_id: int
    ht_player_id: int


@dataclass(frozen=True)
class SyncTransfersHistoryCommand:
    """HL-161, 2026-08-04: botón "Actualizar transferencias", pagina
    transfersteam.xml completo (no solo la página más reciente) para traer
    TODA la historia de compraventas del equipo, así el jugador ya no esté
    en la plantilla ni haya sido visto nunca por `players.xml`. La primera
    vez recorre las ~40 páginas (casi 1000 transferencias); las siguientes
    paran en cuanto encuentran un TransferID ya conocido, ver
    `execute_transfers_history`."""

    user_id: int
    team_id: int
    ht_team_id: int


@dataclass(frozen=True)
class SyncPlayerEnrichmentCommand:
    """HL-161: una llamada a playerdetails.xml por jugador VENDIDO que
    rellena de un tirón edad-en-la-venta, país de origen, carácter y
    especialidad. CORRECCIÓN 2026-08-04: antes era un botón aparte
    ("Calcular edad al vender"), el usuario pidió explícitamente quitarlo,
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
    vendimos, si la hay, calcula la comisión exacta de "club anterior"
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
    # Juntar los lotes de una misma pulsacion en una sola fila de `syncs`. El
    # lote automatico del final de cada sincronizacion (2026-09-13) usa una
    # marca de hace una semana, y reutilizar la fila le colgaria sus hallazgos
    # a una sincronizacion vieja.
    reutilizar_fila: bool = True


@dataclass
class SyncResult:
    sync_id: int
    status: str
    snapshots_written: int = 0
    unchanged: int = 0
    errors: list[str] = field(default_factory=list)
    # HL-140: qué cambió respecto al sync anterior, {"category", "summary"}
    changes: list[dict[str, str]] = field(default_factory=list)
    # HL-2xx, 2026-08-12: filas `Player` recién marcadas `left_team_at` en
    # este sync (ver `mark_departed`), se anuncian en `changes` DESPUÉS de
    # que todos los ficheros terminen, no aquí mismo, porque `transfersteam`
    # (si es parte de este sync) puede rellenar `sale_price` de un jugador
    # que ya salió del roster ANTES de que ese fichero se procese.
    departed_players: list[Any] = field(default_factory=list)
    # Y lo mismo por el otro lado (2026-09-20): los que ENTRARON en la
    # plantilla en este sync. La frase de alta lleva el precio de compra, y
    # ese precio vive en el libro de transferencias, que puede procesarse
    # después de `players`. Se guardan aquí y se anuncian al final.
    arrived_players: list[Any] = field(default_factory=list)
    # HL-161, 2026-08-04: solo los usa `execute_transfers_history`, cuántas
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
    #: Donde cayo en la cola de comisiones cada jugador atendido, y de cuantos
    #: era esa cola. Es lo que deja pintar la barra como un MAPA del barrido
    #: --el frente avanza por la izquierda, el azar enciende marcas donde
    #: caiga-- en vez de como un porcentaje ciego. 2026-08-25.
    # Partidos históricos que `matches.xml` ya no alcanzaba y hubo que sacar
    # de `matchesarchive.xml`. En la primera conexión cuenta todo el pasado
    # recuperado; después sólo los nuevos añadidos a la cola incremental.
    rescued_matches: int = 0
    # El mapa del barrido de comisiones, para pintar la barra como lo que es:
    # un recorrido por la cola, no un porcentaje.
    queue_map: mapa_del_barrido.Mapa | None = None
    # Como queda la vigilancia cuando el barrido para: cuantos siguen vivos,
    # cuantos faltan por mirar y que se zanjo, por motivo.
    queue_balance: mapa_del_barrido.Balance | None = None


async def aforo_del_estadio(
    chpp: CHPPGateway, ht_team_id: int, result: SyncResult
) -> dict[str, int] | None:
    """El aforo actual del estadio DE ESTE CLUB, comprobado.

    2026-09-27, con el reporte de un usuario: «el Estadio saca los datos del
    club principal, sea cual sea el club que estes mirando».

    Es el mismo agujero que tuvo la cantera en septiembre: una cuenta de
    Hattrick puede llevar varios clubes, y si el fichero que contesta no es el
    que pediste, nadie se entera. Alli se arreglo comprobando que la academia
    devuelta fuera la del club; aqui el lector ya venia leyendo de que club es
    el estadio, y ese dato se tiraba sin mirarlo.

    Asi que se mira. Si lo que contesta Hattrick es de otro club, no se usa: el
    aforo se queda sin dato --las asistencias se guardan igual, con el minimo
    observable-- y queda dicho en el informe del sync. Un aforo equivocado es
    peor que ninguno, porque de el salen todas las ocupaciones y la cuenta de
    si compensa ampliar.
    """
    arena = await chpp.fetch(
        "arenadetails", version=FILE_VERSIONS["arenadetails"], teamID=ht_team_id
    )
    de_quien = int(arena.get("ht_team_id") or 0)
    if de_quien and de_quien != ht_team_id:
        result.errors.append(
            f"{_nombre_legible('arenadetails')}: Hattrick contesto con el estadio del "
            f"club {de_quien}, no el del {ht_team_id}; el aforo se deja sin dato"
        )
        return None
    capacidad = arena.get("current_capacity")
    return capacidad if isinstance(capacidad, dict) else None
