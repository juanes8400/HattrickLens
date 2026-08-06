"""Persistir TeamAttitude en match_ratings — HL-2xx, módulo de rivales.

`parse_matchdetails` ya extraía este campo (`payload["attitude"]`) pero se
descartaba al persistir. Se necesita, junto a `tactic_type`, para el
historial real de táctica/actitud del rival — dato de partidos ya
finalizados (hecho público permanente), no un estado que se esté trackeando.

Revision ID: 0017
"""
import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_ratings", sa.Column("attitude", sa.SmallInteger, nullable=True))


def downgrade() -> None:
    op.drop_column("match_ratings", "attitude")
