import { describe, expect, it } from "vitest";
import type { Club } from "../services/api/club";
import {
  SEMANAS_DE_LAS_GRAFICAS,
  corteDeSemanas,
  recortarClub,
  ventanaDeGraficas,
} from "./ventanaDeGraficas";

/** El eje tiene que cubrir TODO lo que la gráfica dibuja.
 *
 *  2026-09-01, visto por el usuario en producción: «esos puntos de compras y
 *  ventas que se van hasta por allá lejos a la izquierda». El eje se calculaba
 *  con las lecturas, los partidos y los socios, pero la gráfica pintaba además
 *  el pulso de mercado, que el backend saca con su propia ventana de ocho
 *  semanas. Seis operaciones eran anteriores al primer partido y sus puntos
 *  caían fuera del dibujo, encima de las etiquetas del eje.
 *
 *  En la copia local no se reproducía: allí el partido más antiguo (8 de
 *  julio) es anterior a la primera venta (11 de julio), así que todo caía
 *  dentro por casualidad.
 */
describe("la ventana de las gráficas", () => {
  const dentro = (dia: string, v: { from: string; to: string }) => {
    const t = new Date(`${dia}T12:00:00`).getTime();
    return t >= new Date(v.from).getTime() && t <= new Date(v.to).getTime();
  };

  it("el caso de producción: el mercado empieza antes que los partidos", () => {
    const v = ventanaDeGraficas({
      instantes: ["2026-07-12T21:40:00", "2026-08-20T15:32:33"],
      dias: ["2026-07-07", "2026-07-09", "2026-08-30"],
    });
    // El 7 de julio es anterior al primer partido y aun así entra.
    expect(dentro("2026-07-07", v)).toBe(true);
    expect(dentro("2026-07-09", v)).toBe(true);
    expect(dentro("2026-08-30", v)).toBe(true);
  });

  it("ningún día de mercado se queda fuera, venga cuando venga", () => {
    const dias = ["2026-05-01", "2026-07-07", "2026-08-30", "2026-09-15"];
    const v = ventanaDeGraficas({ instantes: ["2026-08-01T10:00:00"], dias });
    for (const d of dias) expect(dentro(d, v)).toBe(true);
  });

  it("sigue dejando un día de aire a cada lado", () => {
    // Sin él, el primer y el último punto quedan pegados al marco.
    const v = ventanaDeGraficas({
      instantes: ["2026-08-10T12:00:00"],
      dias: [],
    });
    expect(v.from.slice(0, 10)).toBe("2026-08-09");
    expect(v.to.slice(0, 10)).toBe("2026-08-11");
  });

  it("sin nada que dibujar, no revienta", () => {
    const v = ventanaDeGraficas(
      { instantes: [], dias: [] },
      () => new Date("2026-09-01T00:00:00Z"),
    );
    expect(new Date(v.from).getTime()).toBeLessThan(new Date(v.to).getTime());
  });

  it("los huecos de las series no cuentan", () => {
    const v = ventanaDeGraficas({
      instantes: [null, undefined, "2026-08-10T12:00:00"],
      dias: [],
    });
    expect(v.from.slice(0, 10)).toBe("2026-08-09");
  });
});

/** 2026-11-14, pedido del usuario: «limitar las gráficas de Club y Cuerpo
 *  Técnico a 16 semanas máximo». */
describe("las gráficas de Club abarcan dieciséis semanas como mucho", () => {
  // Una lectura por semana durante veinte semanas, la última el 14/11 a
  // última hora: los días de mercado se cuentan al mediodía local y no deben
  // pasar por delante de ella en ninguna zona horaria.
  const ULTIMA = new Date("2026-11-14T23:00:00Z").getTime();
  const semana = (n: number) =>
    new Date(ULTIMA - n * 7 * 24 * 3600 * 1000).toISOString();
  const veinte = Array.from({ length: 20 }, (_, i) => semana(19 - i));

  const club = (fechas: string[]): Club =>
    ({
      teamName: "Test FC",
      current: { spirit: null, confidence: null, supporters: null },
      staff: null,
      psychology: {
        weeks: 20,
        spirit: {
          scale: [],
          equilibrium: null,
          readings: fechas.map((at) => ({ at, level: 5 })),
          movements: fechas.map((at) => ({
            at,
            from: 5,
            to: 5,
            delta: 0,
            cause: "",
          })),
        },
        confidence: {
          scale: [],
          equilibrium: null,
          readings: fechas.map((at) => ({ at, level: 4 })),
          movements: [],
        },
        matches: fechas.map((playedAt) => ({
          playedAt,
          rival: "Rival",
          isHome: true,
          goalsFor: 1,
          goalsAgainst: 0,
          result: "win",
          attitude: 0,
          attitudeLabel: "Normal",
        })),
        buyDays: fechas.map((f) => ({ day: f.slice(0, 10), count: 1 })),
        sellDays: [],
        intensityDrops: fechas,
      },
      moodHistory: fechas.map((capturedAt) => ({
        capturedAt,
        spirit: 5,
        confidence: 4,
      })),
      supporterHistory: fechas.map((capturedAt) => ({
        capturedAt,
        fanClubSize: 100,
        supportersPopularity: 9,
      })),
      staffHistory: fechas.map((capturedAt) => ({
        capturedAt,
        seasonWeek: null,
        trainerSkillLevel: 5,
        roles: [],
      })),
      notes: [],
    }) as Club;

  const hoy = () => new Date(ULTIMA);

  it("el corte cae dieciséis semanas antes de hoy", () => {
    expect(SEMANAS_DE_LAS_GRAFICAS).toBe(16);
    expect(corteDeSemanas(hoy)).toBe(new Date(semana(16)).getTime());
  });

  it("de veinte semanas quedan las diecisiete lecturas de los extremos", () => {
    // De la semana −16 a la 0, ambas incluidas: 17 lecturas, 16 tramos.
    const r = recortarClub(club(veinte), hoy);
    const psi = r.psychology;
    expect(psi.spirit.readings).toHaveLength(17);
    expect(psi.spirit.readings[0]!.at).toBe(semana(16));
    expect(psi.spirit.movements).toHaveLength(17);
    expect(psi.confidence.readings).toHaveLength(17);
    expect(psi.matches).toHaveLength(17);
    expect(psi.intensityDrops).toHaveLength(17);
    expect(r.supporterHistory).toHaveLength(17);
    expect(r.staffHistory).toHaveLength(17);
    expect(r.moodHistory).toHaveLength(17);
    // El eje sale de lo recortado: no empieza antes del corte (más su día).
    const v = ventanaDeGraficas({
      instantes: psi.spirit.readings.map((x) => x.at),
      dias: psi.buyDays.map((d) => d.day),
    });
    const dias =
      (new Date(v.to).getTime() - new Date(v.from).getTime()) / 864e5;
    expect(dias).toBeLessThanOrEqual(16 * 7 + 2);
  });

  it("con menos de dieciséis semanas no se quita nada", () => {
    const pocas = veinte.slice(-10);
    const r = recortarClub(club(pocas), hoy);
    expect(r.psychology.spirit.readings).toHaveLength(10);
    expect(r.psychology.buyDays).toHaveLength(10);
    expect(r.staffHistory).toHaveLength(10);
  });

  it("cuenta desde hoy, no desde el último dato", () => {
    // Cuatro semanas sin sincronizar: de las veinte quedan las trece (de la
    // −12 a la 0) que caen en las dieciséis semanas que acaban hoy.
    const dentroDeUnMes = () => new Date(ULTIMA + 4 * 7 * 24 * 3600 * 1000);
    const r = recortarClub(club(veinte), dentroDeUnMes);
    expect(r.psychology.spirit.readings).toHaveLength(13);
    expect(r.psychology.spirit.readings[0]!.at).toBe(semana(12));
    expect(r.supporterHistory).toHaveLength(13);
  });
});
