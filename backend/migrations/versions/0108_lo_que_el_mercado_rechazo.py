"""Por qué no se pudo mirar el mercado, guardado en el club.

2026-11-01, dicho por el usuario después de un reporte de sus usuarios: el
fallo del paso del mercado «que sea un aviso en alertas, no un motivo para
mostrarlo ahí». «Ahí» es el cartel de sincronización parcial, donde salía
pegado al error de verdad --una alineación incompleta-- en la misma línea y
con el mismo tono, aunque no son lo mismo: uno es algo que el manager puede
arreglar en Hattrick y el otro es cosa nuestra.

POR QUÉ UNA COLUMNA Y NO MIRAR `market_run_at`. Se podía avisar sólo por la
fecha --«el mercado no se mira desde el martes»-- y no haría falta guardar
nada. Pero entonces el aviso no puede decir qué pasó, y lo que pasó es la
mitad del valor: «Hattrick rechazó el filtro de edad» se puede arreglar, «no
se ha podido mirar» no se puede ni reportar.

SE GUARDA LO QUE DIJO HATTRICK, recortado, no un rastro de la excepción: el
aviso lo lee un manager, no un programador. Y se borra en cuanto un paso sale
bien, porque un aviso que sobrevive a su causa es peor que no avisar.

Revision ID: 0108
Revises: 0107
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0108"
down_revision = "0107"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("market_error", sa.String(length=300), nullable=True))
    op.add_column("teams", sa.Column("market_error_at", UtcDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("teams", "market_error_at")
    op.drop_column("teams", "market_error")
