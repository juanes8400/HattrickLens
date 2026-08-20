import { Link } from "react-router-dom";

/**
 * Every player name in the product is a link to their hub page — the one
 * navigation principle that ties all the tables together (docs/68-catalogo
 * -vistas.md: "todo lo enlazable se enlaza"). One component so it's applied
 * consistently instead of re-implemented per table.
 */
export function PlayerLink({
  htPlayerId,
  name,
  onDark = false,
}: {
  htPlayerId: number;
  name: string;
  /** Sobre el verde de la cancha: el color de texto del tema es casi negro y
   *  ahí no se lee. Reportado el 2026-08-19 en Alineación. */
  onDark?: boolean;
}) {
  return (
    <Link
      to={`/players/${htPlayerId}`}
      className={
        onDark
          ? "text-white underline decoration-white/30 underline-offset-2 hover:decoration-white"
          : "text-[var(--text)] underline decoration-[var(--border)] underline-offset-2 hover:text-[var(--accent)] hover:decoration-[var(--accent)]"
      }
    >
      {name}
    </Link>
  );
}
