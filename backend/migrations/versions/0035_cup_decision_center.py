"""Estado oficial y calendario de Copa para el centro de decisión.

Revision ID: 0035
"""
import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("still_in_cup", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("current_cup_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("current_cup_name", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("current_cup_league_level", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("current_cup_level", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("current_cup_level_index", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("current_cup_match_round", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("current_cup_match_rounds_left", sa.SmallInteger(), nullable=True))

    with op.batch_alter_table("world_context") as batch_op:
        batch_op.add_column(
            sa.Column("league_system_id", sa.SmallInteger(), nullable=False, server_default="1")
        )
        batch_op.add_column(sa.Column("cup_match_date", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("world_cups") as batch_op:
        batch_op.drop_constraint("uq_world_cup_key", type_="unique")
        batch_op.add_column(
            sa.Column("match_round", sa.SmallInteger(), nullable=False, server_default="-1")
        )
        batch_op.add_column(
            sa.Column("match_rounds_left", sa.SmallInteger(), nullable=False, server_default="0")
        )
        batch_op.create_unique_constraint(
            "uq_world_cup_key",
            ["ht_league_id", "cup_league_level", "cup_level", "cup_level_index"],
        )


def downgrade() -> None:
    with op.batch_alter_table("world_cups") as batch_op:
        batch_op.drop_constraint("uq_world_cup_key", type_="unique")
        batch_op.drop_column("match_rounds_left")
        batch_op.drop_column("match_round")
        batch_op.create_unique_constraint(
            "uq_world_cup_key", ["ht_league_id", "cup_level", "cup_level_index"]
        )
    with op.batch_alter_table("world_context") as batch_op:
        batch_op.drop_column("cup_match_date")
        batch_op.drop_column("league_system_id")
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("current_cup_match_rounds_left")
        batch_op.drop_column("current_cup_match_round")
        batch_op.drop_column("current_cup_level_index")
        batch_op.drop_column("current_cup_level")
        batch_op.drop_column("current_cup_league_level")
        batch_op.drop_column("current_cup_name")
        batch_op.drop_column("current_cup_id")
        batch_op.drop_column("still_in_cup")
