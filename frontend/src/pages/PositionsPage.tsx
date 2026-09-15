import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, Loading, Panel, SinDatos } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { CountryFlag } from "../components/CountryFlag";
import { useSquad } from "../hooks/useTeam";
import { htAge } from "../hooks/useFormat";
import { abreviatura } from "../utils/abreviaturas";
import type { SquadPlayer } from "../services/api";

type RoleTab = {
  id: string;
  label: string;
  orders: { key: string; label: string }[];
};

/** Los nombres en español son el texto por defecto; cada idioma los lee de
 *  `posiciones.familia.<id>` y `posiciones.orden.<key>`. */
const ROLE_TABS: RoleTab[] = [
  {
    id: "keeper",
    label: "Portero",
    orders: [{ key: "keeper", label: "Portero" }],
  },
  {
    id: "central",
    label: "Defensa Central",
    orders: [
      { key: "central_defender", label: "Defensa Central" },
      {
        key: "central_defender_towards_wing",
        label: "Defensa Central hacia Lateral",
      },
      { key: "central_defender_offensive", label: "Defensa Central Ofensivo" },
    ],
  },
  {
    id: "wingback",
    label: "Defensa Lateral",
    orders: [
      { key: "wingback", label: "Defensa Lateral" },
      { key: "wingback_towards_middle", label: "Defensa Lateral hacia Medio" },
      { key: "wingback_offensive", label: "Defensa Lateral Ofensivo" },
      { key: "wingback_defensive", label: "Defensa Lateral Defensivo" },
    ],
  },
  {
    id: "midfield",
    label: "Mediocentro",
    orders: [
      { key: "inner_midfield", label: "Mediocentro" },
      {
        key: "inner_midfield_towards_wing",
        label: "Mediocentro hacia Lateral",
      },
      { key: "inner_midfield_offensive", label: "Mediocentro Ofensivo" },
      { key: "inner_midfield_defensive", label: "Mediocentro Defensivo" },
    ],
  },
  {
    id: "winger",
    label: "Extremo",
    orders: [
      { key: "winger", label: "Extremo" },
      { key: "winger_towards_middle", label: "Extremo hacia Medio" },
      { key: "winger_offensive", label: "Extremo Ofensivo" },
      { key: "winger_defensive", label: "Extremo Defensivo" },
    ],
  },
  {
    id: "forward",
    label: "Delantero",
    orders: [
      { key: "forward", label: "Delantero" },
      { key: "forward_defensive", label: "Delantero Defensivo" },
      { key: "forward_towards_wing", label: "Delantero hacia Lateral" },
    ],
  },
  {
    // 2026-08-09, pedido explícitamente: "Capitán" y "Situaciones fijas"
    // fusionados en una sola pestaña "Otros", todas son decisiones de
    // plantilla que no son una posición de campo.
    id: "other",
    label: "Otros",
    orders: [
      { key: "captain", label: "Capitán" },
      { key: "set_piece_taker", label: "Lanzador de faltas" },
      // 2026-08-09, pedido explícitamente tras verificar la fuente: orden
      // DISTINTA de "Lanzador de faltas" (TLD), en Hattrick real tienen
      // su propio código y fórmula (Experiencia + Anotación + Balón
      // Parado, ver positions.yaml), no son el mismo puesto.
      { key: "penalty_taker", label: "Lanzador de penaltis" },
    ],
  },
];

const SKILL_COLUMNS = [
  "playmaking",
  "winger",
  "scoring",
  "keeper",
  "passing",
  "defending",
  "set_pieces",
] as const;

function Rating({ value }: { value: number | null | undefined }) {
  return value == null ? (
    <span className="text-[var(--muted)]">-</span>
  ) : (
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
  const { t } = useTranslation();
  const [roleId, setRoleId] = useState("central");
  const [orderKey, setOrderKey] = useState("central_defender");
  // Veteranos sin habilidades de campo: fuera por defecto (2026-09-13). En
  // un ranking por puesto sólo eran filas al fondo que no se alinean nunca.
  const [mostrarVeteranos, setMostrarVeteranos] = useState(false);
  const activeTab = ROLE_TABS.find((tab) => tab.id === roleId) ?? ROLE_TABS[0]!;
  const activeOrder =
    activeTab.orders.find((order) => order.key === orderKey) ??
    activeTab.orders[0]!;
  const squad = useSquad(activeOrder.key);
  const familia = (tab: RoleTab) =>
    t(`posiciones.familia.${tab.id}`, tab.label);
  const orden = (o: RoleTab["orders"][number]) =>
    t(`posiciones.orden.${o.key}`, o.label);

  if (squad.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (!squad.data) return <SinDatos />;
  const veteranos = squad.data.players.filter((p) => p.withoutFieldSkills);
  const visibles = mostrarVeteranos
    ? squad.data.players
    : squad.data.players.filter((p) => !p.withoutFieldSkills);

  const columns: Column<SquadPlayer>[] = [
    {
      key: "name",
      header: t("jugadores.jugador", "Jugador"),
      align: "left",
      value: (player) => player.name,
      render: (player) => (
        <span className="inline-flex items-center gap-2 whitespace-nowrap">
          <CountryFlag
            code={player.countryCode}
            country={player.nativeLeagueName}
          />
          <PlayerLink htPlayerId={player.htPlayerId} name={player.name} />
        </span>
      ),
    },
    {
      key: "age",
      header: t("jugadores.edad", "Edad"),
      value: (player) => player.ageYears + player.ageDays / 112,
      render: (player) => htAge(player.ageYears, player.ageDays),
    },
    {
      // 2026-08-09, pedido explícitamente: renombrado de "Última semana"
      // el backend ya filtra a partidos de los últimos 7 días (caso real,
      // Volodymyr Manakin: su LastMatch de CHPP era de hace más de un
      // año), así que "sin dato" aquí es honesto: o no hay partido
      // reciente, o no hay dato en absoluto.
      key: "lastMatch",
      header: t("posiciones.ultimoPartido", "Último partido"),
      align: "left",
      value: (player) => player.lastMatchRating ?? -1,
      render: (player) =>
        player.lastMatchPosition ? (
          <span className="whitespace-nowrap">
            {player.lastMatchPosition} <Rating value={player.lastMatchRating} />
          </span>
        ) : (
          <span className="text-[var(--muted)]">
            {t("club.sinDatoMin", "sin dato")}
          </span>
        ),
    },
    {
      key: "roleRating",
      header: t("posiciones.aporteDe", "{{orden}} · aporte", {
        orden: orden(activeOrder),
      }),
      align: "left",
      value: (player) => player.positionRating?.rating ?? -1,
      render: (player) => (
        <span className="whitespace-nowrap">
          {player.positionRating?.label ?? orden(activeOrder)}{" "}
          <Rating value={player.positionRating?.rating} />
        </span>
      ),
    },
    {
      key: "best",
      header: t("posiciones.mayorAporte", "Mayor aporte"),
      align: "left",
      value: (player) => player.bestPosition.rating,
      render: (player) => (
        <span className="whitespace-nowrap">
          {player.bestPosition.label}{" "}
          <Rating value={player.bestPosition.rating} />
        </span>
      ),
    },
    {
      key: "form",
      header: abreviatura("form"),
      value: (player) => player.form,
    },
    {
      key: "experience",
      header: abreviatura("experience"),
      value: (player) => player.experience,
    },
    {
      key: "stamina",
      header: abreviatura("stamina"),
      value: (player) => player.stamina,
    },
    ...SKILL_COLUMNS.map((key): Column<SquadPlayer> => ({
      key,
      header: abreviatura(key),
      value: (player) => player.skills[key] ?? 0,
    })),
    {
      key: "loyalty",
      header: abreviatura("loyalty"),
      value: (player) => player.loyalty,
    },
    {
      key: "leadership",
      header: abreviatura("leadership"),
      value: (player) => player.leadership,
    },
    {
      key: "tsi",
      header: "TSI",
      value: (player) => player.tsi,
      optional: true,
    },
  ];

  function chooseTab(tab: RoleTab) {
    setRoleId(tab.id);
    setOrderKey(tab.orders[0]!.key);
  }

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">
          {t("nav.posiciones", "Posiciones")}
        </h1>
        <p className="text-sm text-[var(--muted)]">
          {t(
            "posiciones.intro",
            "Compara toda la plantilla en una posición y orden individual.",
          )}
        </p>
        <EnlaceATransparencia seccion="posiciones" calculo="aporte" />
      </header>

      <nav
        aria-label={t("posiciones.familias", "Familias de posición")}
        className="flex overflow-x-auto border-b border-[var(--border)]"
      >
        {ROLE_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => chooseTab(tab)}
            className={clsx(
              "whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
              tab.id === activeTab.id
                ? "border-[var(--accent)] text-[var(--text)]"
                : "border-transparent text-[var(--muted)] hover:text-[var(--text)]",
            )}
          >
            {familia(tab)}
          </button>
        ))}
      </nav>

      <Panel
        title={t("posiciones.ordenes", "Órdenes individuales")}
        meta={familia(activeTab)}
      >
        <div className="flex flex-wrap gap-x-6 gap-y-3 p-4">
          {activeTab.orders.map((order) => (
            <label
              key={order.key}
              className="flex cursor-pointer items-center gap-2 text-sm"
            >
              <input
                type="radio"
                name="position-order"
                checked={order.key === activeOrder.key}
                onChange={() => setOrderKey(order.key)}
                className="accent-[var(--accent)]"
              />
              {orden(order)}
            </label>
          ))}
        </div>
      </Panel>

      {veteranos.length > 0 && (
        <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
          <input
            type="checkbox"
            checked={mostrarVeteranos}
            onChange={(e) => setMostrarVeteranos(e.target.checked)}
            className="accent-[var(--accent)]"
          />
          {t(
            "posiciones.mostrarTodos",
            "Mostrar a todos ({{n}} veteranos sin habilidades de campo)",
            { n: veteranos.length },
          )}
        </label>
      )}
      <DataTable
        emptyMessage={t("posiciones.vacia", "Sin jugadores en la plantilla.")}
        rows={visibles}
        columns={columns}
        rowKey={(player) => player.htPlayerId}
        initialSort="roleRating"
        csvName={`posiciones-${activeOrder.key}`}
        filterPlaceholder={t(
          "posiciones.filtrar",
          "Filtrar jugador o habilidad…",
        )}
      />
    </div>
  );
}
