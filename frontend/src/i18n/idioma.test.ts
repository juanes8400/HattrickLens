import { afterAll, beforeAll, describe, expect, it } from "vitest";

import i18n, { idiomaPreferido, OFRECIDOS, type Idioma } from ".";
import { number, ordinal } from "../hooks/useFormat";
import appEn from "./en.json";
import appIt from "./it.json";
import appDe from "./de.json";
import appPl from "./pl.json";
import textosEn from "./textos/en.json";
import textosIt from "./textos/it.json";
import textosDe from "./textos/de.json";
import textosPl from "./textos/pl.json";

describe("idiomaPreferido", () => {
  it("respeta el español del navegador", () => {
    expect(idiomaPreferido(["es-CO", "es"])).toBe("es");
    expect(idiomaPreferido(["es"])).toBe("es");
  });

  it("da inglés a quien no tiene el navegador en español", () => {
    expect(idiomaPreferido(["en-GB", "en"])).toBe("en");
    // Un idioma que la app no habla todavía: inglés, que es lo que entiende
    // más gente, y nunca español por defecto.
    expect(idiomaPreferido(["sv-SE", "nb"])).toBe("en");
    expect(idiomaPreferido([])).toBe("en");
  });

  it("toma el primero de la lista que la app hable", () => {
    expect(idiomaPreferido(["fr", "es", "en"])).toBe("es");
    expect(idiomaPreferido(["fr", "en", "es"])).toBe("en");
  });
});

describe("los idiomas a medias no se le dan a nadie", () => {
  it("un navegador en italiano recibe italiano", () => {
    // 2026-09-28: el italiano se terminó y entró en OFRECIDOS, así que la
    // detección automática ya se lo puede servir a quien lo tenga puesto.
    //
    // Hasta ese día esta prueba pedía lo contrario, y por un buen motivo:
    // esconderlo del selector NO bastaba, porque la detección automática
    // miraba todos los idiomas con diccionario y le servía media pantalla en
    // español a quien tuviera el navegador en italiano. La regla que hacía
    // falta --y que sigue aquí-- es que la detección mire lo OFRECIDO, no lo
    // que hay traducido a medias.
    expect(idiomaPreferido(["it-IT", "it"])).toBe("it");
    expect(idiomaPreferido(["it"])).toBe("it");
  });

  it("un idioma sin diccionario sigue recibiendo inglés", () => {
    // La regla de arriba se comprueba con un idioma que la app NO habla: si
    // mañana alguien añade un diccionario a medias, esto tiene que seguir
    // dando inglés hasta que entre en OFRECIDOS.
    expect(idiomaPreferido(["pt-BR", "pt"])).toBe("en");
  });

  it("el español sigue ganando aunque el italiano vaya delante", () => {
    // Sólo porque el navegador los pida en ese orden: gana el primero de la
    // lista que la app ofrezca, y aquí el italiano va antes.
    expect(idiomaPreferido(["it", "es"])).toBe("it");
    expect(idiomaPreferido(["es", "it"])).toBe("es");
  });
});

/**
 * Un idioma OFRECIDO tiene que estar ENTERO.
 *
 * 2026-09-29. El italiano entró en OFRECIDOS con 226 claves nombradas sin
 * traducir, y nadie se enteró: los tres guardianes de textos miran las
 * cadenas que se escriben con `tx("...")`, y éstas no se escriben enteras en
 * el código. Se arman al vuelo --`abrev.${habilidad}`,
 * `alertas.modulo.${modulo}`-- así que ningún guardián sabe siquiera que
 * existen. Sin traducción i18next cae al defecto que lleva la llamada, que
 * está en español: la app en italiano decía «PO», «DE», «economía».
 *
 * La comprobación es la misma para cualquier idioma que se añada: las mismas
 * claves que el inglés, que es el diccionario de referencia. Si falta una,
 * esa frase sale en español y la pantalla queda a medias.
 */
describe("cada idioma ofrecido está completo", () => {
  const aplanar = (objeto: unknown, prefijo = ""): string[] =>
    Object.entries(objeto as Record<string, unknown>).flatMap(
      ([clave, valor]) =>
        valor !== null && typeof valor === "object"
          ? aplanar(valor, `${prefijo}${clave}.`)
          : [`${prefijo}${clave}`],
    );

  const DICCIONARIOS: Record<string, [unknown, unknown]> = {
    it: [appIt, textosIt],
    de: [appDe, textosDe],
    pl: [appPl, textosPl],
  };

  // El español no entra: es el idioma de origen, y su diccionario está vacío
  // a propósito (cada texto ya está en español en el propio código).
  const OTROS = OFRECIDOS.filter(
    (codigo) => codigo !== "es" && codigo !== "en",
  );

  it("se comprueban todos los que se ofrecen, no una lista escrita a mano", () => {
    // Si mañana entra un idioma en OFRECIDOS y nadie añade su diccionario
    // aquí, esto falla antes que ninguna otra cosa. Es lo que impide que la
    // prueba se quede atrás sin avisar.
    expect(OTROS.filter((codigo) => !(codigo in DICCIONARIOS))).toEqual([]);
  });

  for (const [codigo, [app, textos]] of Object.entries(DICCIONARIOS)) {
    it(`${codigo}: las mismas claves nombradas que el inglés`, () => {
      const suyas = new Set(aplanar(app));
      expect(aplanar(appEn).filter((clave) => !suyas.has(clave))).toEqual([]);
    });

    it(`${codigo}: los mismos textos que el inglés`, () => {
      const suyos = new Set(Object.keys(textos as object));
      expect(
        Object.keys(textosEn).filter((clave) => !suyos.has(clave)),
      ).toEqual([]);
    });
  }
});

/**
 * Un idioma OFRECIDO también escribe sus números como los escribe él.
 *
 * 2026-10-03, al entrar el polaco. `MILES` y `ORDINAL` en
 * `src/hooks/useFormat.ts` son tablas con una entrada por idioma a propósito,
 * pero nada obligaba a rellenarlas: un idioma nuevo sin entrada cae al
 * defecto español --«1.234.567» y «3º»-- y la pantalla no falla, sólo queda
 * mal escrita. El polaco separa los miles con un espacio duro y pone el
 * ordinal con punto, así que aquí se exige, idioma a idioma, lo que cada uno
 * tiene que devolver.
 */
describe("cada idioma ofrecido escribe sus cifras", () => {
  const ESPERADO: Record<Idioma, { miles: string; tercero: string }> = {
    es: { miles: "1.234.567", tercero: "3º" },
    it: { miles: "1.234.567", tercero: "3º" },
    en: { miles: "1,234,567", tercero: "3rd" },
    de: { miles: "1.234.567", tercero: "3." },
    pl: { miles: "1\u00a0234\u00a0567", tercero: "3." },
  };

  it("se comprueban todos los que se ofrecen, no una lista escrita a mano", () => {
    expect(OFRECIDOS.filter((codigo) => !(codigo in ESPERADO))).toEqual([]);
  });

  const html = { documentElement: { lang: "" } };

  beforeAll(() => {
    (globalThis as { document?: unknown }).document = html;
  });

  afterAll(() => {
    delete (globalThis as { document?: unknown }).document;
  });

  for (const codigo of OFRECIDOS) {
    it(`${codigo}: miles y ordinal`, async () => {
      const previo = i18n.language;
      try {
        await i18n.changeLanguage(codigo);
        expect(number(1234567)).toBe(ESPERADO[codigo].miles);
        expect(ordinal(3)).toBe(ESPERADO[codigo].tercero);
        // Y el <html> declara ese idioma: un lector de pantalla lee con la
        // fonética que la página declare, y el polaco con acento español no
        // se entiende. Estas pruebas corren sin DOM, así que el documento se
        // finge: lo que se comprueba es que el idioma llegue al atributo.
        expect(html.documentElement.lang).toBe(codigo);
      } finally {
        await i18n.changeLanguage(previo);
      }
    });
  }
});
