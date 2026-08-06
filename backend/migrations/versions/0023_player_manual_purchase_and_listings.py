"""Saldo neto por jugador (HL-161): compra manual + contador de listados.

`purchase_price_manual`/`purchased_at_manual`: fallback para cuando ni
transfersteam.xml ni transfersplayer.xml traen una compra real — el usuario
lo escribe a mano. Se prioriza siempre el dato real sobre el manual.

`listing_count`: cuántas veces se ha puesto en venta. CHPP no da historial
de esto (solo pujas actuales), así que se cuenta hacia adelante desde que
existe esta columna — 0 por defecto, no es una migración de datos.

Revision ID: 0023
"""
import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("purchase_price_manual", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("purchased_at_manual", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "listing_count", sa.SmallInteger(), nullable=False, server_default="0"
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("listing_count")
        batch_op.drop_column("purchased_at_manual")
        batch_op.drop_column("purchase_price_manual")
