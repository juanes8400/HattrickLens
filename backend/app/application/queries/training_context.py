"""TrainingContextService — contextualiza el perfil de entrenamiento.

Antes, el `TrainingSetup` se construía con tres valores puestos a mano: la suma
de niveles de ayudantes (10), el nivel del entrenador (excelente) y el
%condición (12,5%). Los tres eran supuestos que ajustaban los datos pero que
elegí yo, no lecturas del juego.

Este servicio construye el mismo `TrainingSetup` **leyendo cada valor del
CHPP**:

- ayudantes  ← suma de `stafflist.StaffLevel` de los asistentes de entrenador
  (StaffType=1) — `club.AssistantTrainerLevels` dejó de existir (verificado
  en vivo 2026-08-12, ver `parse_club`)
- intensidad ← `training.TrainingLevel`
- %condición ← `training.StaminaTrainingPart`
- entrenador ← `stafflist.TrainerSkillLevel`

Y adjunta la **procedencia** de cada uno, para que la pantalla del Motor pueda
decir, campo por campo, si viene leído o sigue siendo un supuesto.

Los valores del club se separan de los coeficientes de la fórmula comunitaria
HT-Tools. La API entrega el nivel de entrenador en escala 1–5 y la fórmula
trabaja en escala 4–8; la correspondencia directa vive en `training.yaml`.

El contraste no se inventa: `trainingevents` entrega subidas de habilidad
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
    #: Cómo se le NOMBRA al usuario el origen del valor: la pantalla de
    #: Hattrick de la que sale, o «supuesto». Nunca un fichero de la API:
    #: esto se pinta tal cual en Transparencia (2026-08-31, orden del
    #: usuario: ninguna referencia a la API puede llegar a la pantalla).
    source: str  # "Club", "Entrenamiento", "Cuerpo técnico", "supuesto"
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
        return cast(
            m.StaffSnapshot | None,
            await self._s.scalar(
                select(m.StaffSnapshot)
                .where(m.StaffSnapshot.team_id == team_id)
                .order_by(m.StaffSnapshot.captured_at.desc())
                .limit(1)
            ),
        )

    async def _latest_training(self, team_id: int) -> m.TrainingSnapshot | None:
        return cast(
            m.TrainingSnapshot | None,
            await self._s.scalar(
                select(m.TrainingSnapshot)
                .where(m.TrainingSnapshot.team_id == team_id)
                # Dos lecturas pueden compartir el mismo instante al importar
                # o restaurar datos. En ese caso la fila de id mayor es la que
                # se escribió después y, por tanto, la configuración vigente.
                .order_by(
                    m.TrainingSnapshot.captured_at.desc(),
                    m.TrainingSnapshot.id.desc(),
                )
                .limit(1)
            ),
        )

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
                assistants,
                "Cuerpo técnico",
                True,
                # HL-2xx, 2026-08-12: club.xml dejó de traer el agregado
                # (verificado en vivo) — ahora es la suma real de los
                # asistentes de entrenador (StaffType=1) de stafflist.xml.
                "Suma de los niveles de tus asistentes de entrenador",
            )
        else:
            assistants = int(cfg.get("default_assistant_level_sum", 10))
            prov["assistant_level_sum"] = Provenance(
                assistants,
                "supuesto",
                False,
                "sin datos del club todavía: se usa el valor por defecto",
            )

        # ── Intensidad y condición ─────────────────────────────────────────
        if training is not None:
            intensity = training.training_level
            stamina = training.stamina_part
            training_type = training.training_type
            prov["intensity"] = Provenance(intensity, "Entrenamiento", True, "Intensidad declarada")
            prov["stamina_share"] = Provenance(
                stamina, "Entrenamiento", True, "Parte dedicada a resistencia"
            )
            prov["training_type"] = Provenance(
                training_type, "Entrenamiento", True, "Entrenamiento elegido"
            )
        else:
            intensity = 100
            stamina = cfg.get("default_stamina_share", 0)
            training_type = 10
            prov["intensity"] = Provenance(100, "supuesto", False, "sin datos de entrenamiento")
            prov["stamina_share"] = Provenance(
                stamina,
                "supuesto",
                False,
                # HL-2xx, 2026-08-14: antes caía en 0 en vez del default_stamina_share
                # del yaml (12.5) — contradecía el propio default documentado y
                # asumía "0% a resistencia" en vez de un reparto típico.
                "sin datos de entrenamiento: se usa el reparto típico del perfil",
            )
            prov["training_type"] = Provenance(
                training_type,
                "supuesto",
                False,
                "sin datos de entrenamiento: se asume Pases largos",
            )

        # ── Entrenador ─────────────────────────────────────────────────────
        skill_map = cfg["trainer_skill_to_formula_level"]
        if staff is not None and staff.trainer_skill_level:
            raw = staff.trainer_skill_level
            coach_level = int(skill_map.get(raw, skill_map.get(str(raw), 7)))
            is_excellent = raw >= cfg["excellent_trainer_skill_level"]
            prov["coach_level"] = Provenance(
                coach_level,
                "Cuerpo técnico",
                True,
                f"Entrenador {raw}/5 → nivel {coach_level} (correspondencia 1–5 → 4–8 de HT-Tools)",
            )
        else:
            coach_level, is_excellent = 8, True
            prov["coach_level"] = Provenance(8, "supuesto", False, "sin datos del cuerpo técnico")

        setup = te.TrainingSetup(
            skill=cfg["training_type_to_skill"].get(training_type, "passing"),
            training_type=int(training_type),
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
                "Todos los valores del club se leen de Hattrick. Los coeficientes "
                "son la estimación comunitaria pública de HT-Tools; no son "
                "constantes oficiales de Hattrick ni se ajustan con tus datos.",
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
        target_id = next((int(k) for k, v in skill_map.items() if v == setup.skill), None)
        ups = list(
            (
                await self._s.execute(
                    select(m.SkillUp)
                    .where(m.SkillUp.team_id == team_id)
                    .order_by(m.SkillUp.ht_player_id, m.SkillUp.season, m.SkillUp.match_round)
                )
            ).scalars()
        )

        # Necesitamos la edad del jugador en la fecha del pop. Por ahora usamos
        # la más reciente conocida y declaramos esa limitación.
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
                samples.append(
                    {
                        "player_id": pid,
                        "from_level": a.new_level,
                        "to_level": b.new_level,
                        "observed_weeks": observed_weeks,
                        "predicted_weeks": round(predicted, 1),
                        "error_weeks": round(err, 1),
                    }
                )

        caveats: list[str] = []
        if samples:
            caveats.append(
                "Las semanas observadas salen de la distancia entre subidas "
                "confirmadas (trainingevents). La edad usada es la más reciente "
                "conocida, no la del momento exacto de cada subida. Los pops "
                "solo contrastan la fórmula pública: no reajustan coeficientes."
            )
        else:
            caveats.append(
                "Todavía no hay dos subidas consecutivas en la habilidad "
                "entrenada, así que no se puede contrastar la fórmula con pops "
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
            ages.setdefault(pid, (yrs, days))  # el primero es el más reciente
        return ages
