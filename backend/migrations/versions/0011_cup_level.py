"""CupLevel/CupLevelIndex del partido — HL-116.

Identifican qué copa concreta es cada partido de copa (hay varias en
paralelo: la principal y, tras caer eliminado, las de consolación). CHPP no
numera la ronda directamente; contando cuántos partidos comparten el mismo
par (cup_level, cup_level_index) se puede ESTIMAR en qué ronda va cada uno.

Revision ID: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "matches", sa.Column("cup_level", sa.SmallInteger, nullable=False, server_default="-1")
    )
    op.add_column(
        "matches",
        sa.Column("cup_level_index", sa.SmallInteger, nullable=False, server_default="-1"),
    )


def downgrade() -> None:
    op.drop_column("matches", "cup_level_index")
    op.drop_column("matches", "cup_level")
