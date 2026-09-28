"""Las filas del estadio dicen si se jugo en el tuyo o en el del rival.

2026-09-28, lo dijo el usuario: «los partidos de visitante de Copa tambien me
dan taquilla». En Copa el reparto es 67/33 entre local y visitante, asi que el
33 % de un partido fuera tambien es dinero del club, y para calcularlo hace
falta el publico de ESE estadio.

Hasta hoy `stadium_history` solo recibia partidos propios en casa, y varias
consultas lo daban por hecho sin decirlo en ninguna parte. Con esta columna la
suposicion se vuelve explicita: la pantalla de Estadio se queda con las de
casa --contar un estadio ajeno falsearia la ocupacion, que se mide contra TU
aforo-- y la de Copa usa las dos, cada una con su porcentaje.

Todo lo que ya estaba guardado ES de casa: nace a `True`.

Revision ID: 0093
Revises: 0092
"""

import sqlalchemy as sa
from alembic import op

revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stadium_history") as batch_op:
        batch_op.add_column(
            sa.Column(
                "own_venue", sa.Boolean(), nullable=False, server_default=sa.text("1")
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("stadium_history") as batch_op:
        batch_op.drop_column("own_venue")
