"""2026-08-12, pedido explícitamente ("Conversión" no funcionaba): la
suposición original de que matchdetails.xml trae una lista de `<Event>`
con `EventTypeID` para clasificar ocasiones era incorrecta — verificado en
vivo contra un partido real, la versión 3.1 nunca trae ese elemento. Lo que
sí trae, por cada lado, son conteos reales de ocasiones por zona
(`NrOfChancesLeft/Center/Right/SpecialEvents/Other`). `match_events` queda
vacía desde siempre (0 filas reales) porque el parser nunca encontraba ese
elemento — se elimina en vez de mantener una tabla que nunca tuvo datos
reales que pudiera tener.

Revision ID: 0041
"""
import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("match_ratings") as batch_op:
        batch_op.add_column(sa.Column("chances_left", sa.SmallInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("chances_center", sa.SmallInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("chances_right", sa.SmallInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("chances_special", sa.SmallInteger(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("chances_other", sa.SmallInteger(), nullable=False, server_default="0"))
    op.drop_table("match_events")


def downgrade() -> None:
    op.create_table(
        "match_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ht_match_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("minute", sa.SmallInteger(), nullable=False),
        sa.Column("event_type_id", sa.Integer(), nullable=False),
        sa.Column("subject_team_ht_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("text", sa.String(1000), nullable=True),
    )
    with op.batch_alter_table("match_ratings") as batch_op:
        batch_op.drop_column("chances_other")
        batch_op.drop_column("chances_special")
        batch_op.drop_column("chances_right")
        batch_op.drop_column("chances_center")
        batch_op.drop_column("chances_left")
