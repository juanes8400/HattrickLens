"""match_weather: el clima de la región donde se juega el próximo partido.

Revision ID: 0051
Revises: 0050
"""
import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_weather",
        # Integer y no BigInteger en la PK: sqlite solo hace AUTOINCREMENT
        # sobre INTEGER, y con BIGINT el primer INSERT real revienta aunque
        # los tests pasen.
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ht_match_id", sa.BigInteger(), nullable=False),
        sa.Column("venue_ht_team_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_region_id", sa.BigInteger(), nullable=False),
        sa.Column("region_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("weather_today", sa.SmallInteger(), nullable=False, server_default="-1"),
        sa.Column("weather_tomorrow", sa.SmallInteger(), nullable=False, server_default="-1"),
        sa.Column("forecast_taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_match_weather_ht_match_id", "match_weather", ["ht_match_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_match_weather_ht_match_id", table_name="match_weather")
    op.drop_table("match_weather")
