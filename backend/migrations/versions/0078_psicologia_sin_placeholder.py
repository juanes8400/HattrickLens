"""El -1 temporal de psicologia no es un nivel.

Durante un partido, training.xml puede responder -1 para Morale o
SelfConfidence aunque el estado real del club no haya cambiado. Desde esta
revision el sincronizador conserva la ultima lectura valida de cada indicador
por separado. Si la primera lectura de un equipo ocurre justo durante ese
periodo, la ausencia se guarda como NULL: nunca como un nivel -1.

Las filas historicas con -1 no se reescriben aqui. Su content_hash se calculo
con aquel payload y cambiar solamente la columna rompería la correspondencia
entre foto y huella. Los lectores las ignoran y el siguiente sync deja una
cola valida sin inventar historia.

Revision ID: 0078
Revises: 0077
"""

import sqlalchemy as sa
from alembic import op

revision = "0078"
down_revision = "0077"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("training_snapshots") as batch_op:
        batch_op.alter_column(
            "morale",
            existing_type=sa.SmallInteger(),
            nullable=True,
            server_default=None,
        )
        batch_op.alter_column(
            "self_confidence",
            existing_type=sa.SmallInteger(),
            nullable=True,
            server_default=None,
        )


def downgrade() -> None:
    op.execute("UPDATE training_snapshots SET morale = -1 WHERE morale IS NULL")
    op.execute("UPDATE training_snapshots SET self_confidence = -1 WHERE self_confidence IS NULL")
    with op.batch_alter_table("training_snapshots") as batch_op:
        batch_op.alter_column(
            "morale",
            existing_type=sa.SmallInteger(),
            nullable=False,
            server_default="-1",
        )
        batch_op.alter_column(
            "self_confidence",
            existing_type=sa.SmallInteger(),
            nullable=False,
            server_default="-1",
        )
