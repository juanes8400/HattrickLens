import i18n from "../i18n";
import { money } from "../hooks/useFormat";
import type { ClubStaffRoleEffect } from "../services/api";

const TRAINER_TRAINING_SPEED_PCT: Record<number, number> = {
  1: 65,
  2: 76,
  3: 84,
  4: 92,
  5: 100,
};

/** Tabla paramétrica del nivel oficial 1–5 del entrenador. */
export function trainerTrainingSpeedPct(level: number): number | null {
  return TRAINER_TRAINING_SPEED_PCT[level] ?? null;
}

/** Semáforo pedido para entrenador y asistentes: 5 óptimo, 3–4 atención,
 * 0–2 crítico. `null` también es crítico porque significa que no hay dato. */
export function trainingStaffLevelColor(
  level: number | null | undefined,
): string {
  if (level == null || level <= 2) return "text-[var(--danger)]";
  if (level <= 4) return "text-[var(--warning)]";
  return "text-[var(--positive)]";
}

/** Texto compartido por Club y Entrenamiento para que el aporte del staff
 * se explique siempre con las mismas unidades y las mismas etiquetas. */
export function staffEffectLines(effect: ClubStaffRoleEffect): string[] {
  const t = i18n.t.bind(i18n);
  const lines: string[] = [];
  if (effect.trainingSpeedPct != null)
    lines.push(
      t("staff.velocidadEntrenamiento", "Velocidad de entrenamiento +{{v}}%", {
        v: effect.trainingSpeedPct,
      }),
    );
  if (effect.recoverySpeedPct != null)
    lines.push(
      t("staff.velocidadRecuperacion", "Velocidad de recuperación +{{v}}%", {
        v: effect.recoverySpeedPct,
      }),
    );
  if (effect.backgroundForm != null && effect.backgroundForm !== 0)
    lines.push(
      t("staff.formaDeFondo", "Forma de fondo +{{v}}", {
        v: effect.backgroundForm,
      }),
    );
  if (effect.injuryRiskPp != null && effect.injuryRiskPp !== 0)
    lines.push(
      t("staff.riesgoLesionMas", "Riesgo de lesión +{{v}} pp", {
        v: effect.injuryRiskPp,
      }),
    );
  if (
    effect.injuryRiskReductionPp != null &&
    effect.injuryRiskReductionPp !== 0
  )
    lines.push(
      t("staff.riesgoLesionMenos", "Riesgo de lesión −{{v}} pp", {
        v: effect.injuryRiskReductionPp,
      }),
    );
  if (effect.teamSpirit != null && effect.teamSpirit !== 0)
    lines.push(
      t("staff.espiritu", "Espíritu del equipo +{{v}}", {
        v: effect.teamSpirit,
      }),
    );
  if (effect.confidence != null && effect.confidence !== 0)
    lines.push(
      t("staff.confianza", "Confianza +{{v}}", { v: effect.confidence }),
    );
  if (effect.maxFunds != null)
    lines.push(
      t("staff.fondosMaximos", "Fondos máximos {{v}}", {
        v: money(effect.maxFunds, "US$"),
      }),
    );
  if (effect.weeklyReturn != null)
    lines.push(
      t("staff.retornoSemanal", "Retorno semanal {{v}}", {
        v: money(effect.weeklyReturn, "US$"),
      }),
    );
  if (effect.extraOrders != null && effect.extraOrders !== 0)
    lines.push(
      t("staff.ordenesExtra", "+{{v}} órdenes extra", {
        v: effect.extraOrders,
      }),
    );
  if (effect.styleFlexibilityPp != null && effect.styleFlexibilityPp !== 0)
    lines.push(
      t("staff.flexibilidad", "Flexibilidad de estilo +{{v}} pp", {
        v: effect.styleFlexibilityPp,
      }),
    );
  return lines;
}
