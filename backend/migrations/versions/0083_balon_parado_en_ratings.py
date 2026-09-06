"""Balon parado en los ratings de partido.

`RatingIndirectSetPiecesDef` y `...Att` estaban en matchdetails.xml desde
siempre; el parser leia las siete zonas de campo y se saltaba estas dos. El
modelo de prediccion las pide como variable, asi que sin esto no habia de
donde sacarlas.

Nullable a proposito: lo ya guardado no las tiene y no se pueden inventar. Se
rellenan solas al volver a pedir cada partido.

Revision ID: 0083
Revises: 0082
"""

import sqlalchemy as sa
from alembic import op

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("match_ratings", sa.Column("set_pieces_def", sa.SmallInteger(), nullable=True))
    op.add_column("match_ratings", sa.Column("set_pieces_att", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("match_ratings", "set_pieces_att")
    op.drop_column("match_ratings", "set_pieces_def")
