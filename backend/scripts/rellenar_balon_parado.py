"""Rellena el Balón Parado de los partidos ya guardados.

POR QUÉ HACE FALTA. La migración 0083 añadió las dos columnas a
`match_ratings` pero no tocó lo que ya estaba, así que las filas viejas las
tienen vacías. Las sincronizaciones nuevas sí las guardan --el lector de
partidos ya las lee-- pero lo viejo no se rellena solo.

POR QUÉ IMPORTA. Son dos de las nueve variables del modelo de predicción, y
como los dos lados entran por mediana, faltando aquí faltan también para el
equipo propio. Sin ellas el modelo trabaja con siete duelos y los otros dos
entran neutros a 0,5, que no es un valor: es no saber.

Se ejecuta UNA vez, a mano. No es una descarga por temporizador.

Uso:
    python scripts/rellenar_balon_parado.py            # en seco
    python scripts/rellenar_balon_parado.py --aplicar
"""

import argparse
import asyncio

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def main(aplicar: bool) -> None:
    from app.application.commands.sync_team import FILE_VERSIONS
    from app.core.config import settings
    from app.infrastructure.chpp.client import CHPPClient
    from app.infrastructure.db import models as m
    from app.infrastructure.security.tokens import decrypt_token

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        token = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.status == "active"))
        if token is None:
            raise SystemExit("No hay un token CHPP activo")
        filas = list(
            (
                await session.execute(
                    select(m.MatchRating).where(
                        or_(
                            m.MatchRating.set_pieces_def.is_(None),
                            m.MatchRating.set_pieces_att.is_(None),
                        )
                    )
                )
            ).scalars()
        )

    # Una llamada por PARTIDO, no por fila: cada respuesta trae los dos lados.
    por_partido: dict[int, list[m.MatchRating]] = {}
    for f in filas:
        por_partido.setdefault(f.ht_match_id, []).append(f)
    print(f"{len(filas)} filas sin Balón Parado, en {len(por_partido)} partidos")
    if not por_partido:
        return

    client = CHPPClient(decrypt_token(token.oauth_token_enc), decrypt_token(token.oauth_secret_enc))
    rellenadas = sin_dato = fallos = 0
    cambios: dict[int, tuple[int, int]] = {}
    try:
        for i, (mid, suyas) in enumerate(por_partido.items(), 1):
            try:
                d = await client.fetch(
                    "matchdetails", FILE_VERSIONS["matchdetails"], matchID=mid
                )
            except Exception as e:  # noqa: BLE001 — una caída no tira el relleno
                fallos += 1
                print(f"  {mid}  x {type(e).__name__}")
                continue
            for lado in ("home", "away"):
                bloque = d.get(lado) or {}
                r = (bloque.get("ratings") or {}) if isinstance(bloque, dict) else {}
                equipo = bloque.get("team_id")
                for fila in suyas:
                    if fila.team_ht_id != equipo:
                        continue
                    bp_def, bp_att = r.get("set_pieces_def"), r.get("set_pieces_att")
                    if bp_def is None or bp_att is None:
                        sin_dato += 1
                        continue
                    cambios[fila.id] = (int(bp_def), int(bp_att))
                    rellenadas += 1
            if i % 25 == 0:
                print(f"  … {i} partidos pedidos, {rellenadas} filas listas")
    finally:
        await client.aclose()

    print(f"\nListas {rellenadas} · sin dato {sin_dato} · fallos {fallos}")
    if not aplicar:
        print("EN SECO. Añade --aplicar para guardarlas.")
        return
    async with factory() as session:
        for fila_id, (bp_def, bp_att) in cambios.items():
            fila = await session.get(m.MatchRating, fila_id)
            if fila is not None:
                fila.set_pieces_def = bp_def
                fila.set_pieces_att = bp_att
        await session.commit()
    print(f"Guardadas {len(cambios)} filas.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    asyncio.run(main(a.aplicar))
