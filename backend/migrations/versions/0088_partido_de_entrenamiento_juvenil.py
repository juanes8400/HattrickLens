"""2026-09-19, pedido del usuario: un interruptor de «último entrenamiento»
también en Juveniles. La cantera no entrena con la actualización semanal del
primer equipo: entrena DESPUÉS DE CADA PARTIDO suyo.

Esa fecha ya la publica Hattrick en la ficha de la academia
(`NextTrainingMatchDate`), pero no se guardaba. Sin ella, decir cuándo fue el
último entrenamiento juvenil sería estimarlo; con ella se sabe, y el anterior
sale retrocediendo de siete en siete, igual que en el primer equipo.

Revision ID: 0088
"""

import sqlalchemy as sa
from alembic import op

revision = "0088"
down_revision = "0087"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(
            sa.Column("youth_next_training_match_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("youth_next_training_match_at")
