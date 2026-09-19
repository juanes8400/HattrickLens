import { useTranslation } from "react-i18next";
import { PitchField } from "../components/PitchField";
import { decimal } from "../hooks/useFormat";
import type {
  TeamOverviewGroup,
  TeamOverviewPitchSlot,
  TeamOverviewSpecialRole,
} from "../services/api";

/**
 * La cancha de «Mejor posición»: donde rinde más cada jugador.
 *
 * Vivía dentro de la pantalla de Habilidades y se mudó a Equipo el 2026-09-19,
 * pedido por el usuario. Vive aquí, y no en la pantalla, porque la pregunta
 * que responde --a quién tengo y para qué puesto-- es la de Equipo, mientras
 * que Habilidades es la evolución semana a semana.
 */
function PitchSlotCard({ slot }: { slot: TeamOverviewPitchSlot }) {
  const { t } = useTranslation();
  const best = slot.bestRating;
  return (
    <div className="w-44 shrink-0 rounded-lg border border-white/20 bg-black/45 p-2 text-center shadow-xl backdrop-blur">
      <div className="text-[11px] text-white/70">{slot.label}</div>

      {/* El número grande es CUÁNTOS tienen esta línea como su mejor puesto
          la lectura que se busca de un vistazo al mirar la cancha. */}
      <div className="mt-0.5 text-3xl font-semibold leading-none tabular-nums text-white">
        {slot.count}
      </div>
      <div className="text-[10px] text-white/50">
        {slot.count === 1
          ? t("equipo.loTiene", "lo tiene como mejor")
          : t("equipo.loTienen", "lo tienen como mejor")}
      </div>

      {/* Debajo y en pequeño, el mejor de la línea medido sobre TODA la
          plantilla. Es otra población que el conteo de arriba, por eso la
          línea divisoria. */}
      <div className="mt-1.5 space-y-0.5 border-t border-white/15 pt-1">
        {best == null ? (
          <div className="text-[10px] text-white/40">
            {t("equipo.sinRating", "sin rating")}
          </div>
        ) : (
          <>
            {slot.topPlayer && (
              <div
                className="truncate text-[10px] text-white/80"
                title={slot.topPlayer}
              >
                {slot.topPlayer}
              </div>
            )}
            <div className="text-[10px] tabular-nums text-white/70">
              {t("equipo.max", "máx {{v}}", { v: decimal(best, 2) })}
              {slot.averageRating != null &&
                ` · ${t("equipo.media", "media {{v}}", {
                  v: decimal(slot.averageRating, 2),
                })}`}
            </div>
            {slot.bestVariantLabel && (
              <div
                className="truncate text-[10px] text-white/45"
                title={slot.bestVariantLabel}
              >
                {slot.bestVariantLabel}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

/** Capitán y lanzador de faltas viven FUERA del campo, en una columna al
 *  lado y con otro aspecto: son recomendaciones de rol, no puestos, y su
 *  puntuación usa otra fórmula, nada de la barra 0-20 de las posiciones. */
function SpecialRoles({ roles }: { roles: TeamOverviewSpecialRole[] }) {
  const { t } = useTranslation();
  if (roles.length === 0) return null;
  return (
    <div className="flex shrink-0 flex-col gap-2 sm:w-48">
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
        {t("equipo.roles", "Roles del equipo")}
      </div>
      {roles.map((role) => (
        <div
          key={role.key}
          className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] p-2"
        >
          <div className="text-[11px] text-[var(--muted)]">{role.label}</div>
          <div
            className="mt-0.5 truncate text-sm font-medium"
            title={role.topPlayer ?? ""}
          >
            {role.topPlayer ?? "-"}
          </div>
          {role.rating != null && (
            <div className="text-[10px] tabular-nums text-[var(--muted)]">
              {t("equipo.indice", "índice {{v}}", {
                v: decimal(role.rating, 1),
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** Cancha de portería (abajo) a delantera (arriba), como se lee un campo al
 *  atacar. Extremo y Medio comparten fila, y Lateral con Defensa central,
 *  porque en el campo real ocupan la misma altura. */
export function MejorPosicion({ group }: { group: TeamOverviewGroup }) {
  const { t } = useTranslation();
  const byKey = new Map(group.pitch.map((slot) => [slot.key, slot]));
  const rows: string[][] = [
    ["forward"],
    ["winger", "inner_midfield"],
    ["wingback", "central_defender"],
    ["keeper"],
  ];
  return (
    <div className="flex flex-col gap-4 p-4 lg:flex-row lg:items-start">
      <PitchField
        ariaLabel={t(
          "equipo.canchaAria",
          "Mejor posición de cada jugador sobre la cancha",
        )}
        className="min-w-0 flex-1 rounded-xl"
      >
        <div className="relative flex flex-col gap-3 px-4 py-6">
          {rows.map((row) => (
            <div
              key={row.join("-")}
              className="flex flex-wrap justify-center gap-3"
            >
              {row.map((key) => {
                const slot = byKey.get(key);
                return slot ? <PitchSlotCard key={key} slot={slot} /> : null;
              })}
            </div>
          ))}
        </div>
      </PitchField>
      <SpecialRoles roles={group.specialRoles} />
    </div>
  );
}
