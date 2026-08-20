"""2026-08-15, pedido explícitamente: una academia juvenil se puede cerrar y
volver a abrir, y cada apertura es una academia DISTINTA — `youthteamdetails`
la identifica con su propio `YouthTeamID` y su `CreatedDate`.

Sin ese dato el ROI de Juveniles sumaba los canteranos vendidos de academias
anteriores contra la inversión de la actual: dos cosas distintas en la misma
resta. Con la fecha de creación se puede acotar el cálculo a la cantera viva.

Revision ID: 0046
"""
import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("ht_youth_team_id", sa.BigInteger, nullable=True))
        batch_op.add_column(sa.Column("youth_team_name", sa.String(128), nullable=True))
        batch_op.add_column(
            sa.Column("youth_academy_created_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("youth_academy_created_at")
        batch_op.drop_column("youth_team_name")
        batch_op.drop_column("ht_youth_team_id")
