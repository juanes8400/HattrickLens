"""Con qué reglas se leyó el libro de transferencias.

2026-08-22. Las reglas cambiaron: antes se descartaban los movimientos que
Hattrick entrega sin identificador de jugador, y de los que nos tienen de
comprador y de vendedor a la vez solo se anotaba un lado. El libro ya guardado
se quedó corto --85 ventas y 42 millones-- y la marca de "historial completo"
decía que no faltaba nada.

Este número obliga a releerlo entero UNA vez, para todos, y se vuelve a sellar
al terminar. Sin esto el arreglo solo valdría para quien empiece de cero.

Revision ID: 0062
"""
import sqlalchemy as sa
from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "transfers_import_version", sa.SmallInteger(),
            nullable=False, server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("teams", "transfers_import_version")
