"""Cuándo se le buscaron comparables a cada jugador.

2026-10-26, decisión del usuario para el barrido diario de precios: «una vez
por día natural y por jugador, independiente de cuántas veces sincronices».

POR QUÉ UN SELLO Y NO UNA CUENTA. Lo de antes no necesitaba ninguno: el turno
salía del propio identificador del jugador --`% 5` contra la semana y `% 6`
contra el día-- así que no había reloj que guardar ni que recolocar al fichar o
vender. Era mejor diseño para una rotación, y por eso duró.

Un barrido diario no rota: le toca a todos, todos los días. Lo que hay que
saber ya no es «¿a quién le toca hoy?» sino «¿a éste ya se le miró hoy?», y eso
no se puede derivar del identificador porque depende de lo que haya pasado.

Y SOBRE TODO NO SE PUEDE DEDUCIR DE LOS DATOS. Una búsqueda que no encuentra
nada no deja huella en `market_sales`: cero filas nuevas, igual que un día en
que no se buscó. Sin este sello, un día en blanco y un día sin empezar son
indistinguibles, y entonces o se repite el barrido en cada sincronización --seis
por hora, con lo que cuesta cada una-- o se pierde el día.

Es además lo que permite NO DAR EL DÍA POR HECHO cuando el centinela de la
cuota descubre que Hattrick no estaba contestando: si no se estampa, mañana se
vuelve a intentar.

Revision ID: 0106
Revises: 0105
"""

import sqlalchemy as sa
from alembic import op

revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nulo a propósito y sin valor por defecto: «nunca se le ha buscado» es un
    # estado real y distinto de «se le buscó hace mucho». A todos los jugadores
    # de hoy les toca mañana, que es lo correcto al estrenar esto.
    op.add_column("players", sa.Column("market_swept_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("players", "market_swept_at")
