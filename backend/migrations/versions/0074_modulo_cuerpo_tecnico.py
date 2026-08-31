"""El modulo «staff» de las alertas pasa a llamarse «cuerpo tecnico».

Los nueve modulos que etiquetan una alerta eran nombres comunes en español
--liga, equipo, economia, academia, estadio, partidos, entrenamiento,
general-- salvo uno, que era «staff». El resto de la aplicacion lleva meses
diciendo «cuerpo tecnico»: la pantalla, la pestaña y el propio panel.

Se migran las filas archivadas por la misma razon que la 0072: el buzon guarda
el modulo tal cual estaba al archivar, asi que cambiar solo el motor dejaria
alertas viejas etiquetadas «staff» al lado de las nuevas, y el filtro por
modulo las separaria en dos grupos que son el mismo.

La huella NO se recalcula: se calcula con severidad, titulo, detalle y accion,
y el modulo no entra en ella. Cambiarlo no altera la identidad de la alerta.

Revision ID: 0074
Revises: 0073
"""

import sqlalchemy as sa
from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tabla = sa.table(
        "dismissed_insights",
        sa.column("module", sa.String),
    )
    op.get_bind().execute(
        tabla.update().where(tabla.c.module == "staff").values(module="cuerpo técnico")
    )


def downgrade() -> None:
    tabla = sa.table(
        "dismissed_insights",
        sa.column("module", sa.String),
    )
    op.get_bind().execute(
        tabla.update().where(tabla.c.module == "cuerpo técnico").values(module="staff")
    )
