"""El censo de ojeadores, para poder hacerles la cuenta.

Pedido por el usuario el 2026-08-26: cada ojeador cuesta 5.000 por semana y se
le abona lo que dieron los canteranos que EL descubrio. Hacia falta saber desde
cuando esta cada uno, y eso solo lo da `youthteamdetails.xml` con
`showScouts=true`.

`gone_at`/`last_seen_at`: un ojeador despedido desaparece de la lista sin que
Hattrick diga cuando. Se anota la ultima vez que se le vio y su coste se cierra
ahi, con el error acotado a lo que se tarde entre dos sincronizaciones.

Revision ID: 0069
Revises: 0068
"""
import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import PKBigInt

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "youth_scouts",
        sa.Column("id", PKBigInt, primary_key=True),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_scout_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("hired_at", sa.DateTime(), nullable=True),
        sa.Column("gone_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("region_name", sa.String(128), nullable=True),
    )
    op.create_index("ix_youth_scouts_team_id", "youth_scouts", ["team_id"])
    op.create_index("ix_youth_scouts_ht_scout_id", "youth_scouts", ["ht_scout_id"])


def downgrade() -> None:
    op.drop_table("youth_scouts")
