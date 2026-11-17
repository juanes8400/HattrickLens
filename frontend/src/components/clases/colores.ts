/** Constantes y cuentas que comparten las vistas de Clases de Jugador. Van
 *  aparte de los componentes para que la recarga en caliente siga funcionando. */
import type { JugadorDeClases } from "../../services/api";

/** Los colores con que se pintan los grupos. Son variables del tema, así que
 *  se ven igual de bien en claro y en oscuro. */
export const COLOR = {
  azul: "var(--accent)",
  verde: "var(--positive)",
  naranja: "var(--warning)",
  rojo: "var(--danger)",
  morado: "var(--mercado-venta)",
  gris: "var(--muted)",
  turquesa: "#14a3a3",
} as const;

/** Los colores que se pueden elegir para un grupo propio. La clave es la que
 *  guarda el servidor, que tiene la misma lista. */
export const COLORES_DE_GRUPO: Record<string, string> = {
  blue: COLOR.azul,
  red: COLOR.rojo,
  green: COLOR.verde,
  orange: COLOR.naranja,
  purple: COLOR.morado,
  teal: COLOR.turquesa,
  gray: COLOR.gris,
};

export interface Grupo {
  clave: string;
  nombre: string;
  color: string;
  jugadores: JugadorDeClases[];
}

/** Coloca etiquetas junto a sus puntos sin que se pisen entre sí ni tapen
 *  otro punto: prueba a la derecha, a la izquierda, arriba y abajo, y se
 *  queda con la primera posición libre. */
export interface Etiqueta {
  x: number;
  y: number;
  anchor: "start" | "middle" | "end";
}

export function colocarEtiquetas(
  puntos: { x: number; y: number; texto: string }[],
  limites: { izquierda: number; derecha: number },
  anchoDeLetra = 6.6,
): Etiqueta[] {
  const cajas: [number, number, number, number][] = [];
  const opciones: [number, number, Etiqueta["anchor"]][] = [
    [10, 4, "start"],
    [-10, 4, "end"],
    [0, -12, "middle"],
    [0, 19, "middle"],
    [10, -10, "start"],
    [10, 17, "start"],
    [-10, -10, "end"],
    [-10, 17, "end"],
    [0, -26, "middle"],
    [0, 33, "middle"],
  ];
  const choca = (b: [number, number, number, number]) =>
    b[0] < limites.izquierda ||
    b[2] > limites.derecha ||
    cajas.some(
      (c) => !(b[2] < c[0] || b[0] > c[2] || b[3] < c[1] || b[1] > c[3]),
    ) ||
    puntos.some(
      (p) =>
        b[0] - 4 < p.x && p.x < b[2] + 4 && b[1] - 4 < p.y && p.y < b[3] + 4,
    );
  return puntos.map((p) => {
    const ancho = p.texto.length * anchoDeLetra;
    let elegida: Etiqueta = { x: p.x + 10, y: p.y + 4, anchor: "start" };
    let caja: [number, number, number, number] = [
      p.x + 10,
      p.y - 6,
      p.x + 10 + ancho,
      p.y + 6,
    ];
    for (const [dx, dy, anchor] of opciones) {
      const x0 =
        anchor === "start"
          ? p.x + dx
          : anchor === "end"
            ? p.x + dx - ancho
            : p.x - ancho / 2;
      const b: [number, number, number, number] = [
        x0,
        p.y + dy - 10,
        x0 + ancho,
        p.y + dy + 2,
      ];
      if (!choca(b)) {
        elegida = { x: p.x + dx, y: p.y + dy, anchor };
        caja = b;
        break;
      }
    }
    cajas.push(caja);
    return elegida;
  });
}
