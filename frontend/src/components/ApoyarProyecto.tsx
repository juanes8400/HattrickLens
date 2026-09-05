import { Link } from "react-router-dom";
import { hayApoyo } from "../config/apoyo";

/**
 * El botón de apoyo voluntario, en los dos sitios donde aparece.
 *
 * Un solo componente con dos formas y no dos componentes: el enlace, el
 * `rel` y la decisión de enseñarlo o no son los mismos, y separarlos era
 * garantizar que un día uno abra en pestaña nueva y el otro no.
 *
 * Dónde NO está, que costó más decidir que dónde sí: ni en el Panel --es lo
 * primero que se ve cada día, y pedir dinero antes de dar nada convierte la
 * herramienta en otra cosa-- ni en una ventana al entrar, ni en una barra
 * flotante que estorbe en Alineación o Transferencias.
 */
/** Lo que se dice al pedir apoyo, escrito UNA vez.
 *
 *  Vive aquí y no en cada pantalla porque aparece en dos --Autor y el libro
 *  de visitas-- y ya se reescribió una vez: con el texto duplicado, el
 *  siguiente cambio se deja uno a medias y las dos pantallas dicen cosas
 *  distintas.
 */
export function MensajeDeApoyo() {
  return (
    <p className="prosa max-w-prose text-sm leading-relaxed text-[var(--muted)]">
      Mantener esta página me cuesta{" "}
      <b className="text-[var(--text)]">7 US$ al mes</b> y los pago yo. Si te
      está sirviendo, apóyame, escríbeme en el libro de visitas: podemos
      trabajar juntos en funcionalidades nuevas.
    </p>
  );
}

export function ApoyarProyecto({ forma }: { forma: "menu" | "pagina" }) {
  // La condición se pregunta en `hayApoyo`, no aquí: si cada sitio la
  // repitiera, un día discreparían.
  if (!hayApoyo()) return null;

  // Lleva a UNA PANTALLA nuestra, no a un sitio de cobro. Desde que hay tres
  // vías --Bre-B, Mercado Pago y Buy Me a Coffee-- mandar a una de ellas sería
  // elegir por el usuario, y a un colombiano le conviene una distinta que a un
  // sueco. Además Bre-B es una LLAVE que hay que copiar, no una URL: en un
  // enlace directo no cabía (2026-09-05).
  const destino = "/apoyar";

  if (forma === "menu") {
    return (
      <Link
        to={destino}
        className="mb-1 flex items-center justify-center gap-1.5 rounded-md border border-[var(--border)] px-2 py-1.5 text-xs text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--text)]"
      >
        <span aria-hidden="true">☕</span>
        Invítame a un café
      </Link>
    );
  }

  return (
    <Link
      to={destino}
      className="inline-flex items-center gap-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white"
    >
      <span aria-hidden="true">☕</span>
      Invítame a un café
    </Link>
  );
}
