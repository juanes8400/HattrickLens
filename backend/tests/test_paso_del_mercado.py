"""El paso semanal del mercado, de punta a punta y contra una base de verdad.

Las piezas se prueban sueltas en otros ficheros. Aqui se comprueba que
encajan: que el disparador sale de la fecha economica de la liga, que lo
encontrado se guarda con su perfil, que una venta sirve a un companero sin
gastar otra llamada, y que la puja se convierte en el precio real cuando la
subasta cierra.

El caso que gobierna todo esto es real: el 2026-10-05 Valerio Cataldi tenia
65.000.000 de puja y cerro en 77.720.000, un 16% mas.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.mercado_comparable import del_turno, del_turno_exacto
from app.application.commands.paso_del_mercado import (
    _fecha_economica,
    _plantilla,
    correr_el_paso_semanal,
)
from app.application.queries.precio_comparable import precio_de
from app.domain.engines.mercado_comparable import (
    OBJETIVO,
    REINTENTOS_DE_RESOLUCION,
    Ventana,
)
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


async def test_sin_fecha_economica_solo_corre_el_exacto(base) -> None:
    """Los anchos necesitan la frontera semanal; el exacto no.

    La fecha economica de la liga es la unica fuente del turno de cinco
    semanas, asi que sin ella los escalones anchos no se pueden programar. El
    exacto se reparte por dias sobre el identificador y no la necesita, asi
    que un club recien importado empieza a juntar comparables exactos desde el
    primer dia en vez de esperar a su primera foto de economia (2026-10-09).
    """
    session, equipo = base
    contexto = (await session.execute(select(m.WorldContext))).scalar_one()
    contexto.economy_date = None
    await session.flush()
    mercado = _MercadoFalso([_fila_de_mercado(900)])
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=AHORA
    )
    # Una sola peticion por jugador del dia: el exacto y nada mas.
    assert mercado.llamadas == len(paso.jugadores_del_turno)
    assert equipo.market_run_at is not None


async def test_una_vez_corrido_no_se_repite_el_mismo_dia(base) -> None:
    """La economia principal: casi todas las sincronizaciones no gastan nada.

    Era «en la misma semana» hasta el 2026-10-09: la puerta paso a ser diaria
    porque el escalon exacto de cada jugador toca cada SEIS DIAS y con una
    puerta semanal el reloj de los seis dias solo veria un dia de cada siete.
    """
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
        # Dos horas despues pero el MISMO dia: AHORA son las 22:25 UTC.
        ahora=AHORA + timedelta(minutes=30),
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

    # Cuatro dias: el margen tras el plazo paso de dos horas a TRES DIAS el
    # 2026-10-09, «cuando se sabe que debio terminar».
    despues = AHORA + timedelta(days=4)
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
        # El mismo fondo sirve a los dos, que es lo que esta prueba
        # defiende. Son anuncios, asi que dan lista y no media: desde el
        # 2026-10-09 el numero sale solo de ventas cerradas.
        assert len(precio.comparables) == OBJETIVO
        assert precio.media is None


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
    # Y por eso mismo no hay extremos ni cuenta: una puja no es un precio
    # (2026-10-09). Faltan las seis ventas cerradas.
    assert precio.minimo is None and precio.maximo is None
    assert precio.faltan == OBJETIVO
    # El perfil viaja SIN formatear: la pantalla lo nombra con el glosario
    # oficial de Hattrick, que es el que sabe como se dice «scoring» en el
    # idioma de quien mira.
    assert [(r.habilidad, r.nivel) for r in precio.perfil] == [
        ("scoring", 18),
        ("passing", 13),
        ("playmaking", 7),
    ]
    assert all(isinstance(r.habilidad, str) for c in precio.comparables for r in c.perfil)


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
    # Dos anuncios: lista de dos, cuenta de cero.
    assert precio.n == 0
    assert precio.faltan == OBJETIVO
    assert len(precio.comparables) == 2


async def test_un_jugador_de_otro_equipo_no_tiene_precio(base) -> None:
    session, equipo = base
    assert await precio_de(session, equipo.id, 123456, AHORA) is None


async def test_un_chpp_caido_no_gasta_intentos_de_resolucion(base) -> None:
    """Medido contra Hattrick el 2026-10-07: con puja HAY venta, hay traspaso
    y el plazo casa --Guido Bernacki entro con 4.990.000 y plazo 11:01:13Z y
    cerro en 5.090.000 con plazo 11:01:00Z--. O sea que el mercado no deja a
    nadie colgado.

    Lo que si lo dejaba colgado era esto: hasta ese dia un fallo de red
    gastaba intento igual que un «pregunte y no estaba», y bastaban dos
    seguidos para abandonar una venta que si existia. Los intentos miden lo
    que sabemos de la venta; una llamada que no llego no sabe nada de ella.
    """
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900, puja=65_000_000)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )

    async def se_cae(ht_player_id: int) -> dict[str, Any]:
        raise RuntimeError("CHPP no contesta")

    # Cuatro dias: el margen tras el plazo paso de dos horas a TRES DIAS el
    # 2026-10-09, «cuando se sabe que debio terminar».
    despues = AHORA + timedelta(days=4)
    for _ in range(REINTENTOS_DE_RESOLUCION + 3):
        paso = await correr_el_paso_semanal(
            session, equipo, buscar=_MercadoFalso(), historial_de=se_cae, ahora=despues
        )
        assert paso.resueltas == ()

    fila = (await session.execute(select(m.MarketSale))).scalar_one()
    assert fila.resolve_attempts == 0, "un fallo de transporte no es un intento"
    assert fila.is_final is False

    # Y en cuanto CHPP vuelve, se resuelve: no se habia perdido nada.
    async def historial(ht_player_id: int) -> dict[str, Any]:
        return {"transfers": [{"deadline": PLAZO_HT, "price": 77_720_000}]}

    paso = await correr_el_paso_semanal(
        session, equipo, buscar=_MercadoFalso(), historial_de=historial, ahora=despues
    )
    assert [r.precio for r in paso.resueltas] == [77_720_000]


async def test_la_serie_anota_un_punto_cuando_el_numero_cambia(base) -> None:
    """`market_sales` sabe como esta el fondo AHORA, no como estuvo: al
    resolver una venta su puja se pisa con el precio de cierre. Sin anotar
    la lectura no hay forma de dibujar como fue cambiando."""
    session, equipo = base
    paso = await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i, puja=1_000_000) for i in range(6)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    assert paso.puntos_anotados >= 1

    puntos = (
        (
            await session.execute(
                select(m.MarketEstimate).where(m.MarketEstimate.ht_player_id == ALBERTO)
            )
        )
        .scalars()
        .all()
    )
    assert len(puntos) == 1
    # La lectura se anota aunque todavia no haya numero: lo que cambia es la
    # nube, y es justo lo que luego dibuja la grafica.
    assert puntos[0].n == 0
    assert puntos[0].mean_price is None
    # Y lleva la nube, no solo la media: seis precios, los seis sin cerrar.
    nube = json.loads(puntos[0].prices_json)
    assert len(nube) == OBJETIVO
    assert all(p["firme"] is False for p in nube)
    assert {p["precio"] for p in nube} == {1_000_000}


async def test_la_serie_no_repite_un_punto_que_no_dice_nada_nuevo(base) -> None:
    """Un punto por CAMBIO y no por fecha. Anotando en cada sincronizacion,
    la serie seria una linea plana con cientos de puntos iguales y el tiempo
    entre dos puntos dejaria de significar algo."""
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i, puja=1_000_000) for i in range(6)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    antes = len((await session.execute(select(m.MarketEstimate))).scalars().all())

    # Otra sincronizacion sin nada que resolver y sin turno: nada cambia.
    paso = await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso(),
        historial_de=_sin_historial,
        ahora=AHORA + timedelta(hours=1),
    )
    assert paso.puntos_anotados == 0
    despues = len((await session.execute(select(m.MarketEstimate))).scalars().all())
    assert despues == antes


async def test_al_resolverse_una_puja_la_serie_anota_el_cambio(base) -> None:
    """El otro motivo por el que el numero se mueve: una subasta que cierra
    y pasa de puja a precio real."""
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900, puja=65_000_000)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )

    async def historial(ht_player_id: int) -> dict[str, Any]:
        return {"transfers": [{"ht_transfer_id": 77, "deadline": PLAZO_HT, "price": 77_720_000}]}

    # Cuatro dias: el margen tras el plazo paso de dos horas a TRES DIAS el
    # 2026-10-09, «cuando se sabe que debio terminar».
    despues = AHORA + timedelta(days=4)
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=_MercadoFalso(), historial_de=historial, ahora=despues
    )
    assert [r.precio for r in paso.resueltas] == [77_720_000]
    assert paso.puntos_anotados >= 1
    nube = json.loads(
        (
            (
                await session.execute(
                    select(m.MarketEstimate)
                    .where(m.MarketEstimate.ht_player_id == ALBERTO)
                    .order_by(m.MarketEstimate.captured_at.desc())
                    .limit(1)
                )
            ).scalar_one()
        ).prices_json
    )
    # Con su peso desde el 2026-10-09: la grafica pinta mas pequeño y mas
    # suave lo que se parece menos, y este es un 100 %.
    assert nube == [{"precio": 77_720_000, "firme": True, "peso": 100}]


async def test_a_un_ex_jugador_no_se_le_busca_precio(base) -> None:
    """La tabla guarda a todo el que paso por el club: en la base real eran
    555 filas de este equipo y 530 de gente que ya salio. Sin filtrar, el
    paso les repartia turno y gastaba peticiones de CHPP buscandole
    comparables a quien ya no es tuyo (2026-10-07)."""
    session, equipo = base
    ido = (
        await session.execute(select(m.Player).where(m.Player.ht_player_id == GEMELO))
    ).scalar_one()
    ido.left_team_at = AHORA - timedelta(days=30)
    await session.flush()

    paso = await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i, puja=1_000_000) for i in range(6)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    assert GEMELO not in paso.jugadores_del_turno
    # Y tampoco se le anota un punto en la serie.
    suyos = (
        (
            await session.execute(
                select(m.MarketEstimate).where(m.MarketEstimate.ht_player_id == GEMELO)
            )
        )
        .scalars()
        .all()
    )
    assert suyos == []


async def test_al_que_solo_le_toca_el_exacto_gasta_una_sola_peticion(base) -> None:
    """Los dos ritmos, vistos desde el paso completo (2026-10-09).

    Al jugador del turno ANCHO se le recorre la escalera entera --hasta cinco
    peticiones-- y al que solo le toca su exacto, una. Es lo que hace que el
    coste no se multiplique por cinco al mirar el paso todos los dias.
    """
    session, equipo = base
    plantilla = await _plantilla(session, equipo.id)
    ids = [p.ht_player_id for p in plantilla]
    economica = await _fecha_economica(session, equipo)

    # Un dia en que a alguien le toque el exacto y a nadie los anchos.
    for dia in range(1, 40):
        cuando = AHORA + timedelta(days=dia)
        anchos = del_turno(ids, economica, cuando)
        exactos = del_turno_exacto(ids, cuando)
        if exactos and not anchos:
            break
    else:
        pytest.skip("no se encontro un dia con exacto y sin anchos")

    mercado = _MercadoFalso([_fila_de_mercado(900)])
    paso = await correr_el_paso_semanal(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=cuando
    )
    assert paso.jugadores_del_turno == tuple(sorted(exactos))
    # Una peticion por jugador y ni una mas: nadie recorrio la escalera.
    assert mercado.llamadas == len(exactos)


async def test_un_intento_al_dia_por_venta(base) -> None:
    """Regla del usuario, 2026-10-09: «un intento al dia por venta, posterior
    a la posible hora de cierre».

    Hace falta desde que se pregunta EN CUANTO pasa el plazo, sin margen. La
    resolucion corre en cada sincronizacion y la aplicacion permite seis por
    hora: sin el freno, las cinco oportunidades de una venta se gastaban en la
    primera hora tras el cierre --las cinco posteriores al cierre, las cinco
    legitimas-- y se abandonaba antes de que Hattrick publicara el traspaso.
    """
    session, equipo = base
    preguntas: list[int] = []

    async def historial(ht_player_id: int) -> dict[str, Any]:
        preguntas.append(ht_player_id)
        return {"transfers": []}  # Hattrick todavia no la ha registrado

    # Una venta en el fondo con la subasta ya cerrada.
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    cerrada = datetime.fromisoformat(PLAZO_HT).replace(tzinfo=UTC) + timedelta(minutes=5)

    # Cinco sincronizaciones el mismo dia: UNA sola pregunta.
    for minuto in range(0, 50, 10):
        await correr_el_paso_semanal(
            session,
            equipo,
            buscar=_MercadoFalso(),
            historial_de=historial,
            ahora=cerrada + timedelta(minutes=minuto),
        )
    assert len(preguntas) == 1, preguntas

    # Al dia siguiente, otra.
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso(),
        historial_de=historial,
        ahora=cerrada + timedelta(days=1),
    )
    assert len(preguntas) == 2


async def test_el_paso_barre_lo_de_mas_de_doce_semanas(base) -> None:
    """El barrido borra de verdad, una vez al dia (2026-10-09).

    Regla que el usuario trajo del Comparador de Transferencias de Hattrick:
    si no hay muestra, las ventas se borran hacia las doce semanas. Aqui se
    comprueba que se van de la TABLA, no solo del calculo: el fondo es
    material de trabajo, y lo que se conserva para la historia son las
    lecturas, que viven aparte en `market_estimates`.
    """
    session, equipo = base
    await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    antes = (
        (await session.execute(select(m.MarketSale).where(m.MarketSale.team_id == equipo.id)))
        .scalars()
        .all()
    )
    assert len(antes) == 1

    # Trece semanas despues: ni se busca para el, ni se queda.
    paso = await correr_el_paso_semanal(
        session,
        equipo,
        buscar=_MercadoFalso(),
        historial_de=_sin_historial,
        ahora=AHORA + timedelta(weeks=13),
    )
    assert paso.caducadas == 1
    quedan = (
        (await session.execute(select(m.MarketSale).where(m.MarketSale.team_id == equipo.id)))
        .scalars()
        .all()
    )
    assert quedan == []
