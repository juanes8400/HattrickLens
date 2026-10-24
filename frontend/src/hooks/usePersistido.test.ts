/** Un ajuste guardado no puede tumbar la pantalla.
 *
 *  Es lo único que estas pruebas vigilan, y es lo que había roto a medias.
 *  `usePersistido` ya protegía la ESCRITURA --«en privado o con los datos del
 *  sitio bloqueados, guardar lanza»-- pero dejaba la LECTURA al aire, que es
 *  la mitad peligrosa de las dos: la escritura vive en un efecto y falla
 *  después de pintar, mientras que la lectura es el valor inicial del
 *  `useState` y se ejecuta ANTES del primer render. Con los datos del sitio
 *  bloqueados, la pantalla entera no llegaba a existir.
 *
 *  Se prueba `recordado` y no el hook: el hook es el `useState` de React
 *  alrededor, y lo que puede reventar es esto.
 */
import { afterEach, describe, expect, it } from "vitest";

import { recordado } from "./usePersistido";

/** Pone un almacenamiento de mentira, porque el entorno es node. */
function almacen(datos: Record<string, string> = {}) {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (k: string) => datos[k] ?? null,
      setItem: (k: string, v: string) => {
        datos[k] = v;
      },
      removeItem: (k: string) => {
        delete datos[k];
      },
    },
  });
}

/** Uno que revienta al leer, como el de una ventana privada o un navegador
 *  con los datos del sitio bloqueados. */
function almacenRoto() {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
      removeItem: () => {},
    },
  });
}

afterEach(() => {
  Reflect.deleteProperty(globalThis, "localStorage");
});

describe("recordado", () => {
  it("devuelve lo guardado", () => {
    almacen({ "uso.mapa.magnitud": '"clicks"' });
    expect(recordado("uso.mapa.magnitud", "users")).toBe("clicks");
  });

  it("devuelve el valor por defecto si no hay nada", () => {
    almacen();
    expect(recordado("uso.tiempo.grano", "day")).toBe("day");
  });

  it("no revienta con un valor que no es JSON", () => {
    // Pasa de verdad: basta con que una versión anterior guardara texto plano
    // bajo esa clave.
    almacen({ "uso.tiempo.grano": "day" });
    expect(recordado("uso.tiempo.grano", "week")).toBe("week");
  });

  it("NO REVIENTA CON EL ALMACENAMIENTO BLOQUEADO", () => {
    // El fallo del 2026-10-23. Esto corre antes del primer render, así que una
    // excepción aquí no es un ajuste perdido: es una pantalla en blanco.
    almacenRoto();
    expect(() => recordado("uso.mapa.magnitud", "users")).not.toThrow();
    expect(recordado("uso.mapa.magnitud", "users")).toBe("users");
  });

  it("no revienta si no hay `localStorage` en absoluto", () => {
    // Fuera del navegador no existe. Es lo que hace que los componentes que lo
    // usan se puedan renderizar en una prueba.
    Reflect.deleteProperty(globalThis, "localStorage");
    expect(recordado("lo.que.sea", 7)).toBe(7);
  });

  it("respeta un `false` guardado y no lo confunde con «no hay nada»", () => {
    // El filo clásico de estos ayudantes: con `||` en vez de comprobar `null`,
    // un `false` guardado se lee como ausencia y vuelve al valor por defecto.
    almacen({ "uso.excluirme": "false" });
    expect(recordado("uso.excluirme", true)).toBe(false);
  });

  it("respeta un cero guardado", () => {
    almacen({ "uso.dias": "0" });
    expect(recordado("uso.dias", 30)).toBe(0);
  });
});
