"""Las dos selecciones de cada país.

2026-08-22. `worlddetails.xml` trae, por país, el identificador de la selección
absoluta y el de la sub-21 (CHPP sigue llamando `U20TeamId` al campo por
historia; el equipo se llama "U21 <país>"). Ya se descargaba entero y esos dos
campos se tiraban.

Hacen falta para saber dónde mirar cuando a un jugador le sube el contador de
partidos internacionales: los partidos de selección no están en el archivo de
partidos de ningún club.

Revision ID: 0060
"""
import sqlalchemy as sa
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "world_context",
        sa.Column("national_team_id", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "world_context",
        sa.Column("u21_team_id", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("world_context", "u21_team_id")
    op.drop_column("world_context", "national_team_id")
