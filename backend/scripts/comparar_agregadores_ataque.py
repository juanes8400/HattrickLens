"""Producto de ataques frente a noisy-OR, dentro de la Poisson de HT Lens.

Compara dos hipótesis con exactamente siete parámetros y el mismo tratamiento
del mediocampo, la curvatura y el Balón Parado:

    producto: log(p_izq * p_cen * p_der)
    noisy-OR: log(1 - (1-p_izq)(1-p_cen)(1-p_der))

Los parámetros se vuelven a ajustar en cada corte usando sólo fechas
anteriores. Se miden tanto las Poisson puras como su mezcla 80/20 con el mismo
ordinal de la aplicación. Nunca se ajusta con datos privados del manager.

Uso: python scripts/comparar_agregadores_ataque.py
"""

from __future__ import annotations

import argparse
import asyncio
import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaln
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

NOMBRES = ("producto", "noisy-OR")
CLASES = ("derrota", "empate", "victoria")


@dataclass(frozen=True)
class AjustePoisson:
    parametros: np.ndarray
    centro: float
    nll: float
    convergio: bool


@dataclass(frozen=True)
class MetricasResultado:
    log_loss: float
    brier: float
    acierto: float
    auc: float
    ece: float


def proporcion(a: float, b: float) -> float:
    total = a + b
    return max(a / total if total > 0 else 0.5, 1e-3)


def caracteristica_producto(probabilidades: list[float]) -> float:
    return float(np.log(np.prod(probabilidades)))


def caracteristica_noisy_or(probabilidades: list[float]) -> float:
    union = 1.0 - float(np.prod([1.0 - p for p in probabilidades]))
    return float(np.log(max(union, 1e-3)))


AGREGADORES: dict[str, Callable[[list[float]], float]] = {
    "producto": caracteristica_producto,
    "noisy-OR": caracteristica_noisy_or,
}


def lambdas(
    ajuste: AjustePoisson,
    diseno: np.ndarray,
    *,
    tope: float = 12.0,
) -> np.ndarray:
    p = ajuste.parametros
    eta = p[0] + p[1] * diseno[:, 0] + p[2] * diseno[:, 1]
    # El mismo seguro de producción: una parábola cóncava se detiene en el
    # vértice para que ratings todavía mejores nunca reduzcan los goles.
    if p[6] < 0:
        eta = np.minimum(eta, ajuste.centro - 1.0 / (2.0 * p[6]))
    juego = np.exp(np.clip(eta + p[6] * np.square(eta - ajuste.centro), -30, 30))
    bp = np.exp(
        np.clip(p[3] + p[4] * diseno[:, 0] + p[5] * diseno[:, 2], -30, 30)
    )
    return np.clip(juego + bp, 1e-9, tope)


def ajustar_poisson(
    diseno: np.ndarray,
    goles: np.ndarray,
    hasta_partido: int,
    sm: object,
) -> AjustePoisson:
    limite = 2 * hasta_partido
    x = diseno[:limite]
    y = goles[:limite]
    factorial = gammaln(y + 1)
    base = sm.GLM(y, sm.add_constant(x), family=sm.families.Poisson()).fit()
    p0 = np.asarray(base.params, dtype=float)
    centro = float((p0[0] + x @ p0[1:4]).mean())
    inicio = np.array(
        [
            p0[0] - 0.4,
            p0[1],
            p0[2],
            p0[0] - 1.5,
            p0[1] * 0.3,
            p0[3],
            -0.05,
        ],
        dtype=float,
    )

    def objetivo(parametros: np.ndarray) -> float:
        ajuste = AjustePoisson(parametros, centro, 0.0, False)
        lam = lambdas(ajuste, x, tope=12.0)
        valor = -float(np.sum(y * np.log(lam) - lam - factorial))
        return valor if np.isfinite(valor) else 1e100

    # La suma de exponenciales y la parábola hacen que el objetivo no sea
    # convexo. Se prueban los mismos cuatro comienzos para ambos agregadores;
    # así una victoria no puede ser sólo que uno cayó en un mínimo peor.
    comienzos = (
        inicio,
        inicio + np.array([0.1, 0, 0, -0.1, 0, 0, -0.03]),
        inicio + np.array([0, 0, 0, 0, 0, 0, 0.05]),
        inicio + np.array([-0.1, 0, 0, 0.1, 0, 0, -0.10]),
    )
    resultados = [
        minimize(
            objetivo,
            comienzo,
            method="Nelder-Mead",
            options={"maxiter": 60_000, "maxfev": 60_000},
        )
        for comienzo in comienzos
    ]
    mejor = min(resultados, key=lambda r: float(r.fun))
    return AjustePoisson(
        np.asarray(mejor.x, dtype=float),
        centro,
        float(mejor.fun),
        bool(mejor.success),
    )


def reparto(media: float) -> np.ndarray:
    k = np.arange(13)
    log_p = -media + k * np.log(max(media, 1e-9)) - gammaln(k + 1)
    p = np.exp(log_p)
    return p / p.sum()


def probabilidades_resultado(lam: np.ndarray) -> np.ndarray:
    salida = []
    for i in range(0, len(lam), 2):
        rejilla = np.outer(reparto(float(lam[i])), reparto(float(lam[i + 1])))
        victoria = float(np.tril(rejilla, -1).sum())
        empate = float(np.trace(rejilla))
        derrota = float(np.triu(rejilla, 1).sum())
        total = victoria + empate + derrota
        salida.append([derrota / total, empate / total, victoria / total])
    return np.asarray(salida)


def ece(probabilidad: np.ndarray, real: np.ndarray) -> float:
    valor = 0.0
    for i in range(10):
        minimo, maximo = i / 10, (i + 1) / 10
        seleccion = (probabilidad >= minimo) & (
            probabilidad <= maximo if i == 9 else probabilidad < maximo
        )
        if seleccion.any():
            valor += float(seleccion.mean()) * abs(
                float(probabilidad[seleccion].mean()) - float(real[seleccion].mean())
            )
    return valor


def metricas_resultado(y: np.ndarray, p: np.ndarray) -> MetricasResultado:
    from sklearn.metrics import roc_auc_score

    p = np.clip(p, 1e-12, 1.0)
    uno_caliente = np.eye(3)[y]
    return MetricasResultado(
        log_loss=float(-np.log(p[np.arange(len(y)), y]).mean()),
        brier=float(np.square(p - uno_caliente).sum(axis=1).mean()),
        acierto=float((p.argmax(axis=1) == y).mean()),
        auc=float(roc_auc_score(uno_caliente, p, average="macro", multi_class="ovr")),
        ece=float(np.mean([ece(p[:, k], uno_caliente[:, k]) for k in range(3)])),
    )


def intervalo_por_semana(
    diferencia: np.ndarray,
    semanas: list[tuple[int, int]],
    *,
    semilla: int,
) -> tuple[float, float]:
    grupos: dict[tuple[int, int], list[float]] = {}
    for semana, valor in zip(semanas, diferencia, strict=True):
        grupos.setdefault(semana, []).append(float(valor))
    bloques = list(grupos.values())
    rng = np.random.default_rng(semilla)
    muestras = []
    for _ in range(5000):
        indices = rng.integers(0, len(bloques), size=len(bloques))
        valores = [v for indice in indices for v in bloques[int(indice)]]
        muestras.append(float(np.mean(valores)))
    return tuple(float(x) for x in np.quantile(muestras, [0.025, 0.975]))


def intervalo_por_componentes(
    diferencia: np.ndarray,
    componentes: list[int],
    estratos: list[int],
    *,
    semilla: int,
) -> tuple[float, float]:
    """Bootstrap de ligas/componentes completos, estratificado por cohorte."""
    grupos: dict[tuple[int, int], list[float]] = {}
    for estrato, componente, valor in zip(
        estratos, componentes, diferencia, strict=True
    ):
        grupos.setdefault((estrato, componente), []).append(float(valor))
    por_estrato: dict[int, list[list[float]]] = {}
    for (estrato, _), valores in grupos.items():
        por_estrato.setdefault(estrato, []).append(valores)
    rng = np.random.default_rng(semilla)
    muestras = []
    for _ in range(5000):
        valores_muestra: list[float] = []
        for bloques in por_estrato.values():
            indices = rng.integers(0, len(bloques), size=len(bloques))
            valores_muestra.extend(
                valor for indice in indices for valor in bloques[int(indice)]
            )
        muestras.append(float(np.mean(valores_muestra)))
    return tuple(float(x) for x in np.quantile(muestras, [0.025, 0.975]))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cortes",
        choices=("bloques", "porcentajes"),
        default="bloques",
        help=(
            "bloques prueba cada cohorte/temporada completa; porcentajes "
            "reproduce cinco cortes expansivos del comparador anterior"
        ),
    )
    argumentos = parser.parse_args()

    import statsmodels.api as sm
    from statsmodels.miscmodels.ordinal_model import OrderedModel

    from app.core.config import settings
    from app.domain.engines.prediccion import (
        CAMPOS,
        DUELOS_OFENSIVOS,
        ESCALA,
        PESO_GOLES,
        PESO_ORDINAL,
        TIPOS_DE_ENTRENAMIENTO,
        ModeloOrdinal,
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
    if len(partidos) < 500:
        raise SystemExit(f"Sólo hay {len(partidos)} partidos: muestra insuficiente")

    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    y = np.asarray([resultado(p) for p in partidos], dtype=int)
    goles = np.asarray(
        [gol for p in partidos for gol in (p.home_goals, p.away_goals)], dtype=int
    )
    x_ordinal = np.asarray([variables(local, visita) for local, visita in lados])

    medio = DUELOS_OFENSIVOS[0]
    ataques = DUELOS_OFENSIVOS[1:-1]
    bp = DUELOS_OFENSIVOS[-1]

    def fila(
        mio: dict[str, float],
        suyo: dict[str, float],
        agregador: Callable[[list[float]], float],
    ) -> list[float]:
        ps = [proporcion(mio[a], suyo[b]) for _, a, b in ataques]
        return [
            float(np.log(proporcion(mio[medio[1]], suyo[medio[2]]))),
            agregador(ps),
            float(np.log(proporcion(mio[bp[1]], suyo[bp[2]]))),
        ]

    disenos = {
        nombre: np.asarray(
            [
                vector
                for local, visita in lados
                for vector in (fila(local, visita, fn), fila(visita, local, fn))
            ]
        )
        for nombre, fn in AGREGADORES.items()
    }

    n = len(partidos)

    padres: dict[int, int] = {}

    def raiz(equipo: int) -> int:
        padres.setdefault(equipo, equipo)
        while padres[equipo] != equipo:
            padres[equipo] = padres[padres[equipo]]
            equipo = padres[equipo]
        return equipo

    def unir(equipo_a: int, equipo_b: int) -> None:
        raiz_a, raiz_b = raiz(equipo_a), raiz(equipo_b)
        if raiz_a != raiz_b:
            padres[raiz_b] = raiz_a

    for partido in partidos:
        unir(partido.home_team_id, partido.away_team_id)

    def limite(fraccion: float) -> int:
        candidato = min(int(n * fraccion), n - 1)
        instante = partidos[candidato].played_at
        while candidato > 0 and partidos[candidato - 1].played_at == instante:
            candidato -= 1
        return candidato

    if argumentos.cortes == "porcentajes":
        limites = [limite(f) for f in (0.40, 0.52, 0.64, 0.76, 0.88)] + [n]
        cortes = list(zip(limites[:-1], limites[1:], strict=True))
        descripcion_cortes = "cinco cortes expansivos por porcentaje"
    else:
        # El corpus son cohortes completas de 14 fechas separadas por huecos
        # largos. Probar cada cohorte nueva evita mezclar, en un mismo fold,
        # equipos ya vistos con ligas enteramente desconocidas.
        fronteras = [0]
        for indice in range(1, n):
            if (partidos[indice].played_at - partidos[indice - 1].played_at).days > 21:
                fronteras.append(indice)
        fronteras.append(n)
        if len(fronteras) < 3:
            raise RuntimeError("No se encontraron al menos dos bloques temporales")
        cortes = [
            (fronteras[indice], fronteras[indice + 1])
            for indice in range(1, len(fronteras) - 1)
        ]
        descripcion_cortes = (
            f"{len(cortes)} cohortes completas; la primera sólo ajusta"
        )
    for inicio, fin in cortes:
        if partidos[inicio - 1].played_at >= partidos[inicio].played_at:
            raise RuntimeError("Un corte partió la misma fecha entre ajuste y prueba")
        if inicio >= fin:
            raise RuntimeError("Corte temporal vacío")

    probabilidades: dict[str, list[np.ndarray]] = {
        f"puro {nombre}": [] for nombre in NOMBRES
    } | {f"80/20 {nombre}": [] for nombre in NOMBRES}
    lambdas_por_modelo: dict[str, list[np.ndarray]] = {nombre: [] for nombre in NOMBRES}
    reales: list[np.ndarray] = []
    semanas: list[tuple[int, int]] = []
    componentes: list[int] = []
    estratos: list[int] = []
    tacticas: list[str] = []
    dispersion: list[float] = []
    rangos: list[float] = []
    tabla_cortes: list[tuple[int, str, float, float, float]] = []
    parametros_cortes: dict[str, list[np.ndarray]] = {nombre: [] for nombre in NOMBRES}

    print(
        f"{n} partidos públicos de liga: {partidos[0].played_at:%Y-%m-%d} a "
        f"{partidos[-1].played_at:%Y-%m-%d}"
    )
    print(f"Cortes: {descripcion_cortes}")
    print(f"Prueba cronológica: {sum(fin - ini for ini, fin in cortes)} partidos")
    print("Mismos 7 parámetros; sólo cambia cómo se juntan I/C/D.\n")

    for numero, (inicio, fin) in enumerate(cortes, start=1):
        ordinal_ref = OrderedModel(y[:inicio], x_ordinal[:inicio], distr="logit").fit(
            method="bfgs", disp=False, maxiter=3000
        )
        k = x_ordinal.shape[1]
        u1 = float(ordinal_ref.params[k])
        ordinal = ModeloOrdinal(
            beta=np.asarray(ordinal_ref.params[:k], dtype=float) / ESCALA,
            umbrales=np.asarray(
                [u1, u1 + float(np.exp(ordinal_ref.params[k + 1]))]
            )
            / ESCALA,
        )
        p_ordinal = np.asarray(
            [
                [p.derrota, p.empate, p.victoria]
                for p in (ordinal.probabilidades(x) for x in x_ordinal[inicio:fin])
            ]
        )

        yy = y[inicio:fin]
        goles_del_corte = goles[2 * inicio : 2 * fin]
        reales.append(yy)
        semanas.extend(
            (p.played_at.isocalendar().year, p.played_at.isocalendar().week)
            for p in partidos[inicio:fin]
        )
        componentes.extend(raiz(p.home_team_id) for p in partidos[inicio:fin])
        estratos.extend([numero] * (fin - inicio))
        for partido in partidos[inicio:fin]:
            tipos = (partido.home_tactic_type, partido.away_tactic_type)
            if tipos == (0, 0):
                tacticas.append("ambos Normal")
            elif any(tipo in (3, 4) for tipo in tipos):
                tacticas.append("algún AIM/AOW")
            else:
                tacticas.append("otras tácticas")
        for local, visita in lados[inicio:fin]:
            for mio, suyo in ((local, visita), (visita, local)):
                ps = [proporcion(mio[a], suyo[b]) for _, a, b in ataques]
                dispersion.append(max(ps) - float(np.median(ps)))
                rangos.append(max(ps) - min(ps))

        for nombre in NOMBRES:
            ajuste = ajustar_poisson(disenos[nombre], goles, inicio, sm)
            if not ajuste.convergio:
                raise RuntimeError(f"{nombre} no convergió en el corte {numero}")
            parametros_cortes[nombre].append(ajuste.parametros)
            lam = lambdas(ajuste, disenos[nombre][2 * inicio : 2 * fin])
            lambdas_por_modelo[nombre].append(lam)
            p_puro = probabilidades_resultado(lam)
            p_mixto = PESO_GOLES * p_puro + PESO_ORDINAL * p_ordinal
            probabilidades[f"puro {nombre}"].append(p_puro)
            probabilidades[f"80/20 {nombre}"].append(p_mixto)
            tabla_cortes.append(
                (
                    numero,
                    nombre,
                    float(
                        np.mean(
                            lam
                            - goles_del_corte * np.log(np.clip(lam, 1e-12, None))
                            + gammaln(goles_del_corte + 1)
                        )
                    ),
                    metricas_resultado(yy, p_puro).log_loss,
                    metricas_resultado(yy, p_mixto).log_loss,
                )
            )
        fila_corte = [x for x in tabla_cortes if x[0] == numero]
        print(
            f"corte {numero}: "
            + " · ".join(
                f"{nombre} NLL-gol {nll:.4f}, 1X2 {puro:.4f}, 80/20 {mixto:.4f}"
                for _, nombre, nll, puro, mixto in fila_corte
            )
        )

    yy = np.concatenate(reales)
    pred = {nombre: np.vstack(bloques) for nombre, bloques in probabilidades.items()}
    lam = {nombre: np.concatenate(bloques) for nombre, bloques in lambdas_por_modelo.items()}
    goles_prueba = np.concatenate(
        [goles[2 * inicio : 2 * fin] for inicio, fin in cortes]
    )

    print("\nRESULTADO 1-X-2 (más bajo es mejor, salvo acierto y AUC)")
    print(
        f"  {'modelo':22}{'log-loss':>10}{'Brier':>10}{'acierto':>10}"
        f"{'AUC':>9}{'ECE':>9}"
    )
    for nombre in (
        "puro producto",
        "puro noisy-OR",
        "80/20 producto",
        "80/20 noisy-OR",
    ):
        m = metricas_resultado(yy, pred[nombre])
        print(
            f"  {nombre:22}{m.log_loss:>10.4f}{m.brier:>10.4f}"
            f"{m.acierto:>10.2%}{m.auc:>9.4f}{m.ece:>9.4f}"
        )

    perdida_resultado = {
        nombre: -np.log(np.clip(p[np.arange(len(yy)), yy], 1e-12, 1.0))
        for nombre, p in pred.items()
    }
    print("\nDIFERENCIA PAREADA: positivo significa que noisy-OR mejora")
    for prefijo in ("puro", "80/20"):
        diferencia = (
            perdida_resultado[f"{prefijo} producto"]
            - perdida_resultado[f"{prefijo} noisy-OR"]
        )
        bajo, alto = intervalo_por_semana(
            diferencia, semanas, semilla=20260911 + len(prefijo)
        )
        bajo_comp, alto_comp = intervalo_por_componentes(
            diferencia,
            componentes,
            estratos,
            semilla=20261011 + len(prefijo),
        )
        print(
            f"  {prefijo:6}: {diferencia.mean():+.6f} log-loss "
            f"(IC 95% semanal {bajo:+.6f} a {alto:+.6f}; "
            f"por liga {bajo_comp:+.6f} a {alto_comp:+.6f})"
        )

    print("\nGOLES POR LADO")
    print(f"  {'modelo':12}{'NLL':>10}{'EAM':>10}{'RMSE':>10}{'sesgo':>10}")
    perdida_gol: dict[str, np.ndarray] = {}
    for nombre in NOMBRES:
        perdida_gol[nombre] = (
            lam[nombre]
            - goles_prueba * np.log(np.clip(lam[nombre], 1e-12, None))
            + gammaln(goles_prueba + 1)
        )
        error = lam[nombre] - goles_prueba
        print(
            f"  {nombre:12}{perdida_gol[nombre].mean():>10.4f}"
            f"{np.abs(error).mean():>10.4f}{np.sqrt(np.square(error).mean()):>10.4f}"
            f"{error.mean():>+10.4f}"
        )
    # La unidad primaria es el partido completo: suma la log-verosimilitud de
    # sus dos lados y luego agrupa partidos por semana o liga.
    dif_gol_partido = (
        perdida_gol["producto"].reshape(-1, 2).sum(axis=1)
        - perdida_gol["noisy-OR"].reshape(-1, 2).sum(axis=1)
    )
    bajo, alto = intervalo_por_semana(dif_gol_partido, semanas, semilla=20260913)
    bajo_comp, alto_comp = intervalo_por_componentes(
        dif_gol_partido,
        componentes,
        estratos,
        semilla=20261013,
    )
    print(
        f"  mejora noisy-OR: {dif_gol_partido.mean():+.6f} NLL conjunta/partido "
        f"(IC 95% semanal {bajo:+.6f} a {alto:+.6f}; "
        f"por liga {bajo_comp:+.6f} a {alto_comp:+.6f})"
    )

    print("\nCALIBRACIÓN DE GOLES (ideal: intercepto 0, pendiente 1, Pearson 1)")
    for nombre in NOMBRES:
        calibracion = sm.GLM(
            goles_prueba,
            sm.add_constant(np.log(np.clip(lam[nombre], 1e-12, None))),
            family=sm.families.Poisson(),
        ).fit()
        pearson = float(
            np.sum(np.square(goles_prueba - lam[nombre]) / lam[nombre])
            / (len(goles_prueba) - 2)
        )
        print(
            f"  {nombre:12} intercepto {calibracion.params[0]:+.4f} · "
            f"pendiente {calibracion.params[1]:.4f} · Pearson {pearson:.4f}"
        )

    observado_cero_cero = float(
        np.mean(goles_prueba.reshape(-1, 2).sum(axis=1) == 0)
    )
    observado_bajo = float(
        np.mean(goles_prueba.reshape(-1, 2).sum(axis=1) <= 1)
    )
    print("\nCOLA DE MARCADORES BAJOS: prometido / ocurrido")
    for nombre in NOMBRES:
        total_esperado = lam[nombre].reshape(-1, 2).sum(axis=1)
        cero_cero = float(np.exp(-total_esperado).mean())
        hasta_uno = float((np.exp(-total_esperado) * (1 + total_esperado)).mean())
        print(
            f"  {nombre:12} 0-0 {cero_cero:.2%} / {observado_cero_cero:.2%} · "
            f"0–1 goles {hasta_uno:.2%} / {observado_bajo:.2%}"
        )

    print("\nMARCADOR EXACTO")
    for nombre in NOMBRES:
        aciertos = 0
        for i in range(0, len(lam[nombre]), 2):
            rejilla = np.outer(reparto(lam[nombre][i]), reparto(lam[nombre][i + 1]))
            predicho = np.unravel_index(int(rejilla.argmax()), rejilla.shape)
            real = (int(goles_prueba[i]), int(goles_prueba[i + 1]))
            aciertos += int(predicho == real)
        print(f"  {nombre:12}{aciertos:>5}/{len(yy)} = {aciertos / len(yy):.2%}")

    print("\nCALIBRACIÓN 1-X-2: promedio prometido / ocurrido; ECE")
    for clase, indice in zip(CLASES, range(3), strict=True):
        observado = (yy == indice).astype(float)
        print(f"  {clase}")
        for nombre in ("80/20 producto", "80/20 noisy-OR"):
            print(
                f"    {nombre:20}{pred[nombre][:, indice].mean():>7.2%} / "
                f"{observado.mean():>7.2%}; ECE {ece(pred[nombre][:, indice], observado):.4f}"
            )

    # La hipótesis noisy-OR debería ayudar especialmente cuando una sola vía
    # es mucho mejor que las otras. Se comprueba sobre lados, no partidos.
    disp = np.asarray(dispersion)
    bordes = np.quantile(disp, [0, 0.25, 0.5, 0.75, 1.0])
    print("\nDÓNDE DIFIEREN: dominio de una vía sobre la mediana de las otras")
    print(f"  {'tramo':19}{'lados':>8}{'NLL prod':>11}{'NLL OR':>10}{'mejora OR':>11}")
    for i, (lo, hi) in enumerate(zip(bordes[:-1], bordes[1:], strict=True)):
        seleccion = (disp >= lo) & (disp <= hi if i == 3 else disp < hi)
        diferencia = (
            perdida_gol["producto"][seleccion].mean()
            - perdida_gol["noisy-OR"][seleccion].mean()
        )
        print(
            f"  {lo:.3f}–{hi:.3f}{seleccion.sum():>10}"
            f"{perdida_gol['producto'][seleccion].mean():>11.4f}"
            f"{perdida_gol['noisy-OR'][seleccion].mean():>10.4f}{diferencia:>+11.4f}"
        )

    print("\nSENSIBILIDAD POR CONCENTRACIÓN (diagnóstico, no selección)")
    rango = np.asarray(rangos)
    for etiqueta, seleccion in (
        ("rango de carriles <= 0,15", rango <= 0.15),
        ("rango de carriles > 0,15", rango > 0.15),
    ):
        mejora = (
            perdida_gol["producto"][seleccion].mean()
            - perdida_gol["noisy-OR"][seleccion].mean()
        )
        print(
            f"  {etiqueta:29} n={seleccion.sum():>5} lados · "
            f"mejora OR {mejora:+.4f} NLL"
        )

    print("\nSENSIBILIDAD POR TÁCTICA (diagnóstico, no selección)")
    tactica = np.asarray(tacticas)
    for etiqueta in ("ambos Normal", "algún AIM/AOW", "otras tácticas"):
        seleccion_partido = tactica == etiqueta
        seleccion_lado = np.repeat(seleccion_partido, 2)
        mejora_gol = (
            perdida_gol["producto"][seleccion_lado].mean()
            - perdida_gol["noisy-OR"][seleccion_lado].mean()
        )
        mejora_1x2 = (
            perdida_resultado["puro producto"][seleccion_partido].mean()
            - perdida_resultado["puro noisy-OR"][seleccion_partido].mean()
        )
        print(
            f"  {etiqueta:16} n={seleccion_partido.sum():>4} partidos · "
            f"mejora OR {mejora_gol:+.4f} NLL-gol, {mejora_1x2:+.4f} 1X2"
        )

    print("\nAJUSTE COMPLETO DESCRIPTIVO (mismos 7 parámetros)")
    completos: dict[str, AjustePoisson] = {}
    for nombre in NOMBRES:
        completos[nombre] = ajustar_poisson(disenos[nombre], goles, n, sm)
        ajuste = completos[nombre]
        print(
            f"  {nombre:12} NLL {ajuste.nll:.2f} · AIC {2 * ajuste.nll + 14:.2f} "
            f"· convergió {'sí' if ajuste.convergio else 'NO'}"
        )
        etiquetas = ("A", "B medio", "C ataques", "A BP", "B BP-medio", "C BP", "curva")
        print(
            "    "
            + " · ".join(
                f"{etiqueta}={valor:+.5f}"
                for etiqueta, valor in zip(etiquetas, ajuste.parametros, strict=True)
            )
        )
        parametros = ajuste.parametros
        eta_sin_tope = (
            parametros[0]
            + parametros[1] * disenos[nombre][:, 0]
            + parametros[2] * disenos[nombre][:, 1]
        )
        vertice = (
            ajuste.centro - 1.0 / (2.0 * parametros[6])
            if parametros[6] < 0
            else float("inf")
        )
        eta = np.minimum(eta_sin_tope, vertice)
        juego = np.exp(eta + parametros[6] * np.square(eta - ajuste.centro))
        bp_estimado = np.exp(
            parametros[3]
            + parametros[4] * disenos[nombre][:, 0]
            + parametros[5] * disenos[nombre][:, 2]
        )
        print(
            f"    centro={ajuste.centro:.5f} · vértice={vertice:.5f} · "
            f"eta capada={(eta_sin_tope > vertice).mean():.2%} · "
            f"lambda capada={(juego + bp_estimado >= 12).mean():.2%}"
        )
        print(
            f"    media juego abierto={juego.mean():.4f} · "
            f"media BP={bp_estimado.mean():.4f}"
        )

    print("\nCONTRAFACTUALES CON MEDIO=BP=0,50 (lambda total por lado)")
    perfiles = (
        ("equilibrado", [0.5, 0.5, 0.5]),
        ("misma media, concentrado", [0.8, 0.5, 0.2]),
        ("equilibrado débil", [0.4, 0.4, 0.4]),
        ("una vía fuerte", [0.8, 0.2, 0.2]),
    )
    for etiqueta, ps in perfiles:
        valores = []
        for nombre in NOMBRES:
            diseno = np.asarray(
                [[np.log(0.5), AGREGADORES[nombre](ps), np.log(0.5)]]
            )
            valores.append(float(lambdas(completos[nombre], diseno)[0]))
        print(
            f"  {etiqueta:24} p={ps} · producto {valores[0]:.3f} · "
            f"noisy-OR {valores[1]:.3f}"
        )

    # Los partidos propios posteriores al último dato público son un control
    # congelado: se evalúan, pero jamás participan en el ajuste.
    por_partido = {
        (r.ht_match_id, r.team_ht_id): r for r in ratings_posteriores
    }

    def ratings_guardados(fila_rating: object) -> dict[str, float] | None:
        nombres = {
            **{
                campo: campo
                for campo in ("midfield", "left_def", "central_def", "right_def")
            },
            **{
                campo: campo
                for campo in ("left_att", "central_att", "right_att")
            },
            "sp_def": "set_pieces_def",
            "sp_att": "set_pieces_att",
        }
        valores = {
            campo: float(getattr(fila_rating, origen) or 0)
            for campo, origen in nombres.items()
        }
        return valores if all(valor > 0 for valor in valores.values()) else None

    holdout: list[tuple[object, dict[str, float], dict[str, float]]] = []
    for partido in posteriores:
        local = por_partido.get((partido.ht_match_id, partido.home_team_ht_id))
        visita = por_partido.get((partido.ht_match_id, partido.away_team_ht_id))
        if local is None or visita is None:
            continue
        ratings_local = ratings_guardados(local)
        ratings_visita = ratings_guardados(visita)
        if ratings_local is not None and ratings_visita is not None:
            holdout.append((partido, ratings_local, ratings_visita))

    if holdout:
        y_holdout = np.asarray([resultado(p) for p, _, _ in holdout], dtype=int)
        goles_holdout = np.asarray(
            [
                gol
                for p, _, _ in holdout
                for gol in (p.home_goals, p.away_goals)
            ],
            dtype=int,
        )
        ordinal_ref = OrderedModel(y, x_ordinal, distr="logit").fit(
            method="bfgs", disp=False, maxiter=3000
        )
        k = x_ordinal.shape[1]
        u1 = float(ordinal_ref.params[k])
        ordinal_completo = ModeloOrdinal(
            beta=np.asarray(ordinal_ref.params[:k], dtype=float) / ESCALA,
            umbrales=np.asarray(
                [u1, u1 + float(np.exp(ordinal_ref.params[k + 1]))]
            )
            / ESCALA,
        )
        p_ordinal_holdout = np.asarray(
            [
                [p.derrota, p.empate, p.victoria]
                for p in (
                    ordinal_completo.probabilidades(variables(local, visita))
                    for _, local, visita in holdout
                )
            ]
        )
        print(
            "\nCONTROL LOCAL POSTERIOR, PARÁMETROS PÚBLICOS CONGELADOS "
            f"(n={len(holdout)}; demasiado pequeño para decidir)"
        )
        print(
            f"  {'modelo':12}{'NLL-gol':>10}{'1X2 puro':>12}"
            f"{'1X2 80/20':>13}{'acierto':>10}"
        )
        for nombre in NOMBRES:
            diseno_holdout = np.asarray(
                [
                    vector
                    for _, local, visita in holdout
                    for vector in (
                        fila(local, visita, AGREGADORES[nombre]),
                        fila(visita, local, AGREGADORES[nombre]),
                    )
                ]
            )
            lam_holdout = lambdas(completos[nombre], diseno_holdout)
            p_puro = probabilidades_resultado(lam_holdout)
            p_mixto = PESO_GOLES * p_puro + PESO_ORDINAL * p_ordinal_holdout
            nll_gol = float(
                np.mean(
                    lam_holdout
                    - goles_holdout * np.log(np.clip(lam_holdout, 1e-12, None))
                    + gammaln(goles_holdout + 1)
                )
            )
            metrica_pura = metricas_resultado(y_holdout, p_puro)
            metrica_mixta = metricas_resultado(y_holdout, p_mixto)
            print(
                f"  {nombre:12}{nll_gol:>10.4f}{metrica_pura.log_loss:>12.4f}"
                f"{metrica_mixta.log_loss:>13.4f}{metrica_mixta.acierto:>10.2%}"
            )

    # Control algebraico: ambos diseños usan los mismos campos y ninguna fila
    # desapareció. Dejarlo impreso ayuda a detectar una comparación accidental.
    assert len(disenos["producto"]) == len(disenos["noisy-OR"]) == 2 * n
    assert set(CAMPOS) == {
        "midfield",
        "left_def",
        "central_def",
        "right_def",
        "left_att",
        "central_att",
        "right_att",
        "sp_def",
        "sp_att",
    }


if __name__ == "__main__":
    asyncio.run(main())
