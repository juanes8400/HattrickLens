"""Cada etapa, un registro; y el libro de transferencias, guardado.

2026-08-22, pedido explícitamente. La compra y la venta vivían encima de la
fila del jugador, así que quien volvía al club pisaba su etapa anterior. En la
base del usuario ya había un caso real, Humberto Granada: una fila que decía
"comprado el 01/08/2026, vendido el 17/07/2022", vendido cuatro años antes de
comprarlo.

Dos tablas:

- `team_transfers` guarda cada movimiento tal como lo cuenta Hattrick. Antes se
  leía y se tiraba, y por eso no había forma de reconstruir nada hacia atrás.
- `player_stints` es una fila por paso por el club, derivada de la anterior:
  una compra abre etapa y la venta siguiente la cierra.

Revision ID: 0057
"""
import sqlalchemy as sa
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "team_transfers",
        sa.Column("id", PK, primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"),
                  nullable=False, index=True),
        sa.Column("ht_transfer_id", sa.BigInteger, nullable=False,
                  unique=True, index=True),
        sa.Column("ht_player_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("player_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("price", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("is_buy", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("counterpart_team_id", sa.BigInteger),
        sa.Column("tsi", sa.Integer),
    )
    op.create_table(
        "player_stints",
        sa.Column("id", PK, primary_key=True, autoincrement=True),
        sa.Column("player_id", sa.BigInteger, sa.ForeignKey("players.id"),
                  nullable=False, index=True),
        sa.Column("ht_player_id", sa.BigInteger, nullable=False, index=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"),
                  nullable=False, index=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True)),
        sa.Column("arrival_price", sa.Integer),
        sa.Column("arrival_transfer_id", sa.BigInteger),
        sa.Column("from_academy", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.Column("sale_price", sa.Integer),
        sa.Column("sale_transfer_id", sa.BigInteger),
        sa.Column("buyer_team_id", sa.BigInteger),
        sa.Column("games_played_for_us", sa.SmallInteger),
        sa.Column("games_computed_at", sa.DateTime(timezone=True)),
        sa.Column("excluded", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("training_type_manual", sa.SmallInteger),
        sa.Column("top_skill_manual", sa.String(32)),
        sa.Column("age_years_manual", sa.SmallInteger),
        sa.Column("age_days_manual", sa.SmallInteger),
        sa.UniqueConstraint("player_id", "arrived_at", name="uq_stint_player_arrival"),
    )


def downgrade() -> None:
    op.drop_table("player_stints")
    op.drop_table("team_transfers")
