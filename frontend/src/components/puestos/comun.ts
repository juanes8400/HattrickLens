/** Lo que comparten las pestañas Profundidad y Cuello de botella de Puestos:
 *  el color de cada veredicto y cómo se escriben los números. La pastilla
 *  vive al lado, en `Pastilla.tsx`.
 *
 *  Vivían dentro de `SkillsPage`; salieron con el Cuello de botella, que es su
 *  propia pestaña desde la 8.2.0 (2026-11-26). */
import i18n from "../../i18n";
import { terminoOficial } from "../../i18n/glosario";
import type { SkillsTone } from "../../services/api";

export const COLOR: Record<SkillsTone, string> = {
  danger: "var(--danger)",
  warning: "var(--warning)",
  ok: "var(--positive)",
};

/** «+82%», «−12%», «0%»: la ventaja sobre el mejor rival del sector. */
export function ventaja(pct: number) {
  const n = Math.round(pct);
  return n > 0 ? `+${n}%` : n < 0 ? `−${Math.abs(n)}%` : "0%";
}

/** 16,8 · 211: con coma decimal y sin ceros sobrantes (en español; cada
 *  idioma con su separador). */
export function decimal(n: number | undefined) {
  // Tolera un dato guardado en el navegador con la forma de antes: la página
  // no puede romperse porque llegue un campo que todavía no existía.
  return (n ?? 0).toLocaleString(i18n.language, { maximumFractionDigits: 1 });
}

/** «Defensa» como SECTOR es Defence, y como habilidad es Defending: cada
 *  familia del glosario tiene su propia palabra. */
const CLAVE_DE_SECTOR: Record<string, string> = {
  defensa: "Defense",
  mediocampo: "Midfield",
  ataque: "Attack",
};
export const sectorOficial = (clave: string, respaldo: string) =>
  terminoOficial("sectores", CLAVE_DE_SECTOR[clave] ?? "", respaldo);
