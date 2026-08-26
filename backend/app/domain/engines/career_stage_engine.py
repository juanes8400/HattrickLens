"""Preclasificación de jugadores — HL-15x #87: "en qué momento de su vida
está" un jugador, a partir de señales reales (edad, tendencia de habilidades
entre el snapshot más antiguo y el más reciente, percentil dentro de la
plantilla, liderazgo, fidelidad).

⚠️ Las categorías y umbrales son un juicio de producto, no una fórmula
verificada contra datos externos (a diferencia de `pricing_engine.SALARY_*`,
que sí lo es) — se declara así en `confidence`. Siempre se devuelven las
señales crudas (`signals`) para que la UI pueda mostrar el porqué, no solo
la etiqueta.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.engines.pricing_engine import age_factor

# Bandas de edad alineadas con AGE_FACTOR de pricing_engine (pico real de
# valor ~22-27 años, cae fuerte desde los 28).
YOUNG_MAX_AGE = 21
PEAK_MAX_AGE = 27


@dataclass
class CareerStage:
    stage: str
    label: str
    rationale: str
    confidence: str
    signals: dict[str, Any]


def classify_career_stage(
    age_years: int,
    age_days: int,
    skills_rising: int,
    skills_falling: int,
    skills_stable: int,
    has_sufficient_history: bool,
    squad_percentile: float | None,
    leadership: int,
    loyalty: int,
) -> CareerStage:
    """Clasifica en una de 6 etapas. `skills_rising/falling/stable` cuentan
    las 7 habilidades principales comparando el snapshot más antiguo real
    contra el más reciente — no una proyección, un hecho ya observado.
    `squad_percentile` es el percentil real en la habilidad dominante dentro
    de la plantilla activa (puede ser `None` si el jugador ya no está en
    ella). `has_sufficient_history` exige al menos 2 snapshots reales en
    fechas distintas: con solo 1, no hay tendencia que describir y fingir
    una sería inventar un dato."""
    af = round(age_factor(age_years, age_days), 3)
    signals: dict[str, Any] = {
        "ageYears": age_years,
        "ageDays": age_days,
        "ageFactor": af,
        "skillsRising": skills_rising,
        "skillsFalling": skills_falling,
        "skillsStable": skills_stable,
        "hasSufficientHistory": has_sufficient_history,
        "squadPercentile": squad_percentile,
        "leadership": leadership,
        "loyalty": loyalty,
    }

    if not has_sufficient_history:
        return CareerStage(
            stage="sin_historial",
            label="Sin historial suficiente",
            rationale=(
                "Todavía no hay dos snapshots reales en fechas distintas para comparar "
                "tendencia de habilidades, se necesita al menos una sincronización más, "
                "en otra semana, para clasificar con algo de base."
            ),
            confidence="sin evaluar, falta historial real",
            signals=signals,
        )

    if age_years <= YOUNG_MAX_AGE:
        rationale = (
            f"{age_years} años, edad de formación (factor de edad {af:.2f}, subiendo). "
            f"{skills_rising} de 7 habilidades principales han subido desde el snapshot "
            "más antiguo disponible."
            if skills_rising > 0
            else f"{age_years} años, edad de formación, aunque el historial real todavía "
            "no muestra subidas de habilidad."
        )
        return CareerStage(
            stage="promesa",
            label="Promesa en desarrollo",
            rationale=rationale,
            confidence="moderada, la edad es la señal principal; el historial de "
            "subidas todavía es corto",
            signals=signals,
        )

    if age_years <= PEAK_MAX_AGE:
        if squad_percentile is not None and squad_percentile >= 60:
            return CareerStage(
                stage="pico",
                label="En su pico",
                rationale=(
                    f"{age_years} años (factor de edad {af:.2f}, cerca del máximo real) y "
                    f"percentil {squad_percentile:.0f} en su habilidad dominante dentro de "
                    "la plantilla activa."
                ),
                confidence="alta",
                signals=signals,
            )
        if squad_percentile is not None and squad_percentile < 40:
            return CareerStage(
                stage="rotacion",
                label="Pieza de rotación",
                rationale=(
                    f"Edad óptima ({age_years} años) pero percentil {squad_percentile:.0f} "
                    "en su habilidad dominante, por debajo de la mayoría de la plantilla "
                    "activa."
                ),
                confidence="moderada",
                signals=signals,
            )
        return CareerStage(
            stage="pico",
            label="En su pico",
            rationale=f"{age_years} años, en el tramo de mayor factor de edad (~{af:.2f}).",
            confidence="moderada, sin percentil de plantilla disponible para afinar más",
            signals=signals,
        )

    # Veterano (>= PEAK_MAX_AGE + 1)
    if skills_falling > skills_rising and af < 0.85:
        return CareerStage(
            stage="declive",
            label="En declive",
            rationale=(
                f"{age_years} años, factor de edad {af:.2f} en caída y {skills_falling} de 7 "
                "habilidades principales bajando desde el snapshot más antiguo disponible."
            ),
            confidence="alta",
            signals=signals,
        )
    return CareerStage(
        stage="veterano",
        label="Veterano estable",
        rationale=(
            f"{age_years} años sin señales claras de caída en habilidades reales "
            f"(liderazgo {leadership}, fidelidad {loyalty})."
        ),
        confidence="moderada",
        signals=signals,
    )
