"""2026-08-12, pedido explícitamente ("Lee bien cómo se leen los
asistentes"): club.xml v1.1 (verificado en vivo) ya no trae los niveles
agregados por puesto — el desglose real, persona por persona, vive en
stafflist.xml. Esta columna guarda ese roster real (nombre + tipo + nivel de
cada persona) del snapshot, para poder mostrar "2 asistentes de nivel 5 cada
uno" en vez de un número agregado sin procedencia clara.

Revision ID: 0042
"""
import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("staff_snapshots") as batch_op:
        batch_op.add_column(sa.Column("staff_members_json", sa.String(4000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("staff_snapshots") as batch_op:
        batch_op.drop_column("staff_members_json")
