"""Cual de los clubes del manager es el principal, dicho por Hattrick.

2026-09-28, senalado en la revision de la PR #6. La moneda de un club de liga
internacional --que no tiene pais propio-- se hereda del club principal del
manager. Hasta ahora ese club se adivinaba por la fecha de fundacion, y eso
falla en un caso real: al conectar la cuenta los clubes nacen SIN fecha, y solo
se rellena al sincronizar cada uno. Si se sincroniza antes un club secundario,
el principal se queda sin fecha y pierde la eleccion.

`IsPrimaryClub` viene en el fichero del club y se conoce desde el primer
momento: el alta de la cuenta recorre TODOS los clubes del manager.

Nace a NULL --«todavia no se ha leido»-- y no a False, que seria afirmar que
ningun club es el principal. Se rellena en la siguiente sincronizacion, y
mientras tanto la eleccion cae a la regla anterior.

Revision ID: 0094
Revises: 0093
"""

import sqlalchemy as sa
from alembic import op

revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("is_primary_club", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("is_primary_club")
