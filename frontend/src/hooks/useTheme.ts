import { useEffect, useState } from "react";

/**
 * El tema, con sus TRES estados.
 *
 * Antes eran dos y ninguno se guardaba: el botón volteaba `data-theme` en el
 * DOM y ahí moría, así que cada recarga devolvía al tema claro por mucho que
 * el usuario hubiera elegido el oscuro (comprobado el 2026-08-31 poniendo
 * oscuro, recargando y viendo el fondo volver a #fafafa). Y como el HTML
 * fijaba `data-theme="light"` a mano y el CSS no tenía ni una regla
 * `prefers-color-scheme`, quien tuviera el sistema en oscuro abría la
 * herramienta en claro SIEMPRE.
 *
 * Los tres estados son los que de verdad existen:
 *
 *   «sistema»  no se estampa el atributo y manda `prefers-color-scheme`.
 *   «claro»    y «oscuro»: elección explícita, que gana sobre el sistema.
 *
 * `sistema` tiene que seguir siendo alcanzable después de elegir a mano; si
 * no, el primer clic deja al usuario encerrado fuera de su propia
 * preferencia del sistema para siempre.
 */
export type Tema = "sistema" | "claro" | "oscuro";

export const CLAVE_TEMA = "htlens.tema";

/** Qué se estampa en `<html data-theme>` por cada tema. `null` = nada, que
 *  es lo que deja mandar a `prefers-color-scheme`. */
export const ATRIBUTO: Record<Tema, string | null> = {
  sistema: null,
  claro: "light",
  oscuro: "dark",
};

/** El ciclo del botón. Vuelve a «sistema» a propósito: si no, el primer clic
 *  encierra al usuario fuera de su propia preferencia para siempre. */
export const SIGUIENTE_TEMA: Record<Tema, Tema> = {
  sistema: "claro",
  claro: "oscuro",
  oscuro: "sistema",
};

/** Lo que hay guardado, ya validado. Cualquier cosa que no sea uno de los
 *  tres --ausente, corrupto, de una versión vieja-- es «sistema».
 *
 *  Va aparte de `temaGuardado` para poder probarse sin un DOM: el proyecto
 *  no tiene entorno de navegador en los tests y no merece una dependencia
 *  nueva sólo por esto. */
export function normalizarTema(valor: string | null | undefined): Tema {
  return valor === "claro" || valor === "oscuro" || valor === "sistema"
    ? valor
    : "sistema";
}

/** Lo guardado, o «sistema» si no hay nada (o si el navegador no deja leer). */
export function temaGuardado(): Tema {
  try {
    return normalizarTema(localStorage.getItem(CLAVE_TEMA));
  } catch {
    return "sistema";
  }
}

/** Estampa el tema en el DOM y lo recuerda. */
export function aplicarTema(tema: Tema): void {
  const root = document.documentElement;
  const valor = ATRIBUTO[tema];
  if (valor) root.dataset.theme = valor;
  else delete root.dataset.theme;
  try {
    localStorage.setItem(CLAVE_TEMA, tema);
  } catch {
    // Navegador en privado o con el almacenamiento bloqueado: el tema vale
    // para esta sesión y no se recuerda. Preferible a romper el botón.
  }
}

/** El tema elegido y cómo cambiarlo. */
export function useTema(): [Tema, (t: Tema) => void] {
  const [tema, setTema] = useState<Tema>(temaGuardado);
  const cambiar = (t: Tema) => {
    aplicarTema(t);
    setTema(t);
  };
  return [tema, cambiar];
}

/**
 * Si lo que se está pintando AHORA es oscuro.
 *
 * Lo consultan las gráficas, que van sobre canvas y no pueden resolver
 * variables CSS: necesitan el booleano ya decidido. Por eso mira las dos
 * fuentes --el atributo si hay elección explícita, el sistema si no-- y
 * escucha a las dos: el atributo con un observador y el sistema con el
 * propio `matchMedia`, o una gráfica se quedaría con el tema anterior cuando
 * el usuario cambia el del sistema operativo con la app abierta.
 */
export function useIsDarkTheme(): boolean {
  const resolver = () => {
    const elegido = document.documentElement.dataset.theme;
    if (elegido === "dark") return true;
    if (elegido === "light") return false;
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  };

  const [isDark, setIsDark] = useState(resolver);

  useEffect(() => {
    const root = document.documentElement;
    const alCambiar = () => setIsDark(resolver());

    const observer = new MutationObserver(alCambiar);
    observer.observe(root, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", alCambiar);

    return () => {
      observer.disconnect();
      media.removeEventListener("change", alCambiar);
    };
  }, []);

  return isDark;
}
