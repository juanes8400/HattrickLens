"""Distinguir categoría ausente de valor cero en economy.xml.

Las partidas temporales son campos de la variante antigua. En XML recientes
pueden no llegar porque CHPP entrega partidas más precisas; NULL conserva esa
diferencia y evita mostrar un cero inventado.

Revision ID: 0020
"""
import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("economy_snapshots") as batch_op:
        batch_op.alter_column(
            "income_temporary", existing_type=sa.BigInteger(), nullable=True
        )
        batch_op.alter_column(
            "costs_temporary", existing_type=sa.BigInteger(), nullable=True
        )


def downgrade() -> None:
    op.execute("UPDATE economy_snapshots SET income_temporary = 0 WHERE income_temporary IS NULL")
    op.execute("UPDATE economy_snapshots SET costs_temporary = 0 WHERE costs_temporary IS NULL")
    with op.batch_alter_table("economy_snapshots") as batch_op:
        batch_op.alter_column(
            "income_temporary", existing_type=sa.BigInteger(), nullable=False
        )
        batch_op.alter_column(
            "costs_temporary", existing_type=sa.BigInteger(), nullable=False
        )
