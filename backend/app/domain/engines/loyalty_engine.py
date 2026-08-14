"""Loyalty Engine — Fidelidad, sin fórmula publicada por Hattrick.

A diferencia de Experiencia (que sí tiene un umbral de puntos declarado en
la especificación de Hattrick Control, solo pendiente de validar con datos
reales), Fidelidad no tiene ninguna fórmula publicada: ni Hattrick ni
Hattrick Control documentan cuántos días toma subir de un nivel a otro.

2026-08-10, pedido explícito del usuario: el intervalo real SÍ es
constante entre jugadores para una misma transición de nivel (todos tardan
lo mismo en pasar de 5 a 6), pero NO es constante entre niveles distintos
— subir de 1 a 2 es rápido, de 19 a 20 puede tardar ~3 temporadas
(ejemplos del usuario). Así que en vez de una única constante como en
Experiencia, aquí se calibra una TABLA de hasta 20 intervalos (uno por
cada transición N→N+1), cada uno descubierto por separado observando
jugadores reales que suben de nivel.

Sin ningún valor configurado de partida: mientras una transición no tenga
observaciones, no se puede calcular progreso decimal para ella — la ficha
del jugador cae de vuelta al nivel entero en ese caso, nunca inventa un
número.
"""
from dataclasses import dataclass, field
from statistics import mean, stdev
from typing import Any


@dataclass(frozen=True)
class LoyaltyLevelUp:
    """Una subida de fidelidad realmente observada: días reales
    transcurridos entre el snapshot que empezó el nivel anterior y el que
    confirmó el nuevo — ver `player_history.loyalty_level_up_observations`
    para el criterio de "salto limpio" que produce estas observaciones."""

    player: str
    from_level: int
    to_level: int
    days_elapsed: int


@dataclass
class LoyaltyTransition:
    """Lo que dicen las observaciones reales sobre UNA transición N→N+1."""

    from_level: int
    to_level: int
    avg_days: float
    observations: int
    std_dev: float | None = None


@dataclass
class LoyaltyCalibration:
    """Tabla completa de transiciones calibradas — una entrada por cada
    transición de nivel que ya tiene al menos una observación limpia."""

    transitions: dict[int, LoyaltyTransition] = field(default_factory=dict)
    total_observations: int = 0

    def for_level(self, level: int) -> LoyaltyTransition | None:
        """Calibración de la transición `level` → `level + 1`, si existe."""
        return self.transitions.get(level)


def calibrate(observations: list[LoyaltyLevelUp]) -> LoyaltyCalibration:
    """Agrupa las observaciones por transición y promedia los días reales
    de cada una — sin mínimo de observaciones: incluso una sola
    observación es mejor que ninguna para esa transición específica (a
    diferencia de Experiencia, aquí no hay un valor configurado que sirva
    de respaldo mientras se junta evidencia). La confianza de cada
    transición queda expuesta en `observations`/`std_dev`, no oculta."""
    by_level: dict[int, list[LoyaltyLevelUp]] = {}
    for obs in observations:
        by_level.setdefault(obs.from_level, []).append(obs)

    transitions: dict[int, LoyaltyTransition] = {}
    for level, obs_list in by_level.items():
        days = [o.days_elapsed for o in obs_list]
        transitions[level] = LoyaltyTransition(
            from_level=level,
            to_level=level + 1,
            avg_days=round(mean(days), 1),
            observations=len(obs_list),
            std_dev=round(stdev(days), 1) if len(days) > 1 else None,
        )
    return LoyaltyCalibration(transitions=transitions, total_observations=len(observations))


def progress_within_level(
    current_level: int,
    days_at_level: float | None,
    calibration: LoyaltyCalibration,
) -> float | None:
    """Posición decimal dentro del nivel actual (p.ej. 5.62), o `None` si
    no hay forma honesta de calcularla: falta la fecha real en que empezó
    este nivel, o esa transición todavía no tiene ninguna observación.

    Se recorta a 0.98 como máximo dentro del nivel — un jugador puede
    llevar más días de los que promedia la transición (todavía no subió
    pese a "tocarle"), pero mostrarlo como si ya estuviera en el nivel
    siguiente sería inventar la subida antes de que Hattrick la confirme.
    """
    if days_at_level is None:
        return None
    transition = calibration.for_level(current_level)
    if transition is None or transition.avg_days <= 0:
        return None
    fraction = min(days_at_level / transition.avg_days, 0.98)
    return round(current_level + max(fraction, 0.0), 2)


def model_info(calibration: LoyaltyCalibration) -> dict[str, Any]:
    return {
        "transitions": [
            {
                "fromLevel": t.from_level,
                "toLevel": t.to_level,
                "avgDays": t.avg_days,
                "observations": t.observations,
                "stdDev": t.std_dev,
            }
            for t in sorted(calibration.transitions.values(), key=lambda t: t.from_level)
        ],
        "totalObservations": calibration.total_observations,
        "reference": {
            "implementation": "Descubierto por observación propia — sin fórmula publicada",
            "status": "pending",
            "source_files": [],
            "recovered": (
                "Hattrick y Hattrick Control no publican el intervalo real de "
                "fidelidad. Se calibra transición por transición (N→N+1) "
                "observando jugadores reales que suben de nivel en esta cuenta."
            ),
            "pending": (
                "Las hasta 20 transiciones posibles (0→1 ... 19→20): cada una "
                "necesita su propia evidencia, no se puede extrapolar de una "
                "transición a otra."
            ),
        },
    }
