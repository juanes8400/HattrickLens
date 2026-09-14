"""¿`A/(A+B)`, `A/B` o `log(A/B)`? Las tres, ajustadas y medidas igual.

Las tres dicen lo mismo del duelo --quién manda y por cuánto-- y las tres lo
ORDENAN igual: son transformaciones monótonas unas de otras. Lo que cambia es
la FORMA en que entran a una suma en línea recta, y eso sí cambia el ajuste.

  `A/(A+B)`  vive en [0,1], simétrica en 0,5, y aplasta los extremos: de 1
             contra 10 a 1 contra 100 sólo hay 0,081 de diferencia.
  `A/B`      neutro en 1, ASIMÉTRICA: doblar da 2,0 y que te doblen da 0,5, o
             sea que la misma ventaja pesa cuatro veces más en un sentido.
             Sin techo por arriba, con suelo por abajo.
  `log(A/B)` neutro en 0, simétrica (+0,69 y -0,69 para el mismo duelo del
             revés) y sin techo: una paliza sigue contando como paliza.

No se decide mirando cuál suena mejor: se ajustan las tres con los mismos
partidos, se miden con los mismos cortes de origen móvil --reajustando en cada
corte, sin que ninguna vea lo que va a predecir-- y gana la que gane.

LO QUE SALIÓ el 2026-09-07 sobre 5.232 partidos, log-loss del motor:
`A/(A+B)` 0,6419 · `log(A/B)` 0,6476 · `A/B` 0,6822, y `A/(A+B)` gana los 5
cortes de 5.

Uso:  python scripts/comparar_parametrizacion.py
"""

import asyncio

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")


def _ece(pr: np.ndarray, real: np.ndarray) -> float:
    total = 0.0
    for i in range(10):
        sel = (pr >= i / 10) & (pr < (i + 1) / 10 + (0.001 if i == 9 else 0.0))
        if sel.sum():
            total += sel.sum() / len(pr) * abs(pr[sel].mean() - real[sel].mean())
    return total


def proporcion(a: float, b: float) -> float:
    total = a + b
    return a / total if total > 0 else 0.5


def logaritmo(a: float, b: float) -> float:
    """`log(A/B)`. Un rating de Hattrick nunca es cero en un partido oficial
    --medido: el mínimo de los nueve campos en 6.094 partidos va de 1 a 5--
    pero el suelo en 1 está igualmente, porque un cero aquí no daría un número
    grande: daría un infinito."""
    return float(np.log(max(a, 1.0) / max(b, 1.0)))


def log_proporcion(a: float, b: float) -> float:
    """`log(A/(A+B))`: el logaritmo de la proporción, no del cociente.

    Es la cuarta forma y también monótona, así que ordena igual que las otras
    tres. Su gracia es que es la más asimétrica de todas, y en el sentido
    contrario a `A/B`: como la proporción vive en (0,1), su logaritmo vive en
    (-inf, 0), se dispara cuando te dominan y se aplasta cuando dominas.

    Medido sobre los 94.176 duelos de los 5.232 partidos: `log(p)` va de
    -4,52 a -0,011. O sea 3,83 de recorrido para la mitad en la que pierdes
    el duelo y sólo 0,68 para la mitad en la que lo ganas. `log(A/B)` reparte
    ese mismo rango simétricamente, -4,51 a +4,51.

    Traducido, la hipótesis que asume esta forma es que en el fútbol de
    Hattrick que te revienten una zona duele mucho más de lo que aporta
    reventarla tú. No es descabellada --una defensa floja encaja da igual lo
    que ataques-- y por eso se mide en vez de descartarla de palabra.
    """
    total = a + b
    return float(np.log(a / total)) if total > 0 and a > 0 else float(np.log(1.0 / (total + 1.0)))


def cociente(a: float, b: float) -> float:
    """`A/B` a pelo, la tercera forma y la única ASIMÉTRICA de las tres.

    Doblar al rival da 2,0; que te doblen da 0,5. La misma ventaja, medida en
    veces, pesa cuatro veces más en un sentido que en el otro, y como el
    modelo suma los duelos en línea recta eso no es un detalle de escala: es
    una afirmación sobre el fútbol. Además no tiene techo por arriba (un 100
    contra 1 da 100) pero sí suelo por abajo (nunca baja de 0), así que un
    solo partido con una paliza puede arrastrar un coeficiente.

    El neutro aquí es 1 --ni 0 ni 0,5--, que es lo que hace que el intercepto
    de la Poisson signifique otra cosa distinta en cada una de las tres.
    """
    return max(a, 1.0) / max(b, 1.0)


async def main() -> None:
    import statsmodels.api as sm
    from sklearn.metrics import log_loss, roc_auc_score
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        COMPARACIONES,
        DUELOS_OFENSIVOS,
        ETIQUETAS,
        PESO_GOLES,
        PESO_ORDINAL,
        TIPOS_DE_ENTRENAMIENTO,
        _reparto_de_goles,
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
    n = len(partidos)
    reparto = dict(zip(CLASES, np.bincount(y, minlength=3), strict=True))
    print(f"{n} partidos de liga · reparto {reparto}\n")

    formas = {
        "A/(A+B)": proporcion,
        "A/B": cociente,
        "log(A/B)": logaritmo,
        "log(A/(A+B))": log_proporcion,
    }

    def diseno_de(f):
        return np.array([[f(mio[a], suyo[b]) for _, a, b in COMPARACIONES] for mio, suyo in lados])

    def ofensivo_de(f, mio, suyo):
        return [f(mio[a], suyo[b]) for _, a, b in DUELOS_OFENSIVOS]

    disenos = {k: diseno_de(f) for k, f in formas.items()}

    # ── 1. El ajuste completo, con todo lo que se le puede pedir ──────────
    ancho = max(len(v) for v in ETIQUETAS.values()) + 2
    completos = {}
    for nombre in formas:
        d = disenos[nombre]
        ref = OrderedModel(y, d, distr="logit").fit(method="bfgs", disp=False, maxiter=3000)
        completos[nombre] = ref
        k = d.shape[1]
        print("=" * 84)
        print(f"REGRESIÓN ORDINAL con {nombre}, derrota < empate < victoria")
        print("=" * 84)
        cab = f"  {'duelo':{ancho}}{'coef':>10}{'error':>8}{'z':>8}{'p-valor':>11}{'IC 95%':>21}"
        print(cab)
        for i, (clave, _, _) in enumerate(COMPARACIONES):
            c = float(ref.params[i])
            se = float(ref.bse[i])
            ic = f"[{c - 1.96 * se:.3f}, {c + 1.96 * se:.3f}]"
            print(
                f"  {ETIQUETAS[clave]:{ancho}}{c:>10.4f}{se:>8.4f}"
                f"{c / se:>8.1f}{float(ref.pvalues[i]):>11.2e}{ic:>21}"
            )
        u1 = float(ref.params[k])
        u2 = u1 + float(np.exp(ref.params[k + 1]))
        print(f"\n  umbral 1 (derrota|empate) : {u1:>9.4f}")
        print(f"  umbral 2 (empate|victoria): {u2:>9.4f}")
        print(f"  pseudo-R² (McFadden)      : {ref.prsquared:.4f}")
        print(f"  log-verosimilitud         : {ref.llf:.1f}  (modelo vacío {ref.llnull:.1f})")
        print(f"  AIC                       : {ref.aic:.1f}")
        print()

    # ── 2. Origen móvil: se reajusta en cada corte y se mide lo siguiente ──
    cortes = [(int(n * f), int(n * (f + 0.12))) for f in (0.40, 0.52, 0.64, 0.76, 0.88)]

    def ajusta(nombre, f, hasta):
        d = disenos[nombre]
        ref = OrderedModel(y[:hasta], d[:hasta], distr="logit").fit(
            method="bfgs", disp=False, maxiter=3000
        )
        k = d.shape[1]
        beta = np.asarray(ref.params[:k], dtype=float)
        u1 = float(ref.params[k])
        umbrales = np.array([u1, u1 + float(np.exp(ref.params[k + 1]))])

        def ordinal(x):
            eta = float(beta @ x)
            s1, s2 = 1 / (1 + np.exp(-(umbrales - eta)))
            return np.array([s1, s2 - s1, 1 - s2])

        filas, goles = [], []
        for i, (mio, suyo) in enumerate(lados[:hasta]):
            filas += [ofensivo_de(f, mio, suyo), ofensivo_de(f, suyo, mio)]
            goles += [partidos[i].home_goals, partidos[i].away_goals]
        glm = sm.GLM(
            np.array(goles), sm.add_constant(np.array(filas)), family=sm.families.Poisson()
        ).fit()

        def poisson(mio, suyo):
            duelos = np.array([ofensivo_de(f, mio, suyo), ofensivo_de(f, suyo, mio)])
            lam = glm.predict(sm.add_constant(duelos, has_constant="add"))
            rej = np.outer(
                _reparto_de_goles(min(lam[0], 12.0)), _reparto_de_goles(min(lam[1], 12.0))
            )
            v, e, d_ = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
            t = v + e + d_
            return np.array([d_ / t, e / t, v / t])

        return ordinal, poisson, glm

    filas_tabla = []
    guardadas: dict[str, list] = {}
    por_corte: dict[str, list] = {}
    for nombre, f in formas.items():
        perdida: dict[str, list] = {"ordinal": [], "goles": [], "motor": []}
        otras: dict[str, list] = {"ordinal": [], "goles": [], "motor": []}
        acum: list = []
        for ini, fin in cortes:
            ordinal, poisson, _ = ajusta(nombre, f, ini)
            yy = y[ini:fin]
            p_ord = np.array([ordinal(x) for x in disenos[nombre][ini:fin]])
            p_gol = np.array([poisson(mio, suyo) for mio, suyo in lados[ini:fin]])
            p_mot = PESO_ORDINAL * p_ord + PESO_GOLES * p_gol
            acum.append(p_mot)
            for clave, probs in (("ordinal", p_ord), ("goles", p_gol), ("motor", p_mot)):
                perdida[clave].append(log_loss(yy, np.clip(probs, 1e-12, 1), labels=[0, 1, 2]))
                otras[clave].append(
                    [
                        float((probs.argmax(1) == yy).mean()),
                        roc_auc_score((yy == 2).astype(int), probs[:, 2]),
                        roc_auc_score((yy == 0).astype(int), probs[:, 0]),
                        roc_auc_score((yy == 1).astype(int), probs[:, 1]),
                    ]
                )
        guardadas[nombre] = acum
        por_corte[nombre] = perdida["motor"]
        for clave in ("ordinal", "goles", "motor"):
            ac, av, ad, ae = np.array(otras[clave]).mean(axis=0)
            filas_tabla.append(
                (
                    nombre,
                    clave,
                    float(np.mean(perdida[clave])),
                    float(np.std(perdida[clave])),
                    ac,
                    av,
                    ad,
                    ae,
                )
            )

    print("=" * 84)
    print("ORIGEN MÓVIL, 5 cortes, reajustando en cada uno, midiendo lo siguiente")
    print("=" * 84)
    print(
        f"  {'forma':14}{'modelo':10}{'log-loss':>10}{'±':>7}"
        f"{'aciertos':>10}{'AUC vic':>9}{'AUC der':>9}{'AUC emp':>9}"
    )
    for forma, clave, ll, sd, ac, av, ad, ae in filas_tabla:
        print(
            f"  {forma:14}{clave:10}{ll:>10.4f}{sd:>7.3f}{ac:>10.3f}{av:>9.3f}{ad:>9.3f}{ae:>9.3f}"
        )
    suelo = []
    for ini, fin in cortes:
        base = np.bincount(y[:ini], minlength=3) / ini
        suelo.append(log_loss(y[ini:fin], np.tile(base, (fin - ini, 1)), labels=[0, 1, 2]))
    print(f"  {'-':14}{'no saber':10}{np.mean(suelo):>10.4f}   <- el listón")

    print("\n  el motor, corte a corte (más bajo, mejor):")
    print(f"    {'corte':>7}" + "".join(f"{k:>16}" for k in formas))
    victorias = dict.fromkeys(formas, 0)
    for i, (ini, _) in enumerate(cortes):
        fila = {k: por_corte[k][i] for k in formas}
        mejor = min(fila, key=lambda k: fila[k])
        victorias[mejor] += 1
        print(f"    {ini:>7}" + "".join(f"{fila[k]:>16.4f}" for k in formas) + f"   <- {mejor}")
    print("\n  cortes ganados: " + " · ".join(f"{k} {v}" for k, v in victorias.items()))

    # ── 3. Calibración del motor entero, forma por forma ──────────────────
    yy = np.concatenate([y[a:b] for a, b in cortes])
    rng = np.random.default_rng(20260907)
    print()
    print("=" * 84)
    print(f"CALIBRACIÓN del motor sobre {len(yy)} partidos no vistos")
    print("=" * 84)
    for nombre in formas:
        probs = np.vstack(guardadas[nombre])
        print(f"  {nombre}")
        print(f"    {'clase':10}{'promete':>9}{'ocurre':>9}{'ECE':>8}{'p95':>8}  veredicto")
        for k, nom in enumerate(CLASES):
            pr, real = probs[:, k], (yy == k).astype(int)
            obs = _ece(pr, real)
            sim = np.array([_ece(pr, (rng.random(len(yy)) < pr).astype(int)) for _ in range(1500)])
            p95 = float(np.quantile(sim, 0.95))
            print(
                f"    {nom:10}{pr.sum():>9.0f}{real.sum():>9}{obs:>8.3f}{p95:>8.3f}"
                f"  {'calibrada' if obs <= p95 else 'DESCALIBRADA'}"
            )
        print()

    # ── 4. Lo que habría que pegar en el motor ────────────────────────────
    print("=" * 84)
    print("PARA COPIAR AL MOTOR, log(A/B)")
    print("=" * 84)
    ref = completos["log(A/B)"]
    k = len(COMPARACIONES)
    print("BETA = (")
    for i, (clave, _, _) in enumerate(COMPARACIONES):
        print(f"    {float(ref.params[i]):>9.5f},  # {ETIQUETAS[clave]}")
    print(")")
    u1 = float(ref.params[k])
    print(f"UMBRALES = ({u1:.5f}, {u1 + float(np.exp(ref.params[k + 1])):.5f})")
    print(f"OBSERVACIONES = {n}")

    filas, goles = [], []
    for i, (mio, suyo) in enumerate(lados):
        filas += [ofensivo_de(logaritmo, mio, suyo), ofensivo_de(logaritmo, suyo, mio)]
        goles += [partidos[i].home_goals, partidos[i].away_goals]
    glm = sm.GLM(
        np.array(goles), sm.add_constant(np.array(filas)), family=sm.families.Poisson()
    ).fit()
    print(f"\nPOISSON_INTERCEPTO = {float(glm.params[0]):.5f}")
    print("POISSON_BETA = (")
    for i, (clave, _, _) in enumerate(DUELOS_OFENSIVOS):
        print(f"    {float(glm.params[i + 1]):>9.5f},  # {ETIQUETAS[clave]}")
    print(")")
    print("\n  GLM de goles con log(A/B):")
    print(f"    {'duelo':{ancho}}{'coef':>10}{'error':>8}{'z':>8}{'p-valor':>11}")
    for i, (clave, _, _) in enumerate(DUELOS_OFENSIVOS):
        c, se = float(glm.params[i + 1]), float(glm.bse[i + 1])
        print(
            f"    {ETIQUETAS[clave]:{ancho}}{c:>10.4f}{se:>8.4f}"
            f"{c / se:>8.1f}{float(glm.pvalues[i + 1]):>11.2e}"
        )
    print(f"    devianza/gl = {glm.deviance / glm.df_resid:.3f}  (1 sería Poisson exacta)")


if __name__ == "__main__":
    asyncio.run(main())
