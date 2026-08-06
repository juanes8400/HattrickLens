import clsx from "clsx";
import { PlayerLink } from "./PlayerLink";
import type { PostMatchTraining } from "../services/api";

const SLOT_COORDS: Record<number, { x: number; y: number }> = {
  1: { x: 50, y: 91 },
  100: { x: 50, y: 91 },
  2: { x: 19, y: 72 },
  101: { x: 19, y: 72 },
  3: { x: 35, y: 74 },
  102: { x: 35, y: 74 },
  4: { x: 50, y: 75 },
  103: { x: 50, y: 75 },
  5: { x: 65, y: 74 },
  104: { x: 65, y: 74 },
  6: { x: 81, y: 72 },
  105: { x: 81, y: 72 },
  7: { x: 15, y: 49 },
  106: { x: 15, y: 49 },
  8: { x: 35, y: 51 },
  107: { x: 35, y: 51 },
  9: { x: 50, y: 50 },
  108: { x: 50, y: 50 },
  10: { x: 65, y: 51 },
  109: { x: 65, y: 51 },
  11: { x: 85, y: 49 },
  110: { x: 85, y: 49 },
  12: { x: 35, y: 25 },
  111: { x: 35, y: 25 },
  13: { x: 50, y: 21 },
  112: { x: 50, y: 21 },
  14: { x: 65, y: 25 },
  113: { x: 65, y: 25 },
};

function exposureTone(exposure: number): string {
  if (exposure >= 0.99) return "border-[var(--positive)] bg-[var(--positive)]/20";
  if (exposure > 0) return "border-[var(--warning)] bg-[var(--warning)]/20";
  return "border-[var(--border)] bg-[var(--surface)]/90 opacity-60";
}

function exposureLabel(exposure: number): string {
  if (exposure >= 0.99) return "full";
  if (exposure > 0) return `${Math.round(exposure * 100)}%`;
  return "0%";
}

export function TrainingPitch({
  data,
  selectedTrainingType,
}: {
  data: PostMatchTraining;
  selectedTrainingType: number;
}) {
  const cards = data.players
    .flatMap((player) => {
      const grouped = new Map<
        number,
        {
          positionCode: number;
          position: string;
          minutes: number;
          ratings: number[];
          matches: number;
        }
      >();
      for (const segment of player.segments) {
        const current = grouped.get(segment.positionCode) ?? {
          positionCode: segment.positionCode,
          position: segment.position,
          minutes: 0,
          ratings: [],
          matches: 0,
        };
        current.minutes += segment.minutes;
        current.matches += 1;
        if (segment.rating != null) current.ratings.push(segment.rating);
        grouped.set(segment.positionCode, current);
      }
      return [...grouped.values()].map((segment) => ({
        player,
        segment,
        key: `${player.htPlayerId}-${segment.positionCode}`,
        exposure: player.exposureByTrainingType[String(selectedTrainingType)] ?? 0,
        coords: SLOT_COORDS[segment.positionCode] ?? { x: 50, y: 50 },
      }));
    })
    .sort((a, b) => a.coords.y - b.coords.y || a.coords.x - b.coords.x);

  if (!cards.length) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-8 text-center text-sm text-[var(--muted)]">
        Sin posiciones jugadas para pintar la cancha. Sincroniza playerdetails o matchlineup.
      </div>
    );
  }

  return (
    <div
      className="relative min-h-[620px] overflow-hidden rounded-xl border border-[var(--border)]"
      aria-label="Cancha de exposicion de entrenamiento"
    >
      <div className="absolute inset-0 bg-gradient-to-b from-emerald-950 via-emerald-900 to-emerald-950" />
      <div className="absolute inset-4 rounded-[2rem] border-2 border-white/25" />
      <div className="absolute left-1/2 top-1/2 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/20" />
      <div className="absolute left-4 right-4 top-1/2 border-t-2 border-white/20" />
      <div className="absolute bottom-4 left-1/2 h-24 w-56 -translate-x-1/2 rounded-t-2xl border-x-2 border-t-2 border-white/20" />
      <div className="absolute left-1/2 top-4 h-24 w-56 -translate-x-1/2 rounded-b-2xl border-x-2 border-b-2 border-white/20" />

      <div className="absolute left-4 top-4 rounded-full bg-black/30 px-3 py-1 text-xs text-white/80">
        Verde = full · Amarillo = parcial · Gris = sin entrenamiento
      </div>

      {cards.map(({ player, segment, key, exposure, coords }, idx) => (
        <div
          key={key}
          className={clsx(
            "absolute w-44 -translate-x-1/2 -translate-y-1/2 rounded-lg border p-2 shadow-xl backdrop-blur",
            exposureTone(exposure),
          )}
          style={{
            left: `${coords.x}%`,
            top: `${coords.y + (idx % 2 ? 1.7 : -1.7)}%`,
          }}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 text-sm font-semibold text-white">
              <PlayerLink htPlayerId={player.htPlayerId} name={player.name} />
            </div>
            <span className="rounded bg-black/30 px-1.5 py-0.5 text-[10px] font-semibold text-white">
              {exposureLabel(exposure)}
            </span>
          </div>
          <div className="mt-1 text-[11px] leading-snug text-white/75">
            {segment.position} · {segment.minutes} min
            {segment.matches > 1 && ` · ${segment.matches} partidos`}
            {segment.ratings.length > 0 &&
              ` · rating ${(segment.ratings.reduce((a, b) => a + b, 0) / segment.ratings.length).toFixed(1)}`}
          </div>
        </div>
      ))}
    </div>
  );
}
