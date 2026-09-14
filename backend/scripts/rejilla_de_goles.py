"""El mediocampo como OFFSET de la Poisson de goles, 50 combinaciones.

LA IDEA, planteada el 2026-09-08. Hasta ahora el mediocampo es una variable
más de la Poisson y su coeficiente se estima (sale 1,720). La alternativa es
FIJARLO: declarar que los goles son proporcionales a una función conocida del
mediocampo y dejar que la regresión sólo aprenda lo ofensivo. Eso es un
offset: un término que se suma al predictor lineal con coeficiente 1.

EL AJUSTE QUE HUBO QUE HACER. Un offset se suma a `log(lambda)`, así que
tomar `A^2/B^2` literalmente daría `log(lambda) = 4624 + ...` en el caso
extremo de estos datos, o sea `e^4624`: desborda. Lo que tiene sentido --y lo
que se prueba aquí-- es que el offset diga que lambda es PROPORCIONAL a esa
función:

    lambda ~ (A/B)^0,5   ->  offset = 0,5 * log(A/B)
    lambda ~ (A/B)       ->  offset = 1,0 * log(A/B)     proporcional puro
    lambda ~ (A/B)^2     ->  offset = 2,0 * log(A/B)
    lambda ~ A/(A+B)     ->  offset = log(p)

Cada una es una hipótesis nítida sobre cuánto manda la posesión.

LA FILA DE REFERENCIA. Además de los cuatro offsets se prueba el mediocampo
LIBRE, con su coeficiente estimado, en las mismas cuatro formas. Sin eso los
32 números no dicen si fijar el mediocampo ayuda o estorba: sólo dicen cuál
de las maneras de estorbar es menos mala.

IGUALAR LOS ATAQUES. Los tres ataques abiertos comparten coeficiente, que se
implementa sumando sus tres duelos en UNA columna --el coeficiente compartido
multiplica la suma, que es exactamente el modelo restringido--. El Balón
Parado se queda con el suyo: es otro tipo de ataque.

EL AIC ES AQUÍ EL CRITERIO BUENO dentro de muestra, porque el número de
parámetros SÍ cambia: el offset quita uno e igualar quita dos.

Uso:  python scripts/rejilla_de_goles.py
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


def _r(a: float, b: float) -> float:
    """`A/B` con suelo en 1, que es lo que impide un infinito."""
    return max(a, 1.0) / max(b, 1.0)


def _p(a: float, b: float) -> float:
    t = a + b
    return a / t if t > 0 else 0.5


#: Las cuatro formas de medir un duelo ofensivo.
FORMAS = {
    "log(C/D)": lambda a, b: float(np.log(_r(a, b))),
    "C/(C+D)": _p,
    "raiz(C/D)": lambda a, b: float(np.sqrt(_r(a, b))),
    "(C/D)^2": lambda a, b: _r(a, b) ** 2,
    "log(C/(C+D))": lambda a, b: float(np.log(max(_p(a, b), 1e-9))),
}

#: Los offsets, todos como `log` de la función para que lambda salga
#: proporcional a ella. `None` es la referencia: mediocampo libre.
#:
#: `log(A/(A+B))` NO aparece como una quinta fila y no es un olvido: metido
#: como offset literal --sumado a `log(lambda)`-- es exactamente
#: `lambda ~ A/(A+B)`, que ya está. Y como «lambda proporcional a
#: log(A/(A+B))» no existe: esa función es siempre NEGATIVA, y lambda no
#: puede ser proporcional a un número negativo. En el bucle de las variables
#: sí entra, porque ahí lleva coeficiente y el signo lo absorbe.
OFFSETS = {
    "libre (referencia)": None,
    "lambda ~ raiz(A/B)": lambda a, b: 0.5 * float(np.log(_r(a, b))),
    "lambda ~ A/B": lambda a, b: float(np.log(_r(a, b))),
    "lambda ~ (A/B)^2": lambda a, b: 2.0 * float(np.log(_r(a, b))),
    "lambda ~ A/(A+B)": lambda a, b: float(np.log(max(_p(a, b), 1e-9))),
}


async def main() -> None:
    import statsmodels.api as sm
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

    # El mediocampo es el primero; los tres ataques abiertos, los tres
    # siguientes; el Balón Parado, el último. Se comprueba en vez de
    # suponerlo, porque si cambia el orden esto sumaría las columnas malas.
    assert DUELOS_OFENSIVOS[0][0] == "medio"
    assert DUELOS_OFENSIVOS[-1][0] == "bp_ata"
    medio = DUELOS_OFENSIVOS[0]
    ataques = DUELOS_OFENSIVOS[1:-1]
    balon = DUELOS_OFENSIVOS[-1]
    print(f"{n} partidos · {2 * n} lados · {gl.sum() + gv.sum()} goles")
    print(f"{len(OFFSETS)} offsets x {len(FORMAS)} formas x 2 (igualar) = "
          f"{len(OFFSETS) * len(FORMAS) * 2} combinaciones\n")

    def fila(f, off, igualar, mi, su):
        """Una fila del diseño, y su offset, para un lado del partido."""
        at = [f(mi[a], su[b]) for _, a, b in ataques]
        cols = ([sum(at)] if igualar else at) + [f(mi[balon[1]], su[balon[2]])]
        if off is None:
            cols = [f(mi[medio[1]], su[medio[2]]), *cols]
            return cols, 0.0
        return cols, off(mi[medio[1]], su[medio[2]])

    cortes = [(int(n * fr), int(n * (fr + 0.12))) for fr in (0.40, 0.52, 0.64, 0.76, 0.88)]

    def evalua(f, off, igualar):
        dis, offs, cuenta = [], [], []
        for i, (mi, su) in enumerate(lados):
            for a, b, g in ((mi, su, gl[i]), (su, mi, gv[i])):
                c, o = fila(f, off, igualar, a, b)
                dis.append(c)
                offs.append(o)
                cuenta.append(int(g))
        dis, offs, cuenta = np.array(dis), np.array(offs), np.array(cuenta)

        # AIC dentro de muestra, tipificando para que converja: es una
        # reescritura lineal, no cambia la verosimilitud.
        mu, sd = dis.mean(axis=0), dis.std(axis=0)
        sd = np.where(sd > 1e-12, sd, 1.0)
        try:
            entero = sm.GLM(
                cuenta, sm.add_constant((dis - mu) / sd), family=sm.families.Poisson(), offset=offs
            ).fit()
            aic, k = float(entero.aic), int(len(entero.params))
        except Exception:  # noqa: BLE001
            return None

        lam_t, real_t, res_t, yy_t = [], [], [], []
        for ini, fin in cortes:
            hasta = 2 * ini
            ent = dis[:hasta]
            mu, sd = ent.mean(axis=0), ent.std(axis=0)
            sd = np.where(sd > 1e-12, sd, 1.0)
            try:
                glm = sm.GLM(
                    cuenta[:hasta],
                    sm.add_constant((ent - mu) / sd),
                    family=sm.families.Poisson(),
                    offset=offs[:hasta],
                ).fit()
            except Exception:  # noqa: BLE001
                return None
            tr = slice(hasta, 2 * fin)
            lam = np.clip(
                glm.predict(
                    sm.add_constant((dis[tr] - mu) / sd, has_constant="add"), offset=offs[tr]
                ),
                1e-6,
                12.0,
            )
            if not np.all(np.isfinite(lam)):
                return None
            lam_t += list(lam)
            real_t += list(cuenta[tr])
            for j in range(0, len(lam), 2):
                rej = np.outer(reparto(float(lam[j])), reparto(float(lam[j + 1])))
                v, e, d = np.tril(rej, -1).sum(), np.trace(rej), np.triu(rej, 1).sum()
                t = v + e + d
                res_t.append([d / t, e / t, v / t])
            yy_t += list(y[ini:fin])
        lam_a, real_a = np.array(lam_t), np.array(real_t)
        lv = float(
            np.mean(
                [
                    np.log(max(reparto(a)[min(int(b), TOPE)], 1e-12))
                    for a, b in zip(lam_a, real_a, strict=True)
                ]
            )
        )
        return {
            "aic": aic,
            "k": k,
            "eam": float(np.abs(lam_a - real_a).mean()),
            "ec": float(np.sqrt(((lam_a - real_a) ** 2).mean())),
            "lv": lv,
            "pend": float(np.polyfit(lam_a, real_a, 1)[0]),
            "ved": float(
                log_loss(np.array(yy_t), np.clip(np.array(res_t), 1e-12, 1), labels=[0, 1, 2])
            ),
        }

    filas = []
    for nombre_off, off in OFFSETS.items():
        for nombre_f, f in FORMAS.items():
            for igualar in (False, True):
                r = evalua(f, off, igualar)
                etiqueta = "iguales" if igualar else "libres"
                if r is None:
                    print(f"  {nombre_off:20}{nombre_f:12}{etiqueta:9} NO CONVERGE")
                    continue
                filas.append((nombre_off, nombre_f, etiqueta, r))
                print(
                    f"  {nombre_off:20}{nombre_f:12}{etiqueta:9}"
                    f"{r['lv']:>9.4f}{r['eam']:>9.4f}{r['aic']:>11.1f}"
                )

    base = next(
        r
        for r in filas
        if r[0] == "libre (referencia)" and r[1] == "log(C/D)" and r[2] == "libres"
    )
    filas.sort(key=lambda r: -r[3]["lv"])
    print("\n" + "=" * 108)
    print("LAS COMBINACIONES, ordenadas por verosimilitud de los GOLES (más alta, mejor)")
    print("=" * 108)
    print(
        f"  {'#':>3} {'offset del mediocampo':21}{'forma ataques':13}{'ataques':9}"
        f"{'logver':>9}{'EAM':>8}{'EC':>8}{'pend':>8}{'V/E/D':>9}{'AIC':>11}{'par':>5}"
    )
    for i, (o, f, ig, r) in enumerate(filas, 1):
        marca = "  <- hoy" if (o, f, ig) == (base[0], base[1], base[2]) else ""
        print(
            f"  {i:>3} {o:21}{f:13}{ig:9}{r['lv']:>9.4f}{r['eam']:>8.4f}{r['ec']:>8.4f}"
            f"{r['pend']:>8.4f}{r['ved']:>9.4f}{r['aic']:>11.1f}{r['k']:>5}{marca}"
        )

    print("\n  lo mejor de cada offset:")
    for nombre_off in OFFSETS:
        mejores = [r for r in filas if r[0] == nombre_off]
        if mejores:
            o, f, ig, r = mejores[0]
            print(f"    {o:21}{f:13}{ig:9}{r['lv']:>9.4f}{r['aic']:>11.1f}")
    print("\n  igualar los ataques, en promedio:")
    for ig in ("libres", "iguales"):
        sel = [r[3]["lv"] for r in filas if r[2] == ig]
        aics = [r[3]["aic"] for r in filas if r[2] == ig]
        print(f"    {ig:9} logver medio {np.mean(sel):>9.4f}   AIC medio {np.mean(aics):>11.1f}")


if __name__ == "__main__":
    asyncio.run(main())
