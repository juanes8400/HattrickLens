"""Las cinco tablas que nunca tuvieron migración — descubierto al desplegar.

`matches`, `match_ratings`, `standings`, `stadium_history` y
`former_youth_players` existían en el modelo y en la base de desarrollo, pero
NINGUNA migración las creaba: nacieron de un `create_all` en local y las
migraciones posteriores dieron por hecho que ya estaban ahí. Con la base de
desarrollo delante no se nota nunca; contra una base vacía, `alembic upgrade
head` se para en 0005 con "relation stadium_history does not exist".

Va aquí, entre 0004 y 0005, porque 0005 es la primera que las toca. Las
columnas que añaden 0005, 0011, 0017, 0018, 0022, 0036, 0037 y 0041 NO se
incluyen: son suyas y se añaden después, como en cualquier base que haya
seguido la cadena entera.

Se salta lo que ya exista, para que una base viva (la de desarrollo, que ya
las tiene) pase por aquí sin romperse.

Revision ID: 0004a
"""
import sqlalchemy as sa
from alembic import op

revision = "0004a"
down_revision = "0004"
branch_labels = None
depends_on = None

# En sqlite sólo `INTEGER PRIMARY KEY` es alias del rowid y autoincrementa;
# BIGINT puro no. Misma variante que usa `PKBigInt` en models.py.
PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    existentes = set(sa.inspect(op.get_bind()).get_table_names())

    if "matches" not in existentes:
        op.create_table(
            "matches",
            sa.Column("id", PK, primary_key=True, autoincrement=True),
            sa.Column("ht_match_id", sa.BigInteger, nullable=False, unique=True, index=True),
            sa.Column("played_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("match_type", sa.SmallInteger, nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("home_team_ht_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("away_team_ht_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("home_team_name", sa.String(128), nullable=False),
            sa.Column("away_team_name", sa.String(128), nullable=False),
            sa.Column("home_goals", sa.SmallInteger, nullable=False),
            sa.Column("away_goals", sa.SmallInteger, nullable=False),
        )

    if "match_ratings" not in existentes:
        op.create_table(
            "match_ratings",
            sa.Column("id", PK, primary_key=True, autoincrement=True),
            sa.Column("ht_match_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("team_ht_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("midfield", sa.SmallInteger, nullable=False),
            sa.Column("right_def", sa.SmallInteger, nullable=False),
            sa.Column("central_def", sa.SmallInteger, nullable=False),
            sa.Column("left_def", sa.SmallInteger, nullable=False),
            sa.Column("right_att", sa.SmallInteger, nullable=False),
            sa.Column("central_att", sa.SmallInteger, nullable=False),
            sa.Column("left_att", sa.SmallInteger, nullable=False),
            sa.Column("tactic_type", sa.SmallInteger, nullable=False),
            sa.Column("tactic_skill", sa.SmallInteger, nullable=False),
            sa.Column("possession_first_half", sa.SmallInteger, nullable=False),
            sa.Column("possession_second_half", sa.SmallInteger, nullable=False),
        )

    if "standings" not in existentes:
        op.create_table(
            "standings",
            sa.Column("id", PK, primary_key=True, autoincrement=True),
            sa.Column("sync_id", sa.BigInteger, sa.ForeignKey("syncs.id"), nullable=False),
            sa.Column("series_ht_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("season", sa.SmallInteger, nullable=False),
            sa.Column("match_round", sa.SmallInteger, nullable=False),
            sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("team_ht_id", sa.BigInteger, nullable=False, index=True),
            sa.Column("team_name", sa.String(128), nullable=False),
            sa.Column("position", sa.SmallInteger, nullable=False),
            sa.Column("played", sa.SmallInteger, nullable=False),
            sa.Column("won", sa.SmallInteger, nullable=False),
            sa.Column("draws", sa.SmallInteger, nullable=False),
            sa.Column("lost", sa.SmallInteger, nullable=False),
            sa.Column("goals_for", sa.SmallInteger, nullable=False),
            sa.Column("goals_against", sa.SmallInteger, nullable=False),
            sa.Column("points", sa.SmallInteger, nullable=False),
        )
        op.create_index(
            "ix_standings_series_round",
            "standings",
            ["series_ht_id", "season", "match_round"],
        )

    if "stadium_history" not in existentes:
        op.create_table(
            "stadium_history",
            sa.Column("id", PK, primary_key=True, autoincrement=True),
            sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"),
                      nullable=False, index=True),
            sa.Column("ht_match_id", sa.BigInteger, nullable=False, unique=True),
            sa.Column("played_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("match_type", sa.SmallInteger, nullable=False),
            sa.Column("weather", sa.SmallInteger, nullable=False),
            sa.Column("capacity_total", sa.Integer, nullable=False),
            sa.Column("sold_terraces", sa.Integer, nullable=False),
            sa.Column("sold_basic", sa.Integer, nullable=False),
            sa.Column("sold_roof", sa.Integer, nullable=False),
            sa.Column("sold_vip", sa.Integer, nullable=False),
            sa.Column("revenue", sa.Integer, nullable=False),
        )

    if "former_youth_players" not in existentes:
        op.create_table(
            "former_youth_players",
            sa.Column("id", PK, primary_key=True, autoincrement=True),
            sa.Column("team_id", sa.BigInteger, sa.ForeignKey("teams.id"),
                      nullable=False, index=True),
            sa.Column("ht_player_id", sa.BigInteger, nullable=False, unique=True, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("promoted_at", sa.DateTime(timezone=True)),
            sa.Column("sold_at", sa.DateTime(timezone=True)),
            sa.Column("sold_for", sa.Integer),
            sa.Column("current_team_name", sa.String(128)),
            sa.Column("current_tsi", sa.Integer),
            sa.Column("refreshed_at", sa.DateTime(timezone=True)),
        )


def downgrade() -> None:
    for tabla in (
        "former_youth_players", "stadium_history", "standings",
        "match_ratings", "matches",
    ):
        op.drop_table(tabla)
