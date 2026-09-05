"""Saldo neto por jugador — HL-161.

Hattrick Control te dice cuánto vale un jugador *hoy*; nunca te dice si esa
compra ya fue rentable en términos absolutos: precio de compra, salario
pagado al llegar y en cada actualización económica semanal, coste de cada
intento de venta, la comisión real del
agente al vender — y lo que llega después, cuando alguien revende a un
ex-tuyo y te toca una parte por derechos de formación / club anterior.

    saldo = venta × (1 − %agente) − (compra + salario_acumulado + costo_listados)
            + ingreso_por_reventa_futura

Pedida y validada contra la hoja de cálculo real del usuario (columna
"Ganancia" de su tabla "Compra vs Venta") — la tabla de comisión del agente
de abajo es la oficial de Hattrick, no una estimación.

QUÉ NO SE INVENTA
-----------------
- Si no se conoce el precio de compra (ni real ni escrito a mano) y el
  jugador no es canterano, el saldo es `None` — nunca 0 ni una valoración
  estimada.
- Si el jugador sigue en la plantilla (no vendido), no se usa ninguna
  valoración de mercado hipotética: la venta cuenta 0 hasta que sea real.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.domain.value_objects.ht_time import HATTRICK_TZ

LISTING_COST = 1000
# Un canterano en su PRIMERA venta paga solo agente, 5% fijo — ni derechos
# de formación ni club anterior aplican (eres tú mismo el club de origen,
# y tu club no cuenta como "club anterior" de tu propio canterano).
ACADEMY_FIRST_SALE_PCT = 0.05
# Confirmado por el usuario 2026-08-03: además de la tabla de agente, en
# cualquier venta de un jugador COMPRADO se cobra siempre un 5% adicional.
# Se consideró añadir también un 2% de derechos de formación (real en las
# reglas de Hattrick cuando tu club no es el club de origen), pero el
# usuario pidió explícitamente replicar su hoja de cálculo tal cual —
# validada exactamente contra sus propias filas reales — así que se deja
# fuera a propósito, no por descuido.
ALWAYS_CHARGED_PCT = 0.05

# Tabla oficial de Hattrick: % que se lleva el agente al vender, según los
# días que llevas siendo dueño del jugador. Días 0-6 vienen día a día;
# de ahí en adelante Hattrick publica un valor por SEMANA (7 días), así que
# los días intermedios se interpolan linealmente — verificado contra la
# hoja de cálculo real del usuario (columna "Porc_2"), que hace exactamente
# esta interpolación. El valor se congela en 2% desde la semana 16 (día 112).
AGENT_PCT_BREAKPOINTS: list[tuple[int, float]] = [
    (0, 0.12),
    (1, 0.1045),
    (2, 0.0995),
    (3, 0.0959),
    (4, 0.093),
    (5, 0.0905),
    (6, 0.0883),
    (7, 0.0862),
    (14, 0.0755),
    (21, 0.0676),
    (28, 0.0612),
    (35, 0.0557),
    (42, 0.0509),
    (49, 0.0465),
    (56, 0.0424),
    (63, 0.0387),
    (70, 0.0352),
    (77, 0.0319),
    (84, 0.0288),
    (91, 0.0258),
    (98, 0.023),
    (105, 0.0203),
    (112, 0.02),
]


def agent_commission_pct(days_owned: int) -> float:
    """% que se lleva el agente al vender un jugador COMPRADO (no
    canterano), según cuántos días llevas siendo su dueño."""
    if days_owned <= AGENT_PCT_BREAKPOINTS[0][0]:
        return AGENT_PCT_BREAKPOINTS[0][1]
    if days_owned >= AGENT_PCT_BREAKPOINTS[-1][0]:
        return AGENT_PCT_BREAKPOINTS[-1][1]
    # `strict=False` explicito: es el idioma de "pares consecutivos" y las dos
    # listas tienen distinta longitud a proposito --n y n-1--, asi que con
    # `strict=True` esto reventaria siempre.
    for (d0, p0), (d1, p1) in zip(AGENT_PCT_BREAKPOINTS, AGENT_PCT_BREAKPOINTS[1:], strict=False):
        if d0 <= days_owned <= d1:
            if d1 == d0:
                return p0
            frac = (days_owned - d0) / (d1 - d0)
            return p0 + frac * (p1 - p0)
    return AGENT_PCT_BREAKPOINTS[-1][1]  # inalcanzable, guarda de tipo


@dataclass(frozen=True)
class SalarySnapshot:
    captured_at: datetime
    salary: int


# Lo que cuesta subir a un canterano al primer equipo, en la MONEDA BASE del
# juego (Hattrick da todo el dinero así y cada país tiene su tasa: con la de
# Colombia, 10, son 2.000 US$). 2026-08-19, aportado por el usuario: CHPP no
# publica este cargo por ninguna parte —las nueve partidas de gasto de
# `economy.xml` no lo incluyen— así que el número viene del juego y se declara
# aquí en vez de esconderlo en un cálculo.
YOUTH_PROMOTION_COST = 20_000


@dataclass(frozen=True)
class PlayerTransferRecord:
    """Todo lo que hace falta saber de UN jugador para calcular su saldo.
    `salary_history` es lo que de verdad se sincronizó — con huecos, no
    una serie perfecta semana a semana; el motor extrapola."""

    purchase_price: int | None  # None = desconocido (ni real ni manual)
    purchased_at: datetime | None
    is_academy_graduate: bool
    salary_history: list[SalarySnapshot]
    listing_count: int
    sale_price: int | None  # None = todavía no se ha vendido
    sold_at: datetime | None
    # Una ocurrencia real de la actualización económica semanal de la liga,
    # tomada de EconomyDate en worlddetails.xml. Cualquier ocurrencia sirve de
    # ancla para reconstruir las demás; no depende del día en que se compró.
    economy_date: datetime | None
    # Ingreso por reventas futuras de origen desconocido, ya repartido y
    # asignado a este jugador (ver `resale_bonus.py`) — 0 si no aplica.
    resale_bonus_share: float = 0.0
    as_of: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Lo que costó ascenderlo, si vino de la cantera. Se pasa en vez de leerse
    # de una constante para que el motor siga siendo puro y para que un país
    # con otro cargo no obligue a tocarlo.
    promotion_cost: int = 0
    # El salario que Hattrick reporta de este jugador, para quien no dejo ni
    # un snapshot: comprado y vendido entre dos sincronizaciones. No es una
    # estimacion nuestra, es el dato que da `playerdetails.xml` — que lo
    # devuelve incluso cuando el jugador ya juega en otro club.
    fallback_salary: int = 0
    # El sueldo que la curva le calcula a quien no dejo ni una lectura, porque
    # su etapa es anterior a HT Lens (ver `salary_model.py`). Ultimo recurso:
    # solo se usa cuando no hay historial NI dato reportado, y el resultado
    # viaja marcado como estimado para que nunca se sume con lo observado sin
    # decirlo.
    estimated_salary: int = 0


@dataclass(frozen=True)
class PlayerBalance:
    purchase_price: int | None
    salary_total: int
    listing_cost: int
    agent_pct: float
    net_sale_proceeds: int  # 0 si no se ha vendido — nunca una estimación
    resale_bonus_share: float
    saldo: float | None  # None si falta compra o calendario salarial verificable
    is_sold: bool
    # False cuando de ese jugador no se guardó NUNCA un salario: pasó por el
    # club antes de que la app lo viera y solo se conoce por el historial de
    # transferencias. Entonces `salary_total` es 0 por ignorancia, no porque
    # no cobrara, y el saldo sale mejor de lo que fue. Se marca en vez de
    # inventar una cifra, que es la regla del resto de la app.
    salary_known: bool = True
    #: `observado` | `estimado` | `desconocido` — de donde sale `salary_total`.
    salary_source: str = "observado"


def weeks_owned(purchased_at: datetime, end: datetime) -> int:
    """Semanas completas de posesión.

    Sigue siendo útil como medida de antigüedad, pero ya NO decide cuántos
    salarios se pagaron. Los salarios siguen `salary_payment_dates`.
    """
    return max((end - purchased_at).days // 7, 0)


_WEEK = timedelta(days=7)


def _utc(value: datetime) -> datetime:
    """Normaliza solo para hacer aritmética; un naive de la BD ya significa UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _like(value: datetime, template: datetime) -> datetime:
    """Devuelve UTC con el mismo estilo aware/naive que las fechas del registro."""
    return value if template.tzinfo is not None else value.replace(tzinfo=None)


def salary_payment_dates(
    purchased_at: datetime,
    end: datetime,
    economy_date: datetime | None,
) -> list[datetime]:
    """Instantes en los que el club paga salarios durante una etapa.

    Hay un pago inmediato en `purchased_at`. Después se incluye cada
    actualización económica semanal estrictamente posterior a la compra y
    anterior o igual a `end`. Comprar exactamente durante una actualización
    no genera dos cobros en el mismo instante.

    EconomyDate viene en la hora del servidor sueco. La recurrencia se mueve
    en esa hora de pared, no sumando ciegamente 168 horas UTC: así conserva la
    hora oficial incluso al cruzar un cambio CET/CEST.

    Sin EconomyDate solo es demostrable el pago inmediato; el caller debe
    marcar el total como desconocido si la etapa continuó después de la
    compra.
    """
    purchased_utc = _utc(purchased_at)
    end_utc = _utc(end)
    payments = [purchased_at]
    if economy_date is None or end_utc <= purchased_utc:
        return payments

    anchor_local = _utc(economy_date).astimezone(HATTRICK_TZ)
    purchased_local = purchased_utc.astimezone(HATTRICK_TZ)
    # EconomyDate es una ocurrencia cualquiera de la misma serie semanal.
    # Se calcula en hora local para no perder la hora oficial durante DST.
    wall_delta = purchased_local.replace(tzinfo=None) - anchor_local.replace(tzinfo=None)
    periods = wall_delta // _WEEK + 1  # el primer cruce debe ser > compra
    update_local = anchor_local + periods * _WEEK
    update_utc = update_local.astimezone(UTC)

    # Guarda ante horas ambiguas/no existentes en un cambio de DST. EconomyDate
    # normalmente cae lejos de ese borde, pero el límite estricto no se deja a
    # merced de una particularidad de ZoneInfo.
    while update_utc <= purchased_utc:
        update_local += _WEEK
        update_utc = update_local.astimezone(UTC)

    while update_utc <= end_utc:
        payments.append(_like(update_utc, purchased_at))
        update_local += _WEEK
        update_utc = update_local.astimezone(UTC)
    return payments


def salary_at(history: list[SalarySnapshot], target: datetime) -> int:
    """Último salario conocido en o antes de `target` — el mismo
    carry-forward que ya usa el resto de la app para huecos entre syncs
    (si el salario no cambió, sencillamente no hay snapshot nuevo). Si no
    hay ningún dato anterior a `target`, se usa el primero disponible como
    mejor estimación posible."""
    known = [s.salary for s in history if s.captured_at <= target]
    if known:
        return known[-1]
    return history[0].salary if history else 0


def _total_salary(
    purchased_at: datetime,
    end: datetime,
    economy_date: datetime | None,
    history: list[SalarySnapshot],
    fallback: int = 0,
    estimated: int = 0,
) -> int:
    """Compra inmediata + cada actualización económica atravesada hasta `end`.

    Sin ningún snapshot se usa `fallback`: el salario que Hattrick reporta de
    ese jugador, que sigue dándolo aunque ya juegue en otro club. No es un
    número inventado por nosotros — o se conoce, o la casilla queda vacía.
    """
    payments = salary_payment_dates(purchased_at, end, economy_date)
    if not history:
        return (fallback or estimated) * len(payments)
    return sum(salary_at(history, payment) for payment in payments)


def compute_balance(record: PlayerTransferRecord) -> PlayerBalance:
    if record.purchase_price is None and not record.is_academy_graduate:
        return PlayerBalance(
            purchase_price=None,
            salary_total=0,
            listing_cost=0,
            agent_pct=0.0,
            net_sale_proceeds=0,
            resale_bonus_share=record.resale_bonus_share,
            saldo=None,
            is_sold=record.sale_price is not None,
            # Sin precio de compra no hay saldo que calcular, asi que tampoco
            # hay sueldo que atribuir a ninguna fuente.
            salary_source="desconocido",
        )

    # Un canterano no se compra, pero ascenderlo tampoco es gratis: hasta
    # 2026-08-19 entraba con coste 0 y su saldo salía inflado por ese importe.
    purchase_price = (
        record.promotion_cost if record.is_academy_graduate else (record.purchase_price or 0)
    )
    end = record.sold_at or record.as_of
    # Sin fecha de compra conocida no hay cruces que contar — 0, no negativo.
    purchased_at = record.purchased_at or end
    salary_total = _total_salary(
        purchased_at,
        end,
        record.economy_date,
        record.salary_history,
        record.fallback_salary,
        record.estimated_salary,
    )
    listing_cost = record.listing_count * LISTING_COST

    is_sold = record.sale_price is not None
    if is_sold:
        days_owned = max(((record.sold_at or end) - purchased_at).days, 0)
        # Canterano en su primera venta: solo el agente, plano. Cualquier
        # otra venta: tabla de agente + 5% siempre (ver ALWAYS_CHARGED_PCT
        # arriba — replica la hoja de cálculo real del usuario).
        agent_pct = (
            ACADEMY_FIRST_SALE_PCT
            if record.is_academy_graduate
            else agent_commission_pct(days_owned) + ALWAYS_CHARGED_PCT
        )
        net_sale_proceeds = round((record.sale_price or 0) * (1 - agent_pct))
    else:
        agent_pct = 0.0
        net_sale_proceeds = 0

    saldo = (
        net_sale_proceeds
        - (purchase_price + salary_total + listing_cost)
        + record.resale_bonus_share
    )
    # Sin EconomyDate una etapa que duró más que el instante de llegada sólo
    # tiene demostrado el primer cobro, así que el total del sueldo no está
    # completo y se marca con `salary_known`.
    salary_calendar_known = record.economy_date is not None or _utc(end) <= _utc(purchased_at)
    # ¿La aplicación llegó a VER a este jugador cobrar? Sin una sola lectura,
    # la etapa es anterior a HT Lens.
    observado = bool(record.salary_history) or record.fallback_salary > 0
    salary_known = observado and record.purchased_at is not None and salary_calendar_known
    # Tres estados, no dos: lo que se vio, lo que se calculo y lo que sigue sin
    # saberse. Sin esta distincion un total mezcla lecturas con estimaciones y
    # nadie puede saber cuanto de la cifra es medida.
    if observado:
        salary_source = "observado"
    elif record.estimated_salary > 0:
        salary_source = "estimado"
    else:
        salary_source = "desconocido"

    return PlayerBalance(
        purchase_price=purchase_price,
        salary_total=salary_total,
        listing_cost=listing_cost,
        agent_pct=agent_pct,
        net_sale_proceeds=net_sale_proceeds,
        resale_bonus_share=record.resale_bonus_share,
        # El veto vale para lo que la aplicación VIGILA, no para lo que pasó
        # antes de que existiera (2026-09-04, decisión del usuario).
        #
        # De una etapa observada a la que le falte el calendario económico no
        # se publica saldo: es un hueco real y arreglable --se arregla
        # sincronizando-- y taparlo con un número escondería el fallo.
        #
        # De una etapa anterior a HT Lens no hay ni habrá lecturas de sueldo:
        # Hattrick no publica hacia atrás lo que cobró alguien en 2018. Ahí
        # negarse a dar un saldo es negarse para siempre, así que se da el
        # mejor número posible y se marca con `salary_known` que le falta el
        # sueldo. Desconocido, no falso.
        #
        # Aplicar el veto a todo vació la pantalla el 2026-09-03: de 598
        # etapas guardadas sólo 48 son de jugadores que la aplicación llegó a
        # ver, y la gráfica «Cada transferencia» bajó a trece puntos. El
        # usuario lo notó como «se desapareció mi histórico».
        saldo=round(saldo) if (salary_calendar_known or not observado) else None,
        is_sold=is_sold,
        # Hace falta conocer tanto el importe como el calendario. Si la etapa
        # duró más que el instante de compra y aún no se sincronizó
        # EconomyDate, solo el primer pago es demostrable y el total se marca
        # como desconocido en vez de presentarlo como definitivo.
        salary_known=salary_known,
        salary_source=salary_source,
    )
