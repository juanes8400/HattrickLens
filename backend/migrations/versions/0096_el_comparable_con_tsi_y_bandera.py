"""El comparable guarda tambien su TSI y su pais.

2026-10-07, pedido del usuario al mirar la tabla: quiere la bandera del
jugador y su TSI entre las columnas.

Los dos datos YA venian del mercado --`transfersearch` manda `TSI` dentro de
`Details` y `NativeCountryID` en la raiz-- y se tiraban al construir el
candidato, porque hasta ahora solo se guardaba lo que decide el parecido. No
deciden nada: el usuario comparo por habilidades y edad, no por TSI ni por
pais. Se guardan para enseñarlos.

Nacen a cero, que es «no se sabe»: las filas que ya estaban en el fondo se
anotaron sin ellos y no se van a volver a consultar solo por esto. La
bandera de esas sale como el hueco neutro que ya pinta `CountryFlag` cuando
no reconoce el codigo, y su TSI como cero.

Revision ID: 0096
Revises: 0095
"""

import sqlalchemy as sa
from alembic import op

revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "market_sales",
        sa.Column("tsi", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "market_sales",
        sa.Column("country_id", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("market_sales", "country_id")
    op.drop_column("market_sales", "tsi")
