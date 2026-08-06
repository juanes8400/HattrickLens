"""Saldo neto por jugador (HL-161): precio real de venta.

`sale_price`/`sold_at`, de transfersteam.xml (TransferType="S", vendedor ==
nosotros) — mismo mecanismo y fuente que `purchase_price`, que solo
capturaba compras hasta ahora.

Revision ID: 0025
"""
import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("sale_price", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sold_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("sold_at")
        batch_op.drop_column("sale_price")
