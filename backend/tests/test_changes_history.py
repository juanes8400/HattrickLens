import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.queries.changes_history import SIEMPRE, build_changes_history
from app.application.queries.weekly import cierre_mas_cercano
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

            first = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=now,
                finished_at=now,
            )
            second_time = now + timedelta(days=7)
            second = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=second_time,
                finished_at=second_time,
            )
            session.add_all([first, second])
            await session.flush()
            session.add_all(
                [
                    _snapshot(first.id, player.id, now),
                    _snapshot(
                        second.id,
                        player.id,
                        second_time,
                        passing=7,
                        experience=5,
                        loyalty=6,
                        form=6,
                    ),
                ]
            )
            await session.commit()

            result = await build_changes_history(session, team.id, player.ht_player_id)

        assert result["selectedPlayerId"] == player.ht_player_id
        assert len(result["series"]) == 2
        assert [(event["key"], event["delta"]) for event in result["skillChanges"]] == [
            ("passing", 1)
        ]
        assert [(event["key"], event["delta"]) for event in result["experienceChanges"]] == [
            ("experience", 1)
        ]
        assert [(event["key"], event["delta"]) for event in result["loyaltyChanges"]] == [
            ("loyalty", 1)
        ]
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
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()
            syncs = []
            for offset in (0, 1, 2, 7):
                at = monday + timedelta(days=offset)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                syncs.append(sync)
            session.add_all(
                [
                    _snapshot(syncs[0].id, player.id, monday, passing=5),
                    _snapshot(syncs[1].id, player.id, monday + timedelta(days=1), passing=6),
                    _snapshot(syncs[2].id, player.id, monday + timedelta(days=2), passing=7),
                    _snapshot(syncs[3].id, player.id, monday + timedelta(days=7), passing=8),
                ]
            )
            await session.commit()
            result = await build_changes_history(session, team.id, player.ht_player_id)

        # Week 31 closes at 7; week 32 closes at 8. The intra-week 5→6 and
        # 6→7 transitions remain auditable in storage but are not UI diffs.
        assert [
            (event["before"], event["current"], event["delta"])
            for event in result["skillChanges"]
            if event["key"] == "passing"
        ] == [(7, 8, 1)]
        assert [point["tsi"] for point in result["series"]] == [10_000, 10_000]
        await engine.dispose()

    asyncio.run(scenario())


def test_changes_history_series_salary_is_converted_to_local_currency() -> None:
    """CHPP da el salario en la moneda base del juego, no en la local
    (Colombia = tasa 10), igual que en sync_comparison.py, el gráfico de
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
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()

            sync = m.Sync(
                user_id=1,
                team_id=team.id,
                kind="players",
                status="completed",
                started_at=now,
                finished_at=now,
            )
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
    produce cuatro filas de +1, produce una de 5 → 9. A dieciséis semanas la
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
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()
            # Un cierre por semana durante cinco semanas: Pases 5, 6, 7, 8, 9.
            for week in range(5):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, player.id, at, passing=5 + week))
            await session.commit()

            async def passing(weeks: int) -> list[tuple[int, int, int]]:
                result = await build_changes_history(
                    session,
                    team.id,
                    player.ht_player_id,
                    weeks=weeks,
                )
                return [
                    (e["before"], e["current"], e["delta"])
                    for e in result["skillChanges"]
                    if e["key"] == "passing"
                ]

            # Una semana: sólo el último paso.
            assert await passing(1) == [(8, 9, 1)]
            # Dos y cuatro: el neto, en una sola línea.
            assert await passing(2) == [(7, 9, 2)]
            assert await passing(4) == [(5, 9, 4)]

            # Dieciséis semanas pedidas con cinco de historia: se compara
            # contra el cierre más viejo que existe, y se dice cuál es.
            wide = await build_changes_history(
                session,
                team.id,
                player.ht_player_id,
                weeks=16,
            )
            assert [
                (e["before"], e["current"]) for e in wide["skillChanges"] if e["key"] == "passing"
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
            nuevo = m.Player(
                ht_player_id=22, team_id=team.id, first_name="Recién", last_name="Llegado"
            )
            session.add(nuevo)
            await session.flush()
            # Llegó hace dos semanas; se piden ocho.
            for week in (2, 3):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, nuevo.id, at, passing=4 + week))
            await session.commit()

            result = await build_changes_history(
                session,
                team.id,
                nuevo.ht_player_id,
                weeks=8,
            )

        assert [
            (e["before"], e["current"]) for e in result["skillChanges"] if e["key"] == "passing"
        ] == [(6, 7)]
        await engine.dispose()

    asyncio.run(scenario())


def test_compared_from_is_the_teams_reference_not_a_newcomers() -> None:
    """`comparedFrom` es lo que la pantalla enseña como "hace cuánto". Si se
    calculara como el mínimo entre jugadores, un fichaje reciente, que sí se
    compara contra su propio primer cierre, arrastraría la fecha hacia atrás y
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
            veterano = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Vieja", last_name="Guardia"
            )
            nuevo = m.Player(
                ht_player_id=22, team_id=team.id, first_name="Recién", last_name="Llegado"
            )
            session.add_all([veterano, nuevo])
            await session.flush()

            for week in range(5):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, veterano.id, at, passing=5 + week))
                if week >= 3:  # el nuevo sólo existe las dos últimas
                    session.add(_snapshot(sync.id, nuevo.id, at, passing=9))
            await session.commit()

            result = await build_changes_history(
                session,
                team.id,
                weeks=2,
            )

        # Dos semanas atrás desde la semana 4 es la semana 2, no la 0, aunque
        # el recién llegado se compare contra su cierre de la semana 3.
        assert result["comparedFrom"].startswith("2026-05-18")
        await engine.dispose()

    asyncio.run(scenario())


def test_loyalty_is_not_read_from_the_old_incomplete_snapshots() -> None:
    """Los snapshots del 26-27 de julio de 2026 se guardaron sin fidelidad ni
    liderazgo, y quedaron con 0 en ambos. Comparar contra uno de ellos inventa
    una subida gigante, "0 → 20" en Fidelidad para media plantilla.

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
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()

            for week, (loyalty, leadership, passing) in enumerate(
                [
                    (0, 0, 5),  # lectura incompleta: fidelidad y liderazgo en 0
                    (18, 4, 6),
                    (20, 4, 7),
                ]
            ):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(
                    _snapshot(
                        sync.id,
                        player.id,
                        at,
                        loyalty=loyalty,
                        leadership=leadership,
                        passing=passing,
                    )
                )
            await session.commit()

            wide = await build_changes_history(session, team.id, weeks=4)
            narrow = await build_changes_history(session, team.id, weeks=1)

        # La ventana ancha llega hasta la fila incompleta: nada de "0 → 20".
        assert wide["loyaltyChanges"] == []
        # Pero lo demás de esa misma fila sí se compara: sólo la fidelidad
        # estaba sin guardar.
        assert [
            (e["before"], e["current"]) for e in wide["skillChanges"] if e["key"] == "passing"
        ] == [(5, 7)]
        # Y entre dos filas completas la fidelidad se reporta con normalidad.
        assert [(e["before"], e["current"]) for e in narrow["loyaltyChanges"]] == [(18, 20)]
        await engine.dispose()

    asyncio.run(scenario())


def test_the_aggregate_covers_market_and_leadership_too() -> None:
    """2026-08-17, pedido explícito: el agregado del equipo lleva TODO lo que se
    mide del jugador, TSI, salario y liderazgo incluidos, no sólo habilidades.

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
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()

            for week, (tsi, salary, leadership) in enumerate(
                [
                    (100_000, 50_000, 4),
                    (108_000, 62_000, 5),
                ]
            ):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(
                    _snapshot(
                        sync.id,
                        player.id,
                        at,
                        tsi=tsi,
                        salary=salary,
                        leadership=leadership,
                    )
                )
            await session.commit()

            result = await build_changes_history(
                session,
                team.id,
                weeks=1,
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

    Las filas `Player` de quien se fue nunca se borran, son el histórico de
    traspasos, y se marcan con `left_team_at`. Sin filtrarlas, un vendido
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
                ht_player_id=11,
                team_id=team.id,
                first_name="Sigue",
                last_name="Aquí",
            )
            vendido = m.Player(
                ht_player_id=22,
                team_id=team.id,
                first_name="Viktor",
                last_name="Vendido",
                left_team_at=monday + timedelta(weeks=1, days=3),
            )
            session.add_all([sigue, vendido])
            await session.flush()

            for week in (0, 1):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, sigue.id, at, passing=5 + week))
                session.add(_snapshot(sync.id, vendido.id, at, passing=9 - week, tsi=90_000))
            await session.commit()

            result = await build_changes_history(
                session,
                team.id,
                weeks=1,
            )

        nombres = {e["name"] for e in result["skillChanges"]}
        assert nombres == {"Sigue Aquí"}
        assert not any(e["name"].startswith("Viktor") for e in result["marketChanges"])
        # Y tampoco aparece en la lista de jugadores del selector.
        assert [p["name"] for p in result["players"]] == ["Sigue Aquí"]
        await engine.dispose()

    asyncio.run(scenario())


def test_siempre_compara_contra_el_primer_cierre_de_cada_jugador() -> None:
    """`weeks=SIEMPRE` va al primer dato guardado de CADA UNO, no a una fecha
    común. 2026-09-09, pedido del usuario: «que significa que vamos a ir al
    primer dato guardado del jugador».

    Dos jugadores que llevan aquí distinto tiempo: el veterano tiene que
    contar desde su semana 0 y el fichaje desde la suya, y las dos cuentas
    tienen que ser distintas. Con una ventana normal --aunque fuera de mil
    semanas-- los dos caerían en su primer cierre igualmente, así que la
    prueba de que esto no es «una ventana muy ancha» está abajo, en el
    contraste con `weeks=1`.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            veterano = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Vete", last_name="Rano"
            )
            nuevo = m.Player(ht_player_id=22, team_id=team.id, first_name="Re", last_name="Ciente")
            session.add_all([veterano, nuevo])
            await session.flush()

            # El veterano lleva cinco semanas y sube un nivel por semana; el
            # fichaje sólo lleva las dos últimas.
            for week in range(5):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, veterano.id, at, passing=5 + week))
                if week >= 3:
                    session.add(_snapshot(sync.id, nuevo.id, at, passing=10 + week))
            await session.commit()

            siempre = await build_changes_history(session, team.id, weeks=SIEMPRE)
            una_semana = await build_changes_history(session, team.id, weeks=1)

        def pases(resultado):
            return {
                e["name"]: (e["before"], e["current"])
                for e in resultado["skillChanges"]
                if e["key"] == "passing"
            }

        # Cada uno desde SU principio: el veterano 5 → 9 (cinco cierres), el
        # fichaje 13 → 14 (dos cierres). Puntos de partida distintos, que es
        # justo lo que una ventana común no puede dar.
        assert pases(siempre) == {"Vete Rano": (5, 9), "Re Ciente": (13, 14)}
        # Y no es lo mismo que pedir la última semana, donde los dos se
        # comparan contra el cierre anterior y avanzan un solo escalón.
        assert pases(una_semana) == {"Vete Rano": (8, 9), "Re Ciente": (13, 14)}
        assert siempre["weeks"] == SIEMPRE
        await engine.dispose()

    asyncio.run(scenario())


def test_siempre_sigue_descartando_la_fidelidad_de_las_lecturas_incompletas() -> None:
    """La guarda que ya existía se vuelve LOAD-BEARING con «Siempre».

    Los cierres viejos guardan fidelidad y liderazgo en 0 porque entonces no
    se leían. Con ventanas cortas quedaban fuera; con «Siempre» pasan a ser la
    referencia de todo el que lleve aquí desde entonces, así que sin la guarda
    media plantilla saldría con una subida de fidelidad que nunca ocurrió.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            jugador = m.Player(ht_player_id=33, team_id=team.id, first_name="Anti", last_name="Guo")
            session.add(jugador)
            await session.flush()

            for week, extra in enumerate(
                [
                    # El primer cierre es de los incompletos: liderazgo 0.
                    {"loyalty": 0, "leadership": 0, "passing": 5},
                    {"loyalty": 18, "leadership": 4, "passing": 6},
                    {"loyalty": 20, "leadership": 4, "passing": 7},
                ]
            ):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, jugador.id, at, **extra))
            await session.commit()

            resultado = await build_changes_history(session, team.id, weeks=SIEMPRE)

        # Los Pases sí se cuentan desde el primer cierre.
        assert [
            (e["before"], e["current"]) for e in resultado["skillChanges"] if e["key"] == "passing"
        ] == [(5, 7)]
        # La fidelidad NO: su referencia es una lectura incompleta, y un
        # "0 → 20" sería un dato inventado.
        assert resultado["loyaltyChanges"] == []
        await engine.dispose()

    asyncio.run(scenario())


def _youth_snapshot(sync_id: int, youth_player_id: int, captured_at: datetime, **updates):
    values = {
        "sync_id": sync_id,
        "youth_player_id": youth_player_id,
        "captured_at": captured_at,
        "age_years": 17,
        "age_days": 0,
        "content_hash": bytes([sync_id % 256]) * 32,
    }
    values.update(updates)
    return m.YouthSnapshot(**values)


def test_la_cantera_entra_en_las_mismas_ventanas_que_la_plantilla() -> None:
    """2026-09-09, pedido del usuario: «que los movimientos de esos jugadores
    también entren» en «Última semana», «Hace 2 semanas»...

    Lo que sale depende de si en la fecha de referencia ya se SABÍA esa
    habilidad, y las dos respuestas son correctas:

      · A una semana la referencia ya la conocía: MOVIMIENTO 4 -> 5.
      · Con «Siempre» la referencia es el primer cierre del chico, cuando no
        se le había mirado el Lateral. Aun así manda el MOVIMIENTO, porque
        dentro de la ventana se descubrió Y ADEMÁS subió: enseñar sólo
        «descubierto: 5» se comería la subida. Lo preguntó el usuario el
        2026-09-09 mirando este mismo caso en su academia.
      · Un descubrimiento que no se ha movido desde que se supo sí se enseña
        como tal, eso lo fija el test de abajo.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            chico = m.YouthPlayer(
                ht_youth_player_id=900,
                team_id=team.id,
                first_name="Cante",
                last_name="Rano",
            )
            session.add(chico)
            await session.flush()

            # El ojeador tarda dos semanas en mirarle el Lateral. Antes de eso
            # la habilidad no es 0, es que no se sabe.
            for week, winger in enumerate([None, None, 4, 5]):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_youth_snapshot(sync.id, chico.id, at, winger=winger))
            await session.commit()

            siempre = await build_changes_history(session, team.id, weeks=SIEMPRE)
            una_semana = await build_changes_history(session, team.id, weeks=1)

        def lateral(r):
            return [
                (e["label"], e["before"], e["current"], e["delta"], e["isReveal"])
                for e in r["youthChanges"]
            ]

        # A una semana la referencia ya sabía que era 4: movimiento.
        assert lateral(una_semana) == [("Lateral", 4, 5, 1, False)]
        # Con «Siempre» tampoco lo sabía al empezar, pero se descubrió Y
        # subió dentro de la ventana: manda el movimiento, desde el primer
        # valor que llegó a saberse. Nunca contra un desconocido.
        assert lateral(siempre) == [("Lateral", 4, 5, 1, False)]
        # Van marcados: un juvenil no se enlaza a /players, su ficha no vive
        # ahí, y su «+1» no es la misma noticia que el de un titular.
        assert all(e["isYouth"] for e in siempre["youthChanges"])
        await engine.dispose()

    asyncio.run(scenario())


def test_un_descubrimiento_se_reporta_pero_sin_inventarle_un_antes() -> None:
    """Pasar de «no se sabe» a 5 es un DESCUBRIMIENTO, y también es noticia.

    2026-09-09, pedido del usuario: «los descubrimientos también deben ser
    reportados como cambios». Lo que no se puede es disfrazarlo de subida:
    nadie subió nada, se levantó la niebla. Viaja sin `before` y sin `delta`,
    y la pantalla lo pinta «descubierto: 5» en vez de «0 ▲ 5 (+5)».
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            chico = m.YouthPlayer(
                ht_youth_player_id=901,
                team_id=team.id,
                first_name="Recién",
                last_name="Visto",
            )
            session.add(chico)
            await session.flush()

            for week, scoring in enumerate([None, None, 5]):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_youth_snapshot(sync.id, chico.id, at, scoring=scoring))
            await session.commit()

            resultado = await build_changes_history(session, team.id, weeks=SIEMPRE)

        assert [
            (e["label"], e["before"], e["current"], e["delta"], e["isReveal"])
            for e in resultado["youthChanges"]
        ] == [("Anotación", None, 5, None, True)]
        await engine.dispose()

    asyncio.run(scenario())


def test_las_cifras_de_la_academia_siguen_a_la_ventana() -> None:
    """2026-09-09, pedido del usuario: «estas 3 cifras también deben moverse
    al son de las ventanas de análisis».

    Y no todas se mueven igual, porque no son lo mismo:

      · `revelations` es un FLUJO. Cuántos techos cayeron dentro de la
        ventana: cambia entero según la ventana.
      · `ceilingsNow` es un STOCK. Cuántos se saben HOY, y eso no depende de
        qué periodo se mire.
      · `ceilingsBefore` es el mismo stock al EMPEZAR la ventana, y es lo que
        permite a la pantalla enseñar el recorrido («+3 en la última semana»)
        sin fingir que el total de hoy cambia con el selector.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            chico = m.YouthPlayer(
                ht_youth_player_id=910,
                team_id=team.id,
                first_name="Nie",
                last_name="Bla",
            )
            session.add(chico)
            await session.flush()

            # Un techo por semana: Pases en la 1, Anotación en la 3.
            for week, extra in enumerate(
                [
                    {},
                    {"passing_max": 6},
                    {"passing_max": 6},
                    {"passing_max": 6, "scoring_max": 4},
                ]
            ):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_youth_snapshot(sync.id, chico.id, at, **extra))
            await session.commit()

            una = await build_changes_history(session, team.id, weeks=1)
            siempre = await build_changes_history(session, team.id, weeks=SIEMPRE)

        # Siete habilidades por un canterano.
        assert una["youthSummary"]["readings"] == 7
        # El stock de hoy es el mismo se mire como se mire: dos techos sabidos.
        assert una["youthSummary"]["ceilingsNow"] == 2
        assert siempre["youthSummary"]["ceilingsNow"] == 2
        # Lo que se mueve es el punto de partida y, con él, el flujo.
        assert una["youthSummary"]["ceilingsBefore"] == 1  # hace una semana ya se sabía Pases
        assert una["youthSummary"]["revelations"] == 1  # sólo Anotación cayó dentro
        assert siempre["youthSummary"]["ceilingsBefore"] == 0  # al principio, ninguno
        assert siempre["youthSummary"]["revelations"] == 2  # los dos
        await engine.dispose()

    asyncio.run(scenario())


def test_un_canterano_recien_llegado_sale_con_lo_que_trae() -> None:
    """2026-09-19, pedido del usuario: «los nuevos juveniles también deben ir
    reportados en Cambios con las habilidades con las que llegan».

    Hasta hoy no salía por ningún lado: sin un cierre anterior no había nada
    que comparar y el chico se saltaba entero. Lo que es noticia de él es
    justo con qué llega, así que se enseña su nivel y su techo allí donde se
    sepan, sin inventarle un «antes».
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        monday = datetime(2026, 5, 4, 9, tzinfo=UTC)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            veterano = m.YouthPlayer(
                ht_youth_player_id=900, team_id=team.id, first_name="Ya", last_name="Estaba"
            )
            nuevo = m.YouthPlayer(
                ht_youth_player_id=901, team_id=team.id, first_name="Recién", last_name="Llegado"
            )
            session.add_all([veterano, nuevo])
            await session.flush()

            for week in range(3):
                at = monday + timedelta(weeks=week)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_youth_snapshot(sync.id, veterano.id, at, winger=4))
                # El nuevo sólo aparece en la última foto: llegó esta semana.
                if week == 2:
                    session.add(
                        _youth_snapshot(sync.id, nuevo.id, at, passing=3, passing_max=7, winger=2)
                    )
            await session.commit()

            r = await build_changes_history(session, team.id, weeks=1)

        llegada = [e for e in r["youthChanges"] if e.get("isArrival")]
        assert {(e["label"], e["current"]) for e in llegada} == {
            ("Pases", 3),
            ("Pases (techo)", 7),
            ("Lateral", 2),
        }
        # Sin «antes» inventado y sin contarse como revelación del ojeador:
        # es lo que ya traía puesto.
        assert all(e["before"] is None and e["delta"] is None for e in llegada)
        assert all(not e["isReveal"] for e in llegada)
        assert r["youthSummary"]["revelations"] == 0
        # Y el que ya estaba no se convierte en recién llegado.
        assert all(e["htPlayerId"] == 901 for e in llegada)

        # A dos semanas el nuevo sigue siendo nuevo, pero el veterano no: su
        # primer cierre es anterior al corte.
        r2 = await build_changes_history(session, team.id, weeks=2)
        assert {e["htPlayerId"] for e in r2["youthChanges"] if e.get("isArrival")} == {901}
        await engine.dispose()

    asyncio.run(scenario())


def test_una_sincronizacion_a_deshora_no_estira_la_ventana_a_dos_semanas() -> None:
    """2026-09-21, medido sobre los cierres reales del usuario.

    «Cuando yo pongo en Cambios Última Semana me aparecen un montón de
    movimientos que ni por el putas son de una semana.» Y tenía razón: la
    referencia era «el último cierre que ya existiera hace siete días», y una
    sincronización no cae a la misma hora todas las semanas.

    Sus cierres: domingo 13 a las 23:30 y domingo 20 a las 03:13. Al del 13
    le faltaban veinte horas para tener siete días completos, así que caía
    fuera del corte y la ventana se iba al cierre del 6: trece días de
    fidelidad, de forma y de TSI en una lista que dice «última semana». Con
    esos mismos cierres pasó tres veces en dos meses.

    Las fechas van fijas y la prueba sale igual se ejecute el día que se
    ejecute, que es justo la mitad del arreglo: la ventana ya no depende de
    cuándo se mire, sólo de los cierres que hay. La otra mitad, coger el
    cierre MÁS CERCANO al corte en vez del primero que sea al menos tan
    viejo, está en `test_la_referencia_es_el_cierre_mas_cercano_al_corte`.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        # Las horas son las de verdad, que son las que provocan el fallo.
        fechas = [
            datetime(2026, 9, 6, 11, 51, tzinfo=UTC),
            datetime(2026, 9, 13, 23, 30, tzinfo=UTC),
            datetime(2026, 9, 20, 3, 13, tzinfo=UTC),
        ]
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()

            # Una subida de fidelidad por semana, que es lo que de verdad
            # hace la fidelidad y por eso delata la ventana estirada.
            for at, loyalty in zip(fechas, (5, 6, 7), strict=True):
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, player.id, at, loyalty=loyalty))
            await session.commit()

            r = await build_changes_history(session, team.id, weeks=1)

        assert r["comparedFrom"] == fechas[1].replace(tzinfo=None).isoformat()
        # Una semana es UNA subida de fidelidad, no dos.
        assert [(e["before"], e["current"]) for e in r["loyaltyChanges"]] == [(6, 7)]

    asyncio.run(scenario())


def test_el_corte_se_mide_desde_la_ultima_lectura_y_no_desde_hoy() -> None:
    """Mes y medio sin sincronizar y «última semana» sigue contestando.

    Las diferencias se calculan contra los últimos datos guardados, así que
    la ventana se mide desde ellos: «la última semana de la que hay
    lecturas», y no la semana del calendario, que con los datos parados no
    contiene ningún cierre. Es además lo que la pantalla enseña, porque dice
    contra qué cierre está comparando.
    """

    async def scenario() -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)

        # Cuatro cierres semanales que terminan hace mes y medio.
        primero = datetime.now(UTC) - timedelta(weeks=9)
        async with factory() as session:
            team = m.Team(ht_team_id=1, name="Equipo")
            session.add(team)
            await session.flush()
            player = m.Player(
                ht_player_id=11, team_id=team.id, first_name="Ana", last_name="Prueba"
            )
            session.add(player)
            await session.flush()
            for semana in range(4):
                at = primero + timedelta(weeks=semana)
                sync = m.Sync(
                    user_id=1,
                    team_id=team.id,
                    kind="players",
                    status="completed",
                    started_at=at,
                    finished_at=at,
                )
                session.add(sync)
                await session.flush()
                session.add(_snapshot(sync.id, player.id, at, loyalty=5 + semana))
            await session.commit()

            r = await build_changes_history(session, team.id, weeks=1)

        # El penúltimo cierre, no el primero de todos.
        esperado = (primero + timedelta(weeks=2)).replace(tzinfo=None)
        assert r["comparedFrom"] == esperado.isoformat()
        assert [(e["before"], e["current"]) for e in r["loyaltyChanges"]] == [(7, 8)]

    asyncio.run(scenario())


def test_la_referencia_es_el_cierre_mas_cercano_al_corte() -> None:
    """La regla, sin base de datos de por medio.

    Era «el último cierre que ya existiera al empezar la ventana», y por
    veinte horas se saltaba una semana entera. Ahora se coge el más cercano
    al corte, que con veinte horas de diferencia mueve la referencia veinte
    horas.
    """
    domingo6 = datetime(2026, 9, 6, 11, 51)
    domingo13 = datetime(2026, 9, 13, 23, 30)
    domingo20 = datetime(2026, 9, 20, 3, 13)

    corte = domingo20 - timedelta(weeks=1)
    # La regla vieja: el último que ya existiera en el corte. Al del 13 le
    # faltan veinte horas, así que caía al del 6.
    assert [c for c in (domingo6, domingo13) if c <= corte][-1] == domingo6
    # La nueva no tiene ese filo.
    assert cierre_mas_cercano([domingo6, domingo13], corte) == domingo13

    # Y sigue eligiendo el de antes cuando el corte cae de verdad más atrás.
    assert cierre_mas_cercano([domingo6, domingo13], domingo20 - timedelta(weeks=2)) == domingo6

    # «Siempre» pone el corte en el principio del tiempo: el primero de todos.
    assert cierre_mas_cercano([domingo6, domingo13], datetime.min) == domingo6
