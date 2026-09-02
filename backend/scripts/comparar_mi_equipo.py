"""Lo mismo que `comparar_bases.py`, pero acotado a UN equipo.

La comparación global engaña cuando producción es multiusuario: allí hay 15
equipos y 12 personas, así que «producción tiene más filas» puede convenir con
«producción tiene menos de las TUYAS». Lo que decide qué hay que mover es lo
segundo.

SÓLO LEE.

Uso:
    python scripts/comparar_mi_equipo.py
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

from scripts.comparar_bases import _cargar_url, _dsn  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
LOCAL = RAIZ / "dev.db"

#: Cómo se llega desde cada tabla hasta el equipo. `directa` = tiene team_id;
#: el resto pasa por la tabla que se indica.
POR_EQUIPO: dict[str, str] = {
    "syncs": "directa",
    "players": "directa",
    "player_snapshots": "por_jugador",
    "player_stints": "por_jugador",
    "youth_players": "directa",
    "youth_snapshots": "por_juvenil",
    "youth_scouts": "directa",
    "former_youth_players": "directa",
    "economy_snapshots": "directa",
    "staff_snapshots": "directa",
    "training_snapshots": "directa",
    "sync_changes": "directa",
    "stadium_history": "directa",
    "standings": "directa",
    "player_listing_attempts": "directa",
    "dismissed_insights": "directa",
}

CONSULTAS = {
    "directa": 'select count(*) from "{t}" where team_id = {eq}',
    "por_jugador": (
        'select count(*) from "{t}" x join players p on p.id = x.player_id where p.team_id = {eq}'
    ),
    "por_juvenil": (
        'select count(*) from "{t}" x join youth_players y on y.id = x.youth_player_id '
        "where y.team_id = {eq}"
    ),
}

HT_TEAM_ID = 537758


def _local_equipo() -> dict[str, int]:
    con = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
    eq = con.execute("select id from teams where ht_team_id = ?", (HT_TEAM_ID,)).fetchone()
    if not eq:
        raise SystemExit(f"el equipo {HT_TEAM_ID} no está en la base local")
    salida = {}
    for tabla, forma in POR_EQUIPO.items():
        try:
            sql = CONSULTAS[forma].format(t=tabla, eq=eq[0])
            salida[tabla] = con.execute(sql).fetchone()[0]
        except sqlite3.OperationalError as exc:
            salida[tabla] = -1
            print(f"  (local) {tabla}: {exc}")
    con.close()
    return salida


async def _remoto_equipo(url: str) -> dict[str, int]:
    import asyncpg

    con = await asyncpg.connect(_dsn(url), ssl="require")
    try:
        eq = await con.fetchval("select id from teams where ht_team_id = $1", HT_TEAM_ID)
        if eq is None:
            raise SystemExit(f"el equipo {HT_TEAM_ID} no está en producción")
        print(f"tu equipo es la fila {eq} en producción\n")
        salida = {}
        for tabla, forma in POR_EQUIPO.items():
            try:
                salida[tabla] = await con.fetchval(CONSULTAS[forma].format(t=tabla, eq=eq))
            except Exception as exc:  # noqa: BLE001
                salida[tabla] = -1
                print(f"  (producción) {tabla}: {exc}")
        return salida
    finally:
        await con.close()


async def main() -> None:
    url = _cargar_url()
    rem = await _remoto_equipo(url)
    loc = _local_equipo()

    print(f"{'tabla':<26} {'local':>7} {'producción':>11}   diferencia")
    print("-" * 62)
    total_a_mover = 0
    for tabla in POR_EQUIPO:
        ln, rn = loc[tabla], rem[tabla]
        falta = ln - rn
        marca = ""
        if falta > 0:
            marca = f"  faltan ~{falta} en producción"
            total_a_mover += falta
        elif falta < 0:
            marca = "  producción va por delante"
        print(f"{tabla:<26} {ln:>7} {rn:>11}   {marca}")
    print()
    print(f"Filas que local tiene de más, sumando: {total_a_mover}")


asyncio.run(main())
