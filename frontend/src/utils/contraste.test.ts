import { describe, expect, it } from "vitest";

/**
 * El contraste de la paleta, medido y no opinado.
 *
 * Los colores se eligen mirando UNA pantalla, y así es como se cuelan: el
 * 2026-08-31 la paleta de series de las gráficas era una sola lista con los
 * valores del tema oscuro, y en modo claro el verde medía 2,38, el ámbar 2,04
 * y el cian 2,43 — la mitad de las series de cualquier gráfica se leían mal en
 * el tema por defecto. Nadie lo había visto porque a ojo «se distinguen».
 *
 * Este test fija el umbral de 3:1 para elementos gráficos (WCAG 1.4.11), que
 * es el que aplica a una línea o una barra. Para TEXTO el umbral es 4,5:1 y
 * hay tres tokens que hoy no llegan; están listados abajo con su medida, sin
 * hacer fallar la suite, porque subirlos es una decisión de identidad visual
 * que le corresponde al dueño del proyecto.
 */

const SUPERFICIE = { dark: "#111113", light: "#ffffff" } as const;

/** Lo mismo que hay en index.css y en charts/colors.ts. */
const TOKENS = {
  dark: {
    accent: "#4f7cff",
    positive: "#2fbf71",
    warning: "#f5a524",
    danger: "#e5484d",
    muted: "#8b8b93",
    "mercado-venta": "#a78bda",
    "mercado-compra": "#d9a15c",
  },
  light: {
    accent: "#3b63e0",
    positive: "#1a9e5c",
    warning: "#bd8109",
    danger: "#d1383d",
    muted: "#71717a",
    "mercado-venta": "#6d4fa0",
    "mercado-compra": "#96651f",
  },
} as const;

/** La paleta de series de `charts/Chart.tsx`. */
const SERIES = {
  dark: ["#4f7cff", "#2fbf71", "#f5a524", "#e5484d", "#8b5cf6", "#06b6d4"],
  light: ["#3b63e0", "#1a9e5c", "#bd8109", "#d1383d", "#7c4ddb", "#0e7490"],
} as const;

function luminancia(hex: string): number {
  const c = hex.replace("#", "");
  const canales = [0, 2, 4].map((i) => {
    const x = parseInt(c.slice(i, i + 2), 16) / 255;
    return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
  }) as [number, number, number];
  return 0.2126 * canales[0] + 0.7152 * canales[1] + 0.0722 * canales[2];
}

export function contraste(a: string, b: string): number {
  const [alta, baja] = [luminancia(a), luminancia(b)].sort((x, y) => y - x) as [
    number,
    number,
  ];
  return (alta + 0.05) / (baja + 0.05);
}

const MINIMO_GRAFICO = 3;

describe("la paleta se ve en los dos temas", () => {
  it("mide bien: negro sobre blanco son 21 a 1", () => {
    // Sin esto, un error en la fórmula haría pasar todo lo demás.
    expect(contraste("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contraste("#ffffff", "#ffffff")).toBeCloseTo(1, 2);
  });

  for (const tema of ["dark", "light"] as const) {
    it(`los tokens de ${tema} llegan a 3:1 sobre su superficie`, () => {
      const flojos = Object.entries(TOKENS[tema])
        .map(
          ([nombre, hex]) =>
            [nombre, contraste(hex, SUPERFICIE[tema])] as const,
        )
        .filter(([, r]) => r < MINIMO_GRAFICO)
        .map(([nombre, r]) => `${nombre} ${r.toFixed(2)}`);
      expect(flojos, `por debajo de ${MINIMO_GRAFICO}:1 en ${tema}`).toEqual(
        [],
      );
    });

    it(`las series de ${tema} llegan a 3:1 sobre su superficie`, () => {
      const flojas = SERIES[tema]
        .map((hex) => [hex, contraste(hex, SUPERFICIE[tema])] as const)
        .filter(([, r]) => r < MINIMO_GRAFICO)
        .map(([hex, r]) => `${hex} ${r.toFixed(2)}`);
      expect(flojas, `por debajo de ${MINIMO_GRAFICO}:1 en ${tema}`).toEqual(
        [],
      );
    });
  }

  it("deja constancia de los tokens que no llegan al umbral de TEXTO", () => {
    // No falla: es un inventario. Si alguien sube uno de estos, este test se
    // lo dirá al cambiar la cuenta, y entonces se actualiza a conciencia.
    const bajoTexto = Object.entries(TOKENS.light)
      .filter(([, hex]) => contraste(hex, SUPERFICIE.light) < 4.5)
      .map(([nombre]) => nombre)
      .sort();
    // `muted` sí llega sobre una tarjeta blanca (4,83); se queda en 4,32
    // sólo sobre el fondo gris de la página. `positive` y `warning`
    // pasan el umbral gráfico pero no el de texto: subirlos mueve el
    // verde y el ámbar de toda la interfaz, y eso es del dueño.
    expect(bajoTexto).toEqual(["positive", "warning"]);
  });
});
