import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import i18n from "../i18n";
import {
  useClub,
  usePlayerTrainingLevels,
  usePostMatchTraining,
  useTrainingDevelopment,
  useTrainingFormula,
  useTrainingSquad,
  useUltimoEntrenamiento,
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
import clsx from "clsx";
import {
  date,
  dateTime,
  decimal,
  htAgeTexto,
  number,
} from "../hooks/useFormat";
import { skillLevelLabel } from "../utils/skillLevels";
import { tx } from "../i18n/tx";

type TrainingSection =
  | "datos"
  | "plantilla"
  | "ultimo"
  | "experiencia"
  | "fidelidad"
  | "condicion"
  | "posteriori";
type PlayerTab = "mejoras" | "prevision";

// Resistencia tope real en Hattrick es 9 (formidable), nunca escala 0-20
// como las demás habilidades. Mismo criterio de barra que ya usa el
// Resistencia de la ficha de jugador: azul = nivel actual, rojo = la
// distancia al nivel esperado ("append" si se espera subir, "eat", come su
// propio tramo final, si se espera bajar).
const STAMINA_MAX_LEVEL = 9;

const EXPERIENCE_TYPE_LABELS: Record<string, string> = {
  league: tx("Liga"),
  cup: tx("Copa nacional"),
  cup_secondary: tx("Copa secundaria"),
  qualification: tx("Promoción"),
  friendly: tx("Amistoso"),
  friendly_international: tx("Amistoso internacional"),
  tournament: tx("Torneo"),
  masters: tx("Masters"),
  national_team_friendly: tx("Selección amistoso"),
  youth_league: tx("Liga juvenil"),
  youth_friendly: tx("Amistoso juvenil"),
};

/** Las tablas de esta pantalla se arman fuera de los componentes; leen el
 *  idioma en el momento de pintarse, no al cargar el módulo. */
const t = i18n.t.bind(i18n);

/** «3 sem», «1 partido», «4 días», en el idioma de la app. */
const semanas = (n: string | number) =>
  t("entrenamiento.sem", "{{n}} sem", { n });
const partidos = (n: number) =>
  n === 1
    ? t("entrenamiento.unPartido", "{{n}} partido", { n: number(n) })
    : t("entrenamiento.nPartidos", "{{n}} partidos", { n: number(n) });
const dias = (n: number) =>
  n === 1
    ? t("entrenamiento.unDia", "{{n}} día", { n: number(n) })
    : t("entrenamiento.nDias", "{{n}} días", { n: number(n) });

const sinReferencia = () => t("entrenamiento.sinReferencia", "Sin referencia");
const maximoAlcanzado = () =>
  t("entrenamiento.maximoAlcanzado", "Máximo alcanzado");

function ProgressCell({
  value,
  digits = 0,
}: {
  value: number | null;
  digits?: number;
}) {
  if (value == null)
    return <span className="text-[var(--muted)]">{sinReferencia()}</span>;
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
      title={t(
        "entrenamiento.actualEsperado",
        "Actual: {{actual}} ({{nivel}}). Esperado Ocerin: {{esperado}} ({{nivelEsperado}}).",
        {
          actual: row.levelName,
          nivel: row.level,
          esperado: row.expectedLevelName ?? t("club.sinDatoMin", "sin dato"),
          nivelEsperado: expected,
        },
      )}
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
  const { t } = useTranslation();
  if (role.members.length === 0) {
    return (
      <p className="p-4 text-sm font-medium text-[var(--danger)]">
        {t(
          "entrenamiento.sinAsistentes",
          "Actualmente no hay asistentes de entrenador registrados.",
        )}
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
                  {t("entrenamiento.nivelDe5", "Nivel {{n}}/5", {
                    n: member.level,
                  })}
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
            {t(
              "entrenamiento.aporteCombinado",
              "Aporte combinado · nivel {{n}}",
              { n: role.level },
            )}
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

/** Las columnas que comparten las cuatro tablas por jugador. */
function columnasDeJugador<
  R extends {
    htPlayerId: number;
    name: string;
    nativeCountry: string | null;
    countryCode: string | null;
    age: string;
  },
>(): Column<R>[] {
  return [
    {
      key: "player",
      header: t("entrenamiento.nombre", "Nombre"),
      align: "left",
      value: (r) => r.name,
      render: (r) => <PlayerLink htPlayerId={r.htPlayerId} name={r.name} />,
    },
    {
      key: "nativeCountry",
      header: t("entrenamiento.nac", "Nac."),
      align: "left",
      value: (r) => r.nativeCountry ?? "",
      render: (r) => (
        <CountryCell code={r.countryCode} country={r.nativeCountry} compact />
      ),
    },
    {
      key: "age",
      header: t("jugadores.edad", "Edad"),
      value: (r) => edadOrdenable(r.age),
      render: (r) => htAgeTexto(r.age),
    },
  ];
}

function columnaUltimaMejora<
  R extends { lastImprovement: string },
>(): Column<R> {
  // 2026-08-19: la semana de la última subida, en formato tt-ss. Vacía si no
  // hay ninguna: un guion o un cero se leerían como "no mejoró", y lo que
  // pasa es que no hay registro.
  return {
    key: "lastImprovement",
    header: t("entrenamiento.ultimaMejora", "Última mejora"),
    align: "left",
    value: (r) => r.lastImprovement,
    render: (r) => (
      <span className="tabular-nums text-[var(--muted)]">
        {r.lastImprovement}
      </span>
    ),
  };
}

function columnaPlayerId<R extends { htPlayerId: number }>(): Column<R> {
  return {
    key: "htPlayerId",
    header: "PlayerID",
    raw: true,
    value: (r) => r.htPlayerId,
    render: (r) => <span className="tabular-nums text-xs">{r.htPlayerId}</span>,
  };
}

function squadColumns(): Column<TrainingSquadPlayerRow>[] {
  return [
    ...columnasDeJugador<TrainingSquadPlayerRow>(),
    {
      key: "level",
      header: t("entrenamiento.nivelActual", "Nivel actual"),
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
      header: t("entrenamiento.progreso", "Progreso"),
      value: (r) => r.progressPct ?? -1,
      render: (r) => <ProgressCell value={r.progressPct} digits={1} />,
    },
    {
      key: "accumulated",
      header: t("entrenamiento.acumulado", "Acumulado / meta"),
      value: (r) => r.weeksElapsed ?? -1,
      render: (r) => (
        <span className="tabular-nums whitespace-nowrap">
          {r.hasReference && r.weeksElapsed != null ? (
            decimal(r.weeksElapsed, 1)
          ) : (
            <span className="text-[var(--muted)]">-</span>
          )}
          <span className="text-[var(--muted)]">
            {" "}
            / {semanas(decimal(r.weeksTotal, 1))}
          </span>
        </span>
      ),
    },
    {
      key: "remaining",
      header: t("entrenamiento.falta", "Falta / próximo nivel"),
      value: (r) =>
        r.hasReference && r.weeksElapsed != null
          ? Math.max(r.weeksTotal - r.weeksElapsed, 0)
          : Number.MAX_SAFE_INTEGER,
      render: (r) => {
        if (r.level >= 20)
          return (
            <span className="text-[var(--positive)]">{maximoAlcanzado()}</span>
          );
        if (!r.hasReference || r.weeksElapsed == null) {
          return (
            <span className="whitespace-nowrap text-[var(--muted)]">
              {t("entrenamiento.sinPuntoPartida", "Sin punto de partida")} ·{" "}
              {skillLevelLabel(r.level + 1)} ({r.level + 1})
            </span>
          );
        }
        return (
          <span className="whitespace-nowrap">
            {semanas(decimal(Math.max(r.weeksTotal - r.weeksElapsed, 0), 1))}
            <span className="text-xs text-[var(--muted)]">
              {" "}
              · {skillLevelLabel(r.level + 1)} ({r.level + 1})
            </span>
          </span>
        );
      },
    },
    columnaUltimaMejora<TrainingSquadPlayerRow>(),
    {
      key: "evidence",
      header: t("entrenamiento.evidencia", "Evidencia"),
      align: "left",
      value: (r) => r.currentWeekMinutes,
      render: (r) => {
        const week =
          r.currentWeekMinutes > 0
            ? `${decimal(r.currentWeekMinutes, 0)}′ · ${semanas(decimal(r.currentWeekExposure, 3))}`
            : null;
        const label = r.hasHistoricalReference
          ? week
            ? t(
                "entrenamiento.historialSemana",
                "Historial observado · {{semana}}",
                { semana: week },
              )
            : t("entrenamiento.historialReal", "Historial real observado")
          : week
            ? t(
                "entrenamiento.baseDesconocida",
                "{{semana}} · base anterior desconocida",
                { semana: week },
              )
            : t("entrenamiento.sinPuntoPartida", "Sin punto de partida");
        return <span className="text-xs text-[var(--muted)]">{label}</span>;
      },
    },
    columnaPlayerId<TrainingSquadPlayerRow>(),
  ];
}

function experienceColumns(): Column<TrainingExperienceRow>[] {
  return [
    ...columnasDeJugador<TrainingExperienceRow>(),
    {
      key: "level",
      header: t("entrenamiento.nivelActual", "Nivel actual"),
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
      header: t("entrenamiento.progreso", "Progreso"),
      value: (r) => r.progressPct ?? -1,
      render: (r) => <ProgressCell value={r.progressPct} digits={1} />,
    },
    {
      key: "accumulated",
      header: t("entrenamiento.acumulado", "Acumulado / meta"),
      value: (r) => r.points ?? -1,
      render: (r) =>
        r.points == null ? (
          <span className="text-[var(--muted)]">-</span>
        ) : (
          <span className="whitespace-nowrap tabular-nums">
            {decimal(r.points, 1)}{" "}
            <span className="text-[var(--muted)]">
              /{" "}
              {t("entrenamiento.pts", "{{n}} pts", {
                n: decimal(r.pointsPerLevel, 0),
              })}
            </span>
          </span>
        ),
    },
    {
      key: "remaining",
      header: t("entrenamiento.falta", "Falta / próximo nivel"),
      value: (r) => r.remainingPoints ?? Number.MAX_SAFE_INTEGER,
      render: (r) => {
        if (r.level >= 20)
          return (
            <span className="text-[var(--positive)]">{maximoAlcanzado()}</span>
          );
        if (r.remainingPoints == null)
          return <span className="text-[var(--muted)]">{sinReferencia()}</span>;
        return (
          <span className="whitespace-nowrap tabular-nums">
            {t("entrenamiento.pts", "{{n}} pts", {
              n: decimal(r.remainingPoints, 1),
            })}
            <span className="text-xs text-[var(--muted)]">
              {" "}
              · {skillLevelLabel(r.level + 1)} ({r.level + 1})
            </span>
          </span>
        );
      },
    },
    columnaUltimaMejora<TrainingExperienceRow>(),
    {
      key: "matchCounts",
      header: t("entrenamiento.evidencia", "Evidencia"),
      align: "left",
      value: (r) =>
        Object.values(r.matchCounts).reduce(
          (sum, matches) => sum + matches,
          0,
        ) + r.unscoredNationalMatches,
      render: (r) => {
        const parts = Object.entries(r.matchCounts)
          .filter(([, matches]) => matches > 0)
          .map(
            ([kind, matches]) =>
              `${t(`entrenamiento.tipoPartido.${kind}`, EXPERIENCE_TYPE_LABELS[kind] ?? kind)}: ${partidos(matches)}`,
          );
        if (r.unscoredNationalMatches > 0) {
          parts.push(
            t(
              "entrenamiento.seleccionSinPuntaje",
              "Selección sin puntaje: {{partidos}}",
              { partidos: partidos(r.unscoredNationalMatches) },
            ),
          );
        }
        return parts.length > 0 ? (
          <span className="text-xs text-[var(--muted)]">
            {parts.join(" · ")}
          </span>
        ) : (
          <span className="text-xs text-[var(--muted)]">
            {t(
              "entrenamiento.sinPartidosObservados",
              "Aún sin partidos observados",
            )}
          </span>
        );
      },
    },
    columnaPlayerId<TrainingExperienceRow>(),
  ];
}

function loyaltyColumns(): Column<TrainingLoyaltyRow>[] {
  return [
    ...columnasDeJugador<TrainingLoyaltyRow>(),
    {
      key: "level",
      header: t("entrenamiento.nivelActual", "Nivel actual"),
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
      header: t("entrenamiento.progreso", "Progreso"),
      value: (r) => r.progressPct ?? -1,
      render: (r) => <ProgressCell value={r.progressPct} digits={2} />,
    },
    {
      key: "accumulated",
      header: t("entrenamiento.acumulado", "Acumulado / meta"),
      value: (r) => r.daysInClub ?? -1,
      render: (r) => {
        if (r.daysInClub == null)
          return <span className="text-[var(--muted)]">{sinReferencia()}</span>;
        if (r.daysToNextLevel == null) {
          return (
            <span className="whitespace-nowrap tabular-nums">
              {t("entrenamiento.diasMaximo", "{{n}} días · máximo", {
                n: number(r.daysInClub),
              })}
            </span>
          );
        }
        return (
          <span className="whitespace-nowrap tabular-nums">
            {number(r.daysInClub)}{" "}
            <span className="text-[var(--muted)]">
              / {dias(r.daysInClub + r.daysToNextLevel)}
            </span>
          </span>
        );
      },
    },
    {
      key: "remaining",
      header: t("entrenamiento.falta", "Falta / próximo nivel"),
      value: (r) => r.daysToNextLevel ?? Number.MAX_SAFE_INTEGER,
      render: (r) => {
        if (r.daysInClub == null)
          return <span className="text-[var(--muted)]">{sinReferencia()}</span>;
        if (r.nextLevel == null)
          return (
            <span className="text-[var(--positive)]">{maximoAlcanzado()}</span>
          );
        if (r.daysToNextLevel == null)
          return <span className="text-[var(--muted)]">{sinReferencia()}</span>;
        return (
          <span className="whitespace-nowrap">
            {dias(r.daysToNextLevel)}
            <span className="text-xs text-[var(--muted)]">
              {" "}
              · {skillLevelLabel(r.nextLevel)} ({r.nextLevel})
            </span>
          </span>
        );
      },
    },
    columnaUltimaMejora<TrainingLoyaltyRow>(),
    {
      key: "source",
      header: t("entrenamiento.evidencia", "Evidencia"),
      align: "left",
      value: (r) => r.daysInClub ?? -1,
      render: (r) => (
        <span className="text-xs text-[var(--muted)]">
          {r.daysInClub == null
            ? t("entrenamiento.sinFechaCompra", "Sin fecha de compra")
            : t("entrenamiento.diasDesdeCompra", "{{n}} días desde compra", {
                n: number(r.daysInClub),
              })}
        </span>
      ),
    },
    columnaPlayerId<TrainingLoyaltyRow>(),
  ];
}

function staminaColumns(): Column<TrainingStaminaRow>[] {
  return [
    ...columnasDeJugador<TrainingStaminaRow>(),
    {
      key: "level",
      header: t("entrenamiento.nivelActual", "Nivel actual"),
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
      header: t("entrenamiento.actualGuia", "Actual → guía"),
      value: (r) => r.expectedLevel ?? r.level,
      render: (r) => <StaminaProgressCell row={r} />,
    },
    {
      key: "effectiveTrainingPct",
      header: t("entrenamiento.pctAplicado", "% aplicado"),
      value: (r) => r.effectiveTrainingPct,
      render: (r) => (
        <span className="tabular-nums">
          {decimal(r.effectiveTrainingPct, 1)}%
        </span>
      ),
    },
    {
      key: "expectedLevel",
      header: t("entrenamiento.esperadoOcerin", "Esperado Ocerin"),
      value: (r) => r.expectedLevel ?? -1,
      render: (r) =>
        r.expectedLevel == null ? (
          <span className="text-[var(--muted)]">
            {t("comun.sinDato", "Sin dato")}
          </span>
        ) : (
          <span className="whitespace-nowrap">
            <span>{r.expectedLevelName}</span>{" "}
            <span className="text-xs tabular-nums text-[var(--muted)]">
              ({r.expectedLevel})
            </span>
          </span>
        ),
    },
    // Condición no tiene columna de Evidencia, así que va detrás del
    // progreso, que es su equivalente.
    columnaUltimaMejora<TrainingStaminaRow>(),
    columnaPlayerId<TrainingStaminaRow>(),
  ];
}

function weeklyLogColumns(): Column<TrainingSquadWeeklyLogEntry>[] {
  return [
    {
      key: "seasonWeek",
      header: t("entrenamiento.ttss", "TT-ss"),
      align: "left",
      value: (r) => r.seasonWeek ?? "",
    },
    {
      key: "date",
      header: t("entrenamiento.fecha", "Fecha"),
      align: "left",
      value: (r) => r.date,
    },
    {
      key: "trainingType",
      header: t("club.tipo", "Tipo"),
      align: "left",
      value: (r) => r.trainingType,
    },
    {
      key: "intensity",
      header: t("entrenamiento.intensidad", "Intensidad"),
      value: (r) => r.intensity,
      render: (r) => `${r.intensity}%`,
    },
    {
      key: "staminaShare",
      header: t("flor.resistencia", "Resistencia"),
      value: (r) => r.staminaShare,
      render: (r) => `${r.staminaShare}%`,
    },
    {
      key: "trainerName",
      header: t("entrenamiento.entrenador", "Entrenador"),
      align: "left",
      value: (r) => r.trainerName,
    },
  ];
}

function confirmedColumns(): Column<ConfirmedLevelUp>[] {
  return [
    {
      key: "seasonWeek",
      header: t("entrenamiento.ttss", "TT-ss"),
      align: "left",
      value: (r) => r.seasonWeek,
    },
    {
      key: "change",
      header: t("entrenamiento.subida", "Subida"),
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
      header: t("entrenamiento.semanas", "Semanas"),
      value: (r) => r.weeksBetween ?? -1,
      render: (r) =>
        r.weeksBetween == null ? (
          <span className="text-[var(--muted)]">
            {t("entrenamiento.primeraRegistrada", "primera registrada")}
          </span>
        ) : (
          semanas(r.weeksBetween)
        ),
    },
  ];
}

function forecastColumns(): Column<LevelForecastMilestone>[] {
  return [
    {
      key: "level",
      header: t("club.nivel", "Nivel"),
      value: (r) => r.level,
      render: (r) => `${r.level} · ${r.levelName}`,
    },
    {
      key: "weeksFor",
      header: t("entrenamiento.semanasNivel", "Semanas de este nivel"),
      value: (r) => r.weeksForThisLevel,
      render: (r) => r.weeksForThisLevel.toFixed(1),
    },
    {
      key: "cumulative",
      header: t("entrenamiento.semanasHoy", "Semanas desde hoy"),
      value: (r) => r.weeksFromNow,
      render: (r) => r.weeksFromNow.toFixed(1),
    },
    {
      key: "seasonWeek",
      header: t("entrenamiento.ttssEstimada", "TT-ss estimada"),
      align: "left",
      value: (r) => r.seasonWeek ?? "",
    },
    {
      key: "age",
      header: t("entrenamiento.edadProyectada", "Edad proyectada"),
      value: (r) => edadOrdenable(r.age),
      render: (r) => htAgeTexto(r.age),
    },
  ];
}

function optionColumns(): Column<PostMatchTrainingOption>[] {
  return [
    {
      key: "name",
      header: t("nav.entrenamiento", "Entrenamiento"),
      align: "left",
      value: (r) => r.name,
      render: (r) => (
        <span className={r.recommendable ? "" : "text-[var(--muted)]"}>
          {r.name}
          {!r.recommendable &&
            ` · ${t("entrenamiento.referencia", "referencia")}`}
        </span>
      ),
    },
    {
      // Lo que ordena desde el 2026-09-13: cuánto sube, por semana, el mejor
      // aporte posicional de la plantilla. Sustituye a «Score», que contaba
      // subidas y minutos y ponía primero a Balón parado.
      key: "value",
      header: t("entrenamiento.aporteSem", "Aporte/sem"),
      value: (r) => r.value,
      render: (r) => (
        <span
          title={t(
            "entrenamiento.aporteSemTitle",
            "cuánto sube por semana el mejor aporte posicional de la plantilla",
          )}
        >
          +{r.value.toFixed(2)}
        </span>
      ),
    },
    {
      key: "minutes",
      header: t("entrenamiento.minEquivalentes", "Min. equivalentes"),
      value: (r) => r.equivalentMinutes,
    },
    {
      key: "players",
      header: t("nav.jugadores", "Jugadores"),
      value: (r) => r.trainedPlayers,
    },
    { key: "full", header: "Full", value: (r) => r.fullTrainingPlayers },
    {
      key: "pops",
      header: t("entrenamiento.popsPronto", "Pops <=3s"),
      value: (r) => r.popsSoon,
    },
  ];
}

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

/**
 * El parte de la última actualización semanal (2026-09-19, pedido del usuario).
 *
 * Lo que contesta es «qué pasó el último martes»: cuándo fue exactamente, con
 * qué entrenamiento puesto y quién subió. El cuándo no se estima: Hattrick
 * publica la hora de la actualización de cada liga.
 *
 * Y distingue dos silencios que se parecen mucho: que no subiera nadie, y que
 * todavía no hayas sincronizado desde entonces. Decir «no subió nadie» cuando
 * lo que pasa es que nadie ha mirado sería mentir con datos.
 */
function ParteDelUltimoEntrenamiento({ activa }: { activa: boolean }) {
  const { t } = useTranslation();
  const { data, isLoading, isError, error } = useUltimoEntrenamiento(activa);
  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const cuando = data.at ? dateTime(data.at) : null;
  const ajustes = [
    data.intensity != null
      ? t("entrenamiento.intensidadDe", "intensidad {{v}}%", {
          v: data.intensity,
        })
      : null,
    data.staminaShare != null
      ? t("entrenamiento.resistenciaDe", "resistencia {{v}}%", {
          v: data.staminaShare,
        })
      : null,
    data.trainerName,
  ]
    .filter(Boolean)
    .join(" · ");

  // La cifra grande es la noticia de la semana: cuántos SUBIERON. Con los
  // datos sin actualizar no hay cifra que dar, y poner un cero seria afirmar
  // que no subio nadie.
  //
  // Las bajadas van aparte y no se suman: el mismo fichero de Hattrick
  // reporta las dos cosas --la Resistencia se cae sola cuando el
  // entrenamiento va por otro lado-- y contarlas juntas convertia un mal
  // resultado en una buena noticia (2026-09-19, visto con datos reales).
  const cifra = data.pendingSync ? "?" : String(data.upCount);
  const pie = data.pendingSync
    ? t(
        "entrenamiento.ultimoSinSincronizar",
        "Tus datos llegan hasta el {{fecha}}, antes de este entrenamiento. Sincroniza para ver quién subió.",
        { fecha: data.dataAt ? date(data.dataAt) : "?" },
      )
    : data.upCount === 0 && data.downCount === 0
      ? [
          t("entrenamiento.ultimoSinSubidas", "No subió nadie."),
          data.lastWithUps
            ? t(
                "entrenamiento.ultimaConSubidas",
                "La última vez que alguien subió fue en {{semana}}.",
                { semana: data.lastWithUps },
              )
            : null,
        ]
          .filter(Boolean)
          .join(" ")
      : [
          data.upCount === 1
            ? t("entrenamiento.subioUno", "Subió un jugador.")
            : t("entrenamiento.subieronN", "Subieron {{n}} jugadores.", {
                n: data.upCount,
              }),
          data.downCount === 1
            ? t("entrenamiento.bajoUno", "A uno se le cayó una habilidad.")
            : data.downCount > 1
              ? t(
                  "entrenamiento.bajaronN",
                  "A {{n}} se les cayó alguna habilidad.",
                  { n: data.downCount },
                )
              : null,
        ]
          .filter(Boolean)
          .join(" ");

  return (
    <Panel
      title={t("entrenamiento.ultimo", "Último entrenamiento")}
      meta={
        cuando
          ? `${cuando}${data.seasonWeek ? ` · ${data.seasonWeek}` : ""}`
          : t("entrenamiento.sinHora", "sin la hora de esta liga todavía")
      }
    >
      {/* La cabecera responde de un vistazo las dos preguntas de la semana:
          cuántos subieron y con qué entrenamiento puesto. Antes eran dos
          renglones grises y había que leerlos para enterarse de algo. */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-baseline gap-2">
          <span
            className={clsx(
              "text-4xl font-semibold leading-none tabular-nums",
              data.pendingSync
                ? "text-[var(--muted)]"
                : data.upCount > 0
                  ? "text-[var(--positive)]"
                  : "text-[var(--text)]",
            )}
          >
            {cifra}
          </span>
          <span className="text-xs uppercase tracking-wide text-[var(--muted)]">
            {data.upCount === 1
              ? t("entrenamiento.subida", "subida")
              : t("entrenamiento.subidas", "subidas")}
          </span>
        </div>
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">
            {data.trainingType ??
              t("entrenamiento.sinTipo", "entrenamiento sin identificar")}
          </div>
          {ajustes && (
            <div className="truncate text-xs text-[var(--muted)]">
              {ajustes}
            </div>
          )}
        </div>
      </div>

      <div className="border-b border-[var(--border)] px-4 py-2 text-sm">
        {pie}{" "}
        {data.pendingSync && (
          <Link to="/sync" className="text-[var(--accent)] hover:underline">
            {t("entrenamiento.irASincronizar", "ir a sincronizar")}
          </Link>
        )}
      </div>

      {data.ups.length > 0 && (
        <ul className="divide-y divide-[var(--border)]">
          {data.ups.map((u) => (
            <li
              key={`${u.htPlayerId}-${u.skill}-${u.toLevel}`}
              className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 px-4 py-2.5 text-sm"
            >
              <span className="flex items-baseline gap-2">
                <span
                  className={
                    u.delta > 0
                      ? "text-[var(--positive)]"
                      : "text-[var(--danger)]"
                  }
                >
                  {u.delta > 0 ? "▲" : "▼"}
                </span>
                <PlayerLink htPlayerId={u.htPlayerId} name={u.name} />
              </span>
              <span className="flex items-baseline gap-2 text-xs">
                <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 text-[var(--muted)]">
                  {u.skillLabel}
                </span>
                <span className="text-[var(--muted)]">
                  {skillLevelLabel(u.fromLevel)}
                </span>
                <span className="text-[var(--muted)]">→</span>
                <span
                  className={clsx(
                    "font-medium",
                    u.delta > 0
                      ? "text-[var(--positive)]"
                      : "text-[var(--danger)]",
                  )}
                >
                  {skillLevelLabel(u.toLevel)}
                </span>
                <span className="tabular-nums text-[var(--muted)]">
                  ({u.toLevel})
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {/* Mirar sólo hacia atrás no invita a volver: aquí está con qué
          comparar y cuándo toca el siguiente. */}
      <Note>
        {data.previousSeasonWeek &&
          t(
            "entrenamiento.ultimoAnterior",
            "La actualización anterior ({{semana}}, {{fecha}}) dejó {{n}} subidas confirmadas.",
            {
              semana: data.previousSeasonWeek,
              fecha: data.previousAt ? date(data.previousAt) : "?",
              n: data.previousUps,
            },
          )}{" "}
        {data.nextAt &&
          t("entrenamiento.proximo", "El próximo, el {{fecha}}.", {
            fecha: dateTime(data.nextAt),
          })}
      </Note>
    </Panel>
  );
}

export function TrainingPage() {
  const { t } = useTranslation();
  // Abre en «Entrenamiento actual», no en «Datos Entrenamiento». Hasta el
  // 2026-08-30 la pestaña de entrada era la de la configuración --entrenador,
  // asistentes, intensidad--, que describe el AJUSTE y no el resultado: quien
  // entraba a esta pantalla a ver cómo va su plantilla aterrizaba en la ficha
  // del cuerpo técnico y tenía que dar un clic más. Es el mismo arreglo que se
  // le hizo a Cambios: primero la respuesta, la instrumentación al final.
  const [section, setSection] = useState<TrainingSection>("plantilla");
  const [selectedSkill, setSelectedSkill] = useState<string | null>(null);
  const [includeThisWeek, setIncludeThisWeek] = useState(true);
  // Veteranos sin habilidades de campo: fuera por defecto (2026-09-13).
  const [mostrarVeteranos, setMostrarVeteranos] = useState(false);
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
  if (!data)
    return (
      <Empty>
        {t("entrenamiento.sincroniza", "Sincroniza para ver el entrenamiento.")}
      </Empty>
    );

  const recommendation = post?.recommendation ?? null;

  // La opción que de verdad se puso, buscada entre las comparables por su
  // tipo. Puede no estar: hay entrenamientos que el motor no puntúa.
  const actual =
    post?.options.find(
      (o) => o.trainingType === post?.currentTraining?.trainingType,
    ) ?? null;
  // El puesto se calcula ORDENANDO, no con la posición en el array: la lista
  // no llega ordenada y el número salía distinto del que enseña la tabla.
  //
  // Y se cuenta sólo entre las elegibles: las marcadas «referencia» son
  // entrenamientos obsoletos que Hattrick ya no deja poner, así que ocupar un
  // puesto del ranking con ellas hace parecer peor una decisión que no lo era.
  const elegibles = (post?.options ?? [])
    .filter((o) => o.recommendable)
    .slice()
    // Mismo orden que el servidor desde el 2026-09-13: aporte, y la
    // puntuación vieja sólo para desempatar.
    .sort((a, b) => b.value - a.value || b.score - a.score);
  const puestoActual = actual
    ? elegibles.findIndex((o) => o === actual) + 1
    : null;
  const acerto =
    !!actual &&
    !!recommendation &&
    actual.trainingType === recommendation.trainingType;
  const aportePerdido =
    actual && recommendation ? recommendation.value - actual.value : null;
  const minutosPerdidos =
    actual && recommendation
      ? recommendation.equivalentMinutes - actual.equivalentMinutes
      : null;
  const sinDato = t("comun.sinDato", "Sin dato");
  const currentName =
    post?.currentTraining?.name ?? t("club.sinDatoMin", "sin dato");
  const staff = club.data?.staff ?? null;
  const assistantRole =
    staff?.roles.find((role) => role.key === "assistant_trainer_levels") ??
    null;
  const trainerName = data.weeklyLog[0]?.trainerName || sinDato;
  const trainerSpeed = staff
    ? trainerTrainingSpeedPct(staff.trainer.skillLevel)
    : null;
  const veteranos = data.players.filter((r) => r.withoutFieldSkills).length;
  const tituloActual = t("entrenamiento.actual", "Entrenamiento actual");

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">
          {t("nav.entrenamiento", "Entrenamiento")}
        </h1>
        <p className="text-sm text-[var(--muted)]">
          {t(
            "entrenamiento.cabecera",
            "Entrenamiento actual: {{actual}} · viendo {{habilidad}}",
            { actual: currentName, habilidad: data.skillLabel },
          )}
        </p>
        <EnlaceATransparencia
          seccion="entrenamiento"
          calculo="semanas-al-pop"
        />
      </header>

      <Tabs
        grupo="entrenamiento"
        tabs={[
          { key: "plantilla", label: tituloActual },
          {
            key: "ultimo",
            label: t("entrenamiento.ultimo", "Último entrenamiento"),
          },
          {
            key: "experiencia",
            label: t("abrev.largo.experience", "Experiencia"),
          },
          { key: "fidelidad", label: t("abrev.largo.loyalty", "Fidelidad") },
          { key: "condicion", label: t("flor.resistencia", "Resistencia") },
          {
            key: "posteriori",
            label: t("entrenamiento.aPosteriori", "A posteriori"),
          },
          {
            key: "datos",
            label: t("entrenamiento.datos", "Datos Entrenamiento"),
          },
        ]}
        active={section}
        onChange={setSection}
      />

      <PanelDePestanas
        grupo="entrenamiento"
        activa={section}
        className="space-y-4"
      >
        {section === "ultimo" && (
          <ParteDelUltimoEntrenamiento activa={section === "ultimo"} />
        )}

        {section === "datos" && (
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3 [&>*]:min-w-0">
              <Kpi
                label={t("nav.entrenamiento", "Entrenamiento")}
                value={currentName}
              />
              <Kpi
                label={t(
                  "entrenamiento.pctEntrenamiento",
                  "% de entrenamiento",
                )}
                value={`${data.setup.intensity}%`}
              />
              <Kpi
                label={t("entrenamiento.pctResistencia", "% resistencia")}
                value={`${data.setup.staminaShare}%`}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(18rem,0.72fr)_minmax(0,1.5fr)] [&>*]:min-w-0">
              <Panel
                title={t("entrenamiento.entrenador", "Entrenador")}
                meta={t("entrenamiento.leidoHattrick", "leído de Hattrick")}
              >
                {club.isLoading ? (
                  <Loading />
                ) : (
                  <dl className="space-y-3 p-4 text-sm">
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--muted)]">
                        {t("entrenamiento.nombre", "Nombre")}
                      </dt>
                      <dd className="text-right font-medium">{trainerName}</dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--muted)]">
                        {t(
                          "entrenamiento.nivelEntrenador",
                          "Nivel de entrenador",
                        )}
                      </dt>
                      <dd
                        className={`font-semibold tabular-nums ${trainingStaffLevelColor(staff?.trainer.skillLevel)}`}
                      >
                        {staff ? `${staff.trainer.skillLevel}/5` : sinDato}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-4">
                      <dt className="text-[var(--muted)]">
                        {t(
                          "entrenamiento.nivelLiderazgo",
                          "Nivel de liderazgo",
                        )}
                      </dt>
                      <dd>
                        {staff
                          ? `${skillLevelLabel(staff.trainer.leadership, true)} (${staff.trainer.leadership})`
                          : sinDato}
                      </dd>
                    </div>
                    <div className="flex justify-between gap-4 border-t border-[var(--border)] pt-3">
                      <dt className="text-[var(--muted)]">
                        {t("club.velocidad", "Velocidad de entrenamiento")}
                      </dt>
                      <dd className="tabular-nums font-medium text-[var(--positive)]">
                        {trainerSpeed == null ? sinDato : `${trainerSpeed}%`}
                      </dd>
                    </div>
                  </dl>
                )}
              </Panel>

              <Panel
                title={t(
                  "entrenamiento.asistentesTitulo",
                  "Asistentes de entrenador",
                )}
                meta={
                  assistantRole
                    ? t(
                        "entrenamiento.asistentesMeta",
                        "{{n}} asistente(s) · nivel combinado {{nivel}}",
                        {
                          n: assistantRole.members.length,
                          nivel: assistantRole.level,
                        },
                      )
                    : t("entrenamiento.sinSincronizar", "sin sincronizar")
                }
              >
                {club.isLoading ? (
                  <Loading />
                ) : club.isError ? (
                  <Note>
                    {t(
                      "entrenamiento.errorStaff",
                      "No pudimos cargar el cuerpo técnico.",
                    )}
                  </Note>
                ) : assistantRole ? (
                  <AssistantCards role={assistantRole} />
                ) : (
                  <Note>
                    {t(
                      "entrenamiento.sinDatosAsistentes",
                      "Sin datos de asistentes. Sincroniza para traerlos.",
                    )}
                  </Note>
                )}
              </Panel>
            </div>
          </div>
        )}

        {section === "plantilla" && (
          <>
            <Panel
              title={tituloActual}
              meta={t(
                "entrenamiento.plantillaMeta",
                "{{n}} jugadores actuales · ordenados por progreso",
                { n: data.players.length },
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-4 py-3">
                <span className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                  {t("entrenamiento.configVista", "Configuración de la vista")}
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-sm">
                    <span className="text-[var(--muted)]">
                      {t("entrenamiento.habilidad", "Habilidad")}
                    </span>
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
                    {t(
                      "entrenamiento.incluirSemana",
                      "Incluir los partidos de esta semana",
                    )}
                  </label>
                  {veteranos > 0 && (
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={mostrarVeteranos}
                        onChange={(e) => setMostrarVeteranos(e.target.checked)}
                      />
                      {t(
                        "posiciones.mostrarTodos",
                        "Mostrar a todos ({{n}} veteranos sin habilidades de campo)",
                        { n: veteranos },
                      )}
                    </label>
                  )}
                </div>
              </div>

              <DataTable
                rows={
                  mostrarVeteranos
                    ? data.players
                    : data.players.filter((r) => !r.withoutFieldSkills)
                }
                columns={squadColumns()}
                rowKey={(r) => r.htPlayerId}
                initialSort="progress"
                csvName="entrenamiento-plantilla"
                selectedRowKey={selectedPlayerId}
                onRowClick={(r) => setSelectedPlayerId(r.htPlayerId)}
                emptyMessage={t(
                  "posiciones.vacia",
                  "Sin jugadores en la plantilla.",
                )}
              />
            </Panel>
            {data.notes.length > 0 && <Note>{data.notes.join(" ")}</Note>}

            {data.weeklyLog.length > 0 && (
              <Panel
                title={t(
                  "entrenamiento.historialConfig",
                  "Historial de configuración semanal",
                )}
                meta={t(
                  "entrenamiento.historialMeta",
                  "{{n}} cambio(s) aplicados en la actualización",
                  { n: data.weeklyLog.length },
                )}
              >
                <DataTable
                  emptyMessage={t(
                    "entrenamiento.sinSemanas",
                    "Sin semanas de entrenamiento registradas todavía.",
                  )}
                  rows={data.weeklyLog}
                  columns={weeklyLogColumns()}
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
                    {t(
                      "entrenamiento.contraste",
                      "Contraste con pops reales: diferencia media de",
                    )}{" "}
                    <b className="text-[var(--text)]">
                      {validation.meanErrorWeeks == null
                        ? "-"
                        : semanas(validation.meanErrorWeeks)}
                    </b>{" "}
                    {t(
                      "entrenamiento.sobreSubidas",
                      "sobre {{n}} subida(s) confirmada(s) de {{habilidad}}.",
                      {
                        n: validation.observations,
                        habilidad: formula.data?.trainedSkill,
                      },
                    )}
                  </>
                ) : (
                  <>
                    {t(
                      "entrenamiento.sinDosSubidas",
                      "Todavía no hay dos subidas seguidas de {{habilidad}} para contrastar la fórmula.",
                      { habilidad: formula.data?.trainedSkill },
                    )}
                  </>
                )}{" "}
                <Link
                  to="/engine"
                  className="underline hover:text-[var(--text)]"
                >
                  {t("entrenamiento.verMotor", "ver el detalle en Motor")}
                </Link>
                .
              </div>
            )}

            {selectedPlayerId != null && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-semibold">
                    {playerLevels.data?.name ??
                      t("comun.cargando", "Cargando…")}
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
                    {t("entrenamiento.cerrar", "Cerrar")}
                  </button>
                </div>

                <Tabs
                  grupo="jugador-entrenamiento"
                  label={t("entrenamiento.vistasJugador", "Vistas del jugador")}
                  tabs={[
                    {
                      key: "mejoras",
                      label: t("entrenamiento.mejoras", "Mejoras"),
                    },
                    {
                      key: "prevision",
                      label: t("entrenamiento.prevision", "Previsión subidas"),
                    },
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
                        title={t(
                          "entrenamiento.subidasConfirmadas",
                          "Subidas confirmadas",
                        )}
                        meta={t(
                          "entrenamiento.confirmadasHattrick",
                          "confirmadas por Hattrick",
                        )}
                      >
                        {playerLevels.data.confirmed.length === 0 && (
                          <Empty>
                            {playerLevels.data.notes.join(" ") ||
                              t(
                                "entrenamiento.sinConfirmadas",
                                "Sin subidas confirmadas todavía.",
                              )}
                          </Empty>
                        )}
                      </Panel>
                      {playerLevels.data.confirmed.length > 0 && (
                        <DataTable
                          emptyMessage={t(
                            "entrenamiento.ningunaConfirmada",
                            "Ninguna subida confirmada todavía.",
                          )}
                          rows={playerLevels.data.confirmed}
                          columns={confirmedColumns()}
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
                      title={t(
                        "entrenamiento.previsionTitulo",
                        "Previsión de subidas",
                      )}
                      meta={t(
                        "entrenamiento.previsionMeta",
                        "hasta nivel 20 · {{n}} nivel(es)",
                        { n: playerLevels.data.forecast.length },
                      )}
                    >
                      <DataTable
                        emptyMessage={t(
                          "entrenamiento.sinPrevision",
                          "Sin previsión: hace falta al menos una semana entrenada.",
                        )}
                        rows={playerLevels.data.forecast}
                        columns={forecastColumns()}
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
                  title={t("abrev.largo.experience", "Experiencia")}
                  meta={t(
                    "entrenamiento.experienciaMeta",
                    "{{n}} jugadores · partidos y minutos reales",
                    { n: development.data.experience.length },
                  )}
                >
                  <DataTable
                    rows={development.data.experience}
                    columns={experienceColumns()}
                    rowKey={(r) => r.htPlayerId}
                    initialSort="progress"
                    csvName="entrenamiento-experiencia"
                    emptyMessage={t(
                      "entrenamiento.sinExperiencia",
                      "Sin jugadores para calcular experiencia.",
                    )}
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
                  title={t("abrev.largo.loyalty", "Fidelidad")}
                  meta={t(
                    "entrenamiento.fidelidadMeta",
                    "{{n}} jugadores · antigüedad real en el club",
                    { n: development.data.loyalty.length },
                  )}
                >
                  <DataTable
                    rows={development.data.loyalty}
                    columns={loyaltyColumns()}
                    rowKey={(r) => r.htPlayerId}
                    initialSort="progress"
                    csvName="entrenamiento-fidelidad"
                    emptyMessage={t(
                      "entrenamiento.sinFidelidad",
                      "Sin jugadores para calcular fidelidad.",
                    )}
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
                  title={t("flor.resistencia", "Resistencia")}
                  meta={
                    <span className="flex items-center gap-2">
                      {t(
                        "entrenamiento.resistenciaMeta",
                        "{{n}} jugadores · {{pct}}% efectivo · guía Ocerin",
                        {
                          n: development.data.stamina.length,
                          pct: decimal(
                            development.data.stamina[0]?.effectiveTrainingPct ??
                              0,
                            1,
                          ),
                        },
                      )}
                      <EnlaceATransparencia
                        seccion="entrenamiento"
                        calculo="condicion"
                      />
                    </span>
                  }
                >
                  <DataTable
                    rows={development.data.stamina}
                    columns={staminaColumns()}
                    rowKey={(r) => r.htPlayerId}
                    initialSort="level"
                    csvName="entrenamiento-resistencia"
                    emptyMessage={t(
                      "entrenamiento.sinResistencia",
                      "Sin jugadores para calcular resistencia.",
                    )}
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
            {/* Los tres indicadores COMPARAN. Antes describían los tres la
                misma opción --la recomendada-- y lo que costó la elección real
                había que sacarlo restando a mano en la tabla de abajo. La
                pregunta de esta pestaña no es «cuál era la mejor» sino «cuánto
                me costó no haberla puesto» (2026-09-02). */}
            <div className="grid gap-4 sm:grid-cols-3 [&>*]:min-w-0">
              <Kpi
                label={t("entrenamiento.pusiste", "Pusiste")}
                value={currentName}
                hint={
                  actual
                    ? t(
                        "entrenamiento.pusisteHint",
                        "+{{aporte}} de aporte/sem · {{min}} min · {{puesto}}.º de {{total}}",
                        {
                          aporte: actual.value.toFixed(2),
                          min: actual.equivalentMinutes.toFixed(0),
                          puesto: puestoActual,
                          total: elegibles.length,
                        },
                      )
                    : t(
                        "entrenamiento.noComparable",
                        "no está entre las opciones comparables",
                      )
                }
              />
              <Kpi
                label={t("entrenamiento.convenia", "Convenía")}
                value={
                  recommendation?.name ??
                  t("entrenamiento.sinDatos", "Sin datos")
                }
                hint={
                  recommendation
                    ? t(
                        "entrenamiento.conveniaHint",
                        "+{{aporte}} de aporte/sem · {{min}} min",
                        {
                          aporte: recommendation.value.toFixed(2),
                          min: recommendation.equivalentMinutes.toFixed(0),
                        },
                      )
                    : t(
                        "entrenamiento.sinMinutos",
                        "sin minutos que repartir esta semana",
                      )
                }
              />
              {/* La cifra que da sentido a la pestaña: la diferencia en
                  APORTE (2026-09-13). Antes eran subidas, y una subida de
                  balón parado de 2 a 3 contaba igual que una de defensa. */}
              <Kpi
                label={
                  acerto
                    ? t("entrenamiento.acertaste", "Acertaste")
                    : t("entrenamiento.loQueCosto", "Lo que costó")
                }
                value={
                  acerto
                    ? t("habilidades.nada", "nada")
                    : aportePerdido == null
                      ? t("entrenamiento.sinComparar", "sin comparar")
                      : t(
                          "entrenamiento.aportePerdido",
                          "-{{aporte}} de aporte/sem",
                          { aporte: Math.abs(aportePerdido).toFixed(2) },
                        )
                }
                hint={
                  acerto
                    ? t(
                        "entrenamiento.eraLaMejor",
                        "era la mejor opción con los minutos ya jugados",
                      )
                    : minutosPerdidos == null
                      ? t(
                          "entrenamiento.noEntra",
                          "el entrenamiento puesto no entra en la comparación",
                        )
                      : t(
                          "entrenamiento.minPerdidos",
                          "y {{min}} min equivalentes",
                          { min: Math.abs(minutosPerdidos).toFixed(0) },
                        )
                }
                tone={
                  acerto ? "positive" : aportePerdido ? "danger" : undefined
                }
              />
            </div>

            <Panel
              title={t(
                "entrenamiento.decidido",
                "Entrenamiento decidido a posteriori",
              )}
              meta={t(
                "entrenamiento.decididoMeta",
                "elige después de ver quién jugó y dónde",
              )}
            >
              <div className="grid gap-4 p-4 lg:grid-cols-[1.4fr_1fr] [&>*]:min-w-0">
                <Chart
                  ariaLabel={t(
                    "entrenamiento.rankingAria",
                    "Ranking de entrenamientos por aporte posicional ganado por semana",
                  )}
                  height={320}
                  option={barOption(
                    post.options.slice(0, 8).map((o) => o.name),
                    post.options.slice(0, 8).map((o) => o.value),
                    t("entrenamiento.aporteSem", "Aporte/sem"),
                  )}
                />
                <div className="rounded-lg border border-[var(--border)] p-4">
                  <h3 className="text-sm font-semibold">
                    {recommendation
                      ? t(
                          "entrenamiento.mejorOpcion",
                          "Mejor opción: {{nombre}}",
                          {
                            nombre: recommendation.name,
                          },
                        )
                      : t(
                          "entrenamiento.sinRecomendacion",
                          "Sin recomendación",
                        )}
                  </h3>
                  <p className="mt-2 text-sm text-[var(--muted)]">
                    {t(
                      "entrenamiento.explicacionPosteriori",
                      "La app suma los minutos reales por posición y, para cada entrenamiento, cuánto subiría por semana el mejor aporte posicional de cada jugador. Gana el que más suma: una subida que no mejora a nadie en ningún puesto vale poco, aunque llegue rápido.",
                    )}
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
                              ? "-"
                              : semanas(p.weeksToPop.toFixed(1))}
                          </span>
                        </li>
                      ))}
                  </ul>
                </div>
              </div>
              <Note>{post.notes.join(" ")}</Note>
            </Panel>

            <DataTable
              emptyMessage={t(
                "entrenamiento.sinOpciones",
                "Sin opciones que comparar para este partido.",
              )}
              rows={post.options}
              columns={optionColumns()}
              rowKey={(r) => r.trainingType}
              initialSort="value"
              csvName="entrenamiento-a-posteriori"
              // Marca la fila del entrenamiento que pusiste: sin ella hay que
              // buscarla por el nombre entre doce.
              selectedRowKey={post.currentTraining?.trainingType ?? null}
            />
          </>
        )}
      </PanelDePestanas>
    </div>
  );
}
