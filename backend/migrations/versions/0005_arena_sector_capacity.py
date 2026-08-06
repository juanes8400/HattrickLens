"""Capacidad del estadio por sector.

Sin estas columnas la capacidad de cada sector había que deducirla del reparto
de lo vendido, y ese reparto vuelve indetectable un lleno: la ocupación sale
idéntica en los cuatro sectores por construcción. La demanda censurada —lo que
más importa para decidir una ampliación— quedaba invisible.

Revision ID: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

COLUMNS = ("capacity_terraces", "capacity_basic", "capacity_roof", "capacity_vip")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column("stadium_history", sa.Column(name, sa.Integer, nullable=True))


def downgrade() -> None:
    for name in COLUMNS:
        op.drop_column("stadium_history", name)
