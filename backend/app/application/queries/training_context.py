"""TrainingContextService — contextualiza el perfil de entrenamiento.

Antes, el `TrainingSetup` se construía con tres valores puestos a mano: la suma
de niveles de ayudantes (10), el nivel del entrenador (excelente) y el
%condición (12,5%). Los tres eran supuestos que ajustaban los datos pero que
elegí yo, no lecturas del juego.

Este servicio construye el mismo `TrainingSetup` **leyendo cada valor del
CHPP**:

- ayudantes  ← `club.AssistantTrainerLevels`
- intensidad ← `training.TrainingLevel`
- %condición ← `training.StaminaTrainingPart`
- entrenador ← `stafflist.TrainerSkillLevel`

Y adjunta la **procedencia** de cada uno, para que la pantalla del Motor pueda
decir, campo por campo, si viene leído o sigue siendo un supuesto.

Los valores del club se separan de los coeficientes del perfil: la extracción
de Hattrick Control confirma las entradas y controles por tipo, pero no trae
el Defaults.dat ni la rutina auxiliar que fija sus valores numéricos. La API
entrega además el nivel de entrenador en escala 1–5, mientras que el perfil
usa una escala nominal 7/8; esa correspondencia vive en `training.yaml`,
marcada provisional.

La validación no se inventa: `trainingevents` entrega subidas de habilidad
confirmadas por Hattrick, con temporada y jornada. Para un jugador con dos
subidas consecutivas en la habilidad entrenada, la distancia entre ellas es el
número real de semanas que costó subir un nivel, y se compara con lo que
predice la fórmula alimentada con el contexto real.
"""
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines import training_engine as te
from app.infrastructure.db import models as m

ROUNDS_PER_SEASON = 16


@dataclass
class Provenance:
    """De dónde sale un valor: un fichero CHPP, o un supuesto declarado."""

    value: object
    source: str          # "club.xml", "training.xml", "stafflist.xml", "supuesto"
    is_read: bool
    note: str = ""


@dataclass
class FormulaValidation:
    observations: int
    mean_error_weeks: float | None
    max_error_weeks: float | None
    samples: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


@dataclass
class TrainingContext:
    setup: te.TrainingSetup
    trained_skill: str
    provenance: dict[str, Provenance]
    validation: FormulaValidation
    all_read: bool
    notes: list[str] = field(default_factory=list)


class TrainingContextService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _latest_staff(self, team_id: int) -> m.StaffSnapshot | None:
        return cast(m.StaffSnapshot | None, await self._s.scalar(
            select(m.StaffSnapshot)
            .where(m.StaffSnapshot.team_id == team_id)
            .order_by(m.StaffSnapshot.captured_at.desc())
            .limit(1)
        ))

    async def _latest_training(self, team_id: int) -> m.TrainingSnapshot | None:
        return cast(m.TrainingSnapshot | None, await self._s.scalar(
            select(m.TrainingSnapshot)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        ))

    async def get(self, team_id: int) -> TrainingContext | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        cfg = te._config()
        staff = await self._latest_staff(team_id)
        training = await self._latest_training(team_id)

        prov: dict[str, Provenance] = {}
        notes: list[str] = []

        # ── Ayudantes ──────────────────────────────────────────────────────
        if staff is not None:
            assistants = min(staff.assistant_trainer_levels, cfg["assistant_level_sum_cap"])
            prov["assistant_level_sum"] = Provenance(
                assistants, "club.xml", True,
                "AssistantTrainerLevels: nivel agregado 0–10 leído de la API",
            )
        else:
            assistants = int(cfg.get("default_assistant_level_sum", 10))
            prov["assistant_level_sum"] = Provenance(
                assistants, "supuesto", False,
                "sin sincronizar club.xml: se usa el valor por defecto",
            )

        # ── Intensidad y condición ─────────────────────────────────────────
        if training is not None:
            intensity = training.training_level
            stamina = training.stamina_part
            training_type = training.training_type
            prov["intensity"] = Provenance(intensity, "training.xml", True, "TrainingLevel")
            prov["stamina_share"] = Provenance(stamina, "training.xml", True, "StaminaTrainingPart")
        else:
            intensity, stamina, training_type = 100, 0, 10
            prov["intensity"] = Provenance(100, "supuesto", False, "sin training.xml")
            prov["stamina_share"] = Provenance(0, "supuesto", False, "sin training.xml")

        # ── Entrenador ─────────────────────────────────────────────────────
        skill_map = cfg["trainer_skill_to_formula_level"]
        if staff is not None and staff.trainer_skill_level:
            raw = staff.trainer_skill_level
            coach_level = int(skill_map.get(raw, skill_map.get(str(raw), 7)))
            is_excellent = raw >= cfg["excellent_trainer_skill_level"]
            prov["coach_level"] = Provenance(
                coach_level, "stafflist.xml", True,
                f"TrainerSkillLevel {raw}/5 → nivel {coach_level} "
                "(correspondencia 1–5 ↔ 7/8 PROVISIONAL)",
            )
            notes.append(
                "El nivel del entrenador se lee de stafflist (escala 1–5) y se "
                "traduce a la escala 7/8 de la fórmula con una tabla marcada "
                "provisional: es lo único que queda por reconciliar."
            )
        else:
            coach_level, is_excellent = 8, True
            prov["coach_level"] = Provenance(8, "supuesto", False, "sin stafflist.xml")

        setup = te.TrainingSetup(
            skill=cfg["training_type_to_skill"].get(training_type, "passing"),
            intensity=intensity,
            stamina_share=stamina,
            coach_level=coach_level,
            coach_is_excellent=is_excellent,
            assistant_level_sum=int(assistants),
        )
        trained_skill = setup.skill
        validation = await self._validate(team_id, setup, cfg, notes)

        all_read = all(p.is_read for p in prov.values())
        if all_read:
            notes.insert(
                0,
                "Todos los valores del club se leen del CHPP. Los coeficientes "
                "del perfil HTC compatible siguen visibles y pendientes de "
                "reconstrucción/calibración; no se presentan como constantes "
                "oficiales.",
            )
        else:
            missing = [k for k, p in prov.items() if not p.is_read]
            notes.insert(
                0,
                "Aún hay valores por defecto porque faltan ficheros por "
                f"sincronizar: {', '.join(missing)}.",
            )

        return TrainingContext(
            setup=setup,
            trained_skill=trained_skill,
            provenance=prov,
            validation=validation,
            all_read=all_read,
            notes=notes,
        )

    async def _validate(
        self, team_id: int, setup: te.TrainingSetup, cfg: dict[str, Any], notes: list[str]
    ) -> FormulaValidation:
        """Compara la fórmula (con el contexto real) contra las subidas
        confirmadas por Hattrick."""
        skill_map = cfg["skill_id_map"]
        target_id = next(
            (int(k) for k, v in skill_map.items() if v == setup.skill), None
        )
        ups = list(
            (
                await self._s.execute(
                    select(m.SkillUp)
                    .where(m.SkillUp.team_id == team_id)
                    .order_by(
                        m.SkillUp.ht_player_id, m.SkillUp.season, m.SkillUp.match_round
                    )
                )
            ).scalars()
        )

        # Necesitamos la edad del jugador para la fórmula. La aproximamos con la
        # más reciente conocida; el efecto de unos meses de edad es pequeño
        # frente a un nivel, pero se declara como aproximación.
        ages = await self._player_ages(team_id)

        by_player: dict[int, list[m.SkillUp]] = {}
        for u in ups:
            if target_id is not None and u.skill_id != target_id:
                continue
            by_player.setdefault(u.ht_player_id, []).append(u)

        samples: list[dict[str, Any]] = []
        errors: list[float] = []
        for pid, seq in by_player.items():
            seq.sort(key=lambda u: (u.season, u.match_round))
            for a, b in zip(seq, seq[1:], strict=False):
                observed_weeks = (b.season - a.season) * ROUNDS_PER_SEASON + (
                    b.match_round - a.match_round
                )
                if observed_weeks <= 0:
                    continue
                age = ages.get(pid, (24, 0))
                predicted = te.weeks_to_next_level(
                    setup.skill, a.new_level, age[0], age[1], setup=setup
                ).weeks_to_next_level
                err = abs(predicted - observed_weeks)
                errors.append(err)
                samples.append({
                    "player_id": pid,
                    "from_level": a.new_level,
                    "to_level": b.new_level,
                    "observed_weeks": observed_weeks,
                    "predicted_weeks": round(predicted, 1),
                    "error_weeks": round(err, 1),
                })

        caveats: list[str] = []
        if samples:
            caveats.append(
                "Las semanas observadas salen de la distancia entre subidas "
                "confirmadas (trainingevents). La edad usada es la más reciente "
                "conocida, no la del momento exacto de cada subida: una "
                "aproximación pequeña frente al efecto de un nivel."
            )
        else:
            caveats.append(
                "Todavía no hay dos subidas consecutivas en la habilidad "
                "entrenada, así que no se puede validar la fórmula contra pops "
                "confirmados. Cada sincronización con nuevas subidas la habilita."
            )

        return FormulaValidation(
            observations=len(samples),
            mean_error_weeks=round(sum(errors) / len(errors), 2) if errors else None,
            max_error_weeks=round(max(errors), 2) if errors else None,
            samples=samples,
            caveats=caveats,
        )

    async def _player_ages(self, team_id: int) -> dict[int, tuple[int, int]]:
        rows = await self._s.execute(
            select(
                m.Player.ht_player_id,
                m.PlayerSnapshot.age_years,
                m.PlayerSnapshot.age_days,
                m.PlayerSnapshot.captured_at,
            )
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
        )
        ages: dict[int, tuple[int, int]] = {}
        for pid, yrs, days, _ in rows.all():
            ages.setdefault(pid, (yrs, days))    # el primero es el más reciente
        return ages
