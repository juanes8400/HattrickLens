"""Identidad = cuenta de Hattrick, no email/contraseña propios.

Conectar vía OAuth con CHPP es el único inicio de sesión de HT Lens. Se
reconoce a un usuario que vuelve a conectar por `ht_user_id` (UserID de CHPP),
no por credenciales propias — de ahí que email/password_hash pasen a ser
opcionales en vez de obligatorios.

Revision ID: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ht_user_id", sa.BigInteger, nullable=True))
    op.create_unique_constraint("uq_users_ht_user_id", "users", ["ht_user_id"])
    op.add_column("users", sa.Column("login_name", sa.String(64), nullable=True))
    op.alter_column("users", "email", existing_type=sa.String(320), nullable=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(128), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.String(128), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(320), nullable=False)
    op.drop_column("users", "login_name")
    op.drop_constraint("uq_users_ht_user_id", "users", type_="unique")
    op.drop_column("users", "ht_user_id")
