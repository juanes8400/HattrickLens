"""series_ht_id/match_round en matches, para leaguefixtures.xml.

Hasta ahora el calendario de liga solo conocía los partidos DEL EQUIPO
sincronizado (matches.xml se pide con teamID=<propio>) — los cruces entre
dos rivales (ninguno el propio) nunca se guardaban, así que el simulador de
temporada los daba por congelados. leaguefixtures.xml trae el calendario
completo de la serie (todos los pares, ida y vuelta) pero identifica cada
partido por LeagueLevelUnitID + MatchRound, que hasta ahora no se guardaban.
Ambas columnas nullable: los partidos ya sincronizados antes de este fix, o
que no son de liga (copa, amistoso), simplemente no las tienen.

Revision ID: 0022
"""
import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("series_ht_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("match_round", sa.SmallInteger(), nullable=True))
        batch_op.create_index(
            "ix_matches_series_ht_id", ["series_ht_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_index("ix_matches_series_ht_id")
        batch_op.drop_column("match_round")
        batch_op.drop_column("series_ht_id")
