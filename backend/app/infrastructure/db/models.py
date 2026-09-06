"""SQLAlchemy models — núcleo del sync. Ver docs/02-modelo-datos.md para el modelo completo.

Nota particionado: en PostgreSQL, player_snapshots es RANGE(captured_at) con PK
física (id, captured_at) — eso vive en la migración (raw SQL). El ORM mapea id
como PK lógica; con sqlite (tests) funciona el autoincrement vía variant.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

PKBigInt = BigInteger().with_variant(Integer(), "sqlite")


class UtcDateTime(TypeDecorator[datetime]):
    """Fecha con zona en la base, SIN zona (UTC) en Python.

    La aplicación entera está escrita sobre fechas ingenuas en UTC, porque es
    lo que devuelve sqlite, que es donde se desarrolló y se probó todo. En
    Postgres, `timestamptz` vuelve CON zona, y entonces cualquier resta contra
    un `datetime.now(UTC).replace(tzinfo=None)` revienta con "can't subtract
    offset-naive and offset-aware datetimes". No se ve en local, no se ve en
    los tests, y aparece en cuanto hay datos reales en producción.

    En vez de repartir conversiones por cada consulta, se normaliza una sola
    vez, en la frontera: se guarda con zona (la columna sigue siendo
    `timestamptz`, no hace falta migrar nada) y se lee sin ella.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if dialect.name == "sqlite":
            # sqlite guarda texto sin desfase; una fecha con zona lo rompería.
            return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None or value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Identidad = cuenta de Hattrick. No hay email/contraseña propios de HT
    Lens: conectar vía OAuth con CHPP es el único inicio de sesión, y
    `ht_user_id` (UserID de CHPP) es la clave con la que se reconoce a un
    usuario que vuelve a conectar."""

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    login_name: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(128))
    plan: Mapped[str] = mapped_column(String(16), default="free")
    created_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class CHPPToken(Base):
    __tablename__ = "chpp_tokens"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    oauth_token_enc: Mapped[bytes] = mapped_column(LargeBinary)  # Fernet
    oauth_secret_enc: Mapped[bytes] = mapped_column(LargeBinary)  # Fernet
    key_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|revoked
    ht_user_id: Mapped[int | None] = mapped_column(BigInteger)


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_team_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # Un único dueño por ahora (MVP): multi-manager/multi-club por usuario es
    # una tabla user_teams a futuro, no necesaria mientras cada equipo tiene
    # como mucho un manager conectado.
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    league_name: Mapped[str | None] = mapped_column(String(128))
    series_name: Mapped[str | None] = mapped_column(String(128))
    # LeagueID del PAÍS (de teamdetails.xml, distinto de series_ht_id) —
    # 2026-08-04: clave para cruzar contra worlddetails.xml, que trae la
    # temporada/moneda/copas REALES de cada país en su propio
    # LeagueList/League — verificado en vivo que Colombia es LeagueID=19,
    # no el 50 que se usaba antes por error (esa era Grecia).
    ht_league_id: Mapped[int | None] = mapped_column(BigInteger)
    # LeagueLevelUnitID: leaguedetails.xml se pide por serie, no por equipo.
    # Sin esto no hay forma de sincronizar la clasificación de la liga.
    series_ht_id: Mapped[int | None] = mapped_column(BigInteger)
    # CHPP devuelve todos los importes en la moneda base del juego; cada país
    # tiene su tasa. Colombia = 10 (verificado contra Hattrick Control).
    currency_rate: Mapped[float] = mapped_column(Float, default=1.0)
    currency_name: Mapped[str] = mapped_column(String(16), default="")
    # Academia juvenil ACTUAL — 2026-08-15. Se puede cerrar y reabrir, y cada
    # apertura es una academia distinta con su propio id y fecha. Sin esto, el
    # ROI de la cantera mezclaba canteranos de academias anteriores con la
    # inversión de la actual. `None` hasta que se sincronice youthteamdetails.
    ht_youth_team_id: Mapped[int | None] = mapped_column(BigInteger)
    youth_team_name: Mapped[str | None] = mapped_column(String(128))
    youth_academy_created_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # LeagueLevel de esta serie (1 = división más alta del país) y MaxLevel
    # (divisiones totales) — de leaguedetails.xml. Hacen falta para saber si
    # el 1º puede ascender (no si ya es primera) y si el 7º-8º puede
    # descender (no si ya es la última) — HL-145. -1 = sin sincronizar.
    league_level: Mapped[int] = mapped_column(SmallInteger, default=-1)
    max_level: Mapped[int] = mapped_column(SmallInteger, default=-1)
    # Estado ACTUAL de Copa, de teamdetails.xml. `still_in_cup=None` significa
    # que nunca se sincronizó ese campo; False es una eliminación confirmada.
    # No se deriva del último partido: después de una eliminación, el último
    # encuentro sigue existiendo pero la Copa ya no está activa.
    still_in_cup: Mapped[bool | None] = mapped_column(Boolean)
    current_cup_id: Mapped[int | None] = mapped_column(BigInteger)
    current_cup_name: Mapped[str | None] = mapped_column(String(128))
    current_cup_league_level: Mapped[int | None] = mapped_column(SmallInteger)
    current_cup_level: Mapped[int | None] = mapped_column(SmallInteger)
    current_cup_level_index: Mapped[int | None] = mapped_column(SmallInteger)
    current_cup_match_round: Mapped[int | None] = mapped_column(SmallInteger)
    current_cup_match_rounds_left: Mapped[int | None] = mapped_column(SmallInteger)
    # HL-161 2026-08-04: <Stats> de transfersteam.xml — agregado de TODA la
    # historia del equipo (no de una página), se refresca en cada sync
    # normal (transfersteam siempre pide pageIndex=1). Fuente de los KPI de
    # "Resumen" — nunca se recalculan sumando player rows, que solo cubren
    # lo que esta app ha podido reconstruir jugador por jugador.
    transfer_total_buys: Mapped[int] = mapped_column(BigInteger, default=0)
    transfer_total_sales: Mapped[int] = mapped_column(BigInteger, default=0)
    transfer_number_buys: Mapped[int] = mapped_column(Integer, default=0)
    transfer_number_sales: Mapped[int] = mapped_column(Integer, default=0)
    # HL-161 2026-08-04: marca de agua del backfill histórico de
    # transfersteam.xml paginado ("Actualizar transferencias") — el
    # ht_transfer_id más alto ya procesado. Como las páginas llegan de más
    # reciente a más vieja, un re-sync puede parar en cuanto encuentra un
    # TransferID <= esta marca en vez de volver a pedir las ~40 páginas.
    last_transfer_id_seen: Mapped[int | None] = mapped_column(BigInteger)
    # True solo cuando alguna vez se recorrio la historia ENTERA sin
    # errores. Sin esto, un primer intento que se corta a la mitad deja la
    # marca de agua apuntando a lo mas reciente y la app cree para siempre
    # que ya tiene todo, sin forma de recuperar lo anterior.
    #: Con que version de las reglas se leyo el libro. Cuando las reglas
    #: cambian --y han cambiado: antes se descartaban los movimientos sin
    #: identificador de jugador y solo se anotaba un lado de los que tenian
    #: los dos-- el libro guardado se queda corto sin que nadie lo note. Esto
    #: fuerza UNA relectura completa, y solo una: al terminar se sella con la
    #: version de hoy.
    transfers_import_version: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0"
    )
    #  La caza de comisiones de club anterior. Migración 0064: el dinero
    #  dice CUÁNDO merece la pena buscar, aunque no diga quién.
    commission_seen: Mapped[int] = mapped_column(BigInteger, default=0)
    commission_seen_closed: Mapped[int] = mapped_column(BigInteger, default=0)
    commission_hunting: Mapped[bool] = mapped_column(Boolean, default=False)
    commission_tried_json: Mapped[str] = mapped_column(Text, default="[]")
    # El barrido en curso, congelado al empezarlo: la cola tal como estaba, y
    # desde cuando. Es lo que deja pintar la barra como un mapa estable —ver
    # `app/domain/engines/mapa_del_barrido.py`.
    sweep_axis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sweep_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transfers_history_complete: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    #: El identificador no es suyo: es el de la transferencia. Pasa cuando
    #: Hattrick entrega el movimiento sin identificador de jugador. Se marca
    #: para que la interfaz lo distinga y para que nadie intente pedirle su
    #: ficha a CHPP con un numero que no le corresponde.
    ht_player_id_is_transfer: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    left_team_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # Hechos de una vez, no snapshots: de transfersteam.xml (precio real de
    # compra, HL-15x) y playerdetails.xml (club madre) — no hay "sync sync_id"
    # que les corresponda, así que viven en la identidad, no en player_snapshots.
    purchase_price: Mapped[int | None] = mapped_column(Integer)
    purchased_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # HL-161: cuando ni transfersteam.xml ni transfersplayer.xml traen una
    # compra real (p. ej. el jugador llegó con el equipo antes de que
    # existiera Hattrick Manager, o CHPP no guarda tan atrás), el usuario
    # puede escribirlo a mano. Se prioriza SIEMPRE el dato real
    # (`purchase_price`) sobre el manual — nunca al revés.
    purchase_price_manual: Mapped[int | None] = mapped_column(Integer)
    purchased_at_manual: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # HL-161: precio real de venta, de transfersteam.xml (TransferType="S",
    # vendedor == nosotros) — mismo fichero y mecanismo que purchase_price,
    # nunca se sobrescribe una vez vendido (un jugador solo se vende una
    # vez desde este club).
    sale_price: Mapped[int | None] = mapped_column(Integer)
    # Ultimo salario que Hattrick reporto de este jugador, en moneda base.
    # playerdetails.xml lo trae aunque el jugador ya juegue en otro club
    # (verificado en vivo), y es la unica forma de saber lo que costaba
    # alguien que entro y salio entre dos sincronizaciones: sin esto su
    # coste de salarios figuraba como 0 e inflaba su saldo.
    last_known_salary: Mapped[int | None] = mapped_column(Integer)
    # Ya se pregunto por el pais del club comprador, con exito o sin el.
    # Sin esta marca, un comprador cuyo pais Hattrick no resuelve se queda
    # pendiente para siempre y el relleno por lotes nunca termina.
    destination_attempted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # ── El pasado de un ex-jugador ──────────────────────────────────────
    #
    # Los partidos que jugo con nosotros viven en `games_played_for_us`, unas
    # lineas mas abajo: ya existian para calcular la comision de club anterior.
    # Cerrado para siempre: ya no puede darnos nada mas, asi que no se vuelve a
    # preguntar por el nunca. Un jugador normal se cierra en cuanto lo
    # revenden (la comision es solo de la SIGUIENTE venta) o lo despiden; un
    # canterano cobra en cada venta futura, asi que solo lo cierra el despido.
    resale_closed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    resale_closed_reason: Mapped[str | None] = mapped_column(String(32))
    # Cuando se le pregunto por ultima vez vive en
    # `previous_club_bonus_checked_at`, que ya existia.
    sold_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # HL-161: edad EN EL MOMENTO DE LA VENTA, reconstruida hacia atrás desde
    # la edad actual (playerdetails.xml, válido para cualquier jugador
    # aunque ya no esté en el equipo) menos los días transcurridos desde
    # `sold_at` — solo para jugadores sin un `player_snapshots` de antes de
    # su venta. La edad es una función pura del tiempo (112 días/año en
    # Hattrick), a diferencia de las habilidades, que sí dependen de
    # entrenamiento — confirmado por el usuario 2026-08-04.
    age_years_at_sale: Mapped[int | None] = mapped_column(SmallInteger)
    age_days_at_sale: Mapped[int | None] = mapped_column(SmallInteger)
    # 2026-08-05: misma reconstrucción hacia atrás que age_*_at_sale, pero
    # anclada en `purchased_at` — pedida para la tabla "Detalle" (edad de
    # compra). Solo se rellena si no hay ya un `player_snapshots` de
    # alrededor de la compra (ver `snapshot_at_or_after` en player_balance.py).
    age_years_at_purchase: Mapped[int | None] = mapped_column(SmallInteger)
    age_days_at_purchase: Mapped[int | None] = mapped_column(SmallInteger)
    # HL-161: columnas de la tabla "Detalle" que faltaban frente al Excel
    # del usuario — reconstruidas UNA vez vía playerdetails.xml, automático
    # (no hay botón: pedido explícitamente 2026-08-04, "ya voy a tener los
    # datos después de una única vez que se haga backfill"). Carácter y
    # Especialidad casi no cambian con el tiempo, así que el valor de HOY
    # es una base razonable aunque el jugador ya no esté en el equipo — a
    # diferencia de la edad, no se reconstruyen "hacia atrás" porque no son
    # función del tiempo transcurrido.
    native_country: Mapped[str | None] = mapped_column(String(64))
    agreeability: Mapped[int | None] = mapped_column(SmallInteger)  # "Carácter"
    specialty: Mapped[int | None] = mapped_column(SmallInteger)
    # 2026-08-05: "backfill de un jugador máximo una vez", pedido
    # explícitamente — se marca tras UN intento de playerdetails.xml, haya
    # o no logrado rellenar todo. Un campo que no se pudo resolver esta vez
    # (p. ej. edad reconstruida hacia atrás con resultado negativo, o
    # ErrorCode 56/64 — jugador cuyo ID ya no resuelve en Hattrick) nunca va
    # a poder resolverse en un intento futuro: es una resta contra "hoy"
    # cuyo margen no cambia con el tiempo transcurrido (ver
    # `_apply_player_enrichment`). Sin este flag, `_backfill_sold_player_details`
    # volvía a pedir playerdetails.xml para el mismo jugador en CADA sync,
    # para siempre.
    enrichment_attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    # 2026-08-05: mismo principio, para transfersplayer.xml — si un jugador
    # no aparece con nosotros como comprador en TODA su historia de
    # transferencias, nunca va a aparecer (el historial no cambia hacia
    # atrás). Ver `_apply_transfers_player_purchase`.
    tsi_at_purchase_attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    # HL-161: TSI en el momento exacto de cada transacción — viene del
    # propio registro de transfersteam.xml/transfersplayer.xml (`<TSI>`
    # dentro de `<Transfer>`), NO de playerdetails.xml (que solo da el TSI
    # de HOY, que ya cambió). Ninguna llamada CHPP nueva: ya se pedía este
    # fichero, solo faltaba leer este campo.
    tsi_at_purchase: Mapped[int | None] = mapped_column(Integer)
    tsi_at_sale: Mapped[int | None] = mapped_column(Integer)
    # HL-161: equipo comprador (de transfersteam.xml, TransferType="S") —
    # hace falta guardarlo para poder resolver el país destino después.
    buyer_team_id: Mapped[int | None] = mapped_column(BigInteger)
    destination_country: Mapped[str | None] = mapped_column(String(64))
    # HL-161: cuántas veces se ha puesto en el mercado. CHPP no da un
    # historial de esto — solo pujas ACTUALES (currentbids.xml) — así que
    # se cuenta hacia adelante desde que existe esta columna, detectando
    # apariciones nuevas en cada sync. Subestima jugadores listados antes
    # de este fix.
    listing_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Estado transitorio para detectar una NUEVA aparición en el mercado
    # (False→True) frente a seguir listado desde el sync anterior — no es
    # el dato que le interesa al usuario, solo lo que hace falta guardar
    # para poder contar `listing_count` correctamente.
    currently_listed: Mapped[bool] = mapped_column(Boolean, default=False)
    mother_club_team_name: Mapped[str | None] = mapped_column(String(128))
    # 2026-08-04, pedido explícitamente: "canterano" real = MotherClub/TeamID
    # igual al ht_team_id de este club — reemplaza el `is_academy_graduate`
    # anterior (basado en `YouthPlayer`/`FormerYouthPlayer`, que solo cubre
    # jugadores vistos por el escaneo de cantera de esta app) en
    # PlayerBalanceQueryService. Funciona para cualquier jugador, incluidos
    # los del backfill histórico de transferencias.
    mother_club_team_id: Mapped[int | None] = mapped_column(BigInteger)
    # HL-15x: NativeLeagueName de playerdetails.xml o el cruce oficial entre
    # players.xml/CountryID y worlddetails.xml/CountryID. Nunca se infiere
    # desde el nombre del jugador o el club.
    native_league_name: Mapped[str | None] = mapped_column(String(128))
    # HL-15x #93: la app SUGIERE el momento de carrera (career_stage_engine),
    # el usuario CONFIRMA — nunca se sobreescribe solo. NULL = sin confirmar
    # todavía, se muestra la sugerencia.
    confirmed_career_stage: Mapped[str | None] = mapped_column(String(32))
    confirmed_career_stage_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # HL-161, 2026-08-14, pedido explícitamente ("guardar los transferID de
    # todos los jugadores para que, si hacemos backfilling, no se confunda"):
    # los TransferID exactos de transfersplayer.xml que delimitan ESTE stint
    # (compra→venta) con nosotros — sin ambigüedad de fechas cuando se
    # recorre el historial completo del jugador para calcular la comisión de
    # club anterior. `None` en un jugador nunca vendido, o en uno cuyo precio
    # se escribió a mano sin la transacción real detrás.
    ht_purchase_transfer_id: Mapped[int | None] = mapped_column(BigInteger)
    ht_sale_transfer_id: Mapped[int | None] = mapped_column(BigInteger)
    # Partidos REALES (RatingStars > 0, es decir que sí pisó la cancha, no
    # solo banca) que este jugador disputó con nosotros durante este stint —
    # calculado UNA vez vía matchesarchive.xml + matchlineup.xml (ventana
    # purchased_at→sold_at) y cacheado aquí, porque recalcularlo implica
    # tantas llamadas a CHPP como partidos oficiales tuvo la ventana.
    games_played_for_us: Mapped[int | None] = mapped_column(SmallInteger)
    games_played_for_us_computed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # "Backfill de un jugador máximo una vez [por vuelta al sync]" — igual
    # que `enrichment_attempted`/`tsi_at_purchase_attempted`: cuándo se
    # revisó por última vez transfersplayer.xml buscando una reventa nueva
    # tras nuestra venta. A diferencia de esos dos flags, SÍ puede volver a
    # dar resultado en el futuro (una reventa puede pasar en cualquier
    # momento), así que esto es una marca de tiempo para espaciar los
    # reintentos automáticos, no un "ya se intentó, nunca más".
    previous_club_bonus_checked_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class Sync(Base):
    __tablename__ = "syncs"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    kind: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(UtcDateTime())
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    error: Mapped[str | None] = mapped_column(String(2000))


class UiEvent(Base):
    """Qué usa la gente: una fila por página vista y por clic.

    2026-08-26, pedido por el usuario. Se guarda en CRUDO --instante exacto,
    sesión, duración-- porque de ahí salen cosas que un contador agregado ya no
    puede dar: cuánto dura una sesión, qué se pulsa dentro de cada pantalla, a
    qué horas se usa.

    El precio es espacio y que esto SÍ son datos personales de comportamiento,
    a diferencia de un contador por módulo y día. Por eso hay poda: ver
    `podar_eventos_viejos`.

    No se guarda nunca el contenido de un campo de texto ni nada que el usuario
    escriba: sólo la etiqueta del control que pulsó.
    """

    __tablename__ = "ui_events"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    #: Identificador de la visita, generado por el navegador. Se corta por
    #: silencio, no al cerrar: cerrar no siempre avisa.
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # "page" | "click"
    module: Mapped[str] = mapped_column(String(64), index=True)
    #: En un clic, la etiqueta del control. En una página, la pestaña si la hay.
    label: Mapped[str | None] = mapped_column(String(120))
    at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    #: Milisegundos con la pestaña DE VERDAD visible. Sin esto, una pestaña
    #: olvidada toda la noche diría "ocho horas en Juveniles".
    visible_ms: Mapped[int] = mapped_column(Integer, default=0)


class SyncChange(Base):
    """Qué cambió en un sync respecto al anterior — HL-140. Se calcula una
    sola vez, en el momento del sync (cuando el old/new ya están en memoria),
    no reconstruido después: para `matches`/`teamdetails`, que se sobrescriben
    in-place, es la única forma de conservar el "antes"."""

    __tablename__ = "sync_changes"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(String(500))
    # El mismo cambio como dato (metric/label/before/after/kind), para que el
    # frontend no tenga que sacar los números de `summary` con una regex —
    # ver 0045_sync_change_detail_json.py. `None` en las filas anteriores a
    # 2026-08-15, que se siguen leyendo con el parser de compatibilidad.
    detail_json: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class PlayerMatchRating(Base):
    """Histórico real de rating por partido de UN jugador — HL-15x #21.

    `player_snapshots.last_match_*` solo guarda el partido MÁS RECIENTE (se
    pisa en cada sync de playerdetails). Esta tabla es append-only: una fila
    por partido realmente distinto visto, para poder graficar una serie en
    el tiempo en vez de un único punto. `ht_match_id` deduplica: si
    playerdetails vuelve a traer el mismo último partido en el siguiente
    sync (nada nuevo jugado todavía), no se inserta una fila repetida.
    """

    __tablename__ = "player_match_ratings"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger)
    position_code: Mapped[int] = mapped_column(SmallInteger)
    played_minutes: Mapped[int] = mapped_column(SmallInteger)
    rating: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())

    __table_args__ = (Index("ix_pmr_player_match", "player_id", "ht_match_id", unique=True),)


class PlayerListingAttempt(Base):
    """Un intento de venta detectado — HL-161, 2026-08-08, pedido
    explícitamente ("enumerar los intentos de venta").

    CHPP no da un historial de listados (`currentbids.xml` es solo una foto
    del momento), así que igual que `Player.listing_count` (que solo
    cuenta), esta tabla solo empieza a llenarse desde que existe: una fila
    por aparición NUEVA en el mercado detectada en `_persist_currentbids`
    (no se repite mientras el jugador siga listado desde el sync anterior).
    Subestima intentos anteriores a esta fecha, igual que `listing_count`.
    """

    __tablename__ = "player_listing_attempts"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    # Puja más alta en el momento de la detección, en moneda base del juego
    # (se convierte a moneda local al leer, igual que salary/purchase_price)
    # — `None` si CHPP no reportó ninguna puja todavía en ese instante.
    highest_bid: Mapped[int | None] = mapped_column(BigInteger)
    detected_at: Mapped[datetime] = mapped_column(UtcDateTime())

    # ── El intento como tal, de principio a fin (2026-08-22) ────────────
    #
    # Hasta ahora una fila era solo "apareció en el mercado tal día". Un
    # intento de venta es mas que eso: tiene un plazo, un final y un
    # resultado, y es lo que de verdad se quiere estudiar -a que precio se
    # vende, en que semana, cuantas veces hubo que intentarlo-.
    ht_player_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    #: La etapa a la que pertenece: un jugador puede intentar venderse en dos
    #: pasos distintos por el club.
    stint_id: Mapped[int | None] = mapped_column(ForeignKey("player_stints.id"))
    #: Cuando cierra la puja, segun Hattrick.
    deadline: Mapped[datetime | None] = mapped_column(UtcDateTime())
    #: Cuando se detecto que ya no estaba en el mercado.
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    #: La ultima puja vista antes de que terminara.
    last_highest_bid: Mapped[int | None] = mapped_column(BigInteger)
    #: Termino en venta, o el jugador se quedo.
    sold: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    #: Cuantas veces lo miraron mientras estaba listado. Hattrick solo lo dice
    #: en el texto de las noticias, nunca por CHPP, asi que lo teclea el
    #: usuario. `None` = todavia no lo sabemos.
    times_seen: Mapped[int | None] = mapped_column(Integer)
    #: El usuario ya decidio sobre este intento: lo respondio o lo ignoro. Sin
    #: esto el aviso volveria a salir para siempre.
    times_seen_asked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    #: El precio que se pedia. Tampoco lo da CHPP: sale del mismo mensaje que
    #: las visitas ("El precio solicitado era de 723 000 US$"), en moneda local
    #: porque lo teclea el usuario tal como lo lee.
    asking_price: Mapped[int | None] = mapped_column(BigInteger)


class TeamTransfer(Base):
    """Cada compra y cada venta del club, tal como las cuenta Hattrick.

    Hasta 2026-08-22 el libro de transferencias se leia y se tiraba: de cada
    jugador quedaba solo su ultima compra y su ultima venta, encima de la fila
    del jugador. Por eso quien volvia al club pisaba su etapa anterior.

    Guardarlas permite reconstruir las etapas hacia atras, con toda la historia
    y sin volver a pedirsela a Hattrick. `ht_transfer_id` es unico: una
    transferencia no se cuenta dos veces aunque el recorrido se repita.
    """

    __tablename__ = "team_transfers"
    # Un mismo movimiento puede ser compra Y venta a la vez: cuando el club
    # aparece en los dos lados, Hattrick lo cuenta en sus dos totales. Por eso
    # lo unico no es la transferencia sola, sino la transferencia por lado —
    # que sigue impidiendo contarla dos veces por el mismo concepto.
    __table_args__ = (UniqueConstraint("ht_transfer_id", "is_buy", name="uq_transfer_por_lado"),)
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    ht_transfer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    player_name: Mapped[str] = mapped_column(String(128), default="")
    deadline: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    price: Mapped[int] = mapped_column(BigInteger, default=0)
    #: True si la compramos nosotros; False si la vendimos.
    is_buy: Mapped[bool] = mapped_column(Boolean, default=False)
    #: El otro club: quien nos lo vendio, o quien nos lo compro.
    counterpart_team_id: Mapped[int | None] = mapped_column(BigInteger)
    tsi: Mapped[int | None] = mapped_column(Integer)


class PlayerStint(Base):
    """Cada paso de un jugador por el club, con su propio saldo.

    2026-08-22, pedido explicitamente: "cada etapa, un registro". Hasta ahora
    la compra y la venta vivian en la fila del jugador, asi que quien volvia al
    club pisaba su etapa anterior. En la base del usuario ya habia un caso real
    -Humberto Granada, que salia como "comprado el 01/08/2026, vendido el
    17/07/2022"-: una fila imposible, vendido cuatro años antes de comprarlo.

    Las etapas se derivan del libro de compras y ventas, que trae cada
    movimiento con su fecha y su precio: una compra nuestra abre etapa y la
    venta siguiente la cierra. Nada se inventa, y por eso se puede reconstruir
    hacia atras toda la historia.

    Un canterano no tiene compra: su etapa se abre igual, marcada como llegada
    de cantera, porque tambien tuvo un coste (el ascenso) y tambien vendio.
    """

    __tablename__ = "player_stints"
    __table_args__ = (UniqueConstraint("player_id", "arrived_at", name="uq_stint_player_arrival"),)

    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)

    arrived_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    arrival_price: Mapped[int | None] = mapped_column(Integer)
    arrival_transfer_id: Mapped[int | None] = mapped_column(BigInteger)
    #: Llego de la cantera, no de una compra.
    from_academy: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    #: Ni comprado ni de cantera: no se sabe de donde salio. Pasa con los
    #: movimientos que Hattrick entrega sin identificador de jugador — sin ese
    #: dato no hay compra que enlazar, y darlos por canteranos meteria como
    #: gratis a gente que costo dinero.
    unknown_origin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    left_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    sale_price: Mapped[int | None] = mapped_column(Integer)
    sale_transfer_id: Mapped[int | None] = mapped_column(BigInteger)
    buyer_team_id: Mapped[int | None] = mapped_column(BigInteger)

    #: Partidos jugados de verdad en ESTA etapa. Se cuenta una vez por etapa,
    #: no una vez por jugador: por eso una segunda vuelta se cuenta aparte.
    games_played_for_us: Mapped[int | None] = mapped_column(SmallInteger)
    games_computed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    #: Fuera de todos los calculos de Transferencias, por decision del usuario.
    excluded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    #: Lo que el usuario atribuye a mano cuando Hattrick ya no lo da. Siempre
    #: cede ante el dato real si algun dia aparece.
    training_type_manual: Mapped[int | None] = mapped_column(SmallInteger)
    top_skill_manual: Mapped[str | None] = mapped_column(String(32))
    age_years_manual: Mapped[int | None] = mapped_column(SmallInteger)
    age_days_manual: Mapped[int | None] = mapped_column(SmallInteger)

    #: Habilidad que más creció en TODO el historial observado hasta esta
    #: venta. Sin máximo único, se resuelve por niveles acumulados y cantidad
    #: de jugadores de su temporada, entrenamiento actual y prioridad fija.
    #: Es un cache derivado y recalculable.
    derived_training_skill: Mapped[str | None] = mapped_column(String(32))
    derived_training_levels: Mapped[int | None] = mapped_column(SmallInteger)
    derived_training_method: Mapped[str | None] = mapped_column(String(32))
    derived_training_computed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class PreviousClubBonus(Base):
    """Comisión de "club anterior" EXACTA — HL-161, 2026-08-14, pedido
    explícitamente ("encontré la forma de asignar exactamente el dinero").

    Reemplaza por completo el reparto heurístico que vivía en
    `resale_bonus.py`: cuando alguien revende a un ex-jugador nuestro,
    Hattrick nos paga un % de esa reventa según cuántos partidos REALES
    (`RatingStars > 0`, no banca) jugó con nosotros durante su stint — la
    tabla oficial vive en `previous_club_bonus.py`. Cada fila es una
    reventa real, identificada sin ambigüedad por `resale_transfer_id`
    (único: una reventa nunca se cuenta dos veces aunque el backfill se
    repita). `amount` viene en la moneda base del juego, igual que
    purchase_price/sale_price — se convierte a la moneda local al leer."""

    __tablename__ = "previous_club_bonuses"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    resale_transfer_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    resale_price: Mapped[int] = mapped_column(BigInteger)
    resale_deadline: Mapped[datetime] = mapped_column(UtcDateTime())
    buyer_team_id: Mapped[int] = mapped_column(BigInteger)
    seller_team_id: Mapped[int] = mapped_column(BigInteger)
    games_played_with_us: Mapped[int] = mapped_column(SmallInteger)
    pct_applied: Mapped[float] = mapped_column(Float)
    amount: Mapped[int] = mapped_column(BigInteger)
    computed_at: Mapped[datetime] = mapped_column(UtcDateTime())


class EconomySnapshot(Base):
    """Append-only. 1 fila por cambio real (diffing por content_hash)."""

    __tablename__ = "economy_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())
    cash: Mapped[int] = mapped_column(BigInteger)
    expected_cash: Mapped[int] = mapped_column(BigInteger)
    sponsors_popularity: Mapped[int] = mapped_column(SmallInteger)
    # None = economy.xml devolvió el placeholder -1 y todavía no había una
    # observación válida anterior que conservar. Mismo criterio que el
    # Espíritu y la Confianza: un nivel ausente no es un nivel bajo.
    supporters_popularity: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fan_club_size: Mapped[int] = mapped_column(Integer)
    income_spectators: Mapped[int] = mapped_column(Integer)
    income_sponsors: Mapped[int] = mapped_column(Integer)
    # CHPP 1.5 separa estas partidas; son NULL cuando la versión antigua sólo
    # entrega el agregado IncomeTemporary. Nunca se reconstruyen ni agrupan.
    income_sponsor_bonuses: Mapped[int | None] = mapped_column(BigInteger)
    income_financial: Mapped[int] = mapped_column(Integer)
    income_sold_players: Mapped[int | None] = mapped_column(BigInteger)
    income_sold_players_commission: Mapped[int | None] = mapped_column(BigInteger)
    income_temporary: Mapped[int | None] = mapped_column(BigInteger)
    income_sum: Mapped[int] = mapped_column(BigInteger)
    costs_arena: Mapped[int] = mapped_column(Integer)
    costs_players: Mapped[int] = mapped_column(Integer)
    costs_financial: Mapped[int] = mapped_column(Integer)
    costs_bought_players: Mapped[int | None] = mapped_column(BigInteger)
    costs_arena_building: Mapped[int | None] = mapped_column(BigInteger)
    costs_staff: Mapped[int] = mapped_column(Integer)
    costs_temporary: Mapped[int | None] = mapped_column(BigInteger)
    costs_youth: Mapped[int] = mapped_column(Integer)
    costs_sum: Mapped[int] = mapped_column(BigInteger)
    expected_weeks_total: Mapped[int] = mapped_column(BigInteger)
    last_income_sum: Mapped[int] = mapped_column(BigInteger)
    last_costs_sum: Mapped[int] = mapped_column(BigInteger)
    last_weeks_total: Mapped[int] = mapped_column(BigInteger)
    # Desglose por categoría de la semana YA CERRADA — CHPP solo entrega el
    # agregado (Last*Sum) en versiones antiguas; estos vienen NULL en
    # snapshots sincronizados antes de que el fichero los incluyera. Sin
    # LastIncomeSponsorBonuses: ninguna versión vista lo expone para la
    # semana cerrada, sólo para la semana en curso.
    last_income_spectators: Mapped[int | None] = mapped_column(BigInteger)
    last_income_sponsors: Mapped[int | None] = mapped_column(BigInteger)
    last_income_financial: Mapped[int | None] = mapped_column(BigInteger)
    last_income_sold_players: Mapped[int | None] = mapped_column(BigInteger)
    last_income_sold_players_commission: Mapped[int | None] = mapped_column(BigInteger)
    last_income_temporary: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_arena: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_players: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_financial: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_staff: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_youth: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_bought_players: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_arena_building: Mapped[int | None] = mapped_column(BigInteger)
    last_costs_temporary: Mapped[int | None] = mapped_column(BigInteger)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_es_team_time", "team_id", "captured_at"),)


class TrainingSnapshot(Base):
    """Configuración de entrenamiento observada. Append-only con diffing."""

    __tablename__ = "training_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())
    training_type: Mapped[int] = mapped_column(SmallInteger)
    training_level: Mapped[int] = mapped_column(SmallInteger)
    new_training_level: Mapped[int] = mapped_column(SmallInteger)
    stamina_part: Mapped[int] = mapped_column(SmallInteger)
    last_training_type: Mapped[int] = mapped_column(SmallInteger)
    last_training_level: Mapped[int] = mapped_column(SmallInteger)
    last_stamina_part: Mapped[int] = mapped_column(SmallInteger)
    trainer_ht_id: Mapped[int] = mapped_column(BigInteger)
    trainer_name: Mapped[str] = mapped_column(String(128))
    # None = training.xml devolvió el placeholder -1 y todavía no existía una
    # observación válida anterior que conservar. No se almacena -1 como si
    # fuera un nivel real.
    morale: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    self_confidence: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    formation_xp_json: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_ts_team_time", "team_id", "captured_at"),)


class PlayerSnapshot(Base):
    __tablename__ = "player_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())
    age_years: Mapped[int] = mapped_column(SmallInteger)
    age_days: Mapped[int] = mapped_column(SmallInteger)
    tsi: Mapped[int] = mapped_column(Integer)
    form: Mapped[int] = mapped_column(SmallInteger)
    stamina: Mapped[int] = mapped_column(SmallInteger)
    experience: Mapped[int] = mapped_column(SmallInteger)
    salary: Mapped[int] = mapped_column(Integer)
    keeper: Mapped[int | None] = mapped_column(SmallInteger)
    defending: Mapped[int | None] = mapped_column(SmallInteger)
    playmaking: Mapped[int | None] = mapped_column(SmallInteger)
    winger: Mapped[int | None] = mapped_column(SmallInteger)
    passing: Mapped[int | None] = mapped_column(SmallInteger)
    scoring: Mapped[int | None] = mapped_column(SmallInteger)
    set_pieces: Mapped[int | None] = mapped_column(SmallInteger)
    injury_level: Mapped[int] = mapped_column(SmallInteger, default=-1)
    is_transfer_listed: Mapped[bool] = mapped_column(Boolean, default=False)
    # De players.xml (2.6, ya sincronizado): parseados desde siempre en algún
    # caso (specialty) o nunca, y descartados antes de llegar aquí. Cero
    # llamadas CHPP nuevas — HL-15x.
    specialty: Mapped[int] = mapped_column(Integer, default=0)
    loyalty: Mapped[int] = mapped_column(Integer, default=0)
    leadership: Mapped[int] = mapped_column(Integer, default=0)
    agreeability: Mapped[int] = mapped_column(Integer, default=0)
    aggressiveness: Mapped[int] = mapped_column(Integer, default=0)
    honesty: Mapped[int] = mapped_column(Integer, default=0)
    mother_club_bonus: Mapped[bool] = mapped_column(Boolean, default=False)
    country_id: Mapped[int] = mapped_column(Integer, default=0)
    league_goals: Mapped[int] = mapped_column(Integer, default=0)
    cup_goals: Mapped[int] = mapped_column(Integer, default=0)
    friendlies_goals: Mapped[int] = mapped_column(Integer, default=0)
    career_goals: Mapped[int] = mapped_column(Integer, default=0)
    career_hattricks: Mapped[int] = mapped_column(Integer, default=0)
    career_assists: Mapped[int] = mapped_column(Integer, default=0)
    player_trainer_skill_level: Mapped[int] = mapped_column(Integer, default=0)
    player_trainer_type: Mapped[int] = mapped_column(Integer, default=0)
    # De playerdetails.xml (nunca llamado en el sync normal — HL-15x fase B,
    # sync aparte por jugador): última posición/rating jugado. Se actualizan
    # sobre el snapshot más reciente, no crean uno nuevo: no son un cambio de
    # habilidades.
    last_match_ht_id: Mapped[int | None] = mapped_column(BigInteger)
    last_match_position_code: Mapped[int | None] = mapped_column(SmallInteger)
    last_match_played_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    last_match_rating: Mapped[float | None] = mapped_column(Float)
    # 2026-08-09, pedido explícitamente: caso real (Volodymyr Manakin) probó
    # que `LastMatch` de playerdetails.xml puede ser de hace más de un año
    # — "el último partido con datos de este jugador", no "la semana
    # pasada". Sin esta fecha, "Último partido" no puede distinguir un dato
    # genuinamente reciente de uno viejo (ver `SquadQueryService`, que solo
    # muestra posición/rating si esta fecha cae dentro de los últimos 7
    # días respecto a HOY, calculado en cada consulta).
    last_match_played_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # 2026-08-09, pedido explícitamente: "Última semana" solo mostraba la
    # posición base (portero/defensa/lateral/medio/extremo/delantero) sin
    # decir si la orden individual fue Ofensivo/Defensivo/Hacia el
    # medio/Hacia la banda — ese dato NO está en `LastMatch` de
    # playerdetails.xml, solo en el `Behaviour` de matchlineup.xml para el
    # partido concreto (`last_match_ht_id`). NULL = no se pudo resolver
    # (partido de selección/torneo fuera de alcance, o matchlineup.xml
    # todavía no lo tiene) — nunca se confunde con Behaviour=0 ("Normal").
    last_match_behaviour_code: Mapped[int | None] = mapped_column(SmallInteger)
    # 2026-08-05: Caps/CapsU20 de playerdetails.xml — totales de carrera con
    # la selección nacional (mayor y sub-20). NULL = todavía no se ha pedido
    # playerdetails.xml para este jugador, distinto de 0 caps reales.
    career_caps: Mapped[int | None] = mapped_column(SmallInteger)
    career_caps_u20: Mapped[int | None] = mapped_column(SmallInteger)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_ps_player_time", "player_id", "captured_at"),)


# ── Entities from DATABASE.md that were missing ─────────────────────────────


class Standing(Base):
    """Historical league tables. DATABASE.md: `standings`."""

    __tablename__ = "standings"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    series_ht_id: Mapped[int] = mapped_column(BigInteger, index=True)
    season: Mapped[int] = mapped_column(SmallInteger)
    match_round: Mapped[int] = mapped_column(SmallInteger)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())
    team_ht_id: Mapped[int] = mapped_column(BigInteger, index=True)
    team_name: Mapped[str] = mapped_column(String(128))
    position: Mapped[int] = mapped_column(SmallInteger)
    played: Mapped[int] = mapped_column(SmallInteger)
    won: Mapped[int] = mapped_column(SmallInteger)
    draws: Mapped[int] = mapped_column(SmallInteger)
    lost: Mapped[int] = mapped_column(SmallInteger)
    goals_for: Mapped[int] = mapped_column(SmallInteger)
    goals_against: Mapped[int] = mapped_column(SmallInteger)
    points: Mapped[int] = mapped_column(SmallInteger)

    __table_args__ = (Index("ix_standings_series_round", "series_ht_id", "season", "match_round"),)


class StadiumHistory(Base):
    """Attendance and gate income per match. DATABASE.md: `stadium_history`."""

    __tablename__ = "stadium_history"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    played_at: Mapped[datetime] = mapped_column(UtcDateTime())
    match_type: Mapped[int] = mapped_column(SmallInteger)
    weather: Mapped[int] = mapped_column(SmallInteger, default=-1)
    capacity_total: Mapped[int] = mapped_column(Integer)
    # Capacidad POR SECTOR. Sin esto un lleno es indetectable: si la capacidad
    # se deriva de lo vendido, la ocupación sale siempre igual y la demanda
    # censurada nunca se puede distinguir de la demanda satisfecha.
    capacity_terraces: Mapped[int | None] = mapped_column(Integer)
    capacity_basic: Mapped[int | None] = mapped_column(Integer)
    capacity_roof: Mapped[int | None] = mapped_column(Integer)
    capacity_vip: Mapped[int | None] = mapped_column(Integer)
    # La asistencia va SOLO en total. El desglose por sector es una funcion de
    # HT Supporter y las reglas de CHPP prohiben replicarla, asi que ni se
    # recoge ni se guarda (migracion 0076). El total en cambio es publico:
    # Hattrick lo enseña en la pagina del partido.
    sold_total: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[int] = mapped_column(Integer, default=0)


class Match(Base):
    """Immutable match record. DATABASE.md: `matches`."""

    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    played_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    match_type: Mapped[int] = mapped_column(SmallInteger)
    status: Mapped[str] = mapped_column(String(16))
    home_team_ht_id: Mapped[int] = mapped_column(BigInteger, index=True)
    away_team_ht_id: Mapped[int] = mapped_column(BigInteger, index=True)
    home_team_name: Mapped[str] = mapped_column(String(128))
    away_team_name: Mapped[str] = mapped_column(String(128))
    home_goals: Mapped[int] = mapped_column(SmallInteger, default=-1)
    away_goals: Mapped[int] = mapped_column(SmallInteger, default=-1)
    # De leaguefixtures.xml (HL-090 fix): la ÚNICA fuente que trae el
    # calendario completo de la serie, no solo los partidos del equipo
    # propio — sin esto, el simulador de temporada no puede saber qué pasa
    # en un cruce entre dos rivales. NULL en partidos sincronizados antes de
    # este fix o que no son de liga (copa, amistoso).
    series_ht_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    match_round: Mapped[int | None] = mapped_column(SmallInteger)
    # Identifican qué copa concreta es (hay varias en paralelo). -1 = CHPP no
    # los trajo para este partido. No es el número de ronda: eso se ESTIMA
    # contando partidos con el mismo par, ver cup.py.
    cup_level: Mapped[int] = mapped_column(SmallInteger, default=-1)
    cup_level_index: Mapped[int] = mapped_column(SmallInteger, default=-1)
    # `matches.xml` identifica el sistema al que pertenece el partido. Es
    # imprescindible para pedir sus órdenes: los torneos usan
    # `htointegrated`, mientras los partidos normales usan `hattrick`.
    source_system: Mapped[str | None] = mapped_column(String(32))
    # Solo se suministra para próximos partidos propios. None = CHPP no lo
    # dijo; False = todavía no se enviaron órdenes; True = órdenes enviadas.
    orders_given: Mapped[bool | None] = mapped_column(Boolean)
    # Estado actual de las órdenes enviadas. Se sobrescribe mientras el
    # partido siga próximo porque el manager puede cambiarlas hasta el cierre;
    # después del partido queda como evidencia de la alineación elegida.
    submitted_lineup_json: Mapped[str | None] = mapped_column(String(4000))
    submitted_tactic_type: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_attitude: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_coach_modifier: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_orders_captured_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # Predicción oficial de Hattrick para esas órdenes
    # (`matchorders.xml?actionType=predictratings`). Son ratings de inicio de
    # partido, no el promedio observado que después entrega matchdetails.
    submitted_tactic_skill: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_midfield: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_right_def: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_central_def: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_left_def: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_right_att: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_central_att: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_rating_left_att: Mapped[int | None] = mapped_column(SmallInteger)
    submitted_ratings_captured_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class MatchRating(Base):
    """Sector ratings for one team in one match."""

    __tablename__ = "match_ratings"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger, index=True)
    # HL-2xx: en partidos NO oficiales (Escaleras/Duelos, MatchType 50/62)
    # matchdetails.xml reporta un TeamID efímero para AMBOS lados —incluso el
    # propio, no solo el del rival— que no coincide con ningún ht_team_id real
    # (verificado con datos reales de la cuenta: ni el equipo propio ni el
    # rival aparecen en `team_ht_id` para esos partidos). `team_ht_id` sigue
    # siendo el ht_team_id real para partidos oficiales, pero para localizar
    # la fila de un lado concreto hay que usar `is_home` (posición en el XML,
    # que sí es fiable siempre) en vez de `team_ht_id`.
    team_ht_id: Mapped[int] = mapped_column(BigInteger, index=True)
    is_home: Mapped[bool] = mapped_column(Boolean)
    midfield: Mapped[int] = mapped_column(SmallInteger)
    right_def: Mapped[int] = mapped_column(SmallInteger)
    central_def: Mapped[int] = mapped_column(SmallInteger)
    left_def: Mapped[int] = mapped_column(SmallInteger)
    right_att: Mapped[int] = mapped_column(SmallInteger)
    central_att: Mapped[int] = mapped_column(SmallInteger)
    left_att: Mapped[int] = mapped_column(SmallInteger)
    #: Balón parado indirecto, defensa y ataque. `None` en las filas
    #: anteriores al 2026-09-05: estaban en el XML desde siempre pero el
    #: parser leía las siete zonas y se saltaba estas dos, así que lo ya
    #: guardado no las tiene y sólo se rellenan al volver a pedir el partido.
    set_pieces_def: Mapped[int | None] = mapped_column(SmallInteger)
    set_pieces_att: Mapped[int | None] = mapped_column(SmallInteger)
    tactic_type: Mapped[int] = mapped_column(SmallInteger, default=0)
    tactic_skill: Mapped[int] = mapped_column(SmallInteger, default=0)
    possession_first_half: Mapped[int] = mapped_column(SmallInteger, default=50)
    possession_second_half: Mapped[int] = mapped_column(SmallInteger, default=50)
    # HL-2xx: TeamAttitude ya se parseaba (parse_matchdetails) pero se
    # descartaba al persistir — se necesita para el historial de táctica del
    # módulo de rivales. NULL = fila de antes de esta columna, O lado para
    # el que CHPP no incluyó <TeamAttitude> — que es SIEMPRE el caso de un
    # rival (verificado en vivo: el propio equipo la trae siempre, un
    # rival nunca). -1 sí es un valor real cuando SÍ se leyó: "Jugar
    # relajados".
    attitude: Mapped[int | None] = mapped_column(SmallInteger)
    # HL-2xx, 2026-08-12: la suposición original de un `<Event>`/EventTypeID
    # por evento era incorrecta — matchdetails.xml real (v3.1) nunca lo
    # trae. Lo que sí trae por lado es el conteo de ocasiones por zona
    # (NrOfChances{Left,Center,Right,SpecialEvents,Other}), verificado en
    # vivo. `match_events` (la tabla vieja, siempre vacía) se eliminó.
    chances_left: Mapped[int] = mapped_column(SmallInteger, default=0)
    chances_center: Mapped[int] = mapped_column(SmallInteger, default=0)
    chances_right: Mapped[int] = mapped_column(SmallInteger, default=0)
    chances_special: Mapped[int] = mapped_column(SmallInteger, default=0)
    chances_other: Mapped[int] = mapped_column(SmallInteger, default=0)


class YouthScout(Base):
    """Un ojeador de la academia, con lo que cuesta y desde cuando.

    2026-08-26, pedido por el usuario: cada ojeador cuesta 5.000 por semana y
    se le abona lo que dieron los canteranos que EL descubrio. Para eso hace
    falta saber desde cuando esta.

    Sale de `youthteamdetails.xml` con `showScouts=true` --sin ese parametro el
    fichero no trae ojeadores en NINGUNA version; comprobado de la 1.0 a la
    1.3--.

    `gone_at` existe porque un ojeador despedido simplemente DESAPARECE de la
    lista y Hattrick no dice cuando. Se anota la ultima vez que se le vio y su
    coste se cierra ahi; el error queda acotado a lo que se tarde entre dos
    sincronizaciones.
    """

    __tablename__ = "youth_scouts"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    ht_scout_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(128))
    hired_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    #: Ultima vez que aparecio en la lista. `None` = sigue contratado.
    gone_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UtcDateTime())
    region_name: Mapped[str | None] = mapped_column(String(128))


class FormerYouthPlayer(Base):
    """Graduated or sold academy players. DATABASE.md: `former_youth_players`.

    Only current public data is stored, never a history of another club's
    player: CHPP rules allow displaying current statistics but not tracking.
    """

    __tablename__ = "former_youth_players"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    #: Cuando llego a su club ACTUAL, que casi nunca es el nuestro.
    #: Se llamaba `promoted_at` y se creia la fecha de ascenso al primer
    #: equipo; la referencia dice que `ArrivalDate` es «the date of
    #: arrival to current team» y la aritmetica lo confirmaba: los 43
    #: ex-canteranos salian vendidos ANTES de «ascender» (2026-08-31).
    arrived_at_current_team: Mapped[datetime | None] = mapped_column(UtcDateTime())
    sold_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    sold_for: Mapped[int | None] = mapped_column(Integer)
    current_team_name: Mapped[str | None] = mapped_column(String(128))
    current_tsi: Mapped[int | None] = mapped_column(Integer)
    refreshed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class YouthPlayer(Base):
    """Identidad estable de un juvenil propio. DATABASE.md: `youth_players`.

    Sólo canteranos del propio club: las reglas de CHPP permiten mostrar datos
    actuales de terceros pero no llevar su histórico, y un juvenil ajeno ni
    siquiera es visible.
    """

    __tablename__ = "youth_players"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_youth_player_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    arrived_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    left_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    #: La especialidad, con los mismos códigos que la plantilla principal. Va
    #: aquí y no en el snapshot porque no cambia nunca. `0` es a la vez "sin
    #: especialidad" y "todavía no sincronizado" -- ver la migración 0077.
    specialty: Mapped[int] = mapped_column(Integer, default=0)


class YouthSnapshot(Base):
    """Append-only, igual que el resto: una fila por cambio real.

    Cada skill tiene nivel actual y techo. El techo puede ser NULL mientras el
    ojeador no lo haya revelado, y esa diferencia importa: un techo desconocido
    no es un techo bajo, y el motor de academia los trata distinto.
    """

    __tablename__ = "youth_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    youth_player_id: Mapped[int] = mapped_column(ForeignKey("youth_players.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())
    age_years: Mapped[int] = mapped_column(SmallInteger)
    age_days: Mapped[int] = mapped_column(SmallInteger)
    keeper: Mapped[int | None] = mapped_column(SmallInteger)
    keeper_max: Mapped[int | None] = mapped_column(SmallInteger)
    defending: Mapped[int | None] = mapped_column(SmallInteger)
    defending_max: Mapped[int | None] = mapped_column(SmallInteger)
    playmaking: Mapped[int | None] = mapped_column(SmallInteger)
    playmaking_max: Mapped[int | None] = mapped_column(SmallInteger)
    winger: Mapped[int | None] = mapped_column(SmallInteger)
    winger_max: Mapped[int | None] = mapped_column(SmallInteger)
    passing: Mapped[int | None] = mapped_column(SmallInteger)
    passing_max: Mapped[int | None] = mapped_column(SmallInteger)
    scoring: Mapped[int | None] = mapped_column(SmallInteger)
    scoring_max: Mapped[int | None] = mapped_column(SmallInteger)
    set_pieces: Mapped[int | None] = mapped_column(SmallInteger)
    set_pieces_max: Mapped[int | None] = mapped_column(SmallInteger)
    # `IsMaxReached` de CHPP: la habilidad ya tocó su techo y no subirá más,
    # aunque el techo siga oculto. Es un dato aparte del par nivel/techo — se
    # puede saber "ya no crece" sin saber en qué número se paró.
    keeper_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    defending_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    playmaking_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    winger_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    passing_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    scoring_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    set_pieces_max_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    minutes_last_match: Mapped[int] = mapped_column(SmallInteger, default=0)
    # `CanBePromotedIn`: días hasta poder subirlo al primer equipo. Distinto
    # del plazo para no perderlo por edad — ver la migración 0050.
    can_be_promoted_in: Mapped[int | None] = mapped_column(SmallInteger)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_ys_player_time", "youth_player_id", "captured_at"),)


class YouthScoutReport(Base):
    """Lo que dijo el ojeador que trajo a un canterano. Migración 0063.

    Una fila por canterano. El ojeador que lo encontró no cambia nunca;
    `MayUnlock` sí --se apaga cuando esa habilidad se revela--, así que
    `fetched_at` dice de cuándo es la lectura.

    Los comentarios se guardan con su TEXTO literal, no destilados: el dato
    (habilidad, nivel, potencial) ya vive en las fotos, y lo único que existe
    aquí es cómo lo contó el ojeador.
    """

    __tablename__ = "youth_scout_reports"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    youth_player_id: Mapped[int] = mapped_column(
        ForeignKey("youth_players.id"), unique=True, index=True
    )
    scout_id: Mapped[int | None] = mapped_column(BigInteger)
    scout_name: Mapped[str] = mapped_column(String(128), default="")
    scouting_region_id: Mapped[int | None] = mapped_column(Integer)
    comments_json: Mapped[str] = mapped_column(Text, default="[]")
    may_unlock_json: Mapped[str] = mapped_column(Text, default="{}")
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime())


class StaffSnapshot(Base):
    """Staff del club, append-only. `assistant_trainer_levels` (0–10) es la
    pieza que cierra la fórmula de entrenamiento: el nivel de ayudantes leído,
    no supuesto. El nivel del entrenador y su tipo vienen de stafflist.
    """

    __tablename__ = "staff_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())
    assistant_trainer_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    form_coach_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    medic_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    sport_psychologist_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    tactical_assistant_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    financial_director_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    spokesperson_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Del fichero stafflist (entrenador principal)
    trainer_skill_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    trainer_type: Mapped[int] = mapped_column(SmallInteger, default=2)
    trainer_leadership: Mapped[int] = mapped_column(SmallInteger, default=0)
    youth_investment: Mapped[int] = mapped_column(Integer, default=0)
    youth_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    # HL-2xx, 2026-08-12: roster real de stafflist.xml (nombre/tipo/nivel de
    # cada persona), serializado — club.xml ya no trae niveles agregados por
    # puesto (verificado en vivo), así que las 7 columnas de arriba se
    # calculan sumando ESTE roster, no leyendo un campo que ya no existe.
    staff_members_json: Mapped[str | None] = mapped_column(String(4000))
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_staff_team_time", "team_id", "captured_at"),)


class WorldContext(Base):
    """Contexto del mundo POR PAÍS/LIGA — una fila por cada `LeagueID` que
    trae `worlddetails.xml` (2026-08-04: corregido para guardar el
    `<LeagueList>` completo, no solo un país). Es la fuente de verdad de la
    moneda (fin del ×10 a mano) y de la temporada/jornada (arregla HL-007).
    Cada país tiene su PROPIA temporada — verificado en vivo: Suecia
    temporada 95, Colombia 83, Grecia 80 — `season_offset` es la diferencia
    fija respecto a Suecia (la liga "reloj maestro"). Se sobrescribe: es
    estado actual, no histórico.
    """

    __tablename__ = "world_context"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_league_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # Identidad oficial del país dentro de CHPP. `country_code` es ISO 3166-1
    # alpha-2 (CountryCode de worlddetails.xml) y alimenta las banderas de la
    # interfaz sin inferir nada a partir del nombre traducido.
    country_id: Mapped[int] = mapped_column(Integer, default=0, index=True)
    country_code: Mapped[str] = mapped_column(String(2), default="")
    league_name: Mapped[str] = mapped_column(String(128), default="")
    country_name: Mapped[str] = mapped_column(String(128), default="")
    # Las dos selecciones del pais, para saber donde mirar cuando a un jugador
    # de aqui le sube el contador de partidos internacionales. Vienen gratis
    # en worlddetails, que ya se descarga entero.
    national_team_id: Mapped[int] = mapped_column(Integer, default=0)
    u21_team_id: Mapped[int] = mapped_column(Integer, default=0)
    season: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Diferencia fija de temporada respecto a Suecia — informativo (la
    # aritmética de `season_at` en player_balance.py solo necesita `season`
    # actual, no este offset), pero documenta POR QUÉ un país no comparte
    # numeración de temporada con otro.
    season_offset: Mapped[int] = mapped_column(SmallInteger, default=0)
    match_round: Mapped[int] = mapped_column(SmallInteger, default=0)
    match_rounds_left: Mapped[int] = mapped_column(SmallInteger, default=0)
    number_of_levels: Mapped[int] = mapped_column(SmallInteger, default=0)
    # 1 = masculino, 2 = femenino. Los premios Femme son 25% menores.
    league_system_id: Mapped[int] = mapped_column(SmallInteger, default=1)
    currency_name: Mapped[str] = mapped_column(String(16), default="")
    currency_rate: Mapped[float] = mapped_column(Float, default=1.0)
    training_date: Mapped[datetime | None] = mapped_column(UtcDateTime())
    # Momento oficial de la actualización económica semanal de esta liga.
    # Es el ancla para contar salarios por cruces reales, no por bloques de
    # siete días desde la compra.
    economy_date: Mapped[datetime | None] = mapped_column(UtcDateTime())
    cup_match_date: Mapped[datetime | None] = mapped_column(UtcDateTime())
    series_match_date: Mapped[datetime | None] = mapped_column(UtcDateTime())
    refreshed_at: Mapped[datetime | None] = mapped_column(UtcDateTime())


class WorldCup(Base):
    """Copas de UN país, de `worlddetails.xml` (`<League><Cups><Cup>`) —
    2026-08-04, pedido explícitamente para reemplazar el `CUP_LEVEL_NAMES`
    hardcodeado de `cup.py`, que además tenía un bug real: keyeaba solo por
    `CupLevel` (1-5 supuestos) cuando Hattrick en realidad usa `CupLevel` +
    `CupLevelIndex` para distinguir las copas paralelas de un mismo nivel
    (en Colombia, nivel 2 tiene 3 copas: Esmeralda/Rubí/Zafiro, índices
    1/2/3) — sin el índice, las tres colapsaban al mismo nombre. Se
    sobrescribe cada sync: estado actual, no histórico."""

    __tablename__ = "world_cups"
    __table_args__ = (
        UniqueConstraint(
            "ht_league_id",
            "cup_league_level",
            "cup_level",
            "cup_level_index",
            name="uq_world_cup_key",
        ),
    )
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_league_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ht_cup_id: Mapped[int] = mapped_column(BigInteger, default=0)
    cup_name: Mapped[str] = mapped_column(String(128), default="")
    cup_league_level: Mapped[int] = mapped_column(SmallInteger, default=0)
    cup_level: Mapped[int] = mapped_column(SmallInteger)
    cup_level_index: Mapped[int] = mapped_column(SmallInteger)
    # Ronda oficial de ESTA copa y cuántas faltan, no la jornada de Liga.
    # worlddetails.xml las entrega dentro de cada <Cups><Cup>.
    match_round: Mapped[int] = mapped_column(SmallInteger, default=-1)
    match_rounds_left: Mapped[int] = mapped_column(SmallInteger, default=0)


class SkillUp(Base):
    """Subida de habilidad CONFIRMADA por Hattrick (trainingevents). A
    diferencia de detectar cruces comparando snapshots, esto es evidencia
    directa: Hattrick dice quién subió qué y cuándo. Alimenta la calibración
    de experiencia y valida la fórmula de entrenamiento.

    Único por (jugador, habilidad, nivel nuevo): un mismo pop no se cuenta dos
    veces aunque se sincronice el fichero varias veces.
    """

    __tablename__ = "skill_ups"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, index=True)
    skill_id: Mapped[int] = mapped_column(SmallInteger)
    old_level: Mapped[int] = mapped_column(SmallInteger)
    new_level: Mapped[int] = mapped_column(SmallInteger)
    season: Mapped[int] = mapped_column(SmallInteger)
    match_round: Mapped[int] = mapped_column(SmallInteger)
    day_number: Mapped[int] = mapped_column(SmallInteger, default=0)
    recorded_at: Mapped[datetime | None] = mapped_column(UtcDateTime())

    __table_args__ = (
        Index("ix_skillup_unique", "ht_player_id", "skill_id", "new_level", unique=True),
    )


class DismissedInsight(Base):
    """Alerta que el usuario archivó con la X — 2026-08-16.

    Las alertas no existen como filas: `domain.engines.insights` las deriva de
    los datos en cada petición. Lo que se guarda aquí es la decisión de
    archivarla, más una copia del texto archivado para que el buzón pueda
    mostrarlo aunque la condición que la disparó ya no se cumpla.

    `fingerprint` (hash de severidad+título+detalle+acción) es lo que impide
    que archivar sea silenciar: si la alerta se regenera con otro contenido —
    otra cifra, otra severidad — la huella deja de coincidir y vuelve sola a
    la lista activa.
    """

    __tablename__ = "dismissed_insights"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(String(1000))
    action: Mapped[str] = mapped_column(String(500), default="")
    module: Mapped[str] = mapped_column(String(64), default="")
    dismissed_at: Mapped[datetime] = mapped_column(UtcDateTime())

    __table_args__ = (UniqueConstraint("team_id", "key", name="uq_dismissed_insight"),)


class MatchWeather(Base):
    """Pronóstico del clima de la región donde se juega un partido — 2026-08-18.

    Hattrick decide el clima por REGIÓN y solo lo publica a un día vista:
    `regiondetails.xml` trae el de hoy y el de mañana, y nada más. Por eso
    esta tabla guarda los dos números junto con `forecast_taken_at`, la
    `FetchedDate` del propio fichero: sin saber qué día era "hoy" cuando se
    pidió, los dos valores no se pueden situar en el calendario y un
    pronóstico de anteayer se leería como el de esta tarde.

    Una fila por partido: se reescribe en cada sync mientras el partido siga
    por jugarse, porque el pronóstico cambia de un día para otro.
    """

    __tablename__ = "match_weather"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    # El estadio donde se juega, que es de dónde sale la región: en un partido
    # de visitante es la del rival, no la propia.
    venue_ht_team_id: Mapped[int] = mapped_column(BigInteger)
    ht_region_id: Mapped[int] = mapped_column(BigInteger)
    region_name: Mapped[str] = mapped_column(String(128), default="")
    # -1 = CHPP no lo trajo. 0 lluvia, 1 nublado, 2 parcialmente nublado,
    # 3 soleado — ver `domain.engines.weather`.
    weather_today: Mapped[int] = mapped_column(SmallInteger, default=-1)
    weather_tomorrow: Mapped[int] = mapped_column(SmallInteger, default=-1)
    # Reloj del SERVIDOR de Hattrick, no el nuestro: es el que define qué día
    # es "hoy" para los dos campos de arriba.
    forecast_taken_at: Mapped[datetime] = mapped_column(UtcDateTime())
    captured_at: Mapped[datetime] = mapped_column(UtcDateTime())


class GuestbookEntry(Base):
    """Una firma del libro de visitas.

    2026-09-05, pedido por el usuario: un sitio donde la gente que usa HT Lens
    deje un mensaje, y de donde salgan las funcionalidades siguientes.

    Se guarda el `user_id` de quien firma --el libro pide sesión, así que nadie
    escribe de forma anónima-- pero lo que se ENSEÑA es el nombre del club y la
    liga, no el nombre de la cuenta: en Hattrick uno se conoce por su equipo.

    El nombre del club se copia en la fila en vez de leerse del equipo cada
    vez. Un club puede cambiar de nombre, y entonces una firma de hace un año
    aparecería atribuida a un club que no existía cuando se escribió.

    `hidden` es la moderación: una firma no se borra, se esconde. Borrarla
    dejaría a quien la escribió sin saber que pasó, y a nosotros sin saber qué
    había cuando alguien pregunte.
    """

    __tablename__ = "guestbook_entries"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    #: Cómo se llamaba el club al firmar. Vacío si quien firma aún no ha
    #: sincronizado ninguno.
    team_name: Mapped[str] = mapped_column(String(120), default="")
    country: Mapped[str] = mapped_column(String(64), default="")
    message: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)


class TrainingMatch(Base):
    """Un partido ajeno, recogido UNA vez para entrenar el modelo de predicción.

    2026-09-05. Vive en su propia tabla y no en `matches` por dos motivos que
    no son de gusto:

    - `matches` son TUS partidos, y se reescriben en cada sincronización. Estos
      no se vuelven a pedir: son material de entrenamiento, no estado del club.
    - Se recogen una vez y se refrescan como mucho una vez al año, avisando al
      autor. Mezclarlos obligaría a distinguirlos en cada consulta que ya
      existe.

    Se guarda PLANO --los dos lados en la misma fila-- porque es una tabla de
    modelado: cada fila es una observación y las columnas son sus variables.
    Normalizarla en dos filas obligaría a unirla consigo misma para todo.

    Sólo entran partidos oficiales (liga, promoción y copa). Un torneo o un
    amistoso se juegan con suplentes y no dicen nada de la fuerza del equipo.
    """

    __tablename__ = "training_matches"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    match_type: Mapped[int] = mapped_column(SmallInteger, index=True)
    played_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), index=True)

    home_team_id: Mapped[int] = mapped_column(BigInteger, index=True)
    away_team_id: Mapped[int] = mapped_column(BigInteger, index=True)
    home_goals: Mapped[int] = mapped_column(SmallInteger)
    away_goals: Mapped[int] = mapped_column(SmallInteger)

    home_midfield: Mapped[int] = mapped_column(SmallInteger)
    home_left_def: Mapped[int] = mapped_column(SmallInteger)
    home_central_def: Mapped[int] = mapped_column(SmallInteger)
    home_right_def: Mapped[int] = mapped_column(SmallInteger)
    home_left_att: Mapped[int] = mapped_column(SmallInteger)
    home_central_att: Mapped[int] = mapped_column(SmallInteger)
    home_right_att: Mapped[int] = mapped_column(SmallInteger)
    home_sp_def: Mapped[int] = mapped_column(SmallInteger)
    home_sp_att: Mapped[int] = mapped_column(SmallInteger)
    home_tactic_type: Mapped[int] = mapped_column(SmallInteger, default=0)
    home_tactic_skill: Mapped[int] = mapped_column(SmallInteger, default=0)

    away_midfield: Mapped[int] = mapped_column(SmallInteger)
    away_left_def: Mapped[int] = mapped_column(SmallInteger)
    away_central_def: Mapped[int] = mapped_column(SmallInteger)
    away_right_def: Mapped[int] = mapped_column(SmallInteger)
    away_left_att: Mapped[int] = mapped_column(SmallInteger)
    away_central_att: Mapped[int] = mapped_column(SmallInteger)
    away_right_att: Mapped[int] = mapped_column(SmallInteger)
    away_sp_def: Mapped[int] = mapped_column(SmallInteger)
    away_sp_att: Mapped[int] = mapped_column(SmallInteger)
    away_tactic_type: Mapped[int] = mapped_column(SmallInteger, default=0)
    away_tactic_skill: Mapped[int] = mapped_column(SmallInteger, default=0)

    #: Cuándo se recogió. De aquí sale el aviso anual de refresco.
    collected_at: Mapped[datetime] = mapped_column(UtcDateTime())
