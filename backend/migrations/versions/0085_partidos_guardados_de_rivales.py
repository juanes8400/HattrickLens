"""Los ultimos partidos de cada rival, guardados para no repedirlos.

2026-09-09. Abrir la ficha de un rival costaba una llamada de alineacion y
otra de detalle por partido mirado, cada vez. Un partido terminado no cambia
nunca: se guarda una vez y se lee de aqui.

Tabla propia y no `matches`/`match_ratings`: aquellas son las tablas del club
y toda consulta que ya existe da por hecho que sus filas son partidos propios
o del calendario de la serie.

Revision ID: 0085
Revises: 0084
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import PKBigInt

revision = "0085"
down_revision = "0084"
branch_labels = None
depends_on = None

RATINGS = (
    "midfield",
    "left_def",
    "central_def",
    "right_def",
    "left_att",
    "central_att",
    "right_att",
    "set_pieces_def",
    "set_pieces_att",
)


def upgrade() -> None:
    columnas = [
        # `PKBigInt` y no `BigInteger`: en SQLite un BIGINT no es
        # autoincremental y el primer INSERT real revienta (mordio en la 0068).
        sa.Column("id", PKBigInt, primary_key=True),
        sa.Column("team_ht_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_match_id", sa.BigInteger(), nullable=False),
        sa.Column("match_type", sa.SmallInteger(), nullable=False),
        sa.Column("played_at", sa.DateTime(), nullable=False),
        sa.Column("home_team_ht_id", sa.BigInteger(), nullable=False),
        sa.Column("away_team_ht_id", sa.BigInteger(), nullable=False),
        sa.Column("home_team_name", sa.String(128), nullable=False),
        sa.Column("away_team_name", sa.String(128), nullable=False),
        sa.Column("home_goals", sa.SmallInteger(), nullable=False, server_default="-1"),
        sa.Column("away_goals", sa.SmallInteger(), nullable=False, server_default="-1"),
        sa.Column("tactic_type", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("tactic_skill", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("formation", sa.String(16), nullable=True),
        sa.Column("lineup_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    ]
    # Los nueve del rival van nullables: la alineacion sirve para nombres y
    # posiciones aunque el detalle no se haya podido leer.
    columnas.extend(sa.Column(r, sa.SmallInteger(), nullable=True) for r in RATINGS)

    op.create_table(
        "rival_matches",
        *columnas,
        sa.UniqueConstraint("team_ht_id", "ht_match_id", name="uq_rival_match_por_equipo"),
    )
    op.create_index("ix_rival_matches_team_ht_id", "rival_matches", ["team_ht_id"])
    op.create_index("ix_rival_matches_ht_match_id", "rival_matches", ["ht_match_id"])
    op.create_index("ix_rival_matches_played_at", "rival_matches", ["played_at"])


def downgrade() -> None:
    op.drop_table("rival_matches")
