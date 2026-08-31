"""`former_youth_players.promoted_at` no guardaba la fecha de ascenso.

Guardaba `ArrivalDate` de la consulta de ex-canteranos, y el propio documento
de referencia dice que ese campo es "the date of arrival to current team". En
esa consulta el club actual es donde esta el jugador HOY, no el nuestro: es
cuando llego a quien se lo quedo.

Lo delataba la aritmetica. En la base real los 43 ex-canteranos aparecian
vendidos ANTES de la fecha que llamabamos de ascenso --Carlos Andres Tocancipa,
1.054 dias antes-- y las filas de venta directa tenian las dos fechas el mismo
dia, que es exactamente lo que pasa cuando vendes a alguien y llega a su nuevo
club esa misma tarde.

Se renombra en vez de borrar: el dato es bueno y util --dice cuanto lleva cada
ex-canterano donde esta-- lo que estaba mal era su nombre, y ese nombre es lo
que hizo que se usara para cosas que no puede contestar.

Revision ID: 0073
Revises: 0072
"""

import sqlalchemy as sa
from alembic import op

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # sqlite no sabe renombrar una columna sin recrear la tabla; `batch` lo
    # hace por debajo y en PostgreSQL se traduce a un ALTER normal.
    with op.batch_alter_table("former_youth_players") as batch:
        batch.alter_column(
            "promoted_at",
            new_column_name="arrived_at_current_team",
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("former_youth_players") as batch:
        batch.alter_column(
            "arrived_at_current_team",
            new_column_name="promoted_at",
            existing_type=sa.DateTime(),
            existing_nullable=True,
        )
