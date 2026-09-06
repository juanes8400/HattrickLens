"""Ajusta el modelo de predicción y enseña de qué se le puede acusar.

No basta con que acierte: hay que poder discutirlo. Por eso saca coeficientes
con sus p-valores, pseudo-R², AUC y matriz de aciertos, y todo fuera de la
muestra con la que entrenó.

POR QUÉ FUERA DE MUESTRA. Un modelo evaluado con sus propios datos de
entrenamiento siempre parece bueno: con 9 variables y pocas filas puede
memorizar en vez de aprender. La partición temporal --entrenar con los
partidos viejos y probar con los nuevos-- es además la única honesta aquí,
porque es lo que hará en producción: predecir un partido que todavía no ha
ocurrido con lo aprendido de los que sí.

CADA PARTIDO SE BASTA A SÍ MISMO. Las variables salen de los ratings DEL
PROPIO partido, no de la historia de los equipos. Lo que se aprende es cómo
funciona el motor de Hattrick --una función fija, igual para todos-- y para
medir una función cada observación vale por sí sola.

Predecir un partido futuro es otro problema: allí no se conocen los ratings y
hay que estimarlos de la forma reciente. Ese error vive aparte y no debe
contaminar la calibración de esta parte.

Uso:  python scripts/analizar_prediccion.py [--test 0.25]
"""

import argparse
import asyncio

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _ece(pr: np.ndarray, real: np.ndarray, cajas: int = 10) -> float:
    """Error de calibración: cuánto se desvía lo dicho de lo ocurrido.

    Se reparten las predicciones en cajas por probabilidad y en cada caja se
    compara lo prometido con lo que pasó, pesando por cuántas cayeron ahí.
    Cero sería perfecto, pero cero no se alcanza nunca con muestras finitas
    --por eso `_calibracion` lo compara con lo simulado en vez de con cero--.
    """
    total = 0.0
    for i in range(cajas):
        lo, hi = i / cajas, (i + 1) / cajas + (0.001 if i == cajas - 1 else 0.0)
        sel = (pr >= lo) & (pr < hi)
        if sel.sum():
            total += sel.sum() / len(pr) * abs(pr[sel].mean() - real[sel].mean())
    return total


def _calibracion(prob: np.ndarray, y: np.ndarray) -> None:
    """¿Cuando dice 70 %, ocurre el 70 % de las veces?

    Acertar y estar calibrado son cosas distintas: un modelo puede acertar
    mucho y aun así decir «80 %» donde la verdad es 60 %. En una pantalla que
    enseña porcentajes, la calibración es lo que hace que el número signifique
    algo; sin ella el usuario lee una cifra que no puede usar.

    NO SE COMPARA CON CERO, SE COMPARA CON LO POSIBLE. Con pocos partidos,
    hasta un modelo perfecto da error de calibración: la moneda cargada al
    70 % no sale cara exactamente 7 de cada 10 veces. Así que se simulan dos
    mil mundos en los que el modelo acierta EXACTO --tirando el resultado de
    cada partido con la probabilidad que él mismo dio-- y se mira si el error
    real cabe entre lo que sale ahí. Si cabe, no hay nada que corregir; si se
    sale, está descalibrado de verdad y no por falta de datos.
    """
    rng = np.random.default_rng(20260905)
    print()
    print("=" * 72)
    print(f"CALIBRACIÓN — contra 2.000 mundos simulados con estos {len(y)} partidos")
    print("=" * 72)
    print(f"  {'clase':10}{'ECE real':>10}{'mediana':>10}{'p95':>8}{'p':>7}  veredicto")
    for k, nom in enumerate(("victoria", "empate", "derrota")):
        pr = prob[:, k]
        obs = _ece(pr, (y == k).astype(int))
        sim = np.array(
            [_ece(pr, (rng.random(len(y)) < pr).astype(int)) for _ in range(2000)]
        )
        p95 = float(np.quantile(sim, 0.95))
        veredicto = "calibrada" if obs <= p95 else "DESCALIBRADA"
        print(
            f"  {nom:10}{obs:>10.3f}{np.median(sim):>10.3f}{p95:>8.3f}"
            f"{float((sim >= obs).mean()):>7.2f}  {veredicto}"
        )
    print()
    print("  esperados contra ocurridos:")
    for k, nom in enumerate(("victoria", "empate", "derrota")):
        print(
            f"    {nom:10} el modelo esperaba {prob[:, k].sum():>5.0f},"
            f" ocurrieron {(y == k).sum():>4}"
        )


def _proporciones(p) -> list[float]:  # noqa: ANN001 — fila de ORM
    """Las nueve comparaciones cruzadas, desde el local."""
    from app.domain.engines.prediccion import COMPARACIONES, proporcion

    return [
        proporcion(float(getattr(p, f"home_{mio}")), float(getattr(p, f"away_{suyo}")))
        for _, mio, suyo in COMPARACIONES
    ]


async def main(fraccion_prueba: float) -> None:
    import statsmodels.api as sm
    from sklearn.metrics import confusion_matrix, roc_auc_score

    from app.core.config import settings
    from app.domain.engines.prediccion import COMPARACIONES
    from app.infrastructure.db import models as m

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        partidos = list(
            (
                await session.execute(
                    select(m.TrainingMatch).order_by(m.TrainingMatch.ht_match_id)
                )
            ).scalars()
        )
    if len(partidos) < 50:
        raise SystemExit(f"Sólo hay {len(partidos)} partidos: muy pocos para analizar")

    nombres = [c[0] for c in COMPARACIONES]
    diseno = np.array([_proporciones(p) for p in partidos])
    # 0 victoria local, 1 empate, 2 derrota local.
    y = np.array(
        [0 if p.home_goals > p.away_goals else (1 if p.home_goals == p.away_goals else 2)
         for p in partidos]
    )

    corte = int(len(y) * (1 - fraccion_prueba))
    x_ent, x_pru = diseno[:corte], diseno[corte:]
    y_ent, y_pru = y[:corte], y[corte:]
    print(f"{len(y)} partidos · entrenan {len(y_ent)} · prueban {len(y_pru)}")
    print("reparto entrenamiento:", {n: int((y_ent == i).sum())
                                     for i, n in enumerate(("victoria", "empate", "derrota"))})
    print("reparto prueba       :", {n: int((y_pru == i).sum())
                                     for i, n in enumerate(("victoria", "empate", "derrota"))})

    # ── Multinomial: las tres clases a la vez ────────────────────────────
    print("\n" + "=" * 72)
    print("MULTINOMIAL (victoria / empate / derrota) — base: victoria local")
    print("=" * 72)
    modelo = sm.MNLogit(y_ent, sm.add_constant(x_ent)).fit(disp=False, maxiter=200)
    etiquetas = ["(intercepto)"] + nombres
    for k, clase in enumerate(("empate", "derrota")):
        print(f"\n  frente a VICTORIA, la clase «{clase}»:")
        # `params` viene como (variables x clases): la fila es la variable y
        # la columna la clase. Al revés compila y da números plausibles del
        # sitio equivocado, que es la peor clase de error.
        print(f"    {'variable':14}{'coef':>9}{'error':>9}{'z':>8}{'p-valor':>10}{'x10pp':>8}")
        for i, nom in enumerate(etiquetas):
            coef = float(modelo.params[i, k])
            err = float(modelo.bse[i, k])
            pv = float(modelo.pvalues[i, k])
            estrella = "***" if pv < 0.001 else ("**" if pv < 0.01 else ("*" if pv < 0.05 else ""))
            z = coef / err if err else 0.0
            # Las proporciones viven en [0, 1], así que un coeficiente «por
            # unidad» sería el salto de perderlo todo a ganarlo todo. La
            # columna x10pp lo traduce a algo legible: cuánto se multiplican
            # las probabilidades relativas por cada 10 puntos porcentuales.
            razon = "" if nom == "(intercepto)" else f"{np.exp(coef * 0.1):>8.2f}"
            print(
                f"    {nom:14}{coef:>9.3f}{err:>9.3f}{z:>8.2f}{pv:>10.4f}{razon} {estrella}"
            )
    print(f"\n  pseudo-R² (McFadden): {modelo.prsquared:.4f}")
    print(f"  log-verosimilitud   : {modelo.llf:.1f}   (modelo vacío {modelo.llnull:.1f})")

    # ── Fuera de muestra ─────────────────────────────────────────────────
    prob = modelo.predict(sm.add_constant(x_pru))
    pred = prob.argmax(axis=1)
    print("\n" + "=" * 72)
    print("FUERA DE MUESTRA")
    print("=" * 72)
    acierto = float((pred == y_pru).mean())
    # La comparación honesta: acertar siempre la clase más común. Un modelo que
    # no supere esto no ha aprendido nada, por muy alto que suene su acierto.
    mayoritaria = float((y_pru == np.bincount(y_ent).argmax()).mean())
    print(f"  aciertos           : {acierto:.3f}")
    print(f"  siempre la más común: {mayoritaria:.3f}   ← el listón a superar")

    print("\n  matriz de confusión (filas = real, columnas = predicho)")
    cm = confusion_matrix(y_pru, pred, labels=[0, 1, 2])
    print(f"    {'':10}{'vict':>7}{'emp':>7}{'derr':>7}")
    for i, nom in enumerate(("victoria", "empate", "derrota")):
        print(f"    {nom:10}" + "".join(f"{v:>7}" for v in cm[i]))

    print("\n  AUC uno-contra-el-resto:")
    for i, nom in enumerate(("victoria", "empate", "derrota")):
        binaria = (y_pru == i).astype(int)
        if binaria.sum() in (0, len(binaria)):
            print(f"    {nom:10} sin casos en la muestra de prueba")
            continue
        print(f"    {nom:10} {roc_auc_score(binaria, prob[:, i]):.3f}")

    _calibracion(np.asarray(prob), y_pru)

    # ── Binario victoria/derrota, que es donde el AUC se lee mejor ────────
    print("\n" + "=" * 72)
    print("BINARIO: victoria local contra derrota local (sin empates)")
    print("=" * 72)
    sin_e_ent = y_ent != 1
    sin_e_pru = y_pru != 1
    b_ent = (y_ent[sin_e_ent] == 0).astype(int)
    b_pru = (y_pru[sin_e_pru] == 0).astype(int)
    logit = sm.Logit(b_ent, sm.add_constant(x_ent[sin_e_ent])).fit(disp=False, maxiter=200)
    print(f"    {'variable':14}{'coef':>9}{'error':>9}{'p-valor':>10}{'x10pp':>8}")
    for i, nom in enumerate(etiquetas):
        pv = float(logit.pvalues[i])
        coef = float(logit.params[i])
        estrella = "***" if pv < 0.001 else ("**" if pv < 0.01 else ("*" if pv < 0.05 else ""))
        razon = "" if nom == "(intercepto)" else f"{np.exp(coef * 0.1):>8.2f}"
        print(f"    {nom:14}{coef:>9.3f}{logit.bse[i]:>9.3f}{pv:>10.4f}{razon} {estrella}")
    print(f"\n  pseudo-R² (McFadden): {logit.prsquared:.4f}")
    pb = logit.predict(sm.add_constant(x_pru[sin_e_pru]))
    print(f"  AUC fuera de muestra: {roc_auc_score(b_pru, pb):.3f}")
    print(f"  aciertos            : {float(((pb > 0.5).astype(int) == b_pru).mean()):.3f}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--test", type=float, default=0.25, help="fracción para probar")
    a = p.parse_args()
    asyncio.run(main(a.test))
