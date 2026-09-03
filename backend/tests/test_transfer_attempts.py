"""Cada intento de venta, con su final.

2026-08-22, pedido por el usuario. Antes la app solo contaba cuántas veces se
había listado a alguien; un intento de venta tiene además un plazo, un
resultado y un dato que Hattrick NO entrega por CHPP: cuántas veces miraron al
jugador. Eso solo aparece en el texto de la noticia al cerrarse la puja, así
que lo teclea el usuario.
"""
import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import require_team_owner
from app.application.queries import transfer_attempts as transfer_attempts_query
from app.application.queries.transfer_attempts import TransferAttemptsQueryService
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


def _montar() -> tuple[TestClient, int, int, int]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def preparar() -> tuple[int, int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            equipo = m.Team(
                ht_team_id=537758, name="Pulgas Arrechas",
                currency_name="US$", currency_rate=10.0,
            )
            s.add(equipo)
            await s.flush()
            jugador = m.Player(
                ht_player_id=1, team_id=equipo.id,
                first_name="Stănel", last_name="Didoiu",
            )
            s.add(jugador)
            await s.flush()
            terminado = m.PlayerListingAttempt(
                player_id=jugador.id, ht_player_id=1,
                detected_at=datetime(2026, 8, 19, 8, 0),
                deadline=datetime(2026, 8, 22, 8, 1),
                ended_at=datetime(2026, 8, 22, 8, 5),
                sold=False, last_highest_bid=None,
            )
            abierto = m.PlayerListingAttempt(
                player_id=jugador.id, ht_player_id=1,
                detected_at=datetime(2026, 8, 23, 9, 0),
                deadline=datetime(2026, 8, 26, 9, 0),
                last_highest_bid=7230000,
            )
            s.add_all([terminado, abierto])
            await s.commit()
            return equipo.id, terminado.id, abierto.id

    team_id, terminado, abierto = asyncio.run(preparar())

    async def sesion() -> Any:
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[require_team_owner] = lambda: None
    return TestClient(app), team_id, terminado, abierto


def test_each_attempt_is_a_row_with_its_own_ending() -> None:
    client, team_id, terminado, abierto = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert len(cuerpo["rows"]) == 2

        por_id = {r["id"]: r for r in cuerpo["rows"]}
        assert por_id[terminado]["open"] is False
        assert por_id[terminado]["sold"] is False
        assert por_id[abierto]["open"] is True
        # La puja llega en moneda local, como el resto de la pantalla.
        assert por_id[abierto]["highestBid"] == 723000
    finally:
        app.dependency_overrides.clear()


def test_an_open_attempt_uses_a_utc_naive_cutoff(monkeypatch) -> None:
    """La BD entrega UTC sin tzinfo: el reloj debe pedir UTC explicitamente y
    quitar la zona, no interpretar la hora local del servidor como UTC."""
    calls: list[object] = []

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            return cls(2026, 8, 25, 12, 0, tzinfo=tz)

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            team = m.Team(ht_team_id=537_758, name="Pulgas Arrechas")
            s.add(team)
            await s.flush()
            player = m.Player(
                ht_player_id=99,
                team_id=team.id,
                first_name="Puja",
                last_name="Abierta",
            )
            s.add(player)
            await s.flush()
            s.add(
                m.PlayerListingAttempt(
                    player_id=player.id,
                    ht_player_id=player.ht_player_id,
                    detected_at=datetime(2026, 8, 24),
                    deadline=None,
                    ended_at=None,
                )
            )
            await s.commit()
            team_id = team.id

        monkeypatch.setattr(transfer_attempts_query, "datetime", FrozenDateTime)
        async with factory() as s:
            response = await TransferAttemptsQueryService(s).get(team_id)
        assert response is not None
        assert len(response.rows) == 1

    asyncio.run(run())
    assert calls == [UTC]


def test_attempt_salary_never_uses_a_snapshot_from_a_later_stint() -> None:
    """El primer snapshot futuro sigue siendo valido, pero solo si cae dentro
    del intervalo de la etapa cuyo intento se esta describiendo."""
    async def run() -> tuple[int | str, int | str]:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            team = m.Team(ht_team_id=537_758, name="Pulgas Arrechas")
            s.add(team)
            await s.flush()
            player = m.Player(
                ht_player_id=100,
                team_id=team.id,
                first_name="Dos",
                last_name="Etapas",
            )
            s.add(player)
            sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=datetime(2026, 2, 2),
            )
            s.add(sync)
            await s.flush()
            s.add(
                m.PlayerSnapshot(
                    sync_id=sync.id,
                    player_id=player.id,
                    captured_at=datetime(2026, 2, 2),
                    age_years=20,
                    age_days=1,
                    tsi=1_000,
                    form=5,
                    stamina=5,
                    experience=5,
                    salary=9_000,
                    content_hash=b"later-stint",
                )
            )
            await s.commit()

            service = TransferAttemptsQueryService(s)
            convert = lambda value: value  # noqa: E731
            old = await service._salario_hasta(
                player,
                datetime(2026, 1, 1),
                datetime(2026, 1, 10),
                datetime(2026, 1, 3),
                convert,
            )
            recent = await service._salario_hasta(
                player,
                datetime(2026, 2, 1),
                datetime(2026, 2, 5),
                datetime(2026, 1, 3),
                convert,
            )
            return old, recent

    old, recent = asyncio.run(run())
    assert old == "?"
    # La foto del 2 de febrero es futura respecto a la compra del 1, pero
    # pertenece a esa misma etapa y respalda su pago inmediato.
    assert recent == 9_000


def test_only_finished_attempts_without_an_answer_are_asked_about() -> None:
    """El aviso es para lo que ya no se puede averiguar de otra forma. Una puja
    todavía abierta no tiene visitas que contar, y una ya respondida tampoco
    debe volver a preguntarse."""
    client, team_id, terminado, abierto = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        pendientes = [r["id"] for r in cuerpo["pendingQuestion"]]
        assert pendientes == [terminado]
        assert abierto not in pendientes
    finally:
        app.dependency_overrides.clear()


def test_the_user_can_write_down_the_visits() -> None:
    """Del mensaje real de Hattrick: "este jugador fue visto 8 veces mientras
    estaba en la lista de transferibles"."""
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}",
            json={"times_seen": 8},
        )
        assert r.status_code == 200
        assert r.json()["timesSeen"] == 8

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert cuerpo["pendingQuestion"] == []
    finally:
        app.dependency_overrides.clear()


def test_ignoring_the_question_stops_it_from_coming_back() -> None:
    """Se puede no contestar. Lo que no puede pasar es que el aviso vuelva a
    salir en cada visita a Cambios."""
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}",
            json={"dismissed": True},
        )
        assert r.status_code == 200
        assert r.json()["timesSeen"] is None
        assert r.json()["asked"] is True

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert cuerpo["pendingQuestion"] == []
    finally:
        app.dependency_overrides.clear()


def test_an_attempt_of_another_team_is_not_reachable() -> None:
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id + 99}/transfer-attempts/{terminado}",
            json={"times_seen": 3},
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_attempts_that_missed_their_closing_moment_get_repaired() -> None:
    """La regla normal de cierre se dispara en la TRANSICIÓN: estaba listado, ya
    no lo está. Los intentos anteriores a esa regla se perdieron ese instante y
    quedaban abiertos para siempre — en la cuenta del usuario, 15 figuraban "en
    el mercado" cuando solo 4 jugadores lo estaban.

    La reparación cierra cada uno con lo mejor que se sepa, sin inventar fechas.
    """
    from app.application.commands.sync_team import SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            vendido = m.Player(
                ht_player_id=1, team_id=equipo.id, first_name="Se", last_name="Vendio",
                sold_at=datetime(2026, 7, 5), sale_price=500000,
                left_team_at=datetime(2026, 7, 5),
            )
            relistado = m.Player(
                ht_player_id=2, team_id=equipo.id, first_name="Se", last_name="Quedo",
            )
            s.add_all([vendido, relistado])
            await s.flush()
            # La salida buena es la de SU etapa: un jugador que se vendió y
            # volvió tiene una venta vieja en su ficha que no tiene nada que
            # ver con el intento que se está cerrando.
            s.add(m.PlayerStint(
                player_id=vendido.id, ht_player_id=1, team_id=equipo.id,
                arrived_at=datetime(2026, 1, 1), arrival_price=100000,
                left_at=datetime(2026, 7, 5), sale_price=500000,
            ))
            s.add_all([
                # Salió al mercado y acabó vendido.
                m.PlayerListingAttempt(
                    player_id=vendido.id, ht_player_id=1,
                    detected_at=datetime(2026, 6, 30),
                ),
                # Dos intentos del mismo: el primero tuvo que acabar antes del
                # segundo.
                m.PlayerListingAttempt(
                    player_id=relistado.id, ht_player_id=2,
                    detected_at=datetime(2026, 8, 1),
                ),
                m.PlayerListingAttempt(
                    player_id=relistado.id, ht_player_id=2,
                    detected_at=datetime(2026, 8, 10),
                ),
            ])
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            cerrados = await handler._reparar_intentos_abiertos(u, team_id, set())
            await u.commit()
        assert cerrados == 3

        async with factory() as s:
            intentos = (await s.execute(
                select(m.PlayerListingAttempt).order_by(m.PlayerListingAttempt.detected_at)
            )).scalars().all()
            # El que se vendió cierra el día de la venta, y como vendido.
            assert intentos[0].ended_at == datetime(2026, 7, 5)
            assert intentos[0].sold is True
            # El primero del otro cierra cuando volvió a salir al mercado.
            assert intentos[1].ended_at == datetime(2026, 8, 10)
            assert intentos[1].sold is False
            # Y el último, con lo único seguro: hoy ya no está listado.
            assert intentos[2].ended_at is not None
            assert intentos[2].sold is False
            # El plazo real nunca se vio: no se inventa.
            assert all(i.deadline is None for i in intentos)

    asyncio.run(run())


def test_a_player_still_listed_today_is_left_alone() -> None:
    """La reparación no puede cerrar una puja que sigue viva."""
    from app.application.commands.sync_team import SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            jugador = m.Player(
                ht_player_id=7, team_id=equipo.id, first_name="En", last_name="Venta",
            )
            s.add(jugador)
            await s.flush()
            s.add(m.PlayerListingAttempt(
                player_id=jugador.id, ht_player_id=7, detected_at=datetime(2026, 8, 20),
            ))
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            cerrados = await handler._reparar_intentos_abiertos(u, team_id, {7})
            await u.commit()
        assert cerrados == 0

        async with factory() as s:
            intento = await s.scalar(select(m.PlayerListingAttempt))
            assert intento.ended_at is None

    asyncio.run(run())


def test_who_is_on_sale_comes_from_the_squad_not_from_the_bids() -> None:
    """2026-08-22, pedido explícitamente: `currentbids.xml` es la lista de
    PUJAS, y tomarlo por un censo de transferibles es la forma de equivocarse.

    `TransferListed` viene con la plantilla, jugador por jugador, y responde
    directo a la pregunta. Aquí se comprueba que ESA es la fuente: un jugador
    marcado como transferible en su snapshot queda listado aunque no aparezca
    en ninguna puja.
    """
    from app.application.commands.sync_team import SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        captura = datetime(2026, 8, 22, 12, 0)
        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            en_venta = m.Player(
                ht_player_id=1, team_id=equipo.id, first_name="Sin", last_name="Pujas",
            )
            normal = m.Player(
                ht_player_id=2, team_id=equipo.id, first_name="No", last_name="Listado",
            )
            s.add_all([en_venta, normal])
            await s.flush()
            sync = m.Sync(
                user_id=1, team_id=equipo.id, kind="players", status="completed",
                started_at=captura,
            )
            s.add(sync)
            await s.flush()
            for jugador, listado in ((en_venta, True), (normal, False)):
                s.add(m.PlayerSnapshot(
                    sync_id=sync.id, player_id=jugador.id, captured_at=captura,
                    age_years=25, age_days=0, tsi=1000, form=5, stamina=5,
                    experience=5, salary=1000, content_hash=b"x",
                    is_transfer_listed=listado,
                ))
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            await handler._marcar_quien_esta_en_venta(u, team_id, captura)
            await u.commit()

        async with factory() as s:
            uno = await s.scalar(select(m.Player).where(m.Player.ht_player_id == 1))
            dos = await s.scalar(select(m.Player).where(m.Player.ht_player_id == 2))
            # Sin una sola puja, y aun asi en venta.
            assert uno.currently_listed is True
            assert dos.currently_listed is False

    asyncio.run(run())


def test_the_asking_price_travels_with_the_visits() -> None:
    """Del mensaje real: "El precio solicitado era de 723 000 US$". Tampoco lo
    da CHPP, así que se teclea junto a las visitas y en la misma moneda que lee
    el usuario."""
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}",
            json={"times_seen": 8, "asking_price": 723000},
        )
        assert r.status_code == 200
        assert r.json()["askingPrice"] == 723000

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        fila = next(f for f in cuerpo["rows"] if f["id"] == terminado)
        assert fila["askingPrice"] == 723000
        assert fila["timesSeen"] == 8
    finally:
        app.dependency_overrides.clear()


def test_the_key_is_the_player_and_the_attempt_number() -> None:
    """`IDdelJugador_intento`, con el número creciendo por jugador."""
    client, team_id, terminado, abierto = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        por_id = {f["id"]: f for f in cuerpo["rows"]}
        assert por_id[terminado]["key"] == "1_1"
        assert por_id[abierto]["key"] == "1_2"
        assert por_id[abierto]["attemptNumber"] == 2
    finally:
        app.dependency_overrides.clear()


def test_the_agent_only_charges_when_there_was_a_sale() -> None:
    """En un intento fallido no hay agente que cobre: la casilla queda vacía,
    no en cero, que se leería como "no cobró"."""
    client, team_id, terminado, _ = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        fila = next(f for f in cuerpo["rows"] if f["id"] == terminado)
        assert fila["sold"] is False
        assert fila["agentPct"] == "?"
    finally:
        app.dependency_overrides.clear()


def test_a_photo_far_from_the_closing_is_flagged() -> None:
    """El estado del jugador sale de la foto más cercana al cierre. Si esa foto
    es de días antes, el TSI y las habilidades ya no son las de ese día: se
    marca para que no se lean como exactas."""
    client, team_id, terminado, _ = _montar()
    try:
        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        fila = next(f for f in cuerpo["rows"] if f["id"] == terminado)
        # Sin ninguna foto tampoco se inventa nada.
        assert fila["stale"] is True
        assert fila["tsi"] == "?"
        assert fila["skills"]["scoring"] == "?"
    finally:
        app.dependency_overrides.clear()


def test_saying_i_do_not_know_keeps_the_row_with_question_marks() -> None:
    """Los tres botones del aviso, tal como los definió el usuario:

    - «Guardar» deja la fila con lo que escribió.
    - «No sé» deja la fila igual, pero con "?" en lo que se preguntaba.
    - «No tener en cuenta» la borra, como si nunca hubiera llegado a la lista.

    Lo que este test protege es el del medio: no contestar no puede perder el
    intento, solo el dato.
    """
    client, team_id, terminado, _ = _montar()
    try:
        r = client.patch(
            f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}",
            json={"dismissed": True},
        )
        assert r.status_code == 200
        assert r.json()["timesSeen"] is None
        assert r.json()["askingPrice"] is None

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        fila = next(f for f in cuerpo["rows"] if f["id"] == terminado)
        # Sigue en la tabla, con sus huecos.
        assert fila["timesSeen"] is None
        assert fila["askingPrice"] is None
        # Y ya no se vuelve a preguntar.
        assert all(p["id"] != terminado for p in cuerpo["pendingQuestion"])
    finally:
        app.dependency_overrides.clear()

def test_an_attempt_can_be_deleted_for_good() -> None:
    client, team_id, terminado, abierto = _montar()
    try:
        r = client.delete(f"/api/v1/teams/{team_id}/transfer-attempts/{terminado}")
        assert r.status_code == 200

        cuerpo = client.get(f"/api/v1/teams/{team_id}/transfer-attempts").json()
        assert [f["id"] for f in cuerpo["rows"]] == [abierto]
        # Y el que queda pasa a ser el primer intento de ese jugador.
        assert cuerpo["rows"][0]["attemptNumber"] == 1
    finally:
        app.dependency_overrides.clear()


def test_deleting_an_attempt_of_another_team_is_refused() -> None:
    client, team_id, terminado, _ = _montar()
    try:
        r = client.delete(
            f"/api/v1/teams/{team_id + 99}/transfer-attempts/{terminado}"
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_a_player_who_is_no_longer_ours_cannot_be_on_our_market() -> None:
    """`currentbids.xml` no es la lista de lo que TU vendes: es la de las pujas
    en las que andas metido, incluidas las que haces por jugadores de otros.
    Por eso un ex-jugador tuyo puede aparecer ahi -estas pujando por
    recomprarlo- sin estar en tu plantilla.

    Caso real: Gabriel Cecilio Acasusso, vendido en julio, seguia figurando "en
    venta" en agosto. La plantilla de hoy es la que manda: quien no esta en
    ella no puede estar en venta por nosotros.
    """
    from app.application.commands.sync_team import SyncTeamHandler
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

    async def run() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        captura = datetime(2026, 8, 22, 12, 0)
        async with factory() as s:
            equipo = m.Team(ht_team_id=537758, name="Pulgas Arrechas")
            s.add(equipo)
            await s.flush()
            # Se fue hace meses, pero quedo marcado como "en venta".
            ido = m.Player(
                ht_player_id=1, team_id=equipo.id, first_name="Ya", last_name="Vendido",
                sold_at=datetime(2026, 7, 5), left_team_at=datetime(2026, 7, 5),
                currently_listed=True,
            )
            actual = m.Player(
                ht_player_id=2, team_id=equipo.id, first_name="En", last_name="Plantilla",
            )
            s.add_all([ido, actual])
            await s.flush()
            sync = m.Sync(
                user_id=1, team_id=equipo.id, kind="players", status="completed",
                started_at=captura,
            )
            s.add(sync)
            await s.flush()
            # Solo el que sigue en el club deja foto hoy.
            s.add(m.PlayerSnapshot(
                sync_id=sync.id, player_id=actual.id, captured_at=captura,
                age_years=25, age_days=0, tsi=1000, form=5, stamina=5,
                experience=5, salary=1000, content_hash=b"x",
                is_transfer_listed=True,
            ))
            await s.commit()
            team_id = equipo.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, None)  # type: ignore[arg-type]
        async with uow as u:
            await handler._marcar_quien_esta_en_venta(u, team_id, captura)
            await u.commit()

        async with factory() as s:
            ido = await s.scalar(select(m.Player).where(m.Player.ht_player_id == 1))
            actual = await s.scalar(select(m.Player).where(m.Player.ht_player_id == 2))
            assert ido.currently_listed is False, "ya no es nuestro"
            assert actual.currently_listed is True

    asyncio.run(run())
