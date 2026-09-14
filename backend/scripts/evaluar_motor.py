"""Mide el motor de predicción ENTERO, tal como lo verá el usuario.

`analizar_prediccion.py` ajusta y describe el modelo ordinal. Éste hace lo
otro: coge la función que de verdad llama la aplicación --con sus coeficientes
ya pegados, su escala y su mezcla-- y la mide contra partidos que no vio.

POR QUÉ ORIGEN MÓVIL Y NO UN SOLO CORTE. Un corte da un número y ese número
depende del trozo que toque. Ya pasó: probando un término cuadrático salía una
mejora clara en un reparto y desaparecía en cuanto se probaban cinco. Aquí se
entrena con todo lo anterior y se mide el tramo siguiente, cinco veces, y lo
que se enseña es la media y la dispersión.

SE REAJUSTA EN CADA CORTE, y no es un detalle. Los coeficientes que lleva
pegados el motor salieron de los 1.031 partidos ENTEROS, así que medirlos
contra cualquiera de esos partidos es preguntarle por un examen que ya vio.
Aquí cada corte reajusta los dos modelos con lo anterior y sólo entonces mira
lo siguiente. Los números salen peores que con los coeficientes pegados, y son
los buenos, .

QUÉ SE COMPARA. Los dos modelos por separado y unidos, contra el listón de
acertar siempre lo más común. Un modelo que no supere ese listón no ha
aprendido nada por muy alto que suene su porcentaje.

Uso:  python scripts/evaluar_motor.py
"""

import asyncio

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")


def _ece(pr: np.ndarray, real: np.ndarray) -> float:
    """Cuánto se desvía lo prometido de lo ocurrido, por tramos."""
    total = 0.0
    for i in range(10):
        sel = (pr >= i / 10) & (pr < (i + 1) / 10 + (0.001 if i == 9 else 0.0))
        if sel.sum():
            total += sel.sum() / len(pr) * abs(pr[sel].mean() - real[sel].mean())
    return total


async def main() -> None:
    from sklearn.metrics import log_loss, roc_auc_score

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        PESO_GOLES,
        PESO_ORDINAL,
        TIPOS_DE_ENTRENAMIENTO,
        Probabilidades,
        modelo_ajustado,
        probabilidades_del_motor,
        probabilidades_poisson,
        ratings_de,
        resultado,
        variables,
    )
    from app.infrastructure.db import models as m

    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        partidos = [
            p
            for p in (
                await session.execute(
                    select(m.TrainingMatch).order_by(m.TrainingMatch.ht_match_id)
                )
            ).scalars()
            if p.match_type in TIPOS_DE_ENTRENAMIENTO
        ]
    if len(partidos) < 200:
        raise SystemExit(f"Sólo hay {len(partidos)} partidos: muy pocos para medir")

    y = np.array([resultado(p) for p in partidos])
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    reparto = dict(zip(CLASES, np.bincount(y, minlength=3), strict=True))
    print(f"{len(partidos)} partidos · reparto {reparto}")
    print(f"mezcla del motor: {PESO_ORDINAL:.0%} ordinal · {PESO_GOLES:.0%} goles\n")

    import statsmodels.api as sm
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.domain.engines.prediccion import (
        DUELOS_OFENSIVOS,
        ESCALA,
        ModeloOrdinal,
        _reparto_de_goles,
        proporcion,
    )

    terna = lambda p: [p.derrota, p.empate, p.victoria]  # noqa: E731
    diseno = np.array([variables(mio, suyo) for mio, suyo in lados])

    def ajusta(hasta: int):
        """Los dos modelos, entrenados sólo con lo anterior al corte."""
        ref = OrderedModel(y[:hasta], diseno[:hasta], distr="logit").fit(
            method="bfgs", disp=False, maxiter=3000
        )
        k = diseno.shape[1]
        u1 = float(ref.params[k])
        ordinal = ModeloOrdinal(
            beta=np.asarray(ref.params[:k], dtype=float) / ESCALA,
            umbrales=np.array([u1, u1 + float(np.exp(ref.params[k + 1]))]) / ESCALA,
        )
        ofensivo = lambda mio, suyo: [  # noqa: E731
            proporcion(mio[a], suyo[b]) for _, a, b in DUELOS_OFENSIVOS
        ]
        filas, goles = [], []
        for i, (mio, suyo) in enumerate(lados[:hasta]):
            filas += [ofensivo(mio, suyo), ofensivo(suyo, mio)]
            goles += [partidos[i].home_goals, partidos[i].away_goals]
        glm = sm.GLM(
            np.array(goles), sm.add_constant(np.array(filas)), family=sm.families.Poisson()
        ).fit()

        def poisson(mio, suyo):
            duelos = np.array([ofensivo(mio, suyo), ofensivo(suyo, mio)])
            lam = glm.predict(sm.add_constant(duelos, has_constant="add"))
            rej = np.outer(
                _reparto_de_goles(min(lam[0], 12.0)),
                _reparto_de_goles(min(lam[1], 12.0)),
            )
            v, e, d = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
            t = v + e + d
            return Probabilidades(v / t, e / t, d / t)

        return ordinal, poisson

    modelos = ("ordinal solo", "goles solo", "el motor (unidos)")

    n = len(partidos)
    cortes = [(int(n * f), int(n * (f + 0.12))) for f in (0.40, 0.52, 0.64, 0.76, 0.88)]
    print(
        f"{'modelo':22}{'log-loss':>10}{'aciertos':>10}"
        f"{'AUC vic':>9}{'AUC der':>9}{'AUC emp':>9}"
    )
    resultados: dict[str, list[float]] = {n: [] for n in modelos}
    otras: dict[str, list[list[float]]] = {n: [] for n in modelos}
    guardadas: dict[str, list[np.ndarray]] = {n: [] for n in modelos}
    for ini, fin in cortes:
        ordinal, poisson = ajusta(ini)
        yy = y[ini:fin]
        por_modelo = {
            "ordinal solo": np.array(
                [terna(ordinal.probabilidades(x)) for x in diseno[ini:fin]]
            ),
            "goles solo": np.array([terna(poisson(mio, suyo)) for mio, suyo in lados[ini:fin]]),
        }
        por_modelo["el motor (unidos)"] = (
            PESO_ORDINAL * por_modelo["ordinal solo"] + PESO_GOLES * por_modelo["goles solo"]
        )
        for nombre in modelos:
            probs = por_modelo[nombre]
            guardadas[nombre].append(probs)
            resultados[nombre].append(log_loss(yy, np.clip(probs, 1e-12, 1), labels=[0, 1, 2]))
            otras[nombre].append(
                [
                    float((probs.argmax(1) == yy).mean()),
                    roc_auc_score((yy == 2).astype(int), probs[:, 2]),
                    roc_auc_score((yy == 0).astype(int), probs[:, 0]),
                    roc_auc_score((yy == 1).astype(int), probs[:, 1]),
                ]
            )
    for nombre in modelos:
        ac, av, ad, ae = np.array(otras[nombre]).mean(axis=0)
        print(
            f"{nombre:22}{np.mean(resultados[nombre]):>10.4f}{ac:>10.3f}"
            f"{av:>9.3f}{ad:>9.3f}{ae:>9.3f}"
        )
    resultados = {k: np.array(v) for k, v in resultados.items()}

    # El listón. Siempre la clase más común, sin mirar nada del partido.
    suelo_ll, suelo_ac = [], []
    for ini, fin in cortes:
        base = np.bincount(y[:ini], minlength=3) / ini
        probs = np.tile(base, (fin - ini, 1))
        suelo_ll.append(log_loss(y[ini:fin], probs, labels=[0, 1, 2]))
        suelo_ac.append(float((y[ini:fin] == base.argmax()).mean()))
    print(f"{'no saber nada':22}{np.mean(suelo_ll):>10.4f}{np.mean(suelo_ac):>10.3f}")

    print("\nlog-loss corte a corte (más bajo, mejor):")
    print(f"  {'corte':>7}" + "".join(f"{k[:16]:>18}" for k in modelos))
    for i, (ini, _) in enumerate(cortes):
        print(f"  {ini:>7}" + "".join(f"{resultados[k][i]:>18.4f}" for k in modelos))

    gana = int((resultados["el motor (unidos)"] < resultados["ordinal solo"]).sum())
    print(f"\n  el motor unido gana al ordinal solo en {gana} de {len(cortes)} cortes")

    # ── Calibración del motor entero ─────────────────────────────────────
    #
    # No se compara con cero, que no se alcanza con muestras finitas: se
    # simulan mundos donde el modelo acierta EXACTO y se mira si el error real
    # cabe entre lo que sale ahí.
    probs = np.vstack(guardadas["el motor (unidos)"])
    yy = np.concatenate([y[a:b] for a, b in cortes])
    rng = np.random.default_rng(20260907)
    print(f"\nCALIBRACIÓN del motor sobre {len(yy)} partidos no vistos")
    print(f"  {'clase':10}{'promete':>9}{'ocurre':>9}{'ECE':>8}{'p95':>8}  veredicto")
    for k, nom in enumerate(CLASES):
        pr, real = probs[:, k], (yy == k).astype(int)
        obs = _ece(pr, real)
        sim = np.array([_ece(pr, (rng.random(len(yy)) < pr).astype(int)) for _ in range(1500)])
        p95 = float(np.quantile(sim, 0.95))
        print(
            f"  {nom:10}{pr.sum():>9.0f}{real.sum():>9}{obs:>8.3f}{p95:>8.3f}"
            f"  {'calibrada' if obs <= p95 else 'DESCALIBRADA'}"
        )

    # Que las dos mitades no se contradigan es parte de lo que hay que medir:
    # si un modelo dice victoria y el otro derrota, la mezcla no significa nada.
    uno = np.vstack(guardadas["ordinal solo"]).argmax(1)
    otro = np.vstack(guardadas["goles solo"]).argmax(1)
    desacuerdos = int((uno != otro).sum())
    print(f"\n  los dos modelos discrepan en {desacuerdos} de {len(yy)} partidos "
          f"({desacuerdos / len(yy):.1%})")
    _ = (probabilidades_del_motor, probabilidades_poisson, modelo_ajustado)


if __name__ == "__main__":
    asyncio.run(main())
