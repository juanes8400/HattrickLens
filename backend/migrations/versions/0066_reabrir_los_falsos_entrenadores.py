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

# Las fechas van con `timezone=True` porque las columnas reales son
# `timestamptz`: declararlas sin zona hace que asyncpg rechace el valor en
# Postgres aunque sqlite lo acepte (ver 0071 y su test).
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

# Se declara la tabla en vez de escribir el SQL a mano para que el booleano lo
# escriba el DIALECTO. En crudo salia `resale_closed = 0`, que SQLite acepta
# --no tiene tipo booleano-- y Postgres rechaza de plano, asi que el
# despliegue reventaba aunque en local pasara sin ruido.
players = sa.table(
    "players",
    sa.column("resale_closed", sa.Boolean),
    sa.column("resale_closed_reason", sa.String),
    sa.column("previous_club_bonus_checked_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.execute(
        players.update()
        .where(players.c.resale_closed_reason == "entrenador")
        .values(
            resale_closed=False,
            resale_closed_reason=None,
            previous_club_bonus_checked_at=None,
        )
    )


def downgrade() -> None:
    # No se puede deshacer: no queda constancia de cuales se habian cerrado, y
    # devolverlos a "entrenador" seria repetir el fallo.
    pass
