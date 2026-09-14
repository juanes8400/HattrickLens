"""La última jornada jugada, predicha SIN haberla visto.

POR QUÉ ESTE ENSAYO. Los 5.232 partidos del ajuste son de otras ligas y de
otros niveles. Antes de cambiar el motor conviene verlo trabajar sobre la
serie real del usuario, con sus ocho equipos y sus números, en una jornada
cuyo resultado ya se conoce pero que el modelo no puede haber visto.

LA REGLA, y es la que hace que el ensayo signifique algo: la mediana de cada
equipo se calcula SÓLO con sus partidos ANTERIORES a la jornada que se
predice. Nada de medianas con la jornada dentro. Con siete jornadas jugadas,
predecir la séptima deja seis partidos por equipo, que es justo lo que habría
habido el sábado por la noche.

QUÉ COMPARA:
  · el motor de hoy, ordinal A/(A+B) 75% + Poisson A/(A+B) 25%
  · el motor propuesto, ordinal A/(A+B) 50% + Poisson log(A/(A+B)) 50%

Los coeficientes de la Poisson propuesta salen del ajuste sobre los mismos
5.232 partidos; los de la ordinal son los que ya lleva el motor.

Uso:  python scripts/ensayo_jornada.py [jornada]
"""

import asyncio
import sys

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

#: Poisson con los duelos en `log(A/(A+B))`, ajustada el 2026-09-07 sobre los
#: 5.232 partidos de liga. Es la propuesta, todavía no está en el motor.
NUEVO_INTERCEPTO = 4.10285
NUEVO_BETA = (1.71953, 0.65013, 0.60862, 0.58072, 1.03141)
NUEVO_PESO_GOLES = 0.50


def log_proporcion(a: float, b: float) -> float:
    t = a + b
    return float(np.log(a / t)) if t > 0 and a > 0 else float(np.log(1.0 / (t + 1.0)))


async def main(jornada: int | None) -> None:
    from app.application.commands.sync_team import FILE_VERSIONS
    from app.application.queries.prediccion_liga import DEL_LECTOR
    from app.core.config import settings
    from app.domain.engines.prediccion import (
        CAMPOS,
        DUELOS_OFENSIVOS,
        PESO_GOLES,
        PESO_ORDINAL,
        Probabilidades,
        _reparto_de_goles,
        marcador_mas_probable,
        modelo_ajustado,
        probabilidades_poisson,
        proporcion,
        variables,
    )
    from app.infrastructure.chpp.client import CHPPClient
    from app.infrastructure.db import models as m
    from app.infrastructure.security.tokens import decrypt_token

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        equipo = (await session.execute(select(m.Team))).scalars().first()
        serie = equipo.series_ht_id
        jugados = list(
            (
                await session.execute(
                    select(m.Match)
                    .where(
                        m.Match.series_ht_id == serie,
                        m.Match.match_type == 1,
                        m.Match.status.ilike("finished"),
                    )
                    .order_by(m.Match.played_at)
                )
            ).scalars()
        )
        nombres = {
            s.team_ht_id: s.team_name
            for s in (await session.execute(select(m.Standing))).scalars()
        }
        propios = {
            (r.ht_match_id, r.team_ht_id): r
            for r in (await session.execute(select(m.MatchRating))).scalars()
        }
        token = await session.scalar(select(m.CHPPToken).where(m.CHPPToken.status == "active"))

    rondas = sorted({p.match_round for p in jugados if p.match_round})
    #: Sin jornada, se ensayan TODAS las que tengan historia detrás. Cuatro
    #: partidos no deciden nada; veinticuatro tampoco deciden, pero ya se ven.
    objetivos = [jornada] if jornada else [r for r in rondas if r > 1]
    print(f"Serie {serie} · jornadas ensayadas: {objetivos}")

    cliente = CHPPClient(
        decrypt_token(token.oauth_token_enc), decrypt_token(token.oauth_secret_enc)
    )
    lecturas: dict[int, list[tuple[int, dict[str, float]]]] = {}
    try:
        for p in jugados:
            faltan = [
                t
                for t in (p.home_team_ht_id, p.away_team_ht_id)
                if (p.ht_match_id, t) not in propios
            ]
            for t in (p.home_team_ht_id, p.away_team_ht_id):
                fila = propios.get((p.ht_match_id, t))
                if fila is not None:
                    lecturas.setdefault(t, []).append(
                        (p.match_round or 0, {
                            "midfield": float(fila.midfield or 0),
                            "left_def": float(fila.left_def or 0),
                            "central_def": float(fila.central_def or 0),
                            "right_def": float(fila.right_def or 0),
                            "left_att": float(fila.left_att or 0),
                            "central_att": float(fila.central_att or 0),
                            "right_att": float(fila.right_att or 0),
                            "sp_def": float(fila.set_pieces_def or 0),
                            "sp_att": float(fila.set_pieces_att or 0),
                        })
                    )
            if not faltan:
                continue
            d = await cliente.fetch(
                "matchdetails", FILE_VERSIONS["matchdetails"], matchID=p.ht_match_id
            )
            for lado in ("home", "away"):
                bloque = d.get(lado) or {}
                quien = bloque.get("team_id")
                if quien not in faltan:
                    continue
                r = bloque.get("ratings") or {}
                if not r.get("midfield"):
                    continue
                lecturas.setdefault(int(quien), []).append(
                    (p.match_round or 0, {c: float(r.get(DEL_LECTOR[c]) or 0) for c in CAMPOS})
                )
    finally:
        await cliente.aclose()

    def medianas_hasta(ronda):
        """Cada equipo con lo suyo ANTERIOR a `ronda`, nunca con la jornada
        dentro: es lo que habría habido el sábado por la noche."""
        out = {}
        for t, ls in lecturas.items():
            previas = [x for r, x in ls if r < ronda]
            if previas:
                out[t] = {c: float(np.median([x[c] for x in previas])) for c in CAMPOS}
        return out

    ultima = medianas_hasta(objetivos[-1])
    print(f"\nMEDIANAS ANTES DE LA JORNADA {objetivos[-1]}")
    print(f"  {'equipo':28}" + "".join(f"{c[:8]:>9}" for c in CAMPOS))
    for t, mm in sorted(ultima.items(), key=lambda kv: -kv[1]["midfield"]):
        print(f"  {nombres.get(t, str(t))[:27]:28}" + "".join(f"{mm[c]:>9.1f}" for c in CAMPOS))

    def poisson_nueva(mio, suyo):
        def lam(a, b):
            x = [log_proporcion(a[k], b[j]) for _, k, j in DUELOS_OFENSIVOS]
            return min(float(np.exp(NUEVO_INTERCEPTO + np.dot(NUEVO_BETA, x))), 12.0)

        rej = np.outer(_reparto_de_goles(lam(mio, suyo)), _reparto_de_goles(lam(suyo, mio)))
        v, e, d = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
        t = v + e + d
        return Probabilidades(v / t, e / t, d / t), lam(mio, suyo), lam(suyo, mio)

    print("\n" + "=" * 100)
    print("LO QUE CADA MOTOR HABRIA DICHO, jornada a jornada, sin haberla visto")
    print("=" * 100)
    aciertos = {"hoy": 0, "nuevo": 0}
    perdida = {"hoy": [], "nuevo": []}
    err_goles = {"hoy": [], "nuevo": []}
    for objetivo in objetivos:
      med = medianas_hasta(objetivo)
      print(f"\n  ── jornada {objetivo} ──")
      for p in [q for q in jugados if q.match_round == objetivo]:
        loc, vis = p.home_team_ht_id, p.away_team_ht_id
        if loc not in med or vis not in med:
            print(f"    sin historia para {nombres.get(loc)} o {nombres.get(vis)}")
            continue
        mio, suyo = med[loc], med[vis]
        ordinal = modelo_ajustado().probabilidades(variables(mio, suyo))
        pois_hoy = probabilidades_poisson(mio, suyo)
        hoy = Probabilidades(
            PESO_ORDINAL * ordinal.victoria + PESO_GOLES * pois_hoy.victoria,
            PESO_ORDINAL * ordinal.empate + PESO_GOLES * pois_hoy.empate,
            PESO_ORDINAL * ordinal.derrota + PESO_GOLES * pois_hoy.derrota,
        )
        pois_new, lam_l, lam_v = poisson_nueva(mio, suyo)
        nuevo = Probabilidades(
            (1 - NUEVO_PESO_GOLES) * ordinal.victoria + NUEVO_PESO_GOLES * pois_new.victoria,
            (1 - NUEVO_PESO_GOLES) * ordinal.empate + NUEVO_PESO_GOLES * pois_new.empate,
            (1 - NUEVO_PESO_GOLES) * ordinal.derrota + NUEVO_PESO_GOLES * pois_new.derrota,
        )
        gh, gv = p.home_goals, p.away_goals
        real = 2 if gh > gv else (1 if gh == gv else 0)
        mh, mv = marcador_mas_probable(mio, suyo)
        lam_hoy_l = float(
            np.exp(
                -3.63063
                + np.dot(
                    (3.01537, 1.38636, 1.31952, 1.34806, 1.85908),
                    [proporcion(mio[a], suyo[b]) for _, a, b in DUELOS_OFENSIVOS],
                )
            )
        )
        lam_hoy_v = float(
            np.exp(
                -3.63063
                + np.dot(
                    (3.01537, 1.38636, 1.31952, 1.34806, 1.85908),
                    [proporcion(suyo[a], mio[b]) for _, a, b in DUELOS_OFENSIVOS],
                )
            )
        )
        rej = np.outer(_reparto_de_goles(lam_l), _reparto_de_goles(lam_v))
        nh, nv = np.unravel_index(int(rej.argmax()), rej.shape)

        print(f"\n  {nombres.get(loc, loc)} {gh}-{gv} {nombres.get(vis, vis)}   (lo que pasó)")
        print(f"    {'motor':10}{'V':>8}{'E':>8}{'D':>8}{'goles':>14}{'marcador':>11}")
        for etiqueta, pr, gl_, gv_, mk in (
            ("hoy", hoy, lam_hoy_l, lam_hoy_v, (mh, mv)),
            ("nuevo", nuevo, lam_l, lam_v, (int(nh), int(nv))),
        ):
            terna = [pr.derrota, pr.empate, pr.victoria]
            aciertos[etiqueta] += int(int(np.argmax(terna)) == real)
            perdida[etiqueta].append(-np.log(max(terna[real], 1e-12)))
            err_goles[etiqueta] += [abs(gl_ - gh), abs(gv_ - gv)]
            print(
                f"    {etiqueta:10}{pr.victoria:>8.1%}{pr.empate:>8.1%}{pr.derrota:>8.1%}"
                f"{f'{gl_:.2f}-{gv_:.2f}':>14}{f'{mk[0]}-{mk[1]}':>11}"
            )

    print("\n" + "=" * 100)
    print("RESUMEN DE LA JORNADA")
    print("=" * 100)
    print(f"  {'motor':10}{'aciertos':>10}{'log-loss':>10}{'error de goles':>17}")
    for etiqueta in ("hoy", "nuevo"):
        if not perdida[etiqueta]:
            continue
        print(
            f"  {etiqueta:10}{aciertos[etiqueta]:>7}/{len(perdida[etiqueta])}"
            f"{float(np.mean(perdida[etiqueta])):>10.4f}"
            f"{float(np.mean(err_goles[etiqueta])):>17.4f}"
        )
    print(
        "\n  Cuatro partidos no deciden nada --con tan poco, el orden puede\n"
        "  cambiar por un solo resultado--. Esto es para VER el motor sobre\n"
        "  datos propios, no para elegir con ello."
    )


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else None))
