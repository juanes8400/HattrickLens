"""Juveniles: identidad y snapshots con techo por habilidad.

El techo (`*_max`) es nullable a propósito. Un techo sin revelar no es lo mismo
que un techo bajo, y colapsarlos a cero haría que el motor de academia
descartara promesas por falta de información del ojeador en vez de por falta de
talento.

Revision ID: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

SKILLS = ("keeper", "defending", "playmaking", "winger", "passing", "scoring", "set_pieces")


def upgrade() -> None:
    op.create_table(
        "youth_players",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("ht_youth_player_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("first_name", sa.String(64), nullable=False),
        sa.Column("last_name", sa.String(64), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True)),
        sa.Column("left_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_youth_players_team", "youth_players", ["team_id"])

    cols = [
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("sync_id", sa.BigInteger, sa.ForeignKey("syncs.id"), nullable=False),
        sa.Column(
            "youth_player_id", sa.BigInteger,
            sa.ForeignKey("youth_players.id"), nullable=False,
        ),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("age_years", sa.SmallInteger, nullable=False),
        sa.Column("age_days", sa.SmallInteger, nullable=False),
    ]
    for skill in SKILLS:
        cols.append(sa.Column(skill, sa.SmallInteger))
        cols.append(sa.Column(f"{skill}_max", sa.SmallInteger))
    cols.append(sa.Column("minutes_last_match", sa.SmallInteger, server_default="0"))
    cols.append(sa.Column("content_hash", sa.LargeBinary(32), nullable=False))

    op.create_table("youth_snapshots", *cols)
    op.create_index(
        "ix_ys_player_time", "youth_snapshots", ["youth_player_id", "captured_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ys_player_time", table_name="youth_snapshots")
    op.drop_table("youth_snapshots")
    op.drop_index("ix_youth_players_team", table_name="youth_players")
    op.drop_table("youth_players")
