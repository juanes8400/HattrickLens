"""¿Y si la mezcla fuera 100 % goles? El barrido, con el motor de verdad.

2026-09-20, pregunta del usuario: «¿cómo queda si pongo 100-0?».

SE MIDEN LAS DOS MITADES TAL COMO CORREN, con sus coeficientes pegados: la
Poisson con su descompresión cuadrática, su tope de vértice y su Balón Parado
aparte, y la ordinal con los suyos. Es decir, exactamente lo que devuelve
`probabilidades_del_motor` con cada peso.

POR QUÉ NO SE REAJUSTA EN CADA CORTE, como hace `evaluar_motor.py`. Ese guion
reajusta, sí, pero lo que reajusta es una Poisson LINEAL de cinco duelos, que
es la que había antes del 2026-09-08: no tiene el término cuadrático ni el
Balón Parado separado. Medir con ella dice cómo se portaba el modelo viejo, no
el que corre. Rehacer el ajuste no lineal en cada corte es repetir entero
`descomprimir_goles.py`, y eso es otro trabajo.

LO QUE ESTO SÍ VALE Y LO QUE NO. Los coeficientes salieron de estos mismos
partidos, así que las cifras ABSOLUTAS son optimistas: es preguntarle al
modelo por un examen que ya vio. Lo que no cambia con eso es la COMPARACIÓN
entre pesos, que es la pregunta: las dos ternas son las mismas en las siete
filas y lo único que se mueve es cuánto pesa cada una al sumarlas.

Y EL LOG-LOSS NO DECIDE SOLO. La pantalla enseña porcentajes, así que una
clase descalibrada es una mentira aunque el error medio baje. Por eso cada
peso sale con el veredicto del empate, medido contra mundos simulados en los
que el modelo acierta exacto.

Uso:  python scripts/barrido_de_la_mezcla.py
"""

import asyncio

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")

#: Los pesos que se prueban, como fracción que se lleva el modelo de GOLES.
PESOS = (0.00, 0.10, 0.20, 0.40, 0.60, 0.70, 0.80, 0.90, 1.00)


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
        TIPOS_DE_ENTRENAMIENTO,
        modelo_ajustado,
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
    await engine.dispose()
    if len(partidos) < 200:
        raise SystemExit(f"Sólo hay {len(partidos)} partidos: muy pocos para medir")

    y = np.array([resultado(p) for p in partidos])
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    reparto = dict(zip(CLASES, np.bincount(y, minlength=3), strict=True))
    print(f"{len(partidos)} partidos · reparto {reparto}")
    print(f"la mezcla que corre hoy: {PESO_GOLES:.0%} goles")
    print("(coeficientes pegados: las cifras absolutas son optimistas, la")
    print(" comparación entre pesos no)\n")

    terna = lambda p: [p.derrota, p.empate, p.victoria]  # noqa: E731
    ordinal_m = modelo_ajustado()
    ordinales = np.array([terna(ordinal_m.probabilidades(variables(a, b))) for a, b in lados])
    poissons = np.array([terna(probabilidades_poisson(a, b)) for a, b in lados])

    rng = np.random.default_rng(20260907)
    print(
        f"{'peso goles':>11}{'log-loss':>10}{'aciertos':>10}{'AUC vic':>9}"
        f"{'empate promete':>16}{'ocurre':>8}{'ECE':>7}{'p95':>7}  veredicto"
    )
    for w in PESOS:
        mezcla = w * poissons + (1 - w) * ordinales
        ll = log_loss(y, np.clip(mezcla, 1e-12, 1), labels=[0, 1, 2])
        ac = float((mezcla.argmax(1) == y).mean())
        auc = roc_auc_score((y == 2).astype(int), mezcla[:, 2])
        pr, real = mezcla[:, 1], (y == 1).astype(int)
        obs = _ece(pr, real)
        sim = np.array([_ece(pr, (rng.random(len(y)) < pr).astype(int)) for _ in range(800)])
        p95 = float(np.quantile(sim, 0.95))
        print(
            f"{w:>11.2f}{ll:>10.4f}{ac:>10.3f}{auc:>9.3f}"
            f"{pr.sum():>16.0f}{real.sum():>8}{obs:>7.3f}{p95:>7.3f}"
            f"  {'calibrado' if obs <= p95 else 'DESCALIBRADO'}"
        )

    # Cuánto se movería un partido concreto, que es lo que se ve en pantalla.
    print("\nlo que cambiaría en pantalla, partido a partido (80 % -> 100 %):")
    actual = PESO_GOLES * poissons + (1 - PESO_GOLES) * ordinales
    solo_goles = poissons
    dif = np.abs(actual - solo_goles).max(axis=1)
    print(f"  diferencia mediana: {np.median(dif) * 100:.2f} puntos porcentuales")
    print(f"  diferencia máxima : {dif.max() * 100:.2f} puntos porcentuales")
    cambian = int((actual.argmax(1) != solo_goles.argmax(1)).sum())
    print(f"  partidos en los que cambia el resultado más probable: {cambian} de {len(y)}")


if __name__ == "__main__":
    asyncio.run(main())
