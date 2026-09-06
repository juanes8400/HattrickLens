"""Simula lo que queda de liga con el modelo de zonas mezclado con la Poisson.

Es el ensayo de lo que hará la pantalla de Liga, en la terminal y con los datos
reales del usuario, para poder mirar el resultado antes de cablear nada.

CÓMO CONSIGUE LOS RATINGS. La aplicación guarda los ratings de los partidos
PROPIOS, y de la serie sólo tiene el calendario y los marcadores. Así que los
de los rivales se piden en vivo, uno por partido jugado de la serie, igual que
hace la ficha de rival. No se guardan: son de cuentas ajenas.

QUÉ HACE CON ELLOS. La mediana de cada equipo en sus nueve duelos, los enfrenta
con los del rival de cada partido pendiente, y la terna que sale se mezcla con
la que da la Poisson del simulador de temporada. De ahí salen dos cosas: los
puntos esperados de cada equipo, y la distribución de puestos sorteando las
jornadas que faltan diez mil veces.

Uso:  python scripts/simular_liga.py [--vueltas 10000]
"""

import argparse
import asyncio
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def _ratings_de_la_serie(
    client: Any, session: Any, jugados: list[Any], propio: int
) -> dict[int, list[dict[str, float]]]:
    """Una lectura por partido y equipo, del más viejo al más reciente."""
    from app.application.commands.sync_team import FILE_VERSIONS
    from app.infrastructure.db import models as m

    guardados = {
        (r.ht_match_id, r.team_ht_id): r
        for r in (
            await session.execute(
                select(m.MatchRating).where(
                    m.MatchRating.ht_match_id.in_([p.ht_match_id for p in jugados])
                )
            )
        ).scalars()
    }
    lecturas: dict[int, list[dict[str, float]]] = defaultdict(list)
    pedidos = 0
    for p in jugados:
        for equipo in (p.home_team_ht_id, p.away_team_ht_id):
            fila = guardados.get((p.ht_match_id, equipo))
            if fila is None:
                continue
            lecturas[equipo].append(
                {
                    "midfield": fila.midfield,
                    "left_def": fila.left_def,
                    "central_def": fila.central_def,
                    "right_def": fila.right_def,
                    "left_att": fila.left_att,
                    "central_att": fila.central_att,
                    "right_att": fila.right_att,
                    "sp_def": fila.set_pieces_def,
                    "sp_att": fila.set_pieces_att,
                }
            )
        if all((p.ht_match_id, e) in guardados for e in (p.home_team_ht_id, p.away_team_ht_id)):
            continue
        d = await client.fetch("matchdetails", FILE_VERSIONS["matchdetails"], matchID=p.ht_match_id)
        pedidos += 1
        for lado in ("home", "away"):
            bloque = d.get(lado) or {}
            equipo = bloque.get("team_id")
            if equipo is None or (p.ht_match_id, equipo) in guardados:
                continue
            r = bloque.get("ratings") or {}
            if not r.get("midfield"):
                continue
            lecturas[equipo].append({k: float(r.get(DEL_LECTOR[k]) or 0) for k in CAMPOS_LECTURA})
    print(f"  {pedidos} partidos pedidos en vivo · {len(guardados)} lecturas ya guardadas")
    _ = propio
    return lecturas


CAMPOS_LECTURA = (
    "midfield",
    "left_def",
    "central_def",
    "right_def",
    "left_att",
    "central_att",
    "right_att",
    "sp_def",
    "sp_att",
)

#: Cómo se llama cada uno en lo que devuelve el lector de partidos. Siete
#: coinciden y los dos de Balón Parado no, que es donde estuvo el fallo: la
#: primera versión de este guion los pedía con el nombre corto, no encontraba
#: nada y guardaba cero. Un cero ahí no es un rating bajo, es no saber, y la
#: proporción lo convertía en 0,000 --afirmar que el rival gana ese duelo
#: entero-- en vez de en el 0,5 neutro que corresponde.
DEL_LECTOR = dict.fromkeys(CAMPOS_LECTURA) | {
    **{c: c for c in CAMPOS_LECTURA},
    "sp_def": "set_pieces_def",
    "sp_att": "set_pieces_att",
}


async def main(vueltas: int) -> None:
    import numpy as np

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        COMPARACIONES,
        ETIQUETAS,
        medianas_de_lecturas,
        probabilidades_de_partido,
        proporcion,
        tabla_de_puntos_esperados,
    )
    from app.domain.engines.season_simulator import (
        Fixture,
        TeamRecord,
        forecast_match,
        simulate,
    )
    from app.infrastructure.chpp.client import CHPPClient
    from app.infrastructure.db import models as m
    from app.infrastructure.security.tokens import decrypt_token

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        equipo = await session.scalar(select(m.Team).limit(1))
        serie = await session.scalar(
            select(m.Match.series_ht_id).where(m.Match.series_ht_id.is_not(None)).limit(1)
        )
        partidos = list(
            (
                await session.execute(
                    select(m.Match)
                    .where(m.Match.series_ht_id == serie)
                    .order_by(m.Match.match_round)
                )
            ).scalars()
        )
        token = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.status == "active"))
        if token is None:
            raise SystemExit("No hay un token CHPP activo")

        jugados = [p for p in partidos if (p.status or "").upper() == "FINISHED"]
        pendientes = [p for p in partidos if (p.status or "").upper() != "FINISHED"]
        nombres: dict[int, str] = {}
        for p in partidos:
            nombres.setdefault(p.home_team_ht_id, p.home_team_name or str(p.home_team_ht_id))
            nombres.setdefault(p.away_team_ht_id, p.away_team_name or str(p.away_team_ht_id))
        print(f"Serie {serie}: {len(jugados)} jugados, {len(pendientes)} por jugar\n")

        client = CHPPClient(
            decrypt_token(token.oauth_token_enc), decrypt_token(token.oauth_secret_enc)
        )
        try:
            lecturas = await _ratings_de_la_serie(client, session, jugados, equipo.ht_team_id)
        finally:
            await client.aclose()

    # ── La clasificación de hoy ──────────────────────────────────────────
    acumulado: dict[int, dict[str, int]] = defaultdict(
        lambda: {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0, "pts": 0}
    )
    for p in jugados:
        for yo, tu, mios, tuyos in (
            (p.home_team_ht_id, p.away_team_ht_id, p.home_goals, p.away_goals),
            (p.away_team_ht_id, p.home_team_ht_id, p.away_goals, p.home_goals),
        ):
            a = acumulado[yo]
            a["pj"] += 1
            a["gf"] += mios or 0
            a["gc"] += tuyos or 0
            if (mios or 0) > (tuyos or 0):
                a["g"] += 1
                a["pts"] += 3
            elif mios == tuyos:
                a["e"] += 1
                a["pts"] += 1
            else:
                a["p"] += 1
            _ = tu
    registros = [
        TeamRecord(
            ht_team_id=t,
            name=nombres.get(t, str(t)),
            played=a["pj"],
            won=a["g"],
            drawn=a["e"],
            lost=a["p"],
            goals_for=a["gf"],
            goals_against=a["gc"],
            points=a["pts"],
        )
        for t, a in acumulado.items()
    ]
    por_id = {r.ht_team_id: r for r in registros}

    # ── Las medianas ─────────────────────────────────────────────────────
    print("\nMEDIANA DE CADA EQUIPO (nueve duelos, de sus partidos de esta liga)")
    print(f"  {'equipo':26}{'n':>3}" + "".join(f"{c[:7]:>9}" for c in CAMPOS_LECTURA))
    medianas_por_equipo: dict[int, dict[str, float]] = {}
    for r in sorted(registros, key=lambda x: -x.points):
        med = medianas_de_lecturas(lecturas.get(r.ht_team_id, []))
        if med is None:
            print(f"  {r.name[:26]:26}  0   sin partidos vistos")
            continue
        medianas_por_equipo[r.ht_team_id] = med
        print(
            f"  {r.name[:26]:26}{int(med['_partidos']):>3}"
            + "".join(f"{med[c]:>9.1f}" for c in CAMPOS_LECTURA)
        )

    # ── El próximo partido propio, duelo a duelo ─────────────────────────
    mio = next(
        (p for p in pendientes if equipo.ht_team_id in (p.home_team_ht_id, p.away_team_ht_id)),
        None,
    )
    if mio is not None:
        local, visita = mio.home_team_ht_id, mio.away_team_ht_id
        ml, mv = medianas_por_equipo.get(local), medianas_por_equipo.get(visita)
        print(f"\nPRÓXIMO PARTIDO — jornada {mio.match_round}")
        print(f"  {nombres[local]} contra {nombres[visita]}")
        if ml and mv:
            print(f"\n  {'duelo':26}{'local':>8}{'visita':>8}{'A/(A+B)':>10}")
            for nombre, a, b in COMPARACIONES:
                print(
                    f"  {ETIQUETAS[nombre]:26}{ml[a]:>8.1f}{mv[b]:>8.1f}"
                    f"{proporcion(ml[a], mv[b]):>10.3f}"
                )
            fc = forecast_match(por_id[local], por_id[visita], registros, mio.match_round or 0)
            from app.domain.engines.prediccion import Probabilidades

            po = Probabilidades.normalizada(fc.home_win, fc.draw, fc.away_win)
            solo = probabilidades_de_partido(
                lecturas[local], lecturas[visita]
            )
            mezcla = probabilidades_de_partido(lecturas[local], lecturas[visita], poisson=po)
            print(f"\n  {'':22}{'victoria':>10}{'empate':>9}{'derrota':>9}   (desde el local)")
            for nom, p in (("sólo zonas", solo), ("sólo Poisson", po), ("mezcla 90/10", mezcla)):
                print(f"  {nom:22}{p.victoria:>10.1%}{p.empate:>9.1%}{p.derrota:>9.1%}")
            print(f"\n  puntos esperados del local: {mezcla.puntos_esperados:.2f} de 3")

    # ── Todos los pendientes ─────────────────────────────────────────────
    from app.domain.engines.prediccion import Probabilidades

    ternas: dict[tuple[int, int], tuple[float, float, float]] = {}
    triples = []
    for p in pendientes:
        casa, fuera = p.home_team_ht_id, p.away_team_ht_id
        if casa not in medianas_por_equipo or fuera not in medianas_por_equipo:
            continue
        fc = forecast_match(por_id[casa], por_id[fuera], registros, p.match_round or 0)
        mezcla = probabilidades_de_partido(
            lecturas[casa],
            lecturas[fuera],
            poisson=Probabilidades.normalizada(fc.home_win, fc.draw, fc.away_win),
        )
        if mezcla is None:
            continue
        ternas[(casa, fuera)] = (mezcla.victoria, mezcla.empate, mezcla.derrota)
        triples.append((casa, fuera, mezcla))

    esperados = tabla_de_puntos_esperados(triples)
    print(f"\nPUNTOS ESPERADOS de los {len(triples)} partidos que faltan")
    print(f"  {'equipo':26}{'hoy':>6}{'suma':>8}{'final':>8}")
    for t, extra in sorted(esperados.items(), key=lambda kv: -(por_id[kv[0]].points + kv[1])):
        final = por_id[t].points + extra
        print(f"  {nombres[t][:26]:26}{por_id[t].points:>6}{extra:>8.1f}{final:>8.1f}")

    # ── La distribución de puestos, con y sin el modelo nuevo ────────────
    calendario = [
        Fixture(p.home_team_ht_id, p.away_team_ht_id, p.match_round or 0) for p in pendientes
    ]
    print(f"\nPROBABILIDAD DE ACABAR CAMPEÓN ({vueltas} temporadas simuladas)")
    print(f"  {'equipo':26}{'sólo Poisson':>15}{'mezcla 90/10':>15}")
    solo_poisson = simulate(registros, calendario, runs=vueltas)
    con_zonas = simulate(registros, calendario, runs=vueltas, probabilidades=ternas)
    a_id = {o.ht_team_id: o for o in solo_poisson.teams}
    b_id = {o.ht_team_id: o for o in con_zonas.teams}
    for t in sorted(a_id, key=lambda x: -b_id[x].title_probability):
        print(
            f"  {nombres[t][:26]:26}{a_id[t].title_probability:>15.1%}"
            f"{b_id[t].title_probability:>15.1%}"
        )
    _ = np


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--vueltas", type=int, default=10000)
    a = p.parse_args()
    asyncio.run(main(a.vueltas))
