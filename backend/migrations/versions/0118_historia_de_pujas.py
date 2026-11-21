"""La historia de las pujas de cada anuncio.

2026-11-21, pedido del usuario: avisar cuando la puja más alta de «Esperando su
precio» supera el precio de equilibrio de un jugador. Para saber si lo CRUZÓ
desde la visita anterior hace falta la puja de entonces, y `bid_price` sólo
guarda la última. Una lista de `[momento, puja]`, una entrada cada vez que la
puja cambia.

Revision ID: 0118
Revises: 0117
"""

import sqlalchemy as sa
from alembic import op

revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("market_sales") as batch_op:
        batch_op.add_column(
            sa.Column("bid_history_json", sa.Text(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("market_sales") as batch_op:
        batch_op.drop_column("bid_history_json")
