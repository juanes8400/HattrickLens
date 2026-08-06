"""LeagueLevelUnitID del equipo, leído de teamdetails.

leaguedetails.xml se pide por serie (LeagueLevelUnitID), no por equipo. Sin
guardar este id no hay forma de saber qué serie sincronizar para traer la
clasificación de liga.

Revision ID: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("series_ht_id", sa.BigInteger, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("teams", "series_ht_id")
