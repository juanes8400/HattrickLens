"""2026-08-04: worlddetails.xml trae el <LeagueList> COMPLETO (todos los
países), no un solo registro — corrige la temporada estática errónea (se
usaba LeagueID=50 = Grecia en vez del real de cada equipo) y trae la tasa
de cambio y los nombres de copa reales por país.

- teams.ht_league_id: LeagueID del país del equipo (join key hacia
  world_context), de teamdetails.xml.
- world_context: +country_name, +season_offset.
- world_cups (nueva): copas reales por (ht_league_id, cup_level,
  cup_level_index) — reemplaza el CUP_LEVEL_NAMES hardcodeado de cup.py.

Revision ID: 0029
"""
import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("teams") as batch_op:
        batch_op.add_column(sa.Column("ht_league_id", sa.BigInteger(), nullable=True))

    with op.batch_alter_table("world_context") as batch_op:
        batch_op.add_column(
            sa.Column("country_name", sa.String(128), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("season_offset", sa.SmallInteger(), nullable=False, server_default="0")
        )

    # BigInteger().with_variant(Integer, "sqlite"): igual que `PKBigInt` en
    # models.py — un `id BIGINT PRIMARY KEY` normal en SQLite NO se
    # convierte en alias del rowid (autoincrement real), solo `INTEGER
    # PRIMARY KEY` lo hace. Con el tipo sin corregir, cada INSERT sin `id`
    # explícito fallaba con "NOT NULL constraint failed: world_cups.id" —
    # visto en vivo 2026-08-04 al sincronizar worlddetails contra la cuenta
    # real (invisible en los tests: la suite crea las tablas desde el ORM
    # con `Base.metadata.create_all`, no desde esta migración).
    pk_bigint = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
    op.create_table(
        "world_cups",
        sa.Column("id", pk_bigint, primary_key=True, autoincrement=True),
        sa.Column("ht_league_id", sa.BigInteger(), nullable=False),
        sa.Column("ht_cup_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cup_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("cup_league_level", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("cup_level", sa.SmallInteger(), nullable=False),
        sa.Column("cup_level_index", sa.SmallInteger(), nullable=False),
        sa.UniqueConstraint(
            "ht_league_id", "cup_level", "cup_level_index", name="uq_world_cup_key"
        ),
    )
    op.create_index("ix_world_cups_ht_league_id", "world_cups", ["ht_league_id"])


def downgrade() -> None:
    op.drop_index("ix_world_cups_ht_league_id", table_name="world_cups")
    op.drop_table("world_cups")
    with op.batch_alter_table("world_context") as batch_op:
        batch_op.drop_column("season_offset")
        batch_op.drop_column("country_name")
    with op.batch_alter_table("teams") as batch_op:
        batch_op.drop_column("ht_league_id")
