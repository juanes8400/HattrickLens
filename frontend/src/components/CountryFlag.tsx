import clsx from "clsx";
import "flag-icons/css/flag-icons.min.css";
import { countryCodeFromName } from "../utils/countryCodes";

interface CountryFlagProps {
  code: string | null | undefined;
  country?: string | null;
  className?: string;
}

/** Bandera oficial a partir del CountryCode de worlddetails.xml. */
export function CountryFlag({ code, country, className }: CountryFlagProps) {
  const normalized = code?.trim().toLowerCase() || countryCodeFromName(country);
  if (!normalized || !/^[a-z]{2}$/.test(normalized)) {
    return (
      <span
        aria-label={country ? `País: ${country}` : "País sin identificar"}
        className={clsx(
          "inline-flex h-3.5 w-5 shrink-0 items-center justify-center rounded-sm border border-[var(--border)] bg-[var(--surface-2)] text-[9px] text-[var(--muted)]",
          className,
        )}
        role="img"
        title={country ?? "País sin identificar"}
      >
        ·
      </span>
    );
  }

  return (
    <span
      aria-label={`Bandera de ${country ?? normalized.toUpperCase()}`}
      className={clsx(
        "fi shrink-0 rounded-[2px] shadow-[0_0_0_1px_color-mix(in_srgb,var(--border)_75%,transparent)]",
        `fi-${normalized}`,
        className,
      )}
      role="img"
      title={country ?? normalized.toUpperCase()}
    />
  );
}

interface CountryCellProps extends CountryFlagProps {
  fallback?: string;
  compact?: boolean;
}

export function CountryCell({
  code,
  country,
  fallback = "-",
  compact = false,
}: CountryCellProps) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <CountryFlag code={code} country={country} />
      <span className={clsx(compact && "text-xs", "text-[var(--muted)]")}>
        {country ?? fallback}
      </span>
    </span>
  );
}
