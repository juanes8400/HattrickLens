"""Aporte real de cada categoría de empleado — HL-2xx, 2026-08-12.

Tablas oficiales de Hattrick (página "Empleados"), pasadas explícitamente
por el usuario. Las bonificaciones de Asistente de entrenador, Doctor y
Preparador físico son LINEALES por nivel: "cada nivel de habilidad
adicional siempre contribuye lo mismo que el nivel de habilidad anterior" —
un asistente de entrenador nivel 4 aporta exactamente lo mismo que dos de
nivel 2 (niveles combinados, ver STAFF_TYPE_TO_FIELD en sync_team.py), así
que su fórmula se extrapola sin problema más allá de nivel 5 individual
(hasta 10, con dos empleados de nivel 5 cada uno).

Psicólogo deportivo (confianza), Director financiero y Asistente táctico
son tablas de valores por nivel — el propio texto de Hattrick dice que la
confianza "no es lineal", así que esa columna se toma de la tabla, no de
una fórmula. Director financiero y Asistente táctico solo permiten un
empleado (el táctico, dos) hasta nivel 5, así que no hace falta
extrapolar más allá.

La velocidad de entrenamiento del asistente de entrenador NO se duplica
aquí: reutiliza `training_engine._config()["assistant_bonus_per_level"]`,
la MISMA constante comunitaria (3,2 puntos de coeficiente por nivel) que
alimenta la fórmula de semanas-hasta-el-siguiente-nivel.
"""
from __future__ import annotations

from typing import Any

from app.domain.engines import training_engine as te

# ── Asistente de entrenador ────────────────────────────────────────────────
ASSISTANT_INJURY_RISK_PP_PER_LEVEL = 2.5   # puntos porcentuales por nivel combinado
ASSISTANT_BACKGROUND_FORM_PER_LEVEL = 0.05  # niveles de forma de fondo por nivel combinado

BASE_INJURY_RISK_PCT = 40.0  # % lesiones/partido sin asistentes ni doctor

# ── Doctor ──────────────────────────────────────────────────────────────────
DOCTOR_RECOVERY_SPEED_PCT_PER_LEVEL = 20.0
DOCTOR_INJURY_RISK_REDUCTION_PP_PER_LEVEL = 7.5

# ── Psicólogo deportivo (tabla — la confianza no es lineal, ver docstring) ──
SPORT_PSYCHOLOGIST_SPIRIT: dict[int, float] = {0: 0.0, 1: 0.1, 2: 0.2, 3: 0.3, 4: 0.4, 5: 0.5}
SPORT_PSYCHOLOGIST_CONFIDENCE: dict[int, float] = {
    0: 0.0, 1: 0.24, 2: 0.48, 3: 0.70, 4: 0.92, 5: 1.12,
}

# ── Preparador físico ─────────────────────────────────────────────────────
FORM_COACH_BACKGROUND_FORM_PER_LEVEL = 0.2

# ── Director financiero (tabla absoluta, US$) ───────────────────────────────
FINANCIAL_DIRECTOR: dict[int, tuple[int, int]] = {
    0: (15_000_000, 100_000),
    1: (17_000_000, 200_000),
    2: (19_000_000, 400_000),
    3: (21_000_000, 600_000),
    4: (23_000_000, 800_000),
    5: (25_000_000, 1_000_000),
}

# ── Asistente táctico (tabla absoluta) ──────────────────────────────────────
TACTICAL_ASSISTANT: dict[int, tuple[int, int]] = {
    0: (0, 0), 1: (1, 20), 2: (2, 40), 3: (3, 60), 4: (4, 80), 5: (5, 100),
}


def _clamp5(level: int) -> int:
    return max(0, min(int(level), 5))


def assistant_trainer_effect(combined_level: int) -> dict[str, Any]:
    """`combined_level`: suma de niveles de hasta 2 asistentes de
    entrenador (0–10, ver STAFF_TYPE_TO_FIELD)."""
    cfg = te._config()
    per_level = cfg["assistant_bonus_per_level"]
    cap = cfg["assistant_level_sum_cap"]
    capped = max(0, min(int(combined_level), int(cap)))
    return {
        "trainingSpeedPct": round(capped * per_level * 100, 2),
        "injuryRiskPp": round(combined_level * ASSISTANT_INJURY_RISK_PP_PER_LEVEL, 2),
        "backgroundForm": round(combined_level * ASSISTANT_BACKGROUND_FORM_PER_LEVEL, 3),
    }


def doctor_effect(level: int) -> dict[str, Any]:
    capped = _clamp5(level)
    return {
        "recoverySpeedPct": round(capped * DOCTOR_RECOVERY_SPEED_PCT_PER_LEVEL, 2),
        "injuryRiskReductionPp": round(capped * DOCTOR_INJURY_RISK_REDUCTION_PP_PER_LEVEL, 2),
    }


def sport_psychologist_effect(level: int) -> dict[str, Any]:
    capped = _clamp5(level)
    return {
        "teamSpirit": SPORT_PSYCHOLOGIST_SPIRIT[capped],
        "confidence": SPORT_PSYCHOLOGIST_CONFIDENCE[capped],
    }


def form_coach_effect(level: int) -> dict[str, Any]:
    capped = _clamp5(level)
    return {"backgroundForm": round(capped * FORM_COACH_BACKGROUND_FORM_PER_LEVEL, 2)}


def financial_director_effect(level: int) -> dict[str, Any]:
    max_funds, weekly_return = FINANCIAL_DIRECTOR[_clamp5(level)]
    return {"maxFunds": max_funds, "weeklyReturn": weekly_return}


def tactical_assistant_effect(level: int) -> dict[str, Any]:
    extra_orders, flex_pp = TACTICAL_ASSISTANT[_clamp5(level)]
    return {"extraOrders": extra_orders, "styleFlexibilityPp": flex_pp}


def current_injury_risk_pct(assistant_combined_level: int, doctor_level: int) -> float:
    """Riesgo de lesión real del equipo, combinando ambos efectos —
    verificado contra el ejemplo oficial: 2 asistentes nivel 5 (10
    combinado) + doctor nivel 5 = 0.275 lesiones/partido (27.5%)."""
    assistant = assistant_trainer_effect(assistant_combined_level)["injuryRiskPp"]
    doctor = doctor_effect(doctor_level)["injuryRiskReductionPp"]
    return round(BASE_INJURY_RISK_PCT + assistant - doctor, 2)


# HL-2xx: qué función de efecto corresponde a cada columna de StaffSnapshot
# (mismas claves que STAFF_FIELDS en club.py). "spokesperson_levels"
# (Portavoz) no aparece en las categorías vigentes que pasó el usuario — sin
# tabla oficial, no se inventa una.
STAFF_FIELD_TO_EFFECT_FN: dict[str, Any] = {
    "assistant_trainer_levels": assistant_trainer_effect,
    "medic_levels": doctor_effect,
    "sport_psychologist_levels": sport_psychologist_effect,
    "form_coach_levels": form_coach_effect,
    "financial_director_levels": financial_director_effect,
    "tactical_assistant_levels": tactical_assistant_effect,
}
