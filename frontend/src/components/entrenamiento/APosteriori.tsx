/** A posteriori (8.3.0, 2026-11-26): con lo que de verdad se jugó esta
 *  semana, qué entrenamiento aprovechaba mejor.
 *
 *  Definido con el usuario, texto a texto: el subtítulo dice cuándo, cómo y
 *  por qué se usa; el de debajo, con qué partidos y cuándo se aplica el
 *  entrenamiento. Siempre están el entrenamiento actual y el mejor; tocando un
 *  chip se añade UNO más, que reemplaza al anterior (8.3.1, pedido del
 *  usuario: con varios, los añadidos salían del mismo color y con un número). «Entrenamiento actual» y nunca «lo que pusiste» (pedido del
 *  usuario). El cálculo está en `app/domain/engines/aprovechamiento.py`. */
import { useState } from "react";
import clsx from "clsx";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import { terminoOficial } from "../../i18n/glosario";
import { tx } from "../../i18n/tx";
import {
  date,
  dateTime,
  decimal,
  parseUtc,
  percent,
} from "../../hooks/useFormat";
import { useAprovechamiento } from "../../hooks/useTeam";
import type {
  Aprovechamiento,
  AprovechamientoOpcion,
} from "../../services/api";
import { EnlaceATransparencia } from "../EnlaceATransparencia";
import { Empty, ErrorState, Loading, Note, Panel } from "../Panels";
import { PlayerLink } from "../PlayerLink";
import {
  COLOR_ACTUAL,
  COLOR_MEJOR,
  COLOR_ELEGIDO,
  GraficaDelAprovechamiento,
} from "./GraficaDelAprovechamiento";

/** El nombre oficial del entrenamiento, del glosario de Hattrick. */
const nombre = (o: { trainingType: number; name: string }) =>
  terminoOficial("entrenamientos", String(o.trainingType), o.name);

/** «viernes 27/11/2026» y «00:30», en la hora de quien mira. */
function cuando(iso: string) {
  const d = parseUtc(iso);
  const dia = d.toLocaleDateString(i18n.language, { weekday: "long" });
  return { dia: `${dia} ${date(iso)}`, hora: dateTime(iso).slice(-5) };
}

export function APosteriori() {
  const q = useAprovechamiento();
  if (q.isLoading) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data) return null;
  return <Contenido datos={q.data} />;
}

function Contenido({ datos }: { datos: Aprovechamiento }) {
  const { t } = useTranslation();
  const actual =
    datos.opciones.find((o) => o.trainingType === datos.actual?.trainingType) ??
    null;
  const mejor =
    datos.opciones.find((o) => o.trainingType === datos.mejor) ?? null;
  const [elegido, setElegido] = useState<number | null>(null);
  const [abierta, setAbierta] = useState<number | null>(null);
  const fijos = new Set(
    [actual?.trainingType, mejor?.trainingType].filter(
      (n): n is number => n != null,
    ),
  );
  // Uno a la vez: tocar otro chip reemplaza al anterior, y tocar el mismo lo
  // quita.
  const elegir = (tipo: number) =>
    setElegido((antes) => (antes === tipo ? null : tipo));
  const activos = new Set(fijos);
  if (elegido != null) activos.add(elegido);
  const visibles = datos.opciones.filter((o) => activos.has(o.trainingType));
  const color = (o: AprovechamientoOpcion) =>
    o.trainingType === actual?.trainingType
      ? COLOR_ACTUAL
      : o.trainingType === mejor?.trainingType
        ? COLOR_MEJOR
        : COLOR_ELEGIDO;

  const corte = cuando(datos.corte);
  const partidos = datos.partidos
    .map((p) =>
      tx("{{competicion}} del {{fecha}} contra {{rival}}", {
        competicion: p.competicion,
        fecha: p.jugadoEl ? date(p.jugadoEl).slice(0, 5) : "-",
        rival: p.rival ?? "-",
      }),
    )
    .join(tx(" y "))
    // Un rival que acaba en punto («F.C.») dejaba «F.C..» con el de la frase.
    .replace(/\.$/, "");

  return (
    <Panel
      title={tx("¿Qué entrenamiento aprovechaba mejor esta semana?")}
      meta={t("entrenamiento.aPosteriori", "A posteriori")}
    >
      <div className="space-y-4 p-4">
        <div className="space-y-1">
          <p className="prosa text-sm">
            {tx(
              "Úsalo después del segundo partido de la semana (copa, copa desafío o amistoso) y antes de que se aplique el entrenamiento. Compara todos los entrenamientos con los minutos y puestos que de verdad se jugaron: si la alineación no salió como planeabas, otro entrenamiento puede sacarle más a esos minutos, y una vez aplicado ya no se puede cambiar.",
            )}
          </p>
          <p className="text-xs text-[var(--muted)]">
            {datos.partidos.length > 0 &&
              tx("Con lo que se jugó en {{partidos}}.", { partidos }) + " "}
            {datos.aunSePuedeCambiar
              ? tx(
                  "El entrenamiento se aplica el {{dia}} a las {{hora}}.",
                  corte,
                )
              : tx(
                  "El entrenamiento se aplicó el {{dia}} a las {{hora}}.",
                  corte,
                )}
          </p>
        </div>

        {datos.partidos.length === 0 ? (
          <Empty>
            {tx(
              "Todavía no se ha jugado ningún partido en esta semana de entrenamiento. Vuelve después de la liga.",
            )}
          </Empty>
        ) : (
          <>
            <Veredicto
              datos={datos}
              actual={actual}
              mejor={mejor}
              corte={corte}
            />

            <div className="space-y-1.5">
              <div className="text-xs text-[var(--muted)]">
                {tx("Comparar con (uno a la vez):")}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {datos.opciones.map((o) => {
                  const on = activos.has(o.trainingType);
                  const fijo = fijos.has(o.trainingType);
                  return (
                    <button
                      key={o.trainingType}
                      type="button"
                      aria-pressed={on}
                      // El actual y el mejor están siempre: no se quitan.
                      disabled={fijo}
                      onClick={() => elegir(o.trainingType)}
                      className={clsx(
                        "rounded-full border px-2.5 py-1 text-xs transition-colors",
                        on
                          ? "bg-[var(--surface-2)] font-medium text-[var(--text)]"
                          : "border-[var(--border)] text-[var(--muted)] hover:text-[var(--text)]",
                      )}
                      style={
                        on
                          ? { borderColor: color(o), borderWidth: 1.5 }
                          : undefined
                      }
                    >
                      {on ? "✓ " : ""}
                      {nombre(o)}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col items-center gap-2">
              <GraficaDelAprovechamiento
                opciones={datos.opciones}
                activos={visibles}
                nombre={nombre}
                color={color}
              />
              <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
                <Muestra
                  color={COLOR_ACTUAL}
                  texto={tx("Entrenamiento actual")}
                />
                <Muestra color={COLOR_MEJOR} texto={tx("El mejor")} />
                {elegido != null && (
                  <Muestra
                    color={COLOR_ELEGIDO}
                    texto={tx("El que comparas")}
                  />
                )}
                <span>{tx("Tamaño: casillas que entrenan")}</span>
              </div>
            </div>

            <MiniTabla
              visibles={visibles}
              actual={actual}
              color={color}
              abierta={abierta}
              onAbrir={(tipo) => setAbierta(abierta === tipo ? null : tipo)}
            />

            <details className="rounded-md border border-[var(--border)] px-3 py-2 text-sm">
              <summary className="cursor-pointer font-medium">
                {tx("¿Cómo se calcula?")}
              </summary>
              <div className="prosa mt-2 space-y-2 text-[var(--muted)]">
                <p>
                  {tx(
                    "El ideal (100%) es un jugador de 17 años con nivel 8 (excelente) en la habilidad, jugando 90′ en cada casilla de los dos partidos.",
                  )}
                </p>
                <p>
                  {tx(
                    "Cada jugador aporta según tres cosas: los minutos que jugó en un puesto que entrena (hasta 90′ por semana), lo que sube su HTMS cada semana con ese entrenamiento y su edad. Cuanto más joven, más vale cada subida, hasta dejar de contar a los 34 años.",
                  )}
                </p>
                <p>
                  {tx(
                    "Aprovechado = lo que aportan todos ÷ lo que aportarían jugadores ideales en todas las casillas. Una casilla vacía, o un jugador que repite cuando ya cumplió sus 90′, también cuentan como desperdicio. Las tácticas no entran.",
                  )}
                </p>
                <EnlaceATransparencia
                  seccion="entrenamiento"
                  calculo="a-posteriori"
                >
                  {tx("Ver el detalle en Transparencia →")}
                </EnlaceATransparencia>
              </div>
            </details>
          </>
        )}

        {datos.notas.length > 0 && <Note>{datos.notas.join(" ")}</Note>}
      </div>
    </Panel>
  );
}

function Veredicto({
  datos,
  actual,
  mejor,
  corte,
}: {
  datos: Aprovechamiento;
  actual: AprovechamientoOpcion | null;
  mejor: AprovechamientoOpcion | null;
  corte: { dia: string; hora: string };
}) {
  const unSoloPartido =
    datos.partidos.length === 1
      ? " " +
        tx(
          "Por ahora sólo cuenta un partido: las casillas del segundo cuentan como vacías hasta que se juegue.",
        )
      : "";
  let frase: string;
  if (!actual) {
    frase = tx(
      "No se sabe qué entrenamiento tienes puesto: sincroniza para leerlo.",
    );
  } else if (!mejor || mejor.trainingType === actual.trainingType) {
    frase = tx(
      "Tu entrenamiento actual, {{nombre}}, es el que mejor aprovecha esta semana: {{pct}}.",
      { nombre: nombre(actual), pct: percent(actual.aprovechado * 100) },
    );
  } else {
    frase =
      tx(
        "Entrenamiento actual: {{actual}}, {{pa}}. Con {{mejor}} habrías aprovechado {{pm}}, {{veces}} veces más.",
        {
          actual: nombre(actual),
          pa: percent(actual.aprovechado * 100),
          mejor: nombre(mejor),
          pm: percent(mejor.aprovechado * 100),
          veces: datos.veces != null ? decimal(datos.veces, 1) : "-",
        },
      ) +
      " " +
      (datos.aunSePuedeCambiar
        ? tx(
            "Todavía puedes cambiarlo antes del {{dia}} a las {{hora}}.",
            corte,
          )
        : tx("Este ya se aplicó: tenlo en cuenta para la próxima semana."));
  }
  return (
    <p className="rounded-md bg-[var(--surface-2)] px-3 py-2 text-sm">
      {frase}
      {unSoloPartido}
    </p>
  );
}

function Muestra({ color, texto }: { color: string; texto: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span
        className="inline-block h-2.5 w-2.5 rounded-full"
        style={{ background: color }}
      />
      {texto}
    </span>
  );
}

function MiniTabla({
  visibles,
  actual,
  color,
  abierta,
  onAbrir,
}: {
  visibles: AprovechamientoOpcion[];
  actual: AprovechamientoOpcion | null;
  color: (o: AprovechamientoOpcion) => string;
  abierta: number | null;
  onAbrir: (tipo: number) => void;
}) {
  return (
    <div className="space-y-1">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-[var(--muted)]">
            <th className="py-1 text-left font-normal">#</th>
            <th className="py-1 text-left font-normal">
              {tx("Entrenamiento")}
            </th>
            <th className="py-1 text-right font-normal">{tx("Aprovechado")}</th>
            <th className="whitespace-nowrap py-1 text-right font-normal">
              {tx("× actual")}
            </th>
          </tr>
        </thead>
        <tbody>
          {visibles.map((o, i) => {
            const esActual = o.trainingType === actual?.trainingType;
            const destacado = color(o) !== COLOR_ELEGIDO;
            return (
              <FilaConDetalle
                key={o.trainingType}
                o={o}
                i={i}
                esActual={esActual}
                destacado={destacado}
                color={color(o)}
                veces={
                  !esActual && actual && actual.aprovechado > 0
                    ? `×${decimal(o.aprovechado / actual.aprovechado, 2)}`
                    : "—"
                }
                abierta={abierta === o.trainingType}
                onAbrir={() => onAbrir(o.trainingType)}
              />
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-[var(--muted)]">
        {tx("Toca una fila para ver sus datos.")}
      </p>
    </div>
  );
}

function FilaConDetalle({
  o,
  i,
  esActual,
  destacado,
  color,
  veces,
  abierta,
  onAbrir,
}: {
  o: AprovechamientoOpcion;
  i: number;
  esActual: boolean;
  destacado: boolean;
  color: string;
  veces: string;
  abierta: boolean;
  onAbrir: () => void;
}) {
  return (
    <>
      <tr
        className={clsx(
          "cursor-pointer border-t border-[var(--border)] hover:bg-[var(--surface-2)]",
          destacado && "font-semibold",
        )}
        onClick={onAbrir}
        aria-expanded={abierta}
      >
        <td className="py-1.5 tabular-nums">{i + 1}</td>
        <td className="py-1.5">
          <span
            className="mr-1.5 inline-block h-2 w-2 rounded-full"
            style={{ background: color }}
          />
          {nombre(o)}
          {esActual && (
            <span className="ml-1 text-xs font-normal text-[var(--muted)]">
              · {tx("actual")}
            </span>
          )}
        </td>
        <td className="py-1.5 text-right tabular-nums">
          {percent(o.aprovechado * 100)}
        </td>
        <td className="py-1.5 text-right tabular-nums">{veces}</td>
      </tr>
      {abierta && (
        <tr>
          <td colSpan={4} className="pb-2">
            <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 rounded-md bg-[var(--surface-2)] px-3 py-2 text-xs">
              <dt className="text-[var(--muted)]">
                {tx("Jugador que mejor lo aprovecha")}
              </dt>
              <dd className="text-right">
                {o.mejorJugador ? (
                  <>
                    <PlayerLink
                      htPlayerId={o.mejorJugador.htPlayerId}
                      name={o.mejorJugador.name}
                    />{" "}
                    {percent(o.mejorJugador.pct * 100, 0)}
                  </>
                ) : (
                  "-"
                )}
              </dd>
              <dt className="text-[var(--muted)]">
                {tx("Jugadores que entrenan")}
              </dt>
              <dd className="text-right tabular-nums">{o.jugadores}</dd>
              <dt className="text-[var(--muted)]">
                {tx("Casillas que entrenan")}
              </dt>
              <dd className="text-right tabular-nums">
                {tx("{{n}} de {{total}}", {
                  n: decimal(o.casillasQueEntrenan, 1).replace(/\.0$/, ""),
                  total: decimal(o.casillas, 1).replace(/\.0$/, ""),
                })}
              </dd>
              <dt className="text-[var(--muted)]">
                {tx("Minutos que no entrenan por el cupo de 90′")}
              </dt>
              <dd className="text-right tabular-nums">
                {decimal(o.minutosSinEntrenar, 0)}′
              </dd>
              <dt className="text-[var(--muted)]">
                {tx("Semanas por nivel (media)")}
              </dt>
              <dd className="text-right tabular-nums">
                {o.semanasPorNivel != null
                  ? decimal(o.semanasPorNivel, 1)
                  : "-"}
              </dd>
            </dl>
          </td>
        </tr>
      )}
    </>
  );
}
