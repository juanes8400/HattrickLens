"""Habilidad entrenada inferida de cada etapa cerrada.

Revision ID: 0070
Revises: 0069
"""

import sqlalchemy as sa
from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("player_stints") as batch_op:
        batch_op.add_column(sa.Column("derived_training_skill", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("derived_training_levels", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("derived_training_method", sa.String(32), nullable=True))
        batch_op.add_column(
            sa.Column("derived_training_computed_at", sa.DateTime(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("player_stints") as batch_op:
        batch_op.drop_column("derived_training_computed_at")
        batch_op.drop_column("derived_training_method")
        batch_op.drop_column("derived_training_levels")
        batch_op.drop_column("derived_training_skill")
