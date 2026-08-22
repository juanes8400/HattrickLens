"""Las ventas que Hattrick entrega sin identificador de jugador.

2026-08-22. Eran 54 de las 506 ventas del club, y se descartaban: sin ese dato
no se pueden atribuir a nadie, y meterlas todas bajo el mismo hueco creaba un
jugador fantasma con quince llegadas y ninguna salida. Ahora cada una usa el
numero de su transferencia como identificador, que es unico, asi que cada
movimiento queda en su propia ficha.

Tres cambios:

1. `players.ht_player_id_is_transfer` — el numero no es suyo, es el de la
   transferencia.
2. `player_stints.unknown_origin` — ni comprado ni de cantera. La regla de
   "venta sin compra delante = canterano" es cierta casi siempre, pero no aqui:
   estos no salieron de la cantera, salieron de un dato que falta.
3. `team_transfers` deja de ser unica por transferencia y pasa a serlo por
   transferencia Y lado. Cuando el club aparece de comprador y de vendedor a la
   vez, la venta es tan real como la compra --con su salario y su comision-- y
   Hattrick tambien la cuenta en sus dos totales.

Revision ID: 0061
"""
import sqlalchemy as sa
from alembic import op

revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "players",
        sa.Column(
            "ht_player_id_is_transfer", sa.Boolean(),
            nullable=False, server_default="0",
        ),
    )
    op.add_column(
        "player_stints",
        sa.Column(
            "unknown_origin", sa.Boolean(), nullable=False, server_default="0",
        ),
    )
    # El indice unico de `ht_transfer_id` se cambia por uno compuesto. En
    # SQLite la restriccion vive en el CREATE TABLE, asi que hace falta
    # reconstruir la tabla; en Postgres basta con cambiar el indice.
    with op.batch_alter_table("team_transfers") as batch:
        batch.drop_index("ix_team_transfers_ht_transfer_id")
        batch.create_index(
            "ix_team_transfers_ht_transfer_id", ["ht_transfer_id"], unique=False
        )
        batch.create_unique_constraint(
            "uq_transfer_por_lado", ["ht_transfer_id", "is_buy"]
        )


def downgrade() -> None:
    with op.batch_alter_table("team_transfers") as batch:
        batch.drop_constraint("uq_transfer_por_lado", type_="unique")
        batch.drop_index("ix_team_transfers_ht_transfer_id")
        batch.create_index(
            "ix_team_transfers_ht_transfer_id", ["ht_transfer_id"], unique=True
        )
    op.drop_column("player_stints", "unknown_origin")
    op.drop_column("players", "ht_player_id_is_transfer")
