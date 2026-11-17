/** El selector «Mirar a» de Habilidades (6.10.0, 2026-11-17, decisiones del
 *  usuario): arriba la clasificación, debajo las casillas con sus grupos, y en
 *  Habilidades con varios marcados, el dato que se compara. Sólo se marcan
 *  grupos de la clasificación activa, para que cada línea sea gente distinta. */
import type { ReactNode } from "react";
import { tx } from "../../i18n/tx";
import { Tabs } from "../Tabs";
import type {
  Clasificacion,
  ClaveDeClasificacion,
} from "../clases/clasificaciones";
import { PLANTILLA } from "./graficasPorGrupo";

function Fila({
  etiqueta,
  children,
}: {
  etiqueta: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <span className="w-24 shrink-0 text-sm text-[var(--muted)]">
        {etiqueta}
      </span>
      {children}
    </div>
  );
}

function Casilla({
  nombre,
  color,
  marcada,
  apagada,
  onClick,
}: {
  nombre: string;
  color: string;
  marcada: boolean;
  apagada: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={marcada}
      disabled={apagada}
      onClick={onClick}
      className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm disabled:opacity-40"
      style={{
        borderColor: marcada ? color : "var(--border)",
        background: marcada ? "var(--surface)" : "transparent",
        color: marcada ? "var(--text)" : "var(--muted)",
      }}
    >
      <span
        aria-hidden
        className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-[3px] border text-[10px] leading-none text-white"
        style={{
          borderColor: color,
          background: marcada ? color : "transparent",
        }}
      >
        {marcada ? "✓" : ""}
      </span>
      {nombre}
    </button>
  );
}

export function SelectorMirarA({
  clasificaciones,
  activa,
  onClasificacion,
  marcados,
  onMarcar,
  dato,
}: {
  clasificaciones: Clasificacion[];
  activa: Clasificacion;
  onClasificacion: (c: ClaveDeClasificacion) => void;
  marcados: string[];
  onMarcar: (clave: string) => void;
  /** Sólo en Habilidades con dos o más marcados. */
  dato?: {
    opciones: { key: string; label: string }[];
    activo: string;
    onChange: (key: string) => void;
  };
}) {
  return (
    <div className="space-y-2">
      <Fila etiqueta={tx("Clasificación")}>
        <Tabs<ClaveDeClasificacion>
          modo="filtro"
          label={tx("Clasificación")}
          active={activa.clave}
          onChange={onClasificacion}
          tabs={clasificaciones.map((c) => ({
            key: c.clave,
            label: c.nombre,
            disabled: c.grupos.length === 0,
            title:
              c.grupos.length === 0
                ? tx("Aún no has creado ningún grupo.")
                : undefined,
          }))}
        />
      </Fila>
      <Fila etiqueta={tx("Grupos")}>
        <div className="flex flex-wrap gap-2">
          <Casilla
            nombre={tx("Plantilla entera")}
            color="#94a3b8"
            marcada={marcados.includes(PLANTILLA)}
            apagada={false}
            onClick={() => onMarcar(PLANTILLA)}
          />
          {activa.grupos.map((g) => (
            <Casilla
              key={g.clave}
              nombre={`${g.nombre} · ${g.jugadores.length}`}
              color={g.color}
              marcada={marcados.includes(g.clave)}
              apagada={g.jugadores.length === 0}
              onClick={() => onMarcar(g.clave)}
            />
          ))}
        </div>
      </Fila>
      <p className="text-xs text-[var(--muted)] sm:pl-[6.75rem]">
        {tx(
          "Puedes marcar varios. Con uno solo, las gráficas son las de hoy; con dos o más, una línea por grupo.",
        )}
      </p>
      {dato && (
        <Fila etiqueta={tx("Dato")}>
          <Tabs
            modo="filtro"
            label={tx("Dato")}
            active={dato.activo}
            onChange={dato.onChange}
            tabs={dato.opciones.map((o) => ({ key: o.key, label: o.label }))}
          />
        </Fila>
      )}
    </div>
  );
}
