from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.application.queries.post_match_training import PostMatchTrainingService
from app.infrastructure.db import models as m

from .conftest import seeded_session


@pytest.mark.parametrize("position_code", [102, 105, 109, 110])
def test_long_passing_trains_all_defenders_and_midfielders(position_code: int) -> None:
    """Centrales, laterales, medios interiores y extremos reciben el tipo 10."""
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    assert service._position_share(10, position_code) == "full"


def test_long_passing_does_not_train_forwards() -> None:
    service = PostMatchTrainingService(None)  # type: ignore[arg-type]
    assert service._position_share(10, 113) == "none"


@pytest.mark.asyncio
async def test_post_match_training_counts_real_forward_minutes() -> None:
    factory, team_id = await seeded_session()
    now = datetime.now(UTC)

    async with factory() as s:
        player = (
            await s.execute(
                select(m.Player)
                .where(m.Player.team_id == team_id, m.Player.left_team_at.is_(None))
                .limit(1)
            )
        ).scalar_one()
        team = await s.get(m.Team, team_id)
        assert team is not None

        world = (await s.execute(select(m.WorldContext).limit(1))).scalar_one()
        world.training_date = now + timedelta(days=1)
        world.refreshed_at = now

        s.add(
            m.Match(
                ht_match_id=900001,
                played_at=now,
                match_type=1,
                status="Finished",
                home_team_ht_id=team.ht_team_id,
                away_team_ht_id=123,
                home_team_name=team.name,
                away_team_name="Rival",
                home_goals=2,
                away_goals=0,
            )
        )
        s.add(
            m.PlayerMatchRating(
                player_id=player.id,
                ht_match_id=900001,
                position_code=13,
                played_minutes=90,
                rating=7.0,
                captured_at=now,
            )
        )
        await s.commit()

    result = await PostMatchTrainingService(s).get(team_id)

    assert result is not None
    assert result["recommendation"]["recommendable"] is True
    assert result["recommendation"]["trainingType"] != 1
    scoring = next(o for o in result["options"] if o["trainingType"] == 4)
    stamina = next(o for o in result["options"] if o["trainingType"] == 1)
    keeper = next(o for o in result["options"] if o["trainingType"] == 9)
    assert stamina["recommendable"] is False
    assert scoring["equivalentMinutes"] == 90
    assert keeper["equivalentMinutes"] == 0

    row = next(p for p in result["players"] if p["htPlayerId"] == player.ht_player_id)
    assert row["exposureByTrainingType"]["4"] == 1.0
    assert "9" not in row["exposureByTrainingType"]
    assert row["segments"][0]["position"] == "Delantero medio"
