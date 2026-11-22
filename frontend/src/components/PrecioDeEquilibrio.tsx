import { Fragment, useId } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { tx } from "../i18n/tx";

/** Lo que explica «Precio de equilibrio» al pasar el ratón. La frase la
 *  aprobó el usuario el 2026-11-21, cuando el término sustituyó a «precio de
 *  no perder». */
export function explicacionDelEquilibrio(): string {
  return tx(
    "Lo mínimo por lo que tendrías que vender a este jugador para no perder dinero. Cubre lo que pagaste por él y los sueldos que lleva cobrados, después de las comisiones de la venta. Cambia solo: sube cada semana con el sueldo y baja a medida que la comisión del agente se reduce con los días que lleva en tu club.",
  );
}

/** El término, con su explicación en un tooltip (2026-11-22, pedido del
 *  usuario). Antes era el `title` nativo de un `<abbr>`: tardaba en salir, no
 *  se veía que estuviera ahí --el subrayado sólo aparecía al pasar el ratón--
 *  y en el teléfono no salía nunca. Ahora va subrayado a puntos siempre, sale
 *  al pasar el ratón y también al tocarlo o llegar con el teclado. */
export function TerminoEquilibrio({ children }: { children: ReactNode }) {
  const id = useId();
  return (
    <span className="group relative inline">
      <span
        tabIndex={0}
        aria-describedby={id}
        className="cursor-help underline decoration-[var(--muted)] decoration-dotted underline-offset-2 outline-none focus-visible:text-[var(--accent)]"
      >
        {children}
      </span>
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-30 mt-1 hidden w-64 max-w-[80vw] rounded-md border border-[var(--border)] bg-[var(--surface)] p-2.5 text-left text-xs font-normal normal-case leading-relaxed tracking-normal text-[var(--text)] shadow-lg group-focus-within:block group-hover:block"
      >
        {explicacionDelEquilibrio()}
      </span>
    </span>
  );
}

/** El Comparador de transferencias de un jugador: adonde lleva su nombre en
 *  cada aviso de precio (2026-11-21, pedido del usuario). */
export function enlaceAlComparador(htPlayerId: number): string {
  return `/players/${htPlayerId}?vista=comparador`;
}

/** Un texto con el término explicado y, si se da, el nombre del jugador
 *  enlazado a su comparador. Sirve para los textos que llegan hechos del
 *  servidor (las alertas): se buscan dentro, sin tocar cómo se escriben. */
export function TextoConEquilibrio({
  texto,
  jugador,
}: {
  texto: string;
  jugador?: { htPlayerId: number; name: string };
}) {
  const termino = tx("precio de equilibrio");
  const piezas: ReactNode[] = [];
  let resto = texto;
  let i = 0;
  while (resto) {
    const bajo = resto.toLowerCase();
    const enTermino = termino ? bajo.indexOf(termino.toLowerCase()) : -1;
    const enNombre = jugador?.name ? resto.indexOf(jugador.name) : -1;
    const candidatos = [enTermino, enNombre].filter((p) => p >= 0);
    if (candidatos.length === 0) {
      piezas.push(resto);
      break;
    }
    const donde = Math.min(...candidatos);
    piezas.push(resto.slice(0, donde));
    if (donde === enNombre && jugador) {
      piezas.push(
        <Link
          key={`n${i++}`}
          to={enlaceAlComparador(jugador.htPlayerId)}
          className="underline decoration-[var(--border)] underline-offset-2 hover:text-[var(--accent)] hover:decoration-[var(--accent)]"
        >
          {jugador.name}
        </Link>,
      );
      resto = resto.slice(donde + jugador.name.length);
    } else {
      piezas.push(
        <TerminoEquilibrio key={`t${i++}`}>
          {resto.slice(donde, donde + termino.length)}
        </TerminoEquilibrio>,
      );
      resto = resto.slice(donde + termino.length);
    }
  }
  return (
    <>
      {piezas.map((p, k) => (
        <Fragment key={k}>{p}</Fragment>
      ))}
    </>
  );
}
