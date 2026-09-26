"""2026-09-26, pedido del usuario: el parte de un partido jugado tiene que
contrastarse con las probabilidades que dabamos ANTES de jugarlo.

Se calculaban al vuelo y se tiraban. Recalcularlas despues no vale: eso es lo
que diriamos hoy con los datos de entonces, no lo que dijimos. Asi que se
guardan cuando se dicen.

Revision ID: 0089
"""

import sqlalchemy as sa
from alembic import op

revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_predictions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ht_match_id", sa.BigInteger(), nullable=False),
        sa.Column("home_win", sa.Float(), nullable=False),
        sa.Column("draw", sa.Float(), nullable=False),
        sa.Column("away_win", sa.Float(), nullable=False),
        sa.Column("expected_home_goals", sa.Float(), nullable=False),
        sa.Column("expected_away_goals", sa.Float(), nullable=False),
        sa.Column("most_likely_score", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("engine", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_match_predictions_ht_match_id",
        "match_predictions",
        ["ht_match_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_match_predictions_ht_match_id", table_name="match_predictions")
    op.drop_table("match_predictions")
