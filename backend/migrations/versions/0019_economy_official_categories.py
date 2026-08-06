"""Partidas oficiales desagregadas de economy.xml.

CHPP 1.5 puede entregar sponsor bonuses, compras/ventas de jugadores y obra
de estadio como partidas independientes. Son NULL en snapshots históricos que
provienen de la variante antigua del XML: cero no significa "no vino".

Revision ID: 0019
"""
import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in (
        "income_sponsor_bonuses",
        "income_sold_players",
        "income_sold_players_commission",
        "costs_bought_players",
        "costs_arena_building",
    ):
        op.add_column("economy_snapshots", sa.Column(name, sa.BigInteger(), nullable=True))


def downgrade() -> None:
    for name in (
        "costs_arena_building",
        "costs_bought_players",
        "income_sold_players_commission",
        "income_sold_players",
        "income_sponsor_bonuses",
    ):
        op.drop_column("economy_snapshots", name)
