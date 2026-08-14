"""SQLAlchemy models — núcleo del sync. Ver docs/02-modelo-datos.md para el modelo completo.

Nota particionado: en PostgreSQL, player_snapshots es RANGE(captured_at) con PK
física (id, captured_at) — eso vive en la migración (raw SQL). El ORM mapea id
como PK lógica; con sqlite (tests) funciona el autoincrement vía variant.
"""
from datetime import datetime

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
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PKBigInt = BigInteger().with_variant(Integer(), "sqlite")


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
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CHPPToken(Base):
    __tablename__ = "chpp_tokens"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    oauth_token_enc: Mapped[bytes] = mapped_column(LargeBinary)      # Fernet
    oauth_secret_enc: Mapped[bytes] = mapped_column(LargeBinary)     # Fernet
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


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_player_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(64))
    last_name: Mapped[str] = mapped_column(String(64))
    left_team_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Hechos de una vez, no snapshots: de transfersteam.xml (precio real de
    # compra, HL-15x) y playerdetails.xml (club madre) — no hay "sync sync_id"
    # que les corresponda, así que viven en la identidad, no en player_snapshots.
    purchase_price: Mapped[int | None] = mapped_column(Integer)
    purchased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # HL-161: cuando ni transfersteam.xml ni transfersplayer.xml traen una
    # compra real (p. ej. el jugador llegó con el equipo antes de que
    # existiera Hattrick Manager, o CHPP no guarda tan atrás), el usuario
    # puede escribirlo a mano. Se prioriza SIEMPRE el dato real
    # (`purchase_price`) sobre el manual — nunca al revés.
    purchase_price_manual: Mapped[int | None] = mapped_column(Integer)
    purchased_at_manual: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # HL-161: precio real de venta, de transfersteam.xml (TransferType="S",
    # vendedor == nosotros) — mismo fichero y mecanismo que purchase_price,
    # nunca se sobrescribe una vez vendido (un jugador solo se vende una
    # vez desde este club).
    sale_price: Mapped[int | None] = mapped_column(Integer)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    # HL-15x: NativeLeagueName de playerdetails.xml — hecho de una vez, como
    # mother_club_team_name. No hace falta tabla país→nombre: CHPP ya da el
    # texto real.
    native_league_name: Mapped[str | None] = mapped_column(String(128))
    # HL-15x #93: la app SUGIERE el momento de carrera (career_stage_engine),
    # el usuario CONFIRMA — nunca se sobreescribe solo. NULL = sin confirmar
    # todavía, se muestra la sugerencia.
    confirmed_career_stage: Mapped[str | None] = mapped_column(String(32))
    confirmed_career_stage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    games_played_for_us_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "Backfill de un jugador máximo una vez [por vuelta al sync]" — igual
    # que `enrichment_attempted`/`tsi_at_purchase_attempted`: cuándo se
    # revisó por última vez transfersplayer.xml buscando una reventa nueva
    # tras nuestra venta. A diferencia de esos dos flags, SÍ puede volver a
    # dar resultado en el futuro (una reventa puede pasar en cualquier
    # momento), así que esto es una marca de tiempo para espaciar los
    # reintentos automáticos, no un "ya se intentó, nunca más".
    previous_club_bonus_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Sync(Base):
    __tablename__ = "syncs"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    kind: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(String(2000))


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_pmr_player_match", "player_id", "ht_match_id", unique=True),
    )


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
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
    resale_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    buyer_team_id: Mapped[int] = mapped_column(BigInteger)
    seller_team_id: Mapped[int] = mapped_column(BigInteger)
    games_played_with_us: Mapped[int] = mapped_column(SmallInteger)
    pct_applied: Mapped[float] = mapped_column(Float)
    amount: Mapped[int] = mapped_column(BigInteger)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EconomySnapshot(Base):
    """Append-only. 1 fila por cambio real (diffing por content_hash)."""
    __tablename__ = "economy_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cash: Mapped[int] = mapped_column(BigInteger)
    expected_cash: Mapped[int] = mapped_column(BigInteger)
    sponsors_popularity: Mapped[int] = mapped_column(SmallInteger)
    supporters_popularity: Mapped[int] = mapped_column(SmallInteger)
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
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    training_type: Mapped[int] = mapped_column(SmallInteger)
    training_level: Mapped[int] = mapped_column(SmallInteger)
    new_training_level: Mapped[int] = mapped_column(SmallInteger)
    stamina_part: Mapped[int] = mapped_column(SmallInteger)
    last_training_type: Mapped[int] = mapped_column(SmallInteger)
    last_training_level: Mapped[int] = mapped_column(SmallInteger)
    last_stamina_part: Mapped[int] = mapped_column(SmallInteger)
    trainer_ht_id: Mapped[int] = mapped_column(BigInteger)
    trainer_name: Mapped[str] = mapped_column(String(128))
    morale: Mapped[int] = mapped_column(SmallInteger, default=-1)
    self_confidence: Mapped[int] = mapped_column(SmallInteger, default=-1)
    formation_xp_json: Mapped[str | None] = mapped_column(String(1000))
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_ts_team_time", "team_id", "captured_at"),)


class PlayerSnapshot(Base):
    __tablename__ = "player_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
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
    last_match_played_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
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
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
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
    sold_terraces: Mapped[int] = mapped_column(Integer, default=0)
    sold_basic: Mapped[int] = mapped_column(Integer, default=0)
    sold_roof: Mapped[int] = mapped_column(Integer, default=0)
    sold_vip: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[int] = mapped_column(Integer, default=0)

    @property
    def sold_total(self) -> int:
        return self.sold_terraces + self.sold_basic + self.sold_roof + self.sold_vip


class Match(Base):
    """Immutable match record. DATABASE.md: `matches`."""
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    ht_match_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
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
    submitted_orders_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
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
    submitted_ratings_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


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
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sold_for: Mapped[int | None] = mapped_column(Integer)
    current_team_name: Mapped[str | None] = mapped_column(String(128))
    current_tsi: Mapped[int | None] = mapped_column(Integer)
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
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
    minutes_last_match: Mapped[int] = mapped_column(SmallInteger, default=0)
    content_hash: Mapped[bytes] = mapped_column(LargeBinary(32))

    __table_args__ = (Index("ix_ys_player_time", "youth_player_id", "captured_at"),)


class StaffSnapshot(Base):
    """Staff del club, append-only. `assistant_trainer_levels` (0–10) es la
    pieza que cierra la fórmula de entrenamiento: el nivel de ayudantes leído,
    no supuesto. El nivel del entrenador y su tipo vienen de stafflist.
    """
    __tablename__ = "staff_snapshots"
    id: Mapped[int] = mapped_column(PKBigInt, primary_key=True)
    sync_id: Mapped[int] = mapped_column(ForeignKey("syncs.id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
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
    league_name: Mapped[str] = mapped_column(String(128), default="")
    country_name: Mapped[str] = mapped_column(String(128), default="")
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
    training_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cup_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    series_match_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
            "ht_league_id", "cup_league_level", "cup_level", "cup_level_index",
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
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_skillup_unique", "ht_player_id", "skill_id", "new_level", unique=True),
    )
