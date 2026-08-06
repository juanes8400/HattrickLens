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
}: {
  htPlayerId: number;
  name: string;
}) {
  return (
    <Link
      to={`/players/${htPlayerId}`}
      className="text-[var(--text)] underline decoration-[var(--border)] underline-offset-2 hover:text-[var(--accent)] hover:decoration-[var(--accent)]"
    >
      {name}
    </Link>
  );
}
