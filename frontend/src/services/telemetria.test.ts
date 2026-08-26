import { describe, expect, it } from "vitest";
import { moduloDe } from "./telemetria";

describe("a qué módulo pertenece cada ruta", () => {
  it("reconoce las pantallas normales", () => {
    expect(moduloDe("/academy")).toBe("Juveniles");
    expect(moduloDe("/economy")).toBe("Economía");
    expect(moduloDe("/sync")).toBe("Sincronización");
    expect(moduloDe("/transfers/balance")).toBe("Transferencias");
  });

  it("no deja un identificador de jugador suelto en los resúmenes", () => {
    // Si no se tradujera, cada jugador visitado sería un "módulo" distinto y
    // la tabla tendría cientos de filas de una sola visita.
    expect(moduloDe("/players/483316479")).toBe("Jugadores");
    expect(moduloDe("/rivals/12345")).toBe("Rivales");
  });

  it("separa las tres pantallas del alta", () => {
    // 2026-08-26: caían las tres en "Otros", que es justo donde no se puede
    // ver en cuál se cae la gente.
    expect(moduloDe("/welcome")).toBe("Alta: bienvenida");
    expect(moduloDe("/connected")).toBe("Alta: conectado");
    expect(moduloDe("/setup")).toBe("Alta: importación");
  });

  it("lo que no conoce va a Otros, pero ya no debería caer nada de la app", () => {
    expect(moduloDe("/algo-que-no-existe")).toBe("Otros");
  });
});
