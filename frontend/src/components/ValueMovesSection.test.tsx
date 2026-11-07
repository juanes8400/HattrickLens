import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ValueMovesSection } from "./SyncComparisonReport";
import type { ValueMove } from "../services/api";

/** 2026-11-07, pedido del usuario: «Cambios: advertir qué movimientos de valor
 *  de los jugadores ocurrieron al conectar, con umbrales (±5 % del valor)».
 *
 *  Lo que se vigila aquí es que los cuatro casos NO se vean iguales. Un
 *  porcentaje puesto donde no toca es la forma más fácil de que esta pantalla
 *  anuncie una subida que no ocurrió. */
const base: ValueMove = {
  htPlayerId: 472301981,
  name: "Iñaki Bordalás",
  kind: "movimiento",
  before: 100_000,
  after: 150_000,
  delta: 50_000,
  percent: 50,
  nBefore: 6,
  nAfter: 8,
  from: "2026-11-01T12:00:00+00:00",
  to: "2026-11-07T12:00:00+00:00",
  currency: "US$",
};

/** Cuántos porcentajes hay EN LAS FILAS.
 *
 *  No vale un `not.toContain("%")` sobre el panel entero: su propio subtítulo
 *  dice «a partir del ±5 %», así que esa comprobación fallaría siempre y por
 *  el motivo equivocado. Lo que hay que mirar es si alguna FILA lleva cifra. */
const porcentajesEnFilas = (html: string) =>
  (html.match(/font-semibold tabular-nums/g) ?? []).length;

const pintar = (...moves: Partial<ValueMove>[]) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ValueMovesSection
        moves={moves.map((mv, i) => ({
          ...base,
          htPlayerId: base.htPlayerId + i,
          ...mv,
        }))}
      />
    </MemoryRouter>,
  );

describe("movimientos de valor", () => {
  it("no se pinta cuando no hay nada que avisar", () => {
    // Un panel que dice «no se movió nada» en cada sincronización enseña a
    // saltárselo, y el día que traiga algo de verdad no se mira.
    expect(pintar()).toBe("");
  });

  it("enseña el porcentaje con su signo y de qué a qué", () => {
    const html = pintar({});
    expect(html).toContain("Iñaki Bordalás");
    expect(html).toContain("+50%");
    expect(porcentajesEnFilas(html)).toBe(1);
    expect(html).toContain("100.000");
    expect(html).toContain("150.000");
    // Con cuántas ventas se hizo cada lectura: un movimiento apoyado en dos
    // ventas y otro apoyado en diez no merecen la misma confianza.
    expect(html).toContain("(6 → 8 ventas)");
  });

  it("una bajada se avisa igual que una subida, y en rojo", () => {
    const html = pintar({ after: 70_000, delta: -30_000, percent: -30 });
    expect(html).toContain("-30%");
    expect(html).toContain("--danger");
    expect(html).not.toContain("--positive");
  });

  it("una subida va en verde", () => {
    expect(pintar({})).toContain("--positive");
  });

  it("un estreno no lleva porcentaje", () => {
    // No se puede dividir por lo que no había: un «+∞ %» no es una cifra y un
    // 0 % se leería como «no se movió».
    const html = pintar({
      kind: "estreno",
      before: null,
      percent: null,
      delta: null,
      nBefore: 0,
    });
    expect(html).toContain("Estrenaron valor");
    expect(porcentajesEnFilas(html)).toBe(0);
    expect(html).toContain("150.000");
  });

  it("un cambio de criterios SÍ lleva porcentaje, y dice que no es del mercado", () => {
    // 2026-11-07, pedido del usuario: «quiero que se notifique el cambio en %
    // de valoración así haya habido cambio de edad y lo otro». Lo había hecho
    // sin porcentaje y se lo discutí; lo reafirmó, y tiene su razón: la cifra
    // que ve en Valor de Plantilla cambió de verdad, y el total de su
    // plantilla con ella.
    //
    // LO QUE NO SE PIERDE es el significado: el grupo y su nota siguen
    // diciendo que esa subida no la hizo el mercado, que es lo que de verdad
    // había que no mezclar.
    const html = pintar({ kind: "otra gente", percent: 18 });
    expect(html).toContain("Ahora se les compara con otra gente");
    expect(html).toContain("el mercado no la movió");
    expect(html).toContain("+18%");
    expect(porcentajesEnFilas(html)).toBe(1);
  });

  it("perder el número no se cuenta como una caída", () => {
    const html = pintar({
      kind: "perdido",
      after: null,
      percent: null,
      delta: null,
      nAfter: 0,
    });
    expect(html).toContain("Se quedaron sin número");
    expect(html).toContain("no valen menos");
    expect(porcentajesEnFilas(html)).toBe(0);
    expect(html).not.toContain("--danger");
  });

  it("agrupa cada clase bajo su propio título", () => {
    const html = pintar(
      {},
      { kind: "estreno", before: null, percent: null, delta: null },
      { kind: "otra gente", percent: 18 },
      { kind: "perdido", after: null, percent: null, delta: null },
    );
    for (const titulo of [
      "Se movieron",
      "Estrenaron valor",
      "Ahora se les compara con otra gente",
      "Se quedaron sin número",
    ]) {
      expect(html).toContain(titulo);
    }
  });

  it("un grupo vacío no deja un título huérfano", () => {
    const html = pintar({ kind: "perdido", after: null, percent: null });
    expect(html).toContain("Se quedaron sin número");
    expect(html).not.toContain("Se movieron");
    expect(html).not.toContain("Estrenaron valor");
  });

  it("enlaza a la ficha del jugador", () => {
    expect(pintar({})).toContain("472301981");
  });
});
