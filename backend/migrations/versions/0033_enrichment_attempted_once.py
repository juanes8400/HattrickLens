"""2026-08-05, pedido explícitamente: "backfill de un jugador máximo una
vez" — si la información no se encontró la primera vez, no va a estar
después (ver docstrings en models.py/sync_team.py). Renombra
enrichment_unavailable -> enrichment_attempted (semántica más amplia: se
marca tras CUALQUIER intento, no solo un ErrorCode de CHPP) y añade
tsi_at_purchase_attempted para el mismo principio en transfersplayer.xml.

Revision ID: 0033
"""
import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.alter_column(
            "enrichment_unavailable", new_column_name="enrichment_attempted"
        )
        batch_op.add_column(
            sa.Column(
                "tsi_at_purchase_attempted", sa.Boolean(), nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("tsi_at_purchase_attempted")
        batch_op.alter_column(
            "enrichment_attempted", new_column_name="enrichment_unavailable"
        )
