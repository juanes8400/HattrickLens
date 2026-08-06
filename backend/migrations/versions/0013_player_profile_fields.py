"""Campos de perfil de jugador ya presentes en CHPP y hasta ahora descartados.

`players.xml` (2.6, ya sincronizado en cada sync) trae Loyalty, Leadership,
Agreeability, Aggressiveness, Honesty, MotherClubBonus, CountryID, goles por
competición/carrera y datos del entrenador-jugador — todo se parseaba en
algunos casos (Specialty) o ni eso, y se descartaba antes de tocar la base de
datos. Cero llamadas CHPP nuevas para estos campos.

`purchase_price`/`purchased_at` y `mother_club_team_name` en `players` (no en
`player_snapshots`: son hechos de una vez, no algo que cambie sync a sync) se
llenan con fases posteriores (transfersteam.xml, playerdetails.xml).

`last_match_*` en `player_snapshots` también vienen de playerdetails.xml —
se actualizan sobre el snapshot más reciente en vez de crear uno nuevo, ya
que no son un cambio de habilidades.

Revision ID: 0013
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in (
        "specialty", "loyalty", "leadership", "agreeability", "aggressiveness", "honesty",
        "country_id", "league_goals", "cup_goals", "friendlies_goals", "career_goals",
        "career_hattricks", "career_assists", "player_trainer_skill_level",
        "player_trainer_type",
    ):
        op.add_column(
            "player_snapshots", sa.Column(name, sa.Integer, nullable=False, server_default="0")
        )
    op.add_column(
        "player_snapshots",
        sa.Column("mother_club_bonus", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "player_snapshots", sa.Column("last_match_ht_id", sa.BigInteger, nullable=True)
    )
    op.add_column(
        "player_snapshots",
        sa.Column("last_match_position_code", sa.SmallInteger, nullable=True),
    )
    op.add_column(
        "player_snapshots",
        sa.Column("last_match_played_minutes", sa.SmallInteger, nullable=True),
    )
    op.add_column(
        "player_snapshots", sa.Column("last_match_rating", sa.Float, nullable=True)
    )

    op.add_column("players", sa.Column("purchase_price", sa.Integer, nullable=True))
    op.add_column("players", sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("players", sa.Column("mother_club_team_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "mother_club_team_name")
    op.drop_column("players", "purchased_at")
    op.drop_column("players", "purchase_price")

    op.drop_column("player_snapshots", "last_match_rating")
    op.drop_column("player_snapshots", "last_match_played_minutes")
    op.drop_column("player_snapshots", "last_match_position_code")
    op.drop_column("player_snapshots", "last_match_ht_id")
    op.drop_column("player_snapshots", "mother_club_bonus")
    for name in (
        "specialty", "loyalty", "leadership", "agreeability", "aggressiveness", "honesty",
        "country_id", "league_goals", "cup_goals", "friendlies_goals", "career_goals",
        "career_hattricks", "career_assists", "player_trainer_skill_level",
        "player_trainer_type",
    ):
        op.drop_column("player_snapshots", name)
