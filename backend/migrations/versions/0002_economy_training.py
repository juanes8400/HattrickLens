"""Economy y training snapshots (append-only, diffing por content_hash).

Revision ID: 0002
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economy_snapshots",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("sync_id", sa.BigInteger, sa.ForeignKey("syncs.id"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cash", sa.BigInteger, nullable=False),
        sa.Column("expected_cash", sa.BigInteger, nullable=False),
        sa.Column("sponsors_popularity", sa.SmallInteger, nullable=False),
        sa.Column("supporters_popularity", sa.SmallInteger, nullable=False),
        sa.Column("fan_club_size", sa.Integer, nullable=False),
        sa.Column("income_spectators", sa.Integer, nullable=False),
        sa.Column("income_sponsors", sa.Integer, nullable=False),
        sa.Column("income_financial", sa.Integer, nullable=False),
        sa.Column("income_temporary", sa.BigInteger, nullable=False),
        sa.Column("income_sum", sa.BigInteger, nullable=False),
        sa.Column("costs_arena", sa.Integer, nullable=False),
        sa.Column("costs_players", sa.Integer, nullable=False),
        sa.Column("costs_financial", sa.Integer, nullable=False),
        sa.Column("costs_staff", sa.Integer, nullable=False),
        sa.Column("costs_temporary", sa.BigInteger, nullable=False),
        sa.Column("costs_youth", sa.Integer, nullable=False),
        sa.Column("costs_sum", sa.BigInteger, nullable=False),
        sa.Column("expected_weeks_total", sa.BigInteger, nullable=False),
        sa.Column("last_income_sum", sa.BigInteger, nullable=False),
        sa.Column("last_costs_sum", sa.BigInteger, nullable=False),
        sa.Column("last_weeks_total", sa.BigInteger, nullable=False),
        sa.Column("content_hash", sa.LargeBinary(32), nullable=False),
    )
    op.create_index("ix_es_team_time", "economy_snapshots", ["team_id", "captured_at"])

    op.create_table(
        "training_snapshots",
        sa.Column("id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("sync_id", sa.BigInteger, sa.ForeignKey("syncs.id"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("training_type", sa.SmallInteger, nullable=False),
        sa.Column("training_level", sa.SmallInteger, nullable=False),
        sa.Column("new_training_level", sa.SmallInteger, nullable=False),
        sa.Column("stamina_part", sa.SmallInteger, nullable=False),
        sa.Column("last_training_type", sa.SmallInteger, nullable=False),
        sa.Column("last_training_level", sa.SmallInteger, nullable=False),
        sa.Column("last_stamina_part", sa.SmallInteger, nullable=False),
        sa.Column("trainer_ht_id", sa.BigInteger, nullable=False),
        sa.Column("trainer_name", sa.String(128), nullable=False),
        sa.Column("morale", sa.SmallInteger, nullable=False, server_default="-1"),
        sa.Column("self_confidence", sa.SmallInteger, nullable=False, server_default="-1"),
        sa.Column("formation_xp_json", sa.String(1000)),
        sa.Column("content_hash", sa.LargeBinary(32), nullable=False),
    )
    op.create_index("ix_ts_team_time", "training_snapshots", ["team_id", "captured_at"])


def downgrade() -> None:
    op.drop_table("training_snapshots")
    op.drop_table("economy_snapshots")
