"""2026-08-15, corrección de raíz pedida explícitamente: `sync_changes` sólo
guardaba la frase ya formateada ("Herilala: TSI 202.210 -> 198.930") y el
frontend volvía a extraer los números parseando ese texto. Al unificar el
separador de miles a punto, `Number("202.210")` pasó a valer 202,21 y la UI
mostró un TSI de "202".

Esta columna guarda el cambio como dato: metric/label/before/after/kind, para
que el formato sea una decisión de presentación y no algo que haya que
deshacer con una expresión regular. `summary` se mantiene — sigue siendo útil
para el feed, el CSV y las filas antiguas, que no tienen detalle numérico y
se siguen leyendo con el parser de compatibilidad.

Revision ID: 0045
"""
import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sync_changes") as batch_op:
        batch_op.add_column(sa.Column("detail_json", sa.String(1000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sync_changes") as batch_op:
        batch_op.drop_column("detail_json")
