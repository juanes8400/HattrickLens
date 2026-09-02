"""Qué hay en cada base, sin tocar ninguna.

Paso previo obligatorio de cualquier traspaso local -> producción: hasta no
saber qué tiene ya producción no se puede decidir qué mover, y mover de más es
peor que no mover -- duplica historial que no se puede volver a distinguir.

SÓLO LEE. No abre transacción de escritura en ninguna de las dos.

Uso:
    python scripts/comparar_bases.py

Lee la base local de `dev.db` y la remota de `DATABASE_URL` en `.env.neon`.
La cadena de conexión no se imprime nunca.
"""

# ruff: noqa: S608
# Los nombres de tabla se interpolan porque SQL no permite parametrizarlos, y
# salen de constantes escritas en este mismo fichero -- nunca de entrada
# externa. El aviso de inyección no aplica aquí.

import asyncio
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RAIZ = Path(__file__).resolve().parents[1]
LOCAL = RAIZ / "dev.db"

#: Cada tabla con la columna que marca CUÁNDO se capturó cada fila, para poder
#: comparar no sólo cuántas hay sino qué periodo cubren. `None` = no tiene.
TABLAS: dict[str, str | None] = {
    "users": None,
    "teams": None,
    "syncs": "started_at",
    "players": None,
    "player_snapshots": "captured_at",
    "player_stints": None,
    "youth_players": None,
    "youth_snapshots": "captured_at",
    "youth_scouts": None,
    "youth_scout_reports": None,
    "former_youth_players": None,
    "economy_snapshots": "captured_at",
    "staff_snapshots": "captured_at",
    "training_snapshots": "captured_at",
    "sync_changes": "created_at",
    "matches": "played_at",
    "match_ratings": None,
    "player_match_ratings": None,
    "match_weather": None,
    "standings": None,
    "stadium_history": "played_at",
    "team_transfers": "deadline",
    "previous_club_bonuses": None,
    "player_listing_attempts": None,
    "skill_ups": None,
    "dismissed_insights": None,
    "ui_events": "at",
    "world_context": None,
    "world_cups": None,
    "chpp_tokens": None,
}


def _cargar_url() -> str:
    ruta = RAIZ / ".env.neon"
    if not ruta.exists():
        raise SystemExit("falta backend/.env.neon con DATABASE_URL")
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("DATABASE_URL="):
            return linea.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("`.env.neon` no trae DATABASE_URL")


def _dsn(url: str) -> str:
    """La cadena en la forma que entiende el driver crudo.

    Se quitan DOS cosas: el prefijo `+asyncpg`, que es de SQLAlchemy, y la
    cadena de consulta entera. El valor guardado trae `?sslmode=req`
    --truncado; el válido es `require`-- y asyncpg lo rechaza antes de
    intentar conectarse. El TLS se pide aparte, con `ssl="require"`, que es lo
    que ese parámetro quería decir.
    """
    return url.replace("postgresql+asyncpg://", "postgresql://").split("?", 1)[0]


def _local() -> dict[str, tuple[int, str | None, str | None]]:
    con = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
    salida = {}
    for tabla, col in TABLAS.items():
        try:
            n = con.execute(f'select count(*) from "{tabla}"').fetchone()[0]
            if col and n:
                a, b = con.execute(f'select min({col}), max({col}) from "{tabla}"').fetchone()
            else:
                a = b = None
            salida[tabla] = (n, str(a)[:10] if a else None, str(b)[:10] if b else None)
        except sqlite3.OperationalError:
            salida[tabla] = (-1, None, None)
    con.close()
    return salida


async def _remoto(url: str) -> dict[str, tuple[int, str | None, str | None]]:
    import asyncpg

    con = await asyncpg.connect(_dsn(url), ssl="require")
    salida = {}
    try:
        for tabla, col in TABLAS.items():
            try:
                n = await con.fetchval(f'select count(*) from "{tabla}"')
                if col and n:
                    fila = await con.fetchrow(
                        f'select min({col}) as a, max({col}) as b from "{tabla}"'
                    )
                    a, b = fila["a"], fila["b"]
                else:
                    a = b = None
                salida[tabla] = (n, str(a)[:10] if a else None, str(b)[:10] if b else None)
            except Exception:
                salida[tabla] = (-1, None, None)
    finally:
        await con.close()
    return salida


async def main() -> None:
    url = _cargar_url()
    loc = _local()
    rem = await _remoto(url)

    cabecera = f"{'tabla':<26} {'local':>7} {'producción':>11}   "
    print(cabecera + "periodo local            periodo producción")
    print("-" * 108)
    solo_local = []
    for tabla in TABLAS:
        ln, la, lb = loc[tabla]
        rn, ra, rb = rem[tabla]
        marca = ""
        if ln > 0 and rn == 0:
            marca = "  <- sólo local"
            solo_local.append(tabla)
        elif ln > rn > 0:
            marca = "  <- local tiene más"
        elif rn > ln:
            marca = "  <- producción tiene más"
        per_l = f"{la} .. {lb}" if la else ""
        per_r = f"{ra} .. {rb}" if ra else ""
        print(f"{tabla:<26} {ln:>7} {rn:>11}   {per_l:<24} {per_r:<24}{marca}")

    print()
    print("Tablas vacías en producción y con datos en local:", len(solo_local))


# Sin esta guarda, importar el módulo para reutilizar `_dsn` volvía a correr la
# comparación entera contra producción -- y a imprimirla en medio de la salida
# de quien lo importaba (visto al estrenar el migrador, 2026-09-02).
if __name__ == "__main__":
    asyncio.run(main())
