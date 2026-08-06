"""2026-08-05: playerdetails.xml devuelve <Error>/ErrorCode (HTTP 200) para
jugadores cuyo ID ya no resuelve en Hattrick (ventas viejas, ~105 casos
verificados en vivo contra esta cuenta) — sin este flag,
`_backfill_sold_player_details` los volvía a pedir en CADA sync para
siempre, ~105 llamadas CHPP secuenciales desperdiciadas cada vez.

Revision ID: 0031
"""
import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(
            sa.Column("enrichment_unavailable", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("enrichment_unavailable")
