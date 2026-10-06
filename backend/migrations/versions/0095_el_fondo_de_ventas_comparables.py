"""El fondo de ventas comparables y el sello del paso semanal.

2026-10-06, disenado pregunta a pregunta con el usuario. Para poner precio a un
jugador propio se miran ventas CERRADAS de jugadores parecidos, y esas ventas
hay que guardarlas en algun sitio.

Dos decisiones suyas estan en la forma de esta tabla:

- **El fondo es del equipo, no del jugador.** Por eso cada fila guarda el
  perfil del jugador vendido (edad y las tres habilidades que cuentan) y NO el
  peso. El peso es relativo a quien pregunta: guardandolo, esta venta solo
  serviria para aquel para quien se busco. Con el perfil se vuelve a medir
  contra cualquier jugador de la plantilla sin gastar una sola llamada.
- **La cola de pendientes es la misma tabla.** Mientras `is_final` sea falso,
  `price` es la puja en curso y hay que volver a preguntar cuando pase
  `deadline`. Son dos estados de la misma cosa, no dos tablas.

Por que importa resolver, con un caso medido: el 2026-10-05 Valerio Cataldi
tenia 65.000.000 de puja y cerro en 77.720.000, un 16% mas. La puja no solo es
incierta, se queda corta siempre por el mismo lado.

`teams.market_run_at` nace a NULL, que significa «nunca se ha corrido», y hace
que el primer paso se dispare en cuanto toque.

Revision ID: 0095
Revises: 0094
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_sales",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("team_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_player_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("price", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deadline", UtcDateTime(), nullable=True),
        sa.Column("seen_at", UtcDateTime(), nullable=False),
        sa.Column("resolve_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("age_years", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("primary_skill", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("primary_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("secondary_skill", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("secondary_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tertiary_skill", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("tertiary_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("specialty", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "ht_player_id", name="uq_market_sale_por_equipo"),
    )
    op.create_index("ix_market_sales_team_id", "market_sales", ["team_id"])
    op.create_index("ix_market_sales_ht_player_id", "market_sales", ["ht_player_id"])
    op.create_index(
        "ix_market_sales_pendientes", "market_sales", ["team_id", "is_final", "deadline"]
    )

    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("market_run_at", UtcDateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("market_run_at")
    op.drop_index("ix_market_sales_pendientes", table_name="market_sales")
    op.drop_index("ix_market_sales_ht_player_id", table_name="market_sales")
    op.drop_index("ix_market_sales_team_id", table_name="market_sales")
    op.drop_table("market_sales")
