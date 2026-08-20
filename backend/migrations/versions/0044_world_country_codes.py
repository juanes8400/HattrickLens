"""CountryID y CountryCode oficiales de worlddetails.xml para banderas.

Revision ID: 0044
"""
import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("world_context") as batch_op:
        batch_op.add_column(
            sa.Column("country_id", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("country_code", sa.String(length=2), nullable=False, server_default="")
        )
        batch_op.create_index("ix_world_context_country_id", ["country_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("world_context") as batch_op:
        batch_op.drop_index("ix_world_context_country_id")
        batch_op.drop_column("country_code")
        batch_op.drop_column("country_id")
