import { useState } from "react";
import clsx from "clsx";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, Loading, Note, Panel } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { useSquad } from "../hooks/useTeam";
import { htAge } from "../hooks/useFormat";
import type { SquadPlayer } from "../services/api";

type RoleTab = {
  id: string;
  label: string;
  orders: { key: string; label: string }[];
};

const ROLE_TABS: RoleTab[] = [
  { id: "keeper", label: "Portero", orders: [{ key: "keeper", label: "Portero" }] },
  {
    id: "central", label: "Defensa central", orders: [
      { key: "central_defender", label: "Defensa central" },
      { key: "central_defender_towards_wing", label: "Defensa central hacia lateral" },
      { key: "central_defender_offensive", label: "Defensa central ofensivo" },
    ],
  },
  {
    id: "wingback", label: "Defensa lateral", orders: [
      { key: "wingback", label: "Lateral" },
      { key: "wingback_towards_middle", label: "Lateral hacia el medio" },
      { key: "wingback_offensive", label: "Lateral ofensivo" },
      { key: "wingback_defensive", label: "Lateral defensivo" },
    ],
  },
  {
    id: "midfield", label: "Medio", orders: [
      { key: "inner_midfield", label: "Medio" },
      { key: "inner_midfield_towards_wing", label: "Medio hacia banda" },
      { key: "inner_midfield_offensive", label: "Medio ofensivo" },
      { key: "inner_midfield_defensive", label: "Medio defensivo" },
    ],
  },
  {
    id: "winger", label: "Extremo", orders: [
      { key: "winger", label: "Extremo" },
      { key: "winger_towards_middle", label: "Extremo hacia el medio" },
      { key: "winger_offensive", label: "Extremo ofensivo" },
      { key: "winger_defensive", label: "Extremo defensivo" },
    ],
  },
  {
    id: "forward", label: "Delantero", orders: [
      { key: "forward", label: "Delantero" },
      { key: "forward_defensive", label: "Delantero defensivo" },
      { key: "forward_towards_wing", label: "Delantero hacia banda" },
    ],
  },
  {
    // 2026-08-09, pedido explícitamente: "Capitán" y "Situaciones fijas"
    // fusionados en una sola pestaña "Otros" — todas son decisiones de
    // plantilla que no son una posición de campo.
    id: "other", label: "Otros", orders: [
      { key: "captain", label: "Capitán" },
      { key: "set_piece_taker", label: "Lanzador de faltas" },
      // 2026-08-09, pedido explícitamente tras verificar la fuente: orden
      // DISTINTA de "Lanzador de faltas" (TLD) — en Hattrick real tienen
      // su propio código y fórmula (Experiencia + Anotación + Balón
      // Parado, ver positions.yaml), no son el mismo puesto.
      { key: "penalty_taker", label: "Lanzador de penaltis" },
    ],
  },
];

const SKILL_COLUMNS: [keyof SquadPlayer["skills"], string][] = [
  ["playmaking", "JU"], ["winger", "LA"], ["scoring", "AN"], ["keeper", "PO"],
  ["passing", "PA"], ["defending", "DE"], ["set_pieces", "BP"],
];

function Rating({ value }: { value: number | null | undefined }) {
  return value == null ? <span className="text-[var(--muted)]">—</span> : (
    <b className="tabular-nums text-[var(--accent)]">{value.toFixed(2)}</b>
  );
}

/**
 * Matriz de posiciones inspirada en la pestaña Posiciones de Hattrick
 * Control: una orden individual a la vez, la plantilla ordenada por su
 * resultado y las habilidades que explican la comparación en la misma fila.
 * El cálculo sigue viviendo exclusivamente en position_engine.py.
 */
export function PositionsPage() {
  const [roleId, setRoleId] = useState("central");
  const [orderKey, setOrderKey] = useState("central_defender");
  const activeTab = ROLE_TABS.find((tab) => tab.id === roleId) ?? ROLE_TABS[0]!;
  const activeOrder = activeTab.orders.find((order) => order.key === orderKey) ?? activeTab.orders[0]!;
  const squad = useSquad(activeOrder.key);

  if (squad.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (!squad.data) return null;

  const columns: Column<SquadPlayer>[] = [
    {
      key: "name", header: "Jugador", align: "left", value: (player) => player.name,
      render: (player) => <PlayerLink htPlayerId={player.htPlayerId} name={player.name} />,
    },
    { key: "age", header: "Edad", value: (player) => player.ageYears + player.ageDays / 112, render: (player) => htAge(player.ageYears, player.ageDays) },
    {
      // 2026-08-09, pedido explícitamente: renombrado de "Última semana" —
      // el backend ya filtra a partidos de los últimos 7 días (caso real,
      // Volodymyr Manakin: su LastMatch de CHPP era de hace más de un
      // año), así que "sin dato" aquí es honesto: o no hay partido
      // reciente, o no hay dato en absoluto.
      key: "lastMatch", header: "Último partido", align: "left", value: (player) => player.lastMatchRating ?? -1,
      render: (player) => player.lastMatchPosition
        ? <span className="whitespace-nowrap">{player.lastMatchPosition} <Rating value={player.lastMatchRating} /></span>
        : <span className="text-[var(--muted)]">sin dato</span>,
    },
    {
      key: "roleRating", header: `${activeOrder.label} · aporte`, align: "left", value: (player) => player.positionRating?.rating ?? -1,
      render: (player) => <span className="whitespace-nowrap">{player.positionRating?.label ?? activeOrder.label} <Rating value={player.positionRating?.rating} /></span>,
    },
    {
      key: "best", header: "Mayor aporte", align: "left", value: (player) => player.bestPosition.rating,
      render: (player) => <span className="whitespace-nowrap">{player.bestPosition.label} <Rating value={player.bestPosition.rating} /></span>,
    },
    { key: "form", header: "FO", value: (player) => player.form },
    { key: "experience", header: "EX", value: (player) => player.experience },
    { key: "stamina", header: "CO", value: (player) => player.stamina },
    ...SKILL_COLUMNS.map(([key, label]): Column<SquadPlayer> => ({ key, header: label, value: (player) => player.skills[key] ?? 0 })),
    { key: "loyalty", header: "FI", value: (player) => player.loyalty },
    { key: "leadership", header: "LI", value: (player) => player.leadership },
    { key: "tsi", header: "TSI", value: (player) => player.tsi, optional: true },
  ];

  function chooseTab(tab: RoleTab) {
    setRoleId(tab.id);
    setOrderKey(tab.orders[0]!.key);
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Posiciones</h1>
        <p className="text-sm text-[var(--muted)]">Compara toda la plantilla en una posición y orden individual.</p>
      </header>

      <nav aria-label="Familias de posición" className="flex overflow-x-auto border-b border-[var(--border)]">
        {ROLE_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => chooseTab(tab)}
            className={clsx(
              "whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
              tab.id === activeTab.id ? "border-[var(--accent)] text-[var(--text)]" : "border-transparent text-[var(--muted)] hover:text-[var(--text)]",
            )}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <Panel title="Órdenes individuales" meta={activeTab.label}>
        <div className="flex flex-wrap gap-x-6 gap-y-3 p-4">
          {activeTab.orders.map((order) => (
            <label key={order.key} className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="radio"
                name="position-order"
                checked={order.key === activeOrder.key}
                onChange={() => setOrderKey(order.key)}
                className="accent-[var(--accent)]"
              />
              {order.label}
            </label>
          ))}
        </div>
        <Note>
          El ranking se recalcula en el servidor para «{activeOrder.label}». Es un índice de aporte medio a los sectores, calculado con las matrices y factores del Manual no Escrito; no es una estrella ni el rating oficial de un partido.
        </Note>
      </Panel>

      <DataTable
        rows={squad.data.players}
        columns={columns}
        rowKey={(player) => player.htPlayerId}
        initialSort="roleRating"
        csvName={`posiciones-${activeOrder.key}`}
        filterPlaceholder="Filtrar jugador o habilidad…"
      />
    </div>
  );
}
