/** Las sumas de la Distribución del salario, aparte del componente para
 *  poder probarlas. */
import type { Grupo } from "./colores";

export interface ParteDelSalario {
  grupo: Grupo;
  salario: number;
  /** Sobre el salario de toda la plantilla, de 0 a 100. */
  pct: number;
}

export function repartoDelSalario(grupos: Grupo[]): {
  total: number;
  partes: ParteDelSalario[];
} {
  const sumas = grupos.map((g) => ({
    grupo: g,
    salario: g.jugadores.reduce((t, j) => t + j.salary, 0),
  }));
  const total = sumas.reduce((t, s) => t + s.salario, 0);
  return {
    total,
    partes: sumas.map((s) => ({
      ...s,
      pct: total > 0 ? (s.salario / total) * 100 : 0,
    })),
  };
}
