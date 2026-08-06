import type { ReactNode } from "react";
import clsx from "clsx";

/**
 * Control segmentado tipo píldora (referencia visual del usuario 2026-08-03:
 * "🏠 Inicio" / "</> Code") — patrón general para partir pantallas largas en
 * secciones, en vez de obligar a hacer scroll por todo para llegar a la
 * última parte.
 */
export function Tabs<T extends string>({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: T; label: string; icon?: ReactNode }[];
  active: T;
  onChange: (key: T) => void;
}) {
  return (
    <div
      role="tablist"
      className="inline-flex gap-1 rounded-full border border-[var(--border)] bg-[var(--surface-2)] p-1"
    >
      {tabs.map((t) => (
        <button
          key={t.key}
          role="tab"
          aria-selected={active === t.key}
          onClick={() => onChange(t.key)}
          className={clsx(
            "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
            active === t.key
              ? "bg-[var(--surface)] text-[var(--text)] shadow-sm"
              : "text-[var(--muted)] hover:text-[var(--text)]",
          )}
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </div>
  );
}
