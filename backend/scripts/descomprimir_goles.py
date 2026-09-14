"""Dos arreglos a la vez para el modelo de goles: descomprimir y soltar el BP.

EL DEFECTO QUE SE ATACA. El modelo de hoy aprieta las lambdas hacia el centro:
donde promete 0,8 se marca 0,68 y donde promete 3,3 se marcan 3,55. Eso llena
de marcadores bajos la rejilla --sobran 233 partidos en el bloque de 0 y 1
goles-- y de ahí salen los 115 empates de más. NO es un problema de
dependencia entre los dos lados: se probó Dixon-Coles y su rho sale +0,009 con
p = 0,72, porque esa corrección conserva los marginales y sólo puede repartir
masa DENTRO del bloque, nunca sacarla.

PRIMER ARREGLO: DESCOMPRIMIR. La regresión ya encontró la mejor recta, así que
el sobrante no es de escala --una pendiente libre sobre el predictor lineal
saldría 1 por construcción-- sino de CURVATURA. Se prueba metiendo el cuadrado
del predictor lineal como una variable más: si su coeficiente es positivo y
significativo, la relación se estira en los extremos, que es justo lo que
falta.

SEGUNDO ARREGLO: SOLTAR EL BALÓN PARADO DEL MEDIOCAMPO. Hoy los goles son UN
producto, así que `p(medio)^1,718` multiplica también al Balón Parado: un
equipo que pierde el mediocampo ve hundida hasta su amenaza a balón parado. Y
eso no se sostiene --un córner o una falta no dependen de la posesión como una
jugada de ataque--. La alternativa es DOS SUMANDOS:

    lambda = exp(k1 + a·log p_medio + b·Σ log p_ataque)      <- juego abierto
           + exp(k2 + d·log p_medio + c·log p_bp)            <- balón parado

La suma de dos Poisson sigue siendo Poisson, así que el modelo de conteo no
cambia; lo que cambia es que el Balón Parado tiene su PROPIA dependencia del
mediocampo, `d`, en vez de heredar la del juego abierto. Con d = 0 es
independiente del todo; si sale d < a, el BP depende menos, que es la
hipótesis. Deja de ser un GLM --es una suma de exponenciales-- así que se
ajusta por máxima verosimilitud directa.

Uso:  python scripts/descomprimir_goles.py
"""

import asyncio
import warnings

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TOPE = 12


def reparto(media: float) -> np.ndarray:
    k = np.arange(TOPE + 1)
    lg = (
        -media
        + k * np.log(max(media, 1e-9))
        - np.array([float(np.sum(np.log(np.arange(1, x + 1)))) if x else 0.0 for x in k])
    )
    p = np.exp(lg)
    return p / p.sum()


def lp(a: float, b: float) -> float:
    t = a + b
    return float(np.log(a / t)) if t > 0 and a > 0 else float(np.log(1.0 / (t + 1.0)))


async def main() -> None:
    import statsmodels.api as sm
    from scipy.optimize import minimize
    from sklearn.metrics import log_loss

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        DUELOS_OFENSIVOS,
        TIPOS_DE_ENTRENAMIENTO,
        ratings_de,
        resultado,
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
    y = np.array([resultado(p) for p in partidos])
    gl = np.array([p.home_goals for p in partidos])
    gv = np.array([p.away_goals for p in partidos])
    n = len(partidos)

    medio, ataques, balon = DUELOS_OFENSIVOS[0], DUELOS_OFENSIVOS[1:-1], DUELOS_OFENSIVOS[-1]

    #: Tres columnas por lado: mediocampo, suma de los tres ataques, balón
    #: parado. Todas ya en `log(A/(A+B))`.
    filas, cuenta = [], []
    for i, (mi, su) in enumerate(lados):
        for a, b, g in ((mi, su, gl[i]), (su, mi, gv[i])):
            filas.append(
                [
                    lp(a[medio[1]], b[medio[2]]),
                    sum(lp(a[x], b[z]) for _, x, z in ataques),
                    lp(a[balon[1]], b[balon[2]]),
                ]
            )
            cuenta.append(int(g))
    dis = np.array(filas)
    cnt = np.array(cuenta)
    log_fact = np.array([float(np.sum(np.log(np.arange(1, k + 1)))) if k else 0.0 for k in cnt])

    def verosimilitud(lam: np.ndarray) -> float:
        lam = np.clip(lam, 1e-9, 60.0)
        return float(np.sum(cnt * np.log(lam) - lam - log_fact))

    # ── Los cinco modelos ────────────────────────────────────────────────
    def lam_uno(par, d=dis):
        """Hoy: un solo producto de potencias."""
        return np.exp(par[0] + d @ par[1:4])

    def lam_uno_cuad(par, d=dis):
        """Hoy + el cuadrado del predictor lineal: la descompresión."""
        eta = par[0] + d @ par[1:4]
        return np.exp(eta + par[4] * (eta - eta_media) ** 2)

    def lam_dos(par, d=dis):
        """Dos sumandos, el BP con su propia dependencia del mediocampo."""
        juego = np.exp(par[0] + par[1] * d[:, 0] + par[2] * d[:, 1])
        bp = np.exp(par[3] + par[4] * d[:, 0] + par[5] * d[:, 2])
        return juego + bp

    def lam_dos_libre(par, d=dis):
        """Dos sumandos con el BP INDEPENDIENTE del mediocampo (d = 0)."""
        juego = np.exp(par[0] + par[1] * d[:, 0] + par[2] * d[:, 1])
        bp = np.exp(par[3] + par[4] * d[:, 2])
        return juego + bp

    def lam_dos_cuad(par, d=dis):
        """Los dos arreglos juntos."""
        eta = par[0] + par[1] * d[:, 0] + par[2] * d[:, 1]
        juego = np.exp(eta + par[6] * (eta - eta_media) ** 2)
        bp = np.exp(par[3] + par[4] * d[:, 0] + par[5] * d[:, 2])
        return juego + bp

    base = sm.GLM(cnt, sm.add_constant(dis), family=sm.families.Poisson()).fit()
    p0 = np.asarray(base.params, dtype=float)
    eta_media = float((p0[0] + dis @ p0[1:4]).mean())

    modelos = {
        "hoy (un producto)": (lam_uno, p0, ["k", "medio", "ataque", "bp"]),
        "hoy + descompresión": (
            lam_uno_cuad,
            np.append(p0, 0.0),
            ["k", "medio", "ataque", "bp", "cuadrático"],
        ),
        "BP suelto (d libre)": (
            lam_dos,
            np.array([p0[0] - 0.4, p0[1], p0[2], p0[0] - 1.5, p0[1] * 0.3, p0[3]]),
            ["k juego", "medio", "ataque", "k BP", "medio en BP", "bp"],
        ),
        "BP independiente (d=0)": (
            lam_dos_libre,
            np.array([p0[0] - 0.4, p0[1], p0[2], p0[0] - 1.5, p0[3]]),
            ["k juego", "medio", "ataque", "k BP", "bp"],
        ),
        "BP suelto + descompresión": (
            lam_dos_cuad,
            np.array([p0[0] - 0.4, p0[1], p0[2], p0[0] - 1.5, p0[1] * 0.3, p0[3], 0.0]),
            ["k juego", "medio", "ataque", "k BP", "medio en BP", "bp", "cuadrático"],
        ),
    }

    print(f"{n} partidos · {2 * n} lados · {cnt.sum()} goles\n")
    print("=" * 96)
    print("AJUSTE COMPLETO, máxima verosimilitud sobre los 10.464 lados")
    print("=" * 96)
    ajustados = {}
    for nombre, (fn, inicio, etiquetas) in modelos.items():
        res = minimize(
            lambda p, fn=fn: -verosimilitud(fn(p)),
            inicio,
            method="Nelder-Mead",
            options={"maxiter": 60000, "maxfev": 60000, "xatol": 1e-8, "fatol": 1e-8},
        )
        par = res.x
        ll = verosimilitud(fn(par))
        aic = 2 * len(par) - 2 * ll
        ajustados[nombre] = (fn, par, ll, aic)
        print(f"\n  {nombre}   logL {ll:.1f}   AIC {aic:.1f}   ({len(par)} parámetros)")
        print("    " + "  ".join(f"{e}={v:+.4f}" for e, v in zip(etiquetas, par, strict=True)))

    # ── Fuera de muestra ─────────────────────────────────────────────────
    cortes = [(int(n * f), int(n * (f + 0.12))) for f in (0.40, 0.52, 0.64, 0.76, 0.88)]
    print("\n" + "=" * 96)
    print("FUERA DE MUESTRA, origen móvil, reajustando en cada corte")
    print("=" * 96)
    print(
        f"  {'modelo':28}{'logver':>9}{'EAM':>8}{'EC':>8}{'pend':>8}"
        f"{'V/E/D':>9}{'empates':>10}{'bloque 0-1':>12}"
    )
    for nombre, (fn, _, _, _) in ajustados.items():
        _, inicio, _ = modelos[nombre]
        lam_t, real_t, res_t, yy_t = [], [], [], []
        for ini, fin in cortes:
            h = 2 * ini
            sub_cnt, sub_dis = cnt[:h], dis[:h]
            sub_fact = log_fact[:h]

            def ver(par, c=sub_cnt, d=sub_dis, f=sub_fact, fn=fn):
                lam = np.clip(fn(par, d), 1e-9, 60.0)
                return -float(np.sum(c * np.log(lam) - lam - f))

            par = minimize(
                ver, inicio, method="Nelder-Mead", options={"maxiter": 60000, "maxfev": 60000}
            ).x
            tr = slice(h, 2 * fin)
            lam = np.clip(fn(par, dis[tr]), 1e-6, 12.0)
            lam_t += list(lam)
            real_t += list(cnt[tr])
            for j in range(0, len(lam), 2):
                rej = np.outer(reparto(float(lam[j])), reparto(float(lam[j + 1])))
                v, e, d_ = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
                t = v + e + d_
                res_t.append([d_ / t, e / t, v / t])
            yy_t += list(y[ini:fin])
        la, ra = np.array(lam_t), np.array(real_t)
        lv = float(
            np.mean(
                [
                    np.log(max(reparto(a)[min(int(b), TOPE)], 1e-12))
                    for a, b in zip(la, ra, strict=True)
                ]
            )
        )
        emp = bloque = 0.0
        for j in range(0, len(la), 2):
            rej = np.outer(reparto(float(la[j])), reparto(float(la[j + 1])))
            emp += float(np.trace(rej))
            bloque += float(rej[:2, :2].sum())
        yy = np.array(yy_t)
        obs_emp = int((yy == 1).sum())
        obs_bloque = int(
            sum(1 for j in range(0, len(ra), 2) if ra[j] <= 1 and ra[j + 1] <= 1)
        )
        print(
            f"  {nombre:28}{lv:>9.4f}{np.abs(la - ra).mean():>8.4f}"
            f"{np.sqrt(((la - ra) ** 2).mean()):>8.4f}"
            f"{float(np.polyfit(la, ra, 1)[0]):>8.4f}"
            f"{log_loss(yy, np.clip(np.array(res_t), 1e-12, 1), labels=[0, 1, 2]):>9.4f}"
            f"{f'{emp:.0f}/{obs_emp}':>10}{f'{bloque:.0f}/{obs_bloque}':>12}"
        )
    print("\n  «empates» y «bloque 0-1» son esperados/ocurridos: cuanto más cerca, mejor.")

    # ── Los residuos por tramo, antes y después ──────────────────────────
    print("\n" + "=" * 96)
    print("RESIDUOS POR TRAMO, donde vivía la compresión")
    print("=" * 96)
    print(f"  {'tramo de lambda':>18}", end="")
    for nombre in ajustados:
        print(f"{nombre[:14]:>16}", end="")
    print()
    bordes = [0, 0.6, 0.9, 1.2, 1.6, 2.1, 2.8, 4.0, 12.0]
    lams = {nombre: fn(par) for nombre, (fn, par, _, _) in ajustados.items()}
    for lo, hi in zip(bordes[:-1], bordes[1:], strict=True):
        base_lam = lams["hoy (un producto)"]
        sel = (base_lam >= lo) & (base_lam < hi)
        if sel.sum() < 30:
            continue
        print(f"  {f'{lo:.1f} - {hi:.1f}':>18}", end="")
        for nombre in ajustados:
            r = (cnt[sel] - lams[nombre][sel]) / np.sqrt(np.clip(lams[nombre][sel], 1e-9, None))
            print(f"{r.mean():>+16.4f}", end="")
        print()


if __name__ == "__main__":
    asyncio.run(main())
