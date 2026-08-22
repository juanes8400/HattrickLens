"""El precio que se pedía por el jugador.

2026-08-22. CHPP no lo entrega por ningún lado: aparece en el mismo mensaje de
Hattrick que las visitas, al cerrarse la puja ("El precio solicitado era de
723 000 US$"). Lo teclea el usuario, en su moneda, junto al número de visitas.

Revision ID: 0059
"""
import sqlalchemy as sa
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "player_listing_attempts", sa.Column("asking_price", sa.BigInteger())
    )


def downgrade() -> None:
    op.drop_column("player_listing_attempts", "asking_price")
