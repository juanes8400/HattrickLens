"""La liga del club comprador de cada venta.

2026-11-27, pedido del usuario. Para saber a qué país se fue una venta se pide
la ficha del comprador (`teamdetails.xml`), y de ella sólo se guardaba el
NOMBRE del país, que Hattrick escribe en el idioma del usuario («Alemania»).
La lista de países de la app los tiene en el idioma de cada país
(«Deutschland»), así que no casaban y el mapa de destinos no tenía código.
El `LeagueID` casa sin depender del idioma, pero hay clubes en ligas que no
son de ningún país (1000, 1002, internacionales); por eso se guarda también el
`CountryID` del club, que casa con `world_context.country_id` y manda.

`destination_league_attempted` es el «preguntado queda preguntado» de esta
cola: un comprador que Hattrick ya no resuelve no se vuelve a pedir.

Revision ID: 0121
Revises: 0120
"""

import sqlalchemy as sa
from alembic import op

revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("destination_league_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("destination_country_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "destination_league_attempted",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_column("destination_league_attempted")
        batch_op.drop_column("destination_country_id")
        batch_op.drop_column("destination_league_id")
