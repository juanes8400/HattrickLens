import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();

  return (
    <section
      role="alert"
      className="rounded-lg border border-[var(--warning)] bg-[var(--surface)] p-5"
    >
      <h2 className="font-semibold">
        {t("alineacion.noSePuede", "No se puede calcular el once")}
      </h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        {warning ??
          (availableCount === 1
            ? t(
                "alineacion.hayUno",
                "Hay {{n}} jugador disponible y hacen falta {{minimo}} para calcular una alineación completa.",
                { n: availableCount, minimo: MINIMUM_LINEUP_PLAYERS },
              )
            : t(
                "alineacion.hayVarios",
                "Hay {{n}} jugadores disponibles y hacen falta {{minimo}} para calcular una alineación completa.",
                { n: availableCount, minimo: MINIMUM_LINEUP_PLAYERS },
              ))}
      </p>
      <p className="mt-2 text-xs text-[var(--muted)]">
        {t(
          "alineacion.seReanudara",
          "La página sigue disponible. La optimización se reanudará cuando haya al menos {{minimo}} jugadores disponibles.",
          { minimo: MINIMUM_LINEUP_PLAYERS },
        )}
      </p>
      {canRestore && onRestore && (
        <button
          type="button"
          onClick={onRestore}
          className="mt-3 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:border-[var(--accent)] hover:text-[var(--accent)]"
        >
          {t("alineacion.devolverTodosReparto", "Devolver a todos al reparto")}
        </button>
      )}
    </section>
  );
}
