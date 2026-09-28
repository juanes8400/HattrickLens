"""2026-09-28, senalado en la revision de la PR #4: un pronostico es de UN club.

Un partido tiene dos lados y los dos pueden estar conectados a HT Lens --la
misma cuenta con sus dos clubes, o dos managers distintos-- y el pronostico no
es el mismo para los dos: el motor de zonas usa la alineacion que ESE manager
envio. Con la clave unica solo en `ht_match_id`, el segundo en abrir Liga
pisaba la fila del primero, y despues del partido su parte le enseñaba una
terna que nunca vio.

La tabla se creo hace un dia y todavia no ha llegado a produccion, asi que las
filas que pueda haber en local no tienen dueño que adivinar: se vacian. Es
preferible perder un pronostico de prueba a atribuirselo al club equivocado,
que es justo el fallo que se esta cerrando.

Revision ID: 0091
Revises: 0090
"""

import sqlalchemy as sa
from alembic import op

revision = "0091"
down_revision = "0090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM match_predictions"))
    with op.batch_alter_table("match_predictions") as batch_op:
        batch_op.drop_index("ix_match_predictions_ht_match_id")
        batch_op.add_column(sa.Column("team_id", sa.BigInteger(), nullable=False))
        batch_op.create_index("ix_match_predictions_ht_match_id", ["ht_match_id"])
        batch_op.create_index("ix_match_predictions_team_id", ["team_id"])
        batch_op.create_unique_constraint(
            "uq_match_predictions_partido_equipo", ["ht_match_id", "team_id"]
        )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM match_predictions"))
    with op.batch_alter_table("match_predictions") as batch_op:
        batch_op.drop_constraint("uq_match_predictions_partido_equipo", type_="unique")
        batch_op.drop_index("ix_match_predictions_team_id")
        batch_op.drop_index("ix_match_predictions_ht_match_id")
        batch_op.drop_column("team_id")
        batch_op.create_index("ix_match_predictions_ht_match_id", ["ht_match_id"], unique=True)
