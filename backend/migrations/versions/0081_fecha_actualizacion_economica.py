"""Guarda EconomyDate por liga para contar los salarios por actualización.

Antes WorldContext descartaba este campo de worlddetails.xml y el saldo de un
jugador suponía un cobro cada siete días desde su compra. EconomyDate es el
calendario oficial: permite distinguir una compra minutos antes del cierre
económico de otra hecha minutos después.

Las filas existentes quedan en NULL hasta el siguiente sync de worlddetails.
No se fabrica un día por país: cada liga publica el suyo.

Revision ID: 0081
Revises: 0080
"""

import sqlalchemy as sa
from alembic import op

revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "world_context",
        sa.Column("economy_date", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("world_context", "economy_date")
