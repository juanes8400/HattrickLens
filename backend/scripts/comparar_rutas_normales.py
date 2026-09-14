"""Compara agregadores de ataque sólo en partidos con táctica Normal.

La candidata principal trata cada ocasión como una ruta mutuamente excluyente:

    lambda_juego = exp(A) * p_medio**B
                    * (0.30*p_izq**C + 0.40*p_cen**C + 0.30*p_der**C)

Se conservan el sumando separado de Balón Parado, la descompresión cuadrática,
el tope de producción y la mezcla 80/20 con el ordinal. Los siete parámetros
se reajustan desde cero en cada corte; nunca se usan datos privados para ajustar.

Uso: python scripts/comparar_rutas_normales.py
"""

from __future__ import annotations

import asyncio
import warnings
from dataclasses import dataclass

import numpy as np
from comparar_agregadores_ataque import (
    intervalo_por_componentes,
    intervalo_por_semana,
    metricas_resultado,
    probabilidades_resultado,
)
from scipy.optimize import minimize
from scipy.special import gammaln, logsumexp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

MODELOS = (
    "producto",
    "noisy-OR",
    "geométrico 30/40/30",
    "rutas 30/40/30",
)
PESOS_RUTA = np.asarray([0.30, 0.40, 0.30], dtype=float)
LOG_PESOS_RUTA = np.log(PESOS_RUTA)


@dataclass(frozen=True)
class Ajuste:
    parametros: np.ndarray
    centro: float
    nll: float
    convergio: bool


def proporcion(a: float, b: float) -> float:
    total = a + b
    return max(a / total if total > 0 else 0.5, 1e-3)


def termino_de_ataque(
    nombre: str,
    exponente: float,
    log_carriles: np.ndarray,
) -> np.ndarray:
    """Aporte a eta de los tres carriles para cada arquitectura."""
    if nombre == "producto":
        return exponente * log_carriles.sum(axis=1)
    if nombre == "noisy-OR":
        carriles = np.exp(log_carriles)
        log_fallo = np.log1p(-carriles).sum(axis=1)
        union = -np.expm1(log_fallo)
        return exponente * np.log(np.clip(union, 1e-12, 1.0))
    if nombre == "geométrico 30/40/30":
        return exponente * (log_carriles @ PESOS_RUTA)
    if nombre == "rutas 30/40/30":
        return logsumexp(
            exponente * log_carriles + LOG_PESOS_RUTA,
            axis=1,
        )
    raise ValueError(f"Modelo desconocido: {nombre}")


def lambdas(
    ajuste: Ajuste,
    diseno: np.ndarray,
    nombre: str,
    *,
    tope: float = 12.0,
) -> np.ndarray:
    parametros = ajuste.parametros
    eta = (
        parametros[0]
        + parametros[1] * diseno[:, 0]
        + termino_de_ataque(nombre, parametros[2], diseno[:, 1:4])
    )
    if parametros[6] < 0:
        vertice = ajuste.centro - 1.0 / (2.0 * parametros[6])
        eta = np.minimum(eta, vertice)
    juego = np.exp(
        np.clip(
            eta + parametros[6] * np.square(eta - ajuste.centro),
            -30,
            30,
        )
    )
    balon_parado = np.exp(
        np.clip(
            parametros[3]
            + parametros[4] * diseno[:, 0]
            + parametros[5] * diseno[:, 4],
            -30,
            30,
        )
    )
    return np.clip(juego + balon_parado, 1e-9, tope)


def rasgo_inicial(nombre: str, diseno: np.ndarray) -> np.ndarray:
    log_carriles = diseno[:, 1:4]
    if nombre == "producto":
        return log_carriles.sum(axis=1)
    if nombre == "noisy-OR":
        carriles = np.exp(log_carriles)
        return np.log(
            np.clip(-np.expm1(np.log1p(-carriles).sum(axis=1)), 1e-12, 1.0)
        )
    if nombre == "geométrico 30/40/30":
        return log_carriles @ PESOS_RUTA
    if nombre == "rutas 30/40/30":
        # Sólo inicializa el optimizador. El ajuste final usa el exponente
        # dentro de la suma, tal como dice la ecuación del experimento.
        return np.log(np.exp(log_carriles) @ PESOS_RUTA)
    raise ValueError(f"Modelo desconocido: {nombre}")


def ajustar(
    nombre: str,
    diseno: np.ndarray,
    goles: np.ndarray,
    hasta_partido: int,
    sm: object,
) -> Ajuste:
    limite = 2 * hasta_partido
    x = diseno[:limite]
    y = goles[:limite]
    factorial = gammaln(y + 1)
    inicial_glm = np.column_stack(
        (x[:, 0], rasgo_inicial(nombre, x), x[:, 4])
    )
    base = sm.GLM(
        y,
        sm.add_constant(inicial_glm),
        family=sm.families.Poisson(),
    ).fit()
    p0 = np.asarray(base.params, dtype=float)
    centro = float((p0[0] + inicial_glm @ p0[1:4]).mean())
    inicio = np.asarray(
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
        candidato = Ajuste(parametros, centro, 0.0, False)
        lam = lambdas(candidato, x, nombre)
        valor = -float(np.sum(y * np.log(lam) - lam - factorial))
        return valor if np.isfinite(valor) else 1e100

    comienzos = (
        inicio,
        inicio + np.asarray([0.1, 0, 0, -0.1, 0, 0, -0.03]),
        inicio + np.asarray([0, 0, 0, 0, 0, 0, 0.05]),
        inicio + np.asarray([-0.1, 0, 0, 0.1, 0, 0, -0.10]),
        inicio * np.asarray([1, 1, 0.65, 1, 1, 1, 1]),
        inicio * np.asarray([1, 1, 1.35, 1, 1, 1, 1]),
    )
    resultados = [
        minimize(
            objetivo,
            comienzo,
            method="Nelder-Mead",
            options={"maxiter": 80_000, "maxfev": 80_000},
        )
        for comienzo in comienzos
    ]
    mejor = min(resultados, key=lambda resultado: float(resultado.fun))
    return Ajuste(
        parametros=np.asarray(mejor.x, dtype=float),
        centro=centro,
        nll=float(mejor.fun),
        convergio=bool(mejor.success),
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
        ratings_de,
        resultado,
        variables,
    )
    from app.infrastructure.db import models as m

    warnings.filterwarnings("ignore")
    engine = create_async_engine(settings.database_url)
    async with async_sessionmaker(engine)() as session:
        todos = list(
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
    await engine.dispose()

    partidos = [
        partido
        for partido in todos
        if partido.home_tactic_type in (None, 0)
        and partido.away_tactic_type in (None, 0)
    ]
    if len(partidos) < 500:
        raise SystemExit(f"Sólo quedaron {len(partidos)} partidos Normal")

    lados = [(ratings_de(p, "home"), ratings_de(p, "away")) for p in partidos]
    y = np.asarray([resultado(p) for p in partidos], dtype=int)
    goles = np.asarray(
        [gol for p in partidos for gol in (p.home_goals, p.away_goals)],
        dtype=int,
    )
    x_ordinal = np.asarray([variables(local, visita) for local, visita in lados])

    medio = DUELOS_OFENSIVOS[0]
    ataques = DUELOS_OFENSIVOS[1:-1]
    bp = DUELOS_OFENSIVOS[-1]

    def fila(mio: dict[str, float], suyo: dict[str, float]) -> list[float]:
        return [
            float(np.log(proporcion(mio[medio[1]], suyo[medio[2]]))),
            *[
                float(np.log(proporcion(mio[ataque], suyo[defensa])))
                for _, ataque, defensa in ataques
            ],
            float(np.log(proporcion(mio[bp[1]], suyo[bp[2]]))),
        ]

    diseno = np.asarray(
        [
            vector
            for local, visita in lados
            for vector in (fila(local, visita), fila(visita, local))
        ]
    )
    n = len(partidos)
    fronteras = [0]
    for indice in range(1, n):
        if (partidos[indice].played_at - partidos[indice - 1].played_at).days > 21:
            fronteras.append(indice)
    fronteras.append(n)
    cortes = [
        (fronteras[indice], fronteras[indice + 1])
        for indice in range(1, len(fronteras) - 1)
    ]
    if not cortes:
        raise RuntimeError("No se encontraron cohortes temporales completas")

    padres: dict[int, int] = {}

    def raiz(equipo: int) -> int:
        padres.setdefault(equipo, equipo)
        while padres[equipo] != equipo:
            padres[equipo] = padres[padres[equipo]]
            equipo = padres[equipo]
        return equipo

    def unir(a: int, b: int) -> None:
        raiz_a, raiz_b = raiz(a), raiz(b)
        if raiz_a != raiz_b:
            padres[raiz_b] = raiz_a

    for partido in partidos:
        unir(partido.home_team_id, partido.away_team_id)

    probabilidades: dict[str, list[np.ndarray]] = {
        nombre: [] for nombre in MODELOS
    }
    probabilidades_mixtas: dict[str, list[np.ndarray]] = {
        nombre: [] for nombre in MODELOS
    }
    lambdas_por_modelo: dict[str, list[np.ndarray]] = {
        nombre: [] for nombre in MODELOS
    }
    reales: list[np.ndarray] = []
    semanas: list[tuple[int, int]] = []
    componentes: list[int] = []
    estratos: list[int] = []

    print(
        f"Partidos de Liga: {len(todos)} totales; {n} con ambos equipos "
        "en Normal/vacío"
    )
    print(
        f"Cobertura Normal: {partidos[0].played_at:%Y-%m-%d} a "
        f"{partidos[-1].played_at:%Y-%m-%d}"
    )
    print(
        f"Prueba: {len(cortes)} cohortes completas, "
        f"{sum(fin - inicio for inicio, fin in cortes)} partidos OOF\n"
    )

    for numero, (inicio, fin) in enumerate(cortes, start=1):
        ordinal_ref = OrderedModel(
            y[:inicio], x_ordinal[:inicio], distr="logit"
        ).fit(method="bfgs", disp=False, maxiter=3000)
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
                for p in (
                    ordinal.probabilidades(vector)
                    for vector in x_ordinal[inicio:fin]
                )
            ]
        )

        yy = y[inicio:fin]
        goles_corte = goles[2 * inicio : 2 * fin]
        reales.append(yy)
        semanas.extend(
            (p.played_at.isocalendar().year, p.played_at.isocalendar().week)
            for p in partidos[inicio:fin]
        )
        componentes.extend(raiz(p.home_team_id) for p in partidos[inicio:fin])
        estratos.extend([numero] * (fin - inicio))

        resultados_corte = []
        for nombre in MODELOS:
            ajuste = ajustar(nombre, diseno, goles, inicio, sm)
            if not ajuste.convergio:
                raise RuntimeError(f"{nombre} no convergió en corte {numero}")
            lam = lambdas(ajuste, diseno[2 * inicio : 2 * fin], nombre)
            p_puro = probabilidades_resultado(lam)
            p_mixto = PESO_GOLES * p_puro + PESO_ORDINAL * p_ordinal
            lambdas_por_modelo[nombre].append(lam)
            probabilidades[nombre].append(p_puro)
            probabilidades_mixtas[nombre].append(p_mixto)
            nll = float(
                np.mean(
                    lam
                    - goles_corte * np.log(np.clip(lam, 1e-12, None))
                    + gammaln(goles_corte + 1)
                )
            )
            resultados_corte.append(
                (
                    nombre,
                    nll,
                    metricas_resultado(yy, p_puro).log_loss,
                    metricas_resultado(yy, p_mixto).log_loss,
                )
            )
        print(f"corte {numero}: n={fin - inicio}")
        for nombre, nll, puro, mixto in resultados_corte:
            print(
                f"  {nombre:23} NLL-gol {nll:.4f} · "
                f"1X2 {puro:.4f} · 80/20 {mixto:.4f}"
            )

    yy = np.concatenate(reales)
    goles_oof = np.concatenate(
        [goles[2 * inicio : 2 * fin] for inicio, fin in cortes]
    )
    pred = {nombre: np.vstack(bloques) for nombre, bloques in probabilidades.items()}
    pred_mixta = {
        nombre: np.vstack(bloques)
        for nombre, bloques in probabilidades_mixtas.items()
    }
    lam = {
        nombre: np.concatenate(bloques)
        for nombre, bloques in lambdas_por_modelo.items()
    }

    print("\nRESULTADO AGREGADO FUERA DE MUESTRA")
    print(
        f"  {'modelo':23}{'NLL-gol':>10}{'EAM':>9}{'1X2':>9}"
        f"{'80/20':>9}{'Brier':>9}{'acierto':>10}"
    )
    perdidas_gol: dict[str, np.ndarray] = {}
    perdidas_1x2: dict[str, np.ndarray] = {}
    perdidas_mixtas: dict[str, np.ndarray] = {}
    for nombre in MODELOS:
        perdidas_gol[nombre] = (
            lam[nombre]
            - goles_oof * np.log(np.clip(lam[nombre], 1e-12, None))
            + gammaln(goles_oof + 1)
        )
        perdidas_1x2[nombre] = -np.log(
            np.clip(pred[nombre][np.arange(len(yy)), yy], 1e-12, 1.0)
        )
        perdidas_mixtas[nombre] = -np.log(
            np.clip(pred_mixta[nombre][np.arange(len(yy)), yy], 1e-12, 1.0)
        )
        metrica_pura = metricas_resultado(yy, pred[nombre])
        metrica_mixta = metricas_resultado(yy, pred_mixta[nombre])
        print(
            f"  {nombre:23}{perdidas_gol[nombre].mean():>10.4f}"
            f"{np.abs(lam[nombre] - goles_oof).mean():>9.4f}"
            f"{metrica_pura.log_loss:>9.4f}{metrica_mixta.log_loss:>9.4f}"
            f"{metrica_mixta.brier:>9.4f}{metrica_mixta.acierto:>10.2%}"
        )

    print("\nDIFERENCIAS CONTRA PRODUCTO: positivo favorece al candidato")
    for nombre in MODELOS[1:]:
        diferencia_gol = (
            perdidas_gol["producto"].reshape(-1, 2).sum(axis=1)
            - perdidas_gol[nombre].reshape(-1, 2).sum(axis=1)
        )
        diferencia_mixta = perdidas_mixtas["producto"] - perdidas_mixtas[nombre]
        semana_gol = intervalo_por_semana(
            diferencia_gol, semanas, semilla=20260921 + len(nombre)
        )
        liga_gol = intervalo_por_componentes(
            diferencia_gol,
            componentes,
            estratos,
            semilla=20261021 + len(nombre),
        )
        liga_mixta = intervalo_por_componentes(
            diferencia_mixta,
            componentes,
            estratos,
            semilla=20261121 + len(nombre),
        )
        print(f"  {nombre}")
        print(
            f"    NLL conjunta/partido {diferencia_gol.mean():+.6f} · "
            f"IC semana [{semana_gol[0]:+.6f}, {semana_gol[1]:+.6f}] · "
            f"IC liga [{liga_gol[0]:+.6f}, {liga_gol[1]:+.6f}]"
        )
        print(
            f"    log-loss 80/20 {diferencia_mixta.mean():+.6f} · "
            f"IC liga [{liga_mixta[0]:+.6f}, {liga_mixta[1]:+.6f}]"
        )

    print("\nAJUSTE COMPLETO DESCRIPTIVO (7 parámetros cada uno)")
    completos: dict[str, Ajuste] = {}
    for nombre in MODELOS:
        ajuste = ajustar(nombre, diseno, goles, n, sm)
        completos[nombre] = ajuste
        valores = " · ".join(f"{valor:+.5f}" for valor in ajuste.parametros)
        print(
            f"  {nombre:23} NLL {ajuste.nll:.2f} · "
            f"AIC {2 * ajuste.nll + 14:.2f} · convergió "
            f"{'sí' if ajuste.convergio else 'NO'}"
        )
        print(f"    [A, B medio, C, A BP, B BP-medio, C BP, curva] = {valores}")

    print("\nCONTRAFACTUALES: medio=BP=0,50")
    perfiles = (
        ("equilibrado", [0.5, 0.5, 0.5]),
        ("centro débil", [0.8, 0.2, 0.8]),
        ("izquierda débil", [0.2, 0.8, 0.8]),
        ("centro fuerte", [0.2, 0.8, 0.2]),
    )
    for etiqueta, carriles in perfiles:
        vector = np.asarray(
            [[np.log(0.5), *np.log(carriles), np.log(0.5)]],
            dtype=float,
        )
        valores = [
            float(lambdas(completos[nombre], vector, nombre)[0])
            for nombre in MODELOS
        ]
        print(f"  {etiqueta:17} p={carriles}")
        for nombre, valor in zip(MODELOS, valores, strict=True):
            print(f"    {nombre:23} lambda={valor:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
