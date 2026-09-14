/** Prueba chi-cuadrado de independencia sobre una tabla de contingencia.
 *
 * 2026-09-13, pedido del usuario para Juveniles → Ojeadores: filas = quién
 * trajo al canterano, columnas = su categoría. ¿Depende la categoría de quién
 * lo trajo, o las diferencias caben en el azar?
 *
 * Vive aparte y con prueba porque el valor p sale de una función gamma
 * incompleta escrita aquí: un fallo en ella daría un «hay relación» falso sin
 * que ninguna pantalla lo delatara.
 */

/** Logaritmo de la función gamma (aproximación de Lanczos). */
function lnGamma(x: number): number {
  const g = [
    676.5203681218851, -1259.1392167224028, 771.3234287776531,
    -176.6150291621406, 12.507343278686905, -0.13857109526572012,
    9.984369578019572e-6, 1.5056327351493116e-7,
  ];
  if (x < 0.5) {
    return Math.log(Math.PI / Math.sin(Math.PI * x)) - lnGamma(1 - x);
  }
  const z = x - 1;
  let a = 0.9999999999998099;
  for (let i = 0; i < g.length; i++) a += g[i]! / (z + i + 1);
  const t = z + g.length - 0.5;
  return (
    0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(a)
  );
}

/** Gamma incompleta regularizada por abajo, P(s, x). */
export function gammaP(s: number, x: number): number {
  if (x <= 0) return 0;
  if (x < s + 1) {
    let suma = 1 / s;
    let termino = suma;
    for (let n = 1; n < 500; n++) {
      termino *= x / (s + n);
      suma += termino;
      if (Math.abs(termino) < Math.abs(suma) * 1e-14) break;
    }
    return suma * Math.exp(-x + s * Math.log(x) - lnGamma(s));
  }
  // Fracción continua para la cola: Q = 1 − P.
  let b = x + 1 - s;
  let c = 1 / 1e-300;
  let d = 1 / b;
  let h = d;
  for (let i = 1; i < 500; i++) {
    const an = -i * (i - s);
    b += 2;
    d = an * d + b;
    if (Math.abs(d) < 1e-300) d = 1e-300;
    c = b + an / c;
    if (Math.abs(c) < 1e-300) c = 1e-300;
    d = 1 / d;
    const delta = d * c;
    h *= delta;
    if (Math.abs(delta - 1) < 1e-14) break;
  }
  return 1 - Math.exp(-x + s * Math.log(x) - lnGamma(s)) * h;
}

export interface ResultadoChiCuadrado {
  chi2: number;
  gradosDeLibertad: number;
  p: number;
  /** V de Cramér: el TAMAÑO de la relación, de 0 a 1. */
  cramerV: number;
  n: number;
  /** Frecuencias esperadas, misma forma que la tabla. */
  esperadas: number[][];
  /** Cuántas celdas esperan menos de 5 casos. Con muchas, la prueba es frágil. */
  celdasConPocoEsperado: number;
}

/** `tabla[fila][columna]` = cuántos casos. Las filas y columnas vacías no
 *  cuentan: no aportan información y romperían los grados de libertad. */
export function chiCuadrado(tabla: number[][]): ResultadoChiCuadrado | null {
  const filasUtiles = tabla.filter((f) => f.some((v) => v > 0));
  if (filasUtiles.length < 2) return null;
  const nColumnas = filasUtiles[0]!.length;
  const columnasUtiles = [...Array(nColumnas).keys()].filter((j) =>
    filasUtiles.some((f) => (f[j] ?? 0) > 0),
  );
  if (columnasUtiles.length < 2) return null;
  const t = filasUtiles.map((f) => columnasUtiles.map((j) => f[j] ?? 0));
  const totalFila = t.map((f) => f.reduce((a, b) => a + b, 0));
  const totalColumna = columnasUtiles.map((_, j) =>
    t.reduce((a, f) => a + f[j]!, 0),
  );
  const n = totalFila.reduce((a, b) => a + b, 0);
  let chi2 = 0;
  let pocas = 0;
  const esperadas = t.map((f, i) =>
    f.map((o, j) => {
      const e = (totalFila[i]! * totalColumna[j]!) / n;
      if (e < 5) pocas += 1;
      chi2 += e > 0 ? (o - e) ** 2 / e : 0;
      return e;
    }),
  );
  const gl = (t.length - 1) * (columnasUtiles.length - 1);
  const p = 1 - gammaP(gl / 2, chi2 / 2);
  const k = Math.min(t.length, columnasUtiles.length) - 1;
  return {
    chi2,
    gradosDeLibertad: gl,
    p: Math.min(1, Math.max(0, p)),
    cramerV: k > 0 ? Math.sqrt(chi2 / (n * k)) : 0,
    n,
    esperadas,
    celdasConPocoEsperado: pocas,
  };
}
