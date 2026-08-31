import { useState } from "react";
import clsx from "clsx";
import { CountryCell } from "../components/CountryFlag";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, Loading, SinDatos } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Specialty } from "../components/Specialty";
import { useSquad } from "../hooks/useTeam";
import { htAge, money, number, relative } from "../hooks/useFormat";
import type { SquadPlayer } from "../services/api";

const SKILLS: [keyof SquadPlayer["skills"], string][] = [
  ["keeper", "PO"], ["defending", "DE"], ["playmaking", "JU"],
  ["winger", "LA"], ["passing", "PA"], ["scoring", "AN"], ["set_pieces", "BP"],
];

const TRAINER_TYPES: Record<number, string> = {
  0: "defensivo", 1: "ofensivo", 2: "equilibrado",
};

function signed(value: number | undefined): string {
  if (!value) return "";
  return `${value > 0 ? "+" : ""}${number(value)}`;
}

/** El valor y, pegado a su derecha, cuánto cambió desde el snapshot que se
 *  compara. Un solo renglón: el cambio es un apunte al margen del número, no
 *  otro dato que merezca su propia línea.
 *
 *  Sin cambio no se pinta nada. Antes iba un punto de relleno, que gastaba una
 *  línea en cada celda de la tabla para decir que no había noticia — y como
 *  casi ninguna habilidad se mueve entre dos sincronizaciones, la tabla entera
 *  quedaba al doble de alto para mostrar puntos. */
function MetricCell({ value, delta }: { value: number; delta?: number }) {
  return (
    <span className="inline-flex min-w-12 items-baseline justify-end gap-1 whitespace-nowrap tabular-nums">
      <span>{number(value)}</span>
      {delta ? (
        <span className={clsx(
          "text-[10px] font-semibold",
          delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]",
        )}>
          {signed(delta)}
        </span>
      ) : null}
    </span>
  );
}

function HistoryLabel({ capturedAt, snapshots }: { capturedAt: string; snapshots: number }) {
  const date = new Intl.DateTimeFormat("es-CO", {
    day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
  }).format(new Date(capturedAt));
  return `${date} · ${snapshots} jugadores`;
}

/**
 * Jugadores es la tabla maestra. La ficha, posiciones y análisis individual
 * viven en /players/:id para no convertir la vista de plantilla en un
 * dashboard de un jugador seleccionado.
 */
export function TeamPage() {
  const [comparisonSyncId, setComparisonSyncId] = useState<number | null>(null);
  const squad = useSquad(undefined, comparisonSyncId);

  if (squad.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (!squad.data) return <SinDatos />;

  const data = squad.data;
  // 2026-08-16, pedido explícito: aquí NINGUNA columna nace oculta. Es la tabla
  // maestra de la plantilla y quien la abre quiere verlo todo; el selector
  // "Columnas" sigue estando para quitar lo que estorbe. Por eso ninguna lleva
  // `optional` — que en `DataTable` significa "oculta de salida".
  const columns: Column<SquadPlayer>[] = [
    {
      key: "name", header: "Jugador", align: "left", value: (player) => player.name,
      render: (player) => <PlayerLink htPlayerId={player.htPlayerId} name={player.name} />,
    },
    {
      key: "origin", header: "Origen", align: "left",
      value: (player) => player.nativeLeagueName ?? String(player.countryId),
      render: (player) => (
        <CountryCell
          code={player.countryCode}
          country={player.nativeLeagueName}
          fallback={`#${player.countryId}`}
        />
      ),
    },
    {
      key: "best", header: "Mejor posición", align: "left", value: (player) => player.bestPosition.rating,
      render: (player) => <span className="whitespace-nowrap">{player.bestPosition.label} <b className="text-[var(--accent)]">{player.bestPosition.rating.toFixed(2)}</b></span>,
    },
    {
      key: "specialty", header: "Especialidad", align: "left",
      // `value` se queda en texto plano: es lo que ordena, lo que filtra el
      // buscador de la tabla y lo que sale al CSV. El icono vive sólo en
      // `render`, donde no puede estorbar ninguna de las tres cosas.
      value: (player) => player.specialty,
      render: (player) => <Specialty specialty={player.specialty} />,
    },
    {
      key: "lastMatch", header: "Últ. partido", align: "left", value: (player) => player.lastMatchRating ?? -1,
      render: (player) => player.lastMatchPosition
        ? <span className="whitespace-nowrap">{player.lastMatchPosition} · <b>{player.lastMatchRating?.toFixed(1) ?? "-"}</b></span>
        : <span className="text-[var(--muted)]">—</span>,
    },
    {
      key: "market", header: "Mercado", align: "left", value: (player) => Number(player.isTransferListed),
      render: (player) => <span className={clsx("text-xs font-semibold", player.isTransferListed ? "text-[var(--accent)]" : "text-[var(--muted)]")}>{player.isTransferListed ? "en venta" : "-"}</span>,
    },
    // Edad abre la banda numérica en vez de partir en dos el bloque de texto
    // de la izquierda, que era donde se producían dos de los cuatro quiebres
    // de alineación que quedaban.
    {
      key: "age", header: "Edad", value: (player) => player.ageYears + player.ageDays / 112,
      render: (player) => htAge(player.ageYears, player.ageDays),
    },
    { key: "form", header: "FO", value: (player) => player.form, render: (player) => <MetricCell value={player.form} delta={player.deltas.form} /> },
    { key: "experience", header: "EX", value: (player) => player.experience, render: (player) => <MetricCell value={player.experience} delta={player.deltas.experience} /> },
    { key: "stamina", header: "CO", value: (player) => player.stamina, render: (player) => <MetricCell value={player.stamina} delta={player.deltas.stamina} /> },
    // Fidelidad es un nivel de jugador como Forma, Experiencia o Condición, no
    // un dato de ficha: va con ellas y con su mismo código corto (el que ya usa
    // Posiciones), no perdida entre Especialidad y Carácter. Y como ellas se
    // pinta con `MetricCell`: un número pelado aquí medía 39 px contra los 72
    // de sus vecinas y le faltaba la línea del delta, así que rompía la banda.
    {
      key: "loyalty", header: "FI", value: (player) => player.loyalty,
      render: (player) => <MetricCell value={player.loyalty} delta={player.deltas.loyalty} />,
    },
    ...SKILLS.map(([key, short]): Column<SquadPlayer> => ({
      key, header: short, value: (player) => player.skills[key] ?? 0,
      render: (player) => <MetricCell value={player.skills[key] ?? 0} delta={player.deltas[key]} />,
    })),
    { key: "tsi", header: "TSI", value: (player) => player.tsi, render: (player) => <MetricCell value={player.tsi} delta={player.deltas.tsi} /> },
    // HTMS junto a TSI: las tres son la misma pregunta ("cuanto vale"),
    // solo que TSI la responde con el mercado y HTMS con las habilidades.
    { key: "htms", header: "HTMS", value: (player) => player.htms },
    { key: "htms28", header: "HTMS28", value: (player) => player.htms28 },
    { key: "salary", header: "Salario", value: (player) => player.salary, render: (player) => <MetricCell value={player.salary} delta={player.deltas.salary} /> },
    { key: "purchase", header: "Precio compra", value: (player) => player.purchasePrice ?? -1, render: (player) => player.purchasePrice == null ? <span className="text-[var(--muted)]">—</span> : money(player.purchasePrice, data.currency) },
    // Números primero y textos después, sin mezclarlos. Con las 27 columnas a
    // la vista, la cola alternaba alineación seis veces (4 textos a la
    // izquierda, Liderazgo a la derecha, Entrenador a la izquierda, G. liga a
    // la derecha) y eso es lo que hacía zigzaguear la tabla. Ahora hay una
    // sola frontera entre la banda numérica y la de texto.
    { key: "leadership", header: "Liderazgo", value: (player) => player.leadership },
    { key: "leagueGoals", header: "G. liga", value: (player) => player.leagueGoals },
    { key: "character", header: "Carácter", align: "left", value: (player) => player.agreeability, render: (player) => player.agreeabilityLabel },
    { key: "aggressiveness", header: "Agresividad", align: "left", value: (player) => player.aggressiveness, render: (player) => player.aggressivenessLabel },
    { key: "honesty", header: "Honestidad", align: "left", value: (player) => player.honesty, render: (player) => player.honestyLabel },
    { key: "trainer", header: "Entrenador", align: "left", value: (player) => player.playerTrainerSkillLevel, render: (player) => player.playerTrainerSkillLevel > 0 ? `${player.playerTrainerSkillLevel}/5 · ${TRAINER_TYPES[player.playerTrainerType] ?? "?"}` : "-" },
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Jugadores</h1>
          <p className="text-sm text-[var(--muted)]">Tabla maestra de {data.teamName}. Abre un nombre para ver sus detalles.</p>
        </div>
        <label className="text-xs text-[var(--muted)]">
          Diferencias semanales contra
          <select
            value={comparisonSyncId ?? "previous"}
            onChange={(event) => setComparisonSyncId(event.target.value === "previous" ? null : Number(event.target.value))}
            className="ml-2 rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-sm text-[var(--text)]"
          >
            <option value="previous">cierre semanal anterior</option>
            {data.history.map((entry) => <option key={entry.syncId} value={entry.syncId}>{HistoryLabel(entry)}</option>)}
          </select>
        </label>
      </header>

      <DataTable
        rows={data.players}
        columns={columns}
        rowKey={(player) => player.htPlayerId}
        initialSort="tsi"
        csvName="jugadores"
        filterPlaceholder="Filtrar por jugador, posición o habilidad…"
      />

      <p className="text-xs text-[var(--muted)]">
        Variaciones basadas en cierres semanales de Hattrick. Referencia actual: {data.comparison.baselineCapturedAt ? relative(data.comparison.baselineCapturedAt) : "cierre semanal anterior"}. El valor estimado no es un dato oficial de Hattrick.
      </p>
    </div>
  );
}
