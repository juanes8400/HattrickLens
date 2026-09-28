"""Las migraciones corren en Postgres, no solo en el SQLite de desarrollo.

2026-08-25. El despliegue en Render reventó con:

    column "resale_closed" is of type boolean but expression is of type integer

La migracion 0066 hacia `SET resale_closed = 0` en SQL crudo. SQLite lo acepta
--no tiene tipo booleano, guarda 0 y 1-- asi que en local pasaba sin ruido; en
Postgres es un error duro. El fallo solo aparecia EN PRODUCCION, que es el
peor sitio posible para descubrirlo.

Escribiendo la sentencia con `sa.table(...)` y `.values(resale_closed=False)`
el literal lo pone el dialecto: `false` en Postgres, `0` en SQLite.
"""
import re
from pathlib import Path

from app.infrastructure.db import models as m

MIGRACIONES = Path(__file__).parent.parent / "migrations" / "versions"


def _columnas_booleanas() -> set[str]:
    nombres = set()
    for tabla in m.Base.metadata.tables.values():
        for col in tabla.columns:
            if col.type.__class__.__name__ == "Boolean":
                nombres.add(col.name)
    return nombres


def test_ninguna_migracion_asigna_0_o_1_a_un_booleano() -> None:
    booleanas = _columnas_booleanas()
    assert booleanas, "si no hay booleanas, esta prueba no esta comprobando nada"

    # `col = 0`, `col=1`, con o sin espacios. Solo en SQL de texto: en las
    # sentencias construidas con SQLAlchemy el literal lo elige el dialecto.
    patron = re.compile(
        r"\b(" + "|".join(sorted(booleanas)) + r")\s*=\s*[01]\b"
    )

    culpables = []
    for fichero in sorted(MIGRACIONES.glob("*.py")):
        texto = fichero.read_text(encoding="utf-8")
        # Fuera los comentarios: ahi se explica justamente este fallo.
        sin_comentarios = "\n".join(
            l for l in texto.splitlines() if not l.lstrip().startswith("#")
        )
        for encaje in patron.finditer(sin_comentarios):
            culpables.append(f"{fichero.name}: {encaje.group(0)}")

    assert not culpables, (
        "SQL crudo con 0/1 en una columna booleana; Postgres lo rechaza:\n  "
        + "\n  ".join(culpables)
        + "\nUsa sa.table(...).update().values(col=False) y deja que el "
          "dialecto escriba el literal."
    )


def test_ninguna_clave_primaria_autonumerada_es_biginteger_a_secas() -> None:
    """`BigInteger` en una clave primaria autonumerada no funciona en SQLite.

    2026-09-27. La migracion 0089 declaraba `sa.Column("id", sa.BigInteger(),
    primary_key=True, autoincrement=True)`. En Postgres eso es un `BIGSERIAL`
    y va bien; en SQLite solo `INTEGER PRIMARY KEY` es alias de rowid, asi que
    un `BIGINT PRIMARY KEY` no se autonumera y cada INSERT muere con "NOT NULL
    constraint failed". El modelo ya lo tenia resuelto con `PKBigInt`
    (`BigInteger().with_variant(Integer(), "sqlite")`), pero la migracion es
    la que construye la tabla de verdad y se le habia escapado.

    Costo una sesion entera de depuracion porque el INSERT estaba dentro de un
    `try/except` que se lo callaba: la pantalla salia perfecta y la tabla
    seguia vacia.
    """
    patron = re.compile(
        r'Column\(\s*"[^"]*"\s*,\s*sa\.BigInteger\(\)[^)]*primary_key\s*=\s*True',
        re.S,
    )
    culpables = []
    for fichero in sorted(MIGRACIONES.glob("*.py")):
        texto = fichero.read_text(encoding="utf-8")
        sin_comentarios = "\n".join(
            l for l in texto.splitlines() if not l.lstrip().startswith("#")
        )
        if patron.search(sin_comentarios):
            culpables.append(fichero.name)

    assert not culpables, (
        "clave primaria autonumerada declarada como sa.BigInteger(); en SQLite "
        "no se autonumera y todo INSERT falla:\n  " + "\n  ".join(culpables)
        + "\nUsa PKBigInt, que es BigInteger en Postgres e Integer en SQLite."
    )
