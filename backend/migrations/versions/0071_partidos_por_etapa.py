"""Reparar el censo de partidos jugados por etapa.

Desde 0057 el saldo se presenta por player_stints, pero el censo siguio
guardando su resultado en la fila legada de players. La ficha individual
tenia el numero y Transferencias mostraba "?". En la base real, Jose Vicente
Alvargonzalez tenia exactamente esa divergencia: Player=1, PlayerStint=NULL.

Solo se copia automaticamente cuando el jugador tiene UNA etapa: ahi el dato
legado tiene un destino inequivoco. Quien tuvo varias vueltas debe recontarse
por las fechas de cada una; el nuevo censo de aplicacion lo deja en cola.

Tambien se limpian marcas legadas que decian "calculado" sin contener numero.
No se convierten en cero: ausencia de evidencia sigue siendo desconocida.

Revision ID: 0071
Revises: 0070
"""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

# OJO CON `timezone=True`. Las columnas de fecha de estas dos tablas son
# `TIMESTAMP WITH TIME ZONE` de verdad (creadas asi en 0043 y 0057). Si aqui
# se declaran como `sa.DateTime` a secas, SQLAlchemy convierte el parametro a
# `TIMESTAMP WITHOUT TIME ZONE` y asyncpg rechaza el valor CON zona que acaba
# de leer de esa misma columna:
#
#     invalid input for query argument $2: datetime(..., tzinfo=utc)
#     (can't subtract offset-naive and offset-aware datetimes)
#
# En sqlite no pasaba: devuelve fechas sin zona, asi que todo encajaba. Se vio
# en produccion el 2026-09-01, que es el unico sitio donde hay Postgres.
players = sa.table(
    "players",
    sa.column("id", sa.BigInteger),
    sa.column("games_played_for_us", sa.SmallInteger),
    sa.column("games_played_for_us_computed_at", sa.DateTime(timezone=True)),
)
stints = sa.table(
    "player_stints",
    sa.column("id", sa.BigInteger),
    sa.column("player_id", sa.BigInteger),
    sa.column("left_at", sa.DateTime(timezone=True)),
    sa.column("games_played_for_us", sa.SmallInteger),
    sa.column("games_computed_at", sa.DateTime(timezone=True)),
)


def _con_zona(valor: datetime | None) -> datetime | None:
    """La misma fecha, siempre CON zona.

    El valor sale de la base y llega distinto segun el motor: Postgres lo da
    con zona y sqlite sin ella. Escribirlo en una columna `timestamptz` exige
    que la tenga, asi que se le pone UTC cuando falta -- que es lo que ya era,
    porque toda fecha guardada aqui es UTC.
    """
    if valor is None:
        return None
    return valor if valor.tzinfo is not None else valor.replace(tzinfo=UTC)


def upgrade() -> None:
    bind = op.get_bind()
    other = stints.alias("other_stints")
    stint_count = (
        sa.select(sa.func.count(other.c.id))
        .where(other.c.player_id == players.c.id)
        .scalar_subquery()
    )
    rows = list(
        bind.execute(
            sa.select(
                stints.c.id,
                players.c.games_played_for_us,
                players.c.games_played_for_us_computed_at,
            )
            .select_from(stints.join(players, players.c.id == stints.c.player_id))
            .where(
                stints.c.left_at.is_not(None),
                stints.c.games_played_for_us.is_(None),
                players.c.games_played_for_us.is_not(None),
                stint_count == 1,
            )
        ).mappings()
    )
    # Con zona: la columna es `timestamptz`. Antes se le quitaba con
    # `.replace(tzinfo=None)`, que era justo lo contrario de lo que hace falta.
    ahora = datetime.now(UTC)
    for row in rows:
        bind.execute(
            stints.update()
            .where(stints.c.id == row["id"])
            .values(
                games_played_for_us=row["games_played_for_us"],
                games_computed_at=_con_zona(row["games_played_for_us_computed_at"]) or ahora,
            )
        )

    # La marca sin numero fue producida por un intento fallido o una etapa
    # sin limites. No significa cero y ya no gobierna la cola nueva.
    bind.execute(
        players.update()
        .where(
            players.c.games_played_for_us.is_(None),
            players.c.games_played_for_us_computed_at.is_not(None),
        )
        .values(games_played_for_us_computed_at=None)
    )


def downgrade() -> None:
    # Irreversible a proposito: borrar conteos verdaderos restauraria el bug.
    pass
