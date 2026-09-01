import { useCallback, useRef } from "react";

/**
 * Dónde queda el foco cuando la acción borra su propio botón.
 *
 * Archivar una alerta quita la alerta de la lista, y con ella el botón que
 * acababas de pulsar. El navegador no tiene entonces a quién dárselo y lo
 * manda al `<body>`: comprobado el 2026-08-31, tras archivar una alerta el
 * foco quedaba al principio del documento, así que archivar tres seguidas
 * obligaba a recorrer la página entera con el tabulador dos veces de más.
 *
 * Es un fallo que sólo existe si navegas con teclado, y por eso se pasa por
 * alto con tanta facilidad: con ratón no se nota nada.
 *
 * Lo que hace: recuerda en qué posición de la lista estaba el botón, espera a
 * que la lista encoja y da el foco al que ocupa ahora esa posición --el
 * siguiente-- o al último si se quitó el de abajo. Si la lista se queda
 * vacía, el foco va al contenedor.
 *
 * OJO con el detalle que costó un intento fallido: la lista se busca en el
 * DOCUMENTO en cada comprobación, por su selector, y NO se guarda el nodo.
 * Al archivar, la consulta se refresca y React reemplaza el `<ul>` entero;
 * un nodo guardado queda huérfano, nunca encoge y el hook se rendía.
 */
export function useFocoDeLista(listaSel: string, botonSel: string) {
  const pendiente = useRef(false);

  /** Llamar en el `onClick`, ANTES de disparar la mutación. */
  const alQuitar = useCallback(
    (boton: HTMLElement) => {
      const lista = document.querySelector(listaSel);
      if (!lista || pendiente.current) return;
      const botones = Array.from(lista.querySelectorAll<HTMLElement>(botonSel));
      const indice = botones.indexOf(boton);
      if (indice < 0) return;
      const antes = botones.length;
      pendiente.current = true;

      let intentos = 0;
      const mirar = () => {
        const ahora = document.querySelector(listaSel);
        const actuales = ahora
          ? Array.from(ahora.querySelectorAll<HTMLElement>(botonSel))
          : [];
        if (ahora && actuales.length < antes) {
          const destino = actuales[Math.min(indice, actuales.length - 1)];
          if (!destino) {
            (ahora as HTMLElement).setAttribute("tabindex", "-1");
            (ahora as HTMLElement).focus();
            pendiente.current = false;
            return;
          }
          destino.focus();
          // Segundo detalle que costó otro intento: mientras la mutación
          // está en vuelo, la lista marca TODOS sus botones como
          // `disabled`, y un botón deshabilitado no acepta el foco. El
          // `focus()` de arriba puede no haber hecho nada, así que se
          // comprueba y se reintenta hasta que agarre.
          if (document.activeElement === destino) {
            pendiente.current = false;
            return;
          }
        }
        // ~2 s de margen: si la acción falla y la lista no encoge, esto se
        // rinde en vez de robar el foco más tarde y sin motivo.
        //
        // `setTimeout` y no `requestAnimationFrame`: el navegador SUSPENDE
        // los rAF cuando la pestaña no está visible, así que el reintento no
        // corría en una pestaña de fondo. Un temporizador se frena pero
        // sigue disparando (2026-08-31).
        if (++intentos < 40) window.setTimeout(mirar, 50);
        else pendiente.current = false;
      };
      window.setTimeout(mirar, 50);
    },
    [listaSel, botonSel],
  );

  return alQuitar;
}
