"""Lo que dijo el ojeador que trajo a cada canterano.

2026-08-24. CHPP no publica una lista de ojeadores --`youthscouts`,
`youthscoutlist` y `scouts` devuelven 401--, pero `youthplayerdetails.xml`
trae, por canterano, el `ScoutCall`: quien lo encontro, en que region estaba
ojeando y sus comentarios TAL CUAL, con el texto que el usuario ve en el
juego. Se guarda el texto literal a proposito: el dato destilado (habilidad,
nivel, potencial) ya esta en las fotos; lo que solo vive aqui es el tono de
la ficha original.

El mismo fichero trae `MayUnlock` por habilidad: si el ojeador todavia puede
revelarla. Hasta ahora eso se suponia mirando si el techo estaba vacio; ahora
lo dice el juego.

Una fila por canterano. El ojeador que lo trajo no cambia nunca; `MayUnlock`
si, asi que `fetched_at` dice de cuando es la lectura.

Revision ID: 0063
"""
import sqlalchemy as sa
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

#  Igual que el resto de tablas: BigInteger en Postgres, Integer en SQLite.
#  Sin la variante, el autoincremento de SQLite no funciona y el primer
#  INSERT real revienta aunque las pruebas pasen.
PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "youth_scout_reports",
        sa.Column("id", PK, primary_key=True),
        sa.Column(
            "youth_player_id", sa.BigInteger(),
            sa.ForeignKey("youth_players.id"), nullable=False, unique=True,
        ),
        sa.Column("scout_id", sa.BigInteger(), nullable=True),
        sa.Column("scout_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("scouting_region_id", sa.Integer(), nullable=True),
        #  Los comentarios enteros, con su texto. JSON y no una tabla aparte:
        #  se leen y se escriben siempre juntos, nunca por separado.
        sa.Column("comments_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("may_unlock_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("youth_scout_reports")
