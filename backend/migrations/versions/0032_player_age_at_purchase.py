"""2026-08-05: edad reconstruida en el momento de la COMPRA (misma técnica
que age_*_at_sale, ancla distinta) — pedida para la columna "Edad de
compra" de la tabla Detalle (43 columnas, HL-161).

Revision ID: 0032
"""
import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("age_years_at_purchase", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("age_days_at_purchase", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("age_days_at_purchase")
        batch_op.drop_column("age_years_at_purchase")
