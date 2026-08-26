"""Los intentos de venta, uno por fila.

2026-08-22, pedido explícitamente. Hasta ahora la aplicación sabía cuántas
veces se había listado un jugador, pero no podía enseñar CADA intento con su
final: a qué precio se pedía, si terminó en venta o el jugador se quedó, y
cuántas veces lo miraron.

Ese último dato es el único de toda la aplicación que Hattrick no entrega por
CHPP. Solo lo dice en el texto de las noticias al cerrarse la puja ("este
jugador fue visto 8 veces mientras estaba en la lista de transferibles"), así
que lo teclea el usuario y aquí se sirve tal cual, sin estimarlo jamás.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.player_balance import (
    SalarySnapshot,
    salary_at,
    weeks_owned,
)
from app.domain.value_objects.ht_constants import (
    PLAYER_AGREEABILITY,
    SPECIALTIES,
    training_name,
)
from app.domain.value_objects.skill import Age
from app.infrastructure.db import models as m

SKILL_COLS = (
    "keeper",
    "defending",
    "playmaking",
    "winger",
    "passing",
    "scoring",
    "set_pieces",
)
#: A partir de aqui la foto esta tan lejos del cierre que ya no describe al
#: jugador de ese dia. Se marca para que no se lea como exacta.
DIAS_PARA_DUDAR = 3
#: Comision del agente en una venta. Solo aplica si de verdad hubo venta.
AGENT_PCT = 0.07


@dataclass
class TransferAttemptRow:
    #: "483141997_2": el segundo intento de ese jugador.
    key: str
    id: int
    attempt_number: int
    ht_player_id: int | None
    name: str

    detected_at: str
    #: Cuando cerro la puja. En un intento fallido no hay fecha de venta.
    closed_at: str | None
    open: bool
    sold: bool

    asking_price: int | None
    highest_bid: int | None
    sale_price: int | None
    #: Solo en los exitosos: en un intento fallido no hay agente que cobre.
    agent_pct: float | str
    times_seen: int | None
    asked: bool

    # Como estaba el jugador al cerrar la puja.
    tsi: int | str
    age: str
    skills: dict[str, int | str]
    specialty: str
    character: str
    native_country: str
    #: Para pintar la bandera; `None` si no se pudo resolver.
    native_country_code: str | None
    #: La foto usada es de este dia; si queda lejos del cierre, `stale` avisa.
    snapshot_at: str | None
    stale: bool

    # Su etapa en el club.
    from_academy: bool
    purchased_at: str | None
    purchase_price: int | str
    age_at_purchase: str
    days_since_purchase: int | str
    #: Lo pagado en salarios HASTA el cierre, no hasta hoy: si no, un intento
    #: viejo ensenaria el acumulado de ahora y dos filas de la misma tabla
    #: dejarian de ser comparables.
    salary_to_date: int | str
    training_that_week: str


@dataclass
class TransferAttemptsResponse:
    currency: str
    rows: list[TransferAttemptRow] = field(default_factory=list)
    #: Los que terminaron y siguen sin saber cuántas visitas tuvieron. Es lo
    #: que la pantalla de Cambios convierte en un aviso que se puede ignorar.
    pending_question: list[TransferAttemptRow] = field(default_factory=list)


def _iso(valor: datetime | None) -> str | None:
    return valor.isoformat() if valor is not None else None


def _edad(years: int | None, days: int | None) -> str:
    if years is None or days is None:
        return "?"
    return f"{years};{days:03d}"


def _especialidad(foto, jugador) -> str:
    """La especialidad, mirando primero donde de verdad esta."""
    codigo = foto.specialty if foto is not None else None
    if codigo is None:
        codigo = jugador.specialty
    if codigo is None:
        return "?"
    return SPECIALTIES.get(codigo) or "Ninguna"


def _caracter(foto, jugador) -> str:
    # Cero es "antipatica", un caracter como cualquier otro: hay que
    # preguntar si el dato existe, no si vale cero.
    valor = foto.agreeability if foto is not None else None
    if valor is None:
        valor = jugador.agreeability
    if valor is None:
        return "?"
    return PLAYER_AGREEABILITY.get(valor, "?")


def _edad_en_la_compra(al_llegar, foto, jugador, llegada) -> str:
    """Su edad el dia que llego.

    Lo mejor es una foto del mismo dia de la llegada: esa edad ES la edad de
    compra, sin cuentas. Pero "la primera foto que hay desde que llego" no
    sirve por si sola: el historial empieza el dia que se estreno la
    aplicacion, asi que para quien ya estaba, esa primera foto es de meses
    despues y da una edad de meses despues. Por eso solo vale si es del dia.

    Si no la hay, vale la que dejo escrita el repaso de fichas, y en ultimo
    lugar se calcula restando — la edad avanza un dia por dia real.
    """
    if al_llegar is not None and llegada is not None and (al_llegar.captured_at - llegada).days < 1:
        return _edad(al_llegar.age_years, al_llegar.age_days)
    if jugador.age_years_at_purchase is not None:
        return _edad(jugador.age_years_at_purchase, jugador.age_days_at_purchase)
    if foto is not None and llegada is not None:
        transcurridos = (foto.captured_at - llegada).days
        try:
            entonces = Age(foto.age_years, foto.age_days).add_days(-transcurridos)
        except ValueError:
            return "?"
        return _edad(entonces.years, entonces.days)
    return "?"


class TransferAttemptsQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, team_id: int) -> TransferAttemptsResponse | None:
        equipo = await self._s.get(m.Team, team_id)
        if equipo is None:
            return None
        tasa = equipo.currency_rate or 1.0

        def conv(valor: int | None) -> int | None:
            return None if valor is None else int(round(valor / tasa))

        # Códigos de país para la bandera: por id (el que trae la plantilla) y
        # por nombre (lo único que queda de un ex-jugador enriquecido).
        paises = (
            await self._s.execute(
                select(
                    m.WorldContext.country_id,
                    m.WorldContext.country_name,
                    m.WorldContext.country_code,
                )
            )
        ).all()
        self._codigo_por_id = {cid: cod for cid, _, cod in paises if cod}
        self._codigo_por_nombre = {
            nombre.strip().casefold(): cod for _, nombre, cod in paises if cod and nombre
        }

        intentos = (
            await self._s.execute(
                select(m.PlayerListingAttempt, m.Player)
                .join(m.Player, m.Player.id == m.PlayerListingAttempt.player_id)
                .where(m.Player.team_id == team_id)
                .order_by(
                    m.PlayerListingAttempt.player_id,
                    m.PlayerListingAttempt.detected_at,
                )
            )
        ).all()

        # El numero de intento es por jugador y en orden: el primero es el 1.
        numero: dict[int, int] = {}
        salida: list[TransferAttemptRow] = []
        for intento, jugador in intentos:
            numero[jugador.id] = numero.get(jugador.id, 0) + 1
            salida.append(await self._fila(intento, jugador, numero[jugador.id], conv, equipo))

        salida.sort(key=lambda r: r.detected_at, reverse=True)
        return TransferAttemptsResponse(
            currency=equipo.currency_name,
            rows=salida,
            pending_question=[
                r
                for r in salida
                if not r.open and not r.asked and (r.times_seen is None or r.asking_price is None)
            ],
        )

    async def _fila(self, intento, jugador, numero, conv, equipo) -> TransferAttemptRow:
        cierre = intento.ended_at or intento.deadline
        corte = cierre or datetime.now()

        foto = await self._s.scalar(
            select(m.PlayerSnapshot)
            .where(
                m.PlayerSnapshot.player_id == jugador.id,
                m.PlayerSnapshot.captured_at <= corte,
            )
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        entrenamiento = await self._s.scalar(
            select(m.TrainingSnapshot)
            .where(
                m.TrainingSnapshot.team_id == equipo.id,
                m.TrainingSnapshot.captured_at <= corte,
            )
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        )
        etapa = (
            await self._s.get(m.PlayerStint, intento.stint_id)
            if intento.stint_id is not None
            else None
        )
        if etapa is None:
            etapa = await self._s.scalar(
                select(m.PlayerStint)
                .where(
                    m.PlayerStint.player_id == jugador.id,
                    m.PlayerStint.arrived_at <= intento.detected_at,
                )
                .order_by(m.PlayerStint.arrived_at.desc())
                .limit(1)
            )

        antiguedad = (corte - foto.captured_at).days if foto is not None else None
        llegada = etapa.arrived_at if etapa is not None else None

        # La primera foto desde que llego: su edad es, tal cual, la edad de
        # compra. Es la misma que mira Detalle.
        al_llegar = (
            await self._s.scalar(
                select(m.PlayerSnapshot)
                .where(
                    m.PlayerSnapshot.player_id == jugador.id,
                    m.PlayerSnapshot.captured_at >= llegada,
                )
                .order_by(m.PlayerSnapshot.captured_at.asc())
                .limit(1)
            )
            if llegada is not None
            else None
        )

        return TransferAttemptRow(
            key=f"{jugador.ht_player_id}_{numero}",
            id=intento.id,
            attempt_number=numero,
            ht_player_id=jugador.ht_player_id,
            name=f"{jugador.first_name} {jugador.last_name}".strip(),
            detected_at=intento.detected_at.isoformat(),
            closed_at=_iso(cierre),
            open=intento.ended_at is None,
            sold=intento.sold,
            asking_price=intento.asking_price,
            highest_bid=conv(intento.last_highest_bid or intento.highest_bid) or None,
            sale_price=(conv(etapa.sale_price) if intento.sold and etapa is not None else None),
            agent_pct=AGENT_PCT if intento.sold else "?",
            times_seen=intento.times_seen,
            asked=intento.times_seen_asked,
            tsi=foto.tsi if foto is not None else "?",
            age=_edad(
                foto.age_years if foto is not None else None,
                foto.age_days if foto is not None else None,
            ),
            skills={
                col: (getattr(foto, col) if foto is not None else None) or "?" for col in SKILL_COLS
            },
            # De la FOTO, no de la ficha del jugador. Esos campos en la ficha
            # solo los rellena el repaso de ex-jugadores; a quien sigue en el
            # club nadie se los pide, porque vienen con la plantilla todos los
            # dias. Leerlos de la ficha dejaba en "?" a jugadores que estaban
            # sincronizados esa misma manana.
            specialty=_especialidad(foto, jugador),
            character=_caracter(foto, jugador),
            native_country=jugador.native_country or "?",
            native_country_code=(
                self._codigo_por_id.get(foto.country_id) if foto is not None else None
            )
            or (
                self._codigo_por_nombre.get(jugador.native_country.strip().casefold())
                if jugador.native_country
                else None
            ),
            snapshot_at=_iso(foto.captured_at) if foto is not None else None,
            stale=antiguedad is None or antiguedad > DIAS_PARA_DUDAR,
            from_academy=bool(etapa.from_academy) if etapa is not None else False,
            purchased_at=_iso(llegada),
            purchase_price=(
                conv(etapa.arrival_price) if etapa is not None and etapa.arrival_price else "?"
            ),
            age_at_purchase=_edad_en_la_compra(al_llegar, foto, jugador, llegada),
            days_since_purchase=(corte - llegada).days if llegada is not None else "?",
            salary_to_date=await self._salario_hasta(jugador, llegada, corte, conv),
            training_that_week=(
                training_name(entrenamiento.training_type) if entrenamiento is not None else "?"
            ),
        )

    async def _salario_hasta(self, jugador, desde, hasta, conv) -> int | str:
        """Lo pagado en salarios desde que llego hasta el cierre de la puja.

        Congelado a esa fecha a proposito: contarlo hasta hoy haria que un
        intento de hace tres meses ensenara el acumulado de ahora, y dos
        filas de la misma tabla dejarian de ser comparables.
        """
        if desde is None:
            return "?"
        filas = (
            await self._s.execute(
                select(m.PlayerSnapshot.captured_at, m.PlayerSnapshot.salary)
                .where(m.PlayerSnapshot.player_id == jugador.id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
        ).all()
        historia = [SalarySnapshot(captured_at=c, salary=conv(s) or 0) for c, s in filas]
        if not historia:
            return "?"
        semanas = weeks_owned(desde, hasta)
        return sum(salary_at(historia, desde + timedelta(weeks=w)) for w in range(semanas + 1))
