"""El último partido juvenil que de verdad se jugó, para anclar «Último entrenamiento».

2026-11-09, pedido del usuario: «esto debe conservar la información del
entrenamiento hasta el siguiente entrenamiento, no perderse en el tiempo
intermedio».

LO QUE HABÍA. La pestaña «Último entrenamiento» de Juveniles calculaba cuándo
entrenó la cantera restando siete días a la cita del PRÓXIMO partido. En
cuanto pasaba la hora del partido siguiente, la ventana saltaba a un
entrenamiento del que todavía no se había sincronizado nada, y la pestaña
decía «Nadie se movió»: lo del entrenamiento anterior se perdía hasta la
siguiente sincronización.

LO QUE HAY. La ficha de cada juvenil trae la fecha de SU último partido, y
Hattrick sólo la pone cuando el partido se jugó. La más reciente de la
plantilla es el último entrenamiento que de verdad nos ha llegado, y se guarda
en el equipo. Sin ese dato --equipos aún sin sincronizar tras esta
migración-- se sigue usando la regla vieja.

Revision ID: 0114
Revises: 0113
"""

import sqlalchemy as sa
from alembic import op

revision = "0114"
down_revision = "0113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Mismo tipo y misma forma que su hermana, `youth_next_training_match_at`
    # (migración 0088): el lote hace falta para que SQLite pueda deshacerlo.
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(
            sa.Column("youth_last_match_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("youth_last_match_at")
