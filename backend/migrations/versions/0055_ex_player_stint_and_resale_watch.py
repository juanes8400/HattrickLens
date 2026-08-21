"""El pasado de un ex-jugador, en su propia ficha.

2026-08-21, diseñado con el usuario. Dos cosas distintas sobre quien ya salió
del club, que hasta ahora no se guardaban en ninguna parte:

1. Cuántos partidos jugó de verdad con nosotros (al menos un minuto). Fija la
   comisión si alguien lo revende. Contarlo cuesta una alineación por partido,
   así que es el trabajo más caro que hay: se hace UNA vez por jugador y se
   guarda.
2. Si sigue pudiendo darnos dinero. Un jugador normal cobra comisión solo en
   la SIGUIENTE venta, así que revendido o despedido queda cerrado para
   siempre. Un canterano cobra en cada venta futura: solo lo cierra el
   despido.

Antes, la revisión de reventas cogía 25 ex-jugadores al azar en cada
sincronización, sin recordar a quién había preguntado ya. Nunca convergía.

Revision ID: 0055
"""
import sqlalchemy as sa
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

COLUMNAS = (
    sa.Column("stint_games_played", sa.SmallInteger(), nullable=True),
    sa.Column("stint_census_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("resale_closed", sa.Boolean(), nullable=False, server_default="0"),
    sa.Column("resale_closed_reason", sa.String(32), nullable=True),
)


def upgrade() -> None:
    for columna in COLUMNAS:
        op.add_column("players", columna)


def downgrade() -> None:
    for columna in reversed(COLUMNAS):
        op.drop_column("players", columna.name)
