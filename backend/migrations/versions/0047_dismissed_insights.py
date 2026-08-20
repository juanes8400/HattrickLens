"""2026-08-16, pedido explícito: poder descartar una alerta con una X y que
quede guardada en un buzón.

Las alertas no son filas: `domain.engines.insights` las vuelve a derivar de
los datos en cada petición, así que no hay nada que "marcar como leído". Lo
que se guarda aquí es la decisión del usuario — junto con una copia del texto
que descartó, para que el buzón siga mostrando qué archivó aunque la condición
que la disparó ya no exista.

`fingerprint` es lo que hace que descartar no sea silenciar para siempre: si
la alerta se vuelve a generar con otro contenido (otra cifra, otra severidad),
la huella cambia y vuelve a la lista activa. Descartar "pierdes dinero cada
semana" no puede esconder que la semana siguiente pierdas el doble.

Revision ID: 0047
"""
import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # En sqlite sólo `INTEGER PRIMARY KEY` es alias de rowid y autoincrementa;
    # un `BIGINT PRIMARY KEY` deja el id en NULL y el INSERT falla. Es la misma
    # variante que usa el ORM (`PKBigInt`), así que hay que repetirla aquí.
    pk_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "dismissed_insights",
        sa.Column("id", pk_bigint, primary_key=True, autoincrement=True),
        sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("detail", sa.String(1000), nullable=False),
        sa.Column("action", sa.String(500), nullable=False, server_default=""),
        sa.Column("module", sa.String(64), nullable=False, server_default=""),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("team_id", "key", name="uq_dismissed_insight"),
    )
    op.create_index("ix_dismissed_insights_team_id", "dismissed_insights", ["team_id"])


def downgrade() -> None:
    op.drop_index("ix_dismissed_insights_team_id", table_name="dismissed_insights")
    op.drop_table("dismissed_insights")
