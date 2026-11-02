import { describe, expect, it } from "vitest";
import {
  bandBetween,
  histogramaDeErrorOption,
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
    itemStyle?: { color?: string; borderColor?: string; borderWidth?: number };
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

    /** 2026-11-01: «quiero que se diferencie mejor». El tamaño solo obliga a
     *  tener los dos puntos delante; la forma se lee sola. */
    it("el idéntico es un disco y el equivalente un aro", () => {
      expect(porNombre(opcion, "Idéntico")?.itemStyle?.color).not.toBe(
        "transparent",
      );
      // Y hueco DE VERDAD: `emptyCircle` rellena de blanco, no de nada.
      const aro = porNombre(opcion, "Equivalente")?.itemStyle;
      expect(aro?.color).toBe("transparent");
      expect(aro?.borderWidth).toBeGreaterThan(0);
      expect(aro?.borderColor).toBe(
        porNombre(opcion, "Idéntico")?.itemStyle?.color,
      );
    });

    /** La puja llevaba `emptyCircle` desde el principio, con el mismo nucleo
     *  blanco: grande y azul, nadie lo veia. */
    it("la subasta abierta también es un aro hueco de verdad", () => {
      const puja = porNombre(opcion, "Subasta abierta")?.itemStyle;
      expect(puja?.color).toBe("transparent");
      expect(puja?.borderWidth).toBeGreaterThan(0);
      expect(puja?.borderColor).toBeTruthy();
      // Y no del verde de las cerradas: la puja es lo otro.
      expect(puja?.borderColor).not.toBe(
        porNombre(opcion, "Idéntico")?.itemStyle?.color,
      );
    });

    it("el clavado se pinta MÁS GRANDE que el avalado", () => {
      const clavado = puntos(porNombre(opcion, "Idéntico"))[0]!;
      const avalado = puntos(porNombre(opcion, "Equivalente"))[0]!;
      // Y con holgura: la rampa vieja los dejaba a 1,6 px de diferencia, que
      // es lo que no se veía.
      expect(clavado.symbolSize - avalado.symbolSize).toBeGreaterThanOrEqual(5);
    });

    it("cada punto lleva su propio texto, y dice de qué clase es", () => {
      expect(puntos(porNombre(opcion, "Idéntico"))[0]!.tip).toContain(
        "idéntico",
      );
      expect(puntos(porNombre(opcion, "Equivalente"))[0]!.tip).toContain(
        "equivalente",
      );
      const puja = puntos(porNombre(opcion, "Subasta abierta"))[0]!;
      expect(puja.tip).toContain("no promedia");
    });

    it("las marcas de media y mediana se pueden preguntar", () => {
      // `silent: true` las dejaba mudas, y son el dato que más se mira.
      expect(porNombre(opcion, "Subasta abierta")?.markLine?.silent).toBe(
        false,
      );
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
      expect(puntos(porNombre(opcion, "Idéntico"))[0]!.tip).toContain(
        "2026-10-01",
      );
    });

    it("aquí también el clavado es más grande", () => {
      const clavado = puntos(porNombre(opcion, "Idéntico"))[0]!;
      const avalado = puntos(porNombre(opcion, "Equivalente"))[0]!;
      expect(clavado.symbolSize).toBeGreaterThan(avalado.symbolSize);
    });

    it("y aquí también uno es disco y el otro aro", () => {
      const aro = porNombre(opcion, "Equivalente")?.itemStyle;
      expect(aro?.color).toBe("transparent");
      expect(aro?.borderColor).toBe(
        porNombre(opcion, "Idéntico")?.itemStyle?.color,
      );
    });
  });
});

/** El histograma del error de la fórmula de entrenamiento (2026-11-01). Lo
 *  que se comprueba es lo que lo hace valer algo: que está centrado en el
 *  cero y que cada subida cae en su cubeta. */
describe("histogramaDeErrorOption", () => {
  const eje = (o: Record<string, unknown>) =>
    (o.xAxis as { data: string[] }).data;
  const cuenta = (o: Record<string, unknown>) =>
    (o.series as { data: number[] }[])[0]!.data;

  it("está centrado en el cero y es simétrico", () => {
    const o = histogramaDeErrorOption([-2, 1]) as unknown as Record<
      string,
      unknown
    >;
    expect(eje(o)).toEqual(["-2", "-1", "0", "+1", "+2"]);
    // El cero en medio: si no, el histograma engaña sobre de qué lado cae el
    // montón.
    expect(eje(o)[Math.floor(eje(o).length / 2)]).toBe("0");
  });

  it("cada subida cae en la cubeta de su semana", () => {
    const o = histogramaDeErrorOption([
      -1.2, -0.9, 0.1, 0.4, -0.3, 1.1,
    ]) as unknown as Record<string, unknown>;
    // -1,2 y -0,9 redondean a -1; 0,1, 0,4 y -0,3 al 0; 1,1 al +1.
    expect(eje(o)).toEqual(["-1", "0", "+1"]);
    expect(cuenta(o)).toEqual([2, 3, 1]);
  });

  it("con una sola subida clavada sigue habiendo gráfica", () => {
    const o = histogramaDeErrorOption([0]) as unknown as Record<
      string,
      unknown
    >;
    expect(eje(o)).toEqual(["-1", "0", "+1"]);
    expect(cuenta(o)).toEqual([0, 1, 0]);
  });

  it("el eje de subidas no se parte en medias subidas", () => {
    const o = histogramaDeErrorOption([0, 1]) as unknown as Record<
      string,
      unknown
    >;
    expect((o.yAxis as { minInterval: number }).minInterval).toBe(1);
  });
});
