"""El anuncio sin pujas también se guarda, con su forma y su precio pedido.

2026-11-07. El usuario encontró el agujero por su nombre: «472301981, este
jugador debió haber entrado al comparador. Posible explicación: no lo tomó
porque no tuvo puja sino hasta el final, y ya entre puja final y el jugador
siendo un desconocido, no hubo sincronización».

Tenía razón, y el código lo decía sin que nadie lo leyera: `cosecha` separa los
anuncios en dos montones --con puja y sin puja-- y el segundo se devolvía sólo
para poder CONTARLO. Nunca se guardaba. Un anuncio que pasa días a cero y
recibe su primera puja en la última hora no vuelve a verse: cuando se vendió,
para nosotros no existía, y su precio de cierre --el dato bueno, el que de
verdad se pagó-- se perdía.

LA SOLUCIÓN ES LA SUYA: guardarlos aunque estén a cero, intentar resolverlos
igual que a los demás, y descartar los que al final no se vendieron. No cambia
ningún número de hoy, porque un anuncio sin puja ya no ocupaba plaza ni contaba
para la media; lo que cambia es que ahora puede CONVERTIRSE en una venta
cerrada, que es la única cosa que sí cuenta.

TRES COLUMNAS.

· `form` es la FORMA del vendido, de 1 a 8, que el usuario pidió como columna
  del comparador. El parser del mercado ya la traía desde siempre y se tiraba
  en el camino. `-1` es «no la sabemos»: las ventas guardadas antes de hoy.

· `asking_price` es lo que PEDÍA el vendedor cuando se encontró el anuncio, y
  se escribe UNA SOLA VEZ, al abrir la fila. Volver a ver el mismo anuncio no
  lo pisa, porque los vendedores bajan el precio pedido y lo que el usuario
  quiere guardar es el INICIAL: «guardar el precio inicial, para analizar la
  relación entre precio inicial, final y horario». Cero es «no lo sabemos».

· `never_bid` no existe y no hace falta: `bid_price = 0` ya dice «no vimos
  ninguna puja», porque `HighestBid` vale 0 exactamente cuando no hay pujas y
  las filas de antes de hoy sólo se abrían con puja encima.

Revision ID: 0112
Revises: 0111
"""

import sqlalchemy as sa
from alembic import op

revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_sales",
        sa.Column("form", sa.Integer(), nullable=False, server_default="-1"),
    )
    op.add_column(
        "market_sales",
        sa.Column("asking_price", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("market_sales", "asking_price")
    op.drop_column("market_sales", "form")
