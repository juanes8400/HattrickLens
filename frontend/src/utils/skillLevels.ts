const SKILL_LEVELS = [
  "nulo", "desastroso", "horrible", "pobre", "débil", "insuficiente",
  "aceptable", "bueno", "excelente", "formidable", "destacado", "brillante",
  "magnífico", "clase mundial", "sobrenatural", "titánico", "extraterrestre",
  "mítico", "mágico", "utópico", "divino",
];

export function skillLevelLabel(level: number, capitalize = false): string {
  const label = SKILL_LEVELS[level] ?? `divino+${level - 20}`;
  return capitalize ? label.charAt(0).toUpperCase() + label.slice(1) : label;
}
