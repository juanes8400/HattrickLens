"""Clasificaciones propias: cada una con sus grupos.

2026-11-18, decidido por el usuario: además de las clasificaciones de la app
(Titularidad, Rentabilidad deportiva, Etapa de carrera), las suyas propias
--«Mercado» con Vender / Mantener / Duda, «Rol» con Capitán / Lanzador--.
Dentro de cada una un jugador está en un solo grupo, como en las de la app;
en dos clasificaciones distintas puede estar en un grupo de cada una.

LO QUE HABÍA (0115). Grupos sueltos y la pertenencia como columna del
jugador, `players.player_group_id`: un solo grupo en total.

LO QUE HAY.
- `player_classifications`: la clasificación, con su nombre.
- `player_groups.classification_id`: a cuál pertenece cada grupo.
- `player_group_members`: quién está en qué grupo, una fila por jugador y
  clasificación (único: lo imposible no se puede guardar).

LOS GRUPOS DE HOY NO SE PIERDEN. Cada equipo con grupos estrena una
clasificación «Mis grupos», sus grupos pasan a ella y cada jugador sigue en
el suyo. Después se quita `players.player_group_id`.

Revision ID: 0116
Revises: 0115
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from app.infrastructure.db.models import UtcDateTime

revision = "0116"
down_revision = "0115"
branch_labels = None
depends_on = None


def _pk() -> sa.Column:
    # La misma variante que `PKBigInt`: con `BIGINT PRIMARY KEY` a secas SQLite
    # no autoincrementa (ver la 0111).
    return sa.Column(
        "id",
        sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )


def upgrade() -> None:
    op.create_table(
        "player_classifications",
        _pk(),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("created_at", UtcDateTime(), nullable=False),
    )
    op.create_index("ix_player_classifications_team_id", "player_classifications", ["team_id"])
    with op.batch_alter_table("player_groups") as batch_op:
        batch_op.add_column(sa.Column("classification_id", sa.BigInteger(), nullable=True))
        batch_op.create_index("ix_player_groups_classification_id", ["classification_id"])
    op.create_table(
        "player_group_members",
        _pk(),
        sa.Column(
            "team_id",
            sa.BigInteger(),
            sa.ForeignKey("teams.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ht_player_id", sa.BigInteger(), nullable=False),
        sa.Column("classification_id", sa.BigInteger(), nullable=False),
        sa.Column("group_id", sa.BigInteger(), nullable=False),
        sa.UniqueConstraint(
            "team_id", "ht_player_id", "classification_id", name="uq_un_grupo_por_clasificacion"
        ),
    )
    op.create_index("ix_player_group_members_team_id", "player_group_members", ["team_id"])

    # Los grupos de hoy, a una clasificación «Mis grupos» por equipo.
    con = op.get_bind()
    ahora = datetime.now(UTC)
    equipos = [
        r[0] for r in con.execute(sa.text("SELECT DISTINCT team_id FROM player_groups")).fetchall()
    ]
    for team_id in equipos:
        con.execute(
            sa.text(
                "INSERT INTO player_classifications (team_id, name, created_at) "
                "VALUES (:t, 'Mis grupos', :c)"
            ),
            {"t": team_id, "c": ahora},
        )
        cid = con.execute(
            sa.text("SELECT MAX(id) FROM player_classifications WHERE team_id = :t"),
            {"t": team_id},
        ).scalar_one()
        con.execute(
            sa.text("UPDATE player_groups SET classification_id = :c WHERE team_id = :t"),
            {"c": cid, "t": team_id},
        )
    con.execute(
        sa.text(
            "INSERT INTO player_group_members (team_id, ht_player_id, classification_id, group_id) "
            "SELECT p.team_id, p.ht_player_id, g.classification_id, g.id "
            "FROM players p JOIN player_groups g "
            "ON g.id = p.player_group_id AND g.team_id = p.team_id "
            "WHERE p.player_group_id IS NOT NULL"
        )
    )

    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_index("ix_players_player_group_id")
        batch_op.drop_column("player_group_id")


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(sa.Column("player_group_id", sa.BigInteger(), nullable=True))
        batch_op.create_index("ix_players_player_group_id", ["player_group_id"])
    # De vuelta, cada jugador conserva el grupo de su primera clasificación.
    con = op.get_bind()
    filas = con.execute(
        sa.text(
            "SELECT team_id, ht_player_id, MIN(group_id) FROM player_group_members "
            "GROUP BY team_id, ht_player_id"
        )
    ).fetchall()
    for team_id, ht_player_id, group_id in filas:
        con.execute(
            sa.text(
                "UPDATE players SET player_group_id = :g WHERE team_id = :t AND ht_player_id = :p"
            ),
            {"g": group_id, "t": team_id, "p": ht_player_id},
        )
    op.drop_index("ix_player_group_members_team_id", table_name="player_group_members")
    op.drop_table("player_group_members")
    with op.batch_alter_table("player_groups") as batch_op:
        batch_op.drop_index("ix_player_groups_classification_id")
        batch_op.drop_column("classification_id")
    op.drop_index("ix_player_classifications_team_id", table_name="player_classifications")
    op.drop_table("player_classifications")
