"""La venta resuelta guarda el TransferID de Hattrick.

2026-10-07, pedido del usuario: «eso tiene TransferID para distinguir de
transferencias seguidas».

DONDE EXISTE Y DONDE NO. `transfersplayer.xml` lo trae en cada traspaso.
`transfersearch.xml` NO: comprobado ese dia listando las etiquetas de un
anuncio del mercado --PlayerId, FirstName, NickName, LastName,
NativeCountryID, AskingPrice, Deadline, HighestBid, BidderTeam, SellerTeam y
Details-- y ninguna lo menciona. Es logico: mientras la subasta vive, la
transferencia todavia no ha ocurrido y no tiene id.

Asi que el emparejamiento de la resolucion sigue siendo POR PLAZO, que es el
unico dato presente en los dos lados. Lo que cambia es que, una vez
resuelta, la venta deja de identificarse por una marca de tiempo con
tolerancia de cinco minutos y pasa a tener el identificador real.

Nace a cero, que significa «todavia es una puja». Las filas que ya estaban
sin resolver se quedan asi, y lo recogeran al resolverse.

Revision ID: 0098
Revises: 0097
"""

import sqlalchemy as sa
from alembic import op

revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_sales",
        sa.Column("ht_transfer_id", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("market_sales", "ht_transfer_id")
