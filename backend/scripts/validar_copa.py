"""¿Sirve el motor para la COPA? Se mide antes de cablear esa pantalla.

POR QUÉ HAY QUE PREGUNTARLO. El modelo se ajusta SÓLO con partidos de liga
(`TIPOS_DE_ENTRENAMIENTO`), a propósito: de los 862 partidos de copa recogidos
hay CERO empates --hay prórroga, alguien pasa-- y el local marca mucho menos
que el visitante, porque el sorteo cruza divisiones y el que recibe suele ser
el débil. Entrenar con eso enseñaría dos mentiras.

Lo único que hace `probabilidades_de_copa` es repartir la probabilidad de
empate entre las otras dos en la proporción en que ya estaban. Eso NUNCA se ha
medido contra partidos de copa reales. Este guion lo mide.

QUÉ SE COMPRUEBA:
  1. Los goles: ¿acierta cuántos se marcan en un partido de copa?
  2. El pase: ¿acierta quién pasa? Log-loss binario, AUC y calibración.
  3. El listón: predecir siempre «pasa el que juega en casa» y «50-50».
  4. Si hace falta una corrección de sede neutral --desde octavos se juega en
     campo neutral, así que la ventaja de campo de los ratings sobra.

NADA DE ESTO ENTRENA CON COPA. Los coeficientes son los de liga, tal cual
están en el motor. Es una validación pura sobre datos que el modelo no vio.

Uso:  python scripts/validar_copa.py
"""

import asyncio
import warnings

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _ece(pr: np.ndarray, real: np.ndarray) -> float:
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
        MATCH_TYPE_CUP,
        goles_esperados,
        probabilidades_de_copa,
        probabilidades_del_motor,
        ratings_de,
    )
    from app.infrastructure.db import models as m

    warnings.filterwarnings("ignore")
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        copa = [
            p
            for p in (
                await session.execute(select(m.TrainingMatch).order_by(m.TrainingMatch.ht_match_id))
            ).scalars()
            if p.match_type == MATCH_TYPE_CUP
        ]
    if len(copa) < 100:
        raise SystemExit(f"sólo hay {len(copa)} partidos de copa: muy pocos para validar")

    gl = np.array([p.home_goals for p in copa])
    gv = np.array([p.away_goals for p in copa])
    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in copa]
    n = len(copa)
    empates = int((gl == gv).sum())
    print(f"{n} partidos de copa · {gl.sum() + gv.sum()} goles")
    print(f"local {gl.mean():.3f} por partido · visitante {gv.mean():.3f} · empates {empates}")
    print(f"pasa el local en {(gl > gv).mean():.1%} de los cruces\n")

    # ── 1. Los goles ──────────────────────────────────────────────────────
    lam_l = np.array([goles_esperados(a, b) for a, b in lados])
    lam_v = np.array([goles_esperados(b, a) for a, b in lados])
    lam = np.concatenate([lam_l, lam_v])
    real = np.concatenate([gl, gv])
    print("=" * 88)
    print("1. LOS GOLES, coeficientes de liga aplicados a partidos de copa")
    print("=" * 88)
    print(f"  error absoluto medio : {np.abs(lam - real).mean():.4f}")
    print(f"  error cuadrático     : {np.sqrt(((lam - real) ** 2).mean()):.4f}")
    print(f"  sesgo (predicho-real): {(lam - real).mean():+.4f}")
    print(f"  correlación          : {np.corrcoef(lam, real)[0, 1]:.4f}")
    print(f"  pendiente            : {float(np.polyfit(lam, real, 1)[0]):.4f}")
    print(f"  goles predichos      : {lam.sum():.0f}   ocurridos {real.sum()}")
    print(f"  LISTÓN (siempre la media {real.mean():.2f}): "
          f"EAM {np.abs(real.mean() - real).mean():.4f}")
    print("\n  por lado, que es donde se ve el sesgo del sorteo:")
    print(f"    local     : predice {lam_l.mean():.3f}  ocurre {gl.mean():.3f}"
          f"  {lam_l.mean() - gl.mean():+.3f}")
    print(f"    visitante : predice {lam_v.mean():.3f}  ocurre {gv.mean():.3f}"
          f"  {lam_v.mean() - gv.mean():+.3f}")

    # ── 2. ¿Acierta quién pasa? ───────────────────────────────────────────
    pasa_local = (gl > gv).astype(int)
    p_local = np.array([probabilidades_de_copa(a, b).victoria for a, b in lados])
    print("\n" + "=" * 88)
    print("2. EL PASE, probabilidades_de_copa (el empate repartido, sin empate)")
    print("=" * 88)
    binaria = np.column_stack([1 - p_local, p_local])
    print(f"  log-loss binario     : {log_loss(pasa_local, binaria, labels=[0, 1]):.4f}")
    print(f"  AUC                  : {roc_auc_score(pasa_local, p_local):.4f}")
    aciertos = float(((p_local > 0.5).astype(int) == pasa_local).mean())
    print(f"  aciertos             : {aciertos:.3f}")
    base = np.full(n, pasa_local.mean())
    print(f"  LISTÓN «siempre el local pasa {pasa_local.mean():.0%}»: "
          f"log-loss {log_loss(pasa_local, np.column_stack([1 - base, base]), labels=[0, 1]):.4f}")
    print(f"  LISTÓN «50-50»                   : "
          f"log-loss {log_loss(pasa_local, np.full((n, 2), 0.5), labels=[0, 1]):.4f}")
    print(f"  promete {p_local.sum():.0f} pases del local · ocurren {pasa_local.sum()}")

    rng = np.random.default_rng(20260908)
    obs = _ece(p_local, pasa_local)
    sim = np.array([_ece(p_local, (rng.random(n) < p_local).astype(int)) for _ in range(2000)])
    p95 = float(np.quantile(sim, 0.95))
    print(f"\n  calibración: ECE {obs:.4f} · p95 {p95:.4f} -> "
          f"{'CALIBRADA' if obs <= p95 else 'DESCALIBRADA'}")
    print(f"  {'tramo':>12}{'cruces':>8}{'promete':>10}{'pasa':>9}{'error':>9}")
    for lo in (0.0, 0.2, 0.4, 0.6, 0.8):
        sel = (p_local >= lo) & (p_local < lo + 0.2 + (0.001 if lo == 0.8 else 0))
        if sel.sum() < 15:
            continue
        dif = p_local[sel].mean() - pasa_local[sel].mean()
        print(f"  {f'{lo:.1f}-{lo + 0.2:.1f}':>12}{sel.sum():>8}"
              f"{p_local[sel].mean():>10.3f}{pasa_local[sel].mean():>9.3f}{dif:>+9.3f}")

    # ── 3. ¿Sobra la ventaja de campo? ────────────────────────────────────
    #
    # Desde octavos la copa se juega en campo neutral, y el sorteo cruza
    # divisiones. Si el motor hereda de la liga una ventaja de local que en
    # copa no existe, se vería como un sesgo constante a favor del local.
    print("\n" + "=" * 88)
    print("3. ¿SOBRA LA VENTAJA DE CAMPO?")
    print("=" * 88)
    terna = [probabilidades_del_motor(a, b) for a, b in lados]
    print(f"  el motor (con empate) promete al local: {np.mean([t.victoria for t in terna]):.1%}")
    print(f"  pasa el local realmente               : {pasa_local.mean():.1%}")
    print(f"  empate que hay que repartir, de media : {np.mean([t.empate for t in terna]):.1%}")
    for corte in (0.0, 0.05, 0.10):
        ajustada = np.clip(p_local - corte, 0.001, 0.999)
        ll = log_loss(pasa_local, np.column_stack([1 - ajustada, ajustada]), labels=[0, 1])
        print(f"  restando {corte:.2f} al local: log-loss {ll:.4f}")

    print("\n" + "=" * 88)
    print("VEREDICTO")
    print("=" * 88)
    listón = log_loss(pasa_local, np.column_stack([1 - base, base]), labels=[0, 1])
    real_ll = log_loss(pasa_local, binaria, labels=[0, 1])
    print(f"  ¿le gana al listón?  {real_ll:.4f} contra {listón:.4f}  -> "
          f"{'SÍ' if real_ll < listón else 'NO'}")
    print(f"  ¿está calibrado?     {'SÍ' if obs <= p95 else 'NO'}")
    print("\n  Cablear Copa sólo si las dos dicen SÍ.")


if __name__ == "__main__":
    asyncio.run(main())
