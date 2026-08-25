"""Reabrir los expedientes cerrados por el fallo de `TrainerData`.

En `playerdetails.xml` v3.2 TODO jugador trae la etiqueta `<TrainerData />`
vacia. Darla por buena como senal de "es entrenador" cerraba la vigilancia de
comisiones de cualquiera al que se le pidiera la ficha: 121 expedientes en la
cuenta del usuario, muchos en el mismo minuto.

El motivo "entrenador" nacio ese mismo dia y SIEMPRE se decidio con esa regla
rota, asi que no hay ninguno legitimo que conservar: se reabren todos y se
borra su marca de revision para que se vuelvan a examinar con la regla nueva
--el bloque tiene que traer `TrainerSkillLevel` dentro--.

Revision ID: 0066
Revises: 0065
"""
import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE players
        SET resale_closed = 0,
            resale_closed_reason = NULL,
            previous_club_bonus_checked_at = NULL
        WHERE resale_closed_reason = 'entrenador'
    """))


def downgrade() -> None:
    # No se puede deshacer: no queda constancia de cuales se habian cerrado, y
    # devolverlos a "entrenador" seria repetir el fallo.
    pass
