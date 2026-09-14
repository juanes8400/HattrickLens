"""¿Y si todo saliera de la Poisson? Goles contra goles, y resultado contra resultado.

HASTA HOY la Poisson se ha medido SIEMPRE por el resultado: se predicen los
goles de cada lado, se arma la rejilla de marcadores y se mira el log-loss de
victoria/empate/derrota. Eso es medirla por lo que NO es. Un modelo de goles
hay que medirlo también contra los goles que se marcaron, que es lo único que
la mitad ordinal no puede hacer: la ordinal no sabe lo que es un gol.

QUÉ HACE ESTE GUION, todo con origen móvil y reajustando en cada corte:

  1. La regresión completa, con sus errores, sus p-valores y su dispersión.
  2. GOLES CONTRA GOLES: error medio, sesgo, calibración por tramos y el
     reparto entero de 0,1,2,3... goles, esperado contra ocurrido.
  3. Si conviene meter los nueve duelos en vez de los cinco ofensivos.
  4. MARCADORES: cuántos acierta exactos, y contra qué listón.
  5. RESULTADO: la Poisson sola contra la ordinal sola y contra la mezcla.

EL LISTÓN DE LOS GOLES no es cero error, que no existe: es predecir siempre
la media. Un modelo de goles que no baje de ahí no ha aprendido nada por muy
razonable que suene su ecuación.

Uso:  python scripts/solo_poisson.py
"""

import asyncio
import warnings

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")
TOPE = 12


def reparto(media: float) -> np.ndarray:
    """Probabilidad de marcar 0, 1, 2… goles hasta el tope."""
    k = np.arange(TOPE + 1)
    log = (
        -media
        + k * np.log(max(media, 1e-9))
        - np.array([float(np.sum(np.log(np.arange(1, x + 1)))) if x else 0.0 for x in k])
    )
    p = np.exp(log)
    return p / p.sum()


async def main() -> None:
    import statsmodels.api as sm
    from sklearn.metrics import log_loss, roc_auc_score

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        COMPARACIONES,
        DUELOS_OFENSIVOS,
        ETIQUETAS,
        PESO_GOLES,
        PESO_ORDINAL,
        TIPOS_DE_ENTRENAMIENTO,
        modelo_ajustado,
        proporcion,
        ratings_de,
        resultado,
        variables,
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
    y = np.array([resultado(p) for p in partidos])
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    n = len(partidos)
    goles_local = np.array([p.home_goals for p in partidos])
    goles_visit = np.array([p.away_goals for p in partidos])
    print(f"{n} partidos de liga · {2 * n} lados · {goles_local.sum() + goles_visit.sum()} goles")
    print(
        f"media de goles por lado {np.concatenate([goles_local, goles_visit]).mean():.3f} "
        f"(local {goles_local.mean():.3f} · visitante {goles_visit.mean():.3f})\n"
    )

    #: Los dos juegos de variables que se comparan para los goles. El de cinco
    #: es el que usa el motor: sólo lo OFENSIVO, porque para MIS goles mi
    #: defensa no pinta nada --y la defensa del rival ya está dentro de cada
    #: duelo, que es «mi ataque contra su defensa»--. El de nueve mete también
    #: mis duelos defensivos, para comprobar que esa intuición se sostiene.
    juegos = {
        "5 ofensivos": DUELOS_OFENSIVOS,
        "los 9 duelos": COMPARACIONES,
    }

    def duelos(juego, mio, suyo):
        return [proporcion(mio[a], suyo[b]) for _, a, b in juego]

    cortes = [(int(n * f), int(n * (f + 0.12))) for f in (0.40, 0.52, 0.64, 0.76, 0.88)]

    def ajusta_glm(juego, hasta):
        """Una fila por LADO: cada partido enseña dos veces, una por equipo."""
        filas, goles = [], []
        for i, (mi, su) in enumerate(lados[:hasta]):
            filas += [duelos(juego, mi, su), duelos(juego, su, mi)]
            goles += [int(goles_local[i]), int(goles_visit[i])]
        return sm.GLM(
            np.array(goles), sm.add_constant(np.array(filas)), family=sm.families.Poisson()
        ).fit()

    # ── 1. La regresión completa, sobre todo ──────────────────────────────
    for nombre, juego in juegos.items():
        glm = ajusta_glm(juego, n)
        ancho = max(len(v) for v in ETIQUETAS.values()) + 2
        print("=" * 84)
        print(f"REGRESIÓN DE POISSON sobre los goles de un lado, {nombre}")
        print("=" * 84)
        print(f"  {'duelo':{ancho}}{'coef':>10}{'error':>8}{'z':>8}{'p-valor':>11}{'x1,10':>9}")
        print(f"  {'(intercepto)':{ancho}}{float(glm.params[0]):>10.4f}{float(glm.bse[0]):>8.4f}")
        for i, (clave, _, _) in enumerate(juego):
            c, se = float(glm.params[i + 1]), float(glm.bse[i + 1])
            # Cuánto multiplica los goles subir ese duelo diez puntos.
            print(
                f"  {ETIQUETAS[clave]:{ancho}}{c:>10.4f}{se:>8.4f}{c / se:>8.1f}"
                f"{float(glm.pvalues[i + 1]):>11.2e}{float(np.exp(c * 0.10)):>9.3f}"
            )
        print(f"\n  log-verosimilitud : {glm.llf:.1f}")
        print(f"  AIC               : {glm.aic:.1f}")
        print(f"  devianza / gl     : {glm.deviance / glm.df_resid:.3f}  (1 = Poisson exacta)")
        print(f"  Pearson  / gl     : {glm.pearson_chi2 / glm.df_resid:.3f}\n")

    # ── 2. Goles contra goles, fuera de muestra ───────────────────────────
    print("=" * 84)
    print("GOLES CONTRA GOLES, origen móvil, reajustando en cada corte")
    print("=" * 84)
    guardado = {}
    for nombre, juego in juegos.items():
        lam_todos, real_todos = [], []
        for ini, fin in cortes:
            glm = ajusta_glm(juego, ini)
            for i in range(ini, fin):
                mi, su = lados[i]
                x = np.array([duelos(juego, mi, su), duelos(juego, su, mi)])
                lam = glm.predict(sm.add_constant(x, has_constant="add"))
                lam_todos += [float(lam[0]), float(lam[1])]
                real_todos += [int(goles_local[i]), int(goles_visit[i])]
        lam = np.clip(np.array(lam_todos), 1e-6, 12.0)
        real = np.array(real_todos)
        guardado[nombre] = (lam, real)
        media_ent = real.mean()
        print(f"  {nombre}  ({len(real)} lados no vistos)")
        print(f"    error absoluto medio : {np.abs(lam - real).mean():.4f}")
        print(f"    error cuadrático     : {np.sqrt(((lam - real) ** 2).mean()):.4f}")
        print(f"    sesgo (predicho-real): {(lam - real).mean():+.4f}")
        print(f"    correlación          : {np.corrcoef(lam, real)[0, 1]:.4f}")
        print(f"    goles predichos      : {lam.sum():.0f}   ocurridos {real.sum()}")
        # El listón: predecir siempre la media, sin mirar el partido.
        print(
            f"    LISTÓN (siempre {media_ent:.2f}) : EAM {np.abs(media_ent - real).mean():.4f}"
            f" · EC {np.sqrt(((media_ent - real) ** 2).mean()):.4f}"
        )
        # Verosimilitud de los goles, que es la medida propia de un modelo de
        # conteo: cuánta probabilidad le dio a lo que de verdad pasó.
        lp = np.array(
            [
                np.log(max(reparto(lam_i)[min(r, TOPE)], 1e-12))
                for lam_i, r in zip(lam, real, strict=True)
            ]
        )
        base = reparto(media_ent)
        lp0 = np.array([np.log(max(base[min(r, TOPE)], 1e-12)) for r in real])
        print(f"    log-verosim. por lado: {lp.mean():.4f}   (listón {lp0.mean():.4f})\n")

    lam, real = guardado["5 ofensivos"]

    print("  CALIBRACIÓN por tramo de goles esperados:")
    print(f"    {'tramo':>12}{'lados':>8}{'promete':>10}{'ocurre':>9}{'error':>8}")
    bordes = [0, 0.5, 0.8, 1.1, 1.5, 2.0, 2.5, 3.5, 12.0]
    for lo, hi in zip(bordes[:-1], bordes[1:], strict=True):
        sel = (lam >= lo) & (lam < hi)
        if sel.sum() < 20:
            continue
        print(
            f"    {f'{lo:.1f}-{hi:.1f}':>12}{sel.sum():>8}{lam[sel].mean():>10.3f}"
            f"{real[sel].mean():>9.3f}{lam[sel].mean() - real[sel].mean():>+8.3f}"
        )

    print("\n  EL REPARTO ENTERO, cuántas veces se marcan 0, 1, 2… goles:")
    print(f"    {'goles':>6}{'esperados':>12}{'ocurridos':>12}{'dif':>9}{'%esp':>8}{'%obs':>8}")
    esperado = np.zeros(TOPE + 1)
    for value in lam:
        esperado += reparto(float(value))
    for g in range(0, 8):
        obs = int((real == g).sum()) if g < 7 else int((real >= 7).sum())
        esp = esperado[g] if g < 7 else esperado[7:].sum()
        etiqueta = f"{g}" if g < 7 else "7+"
        print(
            f"    {etiqueta:>6}{esp:>12.1f}{obs:>12}{esp - obs:>+9.1f}"
            f"{esp / len(real):>8.1%}{obs / len(real):>8.1%}"
        )

    # ── 3. Marcadores ─────────────────────────────────────────────────────
    print("\n" + "=" * 84)
    print("MARCADORES, el más probable de la rejilla contra el que ocurrió")
    print("=" * 84)
    aciertos = 0
    marcadores: dict[tuple[int, int], int] = {}
    for i in range(0, len(lam), 2):
        rl, rv = reparto(float(lam[i])), reparto(float(lam[i + 1]))
        rej = np.outer(rl, rv)
        gl, gv = np.unravel_index(int(rej.argmax()), rej.shape)
        marcadores[(int(gl), int(gv))] = marcadores.get((int(gl), int(gv)), 0) + 1
        if (int(gl), int(gv)) == (int(real[i]), int(real[i + 1])):
            aciertos += 1
    total = len(lam) // 2
    print(f"  marcador exacto acertado: {aciertos} de {total} ({aciertos / total:.1%})")
    reales: dict[tuple[int, int], int] = {}
    for i in range(0, len(real), 2):
        clave = (int(real[i]), int(real[i + 1]))
        reales[clave] = reales.get(clave, 0) + 1
    top = max(reales, key=lambda kk: reales[kk])
    print(f"  el listón (decir siempre {top[0]}-{top[1]}): {reales[top] / total:.1%}")
    print("  los marcadores que más propone:")
    for mk, cuantos in sorted(marcadores.items(), key=lambda kv: -kv[1])[:6]:
        print(
            f"    {mk[0]}-{mk[1]}  propuesto {cuantos:>5} veces"
            f"   ocurrió {reales.get(mk, 0):>4}"
        )

    # ── 4. El resultado: la Poisson sola contra las otras dos ─────────────
    print("\n" + "=" * 84)
    print("RESULTADO, la Poisson sola, la ordinal sola y la mezcla de hoy")
    print("=" * 84)
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    diseno = np.array([variables(mi, su) for mi, su in lados])
    k = diseno.shape[1]
    filas_p, filas_o, filas_m, yy_todo = [], [], [], []
    for ini, fin in cortes:
        glm = ajusta_glm(DUELOS_OFENSIVOS, ini)
        ref = OrderedModel(y[:ini], diseno[:ini], distr="logit").fit(
            method="bfgs", disp=False, maxiter=3000
        )
        beta = np.asarray(ref.params[:k], dtype=float)
        u1 = float(ref.params[k])
        umbrales = np.array([u1, u1 + float(np.exp(ref.params[k + 1]))])
        for i in range(ini, fin):
            mi, su = lados[i]
            x = np.array([duelos(DUELOS_OFENSIVOS, mi, su), duelos(DUELOS_OFENSIVOS, su, mi)])
            lm = glm.predict(sm.add_constant(x, has_constant="add"))
            rej = np.outer(reparto(min(lm[0], 12.0)), reparto(min(lm[1], 12.0)))
            v, e, d = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
            t = v + e + d
            filas_p.append([d / t, e / t, v / t])
            eta = float(beta @ diseno[i])
            s1, s2 = 1 / (1 + np.exp(-(umbrales - eta)))
            filas_o.append([s1, s2 - s1, 1 - s2])
            yy_todo.append(int(y[i]))
    pois = np.array(filas_p)
    ordi = np.array(filas_o)
    filas_m = PESO_ORDINAL * ordi + PESO_GOLES * pois
    yy = np.array(yy_todo)
    print(f"  {'modelo':22}{'log-loss':>10}{'aciertos':>10}{'AUC vic':>9}{'AUC emp':>9}")
    for nombre, probs in (
        ("Poisson sola", pois),
        ("ordinal sola", ordi),
        (f"mezcla {PESO_ORDINAL:.0%}/{PESO_GOLES:.0%}", filas_m),
    ):
        print(
            f"  {nombre:22}{log_loss(yy, np.clip(probs, 1e-12, 1), labels=[0, 1, 2]):>10.4f}"
            f"{float((probs.argmax(1) == yy).mean()):>10.3f}"
            f"{roc_auc_score((yy == 2).astype(int), probs[:, 2]):>9.3f}"
            f"{roc_auc_score((yy == 1).astype(int), probs[:, 1]):>9.3f}"
        )
    base = np.bincount(y[: cortes[0][0]], minlength=3) / cortes[0][0]
    print(
        f"  {'no saber nada':22}"
        f"{log_loss(yy, np.tile(base, (len(yy), 1)), labels=[0, 1, 2]):>10.4f}"
    )

    print("\n  DÓNDE SE EQUIVOCA CADA UNA (reparto de las tres clases):")
    print(f"    {'':22}{'derrota':>10}{'empate':>9}{'victoria':>10}")
    print(
        f"    {'ocurrido':22}{(yy == 0).mean():>10.1%}{(yy == 1).mean():>9.1%}"
        f"{(yy == 2).mean():>10.1%}"
    )
    for nombre, probs in (("Poisson sola", pois), ("ordinal sola", ordi), ("mezcla", filas_m)):
        print(
            f"    {nombre:22}{probs[:, 0].mean():>10.1%}{probs[:, 1].mean():>9.1%}"
            f"{probs[:, 2].mean():>10.1%}"
        )
    # ── 5. La compresión, y si alguna forma del duelo la arregla ──────────
    #
    # La calibración por tramos de arriba deja ver un defecto que el log-loss
    # del RESULTADO no puede enseñar: la lambda sale aplastada hacia el
    # centro. Donde promete medio gol se marca 0,13; donde promete tres se
    # marcan 3,4. Eso es una pendiente menor que 1 al regresar lo ocurrido
    # sobre lo prometido, y tiene un sospechoso claro: `A/(A+B)` comprime los
    # extremos por construcción. Aquí se prueba si otra forma del duelo la
    # descomprime, con la misma prueba y los mismos cortes.
    print("\n" + "=" * 84)
    print("LA COMPRESIÓN, ¿la arregla otra forma del duelo?")
    print("=" * 84)

    def t_cociente(a, b):
        return max(a, 1.0) / max(b, 1.0)

    def t_raiz_cociente(a, b):
        return float(np.sqrt(max(a, 1.0) / max(b, 1.0)))

    def t_log_cociente(a, b):
        return float(np.log(max(a, 1.0) / max(b, 1.0)))

    def t_log_proporcion(a, b):
        t = a + b
        return float(np.log(a / t)) if t > 0 and a > 0 else float(np.log(1.0 / (t + 1.0)))

    def t_raices(a, b):
        ra, rb = np.sqrt(max(a, 0.0)), np.sqrt(max(b, 0.0))
        return float(ra / (ra + rb)) if ra + rb > 0 else 0.5

    formas = {
        "A/(A+B)": proporcion,
        "A/B": t_cociente,
        "raiz(A/B)": t_raiz_cociente,
        "log(A/B)": t_log_cociente,
        "log(A/(A+B))": t_log_proporcion,
        "rA/(rA+rB)": t_raices,
    }
    print(
        f"  {'forma':14}{'EAM':>8}{'EC':>8}{'logver':>9}{'pendiente':>11}"
        f"{'sesgo':>8}{'log-loss V/E/D':>16}"
    )
    for nombre, f in formas.items():
        def duelos_f(mio, suyo, f=f):
            return [f(mio[a], suyo[b]) for _, a, b in DUELOS_OFENSIVOS]

        lam_t, real_t, res_t, yy_t = [], [], [], []
        for ini, fin in cortes:
            filas, gg = [], []
            for i, (mi, su) in enumerate(lados[:ini]):
                filas += [duelos_f(mi, su), duelos_f(su, mi)]
                gg += [int(goles_local[i]), int(goles_visit[i])]
            glm = sm.GLM(
                np.array(gg), sm.add_constant(np.array(filas)), family=sm.families.Poisson()
            ).fit()
            for i in range(ini, fin):
                mi, su = lados[i]
                x = np.array([duelos_f(mi, su), duelos_f(su, mi)])
                lm = np.clip(glm.predict(sm.add_constant(x, has_constant="add")), 1e-6, 12.0)
                lam_t += [float(lm[0]), float(lm[1])]
                real_t += [int(goles_local[i]), int(goles_visit[i])]
                rej = np.outer(reparto(float(lm[0])), reparto(float(lm[1])))
                v, e, d = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
                tt = v + e + d
                res_t.append([d / tt, e / tt, v / tt])
                yy_t.append(int(y[i]))
        lm_a, rl_a = np.array(lam_t), np.array(real_t)
        # La PENDIENTE de lo ocurrido sobre lo prometido. Uno sería calibrado;
        # por encima de uno, el modelo se queda corto en los extremos.
        pend = float(np.polyfit(lm_a, rl_a, 1)[0])
        lv = np.mean(
            [
                np.log(max(reparto(a)[min(b, TOPE)], 1e-12))
                for a, b in zip(lm_a, rl_a, strict=True)
            ]
        )
        ll = log_loss(np.array(yy_t), np.clip(np.array(res_t), 1e-12, 1), labels=[0, 1, 2])
        print(
            f"  {nombre:14}{np.abs(lm_a - rl_a).mean():>8.4f}"
            f"{np.sqrt(((lm_a - rl_a) ** 2).mean()):>8.4f}{lv:>9.4f}{pend:>11.4f}"
            f"{(lm_a - rl_a).mean():>+8.4f}{ll:>16.4f}"
        )
    print("\n  pendiente 1 = calibrado · >1 = se queda corto en los extremos")
    _ = modelo_ajustado


if __name__ == "__main__":
    asyncio.run(main())
