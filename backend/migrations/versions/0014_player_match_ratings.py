"""Histórico de rating por partido del jugador — HL-15x #21 (sparkline).

`player_snapshots.last_match_*` solo conserva el partido más reciente (se
sobreescribe en cada sync de playerdetails), así que no sirve como serie en
el tiempo. Esta tabla nueva es append-only: cada partido distinto visto se
inserta una vez (unique player_id+ht_match_id evita duplicar el mismo
"último partido" si todavía no se ha jugado uno nuevo desde el sync
anterior). Hoy habrá pocas filas por jugador — se llena partido a partido a
medida que se sincroniza playerdetails, no de golpe.

Revision ID: 0014
"""
import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # En SQLite, BIGINT puro no es alias de rowid: el autoincrement se pierde
    # en silencio y el INSERT falla con NOT NULL (mismo caso que
    # sync_changes, 0010). La variante Integer en sqlite es la misma que
    # usa el ORM (`PKBigInt` en models.py).
    pk_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "player_match_ratings",
        sa.Column("id", pk_bigint, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("ht_match_id", sa.BigInteger, nullable=False),
        sa.Column("position_code", sa.SmallInteger, nullable=False),
        sa.Column("played_minutes", sa.SmallInteger, nullable=False),
        sa.Column("rating", sa.Float, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_pmr_player_match", "player_match_ratings", ["player_id", "ht_match_id"], unique=True
    )
    op.create_index(
        "ix_pmr_player_id", "player_match_ratings", ["player_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_pmr_player_id", table_name="player_match_ratings")
    op.drop_index("ix_pmr_player_match", table_name="player_match_ratings")
    op.drop_table("player_match_ratings")
