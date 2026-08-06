import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Column, DataTable } from "../components/DataTable";
import { Empty, ErrorState, Loading, Note, Panel } from "../components/Panels";
import { useCup, useLeague } from "../hooks/useTeam";

interface RivalRow {
  htTeamId: number;
  name: string;
  detail: string;
}

/** Orden de exhibición de las categorías — Liga primero, luego las copas en
 * el mismo orden de nivel que ya usa la página de Copa (Escalera de copas):
 * la principal primero, las de consolación después, de mayor a menor. Un
 * nombre de copa que no esté en esta lista (otro país, otro mundo) simplemente
 * se agrega al final, en el orden en que aparezca. */
const KNOWN_CUP_ORDER = [
  "Copa Colombia",
  "Copa Macarena Esmeralda",
  "Copa Cocuy Rubí",
  "Copa Tayrona Zafiro",
  "Copa Peor Es Nada",
];

/**
 * Elegir rival — punto de entrada a la ficha de scouting (`/rivals/:id`) sin
 * tener que saber de antemano el ID del equipo rival.
 *
 * CHPP no expone un listado completo de "todos los posibles rivales" por
 * competición — solo se conoce un rival de copa una vez que el cruce ya está
 * sorteado (jugado o programado). Por eso las categorías de Copa aquí abajo
 * son exactamente los rivales que tu equipo YA enfrentó o tiene programado
 * esta temporada en cada nivel — no una proyección de con quién podrías
 * cruzarte más adelante. La Liga sí es completa: los otros equipos de tu
 * serie, siempre los mismos durante toda la temporada.
 */
export function RivalPickerPage() {
  const league = useLeague();
  const cup = useCup();
  const navigate = useNavigate();
  const [manualId, setManualId] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  if (league.isLoading || cup.isLoading) return <Loading />;
  if (league.isError) return <ErrorState error={league.error} />;
  if (cup.isError) return <ErrorState error={cup.error} />;

  const leagueRows: RivalRow[] = (league.data?.standings ?? [])
    .filter((s) => !s.isOwnTeam)
    .map((s) => ({
      htTeamId: s.htTeamId,
      name: s.name,
      detail: `${s.position}º · ${s.points} pts · ${s.played} jugados`,
    }));

  const cupCandidates = new Map<string, Map<number, RivalRow>>();
  const addCupRow = (
    cupName: string | null,
    htTeamId: number,
    name: string,
    detail: string,
  ) => {
    const key = cupName ?? "Copa (nivel sin identificar)";
    if (!cupCandidates.has(key)) cupCandidates.set(key, new Map());
    // Si el mismo rival aparece dos veces en el mismo nivel (partido de ida
    // y vuelta), se queda la entrada más reciente — no se duplica la fila.
    cupCandidates.get(key)!.set(htTeamId, { htTeamId, name, detail });
  };
  for (const h of cup.data?.history ?? []) {
    addCupRow(
      h.cupName, h.opponentHtTeamId, h.opponent,
      `${h.date} · ${h.goalsFor}-${h.goalsAgainst} (${h.result})`,
    );
  }
  for (const nm of cup.data?.nextMatches ?? []) {
    addCupRow(nm.cupName, nm.opponentHtTeamId, nm.opponent, `${nm.date} · programado`);
  }

  const cupNames = [...cupCandidates.keys()].sort((a, b) => {
    const ia = KNOWN_CUP_ORDER.indexOf(a);
    const ib = KNOWN_CUP_ORDER.indexOf(b);
    if (ia === -1 && ib === -1) return 0;
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });

  const categories = [
    { key: "liga", label: "Liga", rows: leagueRows },
    ...cupNames.map((cupName) => ({
      key: cupName,
      label: cupName,
      rows: [...cupCandidates.get(cupName)!.values()],
    })),
  ].filter((c) => c.rows.length > 0);

  const active = categories.find((c) => c.key === selected) ?? categories[0] ?? null;

  const columns: Column<RivalRow>[] = [
    {
      key: "name", header: "Equipo", value: (r) => r.name,
      render: (r) => (
        <button
          onClick={() => navigate(`/rivals/${r.htTeamId}`)}
          className="text-left hover:text-[var(--accent)] hover:underline"
        >
          {r.name}
        </button>
      ),
    },
    { key: "detail", header: "Detalle", value: (r) => r.detail },
    { key: "id", header: "ID", align: "right", value: (r) => r.htTeamId, optional: true },
  ];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Elegir rival</h1>
        <p className="text-sm text-[var(--muted)]">
          Liga y copas ya cruzadas o programadas esta temporada — o salta directo con el ID.
        </p>
      </header>

      <Panel title="Ir directo por ID de equipo">
        <form
          className="flex items-center gap-2 p-4"
          onSubmit={(e) => {
            e.preventDefault();
            const id = Number(manualId);
            if (id > 0) navigate(`/rivals/${id}`);
          }}
        >
          <input
            type="number"
            value={manualId}
            onChange={(e) => setManualId(e.target.value)}
            placeholder="ID de equipo (EquipoID)"
            className="w-56 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm"
          />
          <button
            type="submit"
            className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white"
          >
            Ver scouting
          </button>
        </form>
      </Panel>

      {categories.length === 0 ? (
        <Panel title="Rivales">
          <Empty>
            Todavía no hay ningún rival de liga ni de copa sincronizado. Sincroniza tu equipo o
            usa el ID directo de arriba.
          </Empty>
        </Panel>
      ) : (
        <Panel title="Rivales por competición" meta={`${active?.rows.length ?? 0} equipo(s)`}>
          <div className="flex flex-wrap gap-1.5 border-b border-[var(--border)] p-4 pb-3">
            {categories.map((c) => (
              <button
                key={c.key}
                onClick={() => setSelected(c.key)}
                className={`rounded-md border px-3 py-1.5 text-xs ${
                  active?.key === c.key
                    ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]"
                }`}
              >
                {c.label}{" "}
                <span className="tabular-nums opacity-70">({c.rows.length})</span>
              </button>
            ))}
          </div>
          {active && (
            <DataTable
              rows={active.rows}
              columns={columns}
              rowKey={(r) => r.htTeamId}
              filterPlaceholder="Filtrar por equipo…"
              emptyMessage="Sin equipos en esta categoría."
            />
          )}
          <Note>
            Liga es la lista completa de tu serie (siempre los mismos rivales toda la temporada).
            Las copas solo muestran a quien ya enfrentaste o tienes programado enfrentar esta
            temporada en cada nivel — CHPP no revela el cruce de una ronda de copa hasta que se
            sortea, así que no hay "todos los rivales posibles" que mostrar de antemano.
          </Note>
        </Panel>
      )}
    </div>
  );
}
