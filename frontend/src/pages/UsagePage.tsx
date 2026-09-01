import { dateTime } from "../hooks/useFormat";
import { useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ErrorState, Panel } from "../components/Panels";
import { PanelDePestanas, Tabs } from "../components/Tabs";
import { api } from "../services/api";
import type { UsageSummary, UsageUser } from "../services/api";

/** Qué usa la gente. Sólo la abre el administrador —la comprobación de verdad
 *  está en el servidor, en `require_admin`; esconder el enlace no protege nada.
 *
 *  2026-08-26. Todo lo que se enseña aquí sale de la misma tabla de eventos:
 *  ningún servicio de fuera, ninguna cookie que consentir.
 *
 *  2026-09-01, pedido del usuario: hasta hoy todo se agregaba a un número por
 *  pantalla, y con doce personas registradas eso esconde justo lo que hay que
 *  saber —si una pantalla la usan nueve o la usa una sola muchas veces—. La
 *  página se parte en cuatro secciones porque son cuatro preguntas distintas:
 *
 *    Resumen   · cuánto se usa esto en total
 *    Personas  · quién hace qué, una por una
 *    Adopción  · a qué se VUELVE, y qué no abrió nadie
 *    Registro  · el detalle en crudo, evento por evento
 */

/** `2 h 15 min`, `3 min 20 s`, `45 s`.
 *
 *  Cada tramo se queda con dos unidades: pasado el minuto los segundos
 *  sueltos no se leen, y pasada la hora tampoco los segundos.
 */
function duracion(segundos: number): string {
  if (segundos < 60) return `${segundos} s`;
  const m = Math.floor(segundos / 60);
  if (m < 60) {
    const s = segundos % 60;
    return s === 0 ? `${m} min` : `${m} min ${s} s`;
  }
  const h = Math.floor(m / 60);
  const resto = m % 60;
  return resto === 0 ? `${h} h` : `${h} h ${resto} min`;
}

/** Los minutos que manda el servidor vienen con decimal (`4427.7`). */
function desdeMinutos(minutos: number): string {
  return duracion(Math.round(minutos * 60));
}

function Cifra({ valor, de }: { valor: string; de: string }) {
  return (
    <div className="rounded-md border border-[var(--border)] p-3">
      <div className="text-xs text-[var(--muted)]">{de}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{valor}</div>
    </div>
  );
}

/** La barra de proporción que se repite en tres tablas. */
function Barra({ parte, de }: { parte: number; de: number }) {
  return (
    <span className="block h-1.5 w-full rounded bg-[var(--surface-2)]">
      <span
        className="block h-full rounded bg-[var(--accent)]"
        style={{ width: `${de > 0 ? (parte / de) * 100 : 0}%` }}
      />
    </span>
  );
}

const PLAZOS = [7, 30, 90] as const;
const th = "px-3 py-2 text-xs font-medium text-[var(--muted)]";
const td = "px-3 py-2 text-sm";

const SECCIONES = [
  { key: "resumen", label: "Resumen" },
  { key: "personas", label: "Personas" },
  { key: "adopcion", label: "Adopción" },
  { key: "registro", label: "Registro" },
] as const;
type Seccion = (typeof SECCIONES)[number]["key"];

export function UsagePage() {
  const [dias, setDias] = useState<number>(30);
  const [seccion, setSeccion] = useState<Seccion>("resumen");
  const { data, isLoading, error } = useQuery({
    queryKey: ["usage", dias],
    queryFn: () => api.usage(dias),
  });

  if (error) return <ErrorState error={error} />;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Uso de la aplicación</h1>
          <p className="text-sm text-[var(--muted)]">
            Qué se usa de verdad, medido en tu propio servidor.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {PLAZOS.map((p) => (
            <button
              key={p}
              onClick={() => setDias(p)}
              data-track={`Uso: ${p} dias`}
              aria-pressed={dias === p}
              className={`rounded-md border px-2 py-1 text-xs ${
                dias === p
                  ? "border-[var(--accent)] text-[var(--accent)]"
                  : "border-[var(--border)] text-[var(--muted)]"
              }`}
            >
              {p} días
            </button>
          ))}
          {/* Descarga directa, sin pasar por React: el navegador la resuelve
              solo. Es la salida de emergencia si la base se pierde —no tiene
              copias y en varios proveedores caduca—. */}
          <a
            href={`/api/v1/usage/export.csv?dias=${Math.max(dias, 365)}`}
            data-track="Uso: exportar CSV"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]"
          >
            Exportar CSV
          </a>
        </div>
      </header>

      {isLoading && <p className="text-sm text-[var(--muted)]">Cargando…</p>}

      {data && data.totals.pages === 0 && (
        <Panel title="Todavía no hay nada que enseñar">
          <p className="p-4 text-sm text-[var(--muted)]">
            La medición empieza el día que se despliega: no hay datos de antes.
            Navega un poco y vuelve.
          </p>
        </Panel>
      )}

      {data && data.totals.pages > 0 && (
        <>
          <Tabs
            tabs={[...SECCIONES]}
            active={seccion}
            onChange={setSeccion}
            grupo="uso"
            label="Secciones de uso"
          />
          <PanelDePestanas grupo="uso" activa={seccion} className="space-y-4">
            {seccion === "resumen" && <Resumen data={data} />}
            {seccion === "personas" && <Personas data={data} />}
            {seccion === "adopcion" && <Adopcion data={data} />}
            {seccion === "registro" && <Registro dias={dias} />}
          </PanelDePestanas>
        </>
      )}
    </div>
  );
}

// ── Resumen ────────────────────────────────────────────────────────────────

function Resumen({ data }: { data: UsageSummary }) {
  const maxMinutos = Math.max(...data.modules.map((m) => m.minutes), 1);
  const maxHora = Math.max(...Object.values(data.byHour), 1);

  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Cifra de="Sesiones" valor={String(data.totals.sessions)} />
        <Cifra de="Páginas vistas" valor={String(data.totals.pages)} />
        <Cifra de="Clics" valor={String(data.totals.clicks)} />
        <Cifra de="Tiempo total" valor={desdeMinutos(data.totals.minutes)} />
        {/* La MEDIANA, no la media: una pestaña olvidada dispara el
            promedio y deja de describir a nadie. */}
        <Cifra
          de="Sesión típica"
          valor={duracion(data.totals.medianSessionSeconds)}
        />
        <Cifra
          de="Clics por sesión"
          valor={String(data.totals.clicksPerSession)}
        />
      </div>

      <Panel title="Por módulo" meta="ordenado por tiempo dentro">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--surface-2)]">
              <tr>
                <th scope="col" className={`${th} text-left`}>
                  Módulo
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Visitas
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Clics
                </th>
                <th
                  scope="col"
                  className={`${th} text-right`}
                  title="con la pestaña de verdad visible"
                >
                  Tiempo
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Por visita
                </th>
                <th scope="col" className={`${th} text-left`}>
                  Reparto
                </th>
              </tr>
            </thead>
            <tbody>
              {data.modules.map((m) => (
                <tr key={m.module} className="border-t border-[var(--border)]">
                  <td className={`${td} font-medium`}>{m.module}</td>
                  <td className={`${td} text-right tabular-nums`}>
                    {m.visits}
                  </td>
                  {/* Cero clics con visitas es la señal interesante: se
                      mira y no se toca nada. */}
                  <td
                    className={`${td} text-right tabular-nums ${
                      m.clicks === 0 ? "text-[var(--warning)]" : ""
                    }`}
                    title={
                      m.clicks === 0
                        ? "se mira, pero no se toca nada"
                        : undefined
                    }
                  >
                    {m.clicks}
                  </td>
                  <td className={`${td} text-right tabular-nums`}>
                    {desdeMinutos(m.minutes)}
                  </td>
                  <td
                    className={`${td} text-right tabular-nums text-[var(--muted)]`}
                  >
                    {duracion(Math.round(m.avgSecondsPerVisit))}
                  </td>
                  <td className={td}>
                    <Barra parte={m.minutes} de={maxMinutos} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <Panel title="Lo más pulsado" meta="qué se usa, no qué se mira">
          {data.topControls.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">
              Ningún clic todavía.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border)]">
              {data.topControls.map((c) => (
                <li
                  key={c.label}
                  className="flex items-baseline justify-between gap-3 px-4 py-2 text-sm"
                >
                  <span className="truncate">{c.label}</span>
                  <span className="shrink-0 tabular-nums font-medium">
                    {c.clicks}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="A qué horas" meta="hora del servidor, UTC">
          <div className="flex h-32 items-end gap-[2px] p-4">
            {Array.from({ length: 24 }, (_, h) => {
              const n = data.byHour[String(h)] ?? 0;
              return (
                <span
                  key={h}
                  title={`${h}:00 — ${n} eventos`}
                  className="flex-1 rounded-t bg-[var(--accent)]"
                  style={{ height: `${Math.max(2, (n / maxHora) * 100)}%` }}
                />
              );
            })}
          </div>
        </Panel>
      </div>

      <Panel title="Sesiones recientes" meta="las 25 últimas">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--surface-2)]">
              <tr>
                <th scope="col" className={`${th} text-left`}>
                  Empezó
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Duró
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Páginas
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Clics
                </th>
                <th scope="col" className={`${th} text-left`}>
                  Por dónde pasó
                </th>
              </tr>
            </thead>
            <tbody>
              {data.recentSessions.map((s) => (
                <tr key={s.id} className="border-t border-[var(--border)]">
                  <td className={`${td} tabular-nums`}>
                    {dateTime(s.startedAt)}
                  </td>
                  <td className={`${td} text-right tabular-nums`}>
                    {duracion(s.seconds)}
                  </td>
                  <td className={`${td} text-right tabular-nums`}>{s.pages}</td>
                  <td className={`${td} text-right tabular-nums`}>
                    {s.clicks}
                  </td>
                  <td className={`${td} text-[var(--muted)]`}>
                    {s.modules.join(" · ")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}

// ── Personas ───────────────────────────────────────────────────────────────

function Personas({ data }: { data: UsageSummary }) {
  const [abierta, setAbierta] = useState<number | null>(null);
  const maxMinutos = Math.max(...data.byUser.map((u) => u.minutes), 1);
  const callados = data.registeredUsers - data.activeUsers;

  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Cifra de="Personas activas" valor={String(data.activeUsers)} />
        <Cifra de="Registradas" valor={String(data.registeredUsers)} />
        {/* La cifra incómoda, y por eso está: quien se registró y no ha
            vuelto no aparece en ninguna tabla ordenada por uso. */}
        <Cifra
          de="Sin aparecer en el plazo"
          valor={String(Math.max(0, callados))}
        />
        <Cifra
          de="Páginas por persona"
          valor={String(
            data.activeUsers > 0
              ? Math.round(data.totals.pages / data.activeUsers)
              : 0,
          )}
        />
      </div>

      <Panel
        title="Quién usa qué"
        meta="pulsa una fila para ver su desglose por pantalla"
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--surface-2)]">
              <tr>
                <th scope="col" className={`${th} text-left`}>
                  Persona
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Sesiones
                </th>
                <th
                  scope="col"
                  className={`${th} text-right`}
                  title="días distintos con actividad, no visitas"
                >
                  Días activos
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Páginas
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Clics
                </th>
                <th
                  scope="col"
                  className={`${th} text-right`}
                  title="mirar o trabajar: cuántas cosas toca cada vez que entra"
                >
                  Clics/página
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Tiempo
                </th>
                <th scope="col" className={`${th} text-left`}>
                  Donde vive
                </th>
                <th scope="col" className={`${th} text-left`}>
                  Última vez
                </th>
              </tr>
            </thead>
            <tbody>
              {data.byUser.map((u) => (
                <FilaDePersona
                  key={u.userId}
                  u={u}
                  abierta={abierta === u.userId}
                  alAbrir={() =>
                    setAbierta(abierta === u.userId ? null : u.userId)
                  }
                  maxMinutos={maxMinutos}
                />
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}

function FilaDePersona({
  u,
  abierta,
  alAbrir,
  maxMinutos,
}: {
  u: UsageUser;
  abierta: boolean;
  alAbrir: () => void;
  maxMinutos: number;
}) {
  const maxDentro = Math.max(...u.modules.map((m) => m.minutes), 1);
  return (
    <>
      <tr className="border-t border-[var(--border)]">
        <td className={`${td} font-medium`}>
          {/* El botón es la celda entera y no un icono suelto: una fila de
              tabla no se anuncia como pulsable por sí sola, y un objetivo de
              24 px es el mínimo que pide la norma. */}
          <button
            onClick={alAbrir}
            aria-expanded={abierta}
            data-track="Uso: desplegar persona"
            className="flex min-h-[24px] items-center gap-1.5 text-left hover:text-[var(--accent)]"
          >
            <span
              aria-hidden
              className={`inline-block text-[var(--muted)] transition-transform ${
                abierta ? "rotate-90" : ""
              }`}
            >
              ›
            </span>
            {u.name}
          </button>
        </td>
        <td className={`${td} text-right tabular-nums`}>{u.sessions}</td>
        <td className={`${td} text-right tabular-nums`}>{u.activeDays}</td>
        <td className={`${td} text-right tabular-nums`}>{u.pages}</td>
        <td className={`${td} text-right tabular-nums`}>{u.clicks}</td>
        <td
          className={`${td} text-right tabular-nums ${
            u.clicksPerPage === 0 ? "text-[var(--warning)]" : ""
          }`}
          title={u.clicksPerPage === 0 ? "sólo mira, no toca nada" : undefined}
        >
          {u.clicksPerPage}
        </td>
        <td className={`${td} text-right tabular-nums`}>
          {desdeMinutos(u.minutes)}
        </td>
        <td className={td}>
          <span className="block">{u.favouriteModule || "—"}</span>
          <Barra parte={u.minutes} de={maxMinutos} />
        </td>
        <td className={`${td} tabular-nums text-[var(--muted)]`}>
          {u.lastSeen ? dateTime(u.lastSeen) : "—"}
        </td>
      </tr>
      {abierta && (
        <tr className="bg-[var(--surface-2)]">
          <td colSpan={9} className="px-3 py-2">
            <table className="w-full">
              <thead>
                <tr>
                  <th scope="col" className={`${th} text-left`}>
                    Pantalla
                  </th>
                  <th scope="col" className={`${th} text-right`}>
                    Visitas
                  </th>
                  <th scope="col" className={`${th} text-right`}>
                    Clics
                  </th>
                  <th scope="col" className={`${th} text-right`}>
                    Tiempo
                  </th>
                  <th scope="col" className={`${th} text-right`}>
                    Por visita
                  </th>
                  <th scope="col" className={`${th} text-left`}>
                    Reparto
                  </th>
                </tr>
              </thead>
              <tbody>
                {u.modules.map((m) => (
                  <tr key={m.module}>
                    <td className={td}>{m.module}</td>
                    <td className={`${td} text-right tabular-nums`}>
                      {m.visits}
                    </td>
                    <td className={`${td} text-right tabular-nums`}>
                      {m.clicks}
                    </td>
                    <td className={`${td} text-right tabular-nums`}>
                      {desdeMinutos(m.minutes)}
                    </td>
                    <td
                      className={`${td} text-right tabular-nums text-[var(--muted)]`}
                    >
                      {duracion(Math.round(m.avgSecondsPerVisit))}
                    </td>
                    <td className={td}>
                      <Barra parte={m.minutes} de={maxDentro} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      )}
    </>
  );
}

// ── Adopción ───────────────────────────────────────────────────────────────

function Adopcion({ data }: { data: UsageSummary }) {
  return (
    <>
      <Panel
        title="A qué se vuelve"
        meta="ordenado por cuánta gente distinta la abre"
      >
        {/* El único aviso de la pantalla, y hace falta: sin él, la tabla se
            lee como el ranking de siempre y no lo es. */}
        <p className="border-b border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
          Volumen y arraigo no son lo mismo. Una pantalla puede acumular horas
          porque alguien la dejó abierta; otra tener pocas visitas pero de mucha
          gente, y repetidas. Ésta ordena por lo segundo.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-[var(--surface-2)]">
              <tr>
                <th scope="col" className={`${th} text-left`}>
                  Pantalla
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Personas
                </th>
                <th
                  scope="col"
                  className={`${th} text-left`}
                  title="de las que aparecieron en el plazo"
                >
                  Alcance
                </th>
                <th
                  scope="col"
                  className={`${th} text-right`}
                  title="abrirla una vez y no volver da 1"
                >
                  Visitas/persona
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Días
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Clics/visita
                </th>
                <th scope="col" className={`${th} text-right`}>
                  Tiempo
                </th>
              </tr>
            </thead>
            <tbody>
              {data.adoption.map((a) => (
                <tr key={a.module} className="border-t border-[var(--border)]">
                  <td className={`${td} font-medium`}>{a.module}</td>
                  <td className={`${td} text-right tabular-nums`}>{a.users}</td>
                  <td className={td}>
                    <span className="mb-1 block text-xs tabular-nums text-[var(--muted)]">
                      {a.reach} %
                    </span>
                    <Barra parte={a.reach} de={100} />
                  </td>
                  <td
                    className={`${td} text-right tabular-nums ${
                      a.visitsPerUser <= 1 ? "text-[var(--warning)]" : ""
                    }`}
                    title={
                      a.visitsPerUser <= 1
                        ? "se abre una vez y no se vuelve"
                        : undefined
                    }
                  >
                    {a.visitsPerUser}
                  </td>
                  <td className={`${td} text-right tabular-nums`}>{a.days}</td>
                  <td className={`${td} text-right tabular-nums`}>
                    {a.clicksPerVisit}
                  </td>
                  <td className={`${td} text-right tabular-nums`}>
                    {desdeMinutos(a.minutes)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2 [&>*]:min-w-0">
        <Panel
          title="Dentro de cada pantalla"
          meta="lo más pulsado ahí, no en el ranking general"
        >
          <ul className="divide-y divide-[var(--border)]">
            {data.insideEach.map((s) => (
              <li key={s.module} className="px-4 py-3">
                <div className="text-sm font-medium">{s.module}</div>
                <ul className="mt-1 space-y-0.5">
                  {s.controls.map((c) => (
                    <li
                      key={c.label}
                      className="flex items-baseline justify-between gap-3 text-sm text-[var(--muted)]"
                    >
                      <span className="truncate">{c.label}</span>
                      <span className="shrink-0 tabular-nums">{c.clicks}</span>
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel
          title="Nadie las abrió"
          meta={`en los últimos ${data.days} días`}
        >
          {data.untouched.length === 0 ? (
            <p className="p-4 text-sm text-[var(--muted)]">
              Todas las pantallas tuvieron al menos una visita.
            </p>
          ) : (
            <>
              <p className="border-b border-[var(--border)] px-4 py-2 text-xs text-[var(--muted)]">
                Un ranking por uso deja el cero fuera del final, donde no se ve.
                Una pantalla que nadie abre es una decisión pendiente.
              </p>
              <ul className="flex flex-wrap gap-2 p-4">
                {data.untouched.map((m) => (
                  <li
                    key={m}
                    className="rounded-full border border-[var(--border)] px-2.5 py-1 text-sm text-[var(--muted)]"
                  >
                    {m}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      </div>
    </>
  );
}

// ── Registro ───────────────────────────────────────────────────────────────

const POR_PAGINA = 100;

function Registro({ dias }: { dias: number }) {
  const [usuario, setUsuario] = useState<number | null>(null);
  const [modulo, setModulo] = useState<string>("");
  const [tipo, setTipo] = useState<"" | "page" | "click">("");
  const [buscar, setBuscar] = useState("");
  const [texto, setTexto] = useState("");
  const [desdeFila, setDesdeFila] = useState(0);

  const { data, isFetching, error } = useQuery({
    queryKey: ["usage-log", dias, usuario, modulo, tipo, buscar, desdeFila],
    queryFn: () =>
      api.usageLog({
        dias,
        usuario,
        modulo: modulo || null,
        tipo: tipo || null,
        buscar: buscar || null,
        desdeFila,
        cuantas: POR_PAGINA,
      }),
    // Sin esto la tabla parpadea a vacío en cada página y se pierde el sitio.
    placeholderData: keepPreviousData,
  });

  if (error) return <ErrorState error={error} />;

  /** Cualquier filtro nuevo devuelve a la primera página: si no, se pide la
   *  página 4 de un resultado que ahora tiene una, y sale vacía. */
  const filtrar = (aplicar: () => void) => {
    aplicar();
    setDesdeFila(0);
  };

  const control =
    "rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm";
  const hasta = Math.min(desdeFila + POR_PAGINA, data?.total ?? 0);

  return (
    <Panel
      title="Registro"
      meta={
        data
          ? `${data.total} eventos · viendo ${data.total === 0 ? 0 : desdeFila + 1}–${hasta}`
          : undefined
      }
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] p-3">
        <label className="text-xs text-[var(--muted)]">
          Persona
          <select
            value={usuario ?? ""}
            onChange={(e) =>
              filtrar(() =>
                setUsuario(e.target.value ? Number(e.target.value) : null),
              )
            }
            data-track="Uso: filtrar por persona"
            className={`ml-1.5 ${control}`}
          >
            <option value="">Todas</option>
            {(data?.users ?? []).map((u) => (
              <option key={u.userId} value={u.userId}>
                {u.name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted)]">
          Pantalla
          <select
            value={modulo}
            onChange={(e) => filtrar(() => setModulo(e.target.value))}
            data-track="Uso: filtrar por pantalla"
            className={`ml-1.5 ${control}`}
          >
            <option value="">Todas</option>
            {(data?.modules ?? []).map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-[var(--muted)]">
          Tipo
          <select
            value={tipo}
            onChange={(e) =>
              filtrar(() => setTipo(e.target.value as "" | "page" | "click"))
            }
            data-track="Uso: filtrar por tipo"
            className={`ml-1.5 ${control}`}
          >
            <option value="">Todo</option>
            <option value="page">Visitas</option>
            <option value="click">Clics</option>
          </select>
        </label>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            filtrar(() => setBuscar(texto.trim()));
          }}
          className="flex items-center gap-1.5"
        >
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Etiqueta del control…"
            aria-label="Buscar por etiqueta del control"
            className={control}
          />
          <button
            type="submit"
            data-track="Uso: buscar en el registro"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)]"
          >
            Buscar
          </button>
        </form>
        {isFetching && (
          <span className="text-xs text-[var(--muted)]">Cargando…</span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-[var(--surface-2)]">
            <tr>
              <th scope="col" className={`${th} text-left`}>
                Cuándo
              </th>
              <th scope="col" className={`${th} text-left`}>
                Persona
              </th>
              <th scope="col" className={`${th} text-left`}>
                Qué
              </th>
              <th scope="col" className={`${th} text-left`}>
                Pantalla
              </th>
              <th scope="col" className={`${th} text-left`}>
                Control
              </th>
              <th scope="col" className={`${th} text-right`}>
                Visible
              </th>
              <th scope="col" className={`${th} text-left`}>
                Sesión
              </th>
            </tr>
          </thead>
          <tbody>
            {(data?.rows ?? []).map((f) => (
              <tr key={f.id} className="border-t border-[var(--border)]">
                <td className={`${td} tabular-nums whitespace-nowrap`}>
                  {dateTime(f.at)}
                </td>
                <td className={td}>{f.name}</td>
                <td className={`${td} text-[var(--muted)]`}>
                  {f.kind === "page" ? "Visita" : "Clic"}
                </td>
                <td className={td}>{f.module}</td>
                <td className={td}>{f.label ?? "—"}</td>
                <td className={`${td} text-right tabular-nums`}>
                  {f.visibleMs > 0
                    ? duracion(Math.round(f.visibleMs / 1000))
                    : "—"}
                </td>
                {/* Los ocho primeros caracteres bastan para ver si dos
                    eventos son de la misma visita, que es para lo único que
                    se mira. */}
                <td
                  className={`${td} font-mono text-xs text-[var(--muted)]`}
                  title={f.session}
                >
                  {f.session.slice(0, 8)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data && data.total === 0 && (
        <p className="p-4 text-sm text-[var(--muted)]">
          Nada que cumpla ese filtro.
        </p>
      )}

      {data && data.total > POR_PAGINA && (
        <div className="flex items-center justify-between gap-3 border-t border-[var(--border)] p-3">
          <button
            onClick={() => setDesdeFila(Math.max(0, desdeFila - POR_PAGINA))}
            disabled={desdeFila === 0}
            data-track="Uso: registro anterior"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] disabled:opacity-40"
          >
            Anteriores
          </button>
          <span className="text-xs tabular-nums text-[var(--muted)]">
            {desdeFila + 1}–{hasta} de {data.total}
          </span>
          <button
            onClick={() => setDesdeFila(desdeFila + POR_PAGINA)}
            disabled={hasta >= data.total}
            data-track="Uso: registro siguiente"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] disabled:opacity-40"
          >
            Siguientes
          </button>
        </div>
      )}
    </Panel>
  );
}
