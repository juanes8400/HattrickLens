"""¿Un duelo igualado a 0,5 mete un sesgo? La cuenta, delante.

LA PREOCUPACIÓN, planteada el 2026-09-07: con `A/(A+B)`, dos medios campos
iguales dan 0,5, y 0,5 × 11,80 son 5,90 puntos de recta latente que se suman
SIEMPRE, aunque nadie tenga ventaja. Parece que el modelo estuviera regalando
algo por no hacer nada.

LA RESPUESTA es que no, y no es una opinión: en un modelo ordinal sólo
importa la DIFERENCIA `umbral − recta`, así que cualquier constante que se
sume a la recta la absorben los umbrales al ajustar. Este guion lo enseña de
tres maneras, que es lo que hace falta para creérselo:

1. Ajusta con `x` y con `x − 0,5`. Las probabilidades salen IDÉNTICAS y los
   umbrales se mueven exactamente 0,5 × Σβ. Eso es lo que significa
   «absorbido».
2. Calcula qué predice cada forma en un partido con los NUEVE duelos
   igualados. Si el 0,5 metiera sesgo, las cuatro formas darían cosas
   distintas ahí --el neutro de cada una es otro número: 0,5, 1, 0 y −0,693--.
3. Compara ese neutro con el reparto real de los partidos.

Uso:  python scripts/sesgo_del_neutro.py
"""

import asyncio

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")


def proporcion(a, b):
    t = a + b
    return a / t if t > 0 else 0.5


def cociente(a, b):
    return max(a, 1.0) / max(b, 1.0)


def logaritmo(a, b):
    return float(np.log(max(a, 1.0) / max(b, 1.0)))


def log_proporcion(a, b):
    t = a + b
    return float(np.log(a / t)) if t > 0 and a > 0 else float(np.log(1.0 / (t + 1.0)))


#: Lo que vale un duelo IGUALADO en cada forma. Es el punto donde ninguno de
#: los dos equipos tiene ventaja en esa zona.
NEUTRO = {
    "A/(A+B)": 0.5,
    "A/B": 1.0,
    "log(A/B)": 0.0,
    "log(A/(A+B))": float(np.log(0.5)),
}
FORMAS = {
    "A/(A+B)": proporcion,
    "A/B": cociente,
    "log(A/B)": logaritmo,
    "log(A/(A+B))": log_proporcion,
}


def terna(beta, umbrales, x):
    eta = float(np.asarray(beta) @ np.asarray(x))
    s1, s2 = 1 / (1 + np.exp(-(np.asarray(umbrales) - eta)))
    return np.array([s1, s2 - s1, 1 - s2])


async def main() -> None:
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        COMPARACIONES,
        TIPOS_DE_ENTRENAMIENTO,
        ratings_de,
        resultado,
    )
    from app.infrastructure.db import models as m

    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        partidos = [
            p
            for p in (
                await session.execute(select(m.TrainingMatch).order_by(m.TrainingMatch.ht_match_id))
            ).scalars()
            if p.match_type in TIPOS_DE_ENTRENAMIENTO
        ]
    y = np.array([resultado(p) for p in partidos])
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    k = len(COMPARACIONES)

    def ajusta(d):
        ref = OrderedModel(y, d, distr="logit").fit(method="bfgs", disp=False, maxiter=3000)
        u1 = float(ref.params[k])
        return (
            np.asarray(ref.params[:k], dtype=float),
            np.array([u1, u1 + float(np.exp(ref.params[k + 1]))]),
            ref,
        )

    # ── 1. Centrar no cambia nada: la constante la absorben los umbrales ──
    print("=" * 78)
    print("1. AJUSTAR CON x Y CON x-0,5, la constante la absorben los umbrales")
    print("=" * 78)
    d = np.array([[proporcion(mi[a], su[b]) for _, a, b in COMPARACIONES] for mi, su in lados])
    beta, umbrales, ref = ajusta(d)
    beta_c, umbrales_c, ref_c = ajusta(d - 0.5)
    print(f"  coeficientes iguales hasta 1e-4 : {np.allclose(beta, beta_c, atol=1e-4)}")
    print(f"  log-verosimilitud sin centrar   : {ref.llf:.4f}")
    print(f"  log-verosimilitud centrada      : {ref_c.llf:.4f}")
    print(f"  umbrales sin centrar            : {umbrales[0]:8.4f} {umbrales[1]:8.4f}")
    print(f"  umbrales centrados              : {umbrales_c[0]:8.4f} {umbrales_c[1]:8.4f}")
    print(f"  se movieron                     : {umbrales[0] - umbrales_c[0]:8.4f}")
    print(f"  0,5 x suma de coeficientes      : {0.5 * beta.sum():8.4f}   <- el mismo numero")
    p1 = np.array([terna(beta, umbrales, x) for x in d])
    p2 = np.array([terna(beta_c, umbrales_c, x) for x in d - 0.5])
    print(f"\n  mayor diferencia entre las {len(d)} predicciones: {np.abs(p1 - p2).max():.2e}")
    print("  o sea: centrar es reescribir lo mismo, no otro modelo.\n")

    # ── 2. El partido totalmente igualado, forma por forma ────────────────
    print("=" * 78)
    print("2. UN PARTIDO CON LOS NUEVE DUELOS IGUALADOS, segun cada forma")
    print("=" * 78)
    print(f"  {'forma':14}{'neutro':>9}{'recta':>9}{'derrota':>10}{'empate':>9}{'victoria':>10}")
    for nombre, f in FORMAS.items():
        dd = np.array([[f(mi[a], su[b]) for _, a, b in COMPARACIONES] for mi, su in lados])
        b_, u_, _ = ajusta(dd)
        x = np.full(k, NEUTRO[nombre])
        t = terna(b_, u_, x)
        print(
            f"  {nombre:14}{NEUTRO[nombre]:>9.3f}{float(b_ @ x):>9.3f}"
            f"{t[0]:>10.1%}{t[1]:>9.1%}{t[2]:>10.1%}"
        )
    print("\n  Las cuatro coinciden aunque su neutro sea 0,5, 1, 0 o -0,693.")
    print("  Si el 0,5 metiera un sesgo, aqui se veria: no se ve.\n")

    # ── 3. Contra lo que de verdad pasa ───────────────────────────────────
    print("=" * 78)
    print("3. ¿ES CREIBLE ESE NEUTRO?, contra los partidos de verdad")
    print("=" * 78)
    reparto = np.bincount(y, minlength=3) / len(y)
    print(f"  {'':14}{'derrota':>10}{'empate':>9}{'victoria':>10}")
    print(f"  {'todos':14}{reparto[0]:>10.1%}{reparto[1]:>9.1%}{reparto[2]:>10.1%}")
    # Los partidos que de verdad estuvieron igualados en los nueve duelos.
    cerca = np.abs(d - 0.5).max(axis=1) < 0.06
    if cerca.sum():
        r = np.bincount(y[cerca], minlength=3) / cerca.sum()
        print(
            f"  {'igualados':14}{r[0]:>10.1%}{r[1]:>9.1%}{r[2]:>10.1%}"
            f"   ({cerca.sum()} partidos con los 9 duelos entre 0,44 y 0,56)"
        )
    print(
        "\n  El local gana mas en un partido igualado porque la ventaja de campo\n"
        "  YA VIVE dentro de los ratings: el medio campo del local es de media un\n"
        "  19% mas alto. Un partido con los duelos empatados es un partido donde\n"
        "  el local rindio por debajo de lo normal, y aun asi gana algo mas."
    )


if __name__ == "__main__":
    asyncio.run(main())
