"""El libro de visitas: una firma por quien quiera dejar un mensaje.

Pedido por el usuario el 2026-09-05, junto al boton de apoyo. La idea es que
de aqui salgan las funcionalidades siguientes: quien usa la herramienta cuenta
que le falta, y eso vale mas que cualquier lista escrita a solas.

Se guarda el nombre del club COPIADO en la fila y no una referencia: un club
puede cambiar de nombre, y una firma de hace un anio quedaria atribuida a un
club que no existia cuando se escribio.

Revision ID: 0082
Revises: 0081
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import PKBigInt

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guestbook_entries",
        # `PKBigInt`, no `BigInteger` a secas: en SQLite un BIGINT no es
        # autoincremental y el primer INSERT real revienta aunque los tests
        # pasen (mordio de verdad en la 0068).
        sa.Column("id", PKBigInt, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("team_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("country", sa.String(64), nullable=False, server_default=""),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "hidden", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.create_index("ix_guestbook_entries_user_id", "guestbook_entries", ["user_id"])
    op.create_index(
        "ix_guestbook_entries_created_at", "guestbook_entries", ["created_at"]
    )


def downgrade() -> None:
    op.drop_table("guestbook_entries")
