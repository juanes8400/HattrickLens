import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.changes_history import build_changes_history
from app.infrastructure.db import models as m


def _snapshot(sync_id: int, player_id: int, captured_at: datetime, **updates):
    values = {
        "sync_id": sync_id,
        "player_id": player_id,
        "captured_at": captured_at,
        "age_years": 25,
        "age_days": 0,
        "tsi": 10_000,
        "form": 5,
        "stamina": 7,
        "experience": 4,
        "loyalty": 5,
        # Liderazgo empieza en 1 en Hattrick: un 0 marca una lectura vieja
        # incompleta y hace que se descarte la fidelidad de esa fila. Los
        # snapshots de estas pruebas son completos salvo donde se diga.
        "leadership": 4,
        "salary": 5_000,
        "keeper": 1,
        "defending": 6,
        "playmaking": 7,
        "winger": 5,
        "passing": 6,
        "scoring": 4,
        "set_pieces": 3,
        "content_hash": bytes([sync_id]) * 32,
    }
    values.update(updates)
    return m.PlayerSnapshot(**values)


def test_changes_history_uses_all_real_snapshot_deltas_and_selected_series() -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()

            first = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=now, finished_at=now)
            second_time = now + timedelta(days=7)
            second = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=second_time, finished_at=second_time)
            session.add_all([first, second])
            await session.flush()
            session.add_all(
                [
                    _snapshot(first.id, player.id, now),
                    _snapshot(
                        second.id, player.id, second_time,
                        passing=7, experience=5, loyalty=6, form=6,
                    ),
                ]
            )
            await session.commit()

            result = await build_changes_history(session, team.id, player.ht_player_id)

        assert result["selectedPlayerId"] == player.ht_player_id
        assert len(result["series"]) == 2
        assert [(event["key"], event["delta"]) for event in result["skillChanges"]] == [("passing", 1)]
        assert [(event["key"], event["delta"]) for event in result["experienceChanges"]] == [("experience", 1)]
        assert [(event["key"], event["delta"]) for event in result["loyaltyChanges"]] == [("loyalty", 1)]
        assert [(event["key"], event["delta"]) for event in result["formChanges"]] == [("form", 1)]
        await engine.dispose()

    asyncio.run(scenario())


def test_changes_history_uses_only_the_last_snapshot_of_each_iso_week() -> None:
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        # Monday makes the boundary unambiguous: the 27th, 28th and 29th are
        # one ISO week; the following Monday is its next weekly close.
        monday = datetime(2026, 7, 27, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba")
            session.add(player)
            await session.flush()
            syncs = []
            for offset in (0, 1, 2, 7):
                at = monday + timedelta(days=offset)
                sync = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=at, finished_at=at)
                session.add(sync)
                await session.flush()
                syncs.append(sync)
            session.add_all([
                _snapshot(syncs[0].id, player.id, monday, passing=5),
                _snapshot(syncs[1].id, player.id, monday + timedelta(days=1), passing=6),
                _snapshot(syncs[2].id, player.id, monday + timedelta(days=2), passing=7),
                _snapshot(syncs[3].id, player.id, monday + timedelta(days=7), passing=8),
            ])
            await session.commit()
            fixed_now = monday + timedelta(days=7, hours=1)
            result = await build_changes_history(
                session, team.id, player.ht_player_id, now=fixed_now
            )

        # Week 31 closes at 7; week 32 closes at 8. The intra-week 5→6 and
        # 6→7 transitions remain auditable in storage but are not UI diffs.
        assert [(event["before"], event["current"], event["delta"])
                for event in result["skillChanges"] if event["key"] == "passing"] == [(7, 8, 1)]
        assert [point["tsi"] for point in result["series"]] == [10_000, 10_000]
        await engine.dispose()

    asyncio.run(scenario())


def test_changes_history_series_salary_is_converted_to_local_currency() -> None:
    """CHPP da el salario en la moneda base del juego, no en la local
    (Colombia = tasa 10) — igual que en sync_comparison.py, el gráfico de
    la ficha del jugador debe dividir por la tasa o se ve 10x inflado."""
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        now = datetime.now(UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo", currency_rate=10.0)
            session.add(team)
            await session.flush()
            player = m.Player(ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba")
            session.add(player)
            await session.flush()

            sync = m.Sync(user_id=1, team_id=team.id, kind="players", status="completed", started_at=now, finished_at=now)
            session.add(sync)
            await session.flush()
            session.add(_snapshot(sync.id, player.id, now, salary=123_450))
            await session.commit()

            result = await build_changes_history(session, team.id, player.ht_player_id)

        assert result["series"][0]["salary"] == 12_345
        await engine.dispose()

    asyncio.run(scenario())


def test_a_wider_window_reports_the_net_change_not_each_weekly_step() -> None:
    """2026-08-17, pedido explícito: comparar contra hace 2, 4, 8 o 16 semanas.

    Un jugador que sube Pases una vez por semana durante cuatro semanas no
    produce cuatro filas de +1 — produce una de 5 → 9. A dieciséis semanas la
    otra forma sería ilegible, y sumar de cabeza es justo lo que la pantalla
    debería ahorrarte.
    """
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba")
            session.add(player)
            await session.flush()
            # Un cierre por semana durante cinco semanas: Pases 5, 6, 7, 8, 9.
            for week in range(5):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1, team_id=team.id, kind="players", status="completed",
                    started_at=at, finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, player.id, at, passing=5 + week))
            await session.commit()

            now = monday + timedelta(weeks=4, hours=1)

            async def passing(weeks: int) -> list[tuple[int, int, int]]:
                result = await build_changes_history(
                    session, team.id, player.ht_player_id, weeks=weeks, now=now,
                )
                return [
                    (e["before"], e["current"], e["delta"])
                    for e in result["skillChanges"] if e["key"] == "passing"
                ]

            # Una semana: sólo el último paso.
            assert await passing(1) == [(8, 9, 1)]
            # Dos y cuatro: el neto, en una sola línea.
            assert await passing(2) == [(7, 9, 2)]
            assert await passing(4) == [(5, 9, 4)]

            # Dieciséis semanas pedidas con cinco de historia: se compara
            # contra el cierre más viejo que existe, y se dice cuál es.
            wide = await build_changes_history(
                session, team.id, player.ht_player_id, weeks=16, now=now,
            )
            assert [
                (e["before"], e["current"]) for e in wide["skillChanges"]
                if e["key"] == "passing"
            ] == [(5, 9)]
            assert wide["weeks"] == 16
            assert wide["comparedFrom"].startswith("2026-05-04")

        await engine.dispose()

    asyncio.run(scenario())


def test_a_player_signed_mid_window_is_compared_against_his_own_first_close() -> None:
    """No se inventa un "antes" para quien no estaba. Su primer cierre es lo
    más viejo que de él se sabe, y contra eso se compara."""
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            nuevo = m.Player(ht_player_id=22, team_id=team.id, first_name="Recién", last_name="Llegado")
            session.add(nuevo)
            await session.flush()
            # Llegó hace dos semanas; se piden ocho.
            for week in (2, 3):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1, team_id=team.id, kind="players", status="completed",
                    started_at=at, finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, nuevo.id, at, passing=4 + week))
            await session.commit()

            result = await build_changes_history(
                session, team.id, nuevo.ht_player_id, weeks=8,
                now=monday + timedelta(weeks=3, hours=1),
            )

        assert [
            (e["before"], e["current"]) for e in result["skillChanges"]
            if e["key"] == "passing"
        ] == [(6, 7)]
        await engine.dispose()

    asyncio.run(scenario())


def test_compared_from_is_the_teams_reference_not_a_newcomers() -> None:
    """`comparedFrom` es lo que la pantalla enseña como "hace cuánto". Si se
    calculara como el mínimo entre jugadores, un fichaje reciente —que sí se
    compara contra su propio primer cierre— arrastraría la fecha hacia atrás y
    haría creer que TODA la tabla mira mucho más lejos de lo que mira."""
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            veterano = m.Player(ht_player_id=11, team_id=team.id, first_name="Vieja", last_name="Guardia")
            nuevo = m.Player(ht_player_id=22, team_id=team.id, first_name="Recién", last_name="Llegado")
            session.add_all([veterano, nuevo])
            await session.flush()

            for week in range(5):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1, team_id=team.id, kind="players", status="completed",
                    started_at=at, finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, veterano.id, at, passing=5 + week))
                if week >= 3:            # el nuevo sólo existe las dos últimas
                    session.add(_snapshot(sync.id, nuevo.id, at, passing=9))
            await session.commit()

            result = await build_changes_history(
                session, team.id, weeks=2, now=monday + timedelta(weeks=4, hours=1),
            )

        # Dos semanas atrás desde la semana 4 es la semana 2, no la 0 — aunque
        # el recién llegado se compare contra su cierre de la semana 3.
        assert result["comparedFrom"].startswith("2026-05-18")
        await engine.dispose()

    asyncio.run(scenario())


def test_loyalty_is_not_read_from_the_old_incomplete_snapshots() -> None:
    """Los snapshots del 26-27 de julio de 2026 se guardaron sin fidelidad ni
    liderazgo, y quedaron con 0 en ambos. Comparar contra uno de ellos inventa
    una subida gigante — "0 → 20" en Fidelidad para media plantilla.

    Con ventanas de una semana no se veía, porque esas filas ya habían salido
    de la ventana; a cuatro semanas vuelven a ser la referencia. La marca es
    liderazgo, no fidelidad: un fichaje recién llegado sí puede tener fidelidad
    0 de verdad, así que su propio valor no sirve para descartarlo.
    """
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba")
            session.add(player)
            await session.flush()

            for week, (loyalty, leadership, passing) in enumerate([
                (0, 0, 5),     # lectura incompleta: fidelidad y liderazgo en 0
                (18, 4, 6),
                (20, 4, 7),
            ]):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1, team_id=team.id, kind="players", status="completed",
                    started_at=at, finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(
                    sync.id, player.id, at,
                    loyalty=loyalty, leadership=leadership, passing=passing,
                ))
            await session.commit()

            now = monday + timedelta(weeks=2, hours=1)
            wide = await build_changes_history(session, team.id, weeks=4, now=now)
            narrow = await build_changes_history(session, team.id, weeks=1, now=now)

        # La ventana ancha llega hasta la fila incompleta: nada de "0 → 20".
        assert wide["loyaltyChanges"] == []
        # Pero lo demás de esa misma fila sí se compara: sólo la fidelidad
        # estaba sin guardar.
        assert [(e["before"], e["current"]) for e in wide["skillChanges"]
                if e["key"] == "passing"] == [(5, 7)]
        # Y entre dos filas completas la fidelidad se reporta con normalidad.
        assert [(e["before"], e["current"]) for e in narrow["loyaltyChanges"]] == [(18, 20)]
        await engine.dispose()

    asyncio.run(scenario())


def test_the_aggregate_covers_market_and_leadership_too() -> None:
    """2026-08-17, pedido explícito: el agregado del equipo lleva TODO lo que se
    mide del jugador — TSI, salario y liderazgo incluidos, no sólo habilidades.

    El salario se compara ya convertido a la moneda local: restar los valores
    crudos de CHPP daría un delta diez veces más grande en una liga con tasa 10.
    """
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo", currency_rate=10.0)
            session.add(team)
            await session.flush()
            player = m.Player(ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba")
            session.add(player)
            await session.flush()

            for week, (tsi, salary, leadership) in enumerate([
                (100_000, 50_000, 4),
                (108_000, 62_000, 5),
            ]):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1, team_id=team.id, kind="players", status="completed",
                    started_at=at, finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(
                    sync.id, player.id, at, tsi=tsi, salary=salary, leadership=leadership,
                ))
            await session.commit()

            result = await build_changes_history(
                session, team.id, weeks=1, now=monday + timedelta(weeks=1, hours=1),
            )

        mercado = {e["key"]: e for e in result["marketChanges"]}
        assert (mercado["tsi"]["before"], mercado["tsi"]["current"]) == (100_000, 108_000)
        # 50.000 y 62.000 crudos son 5.000 y 6.200 locales: el delta es 1.200,
        # no 12.000.
        assert (mercado["salary"]["before"], mercado["salary"]["current"]) == (5_000, 6_200)
        assert mercado["salary"]["delta"] == 1_200

        liderazgo = [e for e in result["loyaltyChanges"] if e["key"] == "leadership"]
        assert [(e["before"], e["current"]) for e in liderazgo] == [(4, 5)]

    asyncio.run(scenario())


def test_players_who_left_the_club_are_out_of_changes_and_of_the_balances() -> None:
    """2026-08-17, pedido explícito: en Cambios sólo la plantilla de hoy.

    Las filas `Player` de quien se fue nunca se borran —son el histórico de
    traspasos— y se marcan con `left_team_at`. Sin filtrarlas, un vendido
    seguía apareciendo con sus cambios y, peor, sus cifras entraban en los
    balances del equipo: el club parecía perder TSI que en realidad se fue con
    el jugador cuando lo vendiste.
    """
    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            sigue = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Sigue", last_name="Aquí",
            )
            vendido = m.Player(
                ht_player_id=22, team_id=team.id, first_name="Viktor", last_name="Vendido",
                left_team_at=monday + timedelta(weeks=1, days=3),
            )
            session.add_all([sigue, vendido])
            await session.flush()

            for week in (0, 1):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1, team_id=team.id, kind="players", status="completed",
                    started_at=at, finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, sigue.id, at, passing=5 + week))
                session.add(_snapshot(sync.id, vendido.id, at, passing=9 - week, tsi=90_000))
            await session.commit()

            result = await build_changes_history(
                session, team.id, weeks=1, now=monday + timedelta(weeks=1, hours=1),
            )

        nombres = {e["name"] for e in result["skillChanges"]}
        assert nombres == {"Sigue Aquí"}
        assert not any(e["name"].startswith("Viktor") for e in result["marketChanges"])
        # Y tampoco aparece en la lista de jugadores del selector.
        assert [p["name"] for p in result["players"]] == ["Sigue Aquí"]
        await engine.dispose()

    asyncio.run(scenario())
