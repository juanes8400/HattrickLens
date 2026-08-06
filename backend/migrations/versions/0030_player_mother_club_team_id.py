"""2026-08-04: MotherClub/TeamID de playerdetails.xml — "canterano" real
(MotherClub == este club), pedido explícitamente para reemplazar el
`is_academy_graduate` anterior (YouthPlayer/FormerYouthPlayer, que solo
cubre jugadores vistos por el escaneo de cantera de esta app) en el
desglose de saldo por jugador y el gráfico de puntos por transferencia.

Revision ID: 0030
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("mother_club_team_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("mother_club_team_id")
