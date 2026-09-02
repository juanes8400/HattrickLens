"""Lleva a producción el historial que sólo existe en la copia local.

QUÉ PROBLEMA RESUELVE. Hattrick publica el estado de HOY. El historial --una
fila por cada cambio real, semana a semana-- se construye sincronizando, y no
se puede volver a pedir. Esta instalación estuvo sincronizando en local desde
el 26 de julio y en producción desde el 20 de agosto, así que hay tres semanas
y media de fotos del club que existen en un fichero de un portátil y en ningún
otro sitio.

LA REGLA QUE GOBIERNA TODO. Sólo se importan filas ANTERIORES a la primera que
producción ya tiene, tabla por tabla. En el periodo que ambas cubren manda
producción y no se toca. Mezclar dos historiales del mismo club por las mismas
semanas no es restaurar: deja dos versiones de la misma semana capturadas en
momentos distintos, y rompe la regla de «una fila por cambio real» de la que
vive todo el módulo de Cambios.

Eso hace el guion IDEMPOTENTE por construcción: después de la primera pasada el
corte se mueve hacia atrás y la segunda no encuentra nada que traer.

LAS IDENTIDADES NO COINCIDEN. Los `id` de fila son de cada base. El
emparejamiento se hace siempre por el identificador de Hattrick --`ht_team_id`,
`ht_player_id`, `ht_youth_player_id`-- y las claves foráneas se reescriben al
vuelo con lo que devuelve cada inserción.

QUÉ NO SE MUEVE, a propósito:
  * `ui_events`: es la navegación de un portátil contra `localhost`. Llevarla
    ensuciaría las métricas de «quién usa qué», que es justo para lo que se
    hicieron.
  * `chpp_tokens`: producción tiene los suyos y están cifrados con otra llave.
  * `world_context` y `world_cups`: datos del mundo, idénticos en las dos.
  * `users` y `teams`: producción tiene doce personas y quince equipos. Aquí no
    se crea ninguno; si el equipo no está allí, el guion para.

CÓMO SE DESHACE. Sólo se INSERTA, nunca se actualiza ni se borra. Antes de
escribir se guarda el `max(id)` de cada tabla en `migracion-marcas.json`, y con
eso el deshacer es exacto: borrar lo que esté por encima de esa marca.

Uso:
    python scripts/migrar_local_a_produccion.py            # ensayo, no escribe
    python scripts/migrar_local_a_produccion.py --aplicar  # escribe
"""

# ruff: noqa: S608
# Los nombres de tabla se interpolan porque SQL no permite parametrizarlos, y
# salen de constantes escritas en este mismo fichero -- nunca de entrada
# externa. El aviso de inyección no aplica aquí.

import asyncio
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.comparar_bases import _cargar_url, _dsn  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
LOCAL = RAIZ / "dev.db"
MARCAS = RAIZ / "migracion-marcas.json"
HT_TEAM_ID = 537758

#: El plan, EN ORDEN DE DEPENDENCIA: nada se inserta antes que aquello a lo que
#: apunta. `tiempo` es la columna por la que se corta; `padre` dice de qué mapa
#: sale su clave foránea principal.
PLAN: list[dict] = [
    {"tabla": "syncs", "tiempo": "started_at", "ambito": "team_id"},
    {"tabla": "player_snapshots", "tiempo": "captured_at", "ambito": "player_id"},
    {"tabla": "youth_snapshots", "tiempo": "captured_at", "ambito": "youth_player_id"},
    {"tabla": "economy_snapshots", "tiempo": "captured_at", "ambito": "team_id"},
    {"tabla": "staff_snapshots", "tiempo": "captured_at", "ambito": "team_id"},
    {"tabla": "training_snapshots", "tiempo": "captured_at", "ambito": "team_id"},
    {"tabla": "sync_changes", "tiempo": "created_at", "ambito": "team_id"},
    # Las alertas archivadas no son historial sino algo que el usuario decidió.
    # No llevan corte por fecha: se traen las que no estén ya, por su huella.
    {
        "tabla": "dismissed_insights",
        "tiempo": None,
        "ambito": "team_id",
        "clave": ("key", "fingerprint"),
    },
]

#: Columnas que son claves foráneas y hay que reescribir con el mapa de su
#: tabla. El nombre manda: en este esquema no hay dos cosas distintas que se
#: llamen igual.
FORANEAS = {
    "team_id": "teams",
    "user_id": "users",
    "sync_id": "syncs",
    "player_id": "players",
    "youth_player_id": "youth_players",
}


def _dt(valor):
    """SQLite devuelve texto; Postgres quiere `datetime`.

    Todas las columnas de tiempo de estas tablas son `timestamp with time
    zone` --comprobado contra el esquema real de producción-- así que la marca
    viaja en UTC, que es como la escribe la aplicación.
    """
    if valor is None or isinstance(valor, datetime):
        return valor
    texto = str(valor).replace("T", " ").replace("Z", "")
    for formato in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto[:26], formato).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


class Migracion:
    def __init__(self, aplicar: bool) -> None:
        self.aplicar = aplicar
        self.loc = sqlite3.connect(f"file:{LOCAL}?mode=ro", uri=True)
        self.loc.row_factory = sqlite3.Row
        self.mapas: dict[str, dict[int, int]] = {}
        #: Contador de identificadores fingidos para el ensayo en seco.
        self.fingido = 0
        self.resumen: list[tuple[str, int, int, str]] = []

    # ── identidades ──────────────────────────────────────────────────────
    async def emparejar(self, con) -> None:
        """Los mapas local -> producción, por identificador de Hattrick."""
        eq_loc = self.loc.execute(
            "select id from teams where ht_team_id = ?", (HT_TEAM_ID,)
        ).fetchone()
        eq_rem = await con.fetchval("select id from teams where ht_team_id = $1", HT_TEAM_ID)
        if not eq_loc or eq_rem is None:
            raise SystemExit(f"el equipo {HT_TEAM_ID} tiene que existir en las dos bases")
        self.equipo_local, self.equipo_remoto = eq_loc[0], eq_rem
        self.mapas["teams"] = {eq_loc[0]: eq_rem}

        us_loc = self.loc.execute("select id, ht_user_id from users").fetchall()
        self.mapas["users"] = {}
        for fila in us_loc:
            remoto = await con.fetchval(
                "select id from users where ht_user_id = $1", fila["ht_user_id"]
            )
            if remoto is not None:
                self.mapas["users"][fila["id"]] = remoto

        for tabla, clave in (("players", "ht_player_id"), ("youth_players", "ht_youth_player_id")):
            mapa: dict[int, int] = {}
            for fila in self.loc.execute(
                f"select id, {clave} from {tabla} where team_id = ?", (self.equipo_local,)
            ):
                remoto = await con.fetchval(
                    f"select id from {tabla} where {clave} = $1", fila[clave]
                )
                if remoto is not None:
                    mapa[fila["id"]] = remoto
            self.mapas[tabla] = mapa
        self.mapas["syncs"] = {}

    # ── el corte ─────────────────────────────────────────────────────────
    async def corte(self, con, paso: dict):
        """La primera marca que producción ya tiene, para este equipo."""
        tabla, tiempo, ambito = paso["tabla"], paso["tiempo"], paso["ambito"]
        if tiempo is None:
            return None
        if ambito == "team_id":
            sql = f"select min({tiempo}) from {tabla} where team_id = $1"
        elif ambito == "player_id":
            sql = (
                f"select min(x.{tiempo}) from {tabla} x "
                "join players p on p.id = x.player_id where p.team_id = $1"
            )
        else:
            sql = (
                f"select min(x.{tiempo}) from {tabla} x "
                "join youth_players y on y.id = x.youth_player_id where y.team_id = $1"
            )
        return await con.fetchval(sql, self.equipo_remoto)

    def _filas_locales(self, paso: dict, corte):
        tabla, tiempo, ambito = paso["tabla"], paso["tiempo"], paso["ambito"]
        if ambito == "team_id":
            base = f"select * from {tabla} where team_id = {self.equipo_local}"
        elif ambito == "player_id":
            base = (
                f"select x.* from {tabla} x join players p on p.id = x.player_id "
                f"where p.team_id = {self.equipo_local}"
            )
        else:
            base = (
                f"select x.* from {tabla} x join youth_players y on y.id = x.youth_player_id "
                f"where y.team_id = {self.equipo_local}"
            )
        filas = [dict(f) for f in self.loc.execute(base)]
        if tiempo and corte is not None:
            limite = corte.replace(tzinfo=None) if corte.tzinfo else corte
            lejos = datetime.max.replace(tzinfo=UTC)

            def antes(f, col=tiempo, tope=limite, lejos=lejos):
                return (_dt(f[col]) or lejos).replace(tzinfo=None) < tope

            filas = [f for f in filas if antes(f)]
        if tiempo:
            filas.sort(key=lambda f: str(f[tiempo]))
        return filas

    # ── el traslado ──────────────────────────────────────────────────────
    @staticmethod
    def _valor(v, tipo: str, tope: int | None):
        """El valor tal como lo quiere Postgres.

        SQLite no tiene tipos de verdad: los booleanos vuelven como 0 y 1, las
        marcas de tiempo como texto, y en un `varchar(2000)` cabe lo que sea.
        Postgres sí los tiene y rechaza los tres. La conversión mira el TIPO DE
        LA COLUMNA DE DESTINO --leído del esquema real-- y no el nombre, que es
        lo que evita adivinar.

        El recorte por longitud salió al primer intento real: cuatro
        sincronizaciones locales guardaron un error de más de 2000 caracteres,
        y la fila entera reventaba. Se recorta con puntos suspensivos para que
        nadie lea un error cortado creyéndolo completo.
        """
        if v is None:
            return None
        if tipo == "boolean":
            return bool(v)
        if tipo.startswith("timestamp"):
            marca = _dt(v)
            # `timestamp without time zone` no admite marca con zona: es el
            # mismo choque que tumbó una migración en producción el 2026-08-31.
            if marca and tipo == "timestamp without time zone":
                return marca.replace(tzinfo=None)
            return marca
        if tope and isinstance(v, str) and len(v) > tope:
            return v[: tope - 1] + "…"
        return v

    async def mover(
        self, con, paso: dict, columnas_prod: dict[str, tuple[str, int | None]]
    ) -> None:
        tabla = paso["tabla"]
        corte = await self.corte(con, paso)
        filas = self._filas_locales(paso, corte)

        # Lo que ya está, para no repetirlo: por huella cuando la tabla la
        # tiene, y si no por el par que la identifica.
        ya_estan: set = set()
        if clave := paso.get("clave"):
            for f in await con.fetch(
                f"select {', '.join(clave)} from {tabla} where team_id = $1", self.equipo_remoto
            ):
                ya_estan.add(tuple(f[c] for c in clave))
            filas = [f for f in filas if tuple(f[c] for c in clave) not in ya_estan]

        cabeceras = filas[0].keys() if filas else []
        comunes = [c for c in cabeceras if c in columnas_prod and c != "id"]
        detalle = f"corte {str(corte)[:16]}" if corte else "sin corte"

        if not filas:
            self.resumen.append((tabla, 0, 0, f"{detalle} · nada que traer"))
            return

        insertadas, huerfanas = 0, 0
        for fila in filas:
            valores = []
            salta = False
            for col in comunes:
                v = fila[col]
                if col in FORANEAS and v is not None:
                    destino = self.mapas.get(FORANEAS[col], {})
                    if v not in destino:
                        # Su padre no está en producción: la fila se queda.
                        # Nunca se inventa un padre para colocar a un hijo.
                        salta = True
                        break
                    v = destino[v]
                else:
                    tipo, tope = columnas_prod[col]
                    v = self._valor(v, tipo, tope)
                valores.append(v)
            if salta:
                huerfanas += 1
                continue
            if self.aplicar:
                marcas = ", ".join(f"${i + 1}" for i in range(len(comunes)))
                nuevo = await con.fetchval(
                    f"insert into {tabla} ({', '.join(comunes)}) values ({marcas}) returning id",
                    *valores,
                )
            else:
                # En seco hay que FINGIR el identificador que asignaría
                # Postgres. Sin esto, `syncs` no se inserta, su mapa se queda
                # vacío y todas las tablas que cuelgan de él salen huérfanas:
                # el ensayo decía «0 filas» de todo y no probaba nada.
                self.fingido -= 1
                nuevo = self.fingido
            if tabla in self.mapas:
                self.mapas[tabla][fila["id"]] = nuevo
            insertadas += 1
        self.resumen.append((tabla, insertadas, huerfanas, detalle))


async def main() -> None:
    import asyncpg

    aplicar = "--aplicar" in sys.argv
    m = Migracion(aplicar)
    con = await asyncpg.connect(_dsn(_cargar_url()), ssl="require")
    try:
        await m.emparejar(con)
        print(
            f"equipo {HT_TEAM_ID}: fila {m.equipo_local} en local, {m.equipo_remoto} en producción"
        )
        print(f"jugadores emparejados: {len(m.mapas['players'])}")
        print(f"juveniles emparejados: {len(m.mapas['youth_players'])}\n")

        # La red de seguridad: sólo se inserta, así que deshacer es borrar por
        # encima de estas marcas.
        if aplicar:
            marcas = {}
            for paso in PLAN:
                marcas[paso["tabla"]] = await con.fetchval(
                    f"select coalesce(max(id), 0) from {paso['tabla']}"
                )
            MARCAS.write_text(json.dumps(marcas, indent=2), encoding="utf-8")
            print(f"marcas de vuelta atrás guardadas en {MARCAS.name}\n")

        # Una sola transacción para las ocho tablas: si la fila 900 falla por
        # un tipo, no puede quedar media migración dentro. Con esto el
        # deshacer de emergencia casi nunca hace falta, pero las marcas se
        # guardan igual.
        transaccion = con.transaction() if aplicar else None
        if transaccion:
            await transaccion.start()
        for paso in PLAN:
            cols = {
                r["column_name"]: (r["data_type"], r["character_maximum_length"])
                for r in await con.fetch(
                    "select column_name, data_type, character_maximum_length "
                    "from information_schema.columns where table_name=$1",
                    paso["tabla"],
                )
            }
            await m.mover(con, paso, cols)

        if transaccion:
            await transaccion.commit()

        print(f"{'tabla':<22} {'a traer':>8} {'huérfanas':>10}   detalle")
        print("-" * 74)
        total = 0
        for tabla, n, huer, det in m.resumen:
            total += n
            print(f"{tabla:<22} {n:>8} {huer:>10}   {det}")
        print()
        if aplicar:
            print(f"INSERTADAS {total} filas en producción.")
        else:
            print(f"ENSAYO: se insertarían {total} filas. Nada se ha escrito.")
            print("Para hacerlo de verdad: --aplicar")
    finally:
        await con.close()


asyncio.run(main())
