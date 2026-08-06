"""Saldo neto por jugador (HL-161): edad en el momento de la venta,
reconstruida hacia atrás para jugadores sin snapshot previo a su venta.

La edad en Hattrick es una función pura del tiempo transcurrido (112 días
por "año"/temporada, sin entrenamiento ni azar de por medio) — a diferencia
de las habilidades, si sabemos la edad de HOY (vía playerdetails.xml, que
funciona para cualquier jugador aunque ya no esté en el equipo) podemos
calcular con exactitud la edad en cualquier fecha pasada. Confirmado por el
usuario 2026-08-04.

Revision ID: 0026
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("age_years_at_sale", sa.SmallInteger(), nullable=True))
        batch_op.add_column(sa.Column("age_days_at_sale", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("age_days_at_sale")
        batch_op.drop_column("age_years_at_sale")
