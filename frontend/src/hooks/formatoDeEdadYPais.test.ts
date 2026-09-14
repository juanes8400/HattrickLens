import { describe, expect, it } from "vitest";
import { date, htAge, htAgeTexto, plural } from "./useFormat";

describe("una fecha sin hora es un día", () => {
  it("no se corre al día anterior por la zona horaria", () => {
    // 2026-09-13: el partido del 26/08 salía el 25/08 en Copa.
    expect(date("2026-08-26")).toBe("26/08/2026");
  });
});
import { nombreDePais } from "../utils/countryCodes";

describe("la edad, en un solo formato", () => {
  it("rellena los días a tres cifras", () => {
    expect(htAge(17, 3)).toBe("17;003");
    expect(htAge(28, 101)).toBe("28;101");
  });

  it("convierte la edad que llega del servidor como texto", () => {
    // Antes «28.101» se leía como un decimal.
    expect(htAgeTexto("28.101")).toBe("28;101");
    expect(htAgeTexto("28.9")).toBe("28;009");
    expect(htAgeTexto("15;088")).toBe("15;088");
    expect(htAgeTexto("?")).toBe("?");
  });
});

describe("plural", () => {
  it("nunca dice «1 jugadores»", () => {
    expect(plural(1, "jugador", "jugadores")).toBe("1 jugador");
    expect(plural(3, "jugador", "jugadores")).toBe("3 jugadores");
    expect(plural(0, "jugador", "jugadores")).toBe("0 jugadores");
  });
});

describe("el país en español", () => {
  it("usa el nombre en español aunque la liga de Hattrick se llame distinto", () => {
    expect(nombreDePais("MG", "Madagasikara")).toBe("Madagascar");
    expect(nombreDePais(null, "Madagasikara")).toBe("Madagascar");
  });

  it("respeta las ligas que no se llaman como su bandera", () => {
    expect(nombreDePais("gb", "Inglaterra")).toBe("Inglaterra");
  });

  it("sin nada que identificar, no inventa", () => {
    expect(nombreDePais(null, null)).toBeNull();
  });
});
