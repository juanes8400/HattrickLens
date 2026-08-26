"""Reabrir TODOS los expedientes de vigilancia y volver a empezar.

Pedido por el usuario el 2026-08-25, despues de encontrarse con que la regla
de "es entrenador" estaba rota y habia cerrado 121 expedientes en falso. Su
razonamiento: si una de las cuatro razones de cierre resulto no ser de fiar,
lo limpio es rehacer el analisis entero con todo corregido, no parchear una.

Se reabre el expediente y se borra la marca de revision. NO se borra ninguna
comision ya calculada (`previous_club_bonuses`): eso es dinero que Hattrick
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

# Declaradas, no escritas a mano: asi el booleano lo escribe el dialecto. En
# SQL crudo (`resale_closed = 0` / `= 1`) SQLite pasa y Postgres rechaza.
players = sa.table(
    "players",
    sa.column("resale_closed", sa.Boolean),
    sa.column("resale_closed_reason", sa.String),
    sa.column("previous_club_bonus_checked_at", sa.DateTime),
)
teams = sa.table(
    "teams",
    sa.column("sweep_axis_json", sa.Text),
    sa.column("sweep_started_at", sa.DateTime),
    sa.column("commission_tried_json", sa.Text),
)


def upgrade() -> None:
    op.execute(
        players.update()
        .where(
            sa.or_(
                players.c.resale_closed.is_(True),
                players.c.previous_club_bonus_checked_at.is_not(None),
            )
        )
        .values(
            resale_closed=False,
            resale_closed_reason=None,
            previous_club_bonus_checked_at=None,
        )
    )
    # El barrido en curso deja de tener sentido: su eje se congelo sobre una
    # cola que ya no existe.
    op.execute(
        teams.update().values(
            sweep_axis_json=None,
            sweep_started_at=None,
            commission_tried_json="[]",
        )
    )


def downgrade() -> None:
    # Irreversible a proposito: no queda constancia de que estaba cerrado ni
    # por que, y devolverlo seria devolver los cierres falsos.
    pass
