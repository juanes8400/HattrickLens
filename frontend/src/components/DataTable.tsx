import { useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { nombreLargo } from "../utils/abreviaturas";

/**
 * Table component meeting the UI_GUIDELINES.md requirements:
 * sorting, filtering, sticky headers, column selector, CSV export and
 * keyboard navigation.
 */
export interface Column<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  /** Value used for sorting, filtering and CSV export. */
  value: (row: T) => string | number;
  /** Optional rich rendering. Falls back to `value`. */
  render?: (row: T) => React.ReactNode;
  /** Hidden by default but offered in the column selector. */
  optional?: boolean;
}

interface Props<T> {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  initialSort?: string;
  /** Dirección inicial del ordenamiento — por defecto descendente (el uso
   * más común: "mayor primero"). Una tabla de posiciones quiere lo
   * contrario: 1º arriba, no 8º. */
  initialDescending?: boolean;
  filterPlaceholder?: string;
  csvName?: string;
  /** Qué poner cuando no hay ni una fila. OBLIGATORIO a propósito.
   *
   *  Era opcional con «Sin datos todavía.» de reserva, y 14 de 23 tablas se
   *  quedaban en él (2026-08-31): un texto que no dice qué debería haber ahí
   *  ni qué hacer para que aparezca, justo en la pantalla que más ve una
   *  cuenta recién creada. Las 9 que sí lo pasaban demuestran la diferencia:
   *  «Sin jugadores para calcular fidelidad», «Sin equipos en esta categoría».
   *
   *  El patrón está copiado de `ariaLabel` en las gráficas: allí es
   *  obligatorio por tipo y las 30 llamadas tienen nombre útil. Donde el
   *  sistema obliga no hay excepciones; donde tiene valor por defecto, el 60%
   *  se queda en él. */
  emptyMessage: string;
  selectedRowKey?: string | number | null;
  onRowClick?: (row: T) => void;
}

export function DataTable<T>({
  rows,
  columns,
  rowKey,
  initialSort,
  initialDescending = true,
  filterPlaceholder = "Filtrar…",
  csvName = "export",
  emptyMessage,
  selectedRowKey,
  onRowClick,
}: Props<T>) {
  const [sortKey, setSortKey] = useState(initialSort ?? columns[0]?.key);
  const [descending, setDescending] = useState(initialDescending);
  const [filter, setFilter] = useState("");
  // Todas las columnas visibles de entrada (2026-09-01, pedido del usuario:
  // «que todas las tablas tengan como default en columnas: Todas»). Antes,
  // las marcadas `optional` nacían ocultas, y en varias tablas eso dejaba
  // fuera justo lo que se había ido añadiendo: había que abrir «Columnas» y
  // saber que faltaba algo para llegar a ello.
  //
  // MENOS EN UNA PANTALLA ESTRECHA (2026-09-02). Ahí «todas» se paga en
  // desplazamiento lateral: en Jugadores son 29 columnas y 2.589px, siete
  // arrastres para llegar al final, y la tabla deja de servir para mirar algo
  // rápido. En móvil se arranca con las esenciales y el selector sigue
  // estando para pedir el resto -- que es justo lo contrario de esconder algo
  // sin decirlo.
  //
  // Se decide UNA VEZ, al montar: una tabla que se reordena sola al girar el
  // teléfono sorprende más de lo que ayuda.
  const [hidden, setHidden] = useState<Set<string>>(() => {
    // Se exige un ancho POSITIVO antes de concluir que la pantalla es
    // estrecha. Un cero no es un móvil: es "todavía no se sabe" -- pasa con la
    // pestaña oculta, en una captura de miniatura o al pintar en el servidor
    // -- y tomarlo por móvil escondía doce columnas en un escritorio. Ante la
    // duda se enseñan todas, que es lo que pidió el usuario.
    const ancho = typeof window === "undefined" ? 0 : window.innerWidth;
    const estrecha = ancho > 0 && ancho < 768;
    return estrecha
      ? new Set(columns.filter((c) => c.optional).map((c) => c.key))
      : new Set();
  });
  const [showPicker, setShowPicker] = useState(false);

  // El selector de columnas sólo se cerraba volviendo a pulsar «Columnas»:
  // ni Escape ni pinchar fuera lo cerraban, que es lo que todo el mundo
  // intenta primero con un desplegable (2026-08-31).
  useEffect(() => {
    if (!showPicker) return;
    const alPulsar = (e: KeyboardEvent) => {
      if (e.key === "Escape") setShowPicker(false);
    };
    const alPinchar = (e: MouseEvent) => {
      // `data-picker` marca lo que pertenece al desplegable --el botón que lo
      // abre y el panel--, que están en ramas distintas del árbol.
      const dentro = (e.target as Element | null)?.closest?.("[data-picker]");
      if (!dentro) setShowPicker(false);
    };
    document.addEventListener("keydown", alPulsar);
    document.addEventListener("mousedown", alPinchar);
    return () => {
      document.removeEventListener("keydown", alPulsar);
      document.removeEventListener("mousedown", alPinchar);
    };
  }, [showPicker]);
  const [focused, setFocused] = useState(0);

  const visible = columns.filter((c) => !hidden.has(c.key));

  const processed = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const filtered = needle
      ? rows.filter((r) =>
          visible.some((c) =>
            String(c.value(r)).toLowerCase().includes(needle),
          ),
        )
      : rows;

    const col = columns.find((c) => c.key === sortKey);
    if (!col) return filtered;

    return [...filtered].sort((a, b) => {
      const x = col.value(a);
      const y = col.value(b);
      const cmp =
        typeof x === "string" || typeof y === "string"
          ? String(x).localeCompare(String(y))
          : (x as number) - (y as number);
      return descending ? -cmp : cmp;
    });
  }, [rows, columns, visible, filter, sortKey, descending]);

  function toggleSort(key: string) {
    if (key === sortKey) setDescending((d) => !d);
    else {
      setSortKey(key);
      setDescending(true);
    }
  }

  function exportCsv() {
    const header = visible.map((c) => c.header).join(",");
    const body = processed
      .map((r) =>
        visible
          .map((c) => {
            const v = String(c.value(r));
            return v.includes(",") || v.includes('"')
              ? `"${v.replace(/"/g, '""')}"`
              : v;
          })
          .join(","),
      )
      .join("\n");
    const blob = new Blob([`${header}\n${body}`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${csvName}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTableSectionElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocused((i) => Math.min(i + 1, processed.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocused((i) => Math.max(i - 1, 0));
    } else if (e.key === "Home") {
      setFocused(0);
    } else if (e.key === "End") {
      setFocused(processed.length - 1);
    }
  }

  return (
    // `min-w-0` para que la tabla pueda encoger por debajo del ancho de su
    // contenido en vez de empujar a su contenedor. NO resuelve por sí solo el
    // desbordamiento de Partidos en móvil --medido: sigue en 110 px-- pero es
    // correcto y quita una de las causas posibles (2026-08-31).
    <div className="min-w-0 rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex min-w-0 flex-wrap items-center gap-2 border-b border-[var(--border)] p-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={filterPlaceholder}
          aria-label={filterPlaceholder}
          className="w-full min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm sm:w-auto sm:min-w-48"
        />
        <span className="text-xs text-[var(--muted)]">
          {processed.length} de {rows.length}
        </span>
        <button
          data-picker=""
          onClick={() => setShowPicker((s) => !s)}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm"
          aria-expanded={showPicker}
        >
          Columnas
        </button>
        <button
          onClick={exportCsv}
          className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm"
        >
          CSV
        </button>
      </div>

      {showPicker && (
        <div
          data-picker=""
          className="flex flex-wrap gap-3 border-b border-[var(--border)] bg-[var(--surface-2)] p-3"
        >
          {columns.map((c) => (
            <label key={c.key} className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={!hidden.has(c.key)}
                onChange={() =>
                  setHidden((h) => {
                    const next = new Set(h);
                    if (next.has(c.key)) {
                      next.delete(c.key);
                    } else {
                      next.add(c.key);
                    }
                    return next;
                  })
                }
              />
              {c.header}
              {nombreLargo(c.header) && (
                <span className="text-[var(--muted)]">
                  {" "}
                  · {nombreLargo(c.header)}
                </span>
              )}
            </label>
          ))}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-[var(--surface-2)]">
            <tr>
              {visible.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  onClick={() => toggleSort(c.key)}
                  // Enter Y Espacio: son las dos teclas con las que se
                  // activa cualquier control, y aquí sólo funcionaba Enter.
                  // Peor: sin `preventDefault` el Espacio hacía scroll de
                  // página, así que quien lo pulsaba para ordenar perdía el
                  // sitio en la tabla y no ordenaba nada (2026-08-31).
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      toggleSort(c.key);
                    }
                  }}
                  tabIndex={0}
                  aria-sort={
                    sortKey === c.key
                      ? descending
                        ? "descending"
                        : "ascending"
                      : "none"
                  }
                  className={clsx(
                    "cursor-pointer whitespace-nowrap px-3 py-2 text-xs font-medium text-[var(--muted)]",
                    c.align === "left" ? "text-left" : "text-right",
                  )}
                >
                  {/* Una abreviatura sin nada que la explique obliga a
                      recordar doce claves. El título la enseña al ratón y
                      `aria-label` se la da al lector de pantalla, que si no
                      leería «FO» y ya. */}
                  <span
                    title={nombreLargo(c.header)}
                    aria-label={nombreLargo(c.header)}
                  >
                    {c.header}
                  </span>
                  {sortKey === c.key && (descending ? " ↓" : " ↑")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody tabIndex={0} onKeyDown={onKeyDown}>
            {processed.length === 0 && (
              <tr>
                <td
                  colSpan={visible.length}
                  className="p-8 text-center text-[var(--muted)]"
                >
                  {/* Vacío por el filtro y vacío porque no hay datos son dos
                      cosas distintas, y hasta el 2026-08-31 las dos decían
                      «Sin datos todavía»: un diagnóstico equivocado --las
                      filas existían-- y un remedio equivocado, porque
                      «todavía» invita a esperar cuando lo que hace falta es
                      borrar el filtro. Además no había salida a mano. */}
                  {filter.trim() && rows.length > 0 ? (
                    <>
                      Ningún resultado para{" "}
                      <b className="text-[var(--text)]">«{filter.trim()}»</b>,
                      de {rows.length} en total.
                      <button
                        type="button"
                        onClick={() => setFilter("")}
                        className="ml-2 rounded border border-[var(--border)] px-2 py-0.5 text-xs hover:border-[var(--accent)] hover:text-[var(--text)]"
                      >
                        Quitar el filtro
                      </button>
                    </>
                  ) : (
                    emptyMessage
                  )}
                </td>
              </tr>
            )}
            {processed.map((row, i) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                className={clsx(
                  "border-t border-[var(--border)]",
                  onRowClick && "cursor-pointer hover:bg-[var(--surface-2)]/70",
                  i === focused && "bg-[var(--accent-soft)]",
                  selectedRowKey === rowKey(row) &&
                    "bg-[var(--accent-soft)] ring-1 ring-inset ring-[var(--accent)]",
                )}
              >
                {visible.map((c) => (
                  <td
                    key={c.key}
                    className={clsx(
                      "px-3 py-1.5 tabular-nums",
                      c.align === "left" ? "text-left" : "text-right",
                    )}
                  >
                    {c.render ? c.render(row) : c.value(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
