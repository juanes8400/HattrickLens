"""Saldo neto por jugador (HL-161, 2026-08-04): agregados de
transfersteam.xml <Stats> (histórico completo del equipo) para los KPI de
"Resumen", y marca de agua del backfill paginado de transferencias.

Revision ID: 0028
"""
import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(
            sa.Column("transfer_total_buys", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("transfer_total_sales", sa.BigInteger(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("transfer_number_buys", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("transfer_number_sales", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("last_transfer_id_seen", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("last_transfer_id_seen")
        batch_op.drop_column("transfer_number_sales")
        batch_op.drop_column("transfer_number_buys")
        batch_op.drop_column("transfer_total_sales")
        batch_op.drop_column("transfer_total_buys")
