"""Cuándo merece la pena buscar una reventa, y a quién ya se probó.

2026-08-24. La vigilancia de reventas era ciega: 218 ex-jugadores en cola y
25 revisiones por sincronización, la inmensa mayoría gastadas en semanas
donde no había nada que encontrar.

Pero el dinero lo delata. `economy.xml` trae `IncomeSoldPlayersCommission`
en una línea propia, separada de las ventas del club, y ya se descargaba en
cada sync: si esa cifra sube, alguien revendió a un ex-jugador nuestro. No
dice quién, pero dice CUÁNDO merece la pena mirar.

Tres columnas en `teams`:

  * `commission_seen` y `commission_seen_closed` — las dos cifras de la
    última vez que se miró, la semana en curso y la ya cerrada. Hacen falta
    las dos: la primera detecta el dinero según entra, y la segunda lo
    rescata si no se sincronizó durante esa semana.
  * `commission_hunting` — hay dinero por atribuir.
  * `commission_tried_json` — a quién ya se probó en ESTA cacería. Se vacía
    al abrir una nueva: si no, la parte aleatoria de la búsqueda se agotaría
    tras el primer barrido y no volvería a mirar a nadie.

Revision ID: 0064
"""
import sqlalchemy as sa
from alembic import op

revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "commission_seen", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "commission_seen_closed", sa.BigInteger(), nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "commission_hunting", sa.Boolean(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "teams",
        sa.Column(
            "commission_tried_json", sa.Text(), nullable=False, server_default="[]"
        ),
    )


def downgrade() -> None:
    op.drop_column("teams", "commission_tried_json")
    op.drop_column("teams", "commission_hunting")
    op.drop_column("teams", "commission_seen_closed")
    op.drop_column("teams", "commission_seen")
