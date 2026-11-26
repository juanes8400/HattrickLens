/** El veredicto de un sector o de una subida, en su color. */
import type { ReactNode } from "react";
import type { SkillsTone } from "../../services/api";
import { COLOR } from "./comun";

export function Pastilla({
  tone,
  children,
}: {
  tone: SkillsTone;
  children: ReactNode;
}) {
  return (
    <span
      className="whitespace-nowrap rounded-md px-2 py-0.5 text-xs"
      style={{
        background: `color-mix(in srgb, ${COLOR[tone]} 14%, transparent)`,
        color: COLOR[tone],
      }}
    >
      {children}
    </span>
  );
}
