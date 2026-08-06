"""Saldo neto por jugador (HL-161): estado transitorio de listado.

`currently_listed` detecta una aparición NUEVA en el mercado (False→True
entre dos syncs) para poder incrementar `listing_count` — CHPP solo da una
foto del momento (currentbids.xml), nunca un historial.

Revision ID: 0024
"""
import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(
            sa.Column(
                "currently_listed", sa.Boolean(), nullable=False, server_default="0"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("currently_listed")
