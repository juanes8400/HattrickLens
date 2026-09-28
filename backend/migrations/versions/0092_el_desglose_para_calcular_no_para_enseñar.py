"""Vuelve la asistencia por sector, para CALCULAR y no para enseñar.

2026-09-28, decision del usuario con esas palabras: «guarda el desglose,
calcula con el, y no lo enseñes nunca».

La 0076 las borro el 2026-09-01 por si enseñar el desglose imitaba una funcion
de HT Supporter. El efecto colateral fue que la taquilla de un partido dejo de
poder calcularse: Hattrick no la publica por partido, la columna `revenue` a
la que se cambio no se rellena nunca, y atribuirla por semanas cerradas no
funciona porque los partidos de Copa comparten semana con los de liga. El
panel de Copa llevaba desde entonces enseñando «0 US$» con sesenta y seis
partidos jugados en casa.

La linea pasa a estar en ENSEÑARLO, no en guardarlo: estos cuatro numeros no
salen por ninguna respuesta de la API, solo alimentan el total de la taquilla.
Lo fija una prueba que recorre las respuestas y falla si alguno se asoma.

Nacen a NULL: los partidos ya sincronizados no tienen el desglose y se rellena
por tandas pidiendo otra vez su detalle. NULL no es cero: es «no se sabe», y
esos partidos no entran en el total hasta que se sepan.

Revision ID: 0092
Revises: 0091
"""

import sqlalchemy as sa
from alembic import op

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None

SECTORES = ("sold_terraces", "sold_basic", "sold_roof", "sold_vip")


def upgrade() -> None:
    with op.batch_alter_table("stadium_history") as batch_op:
        for columna in SECTORES:
            batch_op.add_column(sa.Column(columna, sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("stadium_history") as batch_op:
        for columna in SECTORES:
            batch_op.drop_column(columna)
