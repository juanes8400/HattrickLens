import { MINIMUM_LINEUP_PLAYERS } from "../utils/lineupAvailability";

export function LineupAvailabilityNotice({
  availableCount,
  warning,
  canRestore = false,
  onRestore,
}: {
  availableCount: number;
  warning?: string | null;
  canRestore?: boolean;
  onRestore?: () => void;
}) {
  const noun =
    availableCount === 1 ? "jugador disponible" : "jugadores disponibles";

  return (
    <section
      role="alert"
      className="rounded-lg border border-[var(--warning)] bg-[var(--surface)] p-5"
    >
      <h2 className="font-semibold">No se puede calcular el once</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        {warning ?? (
          <>
            Hay {availableCount} {noun} y hacen falta {MINIMUM_LINEUP_PLAYERS}{" "}
            para calcular una alineación completa.
          </>
        )}
      </p>
      <p className="mt-2 text-xs text-[var(--muted)]">
        La página sigue disponible. La optimización se reanudará cuando haya al
        menos {MINIMUM_LINEUP_PLAYERS} jugadores disponibles.
      </p>
      {canRestore && onRestore && (
        <button
          type="button"
          onClick={onRestore}
          className="mt-3 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:border-[var(--accent)] hover:text-[var(--accent)]"
        >
          Devolver a todos al reparto
        </button>
      )}
    </section>
  );
}
