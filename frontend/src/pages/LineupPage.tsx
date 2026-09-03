import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { api, type LineupHindsight } from "../services/api";
import { TEAM_ID, useLineup } from "../hooks/useTeam";
import {
  Empty,
  ErrorState,
  Kpi,
  Loading,
  Note,
  Panel,
} from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Chart } from "../charts/Chart";
import {
  PITCH_CARD_CLASS,
  PitchField,
  PitchGrid,
} from "../components/PitchField";
import { SplitSelector } from "../components/SplitSelector";
import { barOption } from "../charts/chartOptions";
import { number } from "../hooks/useFormat";

/** Las diez del juego, de la más defensiva a la más ofensiva. Aquí faltaban
 *  5-2-3 y 2-5-3 hasta el 2026-08-19. */
const FORMATIONS = [
  "5-5-0",
  "5-4-1",
  "5-3-2",
  "5-2-3",
  "4-5-1",
  "4-4-2",
  "4-3-3",
  "3-5-2",
  "3-4-3",
  "2-5-3",
];
export function LineupPage() {
  const [formation, setFormation] = useState("");
  // `undefined` = el reparto propio de la formación. Al cambiarla se vuelve a
  // él, porque un reparto de la anterior puede no ser legal aquí.
  const [centrales, setCentrales] = useState<number | undefined>(undefined);
  const [interiores, setInteriores] = useState<number | undefined>(undefined);
  // Órdenes individuales que el usuario fijó a mano: casilla -> posición con
  // orden. Las que no estén aquí las elige el motor dentro de la misma
  // asignación. Cambiar de formación las borra: las casillas ya no son esas.
  const [ordenes, setOrdenes] = useState<Record<number, string>>({});
  // Quién NO entra en el reparto. Se guarda el nombre junto al identificador
  // porque en cuanto sale, el servidor deja de devolverlo: sin el nombre la
  // lista de fuera serían números.
  const [fuera, setFuera] = useState<{ htPlayerId: number; player: string }[]>(
    [],
  );
  const { data, isLoading, isError, error } = useLineup(
    formation || undefined,
    centrales,
    interiores,
    ordenes,
    fuera.map((f) => f.htPlayerId),
  );

  // El once de referencia es esta misma consulta SIN exclusiones. No hace
  // falta guardarlo en un estado ni sincronizarlo con un efecto: mientras no
  // haya nadie fuera las dos consultas comparten clave, así que react-query
  // devuelve la misma entrada de caché y no se pide nada de más.
  const referencia = useLineup(
    formation || undefined,
    centrales,
    interiores,
    ordenes,
  );
  const base = referencia.data
    ? {
        formation: referencia.data.formation,
        rating: referencia.data.totalRating,
      }
    : null;

  const sacar = (htPlayerId: number, player: string) =>
    setFuera((previos) =>
      previos.some((f) => f.htPlayerId === htPlayerId)
        ? previos
        : [...previos, { htPlayerId, player }],
    );
  const devolver = (htPlayerId: number) =>
    setFuera((previos) => previos.filter((f) => f.htPlayerId !== htPlayerId));

  /** La X que saca a alguien del reparto sin arrastrarlo.
   *
   *  En la cancha va flotando en la esquina de la tarjeta, tenue para no
   *  competir con el rating, y se enciende al pasar por encima o al enfocarla
   *  con el teclado. Tenue pero SIEMPRE visible: escondida tras `hover` las
   *  once aspas quedaban en opacidad 0 en un móvil, donde no hay hover que
   *  las devuelva, y desde la cancha no había forma de sacar a nadie
   *  (2026-09-03). En el banquillo va como botón, que ahí sobra el espacio. */
  const BotonSacar = ({
    htPlayerId,
    player,
    enCancha,
  }: {
    htPlayerId: number;
    player: string;
    enCancha?: boolean;
  }) => (
    <button
      onClick={() => sacar(htPlayerId, player)}
      data-track="Alineación: sacar del reparto"
      title={`Sacar a ${player} del reparto`}
      aria-label={`Sacar a ${player} del reparto`}
      className={clsx(
        "leading-none",
        enCancha
          ? "absolute right-0.5 top-0.5 z-10 flex h-6 w-6 items-center justify-center rounded-full text-sm text-white/35 transition hover:bg-black/40 hover:text-white focus-visible:text-white"
          : "min-h-6 rounded border border-[var(--border)] px-2 text-xs text-[var(--muted)] hover:border-[var(--danger)] hover:text-[var(--danger)]",
      )}
    >
      {enCancha ? "\u00d7" : "Sacar"}
    </button>
  );

  /** Lo que hace falta para poder arrastrar a alguien fuera.
   *
   *  Se marca con `draggable` el envoltorio y no el enlace del nombre: un
   *  enlace ya es arrastrable por su cuenta y el navegador soltaría la
   *  dirección en vez del jugador. */
  const arrastrable = (htPlayerId: number, player: string) => ({
    draggable: true,
    onDragStart: (e: React.DragEvent) => {
      e.dataTransfer.setData(
        "application/x-jugador",
        JSON.stringify({ htPlayerId, player }),
      );
      e.dataTransfer.effectAllowed = "move";
    },
  });

  const spirit = useQuery({
    queryKey: ["team-spirit-multiplier", TEAM_ID],
    queryFn: () => api.teamSpiritMultiplier(TEAM_ID),
  });

  const hindsight = useQuery({
    queryKey: ["lineup-hindsight", TEAM_ID],
    queryFn: () => api.lineupHindsight(TEAM_ID),
  });

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <Empty>Sin plantilla sincronizada.</Empty>;

  // Se agrupa por `basePosition` (la casilla de la formación) y no por
  // `position`, que desde 2026-08-21 lleva dentro la orden individual: un
  // "Defensa Lateral Ofensivo" sigue jugando en la línea de atrás.
  const lines = {
    forwards: data.lineup.filter((a) => a.basePosition === "forward"),
    midfield: data.lineup.filter(
      (a) => a.basePosition === "inner_midfield" || a.basePosition === "winger",
    ),
    defence: data.lineup.filter(
      (a) =>
        a.basePosition === "central_defender" || a.basePosition === "wingback",
    ),
    keeper: data.lineup.filter((a) => a.basePosition === "keeper"),
  };

  const Slot = ({ a }: { a: (typeof data.lineup)[number] }) => (
    <div
      className={clsx(PITCH_CARD_CLASS, "group relative")}
      {...arrastrable(a.htPlayerId, a.player)}
      title={`Arrastra a ${a.player} fuera del reparto, o pulsa la X`}
    >
      <BotonSacar htPlayerId={a.htPlayerId} player={a.player} enCancha />
      <div className="truncate pr-5 text-[9px] uppercase tracking-wide text-white/70">
        {a.label}
      </div>
      <div className="truncate text-[11px] font-semibold text-white">
        <PlayerLink htPlayerId={a.htPlayerId} name={a.player} onDark />
      </div>
      <div className="tabular-nums text-sm font-semibold text-amber-300">
        {a.rating.toFixed(2)}
      </div>
      {a.orderOptions.length > 1 && (
        <select
          value={ordenes[a.slot] ?? ""}
          onChange={(e) =>
            setOrdenes((previas) => {
              const siguientes = { ...previas };
              if (e.target.value) siguientes[a.slot] = e.target.value;
              else delete siguientes[a.slot];
              return siguientes;
            })
          }
          aria-label={`Orden individual de ${a.label}`}
          title={
            a.orderPinned
              ? "Orden fijada por ti: el motor solo elige quién la juega"
              : "Orden elegida por el motor"
          }
          className={clsx(
            "mt-1 w-full rounded border bg-black/50 px-1 py-0.5 text-[9px] text-white/90",
            a.orderPinned ? "border-amber-300/70" : "border-white/25",
          )}
        >
          <option value="">Automática</option>
          {a.orderOptions.map((o) => (
            <option key={o.position} value={o.position}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </div>
  );

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Alineación</h1>
          <p className="text-sm text-[var(--muted)]">
            Asignación óptima resuelta con el algoritmo húngaro
          </p>
          <EnlaceATransparencia seccion="posiciones" calculo="once-optimo" />
        </div>
        <div className="flex gap-2">
          <select
            value={formation}
            onChange={(e) => {
              setFormation(e.target.value);
              setCentrales(undefined);
              setInteriores(undefined);
              setOrdenes({});
            }}
            aria-label="Formación"
            className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm"
          >
            <option value="">Mejor formación</option>
            {FORMATIONS.map((f) => (
              <option key={f}>{f}</option>
            ))}
          </select>
          {/* El mismo control que en el once ideal de la liga: solo se
              pregunta por los del centro y las bandas salen por resta. Con
              "Mejor formación" no se ofrece, porque ahí se comparan las diez
              con su reparto propio. */}
          {formation && (
            <>
              <SplitSelector
                label="Defensa central"
                value={data.centralDefenders}
                options={data.centralDefenderOptions}
                onChange={setCentrales}
              />
              <SplitSelector
                label="Medio central"
                value={data.innerMidfielders}
                options={data.innerMidfielderOptions}
                onChange={setInteriores}
              />
            </>
          )}
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-3 [&>*]:min-w-0">
        <Kpi label="Formación" value={data.formation} />
        <Kpi label="Rating total" value={data.totalRating.toFixed(2)} />
        <Kpi label="Banquillo" value={String(data.bench.length)} />
      </div>

      {/* La misma cancha que usan Equipo y la Comparativa de liga: un once se
          lee de un vistazo cuando está puesto sobre el campo, y de tres
          renglones grises hay que reconstruirlo mentalmente. */}
      <PitchField
        ariaLabel={`Once óptimo en formación ${data.formation}, con el índice de cada puesto`}
        className="rounded-lg"
      >
        <PitchGrid
          rows={[lines.forwards, lines.midfield, lines.defence, lines.keeper]}
          // Gente de banda: extremos arriba y laterales atrás. Son los que
          // ocupan las dos columnas de los bordes, y por eso un extremo cae
          // siempre sobre su lateral.
          isFlank={(a) =>
            a.basePosition === "winger" || a.basePosition === "wingback"
          }
          render={(a) => <Slot key={a.slot} a={a} />}
        />
      </PitchField>

      {/* Fuera del reparto.
          El once NO se edita moviendo a alguien de casilla: el motor resuelve
          la asignación entera, así que mover a mano una pieza rompería el
          resultado del resto. Lo que sí tiene sentido es quitar del reparto a
          quien no va a jugar --lesionado, sancionado, o para ver el once sin
          él-- y dejar que vuelva a resolverlo con los demás (2026-09-02). */}
      <Panel
        title="Fuera del reparto"
        meta={
          fuera.length === 0
            ? "arrastra aquí a quien no vaya a jugar"
            : `${fuera.length} jugador(es)`
        }
      >
        <div
          onDragOver={(e) => {
            // Sin esto el navegador rechaza la soltada y no llega `onDrop`.
            if (e.dataTransfer.types.includes("application/x-jugador")) {
              e.preventDefault();
              e.dataTransfer.dropEffect = "move";
            }
          }}
          onDrop={(e) => {
            e.preventDefault();
            const crudo = e.dataTransfer.getData("application/x-jugador");
            if (!crudo) return;
            const { htPlayerId, player } = JSON.parse(crudo);
            sacar(htPlayerId, player);
          }}
          className="m-4 rounded-lg border-2 border-dashed border-[var(--border)] p-3"
        >
          {fuera.length === 0 ? (
            <p className="py-4 text-center text-xs text-[var(--muted)]">
              Arrastra un jugador de la cancha o del banquillo hasta aquí, o usa
              el botón «Sacar». El once se vuelve a resolver con el resto.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {fuera.map((f) => (
                <li
                  key={f.htPlayerId}
                  className="flex items-center justify-between gap-3 py-2 text-sm"
                >
                  <PlayerLink htPlayerId={f.htPlayerId} name={f.player} />
                  <button
                    onClick={() => devolver(f.htPlayerId)}
                    data-track="Alineación: devolver al reparto"
                    className="min-h-6 rounded border border-[var(--border)] px-2 text-xs text-[var(--muted)] hover:border-[var(--accent)] hover:text-[var(--accent)]"
                  >
                    Devolver
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        {fuera.length > 0 && (
          <div className="space-y-2 border-t border-[var(--border)] px-4 py-2">
            {base && (
              <p className="text-xs leading-relaxed text-[var(--muted)]">
                {base.formation === data.formation ? (
                  <>
                    Sigues en {data.formation}: el hueco lo tapa otro jugador y
                    el índice pasa de {base.rating.toFixed(2)} a{" "}
                    {data.totalRating.toFixed(2)}.
                  </>
                ) : (
                  <>
                    Sin ellos la mejor formación ya no es {base.formation} sino{" "}
                    {data.formation}, así que la cancha enseña puestos
                    distintos: no se descartó una posición, se recolocó el
                    equipo entero. El índice pasa de {base.rating.toFixed(2)} a{" "}
                    {data.totalRating.toFixed(2)}. Para mantener{" "}
                    {base.formation}, elígela arriba en vez de «Mejor
                    formación».
                  </>
                )}
              </p>
            )}
            <button
              onClick={() => setFuera([])}
              data-track="Alineación: devolver a todos"
              className="text-xs text-[var(--muted)] underline hover:text-[var(--text)]"
            >
              Devolver a todos
            </button>
          </div>
        )}
      </Panel>

      {data.bench.length > 0 && (
        <Panel title="Banquillo" meta={`${data.bench.length} jugadores`}>
          <ul className="divide-y divide-[var(--border)]">
            {data.bench.map((b) => (
              <li
                key={b.htPlayerId}
                className="flex items-center justify-between gap-3 px-4 py-2 text-sm"
                {...arrastrable(b.htPlayerId, b.player)}
              >
                <PlayerLink htPlayerId={b.htPlayerId} name={b.player} />
                <span className="flex items-center gap-3">
                  <span className="tabular-nums text-[var(--muted)]">
                    TSI {number(b.tsi)}
                  </span>
                  {/* El botón no es un adorno del arrastre: sin él, sacar a
                      alguien sería imposible con teclado o en un móvil. */}
                  <BotonSacar htPlayerId={b.htPlayerId} player={b.player} />
                </span>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {hindsight.data && <HindsightPanel data={hindsight.data} />}

      <Panel
        title="Ranking de formaciones"
        meta="índice total del once óptimo en cada una"
      >
        <Chart
          ariaLabel="Rating total por formación"
          // Alto fijo y corto: son cinco o seis barras y antes ocupaba una
          // pantalla entera para decir lo mismo.
          height={Math.max(120, Object.keys(data.formationRanking).length * 26)}
          option={barOption(
            Object.keys(data.formationRanking),
            Object.values(data.formationRanking),
            "Rating",
          )}
        />
      </Panel>

      <Panel
        title="Espíritu de Equipo × Actitud"
        meta="tabla explorable, no tu Espíritu actual"
      >
        {spirit.data ? (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--muted)]">
                    <th scope="col" className="px-4 py-2">
                      Espíritu
                    </th>
                    <th scope="col" className="px-4 py-2 text-right">
                      PIC
                    </th>
                    <th scope="col" className="px-4 py-2 text-right">
                      Normal
                    </th>
                    <th scope="col" className="px-4 py-2 text-right">
                      MOTS
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {spirit.data.rows.map((r) => (
                    <tr key={r.spirit}>
                      <td className="px-4 py-2">{r.spirit}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {(r.pic * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {(r.normal * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {(r.mots * 100).toFixed(0)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <Empty>Calculando…</Empty>
        )}
      </Panel>

      <Panel
        title="Calificación por sector"
        meta="fórmula exacta de contribución, segunda opinión sobre este mismo once"
      >
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
          {data.sectorRatings.ratings.map((s) => (
            <div
              key={s.sector}
              className="rounded-lg border border-[var(--border)] p-3"
            >
              <div className="text-xs text-[var(--muted)]">{s.label}</div>
              <div className="mt-1 text-xl font-semibold tabular-nums text-[var(--accent)]">
                {s.value.toFixed(1)}
              </div>
              <div className="mt-2 space-y-0.5 text-[11px] text-[var(--muted)]">
                {s.topContributors.map((c) => (
                  <div key={c.player} className="truncate">
                    {c.player}{" "}
                    <span className="tabular-nums">
                      ({c.amount.toFixed(1)})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
        <Note>{data.sectorRatings.note}</Note>
      </Panel>
    </div>
  );
}

/**
 * Evaluar decisiones reales — 2026-08-15, pedido explícito.
 *
 * Hasta ahora la pantalla solo decía qué once es el mejor HOY, en abstracto.
 * Esto lo contrasta con lo que de verdad pasó: quién jugó cada puesto en el
 * último partido, qué calificación sacó, y a quién habría puesto ahí el
 * optimizador. La calificación real es el árbitro: si el optimizador discrepa
 * y el jugador que pusiste sacó un 7,5, la discrepancia no significa error.
 */
function HindsightPanel({ data }: { data: LineupHindsight }) {
  if (data.matchId == null) {
    return (
      <Panel title="Tu alineación contra la propuesta">
        <Empty>
          {data.notes[0] ??
            "No has enviado alineación para ningún partido próximo."}
        </Empty>
      </Panel>
    );
  }

  const disagreements = data.lines.reduce(
    (n, l) => n + l.proposedInstead.length,
    0,
  );

  return (
    <Panel
      title="Tu alineación contra la propuesta"
      meta={
        data.matchLabel
          ? `${data.matchLabel} · coinciden ${data.agreementCount}/${data.comparableCount}`
          : `coinciden ${data.agreementCount}/${data.comparableCount}`
      }
    >
      {/* Contra qué se compara, dicho donde se ve: la alineación que el
          usuario ya envió, no un partido pasado. */}
      {data.notes[0] && (
        <p className="border-b border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
          {data.notes[0]}
        </p>
      )}
      <div className="divide-y divide-[var(--border)]">
        {data.lines.map((line) => (
          <div
            key={line.key}
            className="grid gap-2 p-4 sm:grid-cols-[9rem_1fr]"
          >
            <div>
              <div className="text-sm font-medium">{line.label}</div>
              <div className="text-xs text-[var(--muted)]">
                {line.agreedCount}/{line.usedCount} coinciden
              </div>
            </div>
            <div className="space-y-1.5">
              {line.used.map((p) => (
                <div
                  key={p.htPlayerId}
                  className="flex flex-wrap items-baseline gap-x-2 text-sm"
                >
                  <PlayerLink htPlayerId={p.htPlayerId} name={p.player} />
                  <span className="text-xs text-[var(--muted)]">
                    {p.positionLabel}
                    {p.playedMinutes < 90 && ` · ${p.playedMinutes}′`}
                  </span>
                  {/* El partido no se ha jugado: no hay nota que enseñar. */}
                  {p.rating != null && (
                    <span
                      className={
                        p.rating >= 7
                          ? "tabular-nums font-semibold text-[var(--positive)]"
                          : p.rating <= 4
                            ? "tabular-nums font-semibold text-[var(--danger)]"
                            : "tabular-nums font-semibold"
                      }
                    >
                      {p.rating.toFixed(1)}
                    </span>
                  )}
                  {p.alsoProposed && (
                    <span className="text-xs text-[var(--muted)]">
                      · el optimizador coincide
                    </span>
                  )}
                </div>
              ))}
              {line.proposedInstead.length > 0 && (
                <div className="text-xs text-[var(--warning)]">
                  El optimizador pondría aquí a{" "}
                  {line.proposedInstead
                    .map((p) => `${p.player} (${p.rating.toFixed(2)})`)
                    .join(", ")}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {disagreements === 0 && (
        <Note>
          El optimizador habría usado a los mismos jugadores en todas las
          líneas.
        </Note>
      )}
    </Panel>
  );
}
