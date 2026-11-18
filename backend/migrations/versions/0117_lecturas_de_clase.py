"""Las clases de cada jugador, guardadas por sincronización.

2026-11-18, pedido del usuario («Esto sería espectacular»): en Cambios, quién
cambió de clase desde la sincronización anterior --«Horhoi: Suplencia →
Titular»--. Las clases se calculan al vuelo; para comparar «antes» y «ahora»
hace falta guardar el «antes».

Una fila por jugador y lectura. La lectura se identifica por la
sincronización de la que salen las fotos de la plantilla (la última
`player_snapshots.sync_id` del equipo) y se escribe la primera vez que se
miran las clases después de esa sincronización. Sólo las tres de la app:
lo que el usuario mueve a mano en sus clasificaciones propias no es una
noticia.

Revision ID: 0117
Revises: 0116
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "player_class_readings",
        # La misma variante que `PKBigInt`: con `BIGINT PRIMARY KEY` a secas
        # SQLite no autoincrementa (ver la 0111).
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sync_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_player_id", sa.BigInteger(), nullable=False),
        sa.Column("titularidad", sa.String(length=16), nullable=False),
        sa.Column("rentabilidad", sa.String(length=16), nullable=False),
        sa.Column("etapa", sa.String(length=16), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
        sa.UniqueConstraint(
            "team_id", "sync_id", "ht_player_id", name="uq_una_lectura_por_jugador"
        ),
    )
    op.create_index(
        "ix_player_class_readings_team_sync", "player_class_readings", ["team_id", "sync_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_player_class_readings_team_sync", table_name="player_class_readings")
    op.drop_table("player_class_readings")
