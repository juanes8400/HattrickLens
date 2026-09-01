"""Fuera la asistencia por sector: es una funcion de HT Supporter.

Las reglas de CHPP prohiben replicar o imitar las funciones de HT Supporter, y
el desglose de asistencia por sector es una de ellas. `stadium_history` guardaba
`SoldTerraces/SoldBasic/SoldRoof/SoldVIP` de cada partido, leidos de
matchdetails, que es justo esa funcion (requisito del 2026-09-01).

Lo que SI es publico y se conserva:

  * El total de espectadores, que Hattrick enseña en la pagina del partido.
  * El aforo por sector, que es la configuracion de tu propio estadio y llega
    por arenadetails.

El problema es que el total no estaba guardado: `sold_total` era una PROPIEDAD
que sumaba los cuatro sectores. Por eso esta migracion tiene dos pasos y en
este orden:

  1. Crea `sold_total` y lo rellena con la suma de los cuatro. El dato publico
     se salva antes de tocar nada.
  2. Elimina las cuatro columnas de sector. No se ponen a cero ni a NULL: se
     borran, para que no quede una copia de la funcion de Supporter en la base.

El aforo por sector (`capacity_*`) NO se toca.

Revision ID: 0076
Revises: 0075
"""

import sqlalchemy as sa
from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None

SECTORES = ("sold_terraces", "sold_basic", "sold_roof", "sold_vip")


def upgrade() -> None:
    with op.batch_alter_table("stadium_history") as batch_op:
        batch_op.add_column(
            sa.Column("sold_total", sa.Integer(), nullable=False, server_default="0")
        )

    # Se salva el total ANTES de borrar el desglose. Es la unica oportunidad:
    # despues de este UPDATE los sumandos ya no existen.
    op.execute(
        "UPDATE stadium_history SET sold_total = "
        "COALESCE(sold_terraces, 0) + COALESCE(sold_basic, 0) + "
        "COALESCE(sold_roof, 0) + COALESCE(sold_vip, 0)"
    )

    with op.batch_alter_table("stadium_history") as batch_op:
        for columna in SECTORES:
            batch_op.drop_column(columna)


def downgrade() -> None:
    """Devuelve las columnas VACIAS, no los datos.

    El desglose no se puede reconstruir a partir del total: cuatro sumandos no
    salen de una suma. Y aunque se pudiera, volver a guardarlo seria volver a
    incumplir. Esto existe para que la cadena de migraciones no se rompa.
    """
    with op.batch_alter_table("stadium_history") as batch_op:
        for columna in SECTORES:
            batch_op.add_column(
                sa.Column(columna, sa.Integer(), nullable=False, server_default="0")
            )
        batch_op.drop_column("sold_total")
