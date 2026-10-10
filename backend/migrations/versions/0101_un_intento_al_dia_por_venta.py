"""Cuando se pregunto por ultima vez el precio de una venta.

2026-10-09, decision del usuario: «un intento al dia por venta, posterior a la
posible hora de cierre».

POR QUE HACE FALTA. El mismo dia se quito el margen tras el plazo: se pregunta
en cuanto pasa la hora de cierre que trae el anuncio, porque desde que la media
solo cuenta ventas cerradas cada hora de espera es una hora que el precio del
jugador no se mueve.

Pero la resolucion corre en CADA sincronizacion, y la aplicacion permite seis
por hora. Sin un freno, las cinco oportunidades de una venta se gastaban en la
primera hora tras el cierre --las cinco posteriores al cierre, las cinco
legitimas-- y la venta se abandonaba antes de que Hattrick llegara a publicar
el traspaso. Con este sello, cinco intentos son cinco dias.

Nulo en lo que ya existe: una venta que nunca se pregunto puede preguntarse hoy.

Revision ID: 0101
Revises: 0100
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0101"
down_revision = "0100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_sales", sa.Column("resolve_asked_at", UtcDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("market_sales", "resolve_asked_at")
