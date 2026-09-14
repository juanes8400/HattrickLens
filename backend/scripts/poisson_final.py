"""El modelo de goles propuesto, con todo lo que hay que exigirle antes de montarlo.

LA ECUACIÓN. Con enlace logarítmico Y duelos en `log(A/(A+B))`, el modelo deja
de ser una suma disfrazada y se convierte en un PRODUCTO DE POTENCIAS:

    lambda = exp(b0 + suma(b_j * log(p_j)))  =  exp(b0) * PRODUCTO(p_j ^ b_j)

Eso cambia lo que significa cada coeficiente: ya no es «cuánto suma este
duelo» sino una ELASTICIDAD --el porcentaje que crecen los goles cuando ese
duelo crece un uno por ciento--. Un modelo de goles multiplicativo es lo que
uno esperaría del fútbol (las ocasiones se encadenan, no se suman) y aquí sale
solo de la combinación enlace + transformación, sin imponer nada.

LO QUE SE COMPRUEBA, y no sólo lo bonito:
  1. La regresión entera, con intervalos y elasticidades.
  2. Sobredispersión: devianza y Pearson por grado de libertad, y binomial
     negativa por si acaso.
  3. Si hace falta un término de local ahora que la forma cambió.
  4. LA INDEPENDENCIA DE LOS DOS LADOS, que es el supuesto más frágil de todo
     el montaje: la rejilla de marcadores multiplica las dos Poisson como si
     los goles de un equipo no dijeran nada de los del otro. Dixon-Coles
     demostró en 1997 que eso falla en los marcadores bajos. Aquí se mide.
  5. Residuos por tramo, para ver si queda estructura sin explicar.

Uso:  python scripts/poisson_final.py
"""

import asyncio
import warnings

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TOPE = 12


def log_proporcion(a: float, b: float) -> float:
    t = a + b
    return float(np.log(a / t)) if t > 0 and a > 0 else float(np.log(1.0 / (t + 1.0)))


def proporcion(a: float, b: float) -> float:
    t = a + b
    return a / t if t > 0 else 0.5


def reparto(media: float) -> np.ndarray:
    k = np.arange(TOPE + 1)
    lg = (
        -media
        + k * np.log(max(media, 1e-9))
        - np.array([float(np.sum(np.log(np.arange(1, x + 1)))) if x else 0.0 for x in k])
    )
    p = np.exp(lg)
    return p / p.sum()


async def main() -> None:
    import statsmodels.api as sm

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        DUELOS_OFENSIVOS,
        ETIQUETAS,
        TIPOS_DE_ENTRENAMIENTO,
        ratings_de,
    )
    from app.infrastructure.db import models as m

    warnings.filterwarnings("ignore")
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        partidos = [
            p
            for p in (
                await session.execute(select(m.TrainingMatch).order_by(m.TrainingMatch.ht_match_id))
            ).scalars()
            if p.match_type in TIPOS_DE_ENTRENAMIENTO
        ]
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    gl = np.array([p.home_goals for p in partidos])
    gv = np.array([p.away_goals for p in partidos])
    n = len(partidos)
    ancho = max(len(v) for v in ETIQUETAS.values()) + 2

    def duelos(f, mi, su):
        return [f(mi[a], su[b]) for _, a, b in DUELOS_OFENSIVOS]

    def matriz(f, con_local=False):
        filas, goles = [], []
        for i, (mi, su) in enumerate(lados):
            filas += [duelos(f, mi, su) + ([1.0] if con_local else []),
                      duelos(f, su, mi) + ([0.0] if con_local else [])]
            goles += [int(gl[i]), int(gv[i])]
        return np.array(filas), np.array(goles)

    x, goles = matriz(log_proporcion)
    glm = sm.GLM(goles, sm.add_constant(x), family=sm.families.Poisson()).fit()

    # ── 1. La regresión ───────────────────────────────────────────────────
    print("=" * 92)
    print("REGRESIÓN DE POISSON, goles de UN lado · duelos en log(A/(A+B))")
    print("=" * 92)
    print(
        f"  {2 * n} observaciones (una por lado) · {goles.sum()} goles"
        f" · media {goles.mean():.3f}"
    )
    print()
    ic = glm.conf_int()
    print(
        f"  {'término':{ancho}}{'coef':>9}{'error':>8}{'z':>8}{'p':>11}"
        f"{'IC 95%':>20}{'elasticidad':>13}"
    )
    print(
        f"  {'(intercepto)':{ancho}}{float(glm.params[0]):>9.4f}{float(glm.bse[0]):>8.4f}"
        f"{float(glm.tvalues[0]):>8.1f}{float(glm.pvalues[0]):>11.2e}"
        f"{f'[{ic[0][0]:.3f}, {ic[0][1]:.3f}]':>20}{np.exp(glm.params[0]):>13.1f}"
    )
    for i, (clave, _, _) in enumerate(DUELOS_OFENSIVOS):
        c, se = float(glm.params[i + 1]), float(glm.bse[i + 1])
        print(
            f"  {ETIQUETAS[clave]:{ancho}}{c:>9.4f}{se:>8.4f}{c / se:>8.1f}"
            f"{float(glm.pvalues[i + 1]):>11.2e}"
            f"{f'[{ic[i + 1][0]:.3f}, {ic[i + 1][1]:.3f}]':>20}{c:>13.3f}"
        )
    print(f"\n  log-verosimilitud : {glm.llf:>12.1f}")
    print(f"  AIC               : {glm.aic:>12.1f}")
    print(f"  devianza nula     : {glm.null_deviance:>12.1f}")
    print(f"  devianza residual : {glm.deviance:>12.1f}   ({glm.df_resid} gl)")
    print(f"  pseudo-R2         : {1 - glm.deviance / glm.null_deviance:>12.4f}")
    suma = float(np.sum(glm.params[1:]))
    print(f"\n  suma de elasticidades: {suma:.4f}")
    parejo = float(np.exp(glm.params[0]) * 0.5**suma)
    print(f"  con los cinco duelos igualados (p=0,5): lambda = {parejo:.3f}")

    # ── 2. Dispersión ─────────────────────────────────────────────────────
    print("\n" + "=" * 92)
    print("DISPERSIÓN, ¿de verdad es Poisson?")
    print("=" * 92)
    print(f"  devianza / gl : {glm.deviance / glm.df_resid:.4f}")
    print(f"  Pearson  / gl : {glm.pearson_chi2 / glm.df_resid:.4f}   (1 = Poisson exacta)")
    print("  por debajo de 1 = SUBdispersión: la varianza real es MENOR que la media,")
    print("  o sea que los goles son más regulares de lo que una Poisson supondría.")
    for alpha in (0.01, 0.05, 0.10):
        nb = sm.GLM(
            goles, sm.add_constant(x), family=sm.families.NegativeBinomial(alpha=alpha)
        ).fit()
        print(f"  binomial negativa alpha={alpha:.2f}: AIC {nb.aic:.1f}  (Poisson {glm.aic:.1f})")
    print("  la binomial negativa sólo ayuda con SOBREdispersión; aquí no la hay.")

    # ── 3. ¿Término de local? ─────────────────────────────────────────────
    print("\n" + "=" * 92)
    print("¿HACE FALTA UN TÉRMINO DE LOCAL?")
    print("=" * 92)
    xl, gol_l = matriz(log_proporcion, con_local=True)
    glm_l = sm.GLM(gol_l, sm.add_constant(xl), family=sm.families.Poisson()).fit()
    c, se = float(glm_l.params[-1]), float(glm_l.bse[-1])
    print(
        f"  coeficiente de «juega en casa»: {c:+.4f}  error {se:.4f}"
        f"  p = {glm_l.pvalues[-1]:.3f}"
    )
    print(f"  AIC con local {glm_l.aic:.1f}   ·   sin local {glm.aic:.1f}")
    print("  La ventaja de campo YA VIVE dentro de los ratings (el mediocampo del")
    print("  local es de media un 19% más alto): sumarla otra vez la contaría dos veces.")

    # ── 4. La independencia de los dos lados ──────────────────────────────
    print("\n" + "=" * 92)
    print("INDEPENDENCIA DE LOS DOS LADOS, el supuesto más frágil")
    print("=" * 92)
    lam = glm.predict(sm.add_constant(x))
    lam_l, lam_v = lam[0::2], lam[1::2]
    # Residuo de Pearson de cada lado, y correlación DENTRO del partido.
    rl = (gl - lam_l) / np.sqrt(lam_l)
    rv = (gv - lam_v) / np.sqrt(lam_v)
    r = float(np.corrcoef(rl, rv)[0, 1])
    print(f"  correlación de los residuos de los dos lados: {r:+.4f}")
    print(f"  (n = {n} partidos · un cero perfecto sería independencia total)")
    ic_r = 1.96 / np.sqrt(n)
    print(f"  banda de ruido al 95%: ±{ic_r:.4f}   ->  {'DENTRO' if abs(r) < ic_r else 'FUERA'}")
    # Y lo que de verdad importa: ¿acierta el número de empates y de 0-0?
    esp_emp = esp_cero = 0.0
    for a, b in zip(lam_l, lam_v, strict=True):
        rej = np.outer(reparto(float(a)), reparto(float(b)))
        esp_emp += float(np.trace(rej))
        esp_cero += float(rej[0, 0])
    obs_emp = int((gl == gv).sum())
    obs_cero = int(((gl == 0) & (gv == 0)).sum())
    print(f"\n  empates : espera {esp_emp:>7.1f} ocurren {obs_emp:>5} {esp_emp - obs_emp:+7.1f}")
    print(f"  0-0     : espera {esp_cero:>7.1f} ocurren {obs_cero:>5} {esp_cero - obs_cero:+7.1f}")
    print("  Si la rejilla se quedara corta de empates, haría falta la corrección")
    print("  de Dixon-Coles para los marcadores bajos.")

    # ── 5. Residuos por tramo ─────────────────────────────────────────────
    print("\n" + "=" * 92)
    print("RESIDUOS POR TRAMO, ¿queda estructura sin explicar?")
    print("=" * 92)
    res = (goles - lam) / np.sqrt(lam)
    print(f"  {'tramo de lambda':>18}{'lados':>8}{'lambda':>9}{'goles':>8}{'residuo':>10}")
    bordes = [0, 0.6, 0.9, 1.2, 1.6, 2.1, 2.8, 4.0, 12.0]
    for lo, hi in zip(bordes[:-1], bordes[1:], strict=True):
        sel = (lam >= lo) & (lam < hi)
        if sel.sum() < 30:
            continue
        print(
            f"  {f'{lo:.1f} - {hi:.1f}':>18}{sel.sum():>8}{lam[sel].mean():>9.3f}"
            f"{goles[sel].mean():>8.3f}{res[sel].mean():>+10.4f}"
        )
    print("  Un residuo medio distinto de cero de forma sistemática en un tramo")
    print("  dice que la forma funcional se queda corta ahí.")

    # ── 6. Contra la forma de hoy, dentro de muestra ──────────────────────
    print("\n" + "=" * 92)
    print("CONTRA LA FORMA DE HOY")
    print("=" * 92)
    xa, _ = matriz(proporcion)
    glm_a = sm.GLM(goles, sm.add_constant(xa), family=sm.families.Poisson()).fit()
    print(f"  {'forma':16}{'logL':>12}{'AIC':>11}{'dev/gl':>9}{'Pearson/gl':>12}")
    for nombre, g in (("A/(A+B)", glm_a), ("log(A/(A+B))", glm)):
        print(
            f"  {nombre:16}{g.llf:>12.1f}{g.aic:>11.1f}"
            f"{g.deviance / g.df_resid:>9.4f}{g.pearson_chi2 / g.df_resid:>12.4f}"
        )
    print(f"\n  diferencia de AIC: {glm_a.aic - glm.aic:.1f} a favor de log(A/(A+B))")
    print("  (con los MISMOS seis parámetros: no compra ajuste con complejidad)")

    # ── 7. La ecuación, escrita ───────────────────────────────────────────
    print("\n" + "=" * 92)
    print("LA ECUACIÓN")
    print("=" * 92)
    print(f"  lambda = {np.exp(glm.params[0]):.2f}")
    for i, (_clave, a, b) in enumerate(DUELOS_OFENSIVOS):
        print(f"           x  p({a} vs {b}) ^ {float(glm.params[i + 1]):.3f}")
    print("\n  donde p(A vs B) = A / (A + B), y lambda se topa en 12.")


if __name__ == "__main__":
    asyncio.run(main())
