"""Saldo neto por jugador (HL-161): columnas de la tabla "Detalle" que
faltaban frente al Excel del usuario — país de origen, carácter,
especialidad, TSI en compra/venta, equipo comprador y país destino.

Revision ID: 0027
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("native_country", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("agreeability", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("specialty", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("tsi_at_purchase", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tsi_at_sale", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("buyer_team_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("destination_country", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("destination_country")
        batch_op.drop_column("buyer_team_id")
        batch_op.drop_column("tsi_at_sale")
        batch_op.drop_column("tsi_at_purchase")
        batch_op.drop_column("specialty")
        batch_op.drop_column("agreeability")
        batch_op.drop_column("native_country")
