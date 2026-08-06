"""Desglose por categoría de la semana ya cerrada de economy.xml.

Hasta ahora sólo se guardaba el agregado (last_income_sum/last_costs_sum).
Sin el desglose por categoría de semanas cerradas no se puede sumar varias
semanas para un flujo (Sankey) agregado: sólo la semana en curso tenía
categorías. Todas nullable — CHPP no las trae en todas las versiones, y los
snapshots ya sincronizados no las tienen; NULL dice "no se sabe", nunca cero.

Revision ID: 0021
"""
import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

COLUMNS = [
    "last_income_spectators",
    "last_income_sponsors",
    "last_income_financial",
    "last_income_sold_players",
    "last_income_sold_players_commission",
    "last_income_temporary",
    "last_costs_arena",
    "last_costs_players",
    "last_costs_financial",
    "last_costs_staff",
    "last_costs_youth",
    "last_costs_bought_players",
    "last_costs_arena_building",
    "last_costs_temporary",
]


def upgrade() -> None:
    with op.batch_alter_table("economy_snapshots") as batch_op:
        for name in COLUMNS:
            batch_op.add_column(sa.Column(name, sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("economy_snapshots") as batch_op:
        for name in COLUMNS:
            batch_op.drop_column(name)
