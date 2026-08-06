"""Confirmación manual del momento de carrera — HL-15x #93. La app sugiere
(career_stage_engine), el usuario confirma vía la ficha de jugador; nunca se
sobreescribe la confirmación automáticamente.

Revision ID: 0016
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("players", sa.Column("confirmed_career_stage", sa.String(32), nullable=True))
    op.add_column(
        "players", sa.Column("confirmed_career_stage_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("players", "confirmed_career_stage_at")
    op.drop_column("players", "confirmed_career_stage")
