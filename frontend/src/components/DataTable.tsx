import { useMemo, useState } from "react";
import clsx from "clsx";

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
  emptyMessage?: string;
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
  emptyMessage = "Sin datos todavía.",
  selectedRowKey,
  onRowClick,
}: Props<T>) {
  const [sortKey, setSortKey] = useState(initialSort ?? columns[0]?.key);
  const [descending, setDescending] = useState(initialDescending);
  const [filter, setFilter] = useState("");
  const [hidden, setHidden] = useState<Set<string>>(
    () => new Set(columns.filter((c) => c.optional).map((c) => c.key)),
  );
  const [showPicker, setShowPicker] = useState(false);
  const [focused, setFocused] = useState(0);

  const visible = columns.filter((c) => !hidden.has(c.key));

  const processed = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const filtered = needle
      ? rows.filter((r) =>
          visible.some((c) => String(c.value(r)).toLowerCase().includes(needle)),
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
            return v.includes(",") || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v;
          })
          .join(","),
      )
      .join("\n");
    const blob = new Blob([`${header}\n${body}`], { type: "text/csv;charset=utf-8" });
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
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)] p-3">
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={filterPlaceholder}
          aria-label={filterPlaceholder}
          className="min-w-48 flex-1 rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm"
        />
        <span className="text-xs text-[var(--muted)]">
          {processed.length} de {rows.length}
        </span>
        <button
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
        <div className="flex flex-wrap gap-3 border-b border-[var(--border)] bg-[var(--surface-2)] p-3">
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
                  onKeyDown={(e) => e.key === "Enter" && toggleSort(c.key)}
                  tabIndex={0}
                  aria-sort={
                    sortKey === c.key ? (descending ? "descending" : "ascending") : "none"
                  }
                  className={clsx(
                    "cursor-pointer whitespace-nowrap px-3 py-2 text-xs font-medium text-[var(--muted)]",
                    c.align === "left" ? "text-left" : "text-right",
                  )}
                >
                  {c.header}
                  {sortKey === c.key && (descending ? " ↓" : " ↑")}
                </th>
              ))}
            </tr>
          </thead>
          <tbody tabIndex={0} onKeyDown={onKeyDown}>
            {processed.length === 0 && (
              <tr>
                <td colSpan={visible.length} className="p-8 text-center text-[var(--muted)]">
                  {emptyMessage}
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
                  selectedRowKey === rowKey(row) && "bg-[var(--accent-soft)] ring-1 ring-inset ring-[var(--accent)]",
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
