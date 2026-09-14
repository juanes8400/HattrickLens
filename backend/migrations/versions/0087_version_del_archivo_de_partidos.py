"""Con qué reglas se leyó el archivo de partidos.

2026-09-14. La importación inicial pedía a matchesarchive el rango completo
fundación→hoy en una sola consulta. Medido contra el equipo real: con un rango
largo Hattrick lo ignora sin avisar y devuelve los últimos tres meses. Llegaban
menos de 50 partidos, así que tampoco se partía el rango, y el historial quedaba
sellado como completo con sólo tres meses dentro.

Ahora se pide en ventanas de 12 semanas. Este número obliga a releer el archivo
entero UNA vez a quien ya lo tenía sellado con la regla vieja, y se vuelve a
sellar al terminar.

Revision ID: 0087
"""

import sqlalchemy as sa
from alembic import op

revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "teams",
        sa.Column(
            "matches_history_version",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("teams", "matches_history_version")
