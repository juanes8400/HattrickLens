"""Las migraciones tienen que poder construir el esquema desde cero.

Escrito el 2026-08-19, tras el primer despliegue real. Cinco tablas
(`matches`, `match_ratings`, `standings`, `stadium_history`,
`former_youth_players`) vivían solo en el modelo: nacieron de un `create_all`
en la base de desarrollo y ninguna migración las creaba. Con la base de
desarrollo delante eso no se nota jamás; contra una base vacía, `alembic
upgrade head` se para en seco, que es exactamente lo que pasó al desplegar.

No se puede comprobar ejecutando la cadena en sqlite (0001 crea una tabla
particionada, que es de Postgres), así que se comprueba leyendo las
migraciones: toda tabla del modelo tiene que aparecer en un `create_table`.
"""
import ast
import pathlib

from app.infrastructure.db import models as m

VERSIONES = pathlib.Path(__file__).resolve().parents[1] / "migrations" / "versions"


def _tablas_creadas_por_migraciones() -> set[str]:
    creadas: set[str] = set()
    for fichero in VERSIONES.glob("*.py"):
        texto = fichero.read_text(encoding="utf-8")
        for nodo in ast.walk(ast.parse(texto)):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "create_table"
                and nodo.args
                and isinstance(nodo.args[0], ast.Constant)
            ):
                creadas.add(nodo.args[0].value)
        # Las que se crean con SQL a pelo (la particionada de 0001).
        for linea in texto.splitlines():
            if "CREATE TABLE" in linea.upper():
                resto = linea.upper().split("CREATE TABLE")[1].split()
                if resto:
                    creadas.add(resto[0].strip('"').lower())
    return creadas


def test_every_model_table_has_a_migration_that_creates_it() -> None:
    faltan = sorted(set(m.Base.metadata.tables) - _tablas_creadas_por_migraciones())
    assert faltan == [], (
        "estas tablas existen en el modelo pero ninguna migración las crea, "
        "así que un despliegue nuevo se para al llegar a la primera que las "
        "toque:\n  " + "\n  ".join(faltan)
    )


def test_no_migration_sends_several_statements_in_one_execute() -> None:
    """Postgres no admite varias sentencias dentro de una preparada, y asyncpg
    manda cada SQL así: "cannot insert multiple commands into a prepared
    statement". En sqlite el mismo bloque pasa, de modo que solo aparece al
    migrar de verdad contra Postgres — al desplegar, tarde.
    """
    malos = []
    for fichero in sorted(VERSIONES.glob("*.py")):
        for nodo in ast.walk(ast.parse(fichero.read_text(encoding="utf-8"))):
            if (
                isinstance(nodo, ast.Call)
                and isinstance(nodo.func, ast.Attribute)
                and nodo.func.attr == "execute"
                and nodo.args
                and isinstance(nodo.args[0], ast.Constant)
                and isinstance(nodo.args[0].value, str)
            ):
                sin_comentarios = "\n".join(
                    linea.split("--")[0] for linea in nodo.args[0].value.splitlines()
                )
                if len([t for t in sin_comentarios.split(";") if t.strip()]) > 1:
                    malos.append(f"{fichero.name}:{nodo.lineno}")
    assert malos == [], "una sentencia por execute; estos llevan varias:\n  " + "\n  ".join(malos)
