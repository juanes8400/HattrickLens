"""Un intento de venta, de principio a fin.

2026-08-22, pedido explícitamente. Hasta ahora una fila de
`player_listing_attempts` decía solo "apareció en el mercado tal día". Un
intento de venta es más que eso: tiene un plazo, un final y un resultado, y es
lo que de verdad se quiere estudiar — a qué precio se vende, en qué semana,
cuántas veces hubo que intentarlo.

`times_seen` es el único dato de toda la aplicación que Hattrick no entrega por
CHPP: solo lo dice en el texto de las noticias al cerrarse la puja ("este
jugador fue visto 8 veces mientras estaba en la lista de transferibles"). Lo
teclea el usuario, y `times_seen_asked` recuerda que ya se le preguntó para que
el aviso no vuelva a salir eternamente.

Sin relleno hacia atrás, por decisión del usuario: empieza a contar desde el
primer intento que se detecte.

Revision ID: 0058
"""
import sqlalchemy as sa
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None

COLUMNAS = (
    sa.Column("ht_player_id", sa.BigInteger()),
    sa.Column("stint_id", sa.BigInteger()),
    sa.Column("deadline", sa.DateTime(timezone=True)),
    sa.Column("ended_at", sa.DateTime(timezone=True)),
    sa.Column("last_highest_bid", sa.BigInteger()),
    sa.Column("sold", sa.Boolean(), nullable=False, server_default="0"),
    sa.Column("times_seen", sa.Integer()),
    sa.Column("times_seen_asked", sa.Boolean(), nullable=False, server_default="0"),
)


def upgrade() -> None:
    for columna in COLUMNAS:
        op.add_column("player_listing_attempts", columna)
    op.create_index(
        "ix_player_listing_attempts_ht_player_id",
        "player_listing_attempts",
        ["ht_player_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_listing_attempts_ht_player_id", "player_listing_attempts"
    )
    for columna in reversed(COLUMNAS):
        op.drop_column("player_listing_attempts", columna.name)
