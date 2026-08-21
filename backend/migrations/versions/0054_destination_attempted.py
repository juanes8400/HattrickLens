"""Marcar que ya se preguntó por el país del club comprador.

2026-08-21. El relleno del pasado va por lotes, y cada lote vuelve a pedir lo
que sigue pendiente. El país de destino no tenía marca de "ya preguntado": si
Hattrick no resolvía el país de un comprador, ese jugador reaparecía en el
siguiente lote y en el siguiente, sin fin — visto en vivo, la barra de progreso
marcaba "55 de 11" porque el trabajo nunca se agotaba.

Las otras dos descargas de este relleno (`enrichment_attempted`,
`tsi_at_purchase_attempted`) ya tenían su marca; esta faltaba.

Revision ID: 0054
"""
import sqlalchemy as sa
from alembic import op

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column(
            "destination_attempted", sa.Boolean(), nullable=False, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("players", "destination_attempted")
