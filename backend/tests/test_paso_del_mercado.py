"""El paso semanal del mercado, de punta a punta y contra una base de verdad.

Las piezas se prueban sueltas en otros ficheros. Aqui se comprueba que
encajan: que el disparador sale de la fecha economica de la liga, que lo
encontrado se guarda con su perfil, que una venta sirve a un companero sin
gastar otra llamada, y que la puja se convierte en el precio real cuando la
subasta cierra.

El caso que gobierna todo esto es real: el 2026-10-05 Valerio Cataldi tenia
65.000.000 de puja y cerro en 77.720.000, un 16% mas.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.paso_del_mercado import correr_el_paso_semanal
from app.application.queries.precio_comparable import precio_de
from app.domain.engines.mercado_comparable import OBJETIVO, Ventana
from app.infrastructure.db import models as m

HT_TEAM = 537758
LIGA = 19
#: La proxima actualizacion economica de la liga, y el disparador: menos 24 h.
ECONOMICA = datetime(2026, 10, 9, 21, 25, tzinfo=UTC)
DISPARADOR = ECONOMICA - timedelta(hours=24)
AHORA = DISPARADOR + timedelta(hours=1)

PLAZO_HT = "2026-10-08 23:00:00"

#: Un delantero: anotacion 18, pases 13, creacion 7. Su id cae en el grupo 0,
#: que es justo al que le toca en la semana de `AHORA`.
ALBERTO = 468921490
#: Un companero con el MISMO perfil pero de OTRO grupo: no le toca esta
#: semana, y aun asi tiene que poder usar lo que la busqueda de Alberto trajo.
GEMELO = 468921492


def _skills(scoring: int = 18, passing: int = 13, playmaking: int = 7) -> dict[str, int]:
    return {
        "keeper": 1,
        "defending": 4,
        "playmaking": playmaking,
        "winger": 4,
        "passing": passing,
        "scoring": scoring,
        "set_pieces": 9,
        "stamina": 6,
    }


def _fila_de_mercado(ident: int, *, puja: int = 10_000_000, **extra: Any) -> dict[str, Any]:
    fila: dict[str, Any] = {
        "ht_player_id": ident,
        "first_name": "Ajeno",
        "last_name": str(ident),
        "age_years": 31,
        "asking_price": puja,
        "highest_bid": puja,
        "has_bids": True,
        "deadline": PLAZO_HT,
        "tsi": 170_000,
        "specialty": 0,
        "injury_level": -1,
        "seller_team_id": 7_654_321,
        "seller_league_id": 92,
        "skills": _skills(),
    }
    fila.update(extra)
    return fila


class _MercadoFalso:
    def __init__(self, *paginas: list[dict[str, Any]]) -> None:
        self.paginas = list(paginas)
        self.llamadas = 0

    async def __call__(self, ventana: Ventana) -> list[dict[str, Any]]:
        indice = self.llamadas
        self.llamadas += 1
        return self.paginas[indice] if indice < len(self.paginas) else []


async def _sin_historial(ht_player_id: int) -> dict[str, Any]:
    return {"transfers": []}


@pytest.fixture
async def base():
    """Una base en memoria con el equipo, su liga y dos jugadores."""
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=HT_TEAM, name="Pulgas Arrechas", ht_league_id=LIGA)
        s.add(equipo)
        s.add(m.WorldContext(ht_league_id=LIGA, economy_date=ECONOMICA))
        await s.flush()
        sync = m.Sync(user_id=1, team_id=equipo.id, kind="players", started_at=AHORA)
        s.add(sync)
        await s.flush()
        for ht_id in (ALBERTO, GEMELO):
            jugador = m.Player(team_id=equipo.id, ht_player_id=ht_id, first_name="J", last_name="x")
            s.add(jugador)
            await s.flush()
            s.add(
                m.PlayerSnapshot(
                    sync_id=sync.id,
                    player_id=jugador.id,
                    captured_at=AHORA,
                    age_years=31,
                    age_days=10,
                    specialty=0,
                    content_hash=bytes(32),
                    tsi=170_000,
                    form=7,
                    experience=5,
                    salary=600_000,
                    **_skills(),
                )
            )
        await s.commit()
        yield s, equipo


async def test_el_paso_busca_guarda_y_sella(base) -> None:
    """Lo basico: encuentra, guarda con el perfil y deja constancia de que
    corrio, para no repetirlo en la siguiente sincronizacion."""
    session, equipo = base
    mercado = _MercadoFalso([_fila_de_mercado(900 + i) for i in range(OBJETIVO)])
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=AHORA
    )
    assert paso.se_busco is True
    assert paso.ventas_nuevas == OBJETIVO
    assert equipo.market_run_at == AHORA

    filas = (await session.execute(select(m.MarketSale))).scalars().all()
    assert len(filas) == OBJETIVO
    assert all(f.primary_skill == "scoring" and f.primary_level == 18 for f in filas)
    assert all(f.is_final is False for f in filas), "entran con la puja, no con el precio"


async def test_solo_le_toca_a_los_jugadores_del_turno(base) -> None:
    """Una quinta parte por semana: el grupo sale del propio identificador."""
    session, equipo = base
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=_MercadoFalso(), historial_de=_sin_historial, ahora=AHORA
    )
    assert paso.jugadores_del_turno == (ALBERTO,)


async def test_sin_fecha_economica_el_paso_no_corre(base) -> None:
    """Es la unica fuente del disparador, y Hattrick la da por pais."""
    session, equipo = base
    contexto = (await session.execute(select(m.WorldContext))).scalar_one()
    contexto.economy_date = None
    await session.flush()
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=_MercadoFalso(), historial_de=_sin_historial, ahora=AHORA
    )
    assert paso.se_busco is False
    assert equipo.market_run_at is None


async def test_una_vez_corrido_no_se_repite_en_la_misma_semana(base) -> None:
    """La economia principal: casi todas las sincronizaciones no gastan nada."""
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    segundo = _MercadoFalso([_fila_de_mercado(950)])
    paso = await correr_el_paso_semanal(
        session,
        equipo,
        buscar=segundo,
        historial_de=_sin_historial,
        ahora=AHORA + timedelta(hours=2),
    )
    assert paso.se_busco is False
    assert segundo.llamadas == 0


async def test_la_puja_se_convierte_en_el_precio_de_verdad(base) -> None:
    """El corazon del diseno. Una venta entra con la puja y, cuando su subasta
    cierra, se le pregunta al historial cuanto se pago."""
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900, puja=65_000_000)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )

    async def historial(ht_player_id: int) -> dict[str, Any]:
        return {"transfers": [{"deadline": PLAZO_HT, "price": 77_720_000}]}

    despues = AHORA + timedelta(days=2)
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=_MercadoFalso(), historial_de=historial, ahora=despues
    )
    assert [r.precio for r in paso.resueltas] == [77_720_000]
    fila = (await session.execute(select(m.MarketSale))).scalar_one()
    assert fila.price == 77_720_000
    assert fila.is_final is True


async def test_el_fondo_sirve_a_toda_la_plantilla(base) -> None:
    """LA prueba del fondo compartido: al gemelo no le tocaba turno esta
    semana y aun asi tiene precio, con lo que trajo la busqueda de Alberto y
    sin gastar ni una llamada mas."""
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i) for i in range(OBJETIVO)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    for ht_id in (ALBERTO, GEMELO):
        precio = await precio_de(session, equipo.id, ht_id, AHORA)
        assert precio is not None
        assert precio.n == OBJETIVO
        assert precio.media == 10_000_000


async def test_la_pantalla_recibe_de_que_fiarse(base) -> None:
    """Cuantos son provisionales, cuanto se parecen y de cuando son."""
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i) for i in range(OBJETIVO)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    precio = await precio_de(session, equipo.id, ALBERTO, AHORA)
    assert precio is not None
    assert precio.provisionales == OBJETIVO, "todas son pujas hasta que cierren"
    assert precio.peso_minimo == 100
    assert precio.minimo == precio.maximo == 10_000_000
    assert precio.faltan == 0
    assert "scoring 18" in precio.perfil


async def test_con_pocas_ventas_no_hay_numero_pero_si_lista(base) -> None:
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900), _fila_de_mercado(901)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    precio = await precio_de(session, equipo.id, ALBERTO, AHORA)
    assert precio is not None
    assert precio.media is None
    assert precio.n == 2
    assert precio.faltan == OBJETIVO - 2
    assert len(precio.comparables) == 2


async def test_un_jugador_de_otro_equipo_no_tiene_precio(base) -> None:
    session, equipo = base
    assert await precio_de(session, equipo.id, 123456, AHORA) is None
