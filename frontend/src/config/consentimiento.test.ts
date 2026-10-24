/** La regla que no puede romperse nunca: nada de Google sin permiso.
 *
 *  Estas pruebas no vigilan campos ni estética. Vigilan las dos maneras en
 *  que este módulo podría FALLAR EN SILENCIO y nadie se enteraría hasta
 *  recibir una queja:
 *
 *   · que un consentimiento a medias --tres señales de cuatro-- deje a Google
 *     en un estado que ni la norma ni él saben leer;
 *   · que una decisión no viaje, y el navegador crea una cosa y Google otra.
 *
 *  Y una tercera que es de diseño: el estado de partida tiene que ser
 *  «sin decidir» pase lo que pase, incluso con el almacenamiento roto. En una
 *  ventana privada, leer un fallo como un «sí» sería exactamente el error que
 *  todo esto existe para evitar.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { clienteValido } from "./anuncios";
import {
  alCambiarElConsentimiento,
  decidir,
  decisionGuardada,
  olvidarLaDecision,
} from "./consentimiento";

const LLAVE = "htlens.consentimiento";

/** Un almacenamiento de mentira, porque el entorno de las pruebas es node. */
function montaElAlmacen(): Map<string, string> {
  const datos = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: (k: string) => datos.get(k) ?? null,
      setItem: (k: string, v: string) => datos.set(k, v),
      removeItem: (k: string) => datos.delete(k),
    },
  });
  return datos;
}

/** Un almacenamiento que revienta, como el de una ventana privada. */
function montaUnAlmacenRoto(): void {
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: {
      getItem: () => {
        throw new Error("bloqueado");
      },
      setItem: () => {
        throw new Error("bloqueado");
      },
      removeItem: () => {
        throw new Error("bloqueado");
      },
    },
  });
}

type Llamada = [string, string, Record<string, string>];

function espiaAGtag(): Llamada[] {
  const llamadas: Llamada[] = [];
  (globalThis as unknown as { window: unknown }).window = globalThis;
  (globalThis as unknown as { gtag: unknown }).gtag = (...args: unknown[]) =>
    llamadas.push(args as Llamada);
  return llamadas;
}

describe("el identificador de editor", () => {
  it("sólo acepta la forma exacta que espera Google", () => {
    expect(clienteValido("ca-pub-1234567890123456")).toBe(true);
  });

  it("rechaza lo que se parece pero no sirve", () => {
    // Cada uno de éstos cargaría el script de Google para no servir nada, y
    // el fallo no se vería en ninguna pantalla.
    for (const malo of [
      "",
      "ca-pub-",
      "1234567890123456",
      "pub-1234567890123456",
      "ca-pub-123456789012345", // quince
      "ca-pub-12345678901234567", // diecisiete
      "ca-pub-12345678901234ab",
      " ca-pub-1234567890123456",
    ]) {
      expect(clienteValido(malo), malo).toBe(false);
    }
  });
});

describe("el consentimiento", () => {
  beforeEach(() => {
    montaElAlmacen();
    espiaAGtag();
  });

  it("empieza sin decidir, que es el estado prudente", () => {
    expect(decisionGuardada()).toBe("sin-decidir");
  });

  it("empieza sin decidir TAMBIÉN con el almacenamiento roto", () => {
    montaUnAlmacenRoto();
    // Una ventana privada no es un sí.
    expect(decisionGuardada()).toBe("sin-decidir");
  });

  it("no se cree un valor que no escribió él", () => {
    const datos = montaElAlmacen();
    datos.set(LLAVE, "si-claro-que-si");
    expect(decisionGuardada()).toBe("sin-decidir");
  });

  it("recuerda lo decidido", () => {
    decidir("concedido");
    expect(decisionGuardada()).toBe("concedido");
    decidir("denegado");
    expect(decisionGuardada()).toBe("denegado");
  });

  it("le manda a Google LAS CUATRO señales, nunca unas cuantas", () => {
    const llamadas = espiaAGtag();
    decidir("concedido");

    expect(llamadas).toHaveLength(1);
    const [tipo, accion, señales] = llamadas[0]!;
    expect(tipo).toBe("consent");
    expect(accion).toBe("update");
    expect(señales).toEqual({
      ad_storage: "granted",
      ad_user_data: "granted",
      ad_personalization: "granted",
      analytics_storage: "granted",
    });
  });

  it("y al rechazar las manda todas en denied", () => {
    const llamadas = espiaAGtag();
    decidir("denegado");

    expect(llamadas[0]![2]).toEqual({
      ad_storage: "denied",
      ad_user_data: "denied",
      ad_personalization: "denied",
      analytics_storage: "denied",
    });
  });

  it("olvidar la decisión vuelve a denied, no a «sin decidir» a secas", () => {
    decidir("concedido");
    const llamadas = espiaAGtag();
    olvidarLaDecision();

    // Volver a preguntar NO puede dejar a Google con el permiso de antes
    // mientras no hay respuesta nueva.
    expect(decisionGuardada()).toBe("sin-decidir");
    expect(llamadas[0]![2].ad_storage).toBe("denied");
  });

  it("avisa a quien esté mirando, para que no haya dos pantallas discrepando", () => {
    const aviso = vi.fn();
    const cortar = alCambiarElConsentimiento(aviso);

    decidir("concedido");
    expect(aviso).toHaveBeenCalledTimes(1);

    cortar();
    decidir("denegado");
    expect(aviso).toHaveBeenCalledTimes(1);
  });

  it("no revienta si no hay gtag todavía", () => {
    delete (globalThis as unknown as { gtag?: unknown }).gtag;
    // El script del consentimiento vive en index.html; si por lo que sea no
    // llegó, guardar la decisión no puede tumbar la pantalla.
    expect(() => decidir("denegado")).not.toThrow();
    expect(decisionGuardada()).toBe("denegado");
  });
});
