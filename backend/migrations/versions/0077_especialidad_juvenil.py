"""La especialidad de cada canterano.

2026-09-01, pedido del usuario para la tabla de la plantilla juvenil. El dato
ya venia en el fichero de canteranos --`Specialty`-- y se estaba tirando al
leerlo.

Va en `youth_players` y no en `youth_snapshots` porque es identidad, no
estado: no cambia nunca, y guardarla en cada foto la repetiria una vez por
cada cambio de habilidad sin que ninguna copia dijera nada nuevo.

Se rellena sola en la siguiente sincronizacion; hasta entonces vale 0, que es
lo mismo que Hattrick usa para "sin especialidad" y por eso NO se distingue de
"todavia no lo sabemos". Es una ambiguedad aceptada a proposito: la unica
alternativa era NULL, y entonces cada lectura tendria que decidir que hacer
con un hueco que se cierra solo en cuestion de horas.

Revision ID: 0077
Revises: 0076
"""

import sqlalchemy as sa
from alembic import op

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("youth_players") as batch_op:
        batch_op.add_column(
            sa.Column("specialty", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("youth_players") as batch_op:
        batch_op.drop_column("specialty")
