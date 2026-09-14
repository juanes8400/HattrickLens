"""Historial completo e incremental de partidos propios.

La primera conexión recorre matchesarchive.xml desde la fundación del club y
las siguientes sólo consultan desde la última marca de agua. Las filas viejas
se guardan como resumen para no disparar cientos de matchdetails automáticos.

Revision ID: 0086
Revises: 0085
"""

import sqlalchemy as sa
from alembic import op

revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column("founded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "teams",
        sa.Column(
            "matches_history_complete",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "teams",
        sa.Column("matches_history_synced_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "matches",
        sa.Column(
            "history_summary_only",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("matches", "history_summary_only")
    op.drop_column("teams", "matches_history_synced_until")
    op.drop_column("teams", "matches_history_complete")
    op.drop_column("teams", "founded_at")
