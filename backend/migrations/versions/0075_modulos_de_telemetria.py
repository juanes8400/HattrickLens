"""Unificar los nombres de modulo que guarda la telemetria.

`ui_events.module` guarda el NOMBRE del modulo, no la ruta, asi que renombrar
una pantalla parte su historico en dos filas de la tabla de Uso: las visitas
viejas bajo el nombre antiguo y las nuevas bajo el nuevo, sin forma de sumarlas.

Tres casos, todos del 2026-08-31:

  * «Club y staff» -> «Club y cuerpo tecnico». El menu decia «staff» y la
    pantalla «cuerpo tecnico»; se unifico en la segunda.
  * «Avisos» -> «Alertas». La pantalla se llama Alertas en todas partes.
  * «Motor» -> «Transparencia». Ademas de renombrarse, la ruta cambio de
    `/engine` a `/transparency` y la lista de modulos no tenia la nueva: sus
    visitas llevaban dias cayendo en «Otros», que es donde se pierden las
    cosas sin clasificar.

Se renombra el historico en vez de dejarlo partido porque estas filas existen
para una sola cosa --ver que se usa de verdad-- y un modulo repartido en dos
nombres contesta mal a esa pregunta.

Revision ID: 0075
Revises: 0074
"""

import sqlalchemy as sa
from alembic import op

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None

RENOMBRES = {
    "Club y staff": "Club y cuerpo técnico",
    "Avisos": "Alertas",
    "Motor": "Transparencia",
}


def _tabla() -> sa.Table:
    return sa.table("ui_events", sa.column("module", sa.String))


def upgrade() -> None:
    conn, tabla = op.get_bind(), _tabla()
    for viejo, nuevo in RENOMBRES.items():
        conn.execute(tabla.update().where(tabla.c.module == viejo).values(module=nuevo))


def downgrade() -> None:
    conn, tabla = op.get_bind(), _tabla()
    for viejo, nuevo in RENOMBRES.items():
        conn.execute(tabla.update().where(tabla.c.module == nuevo).values(module=viejo))
