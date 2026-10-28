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

from app.application.commands.paso_del_mercado import (
    correr_el_paso_del_mercado,
)
from app.application.queries.precio_comparable import precio_de, precios_de_la_plantilla
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


#: Lo que devuelve el canario cuando el mercado contesta. El contenido da
#: igual --no se guarda, solo se cuenta-- pero no puede venir vacio, porque
#: vacio significa «Hattrick no esta contestando» y el barrido se cortaria.
CANTO = [{"ht_player_id": -1}]


class _MercadoFalso:
    """Un mercado de mentira que distingue al canario de una busqueda.

    EL CANARIO NO GASTA PAGINA, y tiene que ser asi o cada prueba perderia su
    primera respuesta: el paso le pregunta antes de empezar a buscar. Se
    reconoce por su peso --cero, que no es ningun escalon-- y se le contesta
    que si salvo que la prueba pida lo contrario.
    """

    def __init__(self, *paginas: list[dict[str, Any]], canario_mudo: bool = False) -> None:
        self.paginas = list(paginas)
        self.llamadas = 0
        self.canarios = 0
        self.canario_mudo = canario_mudo

    async def __call__(self, ventana: Ventana) -> list[dict[str, Any]]:
        if ventana.peso == 0:
            self.canarios += 1
            return [] if self.canario_mudo else CANTO
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
    paso = await correr_el_paso_del_mercado(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=AHORA
    )
    assert paso.se_busco is True
    assert paso.ventas_nuevas == OBJETIVO
    assert equipo.market_run_at == AHORA

    filas = (await session.execute(select(m.MarketSale))).scalars().all()
    assert len(filas) == OBJETIVO
    assert all(f.primary_skill == "scoring" and f.primary_level == 18 for f in filas)
    assert all(f.is_final is False for f in filas), "entran con la puja, no con el precio"


async def test_le_toca_a_TODA_la_plantilla(base) -> None:
    """2026-10-26: el barrido es diario y no rota.

    Antes le tocaba a una quinta parte por semana --el grupo salia del propio
    identificador-- y por eso aqui solo entraba Alberto.
    """
    session, equipo = base
    paso = await correr_el_paso_del_mercado(
        session, equipo, buscar=_MercadoFalso(), historial_de=_sin_historial, ahora=AHORA
    )
    assert sorted(paso.jugadores_barridos) == sorted([ALBERTO, GEMELO])


async def test_una_vez_corrido_no_se_repite_el_mismo_dia(base) -> None:
    """La economia principal: casi todas las sincronizaciones no gastan nada.

    Era «en la misma semana» hasta el 2026-10-09: la puerta paso a ser diaria
    porque el escalon exacto de cada jugador toca cada SEIS DIAS y con una
    puerta semanal el reloj de los seis dias solo veria un dia de cada siete.
    """
    session, equipo = base
    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    segundo = _MercadoFalso([_fila_de_mercado(950)])
    paso = await correr_el_paso_del_mercado(
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
    await correr_el_paso_del_mercado(
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
    despues = AHORA + timedelta(days=2)
    paso = await correr_el_paso_del_mercado(
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
    await correr_el_paso_del_mercado(
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
    await correr_el_paso_del_mercado(
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


async def test_la_plantilla_entera_en_una_sentada(base) -> None:
    """La tabla de «Mi Plantilla»: una fila por jugador, el fondo leido una vez.

    Es la version en plural, y defiende lo mismo que `precio_de` jugador a
    jugador defenderia veinticinco veces: el fondo es del EQUIPO. Si algun dia
    los dos caminos dejan de dar el mismo numero para el mismo jugador, esta
    prueba y la de al lado se contradicen, que es justo lo que se quiere.
    """
    session, equipo = base
    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i) for i in range(OBJETIVO)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    # Cinco de las ocho cierran; las otras tres siguen siendo puja. Se tocan
    # aqui a mano porque resolverlas de verdad pide historial por cada una, y
    # lo que esta prueba mira es el reparto, no la resolucion.
    guardadas = list((await session.execute(select(m.MarketSale))).scalars())
    for fila in guardadas[:5]:
        fila.is_final = True
        fila.price = 4_000_000
    await session.flush()

    plantilla = await precios_de_la_plantilla(session, equipo.id, AHORA)
    filas = {f.ht_player_id: f for f in plantilla.jugadores}
    assert set(filas) == {ALBERTO, GEMELO}, "los dos jugadores con foto"

    for ht_id in (ALBERTO, GEMELO):
        fila = filas[ht_id]
        # Los ocho anuncios son clavados a los dos --misma edad y las mismas
        # tres habilidades-- asi que los cinco que cerraron cuentan y pesan 100.
        assert (fila.n, fila.clavadas, fila.avaladas) == (5, 5, 0)
        assert fila.provisionales == 3, "las tres pujas se enseñan y no promedian"
        assert fila.media == fila.mediana == 4_000_000
        assert (fila.minimo, fila.maximo) == (4_000_000, 4_000_000)
        assert fila.faltan == OBJETIVO - 5
        assert [(r.habilidad, r.nivel) for r in fila.perfil] == [
            ("scoring", 18),
            ("passing", 13),
            ("playmaking", 7),
        ]

    # Y DA LO MISMO QUE LA FICHA, que es la razon de que exista en plural: dos
    # caminos al mismo numero acaban dando dos numeros distintos.
    uno = await precio_de(session, equipo.id, ALBERTO, AHORA)
    assert uno is not None
    assert (uno.media, uno.mediana, uno.n) == (
        filas[ALBERTO].media,
        filas[ALBERTO].mediana,
        filas[ALBERTO].n,
    )


async def test_sin_ventas_parecidas_la_fila_existe_y_el_precio_no(base) -> None:
    """«Las que hayan. Si no hay, no hay» --decision del usuario, 2026-10-27--.

    La fila NO desaparece: el jugador sigue en la tabla con su perfil y sin
    precio. Un cero ahi diria que no vale nada, y lo que pasa es que todavia no
    se sabe.
    """
    session, equipo = base
    plantilla = await precios_de_la_plantilla(session, equipo.id, AHORA)
    assert len(plantilla.jugadores) == 2
    for fila in plantilla.jugadores:
        assert fila.media is None and fila.mediana is None
        assert fila.minimo is None and fila.maximo is None
        assert (fila.n, fila.clavadas, fila.avaladas, fila.provisionales) == (0, 0, 0, 0)
        assert fila.serie == ()
        assert fila.nombre and fila.edad == 31, "el jugador sigue estando"


async def test_los_filtros_de_hattrick_viajan_a_la_pantalla(base) -> None:
    """POR QUE esas ventas y no otras, que es lo que la pantalla no podia decir.

    Los criterios son una funcion pura del dominio --la misma que decide si una
    venta lleva el sello-- asi que no cuestan ni una consulta ni una peticion.
    Se escriben aqui con sus numeros y no comparando contra `criterios_de`:
    comparar el motor consigo mismo pasaria igual si los dos estuvieran mal.

    Y viajan SIN FORMATEAR, igual que el perfil: la pantalla los nombra con el
    glosario oficial de Hattrick, que es el que sabe como se dice «scoring» en
    el idioma de quien mira.
    """
    session, equipo = base
    precio = await precio_de(session, equipo.id, ALBERTO, AHORA)
    assert precio is not None
    # Alberto: 31 anos, Anotacion 18, Pases 13, Jugadas 7, Balon parado 9.
    assert (precio.edad_minima, precio.edad_maxima) == (30, 32)
    assert [(c.habilidad, c.operador, c.minimo, c.maximo) for c in precio.criterios] == [
        ("scoring", "=", 18, 18),
        ("passing", "banda", 12, 14),
        ("playmaking", "banda", 6, 9),
        ("winger", "<=", 0, 5),
        ("defending", "<=", 0, 5),
        ("keeper", "<=", 0, 5),
    ]
    # El Balon parado NO es criterio de un jugador de campo aunque lo tenga a 9,
    # y eso es parte de lo que la pantalla tiene que poder decir.
    assert all(c.habilidad != "set_pieces" for c in precio.criterios)
    # El dial, con las cuentas a la vista: su rareza pasa del liston, asi que
    # Hattrick ensancha la ventana de edad y las bandas.
    assert precio.dial_holgado is True
    assert (precio.rareza, precio.liston) == (32, 27)
    assert precio.rareza >= precio.liston, "y por eso afloja"
    # El tope de dias es cosa de los 17 anos, no de los 31.
    assert precio.tope_de_dias is None


async def test_con_pocas_ventas_no_hay_numero_pero_si_lista(base) -> None:
    session, equipo = base
    await correr_el_paso_del_mercado(
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
    await correr_el_paso_del_mercado(
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
    despues = AHORA + timedelta(days=2)
    for _ in range(REINTENTOS_DE_RESOLUCION + 3):
        paso = await correr_el_paso_del_mercado(
            session, equipo, buscar=_MercadoFalso(), historial_de=se_cae, ahora=despues
        )
        assert paso.resueltas == ()

    fila = (await session.execute(select(m.MarketSale))).scalar_one()
    assert fila.resolve_attempts == 0, "un fallo de transporte no es un intento"
    assert fila.is_final is False

    # Y en cuanto CHPP vuelve, se resuelve: no se habia perdido nada.
    async def historial(ht_player_id: int) -> dict[str, Any]:
        return {"transfers": [{"deadline": PLAZO_HT, "price": 77_720_000}]}

    paso = await correr_el_paso_del_mercado(
        session, equipo, buscar=_MercadoFalso(), historial_de=historial, ahora=despues
    )
    assert [r.precio for r in paso.resueltas] == [77_720_000]


async def test_la_serie_anota_un_punto_cuando_el_numero_cambia(base) -> None:
    """`market_sales` sabe como esta el fondo AHORA, no como estuvo: al
    resolver una venta su puja se pisa con el precio de cierre. Sin anotar
    la lectura no hay forma de dibujar como fue cambiando."""
    session, equipo = base
    paso = await correr_el_paso_del_mercado(
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
    # Y lleva la nube, no solo la media: los seis precios que trajo la
    # busqueda, los seis sin cerrar. Son menos que OBJETIVO --que desde el
    # 2026-10-10 son ocho-- y por eso la lectura va sin numero.
    nube = json.loads(puntos[0].prices_json)
    assert len(nube) == 6
    assert all(p["firme"] is False for p in nube)
    assert {p["precio"] for p in nube} == {1_000_000}


async def test_la_serie_no_repite_un_punto_que_no_dice_nada_nuevo(base) -> None:
    """Un punto por CAMBIO y no por fecha. Anotando en cada sincronizacion,
    la serie seria una linea plana con cientos de puntos iguales y el tiempo
    entre dos puntos dejaria de significar algo."""
    session, equipo = base
    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i, puja=1_000_000) for i in range(6)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    antes = len((await session.execute(select(m.MarketEstimate))).scalars().all())

    # Otra sincronizacion sin nada que resolver y sin turno: nada cambia.
    paso = await correr_el_paso_del_mercado(
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
    await correr_el_paso_del_mercado(
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
    despues = AHORA + timedelta(days=2)
    paso = await correr_el_paso_del_mercado(
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

    paso = await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900 + i, puja=1_000_000) for i in range(6)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    assert GEMELO not in paso.jugadores_barridos
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


async def test_una_peticion_por_jugador_y_ni_una_mas(base) -> None:
    """EL GASTO, que es lo que decide si el barrido diario se puede hacer.

    Con la escalera ancha, un jugador costaba hasta cinco peticiones y por eso
    el turno era de cinco semanas. Con una sola ventana cuesta una, y por eso
    se puede mirar a todos todos los dias: una plantilla de veinticinco son
    unas veinticinco peticiones al dia contra una cuota que es de la
    APLICACION y no de cada manager.
    """
    session, equipo = base
    mercado = _MercadoFalso([_fila_de_mercado(900)])
    paso = await correr_el_paso_del_mercado(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=AHORA
    )
    assert len(paso.jugadores_barridos) == 2
    assert mercado.llamadas == 2, "una por jugador"
    # Mas el canario de apertura, que es lo unico que el centinela cuesta
    # cuando el mercado contesta.
    assert mercado.canarios == 1
    assert paso.busquedas == 3


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
    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    cerrada = datetime.fromisoformat(PLAZO_HT).replace(tzinfo=UTC) + timedelta(minutes=5)

    # Cinco sincronizaciones el mismo dia: UNA sola pregunta.
    for minuto in range(0, 50, 10):
        await correr_el_paso_del_mercado(
            session,
            equipo,
            buscar=_MercadoFalso(),
            historial_de=historial,
            ahora=cerrada + timedelta(minutes=minuto),
        )
    assert len(preguntas) == 1, preguntas

    # Al dia siguiente, otra.
    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso(),
        historial_de=historial,
        ahora=cerrada + timedelta(days=1),
    )
    assert len(preguntas) == 2




# --------------------------------------------------------------------------
# El centinela de la cuota, visto desde el paso entero
# --------------------------------------------------------------------------
#
# Una cuota agotada NO da error: devuelve cero resultados, igual que un jugador
# al que nadie se parece (medido el 2026-10-12). Con el barrido diario eso
# costaria el dia entero del mercado --es uno por dia-- y seguiria golpeando un
# servidor que no contesta, con una cuota que es de la aplicacion y no de cada
# manager.


async def test_un_canario_mudo_NO_BARRE_A_NADIE(base) -> None:
    """Y se para antes de gastar una sola busqueda.

    Es lo que el canario de apertura viene a hacer: que un dia sin cuota cueste
    una peticion y no veinticinco.
    """
    session, equipo = base
    mercado = _MercadoFalso([_fila_de_mercado(900)], canario_mudo=True)
    paso = await correr_el_paso_del_mercado(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=AHORA
    )
    assert paso.cuota_agotada is True
    assert paso.jugadores_barridos == ()
    assert mercado.llamadas == 0, "no se llego a buscarle a nadie"
    assert mercado.canarios == 1


async def test_con_la_cuota_muerta_EL_DIA_NO_SE_QUEMA(base) -> None:
    """La razon de ser del sello por jugador.

    Si el barrido se diera por hecho, ese dia del mercado no volveria: no hay
    segundo intento dentro del mismo dia. Como no se estampa nada, la
    siguiente sincronizacion lo reintenta entera.
    """
    session, equipo = base
    mudo = _MercadoFalso([_fila_de_mercado(900)], canario_mudo=True)
    await correr_el_paso_del_mercado(
        session, equipo, buscar=mudo, historial_de=_sin_historial, ahora=AHORA
    )
    sellos = (await session.execute(select(m.Player.market_swept_at))).scalars().all()
    assert all(s is None for s in sellos), "nadie puede quedar marcado como mirado"

    # Media hora despues, con Hattrick ya contestando: se barre de verdad.
    sano = _MercadoFalso([_fila_de_mercado(900)], [_fila_de_mercado(901)])
    paso = await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=sano,
        historial_de=_sin_historial,
        ahora=AHORA + timedelta(minutes=30),
    )
    assert paso.cuota_agotada is False
    assert len(paso.jugadores_barridos) == 2


async def test_barrer_de_verdad_SI_estampa_el_sello(base) -> None:
    """La otra mitad: lo que se miro queda marcado y no se repite hoy."""
    session, equipo = base
    paso = await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    assert len(paso.jugadores_barridos) == 2
    sellos = (await session.execute(select(m.Player.market_swept_at))).scalars().all()
    assert all(s is not None for s in sellos)


async def test_los_vacios_de_verdad_no_cortan_el_barrido(base) -> None:
    """Un mercado que contesta y no tiene a nadie parecido es lo NORMAL.

    La ventana exacta de un jugador raro casi nunca tiene a nadie, asi que si
    un vacio cortara el barrido no se podria barrer. Lo que para el barrido es
    que calle el canario, no que callen las busquedas.
    """
    session, equipo = base
    mercado = _MercadoFalso()  # ninguna pagina: todas las busquedas vuelven vacias
    paso = await correr_el_paso_del_mercado(
        session, equipo, buscar=mercado, historial_de=_sin_historial, ahora=AHORA
    )
    assert paso.cuota_agotada is False
    assert len(paso.jugadores_barridos) == 2
    assert paso.ventas_nuevas == 0


# --------------------------------------------------------------------------
# La grafica vuelve a empezar cuando cambian los criterios
# --------------------------------------------------------------------------


async def test_al_cambiarle_los_criterios_la_SERIE_EMPIEZA_DE_NUEVO(base) -> None:
    """2026-10-26: «en ese caso, la grafica de precios volvera a empezar».

    Se le barre, cumple años, se le vuelve a barrer. Los puntos de antes siguen
    en la tabla --no se borra nada, que es la unica perdida de esta base que no
    se podria deshacer-- pero la pantalla enseña solo el tramo vigente: desde
    que cambio la ventana se le esta comparando con OTRA gente, y unir las dos
    medidas con una linea dibujaria una subida que no ocurrio.
    """
    from app.application.queries.precio_comparable import _serie

    session, equipo = base
    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(900, puja=5_000_000)]),
        historial_de=_sin_historial,
        ahora=AHORA,
    )
    de_antes = (
        (
            await session.execute(
                select(m.MarketEstimate).where(m.MarketEstimate.ht_player_id == ALBERTO)
            )
        )
        .scalars()
        .all()
    )
    assert de_antes, "tiene que haber dejado al menos un punto"
    clave_vieja = de_antes[0].criteria_key
    assert clave_vieja, "el punto nuevo lleva clave"

    # Cumple años: otra foto, un año mas. Hattrick recalcula su ventana de edad
    # con el, asi que desde aqui el barrido pregunta por otra gente.
    jugador = (
        await session.execute(select(m.Player).where(m.Player.ht_player_id == ALBERTO))
    ).scalar_one()
    jugador.market_swept_at = None  # para que le vuelva a tocar
    sync = (await session.execute(select(m.Sync))).scalars().first()
    assert sync is not None
    manana = AHORA + timedelta(days=1)
    session.add(
        m.PlayerSnapshot(
            sync_id=sync.id,
            player_id=jugador.id,
            captured_at=manana,
            age_years=32,
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
    await session.flush()

    await correr_el_paso_del_mercado(
        session,
        equipo,
        buscar=_MercadoFalso([_fila_de_mercado(901, puja=5_000_000)]),
        historial_de=_sin_historial,
        ahora=manana,
    )

    todas = (
        (
            await session.execute(
                select(m.MarketEstimate)
                .where(m.MarketEstimate.ht_player_id == ALBERTO)
                .order_by(m.MarketEstimate.captured_at)
            )
        )
        .scalars()
        .all()
    )
    claves = [f.criteria_key for f in todas]
    assert len(set(claves)) == 2, f"tienen que ser dos tramos: {claves}"
    assert claves[-1] != clave_vieja

    # Y la pantalla enseña SOLO el tramo nuevo, aunque los viejos sigan ahi.
    serie = await _serie(session, equipo.id, ALBERTO, lambda x: x)
    cuantos_del_tramo = sum(1 for k in claves if k == claves[-1])
    assert len(serie) == cuantos_del_tramo
    assert len(serie) < len(todas), "lo de antes no se borra, solo no se pinta"


async def test_sin_cambio_de_criterios_la_serie_NO_se_corta(base) -> None:
    """Que lo de arriba no haya convertido cada barrido en un tramo nuevo."""
    from app.application.queries.precio_comparable import _serie

    session, equipo = base
    for dia, anuncio in enumerate([900, 901, 902]):
        jugadores = (await session.execute(select(m.Player))).scalars().all()
        for j in jugadores:
            j.market_swept_at = None
        await session.flush()
        await correr_el_paso_del_mercado(
            session,
            equipo,
            buscar=_MercadoFalso([_fila_de_mercado(anuncio, puja=1_000_000 * (dia + 1))]),
            historial_de=_sin_historial,
            ahora=AHORA + timedelta(days=dia),
        )
    todas = (
        (
            await session.execute(
                select(m.MarketEstimate).where(m.MarketEstimate.ht_player_id == ALBERTO)
            )
        )
        .scalars()
        .all()
    )
    assert len({f.criteria_key for f in todas}) == 1, "un solo tramo"
    serie = await _serie(session, equipo.id, ALBERTO, lambda x: x)
    assert len(serie) == len(todas)
    assert len(serie) >= 2, "y la serie de verdad tiene varios puntos"
