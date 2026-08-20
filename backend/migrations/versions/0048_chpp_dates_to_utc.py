"""2026-08-16: las fechas que vienen de CHPP estaban guardadas en hora sueca
etiquetada como UTC.

El sync hacía `.replace(tzinfo=UTC)` sobre la cadena de CHPP, que no convierte
nada: sólo le pega una etiqueta falsa. El partido de Copa del miércoles 19 a
las 17:10 hora de Colombia estaba guardado como 2026-08-20 00:10 — siete horas
de más, que es CEST menos la hora colombiana.

Esta migración reinterpreta cada fecha YA GUARDADA como hora sueca y la
convierte a UTC de verdad. Sólo toca columnas cuyo valor venga de CHPP; las
marcas de tiempo propias (`captured_at`, `started_at`, `dismissed_at`…) ya se
escriben con `datetime.now(UTC)` y son correctas — desplazarlas sería
estropearlas.

El desplazamiento NO es constante: +1 en invierno y +2 en verano, así que se
resuelve fila a fila con la base de datos de zonas horarias y no con un
`INTERVAL` fijo.

Revision ID: 0048
"""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

HATTRICK_TZ = ZoneInfo("Europe/Stockholm")

# (tabla, columna) cuyo contenido lo dicta CHPP, no nosotros.
CHPP_DATE_COLUMNS: list[tuple[str, str]] = [
    ("matches", "played_at"),
    ("player_snapshots", "last_match_played_at"),
    ("players", "purchased_at"),
    ("players", "sold_at"),
    ("previous_club_bonuses", "resale_deadline"),
    ("world_context", "training_date"),
    ("world_context", "cup_match_date"),
    ("world_context", "series_match_date"),
    ("teams", "youth_academy_created_at"),
]


def _shift(connection, table: str, column: str, to_utc: bool) -> None:
    inspector = sa.inspect(connection)
    if table not in inspector.get_table_names():
        return
    if column not in {col["name"] for col in inspector.get_columns(table)}:
        return

    rows = connection.execute(
        sa.text(f"SELECT id, {column} AS value FROM {table} WHERE {column} IS NOT NULL")  # noqa: S608
    ).fetchall()
    for row in rows:
        raw = row.value
        current = raw if isinstance(raw, datetime) else datetime.fromisoformat(str(raw))
        if to_utc:
            # Lo guardado era hora sueca disfrazada de UTC.
            fixed = current.replace(tzinfo=HATTRICK_TZ).astimezone(UTC)
        else:
            # Vuelta atrás: de UTC real a la hora sueca que había antes.
            fixed = current.replace(tzinfo=UTC).astimezone(HATTRICK_TZ)
        connection.execute(
            sa.text(f"UPDATE {table} SET {column} = :value WHERE id = :id"),  # noqa: S608
            {"value": fixed.replace(tzinfo=None), "id": row.id},
        )


def upgrade() -> None:
    connection = op.get_bind()
    for table, column in CHPP_DATE_COLUMNS:
        _shift(connection, table, column, to_utc=True)


def downgrade() -> None:
    connection = op.get_bind()
    for table, column in CHPP_DATE_COLUMNS:
        _shift(connection, table, column, to_utc=False)
