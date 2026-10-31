import { describe, expect, it } from "vitest";
import {
  bandBetween,
  serieDePuntosOption,
  tiraDePuntosOption,
} from "./chartOptions";

/** La banda son dos series apiladas: una base invisible y encima el hueco,
 *  que es la única con relleno. Lo que se comprueba aquí es que base+hueco
 *  reconstruye siempre la línea de arriba, sea cual sea el orden. */
describe("bandBetween", () => {
  const valores = (serie: Record<string, unknown>) =>
    serie.data as (number | null)[];

  it("apila desde la línea de abajo hasta la de arriba", () => {
    const [base, hueco] = bandBetween([10, 20, 30], [15, 25, 35]);
    expect(valores(base!)).toEqual([10, 20, 30]);
    expect(valores(hueco!)).toEqual([5, 5, 5]);
  });

  it("sigue cubriendo el hueco real cuando las líneas se cruzan", () => {
    // Punto 1: la primera va por debajo. Punto 2: por encima. La banda no se
    // invierte, la base baja al mínimo de cada semana.
    const [base, hueco] = bandBetween([10, 40], [15, 25]);
    expect(valores(base!)).toEqual([10, 25]);
    expect(valores(hueco!)).toEqual([5, 15]);
  });

  it("deja hueco en la banda si falta cualquiera de las dos lecturas", () => {
    const [base, hueco] = bandBetween([null, 20, 30], [15, null, 35]);
    expect(valores(base!)).toEqual([null, null, 30]);
    expect(valores(hueco!)).toEqual([null, null, 5]);
  });

  it("no pinta ni línea ni símbolo: solo el relleno del hueco", () => {
    const [base, hueco] = bandBetween([10], [20]);
    expect(base!.areaStyle).toBeUndefined();
    expect(hueco!.areaStyle).toBeDefined();
    expect(base!.stack).toBe(hueco!.stack);
  });
});

/** Las dos gráficas del comparador, 2026-10-28: «que cada punto de la
 *  comparación de transferencias, la línea, todo saque tooltip» y «que se
 *  diferencie cuando el peso sea de 100 vs de 90 con colores o tamaños».
 *
 *  Se comprueba sobre la OPCIÓN y no sobre el lienzo porque es donde vive la
 *  decisión: ECharts dibuja lo que esta función le diga. Que el tooltip llega
 *  a la pantalla se vio a mano en el navegador el mismo día. */
describe("las gráficas del comparador", () => {
  type Serie = {
    name?: string;
    type?: string;
    data?: unknown[];
    symbol?: string;
    markLine?: { silent?: boolean };
  };
  const series = (o: Record<string, unknown>) => o.series as Serie[];
  const porNombre = (o: Record<string, unknown>, n: string) =>
    series(o).find((s) => s.name === n);
  const puntos = (s: Serie | undefined) =>
    (s?.data ?? []) as { symbolSize: number; tip: string }[];

  // Dos cerradas --una clavada y una avalada-- y una puja abierta.
  const PRECIOS: [number, boolean, number][] = [
    [100_000, true, 100],
    [200_000, true, 90],
    [300_000, false, 90],
  ];
  const COMUNES = {
    detalle: (v: number) => `${v} US$`,
    etiquetaMedia: "Media",
    etiquetaMediana: "Mediana",
  };

  describe("la tira de precios", () => {
    const opcion = tiraDePuntosOption(PRECIOS, {
      media: 180_000,
      mediana: 200_000,
      ...COMUNES,
    }) as unknown as Record<string, unknown>;

    it("separa el clavado del avalado en series propias, para que haya leyenda", () => {
      expect(porNombre(opcion, "Idéntico")).toBeDefined();
      expect(porNombre(opcion, "Equivalente")).toBeDefined();
      expect(puntos(porNombre(opcion, "Idéntico"))).toHaveLength(1);
      expect(puntos(porNombre(opcion, "Equivalente"))).toHaveLength(1);
    });

    it("el clavado se pinta MÁS GRANDE que el avalado", () => {
      const clavado = puntos(porNombre(opcion, "Idéntico"))[0]!;
      const avalado = puntos(porNombre(opcion, "Equivalente"))[0]!;
      // Y con holgura: la rampa vieja los dejaba a 1,6 px de diferencia, que
      // es lo que no se veía.
      expect(clavado.symbolSize - avalado.symbolSize).toBeGreaterThanOrEqual(5);
    });

    it("cada punto lleva su propio texto, y dice de qué clase es", () => {
      expect(puntos(porNombre(opcion, "Idéntico"))[0]!.tip).toContain("idéntico");
      expect(puntos(porNombre(opcion, "Equivalente"))[0]!.tip).toContain("equivalente");
      const puja = puntos(porNombre(opcion, "Subasta abierta"))[0]!;
      expect(puja.tip).toContain("no promedia");
    });

    it("las marcas de media y mediana se pueden preguntar", () => {
      // `silent: true` las dejaba mudas, y son el dato que más se mira.
      expect(porNombre(opcion, "Subasta abierta")?.markLine?.silent).toBe(false);
    });
  });

  describe("la serie en el tiempo", () => {
    const opcion = serieDePuntosOption(
      [
        { cuando: "2026-10-01", media: 150_000, precios: PRECIOS },
        { cuando: "2026-10-08", media: 160_000, precios: PRECIOS },
      ],
      { etiqueta: (iso) => iso, soloCerradas: true, ...COMUNES },
    ) as unknown as Record<string, unknown>;

    it("LA LÍNEA también saca tooltip: lleva símbolo y texto por punto", () => {
      const linea = porNombre(opcion, "Media")!;
      expect(linea.type).toBe("line");
      // Sin símbolo no hay nada sobre lo que posarse.
      expect(linea.symbol).not.toBe("none");
      const primero = (linea.data as { tip: string }[])[0]!;
      expect(primero.tip).toContain("Media");
      expect(primero.tip).toContain("sobre");
    });

    it("el tooltip de un punto dice de qué lectura es", () => {
      expect(puntos(porNombre(opcion, "Idéntico"))[0]!.tip).toContain("2026-10-01");
    });

    it("aquí también el clavado es más grande", () => {
      const clavado = puntos(porNombre(opcion, "Idéntico"))[0]!;
      const avalado = puntos(porNombre(opcion, "Equivalente"))[0]!;
      expect(clavado.symbolSize).toBeGreaterThan(avalado.symbolSize);
    });
  });
});
