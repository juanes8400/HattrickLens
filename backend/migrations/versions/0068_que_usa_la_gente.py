"""Una fila por pagina vista y por clic, para saber que se usa de verdad.

Pedido por el usuario el 2026-08-26. En crudo y no agregado a proposito: de un
contador por modulo y dia no se puede sacar despues cuanto dura una sesion, que
se pulsa dentro de cada pantalla ni a que horas se usa.

El precio es espacio --y que esto si son datos de comportamiento--, asi que la
tabla se poda; ver `podar_eventos_viejos`.

Revision ID: 0068
Revises: 0067
"""
import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import PKBigInt

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ui_events",
        # `PKBigInt`, no `BigInteger` a secas: en SQLite un BIGINT no es
        # autoincremental y el primer INSERT real revienta aunque los tests
        # pasen.
        sa.Column("id", PKBigInt, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("label", sa.String(120), nullable=True),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("visible_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_ui_events_user_id", "ui_events", ["user_id"])
    op.create_index("ix_ui_events_session_id", "ui_events", ["session_id"])
    op.create_index("ix_ui_events_module", "ui_events", ["module"])
    op.create_index("ix_ui_events_at", "ui_events", ["at"])


def downgrade() -> None:
    op.drop_table("ui_events")
