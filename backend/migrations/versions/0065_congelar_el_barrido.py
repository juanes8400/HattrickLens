"""Congelar el eje del barrido de comisiones.

Sin esto el eje se recalculaba en cada pulsacion contra la tabla viva: cada
expediente cerrado borraba una casilla, las posiciones se corrian y las marcas
ya pintadas saltaban de sitio. Guardando la cola tal como estaba al empezar,
la casilla de un jugador es suya hasta que el barrido termina.

Revision ID: 0065
Revises: 0064
"""
import sqlalchemy as sa
from alembic import op

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("sweep_axis_json", sa.Text(), nullable=True))
    op.add_column("teams", sa.Column("sweep_started_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "sweep_started_at")
    op.drop_column("teams", "sweep_axis_json")
