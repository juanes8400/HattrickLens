"""Compara el motor actual (80 % Poisson + 20 % ordinal) con Poisson pura.

La comparación principal es de origen móvil: en cinco cortes se ajusta cada
arquitectura únicamente con partidos anteriores y se evalúa el bloque
siguiente. Así se compara la forma de los modelos sin medirlos contra partidos
que ya intervinieron en sus parámetros.

También se imprime un diagnóstico con las funciones y coeficientes que están
enchufados hoy a la aplicación. Ese segundo bloque sirve para comprobar el
cableado, pero se etiqueta como «dentro de muestra» y no decide el ganador.

Uso: python scripts/comparar_motor_actual_vs_poisson.py
"""

from __future__ import annotations

import asyncio
import warnings
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

CLASES = ("derrota", "empate", "victoria")


@dataclass(frozen=True)
class Metricas:
    log_loss: float
    brier: float
    acierto: float
    ece: float


def _metricas(y: np.ndarray, probabilidades: np.ndarray) -> Metricas:
    p = np.clip(probabilidades, 1e-12, 1.0)
    reales = np.eye(3)[y]
    perdida = -np.log(p[np.arange(len(y)), y])
    return Metricas(
        log_loss=float(perdida.mean()),
        brier=float(np.square(p - reales).sum(axis=1).mean()),
        acierto=float((p.argmax(axis=1) == y).mean()),
        ece=float(
            np.mean(
                [
                    _ece(p[:, clase], (y == clase).astype(float))
                    for clase in range(3)
                ]
            )
        ),
    )


def _ece(probabilidad: np.ndarray, real: np.ndarray) -> float:
    total = 0.0
    for i in range(10):
        minimo = i / 10
        maximo = (i + 1) / 10
        dentro = (probabilidad >= minimo) & (
            probabilidad <= maximo if i == 9 else probabilidad < maximo
        )
        if dentro.any():
            total += float(dentro.mean()) * abs(
                float(probabilidad[dentro].mean()) - float(real[dentro].mean())
            )
    return total


def _imprimir(nombre: str, metricas: Metricas) -> None:
    print(
        f"  {nombre:24}{metricas.log_loss:>10.4f}{metricas.brier:>10.4f}"
        f"{metricas.acierto:>10.2%}{metricas.ece:>10.4f}"
    )


async def main() -> None:
    import statsmodels.api as sm
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        DUELOS_OFENSIVOS,
        ESCALA,
        PESO_GOLES,
        PESO_ORDINAL,
        TIPOS_DE_ENTRENAMIENTO,
        ModeloOrdinal,
        _reparto_de_goles,
        probabilidades_del_motor,
        probabilidades_poisson,
        ratings_de,
        resultado,
        variables,
    )
    from app.infrastructure.db import models as m

    warnings.filterwarnings("ignore")
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        partidos = list(
            (
                await session.execute(
                    select(m.TrainingMatch)
                    .where(
                        m.TrainingMatch.match_type.in_(TIPOS_DE_ENTRENAMIENTO),
                        m.TrainingMatch.played_at.is_not(None),
                    )
                    .order_by(m.TrainingMatch.played_at, m.TrainingMatch.ht_match_id)
                )
            ).scalars()
        )
        fin_del_corpus = max(p.played_at for p in partidos)
        posteriores = list(
            (
                await session.execute(
                    select(
                        m.Match.ht_match_id,
                        m.Match.played_at,
                        m.Match.home_team_ht_id,
                        m.Match.away_team_ht_id,
                        m.Match.home_goals,
                        m.Match.away_goals,
                    )
                    .where(
                        m.Match.match_type.in_(TIPOS_DE_ENTRENAMIENTO),
                        m.Match.status.ilike("finished"),
                        m.Match.played_at > fin_del_corpus,
                    )
                    .order_by(m.Match.played_at, m.Match.ht_match_id)
                )
            ).all()
        )
        ids_posteriores = [p.ht_match_id for p in posteriores]
        ratings_posteriores = (
            list(
                (
                    await session.execute(
                        select(m.MatchRating).where(
                            m.MatchRating.ht_match_id.in_(ids_posteriores)
                        )
                    )
                ).scalars()
            )
            if ids_posteriores
            else []
        )
    await engine.dispose()
    if len(partidos) < 200:
        raise SystemExit(f"Sólo hay {len(partidos)} partidos: no alcanza para comparar")

    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    y = np.array([resultado(p) for p in partidos], dtype=int)
    goles_local = np.array([p.home_goals for p in partidos], dtype=int)
    goles_visitante = np.array([p.away_goals for p in partidos], dtype=int)
    diseno_ordinal = np.array([variables(local, visitante) for local, visitante in lados])

    def log_proporcion(a: float, b: float) -> float:
        total = a + b
        proporcion = a / total if total > 0 and a > 0 else 1.0 / (total + 1.0)
        return float(np.log(max(proporcion, 1e-3)))

    medio = DUELOS_OFENSIVOS[0]
    ataques = DUELOS_OFENSIVOS[1:-1]
    balon_parado = DUELOS_OFENSIVOS[-1]

    def fila_poisson(mio: dict[str, float], suyo: dict[str, float]) -> list[float]:
        return [
            log_proporcion(mio[medio[1]], suyo[medio[2]]),
            sum(log_proporcion(mio[a], suyo[b]) for _, a, b in ataques),
            log_proporcion(mio[balon_parado[1]], suyo[balon_parado[2]]),
        ]

    diseno_poisson = np.array(
        [
            fila
            for local, visitante in lados
            for fila in (
                fila_poisson(local, visitante),
                fila_poisson(visitante, local),
            )
        ]
    )
    goles = np.array(
        [
            gol
            for local, visitante in zip(goles_local, goles_visitante, strict=True)
            for gol in (local, visitante)
        ],
        dtype=int,
    )
    log_factorial = gammaln(goles + 1)

    def ajustar(hasta: int):
        ordinal_ref = OrderedModel(
            y[:hasta], diseno_ordinal[:hasta], distr="logit"
        ).fit(method="bfgs", disp=False, maxiter=3000)
        k = diseno_ordinal.shape[1]
        u1 = float(ordinal_ref.params[k])
        ordinal = ModeloOrdinal(
            beta=np.asarray(ordinal_ref.params[:k], dtype=float) / ESCALA,
            umbrales=np.array(
                [u1, u1 + float(np.exp(ordinal_ref.params[k + 1]))]
            )
            / ESCALA,
        )

        limite = 2 * hasta
        d = diseno_poisson[:limite]
        cuenta = goles[:limite]
        factorial = log_factorial[:limite]
        base = sm.GLM(
            cuenta,
            sm.add_constant(d),
            family=sm.families.Poisson(),
        ).fit()
        p0 = np.asarray(base.params, dtype=float)
        centro = float((p0[0] + d @ p0[1:4]).mean())
        inicio = np.array(
            [
                p0[0] - 0.4,
                p0[1],
                p0[2],
                p0[0] - 1.5,
                p0[1] * 0.3,
                p0[3],
                0.0,
            ]
        )

        def lambdas(parametros: np.ndarray, x: np.ndarray) -> np.ndarray:
            eta = parametros[0] + parametros[1] * x[:, 0] + parametros[2] * x[:, 1]
            # La producción detiene la parábola en su vértice para que, en
            # ratings extremos, un ataque todavía mejor nunca dé menos goles.
            if parametros[6] < 0:
                eta = np.minimum(eta, centro - 1.0 / (2.0 * parametros[6]))
            juego = np.exp(eta + parametros[6] * np.square(eta - centro))
            bp = np.exp(
                parametros[3]
                + parametros[4] * x[:, 0]
                + parametros[5] * x[:, 2]
            )
            return np.clip(juego + bp, 1e-9, 60.0)

        def negativa(parametros: np.ndarray) -> float:
            lam = lambdas(parametros, d)
            return -float(np.sum(cuenta * np.log(lam) - lam - factorial))

        ajuste = minimize(
            negativa,
            inicio,
            method="Nelder-Mead",
            options={"maxiter": 60_000, "maxfev": 60_000},
        )
        if not ajuste.success:
            raise RuntimeError(f"Poisson no convergió en el corte {hasta}: {ajuste.message}")
        return ordinal, lambda x: np.clip(lambdas(ajuste.x, x), 1e-6, 12.0)

    def terna_poisson(lam_local: float, lam_visitante: float) -> np.ndarray:
        rejilla = np.outer(
            _reparto_de_goles(lam_local),
            _reparto_de_goles(lam_visitante),
        )
        victoria = float(np.tril(rejilla, -1).sum())
        empate = float(np.trace(rejilla))
        derrota = float(np.triu(rejilla, 1).sum())
        total = victoria + empate + derrota
        return np.array([derrota / total, empate / total, victoria / total])

    n = len(partidos)

    def limite_temporal(fraccion: float) -> int:
        """Índice cercano a la fracción, sin partir una misma fecha/hora."""
        candidato = min(int(n * fraccion), n - 1)
        instante = partidos[candidato].played_at
        while candidato > 0 and partidos[candidato - 1].played_at == instante:
            candidato -= 1
        return candidato

    limites = [limite_temporal(f) for f in (0.40, 0.52, 0.64, 0.76, 0.88)] + [n]
    cortes = list(zip(limites[:-1], limites[1:], strict=True))
    for inicio, fin in cortes:
        if inicio <= 0 or inicio >= fin:
            raise RuntimeError(f"Corte temporal inválido: {inicio}:{fin}")
        if partidos[inicio - 1].played_at >= partidos[inicio].played_at:
            raise RuntimeError("Un corte separó partidos con la misma fecha")
    ys: list[np.ndarray] = []
    actuales: list[np.ndarray] = []
    puras: list[np.ndarray] = []
    goles_estimados: list[float] = []
    goles_reales: list[int] = []
    semanas: list[tuple[int, int]] = []
    marcador_acertado = 0
    total_marcadores = 0

    print(
        f"{n} partidos de liga ({partidos[0].played_at:%Y-%m-%d} a "
        f"{partidos[-1].played_at:%Y-%m-%d}); prueba sobre "
        f"{sum(b - a for a, b in cortes)}"
    )
    print(f"Motor de la app: {PESO_GOLES:.0%} Poisson + {PESO_ORDINAL:.0%} ordinal\n")
    print(
        "Aviso: son cortes fuera del ajuste de cada bloque, pero fueron "
        "reutilizados históricamente para escoger el peso 80/20.\n"
    )
    print("Ajustando cinco cortes temporales...")
    for numero, (inicio, fin) in enumerate(cortes, start=1):
        ordinal, poisson = ajustar(inicio)
        lam = poisson(diseno_poisson[2 * inicio : 2 * fin])
        p_poisson = np.array(
            [terna_poisson(lam[i], lam[i + 1]) for i in range(0, len(lam), 2)]
        )
        p_ordinal = np.array(
            [
                [p.derrota, p.empate, p.victoria]
                for p in (
                    ordinal.probabilidades(x) for x in diseno_ordinal[inicio:fin]
                )
            ]
        )
        p_actual = PESO_GOLES * p_poisson + PESO_ORDINAL * p_ordinal
        yy = y[inicio:fin]
        ys.append(yy)
        actuales.append(p_actual)
        puras.append(p_poisson)
        semanas.extend(
            (p.played_at.isocalendar().year, p.played_at.isocalendar().week)
            for p in partidos[inicio:fin]
        )
        goles_estimados.extend(lam.tolist())
        reales_corte = goles[2 * inicio : 2 * fin]
        goles_reales.extend(reales_corte.tolist())
        for i in range(0, len(lam), 2):
            rejilla = np.outer(
                _reparto_de_goles(lam[i]), _reparto_de_goles(lam[i + 1])
            )
            marcador = np.unravel_index(int(rejilla.argmax()), rejilla.shape)
            real = (int(reales_corte[i]), int(reales_corte[i + 1]))
            marcador_acertado += int(marcador == real)
            total_marcadores += 1
        print(
            f"  corte {numero}: actual {_metricas(yy, p_actual).log_loss:.4f}"
            f" · Poisson {_metricas(yy, p_poisson).log_loss:.4f}"
        )

    yy = np.concatenate(ys)
    p_actual = np.vstack(actuales)
    p_poisson = np.vstack(puras)
    actual = _metricas(yy, p_actual)
    pura = _metricas(yy, p_poisson)
    print("\nFUERA DE MUESTRA (más bajo es mejor salvo acierto)")
    print(f"  {'modelo':24}{'log-loss':>10}{'Brier':>10}{'1-X-2':>10}{'ECE':>10}")
    _imprimir("Actual 80/20", actual)
    _imprimir("Poisson 100%", pura)

    perdida_actual = -np.log(np.clip(p_actual[np.arange(len(yy)), yy], 1e-12, 1.0))
    perdida_pura = -np.log(np.clip(p_poisson[np.arange(len(yy)), yy], 1e-12, 1.0))
    diferencia = perdida_pura - perdida_actual
    # Los partidos de una misma jornada comparten equipos y contexto. El
    # intervalo remuestrea semanas completas, no observaciones como si cada
    # partido fuera independiente.
    por_semana: dict[tuple[int, int], list[float]] = {}
    for semana, valor in zip(semanas, diferencia, strict=True):
        por_semana.setdefault(semana, []).append(float(valor))
    grupos = list(por_semana.values())
    rng = np.random.default_rng(20260911)
    bootstrap = []
    for _ in range(5000):
        muestra = rng.integers(0, len(grupos), size=len(grupos))
        valores = [valor for indice in muestra for valor in grupos[int(indice)]]
        bootstrap.append(float(np.mean(valores)))
    bootstrap = np.asarray(bootstrap)
    bajo, alto = np.quantile(bootstrap, [0.025, 0.975])
    print(
        "\n  ventaja de log-loss del actual sobre Poisson: "
        f"{diferencia.mean():+.6f} "
        f"(IC 95% por semana {bajo:+.6f} a {alto:+.6f})"
    )
    print("\nBALANCE GLOBAL: porcentaje medio prometido / ocurrido")
    for i, clase in enumerate(CLASES):
        print(
            f"  {clase:9} actual {p_actual[:, i].mean():6.2%} / {(yy == i).mean():6.2%}"
            f" · Poisson {p_poisson[:, i].mean():6.2%} / {(yy == i).mean():6.2%}"
        )
    print("\nECE POR CLASE (más bajo es mejor)")
    for i, clase in enumerate(CLASES):
        real = (yy == i).astype(float)
        print(
            f"  {clase:9} actual {_ece(p_actual[:, i], real):.4f}"
            f" · Poisson {_ece(p_poisson[:, i], real):.4f}"
        )

    estimados = np.array(goles_estimados)
    reales = np.array(goles_reales)
    print("\nGOLES Y MARCADOR (idénticos en ambos: la mezcla sólo cambia 1-X-2)")
    print(f"  EAM de goles por lado: {np.abs(estimados - reales).mean():.4f}")
    print(f"  RMSE de goles por lado: {np.sqrt(np.square(estimados - reales).mean()):.4f}")
    print(
        f"  marcador exacto: {marcador_acertado}/{total_marcadores}"
        f" ({marcador_acertado / total_marcadores:.2%})"
    )

    # Comprobación del cableado real, con los coeficientes hoy desplegados.
    fijo_actual = np.array(
        [
            [p.derrota, p.empate, p.victoria]
            for p in (probabilidades_del_motor(local, visita) for local, visita in lados)
        ]
    )
    fijo_poisson = np.array(
        [
            [p.derrota, p.empate, p.victoria]
            for p in (probabilidades_poisson(local, visita) for local, visita in lados)
        ]
    )
    print("\nCABLEADO ACTUAL, DENTRO DE MUESTRA (diagnóstico; no elige ganador)")
    print(f"  {'modelo':24}{'log-loss':>10}{'Brier':>10}{'1-X-2':>10}{'ECE':>10}")
    _imprimir("Actual 80/20", _metricas(y, fijo_actual))
    _imprimir("Poisson 100%", _metricas(y, fijo_poisson))

    # Partidos locales posteriores al corpus público. No se ajusta nada con
    # ellos: sólo se aplican los parámetros congelados. Es un control útil,
    # aunque su tamaño normalmente será demasiado pequeño para decidir.
    por_partido = {
        (r.ht_match_id, r.team_ht_id): r for r in ratings_posteriores
    }

    def ratings_guardados(fila: object) -> dict[str, float] | None:
        nombres = {
            **{campo: campo for campo in ("midfield", "left_def", "central_def", "right_def")},
            **{campo: campo for campo in ("left_att", "central_att", "right_att")},
            "sp_def": "set_pieces_def",
            "sp_att": "set_pieces_att",
        }
        valores = {campo: float(getattr(fila, origen) or 0) for campo, origen in nombres.items()}
        return valores if all(valor > 0 for valor in valores.values()) else None

    holdout: list[tuple[object, dict[str, float], dict[str, float]]] = []
    for partido in posteriores:
        local = por_partido.get((partido.ht_match_id, partido.home_team_ht_id))
        visitante = por_partido.get((partido.ht_match_id, partido.away_team_ht_id))
        if local is None or visitante is None:
            continue
        rl, rv = ratings_guardados(local), ratings_guardados(visitante)
        if rl is not None and rv is not None:
            holdout.append((partido, rl, rv))
    if holdout:
        y_holdout = np.array([resultado(p) for p, _, _ in holdout], dtype=int)
        actual_holdout = np.array(
            [
                [p.derrota, p.empate, p.victoria]
                for p in (probabilidades_del_motor(rl, rv) for _, rl, rv in holdout)
            ]
        )
        poisson_holdout = np.array(
            [
                [p.derrota, p.empate, p.victoria]
                for p in (probabilidades_poisson(rl, rv) for _, rl, rv in holdout)
            ]
        )
        print(
            "\nPARTIDOS POSTERIORES AL CORPUS, PARÁMETROS CONGELADOS "
            f"(n={len(holdout)}; control pequeño, no decide)"
        )
        print(f"  {'modelo':24}{'log-loss':>10}{'Brier':>10}{'1-X-2':>10}{'ECE':>10}")
        _imprimir("Actual 80/20", _metricas(y_holdout, actual_holdout))
        _imprimir("Poisson 100%", _metricas(y_holdout, poisson_holdout))


if __name__ == "__main__":
    asyncio.run(main())
