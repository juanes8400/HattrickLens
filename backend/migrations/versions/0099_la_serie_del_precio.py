"""Las lecturas del precio por comparables, para poder dibujar la serie.

2026-10-07, pedido del usuario: ver como cambia el precio en el tiempo, con
la nube de ventas de cada lectura y no solo la media.

POR QUE UNA TABLA Y NO UN CALCULO. `market_sales` sabe como esta el fondo
AHORA, no como estuvo. Cuando una venta se resuelve, su puja se pisa con el
precio de cierre y el valor anterior desaparece; cuando una venta caduca y la
sustituye otra, la vieja se va. Sin guardar la lectura no hay forma de
reconstruir que decia el numero la semana pasada.

UNA FILA POR CAMBIO, no por fecha. Se anota cuando la estimacion de ese
jugador cambia de verdad, y no cuando pasa el tiempo.

`prices_json` lleva los precios de esa lectura con su estado, porque la
grafica enseña la nube entera: la dispersion es la mitad de lo que hay que
juzgar. En la medicion del 2026-10-07 la media de un jugador era 438.701 y
sus siete ventas iban de 1.000 a 1.326.000; decir solo la media callaba eso.

Revision ID: 0099
Revises: 0098
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0099"
down_revision = "0098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_estimates",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_player_id", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", UtcDateTime(), nullable=False),
        sa.Column("mean_price", sa.BigInteger(), nullable=True),
        sa.Column("median_price", sa.BigInteger(), nullable=True),
        sa.Column("n", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_weight", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provisional", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prices_json", sa.Text(), nullable=False, server_default="[]"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_market_estimates_team_id", "market_estimates", ["team_id"])
    op.create_index("ix_market_estimates_ht_player_id", "market_estimates", ["ht_player_id"])
    op.create_index(
        "ix_market_estimates_serie",
        "market_estimates",
        ["team_id", "ht_player_id", "captured_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_estimates_serie", table_name="market_estimates")
    op.drop_index("ix_market_estimates_ht_player_id", table_name="market_estimates")
    op.drop_index("ix_market_estimates_team_id", table_name="market_estimates")
    op.drop_table("market_estimates")
