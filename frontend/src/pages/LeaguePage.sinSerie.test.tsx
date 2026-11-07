import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SinSerieTodavia, sinEmpezar, sinSerieTodavia } from "./LeaguePage";
import type { League, LeagueStandingRow } from "../services/api";

/** 2026-11-07. Un lector del foro preguntó cuándo llegan los datos de la liga
 *  nueva, y la respuesta debería estar en la pantalla de Liga y no en un hilo.
 *
 *  Lo que se vigila aquí son DOS HECHOS QUE SE PARECÍAN DEMASIADO:
 *
 *  · «El sorteo está hecho y nadie ha jugado todavía.» No hay nada que
 *    esperar: la liga empieza el sábado.
 *  · «Hattrick no ha publicado tu serie.» Lo que falta no está de nuestro
 *    lado, y volver a sincronizar no lo trae antes.
 *
 *  `sinEmpezar` los juntaba sin querer: con la tabla vacía, `every` sobre una
 *  lista vacía es `true`, así que un sorteo que todavía no existe salía como
 *  «la temporada no ha empezado» —una frase que da por hecho que ya sabemos
 *  con quién juegas—. */
const fila = (played: number): LeagueStandingRow =>
  ({
    position: 1,
    htTeamId: 1,
    name: "Equipo",
    played,
    won: 0,
    draws: 0,
    lost: 0,
    goalsFor: 0,
    goalsAgainst: 0,
    points: 0,
    isOwnTeam: false,
  }) as unknown as LeagueStandingRow;

const liga = (standings: LeagueStandingRow[], roundsPlayed = 0): League =>
  ({ standings, roundsPlayed, seriesName: "V.123" }) as unknown as League;

describe("liga sin serie publicada", () => {
  it("la tabla vacía es «no hay serie», no «no ha empezado»", () => {
    const data = liga([]);
    expect(sinSerieTodavia(data)).toBe(true);
  });

  it("el sorteo hecho sin jugar NO es «no hay serie»", () => {
    // Ocho equipos a cero: la serie existe, la temporada no ha empezado. Son
    // dos cosas distintas y la pantalla dice una distinta para cada una.
    const data = liga(Array.from({ length: 8 }, () => fila(0)));
    expect(sinSerieTodavia(data)).toBe(false);
    expect(sinEmpezar(data)).toBe(true);
  });

  it("una liga en marcha no es ninguna de las dos", () => {
    const data = liga(
      Array.from({ length: 8 }, () => fila(3)),
      3,
    );
    expect(sinSerieTodavia(data)).toBe(false);
    expect(sinEmpezar(data)).toBe(false);
  });

  it("dice que el sorteo es lo que falta, y que sincronizar no lo adelanta", () => {
    const html = renderToStaticMarkup(<SinSerieTodavia serie="V.123" />);
    expect(html).toContain("Hattrick todavía no ha publicado tu serie");
    expect(html).toContain("V.123");
    expect(html).toContain("sorteo");
    // LO MÁS IMPORTANTE DE TODO EL AVISO: que no se arregla sincronizando.
    // Sin esta frase, lo primero que hace cualquiera es sincronizar otra vez.
    expect(html).toContain("no se arregla volviendo a sincronizar");
    // Y que no se ha perdido nada de la temporada pasada, que es el otro
    // miedo razonable al ver una pantalla vacía.
    expect(html).toContain("no se borra nada");
  });

  it("sin nombre de serie no se inventa uno", () => {
    const html = renderToStaticMarkup(<SinSerieTodavia serie={null} />);
    expect(html).toContain("Hattrick todavía no ha publicado tu serie");
    expect(html).toContain("sorteo");
    expect(html).not.toContain("Sabemos que tu serie es");
  });

  it("es un aviso, no un párrafo cualquiera", () => {
    // `role="alert"` para que un lector de pantalla lo anuncie: quien llega a
    // esta pantalla y la ve vacía necesita oír el por qué, no encontrarlo.
    expect(renderToStaticMarkup(<SinSerieTodavia serie={null} />)).toContain(
      'role="alert"',
    );
  });
});
