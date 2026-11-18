/** Clasificación de jugadores: su propio módulo desde el 2026-11-18.
 *
 *  Antes era una pestaña de Habilidades. El usuario la quiso con entrada
 *  propia en el menú, en «Club» y justo debajo de Jugadores, y que dejara de
 *  estar en Habilidades («una pantalla, un sitio»). Lo que se ve dentro no
 *  cambia: las mismas cuatro pestañas de `components/clases`. */
import { ClasesDeJugador } from "../components/clases/ClasesDeJugador";
import { tx } from "../i18n/tx";
import { nombreNav } from "../layouts/navegacion";

export function ClasificacionPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">
          {nombreNav("Clasificación de jugadores", "clasificacion")}
        </h1>
        <p className="text-sm text-[var(--muted)]">
          {tx(
            "Cuatro formas de partir la plantilla: quién juega, quién rinde lo que cobra, en qué momento de su carrera está cada uno y los grupos que tú decidas.",
          )}
        </p>
      </header>
      {/* El marco de un Panel, sin su cabecera: «Agrupar por» ya va dentro,
          junto a las pestañas, y un título encima lo repetiría. */}
      <section className="rounded-lg border border-[var(--border)] bg-[var(--surface)]">
        <ClasesDeJugador />
      </section>
    </div>
  );
}
