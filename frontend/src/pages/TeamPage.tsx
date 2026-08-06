import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, Loading } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { TEAM_ID, useSquad } from "../hooks/useTeam";
import { htAge, money, number, relative } from "../hooks/useFormat";
import { api, type SquadPlayer } from "../services/api";

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

function MetricCell({ value, delta }: { value: number; delta?: number }) {
  return (
    <span className="inline-flex min-w-12 flex-col text-right tabular-nums">
      <span>{number(value)}</span>
      <span className={clsx(
        "text-[10px] font-semibold",
        !delta && "text-[var(--muted)]",
        delta && delta > 0 && "text-[var(--positive)]",
        delta && delta < 0 && "text-[var(--danger)]",
      )}>
        {signed(delta) || "·"}
      </span>
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
  const valuations = useQuery({
    queryKey: ["valuations", TEAM_ID],
    queryFn: () => api.valuations(TEAM_ID),
    enabled: squad.data != null,
  });
  const valueByPlayer = useMemo(
    () => new Map((valuations.data ?? []).map((valuation) => [valuation.htPlayerId, valuation])),
    [valuations.data],
  );

  if (squad.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (!squad.data) return null;

  const data = squad.data;
  const columns: Column<SquadPlayer>[] = [
    {
      key: "name", header: "Jugador", align: "left", value: (player) => player.name,
      render: (player) => <PlayerLink htPlayerId={player.htPlayerId} name={player.name} />,
    },
    {
      key: "origin", header: "Origen", align: "left",
      value: (player) => player.nativeLeagueName ?? String(player.countryId),
      render: (player) => player.nativeLeagueName ?? <span className="text-[var(--muted)]">#{player.countryId}</span>,
      optional: true,
    },
    {
      key: "age", header: "Edad", value: (player) => player.ageYears + player.ageDays / 112,
      render: (player) => htAge(player.ageYears, player.ageDays),
    },
    {
      key: "best", header: "Mejor posición", align: "left", value: (player) => player.bestPosition.rating,
      render: (player) => <span className="whitespace-nowrap">{player.bestPosition.label} <b className="text-[var(--accent)]">{player.bestPosition.rating.toFixed(2)}</b></span>,
    },
    {
      key: "lastMatch", header: "Últ. partido", align: "left", value: (player) => player.lastMatchRating ?? -1,
      render: (player) => player.lastMatchPosition
        ? <span className="whitespace-nowrap">{player.lastMatchPosition} · <b>{player.lastMatchRating?.toFixed(1) ?? "—"}</b></span>
        : <span className="text-[var(--muted)]">—</span>,
      optional: true,
    },
    {
      key: "market", header: "Mercado", value: (player) => Number(player.isTransferListed),
      render: (player) => <span className={clsx("text-xs font-semibold", player.isTransferListed ? "text-[var(--accent)]" : "text-[var(--muted)]")}>{player.isTransferListed ? "en venta" : "—"}</span>,
    },
    { key: "form", header: "FO", value: (player) => player.form, render: (player) => <MetricCell value={player.form} delta={player.deltas.form} /> },
    { key: "experience", header: "EX", value: (player) => player.experience, render: (player) => <MetricCell value={player.experience} delta={player.deltas.experience} /> },
    { key: "stamina", header: "CO", value: (player) => player.stamina, render: (player) => <MetricCell value={player.stamina} delta={player.deltas.stamina} /> },
    ...SKILLS.map(([key, short]): Column<SquadPlayer> => ({
      key, header: short, value: (player) => player.skills[key] ?? 0,
      render: (player) => <MetricCell value={player.skills[key] ?? 0} delta={player.deltas[key]} />,
    })),
    { key: "tsi", header: "TSI", value: (player) => player.tsi, render: (player) => <MetricCell value={player.tsi} delta={player.deltas.tsi} /> },
    { key: "salary", header: "Salario", value: (player) => player.salary, render: (player) => <MetricCell value={player.salary} delta={player.deltas.salary} /> },
    {
      key: "valuation", header: "Valor estimado", value: (player) => valueByPlayer.get(player.htPlayerId)?.expectedPrice ?? -1,
      render: (player) => {
        const valuation = valueByPlayer.get(player.htPlayerId);
        return valuation ? <span title={`Estimación (${valuation.confidence})`}>{money(valuation.expectedPrice, data.currency)}</span> : <span className="text-[var(--muted)]">calculando…</span>;
      },
    },
    { key: "purchase", header: "Precio compra", value: (player) => player.purchasePrice ?? -1, render: (player) => player.purchasePrice == null ? <span className="text-[var(--muted)]">—</span> : money(player.purchasePrice, data.currency), optional: true },
    { key: "specialty", header: "Especialidad", align: "left", value: (player) => player.specialty, optional: true },
    { key: "loyalty", header: "Fidelidad", value: (player) => player.loyalty, optional: true },
    { key: "character", header: "Carácter", align: "left", value: (player) => player.agreeability, render: (player) => player.agreeabilityLabel, optional: true },
    { key: "aggressiveness", header: "Agresividad", align: "left", value: (player) => player.aggressiveness, render: (player) => player.aggressivenessLabel, optional: true },
    { key: "honesty", header: "Honestidad", align: "left", value: (player) => player.honesty, render: (player) => player.honestyLabel, optional: true },
    { key: "leadership", header: "Liderazgo", value: (player) => player.leadership, optional: true },
    { key: "trainer", header: "Entrenador", align: "left", value: (player) => player.playerTrainerSkillLevel, render: (player) => player.playerTrainerSkillLevel > 0 ? `${player.playerTrainerSkillLevel}/5 · ${TRAINER_TYPES[player.playerTrainerType] ?? "?"}` : "—", optional: true },
    { key: "leagueGoals", header: "G. liga", value: (player) => player.leagueGoals, optional: true },
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
        Variaciones basadas en cierres semanales CHPP. Referencia actual: {data.comparison.baselineCapturedAt ? relative(data.comparison.baselineCapturedAt) : "cierre semanal anterior"}. El valor estimado no es un dato oficial de Hattrick.
      </p>
    </div>
  );
}
