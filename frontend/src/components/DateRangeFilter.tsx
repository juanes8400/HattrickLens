import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

export interface DateRange {
  start: string | null;
  end: string | null;
}

const EMPTY_RANGE: DateRange = { start: null, end: null };

/** Recorta un eje de fechas con un calendario nativo en vez de la barra de
 * dataZoom, misma interacción en cualquier gráfica de serie temporal. */
export function useDateRangeFilter(dates: string[]): {
  range: DateRange;
  setRange: (r: DateRange) => void;
  indices: number[];
  min: string | null;
  max: string | null;
} {
  const [range, setRange] = useState<DateRange>(EMPTY_RANGE);
  const days = useMemo(() => dates.map((d) => d.slice(0, 10)), [dates]);
  const min = days[0] ?? null;
  const max = days[days.length - 1] ?? null;
  const indices = useMemo(
    () =>
      days.reduce<number[]>((acc, day, i) => {
        if (
          (!range.start || day >= range.start) &&
          (!range.end || day <= range.end)
        ) {
          acc.push(i);
        }
        return acc;
      }, []),
    [days, range],
  );
  return { range, setRange, indices, min, max };
}

export function DateRangeFilter({
  range,
  onChange,
  min,
  max,
}: {
  range: DateRange;
  onChange: (r: DateRange) => void;
  min: string | null;
  max: string | null;
}) {
  const { t } = useTranslation();
  if (!min || !max || min === max) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--muted)]">
      <label className="flex items-center gap-1.5">
        {t("comun.desde", "Desde")}
        <input
          type="date"
          className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[var(--text)]"
          min={min}
          max={range.end ?? max}
          value={range.start ?? ""}
          onChange={(e) =>
            onChange({ ...range, start: e.target.value || null })
          }
        />
      </label>
      <label className="flex items-center gap-1.5">
        {t("comun.hasta", "Hasta")}
        <input
          type="date"
          className="rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[var(--text)]"
          min={range.start ?? min}
          max={max}
          value={range.end ?? ""}
          onChange={(e) => onChange({ ...range, end: e.target.value || null })}
        />
      </label>
      {(range.start || range.end) && (
        <button
          type="button"
          className="text-[var(--accent)] underline underline-offset-2"
          onClick={() => onChange(EMPTY_RANGE)}
        >
          {t("comun.verTodo", "ver todo")}
        </button>
      )}
    </div>
  );
}
