import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, Loading, SinDatos } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { CountryFlag } from "../components/CountryFlag";
import { useSquad } from "../hooks/useTeam";
import { htAge } from "../hooks/useFormat";
import { abreviatura } from "../utils/abreviaturas";
import type { SquadPlayer } from "../services/api";
import { tx } from "../i18n/tx";

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
    label: tx("Portero"),
    orders: [{ key: "keeper", label: tx("Portero") }],
  },
  {
    id: "central",
    label: tx("Defensa Central"),
    orders: [
      { key: "central_defender", label: tx("Defensa Central") },
      {
        key: "central_defender_towards_wing",
        label: tx("Defensa Central hacia Lateral"),
      },
      {
        key: "central_defender_offensive",
        label: tx("Defensa Central Ofensivo"),
      },
    ],
  },
  {
    id: "wingback",
    label: tx("Defensa Lateral"),
    orders: [
      { key: "wingback", label: tx("Defensa Lateral") },
      {
        key: "wingback_towards_middle",
        label: tx("Defensa Lateral hacia Medio"),
      },
      { key: "wingback_offensive", label: tx("Defensa Lateral Ofensivo") },
      { key: "wingback_defensive", label: tx("Defensa Lateral Defensivo") },
    ],
  },
  {
    id: "midfield",
    label: tx("Mediocentro"),
    orders: [
      { key: "inner_midfield", label: tx("Mediocentro") },
      {
        key: "inner_midfield_towards_wing",
        label: tx("Mediocentro hacia Lateral"),
      },
      { key: "inner_midfield_offensive", label: tx("Mediocentro Ofensivo") },
      { key: "inner_midfield_defensive", label: tx("Mediocentro Defensivo") },
    ],
  },
  {
    id: "winger",
    label: tx("Extremo"),
    orders: [
      { key: "winger", label: tx("Extremo") },
      { key: "winger_towards_middle", label: tx("Extremo hacia Medio") },
      { key: "winger_offensive", label: tx("Extremo Ofensivo") },
      { key: "winger_defensive", label: tx("Extremo Defensivo") },
    ],
  },
  {
    id: "forward",
    label: tx("Delantero"),
    orders: [
      { key: "forward", label: tx("Delantero") },
      { key: "forward_defensive", label: tx("Delantero Defensivo") },
      { key: "forward_towards_wing", label: tx("Delantero hacia Lateral") },
    ],
  },
  {
    // 2026-08-09, pedido explícitamente: "Capitán" y "Situaciones fijas"
    // fusionados en una sola pestaña "Otros", todas son decisiones de
    // plantilla que no son una posición de campo.
    id: "other",
    label: tx("Otros"),
    orders: [
      { key: "captain", label: tx("Capitán") },
      { key: "set_piece_taker", label: tx("Lanzador de faltas") },
      // 2026-08-09, pedido explícitamente tras verificar la fuente: orden
      // DISTINTA de "Lanzador de faltas" (TLD), en Hattrick real tienen
      // su propio código y fórmula (Experiencia + Anotación + Balón
      // Parado, ver positions.yaml), no son el mismo puesto.
      { key: "penalty_taker", label: tx("Lanzador de penaltis") },
    ],
  },
];

const SELECT =
  "rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm";

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
        <p className="text-sm text-[var(--muted)]">
          {t(
            "posiciones.intro",
            "Compara toda la plantilla en una posición y orden individual.",
          )}
        </p>
        <EnlaceATransparencia seccion="posiciones" calculo="aporte" />
      </header>

      {/* DOS DESPLEGABLES, uno al lado del otro (8.1.0, 2026-11-26, decisión
          del usuario): eran una fila de pestañas por familia y otra de
          botones por orden, y dentro del módulo Puestos habrían sido tres
          filas de botones apiladas. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <span className="text-[var(--muted)]">
            {t("posiciones.posicion", "Posición")}
          </span>
          <select
            className={SELECT}
            value={activeTab.id}
            onChange={(e) => {
              const tab = ROLE_TABS.find((r) => r.id === e.target.value);
              if (tab) chooseTab(tab);
            }}
          >
            {ROLE_TABS.map((tab) => (
              <option key={tab.id} value={tab.id}>
                {familia(tab)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <span className="text-[var(--muted)]">
            {t("posiciones.ordenIndividual", "Orden individual")}
          </span>
          <select
            className={SELECT}
            value={activeOrder.key}
            onChange={(e) => setOrderKey(e.target.value)}
          >
            {activeTab.orders.map((order) => (
              <option key={order.key} value={order.key}>
                {orden(order)}
              </option>
            ))}
          </select>
        </label>
      </div>

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
