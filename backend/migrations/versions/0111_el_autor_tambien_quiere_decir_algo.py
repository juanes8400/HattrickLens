"""El canal que faltaba: del autor hacia quien usa la herramienta.

2026-11-03, pedido por el usuario: «un módulo para comunicarle cosas a los
usuarios de la herramienta: que yo escriba un mensaje que quiera que les llegue
en forma de alerta y ellos lo vean».

ES EL REVERSO DE `bug_reports`. Ese canal existe desde el 2026-10-25 y va de
abajo arriba: cualquiera cuenta un fallo y lo lee el autor. Al revés no había
nada, así que un aviso --«el domingo Hattrick corta la API», «esta pantalla
cambió de nombre»-- no tenía por dónde salir.

POR QUÉ SALE POR ALERTAS Y NO POR UN CARTEL NUEVO. Las alertas ya se miran, ya
se ordenan por urgencia y ya tienen buzón: cada uno archiva la suya y eso no se
la quita a nadie. La clave que se emite es `author.notice.{id}`, una por aviso,
de modo que archivar uno no tapa el siguiente.

SE RETIRA, NO SE BORRA. Una fila del buzón apunta a la clave del aviso; si el
aviso desapareciera de la base, ese archivado quedaría huérfano para siempre.
`retired_at` deja de emitirlo y conserva qué se dijo y cuándo.

`until` existe porque casi todos los avisos caducan solos y nadie se acuerda de
retirarlos a mano. Nulo significa «hasta que yo lo retire».

Revision ID: 0111
Revises: 0110
"""

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0111"
down_revision = "0110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "author_notices",
        # LA MISMA VARIANTE QUE `PKBigInt` EN LOS MODELOS, y no un `BigInteger`
        # a secas. SQLite sólo trata como autoincremental la columna declarada
        # literalmente `INTEGER PRIMARY KEY`: con `BIGINT PRIMARY KEY` el
        # insert falla con «NOT NULL constraint failed». Mismo tropiezo que en
        # la 0104, y por el mismo motivo no lo ven las pruebas: montan las
        # tablas con `create_all`, que usa los modelos y por tanto la variante
        # correcta, así que esto sólo aparece sobre una base migrada. Aquí se
        # vio publicando un aviso en el navegador.
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        sa.Column("author_user_id", sa.BigInteger(), nullable=False),
        sa.Column("at", UtcDateTime(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False, server_default=""),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("until", UtcDateTime(), nullable=True),
        sa.Column("retired_at", UtcDateTime(), nullable=True),
    )
    op.create_index("ix_author_notices_author_user_id", "author_notices", ["author_user_id"])
    op.create_index("ix_author_notices_at", "author_notices", ["at"])


def downgrade() -> None:
    op.drop_index("ix_author_notices_at", table_name="author_notices")
    op.drop_index("ix_author_notices_author_user_id", table_name="author_notices")
    op.drop_table("author_notices")
