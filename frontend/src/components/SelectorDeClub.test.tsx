import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { destinoTrasCambiarDeClub, nombreDelClub } from "./clubes";
import { ElectorDeClub } from "./SelectorDeClub";
import type { SessionTeam } from "../services/api";

const club = (parcial: Partial<SessionTeam> & { id: number }): SessionTeam => ({
  htTeamId: parcial.id * 1000,
  name: `Club ${parcial.id}`,
  leagueName: "Colombia",
  seriesName: "V.92",
  syncedAt: "2026-10-07T12:00:00Z",
  hasImportedData: true,
  isPrimaryClub: false,
  ...parcial,
});

const principal = club({ id: 1, name: "Pulgas Arrechas", isPrimaryClub: true });
const segundo = club({ id: 2, name: "Arrechas de Zipaquirá" });
const tercero = club({ id: 3, name: "Zorros del Tercero" });
const tres = [principal, segundo, tercero];

const pintar = (clubes: SessionTeam[], activo = 1) =>
  renderToStaticMarkup(
    <ElectorDeClub clubes={clubes} activo={activo} onElegir={() => {}} />,
  );

describe("el mando que cambia de club", () => {
  it("no se ve con un solo club", () => {
    // Un desplegable con una única opción no dice nada que no diga ya el
    // nombre del club que tiene encima, y hace creer que falta algo por
    // configurar. Es el caso de casi todos los managers.
    expect(pintar([principal])).toBe("");
    expect(pintar([])).toBe("");
  });

  it("numera los clubes, con el principal de primero", () => {
    const html = pintar(tres);
    expect(html).toContain("1º · Pulgas Arrechas");
    expect(html).toContain("2º · Arrechas de Zipaquirá");
    expect(html).toContain("3º · Zorros del Tercero");
  });

  it("marca el club con el que se está mirando", () => {
    // Sin esto el desplegable enseñaría siempre el primero, y un manager en su
    // segundo club leería «1º» mientras mira datos del 2º.
    const opcion = (html: string, id: number) => {
      const desde = html.indexOf(`value="${id}"`);
      return html.slice(desde, html.indexOf("</option>", desde));
    };
    expect(opcion(pintar(tres, 2), 2)).toContain("selected");
    expect(opcion(pintar(tres, 1), 2)).not.toContain("selected");
    expect(opcion(pintar(tres, 1), 1)).toContain("selected");
  });

  it("avisa del club que todavía no se ha importado", () => {
    // Cambiar a un club sin sincronizar deja la aplicación en blanco. Dicho
    // antes de pulsar, es una espera; sin decirlo, parece que se rompió.
    const html = pintar([
      principal,
      club({ id: 2, name: "Recién creado", hasImportedData: false }),
    ]);
    expect(html).toContain("Recién creado (sin importar)");
  });
});

describe("el nombre de cada club", () => {
  const t = (_clave: string, defecto: string) => defecto;

  it("escribe el ordinal como lo escribe el idioma", () => {
    // `ordinal` ya sabe que el inglés dice «1st» y el alemán «1.»; aquí sólo
    // se comprueba que se usa, y no un `${n}º` cableado.
    expect(nombreDelClub(principal, 0, t)).toBe("1º · Pulgas Arrechas");
  });
});

describe("a dónde se cae al cambiar de club", () => {
  it("se queda en la misma pantalla", () => {
    expect(destinoTrasCambiarDeClub("/economy")).toBe("/economy");
    expect(destinoTrasCambiarDeClub("/transfers/balance")).toBe(
      "/transfers/balance",
    );
  });

  it("vuelve al panel cuando la ruta nombra a alguien de otro club", () => {
    // 498724298 es un jugador del club que se deja atrás: en el nuevo no
    // existe, y recargar esa ruta daría un 404 que parece un fallo del cambio.
    expect(destinoTrasCambiarDeClub("/players/498724298")).toBe("/dashboard");
    expect(destinoTrasCambiarDeClub("/rivals/1750123")).toBe("/dashboard");
  });
});
