"""Las fechas de una migración se declaran CON zona, como la columna real.

2026-09-01, reventó en producción y sólo allí:

    UPDATE player_stints SET games_computed_at=$2::TIMESTAMP WITHOUT TIME ZONE
    invalid input for query argument $2: datetime(..., tzinfo=utc)
    (can't subtract offset-naive and offset-aware datetimes)

Una migración de datos declara sus tablas a mano con `sa.table()`. Si una
columna de fecha se pone como `sa.DateTime` a secas cuando la columna de
verdad es `TIMESTAMP WITH TIME ZONE`, SQLAlchemy convierte el parámetro al
tipo declarado y asyncpg rechaza el valor con zona que acaba de leer de esa
misma columna.

En sqlite no se ve: devuelve fechas sin zona y todo encaja. Es decir, la
suite local puede estar entera en verde y el despliegue caerse igual — el
mismo motivo por el que las claves primarias de otra migración pasaron y
reventaron al primer INSERT real.

De ahí que esto sea una comprobación ESTÁTICA sobre el texto de los ficheros:
no hace falta un Postgres para hacerla, y así corre en cualquier sitio.
"""

from __future__ import annotations

import re
from pathlib import Path

VERSIONES = Path(__file__).resolve().parents[1] / "migrations" / "versions"

#: `sa.column("lo_que_sea", sa.DateTime)` — sin `timezone=True` detrás.
SIN_ZONA = re.compile(r'sa\.column\(\s*"([^"]+)"\s*,\s*sa\.DateTime\s*\)')


def test_ninguna_migracion_declara_una_fecha_sin_zona() -> None:
    culpables: list[str] = []
    for fichero in sorted(VERSIONES.glob("*.py")):
        texto = fichero.read_text(encoding="utf-8")
        for columna in SIN_ZONA.findall(texto):
            culpables.append(f"{fichero.name} → {columna}")

    assert not culpables, (
        "Estas columnas de fecha se declaran sin zona en un `sa.table()` de "
        "migración. Si la columna real es `timestamptz` --y en este esquema "
        "todas lo son-- asyncpg rechazará el valor en Postgres aunque sqlite "
        "lo acepte:\n  " + "\n  ".join(culpables)
    )


def test_el_regreso_del_fallo_se_detecta() -> None:
    """El test de arriba sólo vale si de verdad reconoce el patrón malo."""
    malo = 'sa.column("games_computed_at", sa.DateTime)'
    bueno = 'sa.column("games_computed_at", sa.DateTime(timezone=True))'
    assert SIN_ZONA.findall(malo) == ["games_computed_at"]
    assert SIN_ZONA.findall(bueno) == []
