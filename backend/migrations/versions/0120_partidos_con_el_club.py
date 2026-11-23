"""Partidos con el club actual, según Hattrick.

2026-11-23, pedido del usuario: Hattrick no deja poner en venta a un jugador
más veces que partidos ha jugado con el club. `players.xml` publica ese número
(`MatchesCurrentTeam`) y hasta hoy no se leía. Vacío en las fotos de antes.

Revision ID: 0120
Revises: 0119
"""

import sqlalchemy as sa
from alembic import op

revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.add_column(sa.Column("matches_current_team", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.drop_column("matches_current_team")
