import { Panel } from "../components/Panels";
import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import autor from "../assets/autor.svg";

/** Quién hay detrás de esto.
 *
 *  2026-09-02, pedido del usuario. La aplicación explica de dónde sale cada
 *  número --para eso está Transparencia-- y no decía de dónde sale ella. En
 *  una herramienta hecha por una persona para una comunidad pequeña, eso no
 *  es vanidad: es a quién escribirle cuando algo no cuadra.
 *
 *  Va abajo del todo en el menú y sin datos del club, porque es lo único de
 *  la aplicación que no depende de haber sincronizado nada.
 */
export function AutorPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Autor</h1>
        <p className="text-sm text-[var(--muted)]">
          Quién hace HT Lens, y con qué criterio.
        </p>
      </header>

      <Panel title="Juan Esteban" meta="Pulgas Arrechas · Colombia">
        <div className="flex flex-col gap-5 p-4 sm:flex-row sm:items-start">
          {/* El retrato no se encoge ni estira: es un dibujo con contorno, y
              deformarlo se nota mucho más que en una fotografía. */}
          <img
            src={autor}
            alt="Retrato dibujado del autor de HT Lens"
            width={112}
            height={112}
            className="h-28 w-28 shrink-0 self-center sm:self-start"
          />
          <div className="prosa space-y-3 text-sm leading-relaxed">
            <p>
              HT Lens nació de una hoja de cálculo que se hizo demasiado grande.
              Es una herramienta personal que mira los datos de tu propio club y
              saca de ellos lo que Hattrick no enseña: cuántas semanas le faltan
              a un jugador para subir, qué habilidad conviene entrenar en la
              cantera, qué te dejó de verdad cada traspaso.
            </p>
            <p>
              Todo lo que ves está calculado en tu servidor, a partir de lo que
              tú sincronizas. No hay servicios de terceros ni cookies de
              publicidad, y el historial lo construye la propia aplicación
              porque Hattrick sólo publica el estado de hoy.
            </p>
            <p className="text-[var(--muted)]">
              Ningún número se enseña sin poder explicarlo:{" "}
              <EnlaceATransparencia
                seccion="entrenamiento"
                calculo="semanas-al-pop"
              >
                cómo se calcula cada uno
              </EnlaceATransparencia>
              .
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}
