"""La puja con la que entro una venta, aparte del precio de cierre.

2026-10-07, pedido del usuario: «asegurate que podamos ver la diferencia
entre la puja que detectamos y el verdadero precio de venta».

Hasta ahora `price` era las dos cosas una detras de otra: la puja mientras la
subasta seguia abierta, y el precio de verdad cuando se resolvia, pisando a la
primera. Asi no hay forma de enseñar el salto, que es justo el dato que dice
cuanto se queda corta una puja. Las dos medidas que hay: Valerio Cataldi
65.000.000 -> 77.720.000 (+16%) y Guido Bernacki 4.990.000 -> 5.090.000 (+2%).

`bid_price` se escribe al encontrar la venta y NO se vuelve a tocar. Para las
filas que ya estaban, se copia `price`: todas son provisionales --ninguna se
habia resuelto todavia-- asi que su precio ES su puja.

Revision ID: 0097
Revises: 0096
"""

import sqlalchemy as sa
from alembic import op

revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_sales",
        sa.Column("bid_price", sa.BigInteger(), nullable=False, server_default="0"),
    )
    # Lo ya guardado es todo provisional, asi que su precio es su puja.
    #
    # EN EXPRESION Y NO EN SQL A MANO. La primera version decia
    # `WHERE is_final = 0`, que es SQLite y nada mas: ahi un booleano es un
    # entero, pero en Postgres --que es lo que corre en Render-- comparar
    # boolean con integer es un error de tipos y tumba el despliegue. Paso
    # local y fallo arriba el 2026-10-07. Dejando que SQLAlchemy lo escriba,
    # cada dialecto pone su propia constante.
    ventas = sa.table(
        "market_sales",
        sa.column("bid_price", sa.BigInteger),
        sa.column("price", sa.BigInteger),
        sa.column("is_final", sa.Boolean),
    )
    op.execute(
        ventas.update().where(ventas.c.is_final.is_(False)).values(bid_price=ventas.c.price)
    )


def downgrade() -> None:
    op.drop_column("market_sales", "bid_price")
