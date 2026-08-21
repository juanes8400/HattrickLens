"""PlayerBalanceQueryService — HL-161.

Junta todo lo que hace falta para el saldo neto de cada jugador que ha
pasado por el club (siga o no en la plantilla): precio de compra (real o
manual), historial de salario, intentos de venta, precio de venta real, la
comisión del agente, y su parte del ingreso por reventa futura de origen
desconocido — y llama al motor de dominio (`player_balance.py`) para
calcular el resultado. Nunca inventa un valor de mercado para un jugador
que sigue sin venderse.
"""
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import season_for_datetime, season_week_for_datetime
from app.domain.engines.player_balance import (
    YOUTH_PROMOTION_COST,
    PlayerBalance,
    PlayerTransferRecord,
    SalarySnapshot,
    compute_balance,
    salary_at,
    weeks_owned,
)
from app.domain.value_objects.ht_constants import (
    PLAYER_AGREEABILITY,
    SKILL_LABELS,
    SPECIALTIES,
    training_skill_name,
)
from app.infrastructure.db import models as m

# Habilidad más alta de un jugador en el momento de la venta — pedido
# explícitamente SIN Balón Parado (no es una habilidad "de campo" como las
# demás, y el usuario la excluyó a propósito).
_TOP_SKILL_FIELDS = ("keeper", "defending", "playmaking", "winger", "passing", "scoring")

# Cubos de edad para el desglose "por Edad" — rangos exactos pedidos por el
# usuario 2026-08-04 (17 a 18 años = 17:000 a 18:111, etc.).
_AGE_BUCKETS: list[tuple[int, str]] = [
    (18, "17–18"), (21, "19–21"), (24, "22–24"), (28, "25–28"), (31, "29–31"),
]
_AGE_BUCKET_OVERFLOW = "32+"
_UNKNOWN_AGE = "Edad desconocida"
_UNKNOWN_TOP_SKILL = "?"  # pedido explícitamente 2026-08-04
_UNKNOWN_SEASON = "Temporada desconocida"
_AGE_LABELS_ORDER = [label for _, label in _AGE_BUCKETS] + [_AGE_BUCKET_OVERFLOW, _UNKNOWN_AGE]


def _age_bucket(age_years: int) -> str:
    for max_age, label in _AGE_BUCKETS:
        if age_years <= max_age:
            return label
    return _AGE_BUCKET_OVERFLOW


def _skill_val(snap: "m.PlayerSnapshot | None", field: str) -> int | str:
    """Habilidad AL ENTRAR/AL SALIR (2026-08-05, tabla Detalle de 43
    columnas) — nunca reconstruida hacia atrás/adelante como la edad: a
    diferencia del tiempo, entrenar sí cambia una habilidad, así que sin un
    `player_snapshot` real cerca de la fecha no hay forma honesta de
    saberla ("?")."""
    if snap is None:
        return "?"
    v = getattr(snap, field, None)
    return v if v is not None else "?"


def _top_skill_label(snap: "m.PlayerSnapshot") -> str | None:
    values = {f: getattr(snap, f) for f in _TOP_SKILL_FIELDS if getattr(snap, f) is not None}
    if not values:
        return None
    best = max(values, key=lambda f: values[f])
    return SKILL_LABELS[best]


def _split_12h(hour: int) -> tuple[int, str]:
    period = "a.m." if hour < 12 else "p.m."
    return (hour % 12 or 12), period


def _format_hour_range(start: int, end: int) -> str:
    """"14-16" no dice nada de un vistazo — pedido explícitamente 2026-08-03
    en formato de 12 horas ("2:00 a 4:00 p.m."). Un solo sufijo am/pm cuando
    los dos extremos caen en el mismo periodo (el caso normal); los dos
    cuando cruza el mediodía o la medianoche (ej. "10:00 a.m. a 12:00 p.m.")."""
    start_h12, start_period = _split_12h(start)
    end_h12, end_period = _split_12h(end % 24)
    if start_period == end_period:
        return f"{start_h12}:00 a {end_h12}:00 {end_period}"
    return f"{start_h12}:00 {start_period} a {end_h12}:00 {end_period}"


def _bid_hour_bucket(sold_at: datetime) -> str:
    """Bloques de 2 horas del día en que se cerró la puja — pedido
    explícitamente 2026-08-03. La hora es la que trae CHPP en `Deadline` tal
    cual (sin convertir zona horaria, igual que el resto de la app trata
    `sold_at`/`purchased_at`)."""
    start = (sold_at.hour // 2) * 2
    return _format_hour_range(start, start + 2)


_BID_HOUR_LABELS_ORDER = [_format_hour_range(h, h + 2) for h in range(0, 24, 2)]


@dataclass
class SalaryWeekSegment:
    """Tramo de semanas consecutivas con el mismo sueldo, en la misma
    temporada — pedido explícitamente para la ficha de ex-jugador ("11
    semanas con X sueldo en temporada W, 4 semanas con Y sueldo en
    temporada Z") en vez de un solo total acumulado."""
    weeks: int
    salary: int
    season: str


@dataclass
class ListingAttemptRow:
    """Un intento de venta enumerado (no solo contado) — pedido
    explícitamente 2026-08-08. Solo cubre intentos detectados desde que
    existe `player_listing_attempts` (0038); anteriores a esa fecha siguen
    solo en el contador `listing_count`."""
    highest_bid: int | None
    detected_at: str


@dataclass
class PlayerBalanceRow:
    ht_player_id: int
    name: str
    is_academy_graduate: bool
    # Lo que costó subirlo de la cantera, en moneda local. 0 para quien no vino
    # de ahí. Es el "precio de compra" de un canterano: sin él, su saldo salía
    # inflado por ese importe.
    promotion_cost: int
    is_purchase_price_manual: bool
    purchase_price: int | None
    purchased_at: str | None
    sale_price: int | None
    sold_at: str | None
    salary_total: int
    salary_breakdown: list[SalaryWeekSegment]
    listing_count: int
    listing_attempts: list[ListingAttemptRow]
    listing_cost: int
    agent_pct: float | None
    # HL-161, 2026-08-14: comisión de club anterior EXACTA — suma de
    # `PreviousClubBonus.amount` (convertida) para este jugador, si el club
    # al que se lo vendimos ya lo revendió. 0.0 si todavía no hay ninguna
    # reventa detectada (nunca una aproximación repartida entre candidatos:
    # ver `previous_club_bonus.py`, reemplaza por completo el reparto
    # heurístico que vivía en `resale_bonus.py`).
    resale_bonus_share: float
    saldo: float | None
    is_sold: bool
    training_at_sale: str | None
    # 2026-08-04: filtro general de temporadas, pedido explícitamente —
    # mismo criterio que el desglose "por Temporada" (season_at).
    season_at_sale: str | None
    # La SEMANA de temporada (1-16) de cada movimiento, sin la temporada
    # delante: la cascada de Transferencias agrupa todas las semanas 05 de
    # cualquier temporada en la misma columna. `None` cuando no se puede
    # situar la fecha (sin WorldContext del país, o movimiento sin fecha).
    week_at_sale: int | None
    week_at_purchase: int | None
    # Reutilizados por el filtro de temporadas para recalcular los desgloses
    # "por habilidad más alta"/"por hora de puja" sobre el subconjunto
    # filtrado sin tener que rehacer la consulta — mismo criterio que
    # `by_top_skill` (sin Balón Parado) y `by_bid_hour`.
    top_skill_at_sale: str | None
    bid_hour_at_sale: str | None
    # HL-161: columnas de la tabla "Detalle" que faltaban frente al Excel
    # del usuario (pedido 2026-08-04) — "?" en vez de None/vacío cuando de
    # verdad no hay forma de saberlo, para que se note en la tabla que es
    # un hueco y no un cero.
    native_country: str
    native_country_code: str | None
    character: str
    specialty: str
    tsi_at_purchase: int | str
    tsi_at_sale: int | str
    delta_tsi: int | str
    commission_amount: float | str
    roi_pct: float | str
    destination_country: str
    destination_country_code: str | None
    # HL-161: edad en la venta como número decimal (años + días/112) — para
    # graficar (color por edad, pedido 2026-08-04), no para tabla. Mismo
    # criterio que el desglose "por Edad": snapshot real si existe, si no
    # el backfill reconstruido; "?" solo si de verdad no hay ninguno.
    age_at_sale: float | str
    # 2026-08-05: tabla "Detalle" de 43 columnas, pedida explícitamente tras
    # confirmar la fórmula de ROI. Edad de compra: mismo criterio que
    # age_at_sale (snapshot real primero, backfill reconstruido después),
    # ancla en `purchased_at`.
    age_at_purchase: float | str
    # Habilidades AL ENTRAR (snapshot real más cercano a purchased_at, en o
    # después — nunca reconstruidas: a diferencia de la edad, no son función
    # pura del tiempo, entrenar sí las cambia. "?" si nunca hubo un
    # player_snapshot cerca de la compra, p. ej. jugadores del backfill
    # histórico comprados antes de que esta app existiera).
    experience_at_purchase: int | str
    leadership_at_purchase: int | str
    form_at_purchase: int | str
    stamina_at_purchase: int | str
    keeper_at_purchase: int | str
    defending_at_purchase: int | str
    playmaking_at_purchase: int | str
    winger_at_purchase: int | str
    passing_at_purchase: int | str
    scoring_at_purchase: int | str
    set_pieces_at_purchase: int | str
    # Habilidades AL SALIR (snapshot real más cercano a la venta/salida, en o
    # antes) — mismo criterio, sin Liderazgo (no se pidió "al salir").
    experience_at_sale: int | str
    form_at_sale: int | str
    stamina_at_sale: int | str
    keeper_at_sale: int | str
    defending_at_sale: int | str
    playmaking_at_sale: int | str
    winger_at_sale: int | str
    passing_at_sale: int | str
    scoring_at_sale: int | str
    set_pieces_at_sale: int | str
    days_since_purchase: int | str
    saldo_per_delta_tsi: float | str
    # 2026-08-05, pedido explícitamente: un jugador que sale de la
    # plantilla SIN transferencia real en transfersteam.xml fue despedido —
    # cuenta como venta a $0 (no "sigue en la plantilla" ni "desconocido").
    # Este flag distingue esa venta sintética de una venta real en la UI.
    is_departure_without_sale: bool
    # False cuando de ese jugador no se guardo NUNCA un salario: solo se
    # conoce por el historial de transferencias, asi que su coste de
    # salarios es 0 por ignorancia y el saldo sale mejor de lo que fue. La
    # tabla pone «?» en vez de un cero que parece calculado.
    salary_known: bool = True


def _build_breakdowns(sold_rows: list[PlayerBalanceRow]) -> dict[str, dict[str, float]]:
    """Repartos "por Entrenamiento / Temporada / Edad / Habilidad más alta /
    Hora de puja" a partir de filas YA construidas — reutilizado tanto para
    el total (todas las temporadas) como, con el filtro general de
    temporadas activo (pedido explícitamente 2026-08-04), para el
    subconjunto de una sola temporada. Cada fila ya trae sus etiquetas
    calculadas con el mismo criterio de siempre, así que aquí solo se
    agrupa y se suma — nada de lógica de negocio duplicada."""
    by_training: dict[str, float] = {}
    by_season: dict[str, float] = {}
    by_age: dict[str, float] = {}
    by_top_skill: dict[str, float] = {}
    by_bid_hour: dict[str, float] = {}
    for r in sold_rows:
        if not r.is_sold or r.saldo is None:
            continue
        training_label = r.training_at_sale or "Entrenamiento desconocido"
        by_training[training_label] = by_training.get(training_label, 0.0) + r.saldo
        season_label = r.season_at_sale or _UNKNOWN_SEASON
        by_season[season_label] = by_season.get(season_label, 0.0) + r.saldo
        age_label = (
            _age_bucket(int(r.age_at_sale)) if isinstance(r.age_at_sale, float) else _UNKNOWN_AGE
        )
        by_age[age_label] = by_age.get(age_label, 0.0) + r.saldo
        skill_label = r.top_skill_at_sale or _UNKNOWN_TOP_SKILL
        by_top_skill[skill_label] = by_top_skill.get(skill_label, 0.0) + r.saldo
        if r.bid_hour_at_sale:
            by_bid_hour[r.bid_hour_at_sale] = by_bid_hour.get(r.bid_hour_at_sale, 0.0) + r.saldo

    return {
        "by_training_type": {k: round(v, 2) for k, v in by_training.items()},
        "by_season": {
            k: round(by_season[k], 2)
            for k in sorted(
                by_season,
                key=lambda s: (s == _UNKNOWN_SEASON, s.removeprefix("Temporada ").zfill(6)),
            )
        },
        "by_age_bucket": {k: round(by_age[k], 2) for k in _AGE_LABELS_ORDER if k in by_age},
        "by_top_skill": {
            **{
                SKILL_LABELS[f]: round(by_top_skill[SKILL_LABELS[f]], 2)
                for f in _TOP_SKILL_FIELDS if SKILL_LABELS[f] in by_top_skill
            },
            **(
                {_UNKNOWN_TOP_SKILL: round(by_top_skill[_UNKNOWN_TOP_SKILL], 2)}
                if _UNKNOWN_TOP_SKILL in by_top_skill else {}
            ),
        },
        "by_bid_hour": {
            k: round(by_bid_hour[k], 2) for k in _BID_HOUR_LABELS_ORDER if k in by_bid_hour
        },
    }


@dataclass
class PlayerBalanceResponse:
    team_name: str
    currency: str
    players: list[PlayerBalanceRow]
    total_saldo: float
    unknown_purchase_count: int
    by_training_type: dict[str, float]
    by_season: dict[str, float]
    by_age_bucket: dict[str, float]
    by_top_skill: dict[str, float]
    by_bid_hour: dict[str, float]
    # HL-161, 2026-08-04: <Stats> de transfersteam.xml — TODA la historia
    # de compraventas del equipo (no solo lo que esta app pudo reconstruir
    # jugador por jugador), pedido explícitamente para los KPI de
    # "Resumen". Ver `Team.transfer_total_*` en sync_team.py.
    transfer_total_buys: float
    transfer_total_sales: float
    transfer_number_buys: int
    transfer_number_sales: int


class PlayerBalanceQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self,
        team_id: int,
        season: str | None = None,
    ) -> PlayerBalanceResponse | None:
        """`season`: filtro general de temporadas, pedido explícitamente
        2026-08-04 — `None`/"all" trae todo (comportamiento de siempre); un
        valor real de `by_season` (p. ej. "Temporada 83") limita "Detalle" y
        los desgloses NO-temporada a las ventas cerradas esa temporada. Los
        KPI de "Resumen" (transfer_total_*) quedan fuera a propósito: son un
        agregado de TODA la historia que entrega Hattrick, no algo que se
        pueda recortar por temporada sin datos por transacción que Hattrick
        no da."""
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        # CHPP devuelve todos los importes reales (compra, venta, salario,
        # ingreso por venta de jugadores) en la moneda base del juego, no en
        # la moneda local del equipo — hace falta dividir por la tasa del
        # país (Colombia = 10) igual que ya hace squad.py con purchase_price
        # y salary. Los precios ESCRITOS A MANO no se tocan: el usuario ya
        # los teclea en su propia moneda.
        rate = team.currency_rate or 1.0

        def conv(v: int | None) -> int | None:
            return None if v is None else int(round(v / rate))

        # Todos los que han pasado por el club, sigan o no — append-only,
        # nunca se borran (ver `Player.left_team_at`).
        players = list(
            (
                await self._s.execute(select(m.Player).where(m.Player.team_id == team_id))
            ).scalars()
        )
        if not players:
            return PlayerBalanceResponse(
                team_name=team.name, currency=team.currency_name,
                players=[], total_saldo=0.0, unknown_purchase_count=0,
                by_training_type={}, by_season={}, by_age_bucket={}, by_top_skill={},
                by_bid_hour={},
                transfer_total_buys=conv(team.transfer_total_buys) or 0,
                transfer_total_sales=conv(team.transfer_total_sales) or 0,
                transfer_number_buys=team.transfer_number_buys,
                transfer_number_sales=team.transfer_number_sales,
            )

        # "Canterano" (CORRECCIÓN 2026-08-04, pedido explícitamente): antes
        # se miraba si el jugador pasó por `YouthPlayer`/`FormerYouthPlayer`
        # — el escaneo de cantera de esta app, que solo cubre jugadores
        # vistos DESDE que existe esa sincronización. El backfill histórico
        # de transferencias trae ~470 jugadores que nunca pasaron por ahí,
        # así que ese criterio los daba todos por "comprados" aunque de
        # verdad fueran de tu cantera. El dato real de Hattrick es
        # `MotherClub/TeamID == este equipo` (de playerdetails.xml, ver
        # `_apply_player_enrichment`) — funciona para cualquier jugador, sin
        # importar cuándo pasó por el club.

        # Historial de salario por jugador — lo que de verdad se sincronizó,
        # con huecos; el motor de dominio extrapola.
        player_ids = [p.id for p in players]
        snapshots = list(
            (
                await self._s.execute(
                    select(m.PlayerSnapshot)
                    .where(m.PlayerSnapshot.player_id.in_(player_ids))
                    .order_by(m.PlayerSnapshot.captured_at)
                )
            ).scalars()
        )
        salary_by_player: dict[int, list[SalarySnapshot]] = {}
        snapshots_by_player: dict[int, list[m.PlayerSnapshot]] = {}
        for snap in snapshots:
            salary_by_player.setdefault(snap.player_id, []).append(
                SalarySnapshot(captured_at=snap.captured_at, salary=conv(snap.salary) or 0)
            )
            snapshots_by_player.setdefault(snap.player_id, []).append(snap)

        # Intentos de venta enumerados — pedido explícitamente 2026-08-08,
        # solo cubre lo detectado desde que existe player_listing_attempts
        # (0038); `listing_count` sigue siendo el total real (puede ser
        # mayor si hubo intentos antes de esa fecha).
        listing_attempt_rows = list(
            (
                await self._s.execute(
                    select(m.PlayerListingAttempt)
                    .where(m.PlayerListingAttempt.player_id.in_(player_ids))
                    .order_by(m.PlayerListingAttempt.detected_at)
                )
            ).scalars()
        )
        listing_attempts_by_player: dict[int, list[ListingAttemptRow]] = {}
        for attempt in listing_attempt_rows:
            listing_attempts_by_player.setdefault(attempt.player_id, []).append(
                ListingAttemptRow(
                    highest_bid=conv(attempt.highest_bid),
                    detected_at=attempt.detected_at.isoformat(),
                )
            )

        def snapshot_at(player_id: int, when: datetime) -> m.PlayerSnapshot | None:
            candidates = [
                s for s in snapshots_by_player.get(player_id, []) if s.captured_at <= when
            ]
            return candidates[-1] if candidates else None

        def snapshot_at_or_after(player_id: int, when: datetime) -> m.PlayerSnapshot | None:
            """Igual que `snapshot_at` pero hacia adelante — para "al
            entrar" (compra): no puede haber `player_snapshots` de ANTES de
            la compra (el jugador no era nuestro todavía), así que el
            candidato correcto es el primero capturado en o después de
            `purchased_at` (2026-08-05, tabla Detalle de 43 columnas)."""
            candidates = [
                s for s in snapshots_by_player.get(player_id, []) if s.captured_at >= when
            ]
            return candidates[0] if candidates else None

        # Temporada de Hattrick en la semana de cada venta (para el desglose
        # "por Temporada"). `worlddetails.xml` trae la temporada
        # de TODOS los países, no una sola — cada uno tiene la SUYA (Suecia
        # 95, Colombia 83, Grecia 80, verificado en vivo). Antes se cogía
        # "la fila de WorldContext más reciente" sin más, lo cual da
        # cualquier país al azar en cuanto hay más de una fila — ahora se
        # filtra por `Team.ht_league_id` (de teamdetails.xml), el país real
        # de ESTE equipo. La fecha ya no se resta contra el instante arbitrario
        # del último sync: se convierte con la regla semanal canónica, anclada
        # en Season + MatchRound. Así funciona igual en pasado, presente y
        # futuro, y una venta posterior por minutos al sync nunca inventa la
        # temporada siguiente.
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None else None
        )
        country_rows = (
            await self._s.execute(
                select(
                    m.WorldContext.country_id,
                    m.WorldContext.country_code,
                    m.WorldContext.country_name,
                ).where(m.WorldContext.country_code != "")
            )
        ).all()
        country_codes_by_id = {
            int(country_id): str(country_code).upper()
            for country_id, country_code, _country_name in country_rows
        }
        country_names_by_id = {
            int(country_id): str(country_name)
            for country_id, _country_code, country_name in country_rows
            if country_name
        }
        country_codes_by_name = {
            str(country_name).strip().casefold(): str(country_code).upper()
            for _country_id, country_code, country_name in country_rows
            if country_name
        }

        def week_number(when: datetime | None) -> int | None:
            """El "05" de 83-05: la semana dentro de la temporada.

            Se descarta la temporada a propósito. La pregunta que responde la
            cascada es "en qué semana del calendario me va bien vender", y
            para eso una venta de 83-05 y otra de 81-05 son la misma semana.
            """
            if when is None:
                return None
            etiqueta = season_week_for_datetime(world, when)
            if not etiqueta or "-" not in etiqueta:
                return None
            try:
                return int(etiqueta.split("-")[1])
            except ValueError:
                return None

        def season_at(when: datetime | None) -> str:
            if when is None:
                return _UNKNOWN_SEASON
            season = season_for_datetime(world, when)
            return _UNKNOWN_SEASON if season is None else f"Temporada {season}"

        # Comisión de club anterior EXACTA — HL-161, 2026-08-14. Reemplaza
        # por completo el reparto heurístico de "reventa futura de origen
        # desconocido" que vivía aquí (repartida proporcionalmente entre
        # candidatos, `resale_bonus.py`, ya eliminado): cada reventa real
        # de un ex-jugador nuestro es una fila propia en
        # `previous_club_bonuses`, calculada partido a partido cuando se
        # detecta (ver `_check_previous_club_bonus` en sync_team.py) — no
        # una aproximación.
        bonus_rows = (
            await self._s.execute(
                select(m.PreviousClubBonus.ht_player_id, m.PreviousClubBonus.amount)
                .where(m.PreviousClubBonus.player_id.in_([p.id for p in players]))
            )
        ).all()
        resale_shares: dict[int, float] = {}
        for ht_player_id, amount in bonus_rows:
            resale_shares[ht_player_id] = resale_shares.get(ht_player_id, 0.0) + (conv(amount) or 0)

        # Entrenamiento activo en la semana de cada venta (para agrupar
        # el saldo por tipo de entrenamiento — pedido explícitamente).
        training_rows = list(
            (
                await self._s.execute(
                    select(m.TrainingSnapshot)
                    .where(m.TrainingSnapshot.team_id == team_id)
                    .order_by(m.TrainingSnapshot.captured_at)
                )
            ).scalars()
        )

        def training_at(when: datetime | None) -> str | None:
            if when is None:
                return None
            candidates = [t for t in training_rows if t.captured_at <= when]
            if not candidates:
                return None
            return training_skill_name(candidates[-1].training_type)

        def salary_breakdown(
            purchased_at: datetime | None, end: datetime | None, history: list[SalarySnapshot],
        ) -> list[SalaryWeekSegment]:
            """Mismo recorrido semana a semana que `_total_salary` en el
            motor de dominio (misma cuenta de semanas, mismo carry-forward),
            pero agrupando tramos consecutivos de igual sueldo Y temporada
            en vez de sumarlos — pedido explícitamente para la ficha de
            ex-jugador en vez de un solo total acumulado."""
            if purchased_at is None or end is None:
                return []
            segments: list[SalaryWeekSegment] = []
            for w in range(weeks_owned(purchased_at, end) + 1):
                week_date = purchased_at + timedelta(weeks=w)
                amount = salary_at(history, week_date)
                season = season_at(week_date)
                if segments and segments[-1].salary == amount and segments[-1].season == season:
                    segments[-1].weeks += 1
                else:
                    segments.append(SalaryWeekSegment(weeks=1, salary=amount, season=season))
            return segments

        rows: list[PlayerBalanceRow] = []
        total_saldo = 0.0
        unknown_count = 0

        for p in players:
            is_academy = (
                p.mother_club_team_id is not None and p.mother_club_team_id == team.ht_team_id
            )
            # p.purchase_price viene crudo de CHPP (moneda base del juego,
            # no la local) — hay que convertirlo. p.purchase_price_manual
            # es lo que el usuario tecleó a mano, ya en su propia moneda.
            purchase_price = conv(p.purchase_price)
            purchased_at = p.purchased_at
            is_manual = False
            if purchase_price is None and p.purchase_price_manual is not None:
                purchase_price = p.purchase_price_manual
                purchased_at = p.purchased_at_manual
                is_manual = True
            sale_price = conv(p.sale_price)

            # 2026-08-05, edge case real encontrado en vivo (jugador
            # 461351045): se vendió en 2022, y volvió a la plantilla en
            # 2026 (recomprado) — `sold_at`/`sale_price` de esa venta VIEJA
            # se quedan escritos para siempre (nunca se borran, ver
            # docstring de arriba), así que sin este chequeo el jugador
            # aparecía como "vendido" con datos de 2022 aunque estuviera
            # sentado hoy mismo en la plantilla. `left_team_at IS NULL` NO
            # sirve como señal aquí: el backfill histórico de
            # transfersteam.xml escribe `sold_at` directamente sin pasar
            # nunca por `mark_departed` (esa venta es de antes de que esta
            # app existiera), así que casi ningún vendido real tiene
            # `left_team_at` puesto — usarlo habría marcado como "activo"
            # a la mayoría de los 410 vendidos de verdad. La señal correcta
            # es un `player_snapshot` (de `players.xml`, solo trae quien
            # está HOY en la plantilla) capturado DESPUÉS de esa salida —
            # si existe, es que volvió a verse en el roster desde entonces.
            last_departure_at = p.sold_at or p.left_team_at
            is_currently_active = last_departure_at is not None and any(
                s.captured_at > last_departure_at for s in snapshots_by_player.get(p.id, [])
            )
            # Un jugador que sale de la plantilla SIN que transfersteam.xml
            # reporte nunca una venta real fue despedido — cuenta como
            # venta a $0, no como "sigue en la plantilla" ni "desconocido".
            # Las reglas actuales de Hattrick no tienen retiro forzoso, así
            # que "salió sin venta" es en la práctica siempre un despido.
            is_departure_without_sale = (
                not is_currently_active and p.sold_at is None and p.left_team_at is not None
            )
            effective_sold_at = (
                None if is_currently_active
                else p.sold_at or (p.left_team_at if is_departure_without_sale else None)
            )
            effective_sale_price = (
                None if is_currently_active
                else sale_price if p.sold_at is not None
                else (0 if is_departure_without_sale else None)
            )

            record = PlayerTransferRecord(
                purchase_price=purchase_price,
                purchased_at=purchased_at,
                is_academy_graduate=is_academy,
                promotion_cost=conv(YOUTH_PROMOTION_COST) if is_academy else 0,
                salary_history=salary_by_player.get(p.id, []),
                listing_count=p.listing_count,
                sale_price=effective_sale_price,
                sold_at=effective_sold_at,
                resale_bonus_share=resale_shares.get(p.ht_player_id, 0.0),
                # SQLite no conserva tzinfo en el viaje de ida y vuelta, así
                # que purchased_at/sold_at llegan naive — as_of debe serlo
                # también o la resta de fechas revienta (naive vs aware).
                as_of=datetime.now(UTC).replace(tzinfo=None),
            )
            balance: PlayerBalance = compute_balance(record)
            salary_breakdown_rows = salary_breakdown(
                purchased_at, effective_sold_at or record.as_of, record.salary_history,
            )

            training_label = training_at(effective_sold_at) if effective_sold_at else None
            # Reutilizado tanto en la fila (para el filtro general de
            # temporadas, pedido explícitamente 2026-08-04) como en el
            # desglose "por Temporada" más abajo — mismo criterio, una sola
            # llamada.
            season_label_for_row = season_at(effective_sold_at) if effective_sold_at is not None else None

            # Edad en la venta (número decimal, años + días/112) — reutilizada
            # tanto en la fila (para graficar) como en el desglose "por Edad"
            # más abajo, así que se calcula UNA vez aquí. Mismo criterio que
            # siempre: snapshot real si existe, si no el backfill.
            at_sale = snapshot_at(p.id, effective_sold_at) if effective_sold_at is not None else None
            age_at_sale: float | str = "?"
            if at_sale is not None:
                age_at_sale = round(at_sale.age_years + at_sale.age_days / 112, 2)
            elif p.sold_at is not None and p.age_years_at_sale is not None and p.age_days_at_sale is not None:
                age_at_sale = round(p.age_years_at_sale + p.age_days_at_sale / 112, 2)

            at_purchase = (
                snapshot_at_or_after(p.id, purchased_at) if purchased_at is not None else None
            )
            nationality_snapshot = at_sale or at_purchase
            if nationality_snapshot is None and snapshots_by_player.get(p.id):
                nationality_snapshot = snapshots_by_player[p.id][-1]
            native_country_code = (
                country_codes_by_id.get(nationality_snapshot.country_id)
                if nationality_snapshot is not None else None
            )
            if native_country_code is None and p.native_country:
                native_country_code = country_codes_by_name.get(
                    p.native_country.strip().casefold()
                )
            native_country = p.native_country or (
                country_names_by_id.get(nationality_snapshot.country_id)
                if nationality_snapshot is not None else None
            )
            destination_country_code = (
                country_codes_by_name.get(p.destination_country.strip().casefold())
                if p.destination_country else None
            )
            age_at_purchase: float | str = "?"
            if at_purchase is not None:
                age_at_purchase = round(at_purchase.age_years + at_purchase.age_days / 112, 2)
            elif p.age_years_at_purchase is not None and p.age_days_at_purchase is not None:
                age_at_purchase = round(p.age_years_at_purchase + p.age_days_at_purchase / 112, 2)

            # Igual que season_label_for_row: se calculan una vez y se
            # reutilizan tanto en la fila (filtro de temporadas) como en los
            # desgloses "por habilidad más alta"/"por hora de puja" más abajo.
            top_skill_for_row = _top_skill_label(at_sale) if at_sale is not None else None
            # Hora de puja: solo tiene sentido si de verdad se cerró una
            # puja real — un despido (`effective_sold_at`) no cuenta.
            bid_hour_for_row = _bid_hour_bucket(p.sold_at) if p.sold_at is not None else None

            days_since_purchase: int | str = "?"
            if purchased_at is not None:
                end_for_days = effective_sold_at or datetime.now(UTC).replace(tzinfo=None)
                days_since_purchase = max((end_for_days - purchased_at).days, 0)

            # HL-161: columnas del Excel del usuario que faltaban (pedido
            # 2026-08-04) — "?" cuando de verdad no hay forma de saberlo,
            # nunca 0 ni un guion que se confunda con un valor real.
            specialty_label = "?"
            if p.specialty is not None:
                specialty_label = SPECIALTIES.get(p.specialty) or "Ninguna"
            character_label = (
                PLAYER_AGREEABILITY.get(p.agreeability, "?")
                if p.agreeability is not None else "?"
            )
            tsi_purchase: int | str = p.tsi_at_purchase if p.tsi_at_purchase is not None else "?"
            tsi_sale: int | str = p.tsi_at_sale if p.tsi_at_sale is not None else "?"
            delta_tsi: int | str = (
                p.tsi_at_sale - p.tsi_at_purchase
                if p.tsi_at_purchase is not None and p.tsi_at_sale is not None else "?"
            )
            commission_amount: float | str = "?"
            if balance.is_sold and effective_sale_price is not None:
                commission_amount = round(effective_sale_price - balance.net_sale_proceeds, 2)
            roi_pct: float | str = "?"
            if balance.saldo is not None:
                total_cost = (balance.purchase_price or 0) + balance.salary_total + balance.listing_cost
                if total_cost > 0:
                    roi_pct = round(balance.saldo / total_cost * 100, 2)
            saldo_per_delta_tsi: float | str = "?"
            if balance.saldo is not None and isinstance(delta_tsi, int) and delta_tsi != 0:
                saldo_per_delta_tsi = round(balance.saldo / delta_tsi, 2)

            rows.append(
                PlayerBalanceRow(
                    ht_player_id=p.ht_player_id,
                    name=f"{p.first_name} {p.last_name}".strip(),
                    is_academy_graduate=is_academy,
                    promotion_cost=conv(YOUTH_PROMOTION_COST) if is_academy else 0,
                    is_purchase_price_manual=is_manual,
                    purchase_price=balance.purchase_price,
                    purchased_at=purchased_at.isoformat() if purchased_at else None,
                    sale_price=effective_sale_price,
                    sold_at=effective_sold_at.isoformat() if effective_sold_at else None,
                    salary_total=balance.salary_total,
                    salary_known=balance.salary_known,
                    salary_breakdown=salary_breakdown_rows,
                    listing_count=p.listing_count,
                    listing_attempts=listing_attempts_by_player.get(p.id, []),
                    listing_cost=balance.listing_cost,
                    agent_pct=balance.agent_pct if balance.is_sold else None,
                    resale_bonus_share=balance.resale_bonus_share,
                    saldo=balance.saldo,
                    is_sold=balance.is_sold,
                    training_at_sale=training_label,
                    season_at_sale=season_label_for_row,
                    week_at_sale=week_number(effective_sold_at),
                    week_at_purchase=week_number(purchased_at),
                    top_skill_at_sale=top_skill_for_row,
                    bid_hour_at_sale=bid_hour_for_row,
                    native_country=native_country or "?",
                    native_country_code=native_country_code,
                    character=character_label,
                    specialty=specialty_label,
                    tsi_at_purchase=tsi_purchase,
                    tsi_at_sale=tsi_sale,
                    delta_tsi=delta_tsi,
                    commission_amount=commission_amount,
                    roi_pct=roi_pct,
                    destination_country=p.destination_country or "?",
                    destination_country_code=destination_country_code,
                    age_at_sale=age_at_sale,
                    age_at_purchase=age_at_purchase,
                    experience_at_purchase=_skill_val(at_purchase, "experience"),
                    leadership_at_purchase=_skill_val(at_purchase, "leadership"),
                    form_at_purchase=_skill_val(at_purchase, "form"),
                    stamina_at_purchase=_skill_val(at_purchase, "stamina"),
                    keeper_at_purchase=_skill_val(at_purchase, "keeper"),
                    defending_at_purchase=_skill_val(at_purchase, "defending"),
                    playmaking_at_purchase=_skill_val(at_purchase, "playmaking"),
                    winger_at_purchase=_skill_val(at_purchase, "winger"),
                    passing_at_purchase=_skill_val(at_purchase, "passing"),
                    scoring_at_purchase=_skill_val(at_purchase, "scoring"),
                    set_pieces_at_purchase=_skill_val(at_purchase, "set_pieces"),
                    experience_at_sale=_skill_val(at_sale, "experience"),
                    form_at_sale=_skill_val(at_sale, "form"),
                    stamina_at_sale=_skill_val(at_sale, "stamina"),
                    keeper_at_sale=_skill_val(at_sale, "keeper"),
                    defending_at_sale=_skill_val(at_sale, "defending"),
                    playmaking_at_sale=_skill_val(at_sale, "playmaking"),
                    winger_at_sale=_skill_val(at_sale, "winger"),
                    passing_at_sale=_skill_val(at_sale, "passing"),
                    scoring_at_sale=_skill_val(at_sale, "scoring"),
                    set_pieces_at_sale=_skill_val(at_sale, "set_pieces"),
                    days_since_purchase=days_since_purchase,
                    saldo_per_delta_tsi=saldo_per_delta_tsi,
                    is_departure_without_sale=is_departure_without_sale,
                )
            )
            if balance.saldo is None:
                unknown_count += 1
            else:
                total_saldo += balance.saldo

        # Filtro general de temporadas (pedido explícitamente 2026-08-04):
        # "all"/None trae todo, como siempre; un valor real de `by_season`
        # recorta "Detalle" y los desgloses NO-temporada a esa única
        # temporada — reutilizando las mismas etiquetas por fila que ya se
        # calcularon arriba, nunca recalculando nada distinto.
        season_filter_active = season is not None and season != "all"
        rows_for_response = (
            [r for r in rows if r.season_at_sale == season] if season_filter_active else rows
        )
        breakdowns = _build_breakdowns(rows_for_response)

        return PlayerBalanceResponse(
            team_name=team.name,
            currency=team.currency_name,
            players=rows_for_response,
            total_saldo=round(total_saldo, 2),
            unknown_purchase_count=unknown_count,
            by_training_type=breakdowns["by_training_type"],
            by_season=breakdowns["by_season"],
            by_age_bucket=breakdowns["by_age_bucket"],
            by_top_skill=breakdowns["by_top_skill"],
            by_bid_hour=breakdowns["by_bid_hour"],
            transfer_total_buys=conv(team.transfer_total_buys) or 0,
            transfer_total_sales=conv(team.transfer_total_sales) or 0,
            transfer_number_buys=team.transfer_number_buys,
            transfer_number_sales=team.transfer_number_sales,
        )
