"""Predicción CHPP de ratings para las órdenes enviadas.

Revision ID: 0037
"""
import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("submitted_tactic_skill", sa.SmallInteger(), nullable=True))
        for name in (
            "midfield", "right_def", "central_def", "left_def",
            "right_att", "central_att", "left_att",
        ):
            batch_op.add_column(
                sa.Column(f"submitted_rating_{name}", sa.SmallInteger(), nullable=True)
            )
        batch_op.add_column(
            sa.Column("submitted_ratings_captured_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_column("submitted_ratings_captured_at")
        for name in (
            "left_att", "central_att", "right_att",
            "left_def", "central_def", "right_def", "midfield",
        ):
            batch_op.drop_column(f"submitted_rating_{name}")
        batch_op.drop_column("submitted_tactic_skill")
