/**
 * Especialidad con icono.
 *
 * El backend manda la etiqueta ya traducida (`SPECIALTIES` en
 * `ht_constants.py`), no el número, así que el mapa se indexa por texto. Para
 * que un acento o una mayúscula no dejen un jugador sin icono, la clave se
 * normaliza antes de buscar — dos sitios del backend escriben la ausencia
 * distinto ("" en plantilla, "Ninguna" en Saldo por jugador) y ambos tienen
 * que caer en el mismo hueco.
 */
const ICONS: Record<string, string> = {
  tecnico: "🎯",       // precisión: define fino, no por fuerza
  rapido: "⚡",        // velocidad
  potente: "💪",       // fuerza — y se crece con la lluvia
  imprevisible: "🎲",  // el azar es literalmente lo que hace
  cabeceador: "🗿",    // una cabeza, reconocible a 16 px
  estoico: "🛡️",      // aguanta: resiste lesiones
  influyente: "🤝",    // no brilla solo, levanta a los de al lado
};

/** Cómo escribe el backend "este jugador no tiene especialidad". */
const NONE = new Set(["", "ninguna", "sin especialidad"]);

function normalize(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .normalize("NFD")
    // Rango de tildes combinantes, escrito con escapes para que el patrón no
    // dependa de cómo se guarde este fichero.
    .replace(/[̀-ͯ]/g, "");
}

/** El emoji de una especialidad, o `null` si no la tiene (o es desconocida —
 *  Hattrick podría añadir una y no se inventa un icono para ella). */
export function specialtyIcon(specialty: string | null | undefined): string | null {
  if (!specialty) return null;
  return ICONS[normalize(specialty)] ?? null;
}

/** Texto de la especialidad tal como debe leerse, con la ausencia resuelta. */
export function specialtyLabel(specialty: string | null | undefined): string {
  if (!specialty || NONE.has(normalize(specialty))) return "Sin especialidad";
  return specialty;
}

/**
 * Icono + texto. El icono NO sustituye al nombre: obligar a memorizar siete
 * símbolos no ayuda a nadie, y en las tablas el filtro busca sobre el texto.
 *
 * `iconOnly` existe para los sitios apretados —una tarjeta sobre la cancha—
 * donde no cabe la palabra; ahí el nombre viaja en el `title`, nunca se pierde.
 */
export function Specialty({
  specialty,
  iconOnly = false,
}: {
  specialty: string | null | undefined;
  iconOnly?: boolean;
}) {
  const icon = specialtyIcon(specialty);
  const label = specialtyLabel(specialty);

  if (iconOnly) {
    // Sin especialidad no se pinta nada: un hueco dice lo mismo y no compite
    // por la atención con los que sí tienen una.
    if (!icon) return null;
    return (
      <span title={label} aria-label={label}>
        {icon}
      </span>
    );
  }

  if (!icon) {
    return <span className="text-[var(--muted)]">{label}</span>;
  }
  return (
    <span className="whitespace-nowrap">
      {/* `aria-hidden`: el lector de pantalla ya lee el nombre que va al lado,
          y repetir "trofeo directo al blanco" sería ruido. */}
      <span aria-hidden="true">{icon}</span> {label}
    </span>
  );
}
