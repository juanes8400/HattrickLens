import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useClub,
  usePlayerTrainingLevels,
  usePostMatchTraining,
  useTrainingDevelopment,
  useTrainingFormula,
  useTrainingSquad,
} from "../hooks/useTeam";
import { DataTable, type Column } from "../components/DataTable";
import { CountryCell } from "../components/CountryFlag";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
  ProjectionPanel,
} from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Tabs, PanelDePestanas } from "../components/Tabs";
import { Chart } from "../charts/Chart";
import { barOption } from "../charts/chartOptions";
import type {
  ClubStaffRole,
  ClubStaffRoleEffect,
  ConfirmedLevelUp,
  LevelForecastMilestone,
  PostMatchTrainingOption,
  TrainingExperienceRow,
  TrainingLoyaltyRow,
  TrainingSquadPlayerRow,
  TrainingSquadWeeklyLogEntry,
  TrainingStaminaRow,
} from "../services/api";
import {
  staffEffectLines,
  trainerTrainingSpeedPct,
  trainingStaffLevelColor,
} from "../utils/staffEffects";
import { decimal, number } from "../hooks/useFormat";
import { skillLevelLabel } from "../utils/skillLevels";

type TrainingSection =
  | "datos"
  | "plantilla"
  | "experiencia"
  | "fidelidad"
  | "condicion"
  | "posteriori";
type PlayerTab = "mejoras" | "prevision";

// Resistencia tope real en Hattrick es 9 (formidable) — nunca escala 0-20
// como las demás habilidades. Mismo criterio de barra que ya usa el
// Resistencia de la ficha de jugador: azul = nivel actual, rojo = la
// distancia al nivel esperado ("append" si se espera subir, "eat" —come su
// propio tramo final— si se espera bajar).
const STAMINA_MAX_LEVEL = 9;

const EXPERIENCE_TYPE_LABELS: Record<string, string> = {
  league: "Liga",
  cup: "Copa nacional",
  cup_secondary: "Copa secundaria",
  qualification: "Promoción",
  friendly: "Amistoso",
  friendly_international: "Amistoso internacional",
  tournament: "Torneo",
  masters: "Masters",
  national_team_friendly: "Selección amistoso",
  youth_league: "Liga juvenil",
  youth_friendly: "Amistoso juvenil",
};

function countLabel(value: number, singular: string, plural: string): string {
  return `${number(value)} ${value === 1 ? singular : plural}`;
}

function ProgressCell({
  value,
  digits = 0,
}: {
  value: number | null;
  digits?: number;
}) {
  if (value == null)
    return <span className="text-[var(--muted)]">Sin referencia</span>;
  const bounded = Math.max(0, Math.min(100, value));
  return (
    <div className="flex min-w-28 items-center justify-end gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-[var(--surface-2)]">
        <div
          className="h-full rounded-full bg-[var(--accent)]"
          style={{ width: `${bounded}%` }}
        />
      </div>
      <span className="min-w-12 text-right text-xs tabular-nums">
        {decimal(bounded, digits)}%
      </span>
    </div>
  );
}

// La barra muestra el DESTINO de la guía Ocerin, no vuelve a dibujar el nivel
// actual. El nivel real ya está en la columna anterior; aquí una marca azul
// conserva su posición y la barra se acorta/alarga hasta el esperado. Así un
// cambio 8 → 5 se ve realmente hacia la izquierda y no como una barra 8/9 con
// un tramo rojo difícil de interpretar.
function StaminaProgressCell({ row }: { row: TrainingStaminaRow }) {
  const max = STAMINA_MAX_LEVEL;
  const expected = row.expectedLevel ?? row.level;
  const diff = expected - row.level;
  const currentPct = Math.max(0, Math.min(100, (row.level / max) * 100));
  const expectedPct = Math.max(0, Math.min(100, (expected / max) * 100));
  const direction = diff < 0 ? "↓" : diff > 0 ? "↑" : "=";
  const barTone =
    diff < 0
      ? "bg-[var(--danger)]"
      : diff > 0
        ? "bg-[var(--positive)]"
        : "bg-[var(--accent)]";
  const textTone =
    diff < 0
      ? "text-[var(--danger)]"
      : diff > 0
        ? "text-[var(--positive)]"
        : "text-[var(--muted)]";
  return (
    <div
      className="flex min-w-32 items-center gap-2"
      title={`Actual: ${row.levelName} (${row.level}). Esperado Ocerin: ${row.expectedLevelName ?? "sin dato"} (${expected}).`}
    >
      <span className="min-w-14 whitespace-nowrap text-left text-xs tabular-nums">
        {row.level}{" "}
        <span className={textTone}>
          {direction} {expected}
        </span>
      </span>
      <div className="relative h-2 w-20 rounded-full bg-[var(--surface-2)]">
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${barTone}`}
          style={{ width: `${expectedPct}%` }}
        />
        {diff !== 0 && (
          <div
            className="absolute -top-0.5 h-3 w-0.5 rounded bg-[var(--accent)]"
            style={{ left: `calc(${currentPct}% - 1px)` }}
          />
        )}
      </div>
    </div>
  );
}

function scaledEffect(
  effect: ClubStaffRoleEffect,
  memberLevel: number,
  combinedLevel: number,
): ClubStaffRoleEffect {
  const share = combinedLevel > 0 ? memberLevel / combinedLevel : 0;
  const scale = (value: number | undefined) =>
    value == null ? undefined : Number((value * share).toFixed(3));
  return {
    trainingSpeedPct: scale(effect.trainingSpeedPct),
    injuryRiskPp: scale(effect.injuryRiskPp),
    backgroundForm: scale(effect.backgroundForm),
  };
}

function AssistantCards({ role }: { role: ClubStaffRole }) {
  if (role.members.length === 0) {
    return (
      <p className="p-4 text-sm font-medium text-[var(--danger)]">
        Actualmente no hay asistentes de entrenador registrados.
      </p>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        {role.members.map((member) => {
          const lines = role.effect
            ? staffEffectLines(
                scaledEffect(role.effect, member.level, role.level),
              )
            : [];
          return (
            <div
              key={member.name}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-4"
            >
              <div className="flex items-baseline justify-between gap-3">
                <strong className="text-sm">{member.name}</strong>
                <span
                  className={`shrink-0 text-xs font-semibold tabular-nums ${trainingStaffLevelColor(member.level)}`}
                >
                  Nivel {member.level}/5
                </span>
              </div>
              {lines.length > 0 && (
                <ul className="mt-3 space-y-1 border-t border-[var(--border)] pt-3 text-xs text-[var(--positive)]">
                  {lines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
      {role.effect && (
        <div className="rounded-md border border-[var(--border)] px-3 py-2">
          <p className="text-xs font-medium">
            Aporte combinado · nivel {role.level}
          </p>
          <ul className="mt-1 flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--positive)]">
            {staffEffectLines(role.effect).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function squadColumns(): Column<TrainingSquadPlayerRow>[] {
  return [
    {
      key: "player",
      header: "Nombre",
      align: "left",
      value: (r) => r.name,
      render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
    },
    {
      key: "nativeCountry",
      header: "Nac.",
      align: "left",
      value: (r) => r.nativeCountry ?? "",
      render: (r) => (
        <CountryCell code={r.countryCode} country={r.nativeCountry} compact />
      ),
    },
    {
      key: "age",
      header: "Edad",
      value: (r) => edadOrdenable(r.age),
      render: (r) => r.age,
    },
    {
      key: "level",
      header: "Nivel actual",
      value: (r) => r.level,
      render: (r) => (
        <span className="whitespace-nowrap">
          <span>{r.levelName}</span>{" "}
          <span className="text-xs tabular-nums text-[var(--muted)]">
            ({r.level})
          </span>
        </span>
      ),
    },
    {
      key: "progress",
      header: "Progreso",
      value: (r) => r.progressPct ?? -1,
      render: (r) => <ProgressCell value={r.progressPct} digits={1} />,
    },
    {
      key: "accumulated",
      header: "Acumulado / meta",
      value: (r) => r.weeksElapsed ?? -1,
      render: (r) => (
        <span className="tabular-nums whitespace-nowrap">
          {r.hasReference && r.weeksElapsed != null ? (
            decimal(r.weeksElapsed, 1)
          ) : (
            <span className="text-[var(--muted)]">—</span>
          )}
          <span className="text-[var(--muted)]">
            {" "}
            / {decimal(r.weeksTotal, 1)} sem
          </span>
        </span>
      ),
    },
    {
      key: "remaining",
      header: "Falta / próximo nivel",
      value: (r) =>
        r.hasReference && r.weeksElapsed != null
          ? Math.max(r.weeksTotal - r.weeksElapsed, 0)
          : Number.MAX_SAFE_INTEGER,
      render: (r) => {
        if (r.level >= 20)
          return (
            <span className="text-[var(--positive)]">Máximo alcanzado</span>
          );
        if (!r.hasReference || r.weeksElapsed == null) {
          return (
            <span className="whitespace-nowrap text-[var(--muted)]">
              Sin punto de partida · {skillLevelLabel(r.level + 1)} (
              {r.level + 1})
            </span>
          );
        }
        return (
          <span className="whitespace-nowrap">
            {decimal(Math.max(r.weeksTotal - r.weeksElapsed, 0), 1)} sem
            <span className="text-xs text-[var(--muted)]">
              {" "}
              · {skillLevelLabel(r.level + 1)} ({r.level + 1})
            </span>
          </span>
        );
      },
    },
    {
      // 2026-08-19: la semana de la última subida, en formato tt-ss. Vacía si
      // no hay ninguna: un guion o un cero se leerían como "no mejoró", y lo
      // que pasa es que no hay registro.
      key: "lastImprovement",
      header: "Última mejora",
      align: "left",
      value: (r) => r.lastImprovement,
      render: (r) => (
        <span className="tabular-nums text-[var(--muted)]">
          {r.lastImprovement}
        </span>
      ),
    },
    {
      key: "evidence",
      header: "Evidencia",
      align: "left",
      value: (r) => r.currentWeekMinutes,
      render: (r) => {
        const week =
          r.currentWeekMinutes > 0
            ? `${decimal(r.currentWeekMinutes, 0)}′ · ${decimal(r.currentWeekExposure, 3)} sem`
            : null;
        const label = r.hasHistoricalReference
          ? week
            ? `Historial observado · ${week}`
            : "Historial real observado"
          : week
            ? `${week} · base anterior desconocida`
            : "Sin punto de partida";
        return <span className="text-xs text-[var(--muted)]">{label}</span>;
      },
    },
    {
      key: "htPlayerId",
      header: "PlayerID",
      value: (r) => r.htPlayerId,
      render: (r) => (
        <span className="tabular-nums text-xs">{r.htPlayerId}</span>
      ),
    },
  ];
}

const experienceColumns: Column<TrainingExperienceRow>[] = [
  {
    key: "player",
    header: "Nombre",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  {
    key: "nativeCountry",
    header: "Nac.",
    align: "left",
    value: (r) => r.nativeCountry ?? "",
    render: (r) => (
      <CountryCell code={r.countryCode} country={r.nativeCountry} compact />
    ),
  },
  {
    key: "age",
    header: "Edad",
    value: (r) => edadOrdenable(r.age),
    render: (r) => r.age,
  },
  {
    key: "level",
    header: "Nivel actual",
    value: (r) => r.level,
    render: (r) => (
      <span className="whitespace-nowrap">
        <span>{r.levelName}</span>{" "}
        <span className="text-xs tabular-nums text-[var(--muted)]">
          ({r.level})
        </span>
      </span>
    ),
  },
  {
    key: "progress",
    header: "Progreso",
    value: (r) => r.progressPct ?? -1,
    render: (r) => <ProgressCell value={r.progressPct} digits={1} />,
  },
  {
    key: "accumulated",
    header: "Acumulado / meta",
    value: (r) => r.points ?? -1,
    render: (r) =>
      r.points == null ? (
        <span className="text-[var(--muted)]">—</span>
      ) : (
        <span className="whitespace-nowrap tabular-nums">
          {decimal(r.points, 1)}{" "}
          <span className="text-[var(--muted)]">
            / {decimal(r.pointsPerLevel, 0)} pts
          </span>
        </span>
      ),
  },
  {
    key: "remaining",
    header: "Falta / próximo nivel",
    value: (r) => r.remainingPoints ?? Number.MAX_SAFE_INTEGER,
    render: (r) => {
      if (r.level >= 20)
        return <span className="text-[var(--positive)]">Máximo alcanzado</span>;
      if (r.remainingPoints == null)
        return <span className="text-[var(--muted)]">Sin referencia</span>;
      return (
        <span className="whitespace-nowrap tabular-nums">
          {decimal(r.remainingPoints, 1)} pts
          <span className="text-xs text-[var(--muted)]">
            {" "}
            · {skillLevelLabel(r.level + 1)} ({r.level + 1})
          </span>
        </span>
      );
    },
  },
  {
    // 2026-08-19: la semana de la última subida, en formato tt-ss. Vacía si no
    // hay ninguna: un guion o un cero se leerían como "no mejoró", y lo que
    // pasa es que no hay registro.
    key: "lastImprovement",
    header: "Última mejora",
    align: "left",
    value: (r) => r.lastImprovement,
    render: (r) => (
      <span className="tabular-nums text-[var(--muted)]">
        {r.lastImprovement}
      </span>
    ),
  },
  {
    key: "matchCounts",
    header: "Evidencia",
    align: "left",
    value: (r) =>
      Object.values(r.matchCounts).reduce((sum, matches) => sum + matches, 0) +
      r.unscoredNationalMatches,
    render: (r) => {
      const parts = Object.entries(r.matchCounts)
        .filter(([, matches]) => matches > 0)
        .map(
          ([kind, matches]) =>
            `${EXPERIENCE_TYPE_LABELS[kind] ?? kind}: ${countLabel(matches, "partido", "partidos")}`,
        );
      if (r.unscoredNationalMatches > 0) {
        parts.push(
          `Selección sin puntaje: ${countLabel(r.unscoredNationalMatches, "partido", "partidos")}`,
        );
      }
      return parts.length > 0 ? (
        <span className="text-xs text-[var(--muted)]">{parts.join(" · ")}</span>
      ) : (
        <span className="text-xs text-[var(--muted)]">
          Aún sin partidos observados
        </span>
      );
    },
  },
  {
    key: "htPlayerId",
    header: "PlayerID",
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  },
];

const loyaltyColumns: Column<TrainingLoyaltyRow>[] = [
  {
    key: "player",
    header: "Nombre",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  {
    key: "nativeCountry",
    header: "Nac.",
    align: "left",
    value: (r) => r.nativeCountry ?? "",
    render: (r) => (
      <CountryCell code={r.countryCode} country={r.nativeCountry} compact />
    ),
  },
  {
    key: "age",
    header: "Edad",
    value: (r) => edadOrdenable(r.age),
    render: (r) => r.age,
  },
  {
    key: "level",
    header: "Nivel actual",
    value: (r) => r.calculatedLevel ?? r.reportedLevel,
    render: (r) => (
      <span className="whitespace-nowrap">
        <span>{r.levelName}</span>{" "}
        <span className="text-xs tabular-nums text-[var(--muted)]">
          ({r.calculatedLevel ?? r.reportedLevel})
        </span>
      </span>
    ),
  },
  {
    key: "progress",
    header: "Progreso",
    value: (r) => r.progressPct ?? -1,
    render: (r) => <ProgressCell value={r.progressPct} digits={2} />,
  },
  {
    key: "accumulated",
    header: "Acumulado / meta",
    value: (r) => r.daysInClub ?? -1,
    render: (r) => {
      if (r.daysInClub == null)
        return <span className="text-[var(--muted)]">Sin referencia</span>;
      if (r.daysToNextLevel == null) {
        return (
          <span className="whitespace-nowrap tabular-nums">
            {number(r.daysInClub)} días · máximo
          </span>
        );
      }
      return (
        <span className="whitespace-nowrap tabular-nums">
          {number(r.daysInClub)}{" "}
          <span className="text-[var(--muted)]">
            / {number(r.daysInClub + r.daysToNextLevel)} días
          </span>
        </span>
      );
    },
  },
  {
    key: "remaining",
    header: "Falta / próximo nivel",
    value: (r) => r.daysToNextLevel ?? Number.MAX_SAFE_INTEGER,
    render: (r) => {
      if (r.daysInClub == null)
        return <span className="text-[var(--muted)]">Sin referencia</span>;
      if (r.nextLevel == null)
        return <span className="text-[var(--positive)]">Máximo alcanzado</span>;
      if (r.daysToNextLevel == null)
        return <span className="text-[var(--muted)]">Sin referencia</span>;
      return (
        <span className="whitespace-nowrap">
          {countLabel(r.daysToNextLevel, "día", "días")}
          <span className="text-xs text-[var(--muted)]">
            {" "}
            · {skillLevelLabel(r.nextLevel)} ({r.nextLevel})
          </span>
        </span>
      );
    },
  },
  {
    // 2026-08-19: la semana de la última subida, en formato tt-ss. Vacía si no
    // hay ninguna: un guion o un cero se leerían como "no mejoró", y lo que
    // pasa es que no hay registro.
    key: "lastImprovement",
    header: "Última mejora",
    align: "left",
    value: (r) => r.lastImprovement,
    render: (r) => (
      <span className="tabular-nums text-[var(--muted)]">
        {r.lastImprovement}
      </span>
    ),
  },
  {
    key: "source",
    header: "Evidencia",
    align: "left",
    value: (r) => r.daysInClub ?? -1,
    render: (r) => (
      <span className="text-xs text-[var(--muted)]">
        {r.daysInClub == null
          ? "Sin fecha de compra"
          : `${number(r.daysInClub)} días desde compra`}
      </span>
    ),
  },
  {
    key: "htPlayerId",
    header: "PlayerID",
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  },
];

const staminaColumns: Column<TrainingStaminaRow>[] = [
  {
    key: "player",
    header: "Nombre",
    align: "left",
    value: (r) => r.name,
    render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
  },
  {
    key: "nativeCountry",
    header: "Nac.",
    align: "left",
    value: (r) => r.nativeCountry ?? "",
    render: (r) => (
      <CountryCell code={r.countryCode} country={r.nativeCountry} compact />
    ),
  },
  {
    key: "age",
    header: "Edad",
    value: (r) => edadOrdenable(r.age),
    render: (r) => r.age,
  },
  {
    key: "level",
    header: "Nivel actual",
    value: (r) => r.level,
    render: (r) => (
      <span className="whitespace-nowrap">
        <span>{r.levelName}</span>{" "}
        <span className="text-xs tabular-nums text-[var(--muted)]">
          ({r.level})
        </span>
      </span>
    ),
  },
  {
    key: "progress",
    header: "Actual → guía",
    value: (r) => r.expectedLevel ?? r.level,
    render: (r) => <StaminaProgressCell row={r} />,
  },
  {
    key: "effectiveTrainingPct",
    header: "% aplicado",
    value: (r) => r.effectiveTrainingPct,
    render: (r) => (
      <span className="tabular-nums">
        {decimal(r.effectiveTrainingPct, 1)}%
      </span>
    ),
  },
  {
    key: "expectedLevel",
    header: "Esperado Ocerin",
    value: (r) => r.expectedLevel ?? -1,
    render: (r) =>
      r.expectedLevel == null ? (
        <span className="text-[var(--muted)]">Sin dato</span>
      ) : (
        <span className="whitespace-nowrap">
          <span>{r.expectedLevelName}</span>{" "}
          <span className="text-xs tabular-nums text-[var(--muted)]">
            ({r.expectedLevel})
          </span>
        </span>
      ),
  },
  {
    // Condición no tiene columna de Evidencia, así que va detrás del
    // progreso, que es su equivalente.
    key: "lastImprovement",
    header: "Última mejora",
    align: "left",
    value: (r) => r.lastImprovement,
    render: (r) => (
      <span className="tabular-nums text-[var(--muted)]">
        {r.lastImprovement}
      </span>
    ),
  },
  {
    key: "htPlayerId",
    header: "PlayerID",
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  },
];

const weeklyLogColumns: Column<TrainingSquadWeeklyLogEntry>[] = [
  {
    key: "seasonWeek",
    header: "TT-ss",
    align: "left",
    value: (r) => r.seasonWeek ?? "",
  },
  { key: "date", header: "Fecha", align: "left", value: (r) => r.date },
  {
    key: "trainingType",
    header: "Tipo",
    align: "left",
    value: (r) => r.trainingType,
  },
  {
    key: "intensity",
    header: "Intensidad",
    value: (r) => r.intensity,
    render: (r) => `${r.intensity}%`,
  },
  {
    key: "staminaShare",
    header: "Condición",
    value: (r) => r.staminaShare,
    render: (r) => `${r.staminaShare}%`,
  },
  {
    key: "trainerName",
    header: "Entrenador",
    align: "left",
    value: (r) => r.trainerName,
  },
];

const confirmedColumns: Column<ConfirmedLevelUp>[] = [
  {
    key: "seasonWeek",
    header: "TT-ss",
    align: "left",
    value: (r) => r.seasonWeek,
  },
  {
    key: "change",
    header: "Subida",
    align: "left",
    value: (r) => `${r.fromLevelName} -> ${r.toLevelName}`,
    render: (r) => (
      <span>
        {r.fromLevelName} <span className="text-[var(--muted)]">→</span>{" "}
        <b>{r.toLevelName}</b>
      </span>
    ),
  },
  {
    key: "weeksBetween",
    header: "Semanas",
    value: (r) => r.weeksBetween ?? -1,
    render: (r) =>
      r.weeksBetween == null ? (
        <span className="text-[var(--muted)]">primera registrada</span>
      ) : (
        `${r.weeksBetween} sem`
      ),
  },
];

const forecastColumns: Column<LevelForecastMilestone>[] = [
  {
    key: "level",
    header: "Nivel",
    value: (r) => r.level,
    render: (r) => `${r.level} · ${r.levelName}`,
  },
  {
    key: "weeksFor",
    header: "Semanas de este nivel",
    value: (r) => r.weeksForThisLevel,
    render: (r) => r.weeksForThisLevel.toFixed(1),
  },
  {
    key: "cumulative",
    header: "Semanas desde hoy",
    value: (r) => r.weeksFromNow,
    render: (r) => r.weeksFromNow.toFixed(1),
  },
  {
    key: "seasonWeek",
    header: "TT-ss estimada",
    align: "left",
    value: (r) => r.seasonWeek ?? "",
  },
  {
    key: "age",
    header: "Edad proyectada",
    value: (r) => edadOrdenable(r.age),
    render: (r) => r.age,
  },
];

const optionColumns: Column<PostMatchTrainingOption>[] = [
  {
    key: "name",
    header: "Entrenamiento",
    align: "left",
    value: (r) => r.name,
    render: (r) => (
      <span className={r.recommendable ? "" : "text-[var(--muted)]"}>
        {r.name}
        {!r.recommendable && " · referencia"}
      </span>
    ),
  },
  { key: "score", header: "Score", value: (r) => r.score },
  {
    key: "minutes",
    header: "Min. equivalentes",
    value: (r) => r.equivalentMinutes,
  },
  { key: "players", header: "Jugadores", value: (r) => r.trainedPlayers },
  { key: "full", header: "Full", value: (r) => r.fullTrainingPlayers },
  { key: "pops", header: "Pops <=3s", value: (r) => r.popsSoon },
];

/** La edad de Hattrick es «años.días», no un decimal.
 *
 *  Un año de Hattrick dura 112 días, así que «28.110» son 28 años y 110 días
 *  --casi 29-- y «28.9» son 28 años y 9 días. Pasarlo por `parseFloat` rompe
 *  las dos cosas a la vez: enseña 28.11 en vez de 28.110 (110 días
 *  convertidos en 11) y ordena al de 110 días por delante del de 9, porque
 *  numéricamente 28.11 < 28.9. Hasta el 2026-08-30 las cinco tablas de esta
 *  pantalla lo hacían así, y la edad de un mismo jugador no coincidía con la
 *  que enseñan Jugadores y Posiciones.
 *
 *  Esto devuelve una clave que SÍ ordena; el texto se pinta tal cual llega. */
const DIAS_POR_TEMPORADA = 112;

function edadOrdenable(edad: string): number {
  const [anios, dias] = edad.split(".");
  return Number(anios ?? 0) + Number(dias ?? 0) / DIAS_POR_TEMPORADA;
}

export function TrainingPage() {
  // Abre en «Entrenamiento actual», no en «Datos Entrenamiento». Hasta el
  // 2026-08-30 la pestaña de entrada era la de la configuración --entrenador,
  // asistentes, intensidad--, que describe el AJUSTE y no el resultado: quien
  // entraba a esta pantalla a ver cómo va su plantilla aterrizaba en la ficha
  // del cuerpo técnico y tenía que dar un clic más. Es el mismo arreglo que se
  // le hizo a Cambios: primero la respuesta, la instrumentación al final.
  const [section, setSection] = useState<TrainingSection>("plantilla");
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [includeThisWeek, setIncludeThisWeek] = useState(true);
  const [selectedPlayerId, setSelectedPlayerId] = useState<number | null>(null);
  const [playerTab, setPlayerTab] = useState<PlayerTab>("mejoras");

  const squad = useTrainingSquad(selectedSkill, includeThisWeek);
  const postMatch = usePostMatchTraining();
  const development = useTrainingDevelopment(
    section === "experiencia" ||
      section === "fidelidad" ||
      section === "condicion",
  );
  const formula = useTrainingFormula();
  const club = useClub();
  const playerLevels = usePlayerTrainingLevels(selectedPlayerId, selectedSkill);

  if (squad.isLoading || postMatch.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (postMatch.isError) return <ErrorState error={postMatch.error} />;

  const data = squad.data;
  const post = postMatch.data;
  const validation = formula.data?.validation;
  if (!data) return <Empty>Sincroniza para ver el entrenamiento.</Empty>;

  const recommendation = post?.recommendation ?? null;
  const currentName = post?.currentTraining?.name ?? "sin dato";
  const staff = club.data?.staff ?? null;
  const assistantRole =
    staff?.roles.find((role) => role.key === "assistant_trainer_levels") ??
    null;
  const trainerName = data.weeklyLog[0]?.trainerName || "Sin dato";
  const trainerSpeed = staff
    ? trainerTrainingSpeedPct(staff.trainer.skillLevel)
    : null;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Entrenamiento</h1>
        <p className="text-sm text-[var(--muted)]">
          Entrenamiento actual: {currentName} · viendo {data.skillLabel}
        </p>
        <EnlaceATransparencia
          seccion="entrenamiento"
          calculo="semanas-al-pop"
        />
      </header>

      <Tabs
        grupo="entrenamiento"
        tabs={[
          { key: "plantilla", label: "Entrenamiento actual" },
          { key: "experiencia", label: "Experiencia" },
          { key: "fidelidad", label: "Fidelidad" },
          { key: "condicion", label: "Condición" },
          { key: "posteriori", label: "A posteriori" },
          { key: "datos", label: "Datos Entrenamiento" },
        ]}
        active={section}
        onChange={setSection}
      />

      <PanelDePestanas
        grupo="entrenamiento"
        activa={section}
        className="space-y-4"
      >
        {section === "datos" && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3 [&>*]:min-w-0">
              <Kpi label="Entrenamiento" value={currentName} />
              <Kpi
                label="% de entrenamiento"
                value={`${data.setup.intensity}%`}
              />
              <Kpi label="% condición" value={`${data.setup.staminaShare}%`} />
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(18rem,0.72fr)_minmax(0,1.5fr)] [&>*]:min-w-0">
              <Panel title="Entrenador" meta="leído de Hattrick">
                {club.isLoading ? (
                  <Loading />
                ) : (
                  <dl className="space-y-3 p-4 text-sm">
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--muted)]">Nombre</dt>
                      <dd className="text-right font-medium">{trainerName}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--muted)]">
                        Nivel de entrenador
                      </dt>
                      <dd
                        className={`font-semibold tabular-nums ${trainingStaffLevelColor(staff?.trainer.skillLevel)}`}
                      >
                        {staff ? `${staff.trainer.skillLevel}/5` : "Sin dato"}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--muted)]">
                        Nivel de liderazgo
                      </dt>
                      <dd>
                        {staff
                          ? `${skillLevelLabel(staff.trainer.leadership, true)} (${staff.trainer.leadership})`
                          : "Sin dato"}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-4 border-t border-[var(--border)] pt-3">
                      <dt className="text-[var(--muted)]">
                        Velocidad de entrenamiento
                      </dt>
                      <dd className="tabular-nums font-medium text-[var(--positive)]">
                        {trainerSpeed == null ? "Sin dato" : `${trainerSpeed}%`}
                      </dd>
                    </div>
                  </dl>
                )}
              </Panel>

              <Panel
                title="Asistentes de entrenador"
                meta={
                  assistantRole
                    ? `${assistantRole.members.length} asistente(s) · nivel combinado ${assistantRole.level}`
                    : "sin sincronizar"
                }
              >
                {club.isLoading ? (
                  <Loading />
                ) : club.isError ? (
                  <Note>No pudimos cargar el cuerpo técnico.</Note>
                ) : assistantRole ? (
                  <AssistantCards role={assistantRole} />
                ) : (
                  <Note>
                    Sin datos de asistentes. Sincroniza para traerlos.
                  </Note>
                )}
              </Panel>
            </div>
          </div>
        )}

        {section === "plantilla" && (
          <>
            <Panel
              title="Entrenamiento actual"
              meta={`${data.players.length} jugadores actuales · ordenados por progreso`}
            >
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
                <span className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                  Configuración de la vista
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-sm">
                    <span className="text-[var(--muted)]">Habilidad</span>
                    <select
                      value={selectedSkill ?? data.skill}
                      onChange={(e) => setSelectedSkill(e.target.value)}
                      className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-sm"
                    >
                      {data.availableSkills.map((s) => (
                        <option key={s.skill} value={s.skill}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={includeThisWeek}
                      onChange={(e) => setIncludeThisWeek(e.target.checked)}
                    />
                    Incluir los partidos de esta semana
                  </label>
                </div>
              </div>

              <DataTable
                rows={data.players}
                columns={squadColumns()}
                rowKey={(r) => r.htPlayerId}
                initialSort="progress"
                csvName="entrenamiento-plantilla"
                selectedRowKey={selectedPlayerId}
                onRowClick={(r) => setSelectedPlayerId(r.htPlayerId)}
                emptyMessage="Sin jugadores en la plantilla."
              />
            </Panel>
            {data.notes.length > 0 && <Note>{data.notes.join(" ")}</Note>}

            {data.weeklyLog.length > 0 && (
              <Panel
                title="Historial de configuración semanal"
                meta={`${data.weeklyLog.length} semana(s) registradas`}
              >
                <DataTable
                  emptyMessage="Sin semanas de entrenamiento registradas todavía."
                  rows={data.weeklyLog}
                  columns={weeklyLogColumns}
                  rowKey={(r) => r.date}
                  initialSort="date"
                  csvName="entrenamiento-historial-semanal"
                />
              </Panel>
            )}

            {validation && (
              <div className="prosa rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-xs text-[var(--muted)]">
                {validation.observations > 0 ? (
                  <>
                    Contraste con pops reales: diferencia media de{" "}
                    <b className="text-[var(--text)]">
                      {validation.meanErrorWeeks == null
                        ? "—"
                        : `${validation.meanErrorWeeks} sem`}
                    </b>{" "}
                    sobre {validation.observations} subida(s) confirmada(s) de{" "}
                    {formula.data?.trainedSkill}.
                  </>
                ) : (
                  <>
                    Todavía no hay dos subidas seguidas de{" "}
                    {formula.data?.trainedSkill} para contrastar la fórmula.
                  </>
                )}{" "}
                <Link
                  to="/engine"
                  className="underline hover:text-[var(--text)]"
                >
                  ver el detalle en Motor
                </Link>
                .
              </div>
            )}

            {selectedPlayerId != null && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold">
                    {playerLevels.data?.name ?? "Cargando…"}
                    {playerLevels.data && (
                      <span className="text-[var(--muted)]">
                        {" "}
                        · {playerLevels.data.skillLabel}
                      </span>
                    )}
                  </h2>
                  <button
                    onClick={() => setSelectedPlayerId(null)}
                    className="text-xs text-[var(--muted)] underline hover:text-[var(--text)]"
                  >
                    Cerrar
                  </button>
                </div>

                <Tabs
                  grupo="jugador-entrenamiento"
                  label="Vistas del jugador"
                  tabs={[
                    { key: "mejoras", label: "Mejoras" },
                    { key: "prevision", label: "Previsión subidas" },
                  ]}
                  active={playerTab}
                  onChange={setPlayerTab}
                />

                <PanelDePestanas
                  grupo="jugador-entrenamiento"
                  activa={playerTab}
                  className="space-y-4"
                >
                  {playerLevels.isLoading && <Loading />}
                  {playerLevels.isError && (
                    <ErrorState error={playerLevels.error} />
                  )}

                  {playerLevels.data && playerTab === "mejoras" && (
                    <>
                      <Panel
                        title="Subidas confirmadas"
                        meta="confirmadas por Hattrick"
                      >
                        {playerLevels.data.confirmed.length === 0 && (
                          <Empty>
                            {playerLevels.data.notes.join(" ") ||
                              "Sin subidas confirmadas todavía."}
                          </Empty>
                        )}
                      </Panel>
                      {playerLevels.data.confirmed.length > 0 && (
                        <DataTable
                          emptyMessage="Ninguna subida confirmada todavía."
                          rows={playerLevels.data.confirmed}
                          columns={confirmedColumns}
                          rowKey={(r) => r.seasonWeek}
                          initialSort="seasonWeek"
                          initialDescending={false}
                          csvName="entrenamiento-mejoras"
                        />
                      )}
                    </>
                  )}

                  {playerLevels.data && playerTab === "prevision" && (
                    <ProjectionPanel
                      title="Previsión de subidas"
                      meta={`hasta nivel 20 · ${playerLevels.data.forecast.length} nivel(es)`}
                    >
                      <DataTable
                        emptyMessage="Sin previsión: hace falta al menos una semana entrenada."
                        rows={playerLevels.data.forecast}
                        columns={forecastColumns}
                        rowKey={(r) => r.level}
                        initialSort="level"
                        initialDescending={false}
                        csvName="entrenamiento-prevision"
                      />
                    </ProjectionPanel>
                  )}
                </PanelDePestanas>
              </div>
            )}
          </>
        )}

        {section === "experiencia" && (
          <>
            {development.isLoading && <Loading />}
            {development.isError && <ErrorState error={development.error} />}
            {development.data && (
              <>
                <Panel
                  title="Experiencia"
                  meta={`${development.data.experience.length} jugadores · partidos y minutos reales`}
                >
                  <DataTable
                    rows={development.data.experience}
                    columns={experienceColumns}
                    rowKey={(r) => r.htPlayerId}
                    initialSort="progress"
                    csvName="entrenamiento-experiencia"
                    emptyMessage="Sin jugadores para calcular experiencia."
                  />
                </Panel>
              </>
            )}
          </>
        )}

        {section === "fidelidad" && (
          <>
            {development.isLoading && <Loading />}
            {development.isError && <ErrorState error={development.error} />}
            {development.data && (
              <>
                <Panel
                  title="Fidelidad"
                  meta={`${development.data.loyalty.length} jugadores · antigüedad real en el club`}
                >
                  <DataTable
                    rows={development.data.loyalty}
                    columns={loyaltyColumns}
                    rowKey={(r) => r.htPlayerId}
                    initialSort="progress"
                    csvName="entrenamiento-fidelidad"
                    emptyMessage="Sin jugadores para calcular fidelidad."
                  />
                </Panel>
                {development.data.notes.map((note) => (
                  <Note key={note}>{note}</Note>
                ))}
              </>
            )}
          </>
        )}

        {section === "condicion" && (
          <>
            {development.isLoading && <Loading />}
            {development.isError && <ErrorState error={development.error} />}
            {development.data && (
              <>
                <Panel
                  title="Condición"
                  meta={
                    <span className="flex items-center gap-2">
                      {`${development.data.stamina.length} jugadores · ${decimal(development.data.stamina[0]?.effectiveTrainingPct ?? 0, 1)}% efectivo · guía Ocerin`}
                      <EnlaceATransparencia
                        seccion="entrenamiento"
                        calculo="condicion"
                      />
                    </span>
                  }
                >
                  <DataTable
                    rows={development.data.stamina}
                    columns={staminaColumns}
                    rowKey={(r) => r.htPlayerId}
                    initialSort="level"
                    csvName="entrenamiento-condicion"
                    emptyMessage="Sin jugadores para calcular condición."
                  />
                </Panel>
                {development.data.notes.map((note) => (
                  <Note key={note}>{note}</Note>
                ))}
              </>
            )}
          </>
        )}

        {section === "posteriori" && post && (
          <>
            <div className="grid gap-4 sm:grid-cols-3 [&>*]:min-w-0">
              <Kpi
                label="A posteriori elegiría"
                value={recommendation?.name ?? "Sin datos"}
                hint={`Actual: ${currentName}`}
                tone={
                  recommendation &&
                  post.currentTraining &&
                  recommendation.trainingType !==
                    post.currentTraining.trainingType
                    ? "positive"
                    : undefined
                }
              />
              <Kpi
                label="Minutos aprovechables"
                value={`${recommendation?.equivalentMinutes.toFixed(0) ?? 0}`}
                hint="equivalentes a entrenamiento completo"
              />
              <Kpi
                label="Jugadores entrenados"
                value={`${recommendation?.trainedPlayers ?? 0}`}
                hint={`${recommendation?.fullTrainingPlayers ?? 0} con entrenamiento full`}
              />
            </div>

            <Panel
              title="Entrenamiento decidido a posteriori"
              meta="elige después de ver quién jugó y dónde"
            >
              <div className="grid gap-4 p-4 lg:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
                <Chart
                  ariaLabel="Ranking de entrenamientos por exposición post-partido"
                  height={320}
                  option={barOption(
                    post.options.slice(0, 8).map((o) => o.name),
                    post.options.slice(0, 8).map((o) => o.score),
                    "Score",
                  )}
                />
                <div className="rounded-lg border border-[var(--border)] p-4">
                  <h3 className="text-sm font-semibold">
                    {recommendation
                      ? `Mejor opción: ${recommendation.name}`
                      : "Sin recomendación"}
                  </h3>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    La app suma los minutos reales por posición y compara qué
                    tipo de entrenamiento cosecha mejor esa exposición antes del
                    update semanal.
                  </p>
                  <ul className="mt-4 space-y-1 text-xs text-[var(--muted)]">
                    {(recommendation?.rationale ?? []).map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                  <ul className="mt-4 space-y-2 text-sm">
                    {(recommendation?.topTrainees ?? [])
                      .slice(0, 5)
                      .map((p) => (
                        <li
                          key={p.htPlayerId}
                          className="flex items-center justify-between gap-3"
                        >
                          <PlayerLink htPlayerId={p.htPlayerId} name={p.name} />
                          <span className="text-xs tabular-nums text-[var(--muted)]">
                            {(p.exposure * 100).toFixed(0)}% ·{" "}
                            {p.weeksToPop == null
                              ? "—"
                              : `${p.weeksToPop.toFixed(1)} sem`}
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              </div>
              <Note>{post.notes.join(" ")}</Note>
            </Panel>

            <DataTable
              emptyMessage="Sin opciones que comparar para este partido."
              rows={post.options}
              columns={optionColumns}
              rowKey={(r) => r.trainingType}
              initialSort="score"
              csvName="entrenamiento-a-posteriori"
            />
          </>
        )}
      </PanelDePestanas>
    </div>
  );
}
