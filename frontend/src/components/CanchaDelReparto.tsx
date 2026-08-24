import type { TrainingSlot } from "../services/api";
import { skillLevelLabel } from "../utils/skillLevels";

/** La cancha del reparto de entrenamientos, con el aspecto de Alineación.
 *
 * Dos cosas a la vez, en dos canales distintos para que no se estorben:
 *
 *   el RELLENO dice lo bueno que es en esa habilidad — verde claro un
 *   excelente, verde oscuro un bueno, amarillo de ahí para abajo, gris lo
 *   que no se sabe;
 *   el BORDE dice qué entrenamiento le llega — los dos, uno o ninguno.
 *
 * Pintar la región de relleno mataba el verde del campo y dejaba de parecer
 * una cancha; pintar el nivel en el borde lo hacía invisible.
 */
const NIVEL = {
  excelente: { fondo: "rgba(74,222,128,.32)", borde: "#4ade80", texto: "#dcfce7" },
  bueno: { fondo: "rgba(21,128,61,.5)", borde: "#15803d", texto: "#dcfce7" },
  resto: { fondo: "rgba(250,204,21,.26)", borde: "#facc15", texto: "#fef9c3" },
  desconocido: {
    fondo: "rgba(255,255,255,.07)",
    borde: "rgba(255,255,255,.25)",
    texto: "rgba(255,255,255,.65)",
  },
} as const;

function tono(current: number | null, maximum: number | null) {
  const nivel = current ?? maximum;
  if (nivel == null) return NIVEL.desconocido;
  if (nivel >= 8) return NIVEL.excelente;
  if (nivel === 7) return NIVEL.bueno;
  return NIVEL.resto;
}

const BORDE_REGION: Record<string, string> = {
  ambos: "#c4b5fd",
  solo_principal: "#93c5fd",
  solo_secundaria: "#6ee7b7",
};

const PUESTO_CORTO: Record<string, string> = {
  keeper: "PORTERO",
  wingback: "DEFENSA LATERAL",
  central_defender: "DEFENSA CENTRAL",
  winger: "EXTREMO",
  inner_midfield: "MEDIOCENTRO",
  forward: "DELANTERO",
};

function edad(dias: number): string {
  return Math.floor(dias / 112) + ";" + String(dias % 112).padStart(3, "0");
}

function Tarjeta({
  a,
  mainLabel,
  secondaryLabel,
}: {
  a: TrainingSlot;
  mainLabel: string;
  secondaryLabel: string;
}) {
  const t = tono(a.current, a.maximum);
  const raciones = [
    a.racionPrincipal > 0 ? mainLabel + " " + a.racionPrincipal + "%" : null,
    a.racionSecundaria > 0 ? secondaryLabel + " " + a.racionSecundaria + "%" : null,
  ].filter(Boolean);
  const anillo = BORDE_REGION[a.region];
  const sabeAlgo = a.current != null || a.maximum != null;

  return (
    <div
      className="rounded-lg p-1.5 text-center backdrop-blur"
      style={{
        background: t.fondo,
        border: "1px solid " + (a.maxReached ? "#f87171" : t.borde),
        boxShadow: anillo ? "0 0 0 2px " + anillo : "none",
      }}
    >
      <p className="text-[9px] tracking-wide text-white/55">
        {PUESTO_CORTO[a.puesto] ?? " "}
      </p>
      <p className="text-[12px] leading-tight text-white">{a.player}</p>
      <p className="text-[10px]" style={{ color: t.texto }}>
        {a.maxReached ? "🔒 " : ""}
        {sabeAlgo
          ? skillLevelLabel(a.current ?? a.maximum ?? 0) +
            " " +
            (a.current ?? "?") +
            "/" +
            (a.maximum ?? "?")
          : "desconocido"}
      </p>
      <p className="text-[10px] tabular-nums text-white/50">
        {edad(a.ageDaysTotal)}
        {a.weeksLeft != null && (
          <span
            title="Entrenamientos que le quedan antes de irse"
            style={{ color: a.weeksLeft <= 5 ? "#fca5a5" : undefined }}
          >
            {" · " + a.weeksLeft + " sem"}
          </span>
        )}
      </p>
      {raciones.length > 0 && (
        <p className="text-[10px] text-white/75">{raciones.join(" · ")}</p>
      )}
    </div>
  );
}

/** Una fila de la cancha: los de banda a los lados, el resto en el centro. */
function Fila({
  items,
  mainLabel,
  secondaryLabel,
}: {
  items: TrainingSlot[];
  mainLabel: string;
  secondaryLabel: string;
}) {
  if (items.length === 0) return null;
  const esBanda = (a: TrainingSlot) =>
    a.puesto === "winger" || a.puesto === "wingback";
  const bandas = items.filter(esBanda);
  const centro = items.filter((a) => !esBanda(a));
  const izq = bandas[0];
  const der = bandas.length > 1 ? bandas[bandas.length - 1] : undefined;
  const medio = [...bandas.slice(1, Math.max(1, bandas.length - 1)), ...centro];

  return (
    <div className="grid grid-cols-5 gap-2">
      <div>
        {izq && <Tarjeta a={izq} mainLabel={mainLabel} secondaryLabel={secondaryLabel} />}
      </div>
      <div
        className="col-span-3 grid gap-2"
        style={{
          gridTemplateColumns:
            "repeat(" + Math.max(1, medio.length) + ", minmax(0,1fr))",
        }}
      >
        {medio.map((a) => (
          <Tarjeta key={a.player} a={a} mainLabel={mainLabel} secondaryLabel={secondaryLabel} />
        ))}
      </div>
      <div>
        {der && <Tarjeta a={der} mainLabel={mainLabel} secondaryLabel={secondaryLabel} />}
      </div>
    </div>
  );
}

const COLUMNAS_BANQUILLO = [
  "Portero",
  "Defensa Central",
  "Defensa Lateral",
  "Medio Centro",
  "Delantero",
  "Extremo",
  "Extra",
];

export function CanchaDelReparto({
  assignments,
  outside,
  mainLabel,
  secondaryLabel,
}: {
  assignments: TrainingSlot[];
  outside: (TrainingSlot & { benchColumn: string })[];
  mainLabel: string;
  secondaryLabel: string;
}) {
  const de = (p: string) => assignments.filter((a) => a.puesto === p);
  const filas = [
    de("forward"),
    [...de("winger"), ...de("inner_midfield")],
    [...de("wingback"), ...de("central_defender")],
    de("keeper"),
  ];

  return (
    <div>
      <div
        className="overflow-x-auto rounded-lg p-4"
        style={{ background: "linear-gradient(to bottom,#022c22,#064e3b,#022c22)" }}
      >
        <div className="mx-auto flex min-w-[36rem] flex-col gap-2">
          {filas.map((f, i) => (
            <Fila key={i} items={f} mainLabel={mainLabel} secondaryLabel={secondaryLabel} />
          ))}

          {/* El banquillo, como en Hattrick: una columna por tipo de puesto.
              Un juvenil no tiene puesto asignado, así que la columna sale de
              la habilidad en la que más destaca — es una lectura nuestra, no
              un dato del juego. */}
          <div className="mt-3 rounded-md border border-white/15 p-3">
            <p className="mb-2 text-center text-[11px] text-white/60">Banquillo</p>
            <div
              className="grid gap-2"
              style={{
                gridTemplateColumns:
                  "repeat(" + COLUMNAS_BANQUILLO.length + ", minmax(0,1fr))",
              }}
            >
              {COLUMNAS_BANQUILLO.map((col) => {
                const suyos = outside.filter((o) => o.benchColumn === col);
                return (
                  <div key={col} className="space-y-1">
                    <p className="text-[9px] text-white/45">{col}</p>
                    {suyos.length === 0 ? (
                      <div className="rounded border border-dashed border-white/15 py-3" />
                    ) : (
                      suyos.map((o) => (
                        <Tarjeta
                          key={o.player}
                          a={o}
                          mainLabel={mainLabel}
                          secondaryLabel={secondaryLabel}
                        />
                      ))
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
        <span>
          <i
            style={{ background: "#c4b5fd" }}
            className="mr-1 inline-block h-2 w-2 rounded-sm align-middle"
          />
          reciben los dos
        </span>
        <span>
          <i
            style={{ background: "#93c5fd" }}
            className="mr-1 inline-block h-2 w-2 rounded-sm align-middle"
          />
          solo {mainLabel}
        </span>
        <span>
          <i
            style={{ background: "#6ee7b7" }}
            className="mr-1 inline-block h-2 w-2 rounded-sm align-middle"
          />
          solo {secondaryLabel}
        </span>
        <span>
          el color de la tarjeta es el nivel: verde claro excelente, verde oscuro
          bueno, amarillo el resto, gris sin revelar
        </span>
      </div>
    </div>
  );
}
