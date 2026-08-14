"""2026-08-09, pedido explícitamente: caso real (Volodymyr Manakin) probó
que `LastMatch` de playerdetails.xml puede ser de hace más de un año — "el
último partido con datos de este jugador", no "la semana pasada". Se
guarda la fecha real para que "Último partido" solo muestre dato cuando el
partido cayó dentro de los últimos 7 días respecto a hoy (calculado
dinámicamente en cada consulta, nunca una fecha fija).

Revision ID: 0040
"""
import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.add_column(sa.Column("last_match_played_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.drop_column("last_match_played_at")
