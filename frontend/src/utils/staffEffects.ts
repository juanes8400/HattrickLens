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
export function trainingStaffLevelColor(level: number | null | undefined): string {
  if (level == null || level <= 2) return "text-[var(--danger)]";
  if (level <= 4) return "text-[var(--warning)]";
  return "text-[var(--positive)]";
}

/** Texto compartido por Club y Entrenamiento para que el aporte del staff
 * se explique siempre con las mismas unidades y las mismas etiquetas. */
export function staffEffectLines(effect: ClubStaffRoleEffect): string[] {
  const lines: string[] = [];
  if (effect.trainingSpeedPct != null) lines.push(`Velocidad de entrenamiento +${effect.trainingSpeedPct}%`);
  if (effect.recoverySpeedPct != null) lines.push(`Velocidad de recuperación +${effect.recoverySpeedPct}%`);
  if (effect.backgroundForm != null && effect.backgroundForm !== 0) lines.push(`Forma de fondo +${effect.backgroundForm}`);
  if (effect.injuryRiskPp != null && effect.injuryRiskPp !== 0) lines.push(`Riesgo de lesión +${effect.injuryRiskPp} pp`);
  if (effect.injuryRiskReductionPp != null && effect.injuryRiskReductionPp !== 0) lines.push(`Riesgo de lesión −${effect.injuryRiskReductionPp} pp`);
  if (effect.teamSpirit != null && effect.teamSpirit !== 0) lines.push(`Espíritu del equipo +${effect.teamSpirit}`);
  if (effect.confidence != null && effect.confidence !== 0) lines.push(`Confianza +${effect.confidence}`);
  if (effect.maxFunds != null) lines.push(`Fondos máximos ${money(effect.maxFunds, "US$")}`);
  if (effect.weeklyReturn != null) lines.push(`Retorno semanal ${money(effect.weeklyReturn, "US$")}`);
  if (effect.extraOrders != null && effect.extraOrders !== 0) lines.push(`+${effect.extraOrders} órdenes extra`);
  if (effect.styleFlexibilityPp != null && effect.styleFlexibilityPp !== 0) lines.push(`Flexibilidad de estilo +${effect.styleFlexibilityPp} pp`);
  return lines;
}
