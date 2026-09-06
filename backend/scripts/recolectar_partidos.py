"""Recoge partidos ajenos para entrenar el modelo de predicción.

Se ejecuta UNA vez y se refresca como mucho una vez al año. No es una descarga
por temporizador: la lanza el autor a mano.

CÓMO ENCUENTRA LOS PARTIDOS. Bajando de uno en uno desde un MatchID conocido.
Medido el 2026-09-05: 20 identificadores consecutivos dieron 20 partidos de
liga de la MISMA serie --ocho equipos, cinco jornadas-- porque Hattrick los
asigna en bloque al generar el calendario.

Eso es justo lo que el modelo necesita. Sus variables no salen del partido
sino de la HISTORIA previa de cada equipo, así que hacen falta partidos
anteriores de los mismos equipos; dentro de un bloque consecutivo vienen
gratis, y con muestreo disperso costarían miles de llamadas.

POR QUÉ VARIOS BLOQUES Y NO UNO LARGO. 500 seguidos son nueve temporadas de
ocho equipos de la misma división: mucha historia y ningún contraste. Cinco
bloques de 100 en series distintas dan cuarenta equipos de niveles distintos
por el mismo precio.

Uso:

    python scripts/recolectar_partidos.py 770453129 --cuantos 5            # en seco
    python scripts/recolectar_partidos.py 770453129 --cuantos 100 --aplicar
    python scripts/recolectar_partidos.py 770453129 812345678 --cuantos 100 --aplicar
"""

import argparse
import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

#: El marcador con el que Hattrick registra una no comparecencia. Hay 5-0
#: legítimos --y se pierden unos pocos al descartarlos-- pero un partido que
#: nadie jugó tiene ratings que no corresponden a lo que pasó en el campo, y
#: eso envenena justo lo que el modelo intenta aprender. Mejor perder algunos
#: buenos que colar los malos (decisión del usuario, 2026-09-05).
INCOMPARECENCIA = ((5, 0), (0, 5))

#: Liga, promoción y copa. Un torneo o un amistoso se juegan con suplentes y no
#: dicen nada de la fuerza del equipo — el mismo criterio que ya usa el motor
#: de economía para decidir qué partido deja taquilla.
TIPOS_OFICIALES = (1, 2, 3)

RATINGS = (
    "midfield",
    "left_def",
    "central_def",
    "right_def",
    "left_att",
    "central_att",
    "right_att",
)


def _fecha(d: dict[str, Any]) -> datetime | None:
    """Cuándo se jugó. La clave es `match_date`, NO `played_at`.

    Aquí estuvo el fallo: el recolector pedía `played_at`, que no existe en lo
    que devuelve el lector de partidos, y guardó 1.031 filas con la fecha
    vacía. No reventó nada porque el orden por identificador funciona igual
    --los identificadores de Hattrick crecen con el tiempo-- pero sin fecha no
    se puede separar por temporada ni cortar por el presente.
    """
    crudo = d.get("match_date") or ""
    for formato in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(crudo, formato)
        except ValueError:
            continue
    return None


def _fila(mid: int, d: dict[str, Any], ahora: datetime) -> dict[str, Any] | None:
    """La fila plana de un partido, o `None` si no sirve para entrenar."""
    if d.get("chpp_error") or d.get("match_type") not in TIPOS_OFICIALES:
        return None
    fecha = _fecha(d)
    # Un partido por jugar viene 0-0 con todos los ratings a cero, así que el
    # filtro de ratings ya lo caza. La fecha es el segundo cerrojo: si algún
    # día Hattrick devolviera ratings de un partido futuro, aquí se para.
    if fecha is not None and fecha > ahora:
        return None
    marcador = ((d.get("home") or {}).get("goals"), (d.get("away") or {}).get("goals"))
    if marcador in INCOMPARECENCIA:
        return None
    lados = {}
    for lado in ("home", "away"):
        e = d.get(lado) or {}
        r = e.get("ratings") or {}
        # Sin ratings de AMBOS lados la fila no vale: el modelo compara uno
        # contra otro, y media comparación no es media observación, es ninguna.
        if not r.get("midfield"):
            return None
        lados[lado] = (e, r)

    fila: dict[str, Any] = {
        "ht_match_id": mid,
        "match_type": d.get("match_type"),
        "played_at": fecha,
        "collected_at": ahora,
    }
    for lado, (e, r) in lados.items():
        fila[f"{lado}_team_id"] = e.get("team_id") or 0
        fila[f"{lado}_goals"] = e.get("goals") or 0
        for k in RATINGS:
            fila[f"{lado}_{k}"] = r.get(k) or 0
        # `or 0` y no `.get(k, 0)`: la 1.5 de matchdetails no trae balón
        # parado y devolvería `None`. Aquí no puede llegar --se pide la 3.1--
        # pero si alguien cambia la versión, un 0 se ve y un None revienta.
        fila[f"{lado}_sp_def"] = r.get("set_pieces_def") or 0
        fila[f"{lado}_sp_att"] = r.get("set_pieces_att") or 0
        fila[f"{lado}_tactic_type"] = e.get("tactic_type") or 0
        fila[f"{lado}_tactic_skill"] = e.get("tactic_skill") or 0
    return fila


async def main(desdes: list[int], cuantos: int, aplicar: bool) -> None:
    from app.application.commands.sync_team import FILE_VERSIONS
    from app.core.config import settings
    from app.infrastructure.chpp.client import CHPPClient
    from app.infrastructure.db import models as m
    from app.infrastructure.security.tokens import decrypt_token

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        token = await session.scalar(
            select(m.CHPPToken).where(m.CHPPToken.status == "active")
        )
        if token is None:
            raise SystemExit("No hay un token CHPP activo")
        # Reanudable: lo ya recogido no se vuelve a pedir. Si la recogida se
        # corta a mitad --y con 500 llamadas se corta-- volver a lanzarla sigue
        # donde iba en vez de gastar la cuota otra vez.
        ya = set((await session.execute(select(m.TrainingMatch.ht_match_id))).scalars())

    client = CHPPClient(
        decrypt_token(token.oauth_token_enc), decrypt_token(token.oauth_secret_enc)
    )
    ahora = datetime.now(UTC).replace(tzinfo=None)
    nuevas: list[dict[str, Any]] = []
    saltados = descartados = fallos = 0

    try:
        for desde in desdes:
            print(f"\nBloque desde {desde}, {cuantos} identificadores")
            for i in range(cuantos):
                mid = desde - i
                if mid in ya:
                    saltados += 1
                    continue
                try:
                    d = await client.fetch(
                        "matchdetails",
                        FILE_VERSIONS["matchdetails"],
                        matchID=mid,
                        sourceSystem="hattrick",
                    )
                except Exception as e:  # noqa: BLE001 — una caída no tira la recogida
                    fallos += 1
                    print(f"  {mid}  ✗ {type(e).__name__}")
                    continue
                fila = _fila(mid, d, ahora)
                if fila is None:
                    descartados += 1
                    continue
                nuevas.append(fila)
                if len(nuevas) % 25 == 0:
                    print(f"  … {len(nuevas)} recogidos")
    finally:
        await client.aclose()

    print(
        f"\nRecogidos {len(nuevas)} · ya estaban {saltados} · "
        f"descartados {descartados} · fallos {fallos}"
    )
    if not aplicar:
        print("EN SECO. Añade --aplicar para guardarlos.")
        return
    async with factory() as session:
        session.add_all([m.TrainingMatch(**f) for f in nuevas])
        await session.commit()
        total = await session.scalar(
            select(m.TrainingMatch.id).order_by(m.TrainingMatch.id.desc()).limit(1)
        )
    print(f"Guardados. La tabla tiene ahora {total} filas.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("desde", type=int, nargs="+", help="MatchID(s) desde los que bajar")
    p.add_argument("--cuantos", type=int, default=100)
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    asyncio.run(main(a.desde, a.cuantos, a.aplicar))
