"""2026-09-27, caso del usuario: el partido 770393948 del FC Villainy salia en
Equipo con ocho jugadores y una formacion «3-5-0», que no existe.

`submitted_lineup_json` son las ORDENES, y solo se pueden capturar mientras el
partido sigue proximo y con ordenes dadas. Si nadie sincronizo en esa ventana
--lo normal en un segundo equipo-- ese partido se queda sin ellas para siempre,
y el once tenia que salir de las fichas de los jugadores, que se pisan en cuanto
juegan otro partido.

Un partido ya jugado es un hecho publico y permanente: `matchlineup.xml` lo
sirve cuando sea. Aqui se guarda ese once, una vez por partido.

Revision ID: 0090
Revises: 0089
"""

import sqlalchemy as sa
from alembic import op

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.add_column(sa.Column("played_lineup_json", sa.String(length=4000), nullable=True))
        batch_op.add_column(
            sa.Column("played_lineup_captured_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_column("played_lineup_captured_at")
        batch_op.drop_column("played_lineup_json")
