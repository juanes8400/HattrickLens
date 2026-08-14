"""Comisión de club anterior EXACTA — HL-161, 2026-08-14, pedido
explícitamente ("encontré la forma de asignar exactamente el dinero").

`players` gana los TransferID de compra/venta de ESTE stint (para
delimitar sin ambigüedad la ventana de partidos a contar cuando se recorre
el historial completo del jugador vía transfersplayer.xml), el conteo de
partidos reales cacheado, y una marca de cuándo se revisó por última vez si
hubo una reventa nueva. `previous_club_bonuses` guarda cada reventa
detectada, una fila por `resale_transfer_id` (único — nunca se cuenta dos
veces). Reemplaza el reparto heurístico de `resale_bonus.py`.

Revision ID: 0043
"""
import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("ht_purchase_transfer_id", sa.BigInteger, nullable=True))
        batch_op.add_column(sa.Column("ht_sale_transfer_id", sa.BigInteger, nullable=True))
        batch_op.add_column(sa.Column("games_played_for_us", sa.SmallInteger, nullable=True))
        batch_op.add_column(
            sa.Column("games_played_for_us_computed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("previous_club_bonus_checked_at", sa.DateTime(timezone=True), nullable=True)
        )

    pk_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "previous_club_bonuses",
        sa.Column("id", pk_bigint, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id"), nullable=False),
        sa.Column("ht_player_id", sa.BigInteger, nullable=False),
        sa.Column("resale_transfer_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("resale_price", sa.BigInteger, nullable=False),
        sa.Column("resale_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("buyer_team_id", sa.BigInteger, nullable=False),
        sa.Column("seller_team_id", sa.BigInteger, nullable=False),
        sa.Column("games_played_with_us", sa.SmallInteger, nullable=False),
        sa.Column("pct_applied", sa.Float, nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_previous_club_bonuses_player_id", "previous_club_bonuses", ["player_id"]
    )
    op.create_index(
        "ix_previous_club_bonuses_ht_player_id", "previous_club_bonuses", ["ht_player_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_previous_club_bonuses_ht_player_id", table_name="previous_club_bonuses")
    op.drop_index("ix_previous_club_bonuses_player_id", table_name="previous_club_bonuses")
    op.drop_table("previous_club_bonuses")

    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("previous_club_bonus_checked_at")
        batch_op.drop_column("games_played_for_us_computed_at")
        batch_op.drop_column("games_played_for_us")
        batch_op.drop_column("ht_sale_transfer_id")
        batch_op.drop_column("ht_purchase_transfer_id")
