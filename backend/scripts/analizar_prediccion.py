"""Ajusta el modelo de predicción y enseña de qué se le puede acusar.

No basta con que acierte: hay que poder discutirlo. Por eso saca coeficientes
con sus p-valores, pseudo-R², AUC, calibración y matriz de aciertos, y todo
fuera de la muestra con la que entrenó.

QUÉ AJUSTA. Una regresión logística ORDINAL: victoria, empate y derrota están
ordenadas, así que un solo juego de nueve coeficientes más dos umbrales basta
--once parámetros-- donde un multinomial gastaba veinte para el mismo ajuste.

DÓNDE VIVE EL RESULTADO. Los coeficientes que imprime este guion se copian a
mano al motor. Producción no ajusta nada: los 1.031 partidos no viajan al
servidor y el servidor sólo aplica aritmética.

POR QUÉ FUERA DE MUESTRA. Un modelo evaluado con sus propios datos de
entrenamiento siempre parece bueno. La partición temporal --entrenar con los
partidos viejos y probar con los nuevos-- es además la única honesta aquí,
porque es lo que hará en producción.

CADA PARTIDO SE BASTA A SÍ MISMO. Las variables salen de los ratings DEL
PROPIO partido, no de la historia de los equipos. Lo que se aprende es cómo
funciona el motor de Hattrick --una función fija, igual para todos-- y para
medir una función cada observación vale por sí sola.

Uso:  python scripts/analizar_prediccion.py [--test 0.25]
"""

import argparse
import asyncio

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")


def _ece(pr: np.ndarray, real: np.ndarray, cajas: int = 10) -> float:
    """Error de calibración: cuánto se desvía lo dicho de lo ocurrido.

    Se reparten las predicciones en cajas por probabilidad y en cada caja se
    compara lo prometido con lo que pasó, pesando por cuántas cayeron ahí.
    Cero sería perfecto, pero cero no se alcanza nunca con muestras finitas
    --por eso `_calibracion` lo compara con lo simulado y no con cero--.
    """
    total = 0.0
    for i in range(cajas):
        lo, hi = i / cajas, (i + 1) / cajas + (0.001 if i == cajas - 1 else 0.0)
        sel = (pr >= lo) & (pr < hi)
        if sel.sum():
            total += sel.sum() / len(pr) * abs(pr[sel].mean() - real[sel].mean())
    return total


def _calibracion(prob: np.ndarray, y: np.ndarray, y_ent: np.ndarray | None = None) -> None:
    """¿Cuando dice 70 %, ocurre el 70 % de las veces?

    Acertar y estar calibrado son cosas distintas: un modelo puede acertar
    mucho y aun así decir «80 %» donde la verdad es 60 %. En una pantalla que
    enseña porcentajes, la calibración es lo que hace que el número signifique
    algo.

    NO SE COMPARA CON CERO, SE COMPARA CON LO POSIBLE. Con pocos partidos,
    hasta un modelo perfecto da error de calibración: la moneda cargada al
    70 % no sale cara exactamente 7 de cada 10 veces. Así que se simulan dos
    mil mundos en los que el modelo acierta EXACTO --tirando el resultado de
    cada partido con la probabilidad que él mismo dio-- y se mira si el error
    real cabe entre lo que sale ahí.
    """
    rng = np.random.default_rng(20260905)
    print()
    print("=" * 72)
    print(f"CALIBRACIÓN — contra 2.000 mundos simulados con estos {len(y)} partidos")
    print("=" * 72)
    print(f"  {'clase':10}{'ECE real':>10}{'mediana':>10}{'p95':>8}{'p':>7}  veredicto")
    for k, nom in enumerate(CLASES):
        pr = prob[:, k]
        obs = _ece(pr, (y == k).astype(int))
        sim = np.array([_ece(pr, (rng.random(len(y)) < pr).astype(int)) for _ in range(2000)])
        p95 = float(np.quantile(sim, 0.95))
        print(
            f"  {nom:10}{obs:>10.3f}{np.median(sim):>10.3f}{p95:>8.3f}"
            f"{float((sim >= obs).mean()):>7.2f}  "
            f"{'calibrada' if obs <= p95 else 'DESCALIBRADA'}"
        )
    print()
    print("  esperados contra ocurridos:")
    for k, nom in enumerate(CLASES):
        print(
            f"    {nom:10} el modelo esperaba {prob[:, k].sum():>5.0f},"
            f" ocurrieron {(y == k).sum():>4}"
        )
    if y_ent is None:
        return
    # Sin esto, una diferencia entre esperado y ocurrido se lee como defecto
    # del modelo cuando muchas veces es que al bloque de medida le tocaron más
    # empates de la cuenta. El modelo aprende la tasa que ve; si la de medida
    # es otra, no falla él, cambió el trozo.
    print()
    print("  la tasa de cada clase cambia entre bloques, y eso mueve lo de arriba:")
    print(f"    {'clase':10}{'entrenamiento':>15}{'medida':>10}")
    for k, nom in enumerate(CLASES):
        print(f"    {nom:10}{(y_ent == k).mean():>15.1%}{(y == k).mean():>10.1%}")


def _del_ajuste(ajuste, k: int, n: int, escala: float | None = None):
    """El modelo del motor, cargado con lo que devolvió statsmodels.

    Los dos últimos parámetros son el primer umbral y el LOGARITMO de la
    distancia al segundo, no los dos umbrales sueltos.

    `escala` aplana la recta latente igual que hace el motor. Se aplica aquí
    también para que lo que se mide sea lo que el usuario verá: sin ella, el
    informe describiría un modelo distinto del que corre.
    """
    from app.domain.engines.prediccion import ESCALA, ModeloOrdinal

    s = ESCALA if escala is None else escala
    primero = float(ajuste.params[k])
    return ModeloOrdinal(
        beta=np.asarray(ajuste.params[:k], dtype=float) / s,
        umbrales=np.array([primero, primero + float(np.exp(ajuste.params[k + 1]))]) / s,
        observaciones=n,
    )


async def main(fraccion_prueba: float) -> None:
    from sklearn.metrics import confusion_matrix, log_loss, roc_auc_score
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        COMPARACIONES,
        ESCALA,
        ETIQUETAS,
        tabla_de_entrenamiento,
    )
    from app.infrastructure.db import models as m

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        partidos = list(
            (
                await session.execute(select(m.TrainingMatch).order_by(m.TrainingMatch.ht_match_id))
            ).scalars()
        )
    diseno, y, _ = tabla_de_entrenamiento(partidos)
    if len(y) < 50:
        raise SystemExit(f"Sólo hay {len(y)} partidos: muy pocos para analizar")

    corte = int(len(y) * (1 - fraccion_prueba))
    x_ent, x_pru = diseno[:corte], diseno[corte:]
    y_ent, y_pru = y[:corte], y[corte:]
    print(f"{len(y)} partidos · entrenan {len(y_ent)} · prueban {len(y_pru)}")
    for nombre, etiquetas in (("entrenamiento", y_ent), ("prueba", y_pru)):
        reparto = {n: int((etiquetas == i).sum()) for i, n in enumerate(CLASES)}
        print(f"  reparto {nombre:14} {reparto}")

    # Ajusta statsmodels y el resultado se APLICA con la clase del motor, que
    # es la que corre en producción. Así lo que se mide aquí abajo pasa por
    # exactamente la misma aritmética que verá el usuario.
    #
    # El segundo umbral viene como logaritmo de la distancia al primero: esa
    # parametrización es la que impide que se crucen durante el ajuste.
    k = len(COMPARACIONES)
    ref = OrderedModel(y_ent, x_ent, distr="logit").fit(method="bfgs", disp=False, maxiter=800)
    mio = _del_ajuste(ref, k, len(y_ent))

    print()
    print("=" * 72)
    print("REGRESIÓN ORDINAL — derrota < empate < victoria")
    print("=" * 72)
    print(f"  {'duelo':26}{'coef':>9}{'error':>8}{'z':>7}{'p-valor':>10}{'x10pp':>8}")
    for i, (nombre, _, _) in enumerate(COMPARACIONES):
        # Los coeficientes se enseñan CRUDOS, tal como los devolvió la
        # regresión: son los que hay que poder discutir. La escala es un paso
        # posterior y se declara aparte, no disuelta en los números.
        coef, err, pv = float(ref.params[i]), float(ref.bse[i]), float(ref.pvalues[i])
        estrella = "***" if pv < 0.001 else ("**" if pv < 0.01 else ("*" if pv < 0.05 else ""))
        # Los duelos viven en [0, 1], así que un coeficiente «por unidad»
        # sería el salto de perderlo todo a ganarlo todo. x10pp lo traduce:
        # cuánto se multiplican las probabilidades relativas de acabar más
        # arriba por cada 10 puntos porcentuales que uno se lleva del duelo.
        print(
            f"  {ETIQUETAS[nombre]:26}{coef:>9.3f}{err:>8.3f}{coef / err if err else 0:>7.2f}"
            f"{pv:>10.4f}{np.exp(coef * 0.1):>8.2f} {estrella}"
        )
    # Crudos, como los coeficientes de arriba: en la misma tabla no pueden
    # convivir unos números escalados y otros sin escalar.
    umbral_crudo = float(ref.params[k])
    print(
        f"\n  umbrales: {umbral_crudo:.3f} y "
        f"{umbral_crudo + float(np.exp(ref.params[k + 1])):.3f}"
    )
    print(f"  escala de calibración que se aplica después: {ESCALA}")
    print(f"  pseudo-R² (McFadden): {ref.prsquared:.4f}")
    print(f"  log-verosimilitud   : {ref.llf:.1f}   (modelo vacío {ref.llnull:.1f})")

    prob = np.array(
        [[p.derrota, p.empate, p.victoria] for p in (mio.probabilidades(x) for x in x_pru)]
    )
    pred = prob.argmax(axis=1)
    print()
    print("=" * 72)
    print("FUERA DE MUESTRA")
    print("=" * 72)
    # El listón: acertar siempre la clase más común. Un modelo que no lo supere
    # no ha aprendido nada, por muy alto que suene su porcentaje de aciertos.
    mayoritaria = float((y_pru == np.bincount(y_ent).argmax()).mean())
    print(f"  aciertos            : {float((pred == y_pru).mean()):.3f}")
    print(f"  siempre la más común: {mayoritaria:.3f}   <- el liston a superar")
    print(f"  log-loss            : {log_loss(y_pru, prob, labels=[0, 1, 2]):.3f}")

    print("\n  matriz de confusión (filas = real, columnas = predicho)")
    cm = confusion_matrix(y_pru, pred, labels=[0, 1, 2])
    print(f"    {'':10}{'derr':>7}{'emp':>7}{'vict':>7}")
    for i, nom in enumerate(CLASES):
        print(f"    {nom:10}" + "".join(f"{v:>7}" for v in cm[i]))

    print("\n  AUC uno-contra-el-resto:")
    for i, nom in enumerate(CLASES):
        binaria = (y_pru == i).astype(int)
        if binaria.sum() in (0, len(binaria)):
            print(f"    {nom:10} sin casos en la muestra de prueba")
            continue
        print(f"    {nom:10} {roc_auc_score(binaria, prob[:, i]):.3f}")

    _calibracion(prob, y_pru, y_ent)

    print()
    print("=" * 72)
    print("PARA COPIAR AL MOTOR")
    print("=" * 72)
    # Se reajusta con TODO antes de copiar: la partición existe para medir, no
    # para producir el modelo final. Una vez medido, tirar un cuarto de los
    # datos sería regalar precisión.
    completo = OrderedModel(y, diseno, distr="logit").fit(
        method="bfgs", disp=False, maxiter=2000
    )
    # CRUDOS, sin escalar. El motor divide por `ESCALA` al cargarlos; pegar
    # aquí los ya escalados los dividiría dos veces y aplanaría el modelo
    # hasta dejarlo casi mudo, sin que nada fallara ni avisara.
    print("BETA = (")
    for i, (nombre, _, _) in enumerate(COMPARACIONES):
        print(f"    {float(completo.params[i]):>9.5f},  # {ETIQUETAS[nombre]}")
    print(")")
    primero = float(completo.params[k])
    print(f"UMBRALES = ({primero:.5f}, {primero + float(np.exp(completo.params[k + 1])):.5f})")
    print(f"OBSERVACIONES = {len(y)}")
    print(f"ESCALA = {ESCALA}   # no sale de este ajuste: se elige aparte")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--test", type=float, default=0.25, help="fracción para probar")
    a = p.parse_args()
    asyncio.run(main(a.test))
