import type { ClubStaffRole } from "../services/api";
import {
  staffEffectLines,
  trainingStaffLevelColor,
} from "../utils/staffEffects";

export function StaffRoleCard({ role }: { role: ClubStaffRole }) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-[var(--muted)]">{role.label}</span>
        <span className="tabular-nums text-sm font-semibold">{role.level}</span>
      </div>
      {role.members.length > 0 ? (
        <ul className="mt-2 space-y-0.5 text-xs text-[var(--muted)]">
          {role.members.map((member, i) => (
            <li key={i} className="flex justify-between gap-2">
              <span className="truncate">{member.name}</span>
              <span
                className={`tabular-nums shrink-0 ${
                  role.key === "assistant_trainer_levels"
                    ? trainingStaffLevelColor(member.level)
                    : ""
                }`}
              >
                {member.level}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p
          className={`mt-2 text-xs ${
            role.key === "assistant_trainer_levels"
              ? "font-medium text-[var(--danger)]"
              : "text-[var(--muted)]"
          }`}
        >
          Sin nadie en este puesto.
        </p>
      )}
      {role.level > 0 && role.effect && (
        <ul className="mt-2 space-y-0.5 border-t border-[var(--border)] pt-2 text-xs text-[var(--positive)]">
          {staffEffectLines(role.effect).map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
