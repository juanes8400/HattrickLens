"""Techo alcanzado por habilidad en los snapshots juveniles.

CHPP publica `IsMaxReached` en cada habilidad juvenil y la app lo estaba
tirando. Es un dato distinto del par nivel/techo: dice "esto ya no sube" y se
sabe aunque el techo en sí siga oculto. Sin él no se puede decidir a quién
entrenar — una habilidad topada no mejora por mucho que se la entrene.

Revision ID: 0049
Revises: 0048
"""
import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None

SKILLS = (
    "keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces",
)


def upgrade() -> None:
    for skill in SKILLS:
        op.add_column(
            "youth_snapshots",
            # `server_default` para que las filas ya guardadas queden en False:
            # de ellas no se sabe si el techo estaba tocado, y "no tocado" es
            # el supuesto que no borra a nadie del cálculo. El próximo sync
            # trae el valor real.
            sa.Column(
                f"{skill}_max_reached",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    for skill in SKILLS:
        op.drop_column("youth_snapshots", f"{skill}_max_reached")
