"""GET /teams/{id}/cup — HL-111 a HL-115.

Solo hechos: partidos de copa ya jugados (resultado real) y ya programados
(fecha confirmada, no una predicción). Nunca un pronóstico del próximo
cruce — HL-140's mismo principio: no presentar el futuro como si fuera cierto."""
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.application.commands.sync_team import SyncTeamCommand, SyncTeamHandler
from app.infrastructure.chpp.parsers import get_parser
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
OWN_HT_TEAM_ID = 537758
SUBMITTED_IDS = [
    476719421, 471016867, 474341053, 468921494, 475735542,
    484269024, 484830978, 493839156, 444563841, 434712334, 440329107,
]


async def _seed_roster(team_id: int, specs: list[tuple[int, int, int]]) -> None:
    """specs: (ht_player_id, tsi, stamina) por jugador."""
    gen = app.dependency_overrides[get_session]()
    session = await gen.__anext__()
    now = datetime.now(UTC)
    sync = m.Sync(user_id=1, team_id=team_id, kind="test", status="completed", started_at=now)
    session.add(sync)
    await session.flush()
    for index, (ht_player_id, tsi, stamina) in enumerate(specs):
        player = m.Player(
            ht_player_id=ht_player_id, team_id=team_id,
            first_name="Jugador", last_name=str(index + 1),
        )
        session.add(player)
        await session.flush()
        session.add(m.PlayerSnapshot(
            sync_id=sync.id, player_id=player.id, captured_at=now,
            age_years=25, age_days=0, tsi=tsi, form=7, stamina=stamina,
            experience=7, salary=1_000, keeper=1, defending=1, playmaking=1,
            winger=1, passing=1, scoring=1, set_pieces=1,
            content_hash=f"player-{index}".encode(),
        ))
    await session.commit()
    await gen.aclose()


async def _set_upcoming_submitted_lineup(lineup_json: str | None) -> None:
    gen = app.dependency_overrides[get_session]()
    session = await gen.__anext__()
    match = (
        await session.execute(select(m.Match).where(m.Match.ht_match_id == 767370369))
    ).scalar_one()
    match.submitted_lineup_json = lineup_json
    match.submitted_orders_captured_at = datetime.now(UTC) if lineup_json else None
    await session.commit()
    await gen.aclose()


class FakeCHPP:
    async def fetch(self, file: str, version: str = "latest", **_params: Any) -> dict[str, Any]:
        return get_parser(file)((FIXTURES / f"{file}.xml").read_bytes())


@pytest.fixture
def seeded() -> tuple[TestClient, int]:
    import asyncio

    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def setup() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            # 2026-08-04: los nombres de copa ya no son un CUP_LEVEL_NAMES
            # hardcodeado — salen de `WorldCup`, keyeado por
            # (ht_league_id, cup_level, cup_level_index), el mismo par real
            # que usa Hattrick (el nivel 2 de Colombia tiene tres copas
            # paralelas: Esmeralda/Rubí/Zafiro, índices 1/2/3).
            team = m.Team(
                ht_team_id=OWN_HT_TEAM_ID, name="Pulgas Arrechas", ht_league_id=19,
                currency_name="US$", currency_rate=10.0,
                still_in_cup=True, current_cup_id=18, current_cup_name="Copa Colombia",
                current_cup_league_level=0, current_cup_level=1,
                current_cup_level_index=1, current_cup_match_round=2,
                current_cup_match_rounds_left=9,
            )
            s.add(team)
            s.add(m.WorldCup(
                ht_league_id=19, ht_cup_id=18, cup_league_level=0,
                cup_level=1, cup_level_index=1, cup_name="Copa Colombia",
                match_round=2, match_rounds_left=9,
            ))
            s.add(m.WorldCup(
                ht_league_id=19, cup_level=2, cup_level_index=1,
                cup_name="Copa Macarena Esmeralda",
            ))
            await s.commit()
            team_id = team.id

        uow = SqlAlchemyUnitOfWork(factory)
        handler = SyncTeamHandler(uow, FakeCHPP())
        await handler.execute(
            SyncTeamCommand(
                user_id=1, team_id=team_id, ht_team_id=OWN_HT_TEAM_ID, files=["matches"],
            )
        )
        return team_id

    team_id = asyncio.run(setup())

    async def override_get_session():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)
    yield client, team_id
    app.dependency_overrides.clear()


def test_cup_lists_the_upcoming_fixture_from_the_fixture(
    seeded: tuple[TestClient, int],
) -> None:
    client, team_id = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200

    body = resp.json()
    assert body["matchesPlayed"] == 0
    assert body["record"] == "0-0-0"
    assert len(body["nextMatches"]) == 1
    nm = body["nextMatches"][0]
    assert nm["opponent"] == "Leones de la Selva"
    assert nm["isHome"] is True
    assert nm["officialRound"] == 2
    assert body["status"]["stageLabel"] == "Ronda de 512"
    assert body["status"]["stillInCup"] is True


def test_cup_readiness_defaults_to_top_tsi_without_finished_lineup_history(
    seeded: tuple[TestClient, int],
) -> None:
    """Sin ningún partido FINISHED con alineación conocida (de Copa o Liga),
    el único once de referencia posible es el de mayor TSI — rediseño
    2026-08-13 en toggle top TSI / última Copa / última Liga."""
    import asyncio

    client, team_id = seeded
    specs = [(pid, 10_000 - index, 5) for index, pid in enumerate(SUBMITTED_IDS)]
    specs.append((999999999, 1_000_000, 9))  # mayor TSI de todos, sí entra al top 11
    asyncio.run(_seed_roster(team_id, specs))
    asyncio.run(_set_upcoming_submitted_lineup(None))

    body = client.get(f"/api/v1/teams/{team_id}/cup").json()
    readiness = body["readiness"]
    assert [v["mode"] for v in readiness["referenceVariants"]] == ["top_tsi"]
    assert readiness["defaultMode"] == "top_tsi"
    variant = readiness["referenceVariants"][0]
    assert variant["startersCount"] == 11
    assert variant["staminaBands"][2]["count"] == 1  # el jugador de resistencia 9 ("Preparada")


def test_cup_readiness_uses_submitted_formation_for_stamina(
    seeded: tuple[TestClient, int],
) -> None:
    """La formación enviada del próximo partido aparece como opción y es la
    referencia predeterminada porque representa los jugadores que realmente
    van a disputar el partido, no los once con mayor TSI."""
    import asyncio

    client, team_id = seeded
    specs = [(pid, 10_000 - index, 6) for index, pid in enumerate(SUBMITTED_IDS)]
    # Este jugador desplaza a uno de la lista en el once por TSI, pero no está
    # en la formación enviada: no debe alterar su resistencia media.
    specs.append((999999999, 1_000_000, 9))
    asyncio.run(_seed_roster(team_id, specs))

    readiness = client.get(f"/api/v1/teams/{team_id}/cup").json()["readiness"]
    submitted = next(
        variant
        for variant in readiness["referenceVariants"]
        if variant["mode"] == "submitted"
    )
    assert submitted["label"] == "Formación enviada"
    assert submitted["sourceMatchId"] == 767370369
    assert submitted["sourceOpponent"] == "Leones de la Selva"
    assert submitted["startersCount"] == 11
    assert submitted["averageStamina"] == 6.0
    assert submitted["staminaBands"][1]["count"] == 11
    assert readiness["defaultMode"] == "submitted"


def test_cup_readiness_hides_last_cup_variant_with_only_one_match_played(
    seeded: tuple[TestClient, int],
) -> None:
    """"Última formación en Copa" solo se ofrece con más de un partido de
    Copa jugado esta temporada — pedido explícito 2026-08-13."""
    import asyncio

    client, team_id = seeded
    specs = [(pid, 10_000 - index, 5) for index, pid in enumerate(SUBMITTED_IDS)]
    asyncio.run(_seed_roster(team_id, specs))
    asyncio.run(_set_upcoming_submitted_lineup(None))

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999010, played_at=datetime(2026, 6, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=50,
            home_team_name="Pulgas Arrechas", away_team_name="Único Rival",
            home_goals=2, away_goals=0, cup_level=1, cup_level_index=1,
            submitted_lineup_json=json.dumps([{"ht_player_id": pid} for pid in SUBMITTED_IDS]),
        ))
        await session.commit()

    asyncio.run(run())

    modes = [v["mode"] for v in client.get(f"/api/v1/teams/{team_id}/cup").json()["readiness"]["referenceVariants"]]
    assert "last_cup" not in modes


def test_cup_readiness_shows_last_cup_variant_when_more_than_one_match_played(
    seeded: tuple[TestClient, int],
) -> None:
    """Con más de un partido de Copa jugado, "Última formación en Copa" usa
    la alineación enviada del más reciente y se vuelve el modo por defecto."""
    import asyncio

    client, team_id = seeded
    specs = [(pid, 10_000 - index, 5) for index, pid in enumerate(SUBMITTED_IDS)]
    asyncio.run(_seed_roster(team_id, specs))
    asyncio.run(_set_upcoming_submitted_lineup(None))

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999011, played_at=datetime(2026, 5, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=50,
            home_team_name="Pulgas Arrechas", away_team_name="Rival Anterior",
            home_goals=1, away_goals=0, cup_level=1, cup_level_index=1,
        ))
        session.add(m.Match(
            ht_match_id=999012, played_at=datetime(2026, 6, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=50, away_team_ht_id=team.ht_team_id,
            home_team_name="Rival Reciente", away_team_name="Pulgas Arrechas",
            home_goals=0, away_goals=3, cup_level=1, cup_level_index=1,
            submitted_lineup_json=json.dumps([{"ht_player_id": pid} for pid in SUBMITTED_IDS]),
        ))
        await session.commit()

    asyncio.run(run())

    readiness = client.get(f"/api/v1/teams/{team_id}/cup").json()["readiness"]
    last_cup = next(v for v in readiness["referenceVariants"] if v["mode"] == "last_cup")
    assert last_cup["sourceMatchId"] == 999012
    assert last_cup["sourceOpponent"] == "Rival Reciente"
    assert last_cup["startersCount"] == 11
    assert last_cup["averageStamina"] == 5.0
    assert readiness["defaultMode"] == "last_cup"


def test_cup_readiness_shows_last_league_variant_from_finished_league_match(
    seeded: tuple[TestClient, int],
) -> None:
    """"Última formación en Liga" no tiene el filtro de "más de un partido":
    basta un único partido de Liga FINISHED con alineación conocida."""
    import asyncio

    client, team_id = seeded
    specs = [(pid, 10_000 - index, 5) for index, pid in enumerate(SUBMITTED_IDS)]
    asyncio.run(_seed_roster(team_id, specs))

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999020, played_at=datetime(2026, 6, 1, tzinfo=UTC),
            match_type=1, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=60,
            home_team_name="Pulgas Arrechas", away_team_name="Rival de Liga",
            home_goals=2, away_goals=2,
            submitted_lineup_json=json.dumps([{"ht_player_id": pid} for pid in SUBMITTED_IDS]),
        ))
        await session.commit()

    asyncio.run(run())

    readiness = client.get(f"/api/v1/teams/{team_id}/cup").json()["readiness"]
    last_league = next(v for v in readiness["referenceVariants"] if v["mode"] == "last_league")
    assert last_league["sourceMatchId"] == 999020
    assert last_league["sourceOpponent"] == "Rival de Liga"
    assert last_league["startersCount"] == 11


def test_cup_computes_record_from_finished_matches(
    seeded: tuple[TestClient, int],
) -> None:
    """Un partido de copa ya jugado se cuenta en el récord, con HatStats si
    hay ratings sincronizados — nada de esto es una predicción."""
    import asyncio

    client, team_id = seeded

    # Usa el mismo override de sesión que ya instaló la fixture `seeded`.
    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999001, played_at=datetime(2026, 6, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=42,
            home_team_name="Pulgas Arrechas", away_team_name="Copa Rival",
            home_goals=2, away_goals=1,
        ))
        session.add(m.MatchRating(
            ht_match_id=999001, team_ht_id=team.ht_team_id, is_home=True,
            midfield=10, right_def=10, central_def=10, left_def=10,
            right_att=10, central_att=10, left_att=10,
        ))
        await session.commit()

    asyncio.run(run())

    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200
    body = resp.json()
    assert body["matchesPlayed"] == 1
    assert body["record"] == "1-0-0"
    assert body["goalsFor"] == 2
    assert body["goalsAgainst"] == 1

    row = next(h for h in body["history"] if h["htMatchId"] == 999001)
    assert row["result"] == "V"
    assert row["hatstats"] is not None


def test_cup_estimates_round_by_counting_matches_in_the_same_cup_level(
    seeded: tuple[TestClient, int],
) -> None:
    """CHPP no numera la ronda, pero sí manda CupLevel/CupLevelIndex — HL-116.
    La fixture ya trae un partido de copa (767370369) con CupLevel=1,
    CupLevelIndex=1: eso es la ronda 1. Un segundo partido jugado antes con el
    mismo par es la ronda 1 y este pasa a ser la 2 — nunca un número inventado
    para partidos donde CHPP no mandó esos campos."""
    import asyncio

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999002, played_at=datetime(2026, 7, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=43,
            home_team_name="Pulgas Arrechas", away_team_name="Copa Rival Anterior",
            home_goals=3, away_goals=0, cup_level=1, cup_level_index=1,
        ))
        await session.commit()

    asyncio.run(run())

    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200
    body = resp.json()

    earlier = next(h for h in body["history"] if h["htMatchId"] == 999002)
    assert earlier["round"] == 1

    upcoming = next(nm for nm in body["nextMatches"] if nm["htMatchId"] == 767370369)
    assert upcoming["roundEstimate"] == 2

    assert body["status"]["officialRound"] == 2


def test_cup_resolves_the_cup_name_from_cup_level(seeded: tuple[TestClient, int]) -> None:
    """CupLevel=1 en la fixture es la copa principal de Colombia — el nombre
    no viene en `matches`, se resuelve contra la tabla real de CupID de CHPP
    (HL-116). currentCupName usa el próximo partido si hay uno programado."""
    client, team_id = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200
    body = resp.json()

    assert body["currentCupName"] == "Copa Colombia"
    row = next(nm for nm in body["nextMatches"] if nm["htMatchId"] == 767370369)
    assert row["cupName"] == "Copa Colombia"


def test_cup_shows_the_national_prize_table_for_cup_level_1(
    seeded: tuple[TestClient, int],
) -> None:
    """CupLevel=1 (Copa Colombia) usa la tabla Nacional del manual — desde
    Ronda de 512 hasta Ganador, en orden cronológico."""
    client, team_id = seeded
    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    body = resp.json()

    table = body["prizeTable"]
    assert table[0]["stage"] == "Ronda de 512"
    assert table[0]["amount"] == 120_000
    assert table[0]["status"] == "current"
    assert table[-1]["stage"] == "Campeón"
    assert table[-1]["amount"] == 1_500_000
    # 2026-08-13, pedido explícito: la nota "Premios oficiales convertidos
    # desde SEK..." se quitó por redundante — la tabla de premios ya deja
    # claro que son cifras convertidas.
    assert not any("Premios oficiales" in n for n in body["notes"])


def test_cup_uses_divisional_prizes_and_official_loss_route(
    seeded: tuple[TestClient, int],
) -> None:
    """CupLevel=1 no basta: CupLeagueLevel=7 usa la tabla Divisional.
    Una derrota en la ronda 2 conduce a la Desafío Rubí del mismo nivel."""
    import asyncio

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        team.current_cup_id = 7001
        team.current_cup_name = "Copa Divisional VII"
        team.current_cup_league_level = 7
        team.current_cup_level = 1
        team.current_cup_level_index = 1
        team.current_cup_match_round = 2
        team.current_cup_match_rounds_left = 4
        session.add(m.WorldCup(
            ht_league_id=19, ht_cup_id=7001, cup_name="Copa Divisional VII",
            cup_league_level=7, cup_level=1, cup_level_index=1,
            match_round=2, match_rounds_left=4,
        ))
        session.add(m.WorldCup(
            ht_league_id=19, ht_cup_id=7002, cup_name="Desafío Rubí VII",
            cup_league_level=7, cup_level=2, cup_level_index=2,
            match_round=0, match_rounds_left=4,
        ))
        await session.commit()

    asyncio.run(run())
    body = client.get(f"/api/v1/teams/{team_id}/cup").json()
    assert body["status"]["scope"] == "divisional"
    assert body["prizeTable"][-1]["amount"] == 300_000
    assert body["scenarios"]["loss"]["destination"] == "Desafío Rubí VII"


def test_cup_uses_divisional_prizes_and_official_loss_route(
    seeded: tuple[TestClient, int],
) -> None:
    """CupLevel=1 no basta: CupLeagueLevel=7 usa la tabla Divisional.
    Una derrota en la ronda 2 conduce a la Desafío Rubí del mismo nivel."""
    import asyncio

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        team.current_cup_id = 7001
        team.current_cup_name = "Copa Divisional VII"
        team.current_cup_league_level = 7
        team.current_cup_level = 1
        team.current_cup_level_index = 1
        team.current_cup_match_round = 2
        team.current_cup_match_rounds_left = 4
        session.add(m.WorldCup(
            ht_league_id=19, ht_cup_id=7001, cup_name="Copa Divisional VII",
            cup_league_level=7, cup_level=1, cup_level_index=1,
            match_round=2, match_rounds_left=4,
        ))
        session.add(m.WorldCup(
            ht_league_id=19, ht_cup_id=7002, cup_name="Desafío Rubí VII",
            cup_league_level=7, cup_level=2, cup_level_index=2,
            match_round=0, match_rounds_left=4,
        ))
        await session.commit()

    asyncio.run(run())
    body = client.get(f"/api/v1/teams/{team_id}/cup").json()
    assert body["status"]["scope"] == "divisional"
    assert body["prizeTable"][-1]["amount"] == 300_000
    assert body["scenarios"]["loss"]["destination"] == "Desafío Rubí VII"


def test_cup_current_streak_counts_from_the_most_recent_match_backward(
    seeded: tuple[TestClient, int],
) -> None:
    """Racha: solo hechos ya jugados, cuenta hacia atrás desde el más
    reciente mientras el resultado se repita."""
    import asyncio

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999020, played_at=datetime(2026, 6, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=60,
            home_team_name="Pulgas Arrechas", away_team_name="Rival A",
            home_goals=2, away_goals=1,  # V
        ))
        session.add(m.Match(
            ht_match_id=999021, played_at=datetime(2026, 6, 8, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=61,
            home_team_name="Pulgas Arrechas", away_team_name="Rival B",
            home_goals=0, away_goals=1,  # D
        ))
        session.add(m.Match(
            ht_match_id=999022, played_at=datetime(2026, 6, 15, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=62,
            home_team_name="Pulgas Arrechas", away_team_name="Rival C",
            home_goals=3, away_goals=0,  # V — rompe la racha de derrota anterior
        ))
        await session.commit()

    asyncio.run(run())

    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200
    streak = resp.json()["currentStreak"]
    assert streak == {"count": 1, "result": "V"}


def test_cup_ladder_groups_consecutive_matches_by_cup_level(
    seeded: tuple[TestClient, int],
) -> None:
    """Escalera: agrupa partidos consecutivos por CupLevel real — un hecho,
    no una estimación, distinto de `roundEstimate`."""
    import asyncio

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999030, played_at=datetime(2026, 6, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=70,
            home_team_name="Pulgas Arrechas", away_team_name="Rival A",
            home_goals=1, away_goals=0, cup_level=1, cup_level_index=1,
        ))
        session.add(m.Match(
            ht_match_id=999031, played_at=datetime(2026, 6, 8, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=71,
            home_team_name="Pulgas Arrechas", away_team_name="Rival B",
            home_goals=0, away_goals=2, cup_level=2, cup_level_index=1,
        ))
        await session.commit()

    asyncio.run(run())

    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200
    ladder = resp.json()["ladder"]

    lvl1 = next(e for e in ladder if e["cupLevel"] == 1 and e["fromDate"] == "2026-06-01")
    assert lvl1["matches"] == 1
    assert lvl1["cupName"] == "Copa Colombia"

    lvl2 = next(e for e in ladder if e["cupLevel"] == 2)
    assert lvl2["matches"] == 1
    assert lvl2["cupName"] == "Copa Macarena Esmeralda"


def test_cup_round_estimate_is_none_without_cup_level_data(
    seeded: tuple[TestClient, int],
) -> None:
    """Un partido viejo, sincronizado antes de que se guardara CupLevel, no
    tiene ronda estimada — mostrar un número ahí sería inventarlo."""
    import asyncio

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        session.add(m.Match(
            ht_match_id=999003, played_at=datetime(2026, 5, 1, tzinfo=UTC),
            match_type=3, status="FINISHED",
            home_team_ht_id=team.ht_team_id, away_team_ht_id=44,
            home_team_name="Pulgas Arrechas", away_team_name="Copa Sin Nivel",
            home_goals=1, away_goals=0,  # cup_level/cup_level_index quedan en -1 por defecto
        ))
        await session.commit()

    asyncio.run(run())

    resp = client.get(f"/api/v1/teams/{team_id}/cup")
    assert resp.status_code == 200
    row = next(h for h in resp.json()["history"] if h["htMatchId"] == 999003)
    assert row["round"] is None


def test_cup_does_not_treat_legacy_zero_rounds_left_as_champion(
    seeded: tuple[TestClient, int],
) -> None:
    """Migration defaults are not official CHPP facts. A legacy WorldCup row
    with MatchRound=-1 and MatchRoundsLeft=0 stays unknown until the next
    worlddetails/teamdetails sync; it must not award the title in the UI."""
    import asyncio

    from sqlalchemy import select

    client, team_id = seeded

    async def run() -> None:
        gen = app.dependency_overrides[get_session]()
        session = await gen.__anext__()
        team = await session.get(m.Team, team_id)
        team.current_cup_match_round = None
        team.current_cup_match_rounds_left = None
        cup_row = await session.scalar(
            select(m.WorldCup).where(m.WorldCup.ht_cup_id == team.current_cup_id)
        )
        cup_row.match_round = -1
        cup_row.match_rounds_left = 0
        await session.commit()

    asyncio.run(run())

    body = client.get(f"/api/v1/teams/{team_id}/cup").json()
    assert body["status"]["officialRound"] is None
    assert body["status"]["roundsLeft"] is None
    assert body["status"]["stageLabel"] is None
    assert body["goal"]["stage"] is None
    assert body["goal"]["securedAmount"] == 0
    assert body["scenarios"]["win"]["nextStage"] is None
