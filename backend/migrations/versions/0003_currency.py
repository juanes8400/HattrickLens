"""Tasa de conversión de moneda por equipo.

CHPP entrega todos los importes en la moneda base del juego. Cada país tiene su
CurrencyRate (Colombia = 10, verificado contra Hattrick Control en 6 campos
independientes). Sin esta conversión el producto muestra el dinero inflado.

Revision ID: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("currency_rate", sa.Float, nullable=False, server_default="1.0"),
    )
    op.add_column(
        "teams",
        sa.Column("currency_name", sa.String(16), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("teams", "currency_name")
    op.drop_column("teams", "currency_rate")
