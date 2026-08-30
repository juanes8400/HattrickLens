"""El boton de Transferencias atiende primero a los mas recientes.

2026-08-24. Se ordenaron las consultas de `pendientes_de_ficha` y no basto:
el consumidor hacia `sorted(ficha | precio | ...)` sobre la UNION DE
CONJUNTOS, y eso ordena por numero de jugador, que sube con la antiguedad.
El lote empezaba siempre por los mas viejos.

Esta prueba mira lo que hace el BOTON, no lo que devuelve la consulta: es la
unica forma de que el fallo no vuelva a colarse por el mismo sitio.
"""
import asyncio
import json
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamHandler
from app.infrastructure.db import models as m
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork


class CHPPMudo:
    """No hace falta que responda nada: lo que se mide es a QUIEN se pregunta."""

    async def fetch(self, file: str, version: str = "latest", **params: Any) -> dict:
        return {}


VENTAS = [
    ("Viejo", 900_000_001, datetime(2020, 9, 10)),
    ("Medio", 900_000_002, datetime(2024, 7, 16)),
    ("Reciente", 900_000_003, datetime(2026, 8, 20)),
]


async def _monta() -> tuple[SqlAlchemyUnitOfWork, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(m.Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        equipo = m.Team(ht_team_id=1, name="Pulgas Arrechas")
        s.add(equipo)
        await s.flush()
        for apellido, ht_id, vendido in VENTAS:
            s.add(m.Player(
                team_id=equipo.id, ht_player_id=ht_id,
                first_name="Ex", last_name=apellido,
                sold_at=vendido, purchased_at=datetime(2018, 1, 1),
                purchase_price=1000,
            ))
        await s.commit()
        return SqlAlchemyUnitOfWork(factory), equipo.id


def test_el_lote_empieza_por_la_venta_mas_reciente() -> None:
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 24), result,
            )
            await uow.commit()

        # `players_named` guarda los nombres completos en el orden en que se
        # atendieron, que es justo lo que hay que comprobar.
        # 2026-08-25: la alternancia corre SIEMPRE --uno reciente, uno al
        # azar-- porque lo viejo es lo que cierra expedientes: los
        # entrenadores estan entre las ventas de hace años. Lo que se fija es
        # que el PRIMERO sea el mas reciente y que no se pierda a nadie.
        assert result.players_named[0] == "Ex Reciente"
        assert sorted(result.players_named) == ["Ex Medio", "Ex Reciente", "Ex Viejo"]

    asyncio.run(corre())


def test_el_limite_se_lleva_a_los_mas_recientes() -> None:
    """Con lotes de uno, el numero 1 no puede ser el de 2020."""
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 24), result, limite=1,
            )
            await uow.commit()
        assert result.players_named == ["Ex Reciente"]

    asyncio.run(corre())


def test_con_comision_por_atribuir_el_lote_alterna() -> None:
    """El boton de Transferencias, persiguiendo: uno reciente, uno al azar.

    2026-08-24. La senal sale de la economia YA GUARDADA --el boton de arriba
    la trajo-- asi que este boton no le pide nada a Hattrick para saberlo.
    """
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        # Una comision que nadie ha atribuido todavia.
        async with uow:
            usuario = m.User(ht_user_id=1, login_name="yo")
            uow.session.add(usuario)
            await uow.session.flush()
            sync = m.Sync(user_id=usuario.id, team_id=team_id, kind="economy",
                          status="completed", started_at=datetime(2026, 8, 24))
            uow.session.add(sync)
            await uow.session.flush()
            obligatorias = {
                c: 0 for c in (
                    "sponsors_popularity", "supporters_popularity", "fan_club_size",
                    "income_spectators", "income_sponsors", "income_financial",
                    "income_sum", "costs_arena", "costs_players", "costs_financial",
                    "costs_staff", "costs_youth", "costs_sum", "expected_weeks_total",
                    "last_income_sum", "last_costs_sum", "last_weeks_total",
                )
            }
            uow.session.add(m.EconomySnapshot(
                sync_id=sync.id, team_id=team_id,
                captured_at=datetime(2026, 8, 24), cash=0, expected_cash=0,
                income_sold_players_commission=183_600,
                last_income_sold_players_commission=0,
                content_hash=b"e" * 32, **obligatorias,
            ))
            await uow.commit()

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 24), result,
            )
            await uow.commit()

        async with uow:
            equipo = await uow.session.get(m.Team, team_id)
            probados = equipo.commission_tried_json

        # La caceria se abrio sola con el dinero guardado, y al probarlos a
        # todos sin encontrar nada se cerro. La lista se vacia para que el
        # siguiente barrido empiece de cero.
        assert probados == "[]"
        assert equipo.commission_hunting is False
        assert result.players_named[0] == "Ex Reciente", (
            "aun persiguiendo, el primero es el mas reciente"
        )

    asyncio.run(corre())


def test_sin_comision_pendiente_tambien_alterna() -> None:
    """2026-08-25, pedido asi. Lo reciente es lo que PAGA; lo viejo es lo que
    CIERRA expedientes --los entrenadores estan entre las ventas de hace
    años--. Con recencia pura, el unico entrenador localizado en la cuenta
    real estaba en el puesto 210 de 218.
    """
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            equipo = await uow.session.get(m.Team, team_id)
            assert equipo.commission_hunting is False, "sin dinero por atribuir"
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 24), result, limite=2,
            )
            await uow.commit()

        # Dos de tres: el mas reciente y uno al azar de los que quedan.
        assert result.players_named[0] == "Ex Reciente"
        assert result.players_named[1] in ("Ex Medio", "Ex Viejo")
        assert len(result.players_named) == 2

    asyncio.run(corre())


def test_cada_respuesta_trae_el_barrido_ENTERO() -> None:
    """No solo lo de esta pulsacion: todo lo que va hecho.

    2026-08-25. Lo acumulaba el navegador, y por eso se perdia al recargar la
    pagina. Ahora el eje se congela al empezar el barrido, lo hecho se deduce
    de la base --quien tiene revision posterior al arranque-- y el mapa llega
    entero en cada respuesta.
    """
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        pulsacion = datetime(2026, 8, 25, 6, 0)
        mapas = []
        for _ in range(3):
            result = SyncResult(sync_id=1, status="running")
            async with uow:
                await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                    uow, team_id, datetime(2026, 8, 25), result,
                    limite=1, revisar_desde=pulsacion,
                )
                await uow.commit()
            assert result.queue_map is not None
            mapas.append(result.queue_map)

        assert [m.total for m in mapas] == [3, 3, 3], (
            "el eje se congela: no puede encogerse a mitad del barrido"
        )
        assert [len(m.hechas) for m in mapas] == [1, 2, 3]
        for antes, despues in zip(mapas, mapas[1:]):
            assert set(antes.hechas) < set(despues.hechas), (
                "nada de lo ya hecho se apaga"
            )
        assert mapas[0].hechas == [0], "el primero es la cabeza de la cola"
        assert mapas[-1].frente == 3, "barrido completo, barra llena"

    asyncio.run(corre())


def test_quien_no_se_mira_nunca_no_ocupa_casilla_en_la_barra() -> None:
    """El hueco de la izquierda que no se llenaba nunca, 2026-08-25.

    Quien lleva prestado el numero de su transferencia no tiene ficha en
    CHPP, asi que ninguna cola lo mira --las colas ya lo excluian--. El eje
    de la barra no lo excluia: en la cuenta real eran 67 de 266 casillas
    inalcanzables, y DIECISEIS de ellas las primeras, de modo que el bloque
    solido no podia arrancar aunque el barrido fuera perfecto.
    """
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        # Uno mas reciente que todos, pero con el numero prestado.
        async with uow:
            uow.session.add(m.Player(
                team_id=team_id, ht_player_id=900_000_009,
                first_name="Numero", last_name="Prestado",
                sold_at=datetime(2026, 8, 23), purchased_at=datetime(2018, 1, 1),
                purchase_price=1000, ht_player_id_is_transfer=True,
            ))
            await uow.commit()

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 25), result,
                limite=1, revisar_desde=datetime(2026, 8, 25, 6, 0),
            )
            await uow.commit()

        assert result.players_named == ["Ex Reciente"], "a ese no se le pregunta"
        assert result.queue_map is not None
        assert result.queue_map.total == 3, "no ocupa casilla"
        assert result.queue_map.hechas == [0], (
            "y por eso el frente puede arrancar en la casilla 0"
        )

    asyncio.run(corre())


def test_un_barrido_nuevo_no_hereda_la_lista_de_probados() -> None:
    """La causa de "sigue llenando de izquierda a derecha", 2026-08-25.

    `commission_tried_json` sobrevivia de un barrido al siguiente, asi que la
    busqueda saltaba a jugadores que el EJE seguia contando. Sus casillas
    quedaban muertas y, estando al principio, el frente no arrancaba nunca:
    en la cuenta real las casillas 0, 1 y 2 estaban ocupadas por tres
    ex-jugadores ya apuntados, y lo unico que crecia era el racimo de marcas
    pegado a la izquierda.

    El eje se congela por barrido; la lista de probados tiene que decir lo
    mismo, asi que se vacia con el. Repetir a alguien dentro del mismo barrido
    lo sigue impidiendo `revisar_desde`.
    """
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        # Un barrido anterior dejo apuntada a la cabeza de la cola.
        async with uow:
            equipo = await uow.session.get(m.Team, team_id)
            equipo.commission_tried_json = json.dumps([900_000_003])
            await uow.commit()

        result = SyncResult(sync_id=1, status="running")
        async with uow:
            await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                uow, team_id, datetime(2026, 8, 25), result,
                limite=1, revisar_desde=datetime(2026, 8, 25, 6, 0),
            )
            await uow.commit()

        assert result.players_named == ["Ex Reciente"], (
            "la cabeza vuelve a la cola: el barrido nuevo empieza por ella"
        )
        assert result.queue_map is not None
        assert result.queue_map.hechas == [0]
        assert result.queue_map.frente == 1, "y por eso el bloque puede arrancar"

    asyncio.run(corre())


def test_dentro_del_mismo_barrido_nadie_se_repite() -> None:
    """Vaciar la lista de probados no puede costar llamadas repetidas.

    No las cuesta: `revisar_desde` saca de la cola a quien ya se miro en esta
    pasada, que es una razon mas solida --sale de la base, no de un contador
    que se puede vaciar--.
    """
    async def corre() -> None:
        uow, team_id = await _monta()
        from app.application.commands.sync_team import SyncResult

        pulsacion = datetime(2026, 8, 25, 6, 0)
        atendidos = []
        for _ in range(3):
            result = SyncResult(sync_id=1, status="running")
            async with uow:
                await SyncTeamHandler(uow, CHPPMudo())._backfill_sold_player_details(
                    uow, team_id, datetime(2026, 8, 25), result,
                    limite=1, revisar_desde=pulsacion,
                )
                await uow.commit()
            atendidos += result.players_named

        assert sorted(atendidos) == ["Ex Medio", "Ex Reciente", "Ex Viejo"], (
            "los tres, cada uno una vez"
        )

    asyncio.run(corre())
