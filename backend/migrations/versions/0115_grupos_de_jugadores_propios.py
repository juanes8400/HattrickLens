"""Los grupos propios de Clases de Jugador → Personalizar.

2026-11-16, pedido del usuario: en Clases de Jugador, además de las
clasificaciones que calcula la app, una que arma él: «Creas grupos y pones a
cada jugador donde quieras». Un jugador va en un solo grupo («No» a estar en
varios), así que la pertenencia es una columna del jugador y no una tabla
intermedia: lo imposible no se puede guardar.

`player_groups` lleva nombre y color; `players.player_group_id` dice en cuál
está cada uno, nulo es «Sin grupo».

Revision ID: 0115
Revises: 0114
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0115"
down_revision = "0114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_groups",
        # La misma variante que `PKBigInt`: con `BIGINT PRIMARY KEY` a secas
        # SQLite no autoincrementa (ver la 0111).
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_player_groups_team_id", "player_groups", ["team_id"])
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("player_group_id", sa.BigInteger(), nullable=True))
        batch_op.create_index("ix_players_player_group_id", ["player_group_id"])


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_index("ix_players_player_group_id")
        batch_op.drop_column("player_group_id")
    op.drop_index("ix_player_groups_team_id", table_name="player_groups")
    op.drop_table("player_groups")
