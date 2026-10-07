import { describe, expect, it } from "vitest";
import { simularVenta } from "./simulacionDeVenta";

/** La simulación tiene que decir lo mismo que dirá el libro de transferencias
 *  el día que la venta ocurra de verdad. Las cifras de aquí salen de la misma
 *  fórmula que el servidor aplica a una venta real:
 *
 *      venta_neta = precio · (1 − %agente)
 *      saldo      = venta_neta − gastos
 *      ROI        = saldo ÷ gastos · 100
 */
describe("simularVenta", () => {
  it("descuenta lo que se lleva la casa", () => {
    const s = simularVenta({ precio: 4_000_000, agentPct: 0.1327, gastos: 0 });
    expect(s.neto).toBe(3_469_200);
  });

  it("el saldo es lo que entra menos lo invertido", () => {
    const s = simularVenta({
      precio: 4_000_000,
      agentPct: 0.1327,
      gastos: 3_000_000,
    });
    expect(s.saldo).toBe(469_200);
    expect(s.roiPct).toBe(15.64);
  });

  it("una venta ruinosa sale en negativo, no en cero", () => {
    const s = simularVenta({
      precio: 500_000,
      agentPct: 0.15,
      gastos: 3_000_000,
    });
    expect(s.saldo).toBe(-2_575_000);
    expect(s.roiPct).toBe(-85.83);
  });

  it("suma la comisión de reventa, que también es dinero suyo", () => {
    const s = simularVenta({
      precio: 1_000_000,
      agentPct: 0.1,
      gastos: 1_000_000,
      resaleBonusShare: 50_000,
    });
    expect(s.saldo).toBe(-50_000);
  });

  it("sin nada invertido no hay ROI, y eso no es un cero", () => {
    // Dividir por cero daría infinito, y un infinito en pantalla no dice nada.
    const s = simularVenta({ precio: 1_000_000, agentPct: 0.1, gastos: 0 });
    expect(s.roiPct).toBeNull();
  });

  it("dice a qué precio se queda uno igual que estaba", () => {
    const s = simularVenta({
      precio: 0,
      agentPct: 0.2,
      gastos: 800_000,
    });
    expect(s.precioDeEquilibrio).toBe(1_000_000);
    // Y pedir eso deja el saldo en cero, que es lo que significa.
    const equilibrio = simularVenta({
      precio: s.precioDeEquilibrio ?? 0,
      agentPct: 0.2,
      gastos: 800_000,
    });
    expect(equilibrio.saldo).toBe(0);
  });

  it("redondea al par, como el servidor", () => {
    // 1.000.001 × 0,5 = 500.000,5: `Math.round` daría 500.001 y el libro de
    // transferencias, que redondea con Python, apunta 500.000.
    const s = simularVenta({ precio: 1_000_001, agentPct: 0.5, gastos: 0 });
    expect(s.neto).toBe(500_000);
  });
});
