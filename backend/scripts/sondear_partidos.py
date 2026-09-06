"""¿Sirve bajar de uno en uno desde un MatchID conocido?

Sonda del 2026-09-05, antes de montar el recolector de 500 partidos para el
modelo de predicción. La idea del usuario es coger un identificador cualquiera
e iterar hacia atrás. Antes de gastar 500 llamadas hay que saber tres cosas
que sólo se contestan preguntando de verdad:

1. ¿Se puede pedir un partido que NO jugó el usuario?
2. Si se puede, ¿vienen los ratings por zona, o Hattrick los oculta?
3. ¿Qué proporción de identificadores cae en partidos que no sirven --torneos,
   amistosos, juveniles-- o directamente no existen?

No escribe nada en la base: sólo mira y cuenta. Uso:

    python scripts/sondear_partidos.py 770453129 --cuantos 5
"""

import argparse
import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

#: Los tipos que sirven para el modelo: liga, calificación, copa y amistosos.
#: Torneos, escaleras y duelos quedan fuera --se juegan con otras reglas y con
#: suplentes-- igual que ya hace el motor de economía.
TIPOS_UTILES = {1: "liga", 2: "calificación", 3: "copa", 4: "amistoso", 5: "amistoso"}


async def main(desde: int, cuantos: int) -> None:
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

    client = CHPPClient(
        decrypt_token(token.oauth_token_enc),
        decrypt_token(token.oauth_secret_enc),
    )

    utiles = 0
    print(f"Sondeando {cuantos} identificadores hacia atrás desde {desde}\n")
    try:
        for i in range(cuantos):
            mid = desde - i
            try:
                # La MISMA versión que usa la aplicación, no «latest».
                #
                # Pedir «latest» devuelve la 1.5, que trae 49 etiquetas frente
                # a las 79 de la 3.1: sin balón parado, sin ocasiones por
                # zona, sin formación, sin lesiones y sin la venta por sector
                # del estadio. Y pedir una versión inexistente --3.2, 4.0--
                # tampoco falla: cae en silencio a la 1.5. Comprobado en vivo
                # el 2026-09-05, con esta sonda pidiendo mal y dando ceros.
                d: dict[str, Any] = await client.fetch(
                    "matchdetails",
                    FILE_VERSIONS["matchdetails"],
                    matchID=mid,
                    sourceSystem="hattrick",
                )
            except Exception as e:  # noqa: BLE001 — la sonda informa, no falla
                print(f"  {mid}  ✗ {type(e).__name__}: {str(e)[:70]}")
                continue

            if d.get("chpp_error"):
                print(f"  {mid}  ✗ {str(d['chpp_error'])[:70]}")
                continue

            tipo = d.get("match_type")
            local = (d.get("home") or {}).get("ratings") or {}
            visitante = (d.get("away") or {}).get("ratings") or {}
            hay_ratings = bool(local.get("midfield")) and bool(visitante.get("midfield"))
            nombre = TIPOS_UTILES.get(tipo, f"otro ({tipo})")
            marca = "✓" if (hay_ratings and tipo in TIPOS_UTILES) else "·"
            if marca == "✓":
                utiles += 1
            print(
                f"  {mid}  {marca} {nombre:14} "
                f"{(d.get('home') or {}).get('name', '?')[:18]:18} "
                f"{(d.get('home') or {}).get('goals', '?')}-"
                f"{(d.get('away') or {}).get('goals', '?')} "
                f"{(d.get('away') or {}).get('name', '?')[:18]:18} "
                f"| medio {local.get('midfield', '—')}/{visitante.get('midfield', '—')}"
                f" | bp {local.get('set_pieces_def', '—')}/{visitante.get('set_pieces_def', '—')}"
            )
    finally:
        await client.aclose()

    print(f"\nUtilizables: {utiles} de {cuantos}")
    if utiles:
        falta = round(500 * cuantos / utiles)
        print(f"A este ritmo, para 500 útiles harían falta ~{falta} llamadas.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("desde", type=int, help="MatchID desde el que bajar")
    p.add_argument("--cuantos", type=int, default=5)
    a = p.parse_args()
    asyncio.run(main(a.desde, a.cuantos))
