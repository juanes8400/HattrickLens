/**
 * El reparto de una línea: cuántos juegan por dentro.
 *
 * Lo comparten Alineación y el once ideal de la liga (2026-08-19), porque es
 * el mismo control de Hattrick Control y tiene que comportarse igual en las
 * dos: solo se pregunta por los del centro, y los de banda salen por resta
 * (4 defensas menos 3 centrales son 1 lateral). Cuando la línea admite un
 * único reparto, el botón sale marcado y sin efecto en vez de desaparecer,
 * para que se vea que no hay elección.
 */
export function SplitSelector({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: number | undefined;
  options: number[];
  onChange: (v: number) => void;
}) {
  if (options.length === 0) return null;
  return (
    <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
      {label}
      <span className="flex overflow-hidden rounded border border-[var(--border)]">
        {options.map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onChange(n)}
            disabled={options.length === 1}
            className={`px-2.5 py-1 tabular-nums ${
              n === value
                ? "bg-[var(--accent)] text-white"
                : "bg-[var(--surface)] text-[var(--text)]"
            } ${options.length === 1 ? "cursor-default opacity-70" : ""}`}
          >
            {n}
          </button>
        ))}
      </span>
    </label>
  );
}
