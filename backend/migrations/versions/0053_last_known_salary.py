"""El último salario conocido de un jugador, aunque ya no sea nuestro.

2026-08-21. Un jugador comprado y vendido entre dos sincronizaciones no deja
ningún snapshot, así que su coste de salarios salía 0 y su saldo aparecía
mejor de lo que fue. `playerdetails.xml` sí devuelve `<Salary>` para él —
verificado en vivo con uno ya vendido, jugando en otro club—, de modo que el
dato existe: lo que faltaba era guardarlo.

Revision ID: 0053
"""
import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("last_known_salary", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "last_known_salary")
