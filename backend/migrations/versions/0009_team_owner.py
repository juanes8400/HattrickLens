"""Dueño del equipo (MVP: un manager por equipo).

Revision ID: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams", sa.Column("owner_user_id", sa.BigInteger, nullable=True))
    op.create_foreign_key(
        "fk_teams_owner_user_id", "teams", "users", ["owner_user_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_teams_owner_user_id", "teams", ["owner_user_id"])


def downgrade() -> None:
    op.drop_index("ix_teams_owner_user_id", table_name="teams")
    op.drop_constraint("fk_teams_owner_user_id", "teams", type_="foreignkey")
    op.drop_column("teams", "owner_user_id")
