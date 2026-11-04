import { describe, expect, it } from "vitest";
import type { Equipo, Petalo } from "./FlorDeFuerza";
import { normalizar, valorComparable, valorPintado } from "./FlorDeFuerza";

/** El orden de la flor, 2026-11-03.
 *
 *  Pedido del usuario: «lo de la flor debe estar ordenado por "dato" y no por
 *  columna flor, ya que por redondeo podemos confundir el orden real».
 *
 *  La columna «flor» es el dato normalizado a un entero de 0 a 100, así que
 *  dos equipos que no empatan de verdad empatan ahí, y el desempate por nombre
 *  los dejaba en un orden que no era el real. No es un detalle estético: el
 *  puesto que la flor anuncia («3.º de 8») sale de esta misma lista.
 */
const EQUIPOS: Equipo[] = [
  { htTeamId: 1, nombre: "Zeta", propio: false },
  { htTeamId: 2, nombre: "Alfa", propio: false },
  { htTeamId: 3, nombre: "Mío", propio: true },
  // El ancla de abajo. La normalización es min-max sobre la propia muestra,
  // así que para que tres valores casi iguales colisionen en el mismo entero
  // hace falta que el rango sea ancho; sin este equipo, 998 y 1000 serían el
  // 0 y el 100.
  { htTeamId: 4, nombre: "Farolillo", propio: false },
];

function petalo(valores: Record<number, number>, menorEsMejor = false): Petalo {
  return {
    clave: "x",
    nombre: "X",
    valores: new Map(Object.entries(valores).map(([k, v]) => [Number(k), v])),
    menorEsMejor,
    formato: (v) => String(v),
    frase: () => "",
  };
}

describe("normalizar", () => {
  it("ordena por el dato, aunque la columna flor empate", () => {
    // Los tres de arriba caen en el mismo entero: 1000 → 100, 999 → 99,9 →
    // 100, 998 → 99,8 → 100. Antes mandaba el nombre y «Alfa», que es el peor
    // de los tres, salía primero.
    const lista = normalizar(
      petalo({ 1: 999, 2: 998, 3: 1000, 4: 0 }),
      EQUIPOS,
    );
    expect(lista.map((x) => x.nombre)).toEqual([
      "Mío",
      "Zeta",
      "Alfa",
      "Farolillo",
    ]);
    // Y la columna que se pinta sigue siendo el entero: lo que cambia es el
    // orden, no lo que se enseña.
    expect(lista.map((x) => x.valor)).toEqual([100, 100, 100, 0]);
  });

  it("respeta que en algunos pétalos lo menor es lo mejor", () => {
    // La posición esperada en la simulación: 1,2 es mejor que 1,4.
    const lista = normalizar(
      petalo({ 1: 1.4, 2: 1.6, 3: 1.2, 4: 8 }, true),
      EQUIPOS,
    );
    expect(lista.map((x) => x.nombre)).toEqual([
      "Mío",
      "Zeta",
      "Alfa",
      "Farolillo",
    ]);
  });

  it("desempata por nombre sólo cuando el dato es idéntico", () => {
    const lista = normalizar(petalo({ 1: 5, 2: 5, 3: 9, 4: 1 }), EQUIPOS);
    expect(lista.map((x) => x.nombre)).toEqual([
      "Mío",
      "Alfa",
      "Zeta",
      "Farolillo",
    ]);
  });

  it("guarda el 0-100 sin redondear además del redondeado", () => {
    // `exacto` es lo único comparable ENTRE pétalos --los datos crudos de
    // Ataque y de TSI no lo son-- y por eso se elige con él cuál es el más
    // flojo al abrir la flor.
    const lista = normalizar(
      petalo({ 1: 999, 2: 998, 3: 1000, 4: 0 }),
      EQUIPOS,
    );
    const exactos = lista.map((x) => x.exacto);
    expect(exactos[0]).toBeGreaterThan(exactos[1]!);
    expect(exactos[1]).toBeGreaterThan(exactos[2]!);
    expect(exactos[0]).toBeCloseTo(100, 6);
  });

  it("deja fuera a quien no tiene el dato", () => {
    const lista = normalizar(petalo({ 1: 10, 3: 20 }), EQUIPOS);
    expect(lista.map((x) => x.nombre)).toEqual(["Mío", "Zeta"]);
  });

  it("con un solo equipo no divide por cero", () => {
    const lista = normalizar(petalo({ 3: 7 }), EQUIPOS);
    expect(lista).toHaveLength(1);
    expect(lista[0]!.valor).toBe(100);
  });
});

/** Las dos lecturas del mismo número, 2026-11-03.
 *
 *  Al ordenar la flor por el dato hizo falta guardar el 0-100 SIN redondear,
 *  y durante un rato la misma función servía para pintar y para comparar: la
 *  flor salió llena de decimales --«99.83333333333333» dentro del pétalo--.
 *  Separadas y con nombre, lo que queda fijado aquí es cuál hace qué.
 */
describe("valorPintado y valorComparable", () => {
  const lista = normalizar(petalo({ 1: 999, 2: 998, 3: 1000, 4: 0 }), EQUIPOS);

  it("lo que se pinta es siempre un entero", () => {
    const v = valorPintado(lista);
    expect(v).not.toBeNull();
    expect(Number.isInteger(v)).toBe(true);
  });

  it("lo que se compara no se redondea", () => {
    // 999 sobre un rango de 1000 es 99,9: si esto fuera entero, empataría con
    // el 100 y al entrar se abriría un pétalo que no es el más flojo.
    const exacto = valorComparable(
      normalizar(petalo({ 1: 1000, 2: 998, 3: 999, 4: 0 }), EQUIPOS),
    );
    expect(exacto).toBeCloseTo(99.9, 6);
    expect(Number.isInteger(exacto)).toBe(false);
  });

  it("las dos devuelven nulo si el equipo propio no tiene el dato", () => {
    const sinMio = normalizar(petalo({ 1: 10, 2: 20 }), EQUIPOS);
    expect(valorPintado(sinMio)).toBeNull();
    expect(valorComparable(sinMio)).toBeNull();
  });
});
