"""Lo que suponíamos de cada lado al predecir un partido.

2026-11-22, pedido del usuario: la autopsia del último partido. Para decir «el
rival vino más fuerte de lo que pensábamos» hay que saber qué pensábamos: las
valoraciones de los dos lados y la táctica con que entraron en el motor. Una
columna JSON en la fila de lo dicho; vacía en los partidos de antes.

Revision ID: 0119
Revises: 0118
"""

import sqlalchemy as sa
from alembic import op

revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("match_predictions") as batch_op:
        batch_op.add_column(sa.Column("supuesto_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("match_predictions") as batch_op:
        batch_op.drop_column("supuesto_json")
