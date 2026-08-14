"""Enumerar intentos de venta — HL-161, 2026-08-08, pedido explícitamente.

`Player.listing_count` (0027) solo CUENTA apariciones nuevas en el mercado;
esta tabla nueva guarda cada una como fila propia (con la puja más alta del
momento) para poder enumerarlas en la ficha de ex-jugador, no solo contarlas.
Empieza a llenarse desde hoy — CHPP no da historial, así que subestima lo
anterior, igual que `listing_count` ya lo hacía.

Revision ID: 0038
"""
import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pk_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "player_listing_attempts",
        sa.Column("id", pk_bigint, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("highest_bid", sa.BigInteger, nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_player_listing_attempts_player_id", "player_listing_attempts", ["player_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_player_listing_attempts_player_id", table_name="player_listing_attempts")
    op.drop_table("player_listing_attempts")
