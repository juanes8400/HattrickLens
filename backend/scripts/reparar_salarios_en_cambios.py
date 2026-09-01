"""Repara las frases de salario que se escribieron sin convertir la moneda.

Hasta el 2026-09-01, `diff_player_skills` escribía el salario con el número
crudo de Hattrick en vez de dividirlo por la tasa del país. Como esa frase se
CONGELA en la fila del cambio cuando se sincroniza, arreglar el origen no toca
lo que ya quedó escrito: en Colombia esas filas dicen un salario diez veces
mayor del real, y lo seguirán diciendo.

Esto las reescribe. Es idempotente por construcción: sólo toca las filas cuya
frase NO lleva el nombre de la moneda al final, que es justo la marca que
dejan las filas nuevas. Correrlo dos veces no divide dos veces.

Uso (primero en la copia local, luego --si se quiere-- en la de producción):

    python scripts/reparar_salarios_en_cambios.py            # enseña, no toca
    python scripts/reparar_salarios_en_cambios.py --aplicar  # escribe

`DATABASE_URL` manda; por omisión, `sqlite+aiosqlite:///dev.db`.
"""

import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

#: `Nombre: Salario 1.234 -> 5.678`, con el número tal como lo escribe
#: `thousands()`. El final sin moneda es lo que delata a una fila vieja.
PATRON = re.compile(r"^(?P<quien>.+): Salario (?P<antes>[\d.]+) -> (?P<despues>[\d.]+)$")


def _numero(texto: str) -> int:
    return int(texto.replace(".", ""))


async def main() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.domain.engines.sync_diff import thousands
    from app.infrastructure.db import models as m

    aplicar = "--aplicar" in sys.argv
    url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///dev.db")
    engine = create_async_engine(url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as s:
        tasas = {
            t.id: ((t.currency_rate or 1.0), t.currency_name or "")
            for t in (await s.execute(select(m.Team))).scalars()
        }
        filas = (
            (
                await s.execute(
                    select(m.SyncChange).where(m.SyncChange.summary.like("%: Salario %"))
                )
            )
            .scalars()
            .all()
        )

        tocadas = 0
        for fila in filas:
            coincide = PATRON.match(fila.summary)
            if not coincide:
                continue  # ya lleva moneda: está convertida
            tasa, moneda = tasas.get(fila.team_id, (1.0, ""))
            if tasa in (0, 1.0):
                continue  # nada que convertir en esos países
            antes = round(_numero(coincide["antes"]) / tasa)
            despues = round(_numero(coincide["despues"]) / tasa)
            nueva = (
                f"{coincide['quien']}: Salario {thousands(antes)} -> {thousands(despues)} {moneda}"
            ).rstrip()
            # Sin caracteres fuera de ASCII en la salida: la consola de Windows
            # va en cp1252 y una flecha bonita tumbaba el script antes de tocar
            # nada.
            print(f"  antes: {fila.summary}")
            print(f"  ahora: {nueva}\n")
            if aplicar:
                fila.summary = nueva
                if fila.detail_json:
                    detalle = json.loads(fila.detail_json)
                    detalle["before"], detalle["after"] = antes, despues
                    detalle["currency"] = moneda
                    fila.detail_json = json.dumps(detalle, ensure_ascii=False)
            tocadas += 1

        if aplicar:
            await s.commit()
        print(f"{tocadas} fila(s) {'reescritas' if aplicar else 'por reescribir (nada tocado)'}")

    await engine.dispose()


asyncio.run(main())
