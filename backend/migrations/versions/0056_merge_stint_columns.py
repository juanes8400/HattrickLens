"""Un solo sitio para los partidos jugados con nosotros.

2026-08-21. Al guardar el censo del stint añadí `stint_games_played` y
`stint_census_at` sin ver que ya existían `games_played_for_us` y
`games_played_for_us_computed_at`, creadas para calcular la comisión de club
anterior. Dos columnas para el mismo número: la ficha leía una y la comisión
llenaba la otra, así que el mismo jugador podía enseñar "?" en pantalla
teniendo sus partidos contados.

Se conservan las que ya existían, que son las que usa el cálculo del dinero, y
lo que hubiera caído en las nuevas se copia antes de tirarlas.

Revision ID: 0056
"""
import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE players SET games_played_for_us = stint_games_played "
        "WHERE games_played_for_us IS NULL AND stint_games_played IS NOT NULL"
    )
    op.execute(
        "UPDATE players SET games_played_for_us_computed_at = stint_census_at "
        "WHERE games_played_for_us_computed_at IS NULL AND stint_census_at IS NOT NULL"
    )
    op.drop_column("players", "stint_games_played")
    op.drop_column("players", "stint_census_at")


def downgrade() -> None:
    op.add_column("players", sa.Column("stint_games_played", sa.SmallInteger(), nullable=True))
    op.add_column(
        "players", sa.Column("stint_census_at", sa.DateTime(timezone=True), nullable=True)
    )
