"""Diff de sync — HL-140. Qué cambió respecto al sync anterior, al estilo
Hattrick Control: skills de jugadores, resultados, liga, aficionados/
patrocinadores y economía. Se calcula en el momento del sync, cuando el
old/new todavía están en memoria.

Revision ID: 0010
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # En SQLite, BIGINT puro no es alias de rowid: el autoincrement se pierde
    # en silencio y el INSERT falla con NOT NULL. La variante Integer en
    # sqlite es la misma que ya usa el ORM (`PKBigInt` en models.py).
    pk_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "sync_changes",
        sa.Column("id", pk_bigint, primary_key=True, autoincrement=True),
        sa.Column("sync_id", sa.BigInteger, sa.ForeignKey("syncs.id"), nullable=False),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sync_changes_sync", "sync_changes", ["sync_id"])
    op.create_index("ix_sync_changes_team", "sync_changes", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_changes_team", table_name="sync_changes")
    op.drop_index("ix_sync_changes_sync", table_name="sync_changes")
    op.drop_table("sync_changes")
