"""El mediocampo como MULTIPLICADOR, contra 84 estructuras distintas.

LA IDEA. Hasta hoy los nueve duelos entran sumados: el mediocampo es un
sumando más, igual que el ataque izquierdo. Pero en Hattrick el mediocampo no
es otro sector: decide la POSESIÓN, y la posesión no se suma a tus ataques,
los multiplica. Dominar el medio no vale un número fijo de puntos, vale un
porcentaje más de las ocasiones que tus ataques generan.

    hoy:      eta = b_medio*medio + suma(b_zona * zona)
    a probar: eta = b_medio*medio + m(medio) * suma(b_zona * zona)

POR QUÉ SE PUEDE AJUSTAR IGUAL. Si `m` no lleva parámetros libres dentro,
`m * zona` es sólo otra columna y el modelo sigue siendo lineal en sus
coeficientes: `OrderedModel` lo ajusta sin cambiar nada. Por eso el
multiplicador se declara como una función CERRADA del mediocampo y no como
algo que la regresión tenga que aprender.

DOS ARMAZONES, no una. En la primera el mediocampo conserva su sumando
propio Y multiplica a las otras ocho: nueve coeficientes, once parámetros. En
la segunda --preguntada el 2026-09-07-- el mediocampo NO es una variable y
sólo existe como multiplicador: ocho coeficientes, diez parámetros. El AIC
compara las dos sin trampa porque castiga el parámetro de más.

LO QUE SALIÓ, sobre 5.232 partidos y cinco cortes:

    1  medio suelto  A/(A+B)  sin multiplicador   0,6445  AIC 7036,5  (11 par.)
    2  solo zonas    A/(A+B)  x raiz(2p)          0,6447  AIC 7033,6  (10 par.)
    3  medio suelto  A/(A+B)  x raiz(2p)          0,6449  AIC 7035,6  (11 par.)
   57  solo zonas    A/(A+B)  sin multiplicador   0,7032  AIC 7595,2  (10 par.)

La 2ª empata en predicción con la 1ª (+0,0002, y gana 3 de los 5 cortes) con
un parámetro menos, y tiene el MEJOR AIC de las 84. La 57ª es el control: sin
mediocampo y sin multiplicador el modelo se cae, o sea que el multiplicador
sí está haciendo el trabajo del mediocampo. Elegir entre la 1ª y la 2ª no lo
deciden estos datos.

TODOS LOS MULTIPLICADORES VALEN 1 EN LA IGUALDAD, para que la estructura de
hoy sea literalmente el caso `m = 1` y no una parametrización distinta.

SE TIPIFICAN LAS COLUMNAS antes de ajustar, con la media y la desviación del
TRAMO DE ENTRENAMIENTO nada más. No cambia el modelo --es una reescritura
lineal, misma verosimilitud y mismas probabilidades-- pero sin eso los
productos de dos cocientes sin techo (`A/B` por `A/B`) llegan a valer miles y
el BFGS no converge.

Uso:  python scripts/rejilla_de_estructuras.py
"""

import asyncio
import time
import warnings

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")

# ── Las seis formas de medir un duelo ────────────────────────────────────
#
# Todas son monótonas en A/B, así que ORDENAN los duelos igual; lo que cambia
# es cómo entran a una suma en línea recta. Entre paréntesis, lo que vale un
# duelo igualado en cada una.


def t_proporcion(a, b):  # 0,5
    t = a + b
    return a / t if t > 0 else 0.5


def t_cociente(a, b):  # 1
    return max(a, 1.0) / max(b, 1.0)


def t_raiz_cociente(a, b):  # 1, la cola de A/B, domada
    return float(np.sqrt(max(a, 1.0) / max(b, 1.0)))


def t_log_cociente(a, b):  # 0
    return float(np.log(max(a, 1.0) / max(b, 1.0)))


def t_log_proporcion(a, b):  # -0,693
    t = a + b
    return float(np.log(a / t)) if t > 0 and a > 0 else float(np.log(1.0 / (t + 1.0)))


def t_proporcion_de_raices(a, b):  # 0,5, comprime menos que A/(A+B)
    ra, rb = np.sqrt(max(a, 0.0)), np.sqrt(max(b, 0.0))
    return float(ra / (ra + rb)) if ra + rb > 0 else 0.5


TRANSFORMACIONES = {
    "A/(A+B)": t_proporcion,
    "A/B": t_cociente,
    "raiz(A/B)": t_raiz_cociente,
    "log(A/B)": t_log_cociente,
    "log(A/(A+B))": t_log_proporcion,
    "rA/(rA+rB)": t_proporcion_de_raices,
}

# ── Los siete multiplicadores de posesión ────────────────────────────────
#
# Reciben la PROPORCIÓN del mediocampo, `p = medio_mio / (medio_mio + suyo)`,
# y devuelven cuánto escalan las otras ocho zonas. Los siete valen 1 en p=0,5.
# Se acotan por arriba: `A/B` del mediocampo puede valer 68 en los datos, y
# multiplicado por un duelo de zona daría columnas de miles.

TOPE = 4.0


def m_ninguno(p):  # la estructura de hoy
    return 1.0


def m_lineal(p):  # 0 sin medio, 1 igualados, 2 con todo
    return 2.0 * p


def m_raiz(p):  # más suave que lineal
    return float(np.sqrt(2.0 * p))


def m_cuadratico(p):  # más agresivo que lineal
    return min((2.0 * p) ** 2, TOPE)


def m_cociente(p):  # p/(1-p): sin techo, el más agresivo
    return min(p / (1.0 - p) if p < 1.0 else TOPE, TOPE)


def m_raiz_cociente(p):
    return min(float(np.sqrt(p / (1.0 - p))) if p < 1.0 else TOPE, TOPE)


def m_exponencial(p):  # e^(2p-1): suave y siempre positivo
    return min(float(np.exp(2.0 * p - 1.0)), TOPE)


MULTIPLICADORES = {
    "1 (aditivo)": m_ninguno,
    "2p": m_lineal,
    "raiz(2p)": m_raiz,
    "(2p)^2": m_cuadratico,
    "p/(1-p)": m_cociente,
    "raiz(p/(1-p))": m_raiz_cociente,
    "e^(2p-1)": m_exponencial,
}


def terna(beta, umbrales, x):
    eta = float(np.asarray(beta) @ np.asarray(x))
    s1, s2 = 1 / (1 + np.exp(-(np.asarray(umbrales) - eta)))
    return np.array([s1, s2 - s1, 1 - s2])


async def main() -> None:
    from sklearn.metrics import log_loss, roc_auc_score
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        COMPARACIONES,
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
    y = np.array([resultado(p) for p in partidos])
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    n = len(partidos)
    print(
        f"{n} partidos de liga · 2 armazones x {len(TRANSFORMACIONES)} duelos "
        f"x {len(MULTIPLICADORES)} multiplicadores = "
        f"{2 * len(TRANSFORMACIONES) * len(MULTIPLICADORES)} estructuras\n"
    )

    # El mediocampo es siempre la PRIMERA de COMPARACIONES; se comprueba en
    # vez de darlo por supuesto, porque si algún día cambia el orden esto
    # multiplicaría la columna equivocada sin avisar.
    assert COMPARACIONES[0][0] == "medio", "el mediocampo tiene que ir primero"

    #: `p` del mediocampo de cada partido, que es lo que alimenta el
    #: multiplicador. Se calcula una vez.
    p_medio = np.array([t_proporcion(mi["midfield"], su["midfield"]) for mi, su in lados])

    def diseno(nombre_t, nombre_m, con_medio):
        """La matriz de una estructura.

        `con_medio` decide la ARMAZÓN, que es la segunda cosa que se compara:

          True, el mediocampo lleva su propio coeficiente Y multiplica a las
                  otras ocho. Nueve columnas, once parámetros.
          False, el mediocampo NO es una variable: sólo existe como
                  multiplicador de las otras ocho. Ocho columnas, diez
                  parámetros. Es la pregunta del 2026-09-07: ¿basta con que la
                  posesión escale, sin sumar por sí misma?

        LA ARMAZÓN SIN MEDIOCAMPO NO LE SIRVE A CUALQUIER FORMA, y se dejó
        que saliera en los números en vez de excluir nada por adelantado.

        Con `log(A/B)`, cuyo neutro es 0, las ocho zonas igualadas suman 0 y
        el multiplicador multiplica a cero: el mediocampo deja de decir nada
        justo en el partido más parejo, que es donde más falta hace. Sale
        entre 0,71 y 0,73, malo.

        Con `log(A/(A+B))` es peor y no era lo que yo esperaba: todos sus
        valores son negativos (de -4,52 a -0,011), así que la suma es un
        número grande y negativo casi constante y el multiplicador se
        convierte en una palanca sobre esa constante. Sale entre 0,84 y 0,93,
        o sea a un pelo de no saber nada (0,98). Las seis peores de las 84
        son exactamente esas.

        Con `A/(A+B)` (neutro 0,5) la armazón funciona, y de hecho da la
        segunda mejor de las 84.
        """
        f = TRANSFORMACIONES[nombre_t]
        g = MULTIPLICADORES[nombre_m]
        filas = []
        for i, (mi, su) in enumerate(lados):
            mult = g(float(p_medio[i]))
            fila = [f(mi[a], su[b]) for _, a, b in COMPARACIONES]
            zonas = [v * mult for v in fila[1:]]
            filas.append(([fila[0]] + zonas) if con_medio else zonas)
        return np.array(filas, dtype=float)

    cortes = [(int(n * f), int(n * (f + 0.12))) for f in (0.40, 0.52, 0.64, 0.76, 0.88)]

    def evalua(d, k):
        """Origen móvil sobre una estructura ya construida.

        `k` es el número de columnas, que ya no es siempre nueve: la armazón
        sin mediocampo tiene ocho."""
        perdidas, aciertos, aucs = [], [], []
        for ini, fin in cortes:
            ent, pru = d[:ini], d[ini:fin]
            # Tipificado con lo del tramo de entrenamiento, nunca con lo que
            # se va a predecir.
            mu, sd = ent.mean(axis=0), ent.std(axis=0)
            sd = np.where(sd > 1e-12, sd, 1.0)
            ref = OrderedModel(y[:ini], (ent - mu) / sd, distr="logit").fit(
                method="bfgs", disp=False, maxiter=5000
            )
            beta = np.asarray(ref.params[:k], dtype=float)
            u1 = float(ref.params[k])
            umbrales = np.array([u1, u1 + float(np.exp(ref.params[k + 1]))])
            probs = np.array([terna(beta, umbrales, x) for x in (pru - mu) / sd])
            if not np.all(np.isfinite(probs)):
                return None
            yy = y[ini:fin]
            perdidas.append(log_loss(yy, np.clip(probs, 1e-12, 1), labels=[0, 1, 2]))
            aciertos.append(float((probs.argmax(1) == yy).mean()))
            aucs.append(
                [
                    roc_auc_score((yy == 2).astype(int), probs[:, 2]),
                    roc_auc_score((yy == 0).astype(int), probs[:, 0]),
                    roc_auc_score((yy == 1).astype(int), probs[:, 1]),
                ]
            )
        return (
            float(np.mean(perdidas)),
            float(np.std(perdidas)),
            float(np.mean(aciertos)),
            np.array(aucs).mean(axis=0),
            np.array(perdidas),
        )

    armazones = {"medio suelto + zonas x m": True, "solo zonas x m": False}

    resultados = []
    empezo = time.time()
    for etiqueta, con_medio in armazones.items():
        for nombre_t in TRANSFORMACIONES:
            for nombre_m in MULTIPLICADORES:
                d = diseno(nombre_t, nombre_m, con_medio)
                # AIC dentro de muestra, con las mismas columnas tipificadas.
                mu, sd = d.mean(axis=0), d.std(axis=0)
                sd = np.where(sd > 1e-12, sd, 1.0)
                try:
                    completo = OrderedModel(y, (d - mu) / sd, distr="logit").fit(
                        method="bfgs", disp=False, maxiter=5000
                    )
                    aic = float(completo.aic)
                except Exception:  # noqa: BLE001, la que no converge se reporta
                    aic = float("nan")
                fuera = evalua(d, d.shape[1])
                if fuera is None:
                    print(f"  {etiqueta:26}{nombre_t:14}{nombre_m:16} NO CONVERGE")
                    continue
                ll, sdll, ac, auc, por_corte = fuera
                resultados.append(
                    (etiqueta, nombre_t, nombre_m, ll, sdll, ac, auc, aic, por_corte)
                )
                print(
                    f"  {etiqueta:26}{nombre_t:14}{nombre_m:16}{ll:>9.4f}{sdll:>7.3f}"
                    f"{ac:>8.3f}{auc[0]:>8.3f}{aic:>10.1f}   ({time.time() - empezo:5.0f}s)"
                )

    base = next(
        r
        for r in resultados
        if r[0] == "medio suelto + zonas x m"
        and r[1] == "A/(A+B)"
        and r[2] == "1 (aditivo)"
    )
    resultados.sort(key=lambda r: r[3])

    print("\n" + "=" * 108)
    print(f"LAS {len(resultados)} ESTRUCTURAS, ordenadas por log-loss fuera de muestra")
    print("=" * 108)
    print(
        f"  {'#':>3} {'armazon':26}{'duelo':14}{'multiplicador':16}{'log-loss':>9}{'±':>7}"
        f"{'aciertos':>9}{'AUC vic':>9}{'AIC':>10}{'vs hoy':>9}{'gana':>6}"
    )
    for i, (et, nt, nm, ll, sdll, ac, auc, aic, por_corte) in enumerate(resultados, 1):
        gana = int((por_corte < base[8]).sum())
        marca = "  <- hoy" if (et, nt, nm) == (base[0], base[1], base[2]) else ""
        print(
            f"  {i:>3} {et:26}{nt:14}{nm:16}{ll:>9.4f}{sdll:>7.3f}{ac:>9.3f}"
            f"{auc[0]:>9.3f}{aic:>10.1f}{ll - base[3]:>+9.4f}{gana:>4}/5{marca}"
        )

    print("\n  lo mejor de cada armazon:")
    for etiqueta in armazones:
        fila = next(r for r in resultados if r[0] == etiqueta)
        print(f"    {etiqueta:26}{fila[1]:14}{fila[2]:16}{fila[3]:>9.4f}")

    suelo = []
    for ini, fin in cortes:
        b = np.bincount(y[:ini], minlength=3) / ini
        suelo.append(log_loss(y[ini:fin], np.tile(b, (fin - ini, 1)), labels=[0, 1, 2]))
    print(f"\n  el listón (no saber nada): {np.mean(suelo):.4f}")

    mejor = resultados[0]
    print("\n" + "=" * 92)
    print("EL MEJOR CONTRA EL DE HOY, corte a corte")
    print("=" * 92)
    print(f"  mejor : {mejor[0]} · {mejor[1]} · multiplicador {mejor[2]}")
    print(f"  hoy   : {base[0]} · {base[1]} · multiplicador {base[2]}")
    print(f"\n  {'corte':>7}{'hoy':>12}{'mejor':>12}{'diferencia':>13}")
    for i, (ini, _) in enumerate(cortes):
        print(
            f"  {ini:>7}{base[8][i]:>12.4f}{mejor[8][i]:>12.4f}"
            f"{mejor[8][i] - base[8][i]:>+13.4f}"
        )
    ganados = int((mejor[8] < base[8]).sum())
    print(f"\n  el mejor gana en {ganados} de {len(cortes)} cortes")
    if ganados < len(cortes):
        print("  OJO: si no gana los cinco, la ventaja media puede ser del reparto")
        print("  de los cortes y no de la estructura.")


if __name__ == "__main__":
    asyncio.run(main())
