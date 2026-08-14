"""Alineación y órdenes enviadas para próximos partidos propios.

Revision ID: 0036
"""
import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("source_system", sa.String(32), nullable=True))
        batch_op.add_column(sa.Column("orders_given", sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column("submitted_lineup_json", sa.String(4000), nullable=True))
        batch_op.add_column(sa.Column("submitted_tactic_type", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("submitted_attitude", sa.SmallInteger(), nullable=True))
        batch_op.add_column(
            sa.Column("submitted_coach_modifier", sa.SmallInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("submitted_orders_captured_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_column("submitted_orders_captured_at")
        batch_op.drop_column("submitted_coach_modifier")
        batch_op.drop_column("submitted_attitude")
        batch_op.drop_column("submitted_tactic_type")
        batch_op.drop_column("submitted_lineup_json")
        batch_op.drop_column("orders_given")
        batch_op.drop_column("source_system")
