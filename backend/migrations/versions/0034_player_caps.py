"""2026-08-05, pedido explícitamente: saber si un jugador tiene partidos con
la selección nacional. playerdetails.xml expone Caps/CapsU20 (totales de
carrera) y no se guardaban en ningún lado — se añaden a player_snapshots,
carry-forward como career_assists/last_match_* (ver repositories.py).

Revision ID: 0034
"""
import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.add_column(sa.Column("career_caps", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("career_caps_u20", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.drop_column("career_caps_u20")
        batch_op.drop_column("career_caps")
