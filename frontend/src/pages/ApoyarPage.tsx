import { useState } from "react";
import { MensajeDeApoyo } from "../components/ApoyarProyecto";
import { Panel } from "../components/Panels";
import { type ViaDeApoyo, hayApoyo, viasPara } from "../config/apoyo";
import { useDashboard } from "../hooks/useTeam";

/**
 * Las formas de apoyar el proyecto.
 *
 * Existe como pantalla propia y no como menú desplegable por un motivo
 * concreto: Bre-B no es un enlace sino una llave que hay que COPIAR, y en un
 * desplegable de la barra lateral no cabe con dignidad. De paso queda sitio
 * para decir POR QUÉ elegir cada una, que es lo que convierte tres botones en
 * una decisión que alguien puede tomar sin adivinar.
 */

/** La llave, con su botón de copiar.
 *
 *  El `navigator.clipboard` puede fallar --contexto no seguro, permiso
 *  denegado-- y entonces el botón no haría nada visible. Por eso la llave se
 *  enseña siempre en claro: aunque copiar falle, se puede leer y teclear.
 */
function Llave({ valor }: { valor: string }) {
  const [copiada, setCopiada] = useState(false);
  return (
    <div className="flex items-center gap-2">
      <code className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 font-mono text-sm">
        {valor}
      </code>
      <button
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(valor);
            setCopiada(true);
            setTimeout(() => setCopiada(false), 2000);
          } catch {
            // Sin portapapeles no pasa nada: la llave está ahí al lado.
          }
        }}
        className="rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--text)]"
      >
        {copiada ? "Copiada" : "Copiar"}
      </button>
    </div>
  );
}

function Via({ via, primera }: { via: ViaDeApoyo; primera: boolean }) {
  return (
    <li className="flex flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="text-sm font-medium">{via.nombre}</p>
        <p className="prosa text-sm leading-relaxed text-[var(--muted)]">
          {via.porQue}
        </p>
      </div>
      {via.llave ? (
        <Llave valor={via.llave} />
      ) : (
        <a
          href={via.enlace}
          target="_blank"
          rel="noopener noreferrer"
          /* Sólo la primera va en color: son tres caminos al mismo sitio, y
             pintar los tres como llamada principal es no recomendar nada. */
          className={
            primera
              ? "shrink-0 rounded-md bg-[var(--accent)] px-4 py-2 text-center text-sm font-medium text-white"
              : "shrink-0 rounded-md border border-[var(--border)] px-4 py-2 text-center text-sm text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--text)]"
          }
        >
          Abrir
        </a>
      )}
    </li>
  );
}

export function ApoyarPage() {
  const { data } = useDashboard();
  if (!hayApoyo()) return null;
  // El país sale del club, que es lo que la aplicación sabe de verdad. No se
  // mira el idioma del navegador: alguien puede tener el navegador en inglés
  // y el club en Colombia, y lo que decide cómo puede pagar es lo segundo.
  const vias = viasPara(data?.leagueName);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Apoyar el proyecto</h1>
        <p className="prosa text-sm text-[var(--muted)]">
          Tres formas de hacerlo. Elige la que te quede más cómoda.
        </p>
      </header>

      <Panel title="Por qué">
        <div className="p-4">
          <MensajeDeApoyo />
        </div>
      </Panel>

      <Panel
        title="Cómo"
        meta={data?.leagueName ? `ordenadas para ${data.leagueName}` : ""}
      >
        <ul className="divide-y divide-[var(--border)]">
          {vias.map((v, i) => (
            <Via key={v.id} via={v} primera={i === 0} />
          ))}
        </ul>
      </Panel>

      <p className="prosa text-sm text-[var(--muted)]">
        Y si prefieres no poner dinero, escribe en el{" "}
        <a href="/libro" className="text-[var(--accent)] hover:underline">
          libro de visitas
        </a>
        : saber qué te falta vale tanto como un café.
      </p>
    </div>
  );
}
