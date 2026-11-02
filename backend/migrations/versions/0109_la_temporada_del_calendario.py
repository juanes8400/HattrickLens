"""De qué temporada es cada partido de la serie.

2026-11-02, dicho por el usuario después de ascender: «Calendario completo: 14
jornadas que son de la temporada pasada y de equipos que ya no son tus
rivales. Después del ascenso eso no es tu calendario, y es lo que más confunde
de las tres».

Una serie guarda los partidos de TODAS sus temporadas bajo el mismo
`series_ht_id`, y nada decía de cuál era cada uno. Mientras uno se queda en su
serie da igual, porque la tabla va avanzando con ellos; al cambiar de serie no:
la tabla es del sorteo nuevo, a cero, y los partidos que hay son los del año
pasado entre los ocho equipos de entonces. Esos catorce cruces salían como
«calendario completo», entraban en las clasificaciones de local y visitante y
alimentaban al simulador.

LO DICE HATTRICK, no lo deducimos. `leaguefixtures.xml` trae `<Season>`, «la
temporada a la que se refieren los datos», y el lector ya la extraía sin que
nadie la guardara. Aquí sólo se le hace sitio.

NULL EN LO VIEJO, a propósito. Lo sincronizado antes de esto no lleva
temporada y no hay de dónde sacarla sin inventarla; la consulta lo trata como
«no se sabe» y lo sigue contando, igual que se hizo con `series_ht_id` cuando
se añadió. El primer sync lo etiqueta: ese fichero trae el calendario entero
de la temporada en curso cada vez.

Revision ID: 0109
Revises: 0108
"""

import sqlalchemy as sa
from alembic import op

revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("series_season", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "series_season")
