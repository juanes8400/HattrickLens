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

  it("lo que no conoce va a «Otros» CON su ruta puesta", () => {
    // 2026-09-01: antes era un «Otros» a secas, y como se guarda el nombre del
    // módulo --no la ruta-- después no había forma de saber qué había dentro.
    // Paso el 31 de agosto: `/transparency` nació sin entrada en el mapa y 51
    // eventos, 23 de ellos vistas sin etiqueta con casi siete horas dentro,
    // acabaron en un cajón imposible de desglosar.
    expect(moduloDe("/algo-que-no-existe")).toBe("Otros (/algo-que-no-existe)");
  });

  it("los identificadores no multiplican los cajones", () => {
    // Sin esto, mil fichas sin mapear serían mil módulos distintos en la tabla.
    expect(moduloDe("/loquesea/123")).toBe("Otros (/loquesea/:id)");
    expect(moduloDe("/loquesea/456")).toBe("Otros (/loquesea/:id)");
  });

  it("una fila «Otros» es un aviso, no una categoría", () => {
    // Toda ruta real de la aplicación tiene que estar mapeada. Si alguna cae
    // aquí, es que falta una entrada -- que es exactamente lo que pasó con
    // Transparencia.
    for (const ruta of [
      "/dashboard",
      "/club",
      "/overview",
      "/team",
      "/positions",
      "/lineup",
      "/training",
      "/academy",
      "/transfers/balance",
      "/matches",
      "/league",
      "/cup",
      "/rivals",
      "/economy",
      "/arena",
      "/insights",
      "/sync",
      "/news",
      "/transparency",
      "/engine",
      "/uso",
      "/welcome",
      "/connected",
      "/setup",
    ]) {
      expect(moduloDe(ruta)).not.toMatch(/^Otros/);
    }
  });
});
