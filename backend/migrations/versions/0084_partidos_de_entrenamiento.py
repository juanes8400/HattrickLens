"""Partidos ajenos para entrenar el modelo de prediccion.

2026-09-05. Se recogen UNA vez --500 llamadas-- y se refrescan como mucho una
vez al ano. Tabla propia y no `matches`: aquellos son los partidos del club y
se reescriben en cada sincronizacion; estos son material de entrenamiento.

Plana a proposito: cada fila es una observacion y cada columna una variable.
Partirla en dos filas obligaria a unirla consigo misma para todo.

Revision ID: 0084
Revises: 0083
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import PKBigInt

revision = "0084"
down_revision = "0083"
branch_labels = None
depends_on = None

LADOS = ("home", "away")
RATINGS = (
    "midfield",
    "left_def",
    "central_def",
    "right_def",
    "left_att",
    "central_att",
    "right_att",
    "sp_def",
    "sp_att",
)


def upgrade() -> None:
    columnas = [
        # `PKBigInt` y no `BigInteger`: en SQLite un BIGINT no es
        # autoincremental y el primer INSERT real revienta (mordio en la 0068).
        sa.Column("id", PKBigInt, primary_key=True),
        sa.Column("ht_match_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("match_type", sa.SmallInteger(), nullable=False),
        sa.Column("played_at", sa.DateTime(), nullable=True),
        sa.Column("home_team_id", sa.BigInteger(), nullable=False),
        sa.Column("away_team_id", sa.BigInteger(), nullable=False),
        sa.Column("home_goals", sa.SmallInteger(), nullable=False),
        sa.Column("away_goals", sa.SmallInteger(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
    ]
    for lado in LADOS:
        for r in RATINGS:
            columnas.append(sa.Column(f"{lado}_{r}", sa.SmallInteger(), nullable=False))
        columnas.append(
            sa.Column(f"{lado}_tactic_type", sa.SmallInteger(), nullable=False, server_default="0")
        )
        columnas.append(
            sa.Column(f"{lado}_tactic_skill", sa.SmallInteger(), nullable=False, server_default="0")
        )
    op.create_table("training_matches", *columnas)
    op.create_index("ix_training_matches_ht_match_id", "training_matches", ["ht_match_id"])
    op.create_index("ix_training_matches_match_type", "training_matches", ["match_type"])
    op.create_index("ix_training_matches_played_at", "training_matches", ["played_at"])
    op.create_index("ix_training_matches_home_team_id", "training_matches", ["home_team_id"])
    op.create_index("ix_training_matches_away_team_id", "training_matches", ["away_team_id"])


def downgrade() -> None:
    op.drop_table("training_matches")
