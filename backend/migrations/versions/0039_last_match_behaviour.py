"""2026-08-09, pedido explícitamente: "Última semana" solo mostraba la
posición base (portero/defensa/lateral/medio/extremo/delantero) sin decir
si la orden individual fue Ofensivo/Defensivo/Hacia el medio/Hacia la
banda. Ese dato no está en `LastMatch` de playerdetails.xml — solo en el
`Behaviour` de matchlineup.xml para el partido concreto. Se guarda aparte
de `last_match_position_code`, con su propio NULL para "no se pudo
resolver" (nunca confundido con Behaviour=0 "Normal").

Revision ID: 0039
"""
import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.add_column(sa.Column("last_match_behaviour_code", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("player_snapshots") as batch_op:
        batch_op.drop_column("last_match_behaviour_code")
