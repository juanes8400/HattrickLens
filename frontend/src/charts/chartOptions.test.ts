import { describe, expect, it } from "vitest";
import {
  anchoDeKernel,
  bandBetween,
  histogramaDeErrorOption,
  lineasDeUnGrupo,
  puentes,
  semanasEntre,
  serieDePuntosOption,
  tiraDePuntosOption,
  tramosPorConteo,
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

    /** 2026-11-14, pedido del usuario: «quitar los puntos azules del
     *  histograma». Ni puntos ni entrada en la leyenda. */
    it("las subastas abiertas no se pintan", () => {
      expect(porNombre(opcion, "Subasta abierta")).toBeUndefined();
      const todos = series(opcion).flatMap((x) => puntos(x));
      expect(todos.some((x) => x.tip.includes("no promedia"))).toBe(false);
      expect(todos).toHaveLength(2);
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
    });

    it("las marcas de media y mediana se pueden preguntar", () => {
      // `silent: true` las dejaba mudas, y son el dato que más se mira.
      expect(porNombre(opcion, "Idéntico")?.markLine?.silent).toBe(false);
    });
  });

  describe("la serie en el tiempo", () => {
    const opcion = serieDePuntosOption(
      [
        {
          cuando: "2026-10-01",
          semana: "83-05",
          enCurso: false,
          media: 150_000,
          precios: PRECIOS,
        },
        {
          cuando: "2026-10-08",
          semana: "83-06",
          enCurso: true,
          media: 160_000,
          precios: PRECIOS,
        },
      ],
      COMUNES,
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

    it("el tooltip de un punto dice de qué SEMANA es", () => {
      // Era la fecha de la lectura; desde el 2026-11-08 la serie es semanal
      // y lo que sitúa un punto es su semana de Hattrick, no el día en que
      // lo leímos.
      expect(puntos(porNombre(opcion, "Idéntico"))[0]!.tip).toContain("83-05");
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

  /** 2026-11-08, decisión del usuario: un punto por semana de Hattrick, hecho
   *  de lo que cerró ESA semana. Lo que se fija aquí es el dibujo: el eje
   *  enseña también las semanas sin ventas, el tramo que las cruza va
   *  punteado, y la semana en curso se distingue de las selladas. */
  describe("la serie semanal", () => {
    const lectura = (semana: string, media: number, enCurso = false) => ({
      cuando: "2026-11-09",
      semana,
      enCurso,
      media,
      precios: [[media, true, 100]] as [number, boolean, number][],
    });
    // Tres semanas con ventas y dos huecos: 83-15 y 83-16 se quedan vacías, y
    // el salto de 83-16 a 84-01 es un cambio de temporada.
    const opcion = serieDePuntosOption(
      [
        lectura("83-13", 100_000),
        lectura("83-14", 120_000),
        lectura("84-01", 90_000, true),
      ],
      { ...COMUNES, acumulado: 105_000, etiquetaAcumulado: "acumulado" },
    ) as unknown as Record<string, unknown>;

    type Linea = Serie & {
      connectNulls?: boolean;
      lineStyle?: { type?: string };
      markLine?: { data?: { yAxis: number }[] };
    };
    const lineas = () =>
      series(opcion).filter((s) => s.name === "Media") as Linea[];
    type PuntoDeMedia = {
      value: number;
      tip: string;
      itemStyle: { color: string };
    } | null;

    it("el eje lleva TODAS las semanas, también las vacías", () => {
      const eje = (opcion.xAxis as { data: string[] }).data;
      expect(eje).toEqual(["83-13", "83-14", "83-15", "83-16", "84-01"]);
    });

    it("la última semana se rotula siempre, aunque no quepan todas", () => {
      const rotulo = (opcion.xAxis as { axisLabel: { showMaxLabel: boolean } })
        .axisLabel;
      expect(rotulo.showMaxLabel).toBe(true);
    });

    it("cada media va en SU semana y las vacías se quedan sin punto", () => {
      const medias = lineas()[0]!.data as PuntoDeMedia[];
      expect(medias.map((p) => p?.value ?? null)).toEqual([
        100_000,
        120_000,
        null,
        null,
        90_000,
      ]);
    });

    it("la sólida se corta en el hueco y la punteada lo cruza", () => {
      const [solida, puente] = lineas();
      // La sólida va PRIMERA: es la que se encuentra por nombre, y la que
      // lleva los símbolos y los tooltips.
      expect(solida!.connectNulls).toBe(false);
      expect(solida!.symbol).not.toBe("none");
      expect(puente!.lineStyle?.type).toBe("dotted");
      expect(puente!.symbol).toBe("none");
      // SÓLO EL HUECO (2026-11-15): de 83-14 a 84-01, y nada entre 83-13 y
      // 83-14, que son seguidas. Con los mismos precios: no inventa ninguno.
      expect(puente!.data).toEqual([[1, 120_000], [4, 90_000], null]);
    });

    it("la semana en curso va HUECA y lo dice", () => {
      const medias = lineas()[0]!.data as PuntoDeMedia[];
      expect(medias[0]!.itemStyle.color).not.toBe("transparent");
      expect(medias[4]!.itemStyle.color).toBe("transparent");
      expect(medias[4]!.tip).toContain("en curso");
      expect(medias[0]!.tip).not.toContain("en curso");
    });

    it("una sola venta se dice en singular", () => {
      const medias = lineas()[0]!.data as PuntoDeMedia[];
      expect(medias[0]!.tip).toContain("sobre 1 venta");
      expect(medias[0]!.tip).not.toContain("ventas");
    });

    it("la raya del acumulado sólo sale cuando hay acumulado", () => {
      expect(lineas()[0]!.markLine?.data).toEqual([{ yAxis: 105_000 }]);
      const sin = serieDePuntosOption(
        [lectura("83-13", 100_000)],
        COMUNES,
      ) as unknown as Record<string, unknown>;
      const linea = series(sin).find((s) => s.name === "Media") as Linea;
      expect(linea.markLine).toBeUndefined();
    });

    // 2026-11-15: la gráfica ya no vuelve a empezar cuando cambian los
    // criterios. Sigue, y la semana del cambio lleva una raya vertical.
    describe("la semana en que cambiaron los criterios", () => {
      const conCambio = (
        cambia: string,
        extra: Partial<Parameters<typeof serieDePuntosOption>[1]> = {},
      ) =>
        serieDePuntosOption(
          [
            lectura("83-13", 100_000),
            { ...lectura("83-14", 160_000), cambios: [{}] },
            lectura("84-01", 170_000),
          ].map((l) => (l.semana === cambia ? l : { ...l, cambios: [] })),
          {
            ...COMUNES,
            etiquetaCambio: "cambio",
            describirCambio: (i) => `marca ${i}`,
            ...extra,
          },
        ) as unknown as Record<string, unknown>;
      type ConMarca = Serie & {
        markLine?: { data?: { xAxis: string; tip: string }[] };
      };
      const marcas = (opcion: Record<string, unknown>) =>
        series(opcion).flatMap(
          (s) =>
            (s as ConMarca).markLine?.data?.filter((d) => "xAxis" in d) ?? [],
        );

      it("lleva una raya en esa semana, con lo que cambió", () => {
        expect(marcas(conCambio("83-14"))).toEqual([
          { xAxis: "83-14", tip: "marca 1" },
        ]);
      });

      it("la raya sale aunque todavía no haya media", () => {
        expect(marcas(conCambio("83-14", { conMedia: false }))).toHaveLength(1);
      });

      it("sin cambio no hay raya", () => {
        expect(marcas(conCambio("ninguna"))).toEqual([]);
      });
    });

    it("lo que queda fuera de las 25 semanas no se pinta encima de otra", () => {
      // La serie ya no se corta al cambiar los criterios, así que puede traer
      // más semanas de las que caben en el eje.
      const larga = serieDePuntosOption(
        [lectura("80-01", 999_000), lectura("84-01", 100_000)],
        COMUNES,
      ) as unknown as Record<string, unknown>;
      const puntos = series(larga)
        .filter((s) => s.type === "scatter")
        .flatMap((s) => s.data as { value: [number, number] }[]);
      expect(puntos.map((p) => p.value[1])).toEqual([100_000]);
    });
  });

  describe("puentes", () => {
    it("dos semanas seguidas no llevan punteado", () => {
      expect(puentes([1, 2, 3])).toEqual([]);
    });

    it("cada hueco es un tramo suelto", () => {
      expect(puentes([1, null, 3, 4, null, null, 7])).toEqual([
        [0, 1],
        [2, 3],
        null,
        [3, 4],
        [6, 7],
        null,
      ]);
    });

    it("los vacíos de los extremos no se unen con nada", () => {
      expect(puentes([null, 2, null])).toEqual([]);
    });
  });

  describe("semanasEntre", () => {
    it("cuenta dieciséis semanas por temporada al cruzar de una a otra", () => {
      expect(semanasEntre("83-15", "84-02")).toEqual([
        "83-15",
        "83-16",
        "84-01",
        "84-02",
      ]);
    });

    it("una sola semana es un eje de un rótulo", () => {
      expect(semanasEntre("84-01", "84-01")).toEqual(["84-01"]);
    });

    it("no pasa de 25 rótulos, y se queda con los más recientes", () => {
      const eje = semanasEntre("80-01", "84-01");
      expect(eje).toHaveLength(25);
      expect(eje[eje.length - 1]).toBe("84-01");
      expect(eje[0]).toBe("82-09");
    });
  });
});

/** El reparto del error de la fórmula de entrenamiento (2026-11-01; sin
 *  redondear, con kernel, 2026-11-03). Lo que se comprueba es lo que lo hace
 *  valer algo: que está centrado en el cero, que cada subida aparece en su
 *  decimal exacto y que el área bajo la curva son las subidas que hay. */
describe("histogramaDeErrorOption", () => {
  const curva = (o: Record<string, unknown>) =>
    (o.series as { data: number[][] }[])[0]!.data;
  const marcas = (o: Record<string, unknown>) =>
    (o.series as { data: number[][] }[])[1]!.data;
  const eje = (o: Record<string, unknown>) =>
    o.xAxis as { min: number; max: number };
  const opcion = (errores: number[]) =>
    histogramaDeErrorOption(errores) as unknown as Record<string, unknown>;

  it("está centrado en el cero y es simétrico", () => {
    const o = opcion([-2, 1]);
    expect(eje(o).min).toBe(-eje(o).max);
    // El cero en medio: si no, el reparto engaña sobre de qué lado cae el
    // montón.
    const xs = curva(o).map((p) => p[0]!);
    expect(xs[0]).toBe(eje(o).min);
    expect(xs[xs.length - 1]).toBe(eje(o).max);
  });

  it("cada subida se marca en su decimal, sin redondear", () => {
    // Éste es el fallo que había: con `Math.round` por cubetas, -1,2 y -0,9
    // caían juntas en la de -1 y -0,3 se iba con 0,1 y 0,4 a la del cero.
    const o = opcion([-1.2, -0.9, 0.1, 0.4, -0.3, 1.1]);
    expect(marcas(o).map((m) => m[0])).toEqual([
      -1.2, -0.9, 0.1, 0.4, -0.3, 1.1,
    ]);
    // Y todas en la línea del cero, que es donde se leen contra la curva.
    expect(marcas(o).every((m) => m[1] === 0)).toBe(true);
  });

  it("el área bajo la curva son las subidas que hay", () => {
    // Lo que hace legible el eje: si el área no fuera el número de subidas,
    // «subidas por semana» sería una etiqueta inventada.
    const errores = [-1.2, -0.9, 0.1, 0.4, -0.3, 1.1];
    const o = opcion(errores);
    const puntos = curva(o);
    let area = 0;
    for (let i = 1; i < puntos.length; i += 1) {
      const [x0, y0] = puntos[i - 1]! as [number, number];
      const [x1, y1] = puntos[i]! as [number, number];
      area += ((y0 + y1) / 2) * (x1 - x0);
    }
    expect(area).toBeCloseTo(errores.length, 1);
  });

  it("dos errores que no se parecen no acaban en el mismo sitio", () => {
    // -1,4 y -0,6 redondeaban los dos a -1 y salían en la misma barra.
    const o = opcion([-1.4, -0.6]);
    const ms = marcas(o).map((m) => m[0]);
    expect(ms).toEqual([-1.4, -0.6]);
    expect(ms[0]).not.toBe(ms[1]);
  });

  it("con una sola subida clavada sigue habiendo curva", () => {
    const o = opcion([0]);
    expect(marcas(o)).toEqual([[0, 0]]);
    // El eje no se encoge alrededor de un único punto: ±1 semana como
    // mínimo, o un error diminuto parecería enorme.
    expect(eje(o).max).toBeGreaterThanOrEqual(1);
    expect(curva(o).some((pt) => pt[1]! > 0)).toBe(true);
  });

  it("sin ninguna subida no revienta", () => {
    const o = opcion([]);
    expect(marcas(o)).toEqual([]);
    expect(curva(o).every((pt) => pt[1] === 0)).toBe(true);
  });

  it("el ancho de campana nunca baja del suelo", () => {
    // Con una sola observación no hay dispersión de la que deducirlo, y con
    // muchas idénticas tampoco: en los dos casos manda el suelo.
    expect(anchoDeKernel([0.3])).toBeCloseTo(0.2, 6);
    expect(anchoDeKernel([0.3, 0.3, 0.3])).toBeCloseTo(0.2, 6);
    // Y con dispersión de verdad, lo supera.
    expect(anchoDeKernel([-3, -1, 0, 1, 3])).toBeGreaterThan(0.2);
  });
});

/** «Mirar a» (2026-11-17): la media de un grupo se puntea donde cambia cuántos
 *  jugadores entran en ella, porque ese salto lo trae quien llega. */
describe("tramosPorConteo", () => {
  it("con el mismo conteo todo es un tramo continuo, sin punteado", () => {
    const { continuos, puentes } = tramosPorConteo([1, 2, 3], [2, 2, 2]);
    expect(continuos[0]).toEqual([1, 2, 3]);
    expect(continuos[1]).toEqual([null, null, null]);
    expect(puentes).toEqual([]);
  });

  it("puntea justo donde cambia el conteo, y los tramos alternan de serie", () => {
    const { continuos, puentes } = tramosPorConteo(
      [4, 4, 6, 6, 5],
      [1, 1, 2, 2, 3],
    );
    expect(puentes).toEqual([[1, 4], [2, 6], null, [3, 6], [4, 5], null]);
    // Dos tramos seguidos nunca en la misma serie: si no, la línea continua
    // los uniría por encima del punteado.
    expect(continuos[0]).toEqual([4, 4, null, null, 5]);
    expect(continuos[1]).toEqual([null, null, 6, 6, null]);
  });

  it("desde una semana sin nadie no se salta: no hay de dónde", () => {
    const { puentes } = tramosPorConteo([null, null, 8], [0, 0, 1]);
    expect(puentes).toEqual([]);
  });
});

describe("lineasDeUnGrupo", () => {
  const opcion = lineasDeUnGrupo(
    ["83-10", "83-11", "83-12"],
    [
      { name: "Gangas", values: [5, 6, 7] },
      { name: "Plantilla completa", values: [9, 9, 9], reference: true },
    ],
    [1, 2, 2],
  );
  const series = opcion.series as Record<string, unknown>[];

  it("los tramos llevan el nombre de su serie y quedan fuera del tooltip", () => {
    const deGangas = series.filter((s) => s.name === "Gangas");
    expect(deGangas).toHaveLength(4);
    expect(deGangas.filter((s) => s.id).every((s) => s.silent)).toBe(true);
  });

  it("la referencia va entera, en gris y sin punteado", () => {
    const referencia = series.filter((s) => s.name === "Plantilla completa");
    expect(referencia).toHaveLength(1);
    expect(referencia[0]?.data).toEqual([9, 9, 9]);
    expect(referencia[0]?.color).toBe("#94a3b8");
  });

  it("bajo cada semana, cuántos entran en la media", () => {
    const eje = opcion.xAxis as {
      axisLabel: { formatter: (v: string, i: number) => string };
    };
    expect(eje.axisLabel.formatter("83-10", 0)).toBe("83-10\n{n|1}");
  });
});
