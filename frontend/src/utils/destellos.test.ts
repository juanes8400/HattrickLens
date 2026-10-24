/** Los destellos del mapa en vivo.
 *
 *  Lo que se prueba aquí no se ve en una captura de pantalla, que es la razón
 *  de que exista el fichero. Son tres cosas con filo:
 *
 *   · DOS CLICS SOLAPADOS DEL MISMO PAÍS. Si el encendido fuera un `true` en
 *     vez de una cuenta, el primero en cumplir su segundo apagaría también al
 *     segundo, que acababa de empezar. El país parpadearía cuando más
 *     actividad tiene, que es justo al revés de lo que el mapa viene a decir.
 *   · QUE `getSnapshot` DEVUELVA LA MISMA REFERENCIA mientras nada cambia.
 *     `useSyncExternalStore` compara por identidad: un objeto nuevo en cada
 *     llamada es un bucle infinito de renders.
 *   · QUE APAGAR APAGUE DE VERDAD. Un reloj pendiente que toca el almacén
 *     después de apagar vuelve a encender un país solo.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { creaDestellos } from "./destellos";

const DURACION = 1000;
const CUANDO = "2026-10-24T10:00:00Z";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("el almacén de destellos", () => {
  it("empieza vacío", () => {
    const d = creaDestellos(DURACION);
    expect(d.getSnapshot()).toEqual({
      encendidos: {},
      vistos: 0,
      ultimo: null,
    });
  });

  it("enciende un país y lo apaga él solo", () => {
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    expect(d.getSnapshot().encendidos).toEqual({ co: 1 });

    vi.advanceTimersByTime(DURACION + 1);
    expect(d.getSnapshot().encendidos).toEqual({});
  });

  it("DOS CLICS SOLAPADOS no se apagan antes de tiempo", () => {
    // El fallo que justifica la cuenta. Segundo clic a mitad del primero:
    // cuando el primero cumple, el país sigue encendido por el segundo.
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    vi.advanceTimersByTime(DURACION / 2);
    d.encender("co", CUANDO);
    expect(d.getSnapshot().encendidos).toEqual({ co: 2 });

    // Cumple el primero: queda uno.
    vi.advanceTimersByTime(DURACION / 2 + 1);
    expect(d.getSnapshot().encendidos).toEqual({ co: 1 });

    // Y cumple el segundo.
    vi.advanceTimersByTime(DURACION / 2 + 1);
    expect(d.getSnapshot().encendidos).toEqual({});
  });

  it("dos países a la vez no se estorban", () => {
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    d.encender("se", CUANDO);
    expect(d.getSnapshot().encendidos).toEqual({ co: 1, se: 1 });
  });

  it("cuenta los destellos y recuerda el último", () => {
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    d.encender("se", "2026-10-24T10:00:05Z");

    const estado = d.getSnapshot();
    expect(estado.vistos).toBe(2);
    expect(estado.ultimo).toEqual({
      code: "se",
      cuando: "2026-10-24T10:00:05Z",
    });
  });

  it("la cuenta NO baja al apagarse un destello", () => {
    // «Vistos» son los que han pasado, no los que están encendidos. Si bajara,
    // el contador de la cabecera volvería a cero cada segundo de calma.
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    vi.advanceTimersByTime(DURACION + 1);
    expect(d.getSnapshot().vistos).toBe(1);
    expect(d.getSnapshot().ultimo).not.toBeNull();
  });

  it("devuelve LA MISMA referencia mientras nada cambia", () => {
    // `useSyncExternalStore` compara por identidad: un objeto nuevo en cada
    // llamada es un bucle de renders sin fin.
    const d = creaDestellos(DURACION);
    expect(d.getSnapshot()).toBe(d.getSnapshot());
    d.encender("co", CUANDO);
    const tras = d.getSnapshot();
    expect(d.getSnapshot()).toBe(tras);
  });

  it("avisa a quien esté mirando, y deja de avisar al desuscribirse", () => {
    const d = creaDestellos(DURACION);
    const aviso = vi.fn();
    const cortar = d.subscribe(aviso);

    d.encender("co", CUANDO);
    expect(aviso).toHaveBeenCalledTimes(1);

    // Y también al apagarse solo, que es el aviso que redibuja el mapa en
    // negro.
    vi.advanceTimersByTime(DURACION + 1);
    expect(aviso).toHaveBeenCalledTimes(2);

    cortar();
    d.encender("se", CUANDO);
    expect(aviso).toHaveBeenCalledTimes(2);
  });

  it("apagar todo deja el almacén como recién nacido", () => {
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    d.apagarTodo();
    expect(d.getSnapshot()).toEqual({
      encendidos: {},
      vistos: 0,
      ultimo: null,
    });
  });

  it("y los relojes pendientes NO vuelven a encender nada", () => {
    // Sin soltar los relojes, el `setTimeout` del clic de antes se dispara
    // después de apagar y deja un país encendido con la cuenta en cero: un
    // destello fantasma en un mapa que se mandó apagar.
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    d.apagarTodo();

    vi.advanceTimersByTime(DURACION * 3);
    expect(d.getSnapshot().encendidos).toEqual({});
    expect(d.getSnapshot().vistos).toBe(0);
  });

  it("soltar los relojes no avisa a nadie", () => {
    // Es lo que se llama al desmontar: tocar el almacén cuando ya nadie lo
    // lee no hace falta.
    const d = creaDestellos(DURACION);
    const aviso = vi.fn();
    d.encender("co", CUANDO);
    d.subscribe(aviso);

    d.soltarRelojes();
    vi.advanceTimersByTime(DURACION * 3);
    expect(aviso).not.toHaveBeenCalled();
  });

  it("apagar un país que no estaba encendido no deja un cero suelto", () => {
    // Pasaría si un reloj sobreviviera a un `apagarTodo`. La clave tiene que
    // desaparecer, no quedarse a cero: el mapa recorre las que hay.
    const d = creaDestellos(DURACION);
    d.encender("co", CUANDO);
    vi.advanceTimersByTime(DURACION + 1);
    expect("co" in d.getSnapshot().encendidos).toBe(false);
  });
});
