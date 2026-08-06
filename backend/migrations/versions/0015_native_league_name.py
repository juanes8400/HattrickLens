"""Nacionalidad real del jugador — HL-15x. `NativeLeagueName` ya viene como
texto en playerdetails.xml (fase B, ya se sincroniza) — no hace falta tabla
país→nombre propia. Hecho de una vez, como mother_club_team_name.

Revision ID: 0015
"""
import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("native_league_name", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "native_league_name")
