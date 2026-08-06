"""LeagueLevel/MaxLevel del equipo — HL-145.

Hacen falta para saber si el 1º puede ascender (no si ya está en primera
división) y si el 7º-8º puede descender (no si ya está en la última) — sin
esto, la simulación de temporada asumía siempre que había una división
arriba y otra abajo, lo cual es falso en los dos extremos de la pirámide.

Revision ID: 0012
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams", sa.Column("league_level", sa.SmallInteger, nullable=False, server_default="-1")
    )
    op.add_column(
        "teams", sa.Column("max_level", sa.SmallInteger, nullable=False, server_default="-1")
    )


def downgrade() -> None:
    op.drop_column("teams", "max_level")
    op.drop_column("teams", "league_level")
