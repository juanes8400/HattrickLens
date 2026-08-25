"""Reabrir TODOS los expedientes de vigilancia y volver a empezar.

Pedido por el usuario el 2026-08-25, despues de encontrarse con que la regla
de "es entrenador" estaba rota y habia cerrado 121 expedientes en falso. Su
razonamiento: si una de las cuatro razones de cierre resulto no ser de fiar,
lo limpio es rehacer el analisis entero con todo corregido, no parchear una.

Se reabre el expediente y se borra la marca de revision. NO se borra ninguna
comision ya calculada (`previous_club_bonus`): eso es dinero que Hattrick
pago de verdad y sigue siendo cierto. A quien ya tenia su comision anotada se
le volvera a cerrar como "revendido" en cuanto se le mire, que es barato.

El precio es que la cola vuelve a estar entera y hay que recorrerla de nuevo,
una llamada por ex-jugador. Se asume a proposito.

Revision ID: 0067
Revises: 0066
"""
import sqlalchemy as sa
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE players
        SET resale_closed = 0,
            resale_closed_reason = NULL,
            previous_club_bonus_checked_at = NULL
        WHERE resale_closed = 1
           OR previous_club_bonus_checked_at IS NOT NULL
    """))
    # El barrido en curso deja de tener sentido: su eje se congelo sobre una
    # cola que ya no existe.
    op.execute(sa.text("""
        UPDATE teams
        SET sweep_axis_json = NULL,
            sweep_started_at = NULL,
            commission_tried_json = '[]'
    """))


def downgrade() -> None:
    # Irreversible a proposito: no queda constancia de que estaba cerrado ni
    # por que, y devolverlo seria devolver los cierres falsos.
    pass
