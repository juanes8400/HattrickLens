import clsx from "clsx";
import { useTranslation } from "react-i18next";
// Las DOS banderas del selector, cada una como su propio fichero.
//
// Antes esto traía la hoja de estilos entera de las banderas, 420 kB de
// reglas para 260 países, y como el selector vive en la barra de arriba esa
// hoja BLOQUEABA la primera pintura de todas las pantallas (medido el
// 2026-09-20). Aquí sólo hacen falta dos, así que se piden dos y ya.
//
// Copiadas al proyecto a propósito: pedidas por su ruta dentro de la
// librería, el pre-empaquetador de desarrollo intenta empaquetar un SVG como
// si fuera código y se cae al arrancar.
import banderaES from "../assets/banderas/es.svg";
import banderaGB from "../assets/banderas/gb.svg";

import i18nActual, { cambiarIdioma, IDIOMAS, type Idioma } from "../i18n";

/** Cada idioma se nombra en su propio idioma: así lo reconoce quien no
 *  entiende el otro. Por eso no pasa por el diccionario. */
const NOMBRE_DE_IDIOMA: Record<Idioma, string> = {
  es: "Español",
  en: "English",
};

/** La bandera de cada idioma, con la variante que usa el glosario oficial de
 *  Hattrick: «Español, España» y «English (UK)». */
const BANDERA_DE_IDIOMA: Record<Idioma, string> = {
  es: banderaES,
  en: banderaGB,
};

function idiomaActual(): Idioma {
  const actual = i18nActual.language || "es";
  return IDIOMAS.find((codigo) => actual.startsWith(codigo)) ?? "es";
}

/**
 * El idioma, en una lista desplegable (2026-09-16).
 *
 * Vive fuera del menú porque la primera pantalla que ve alguien --la de
 * conectar el club-- no lleva menú, y ahí es justo donde hace falta: quien
 * llega con la app en un idioma que no lee tiene que poder cambiarlo antes
 * de entrar. Con la bandera del idioma puesto al lado, para reconocerlo de
 * un vistazo sin leer.
 *
 * Lista nativa y no un menú propio: se abre igual con teclado, con lector de
 * pantalla y en el móvil, y crecer a un tercer idioma es añadir una línea.
 */
export function SelectorDeIdioma({ className }: { className?: string }) {
  const { t } = useTranslation();
  const actual = idiomaActual();

  return (
    <div
      className={clsx(
        "flex items-center gap-1.5 rounded-md border border-[var(--border)] px-2 py-1",
        className,
      )}
    >
      <img
        aria-hidden
        alt=""
        src={BANDERA_DE_IDIOMA[actual]}
        className="h-3 w-4 rounded-[2px] object-cover shadow-[0_0_0_1px_color-mix(in_srgb,var(--border)_75%,transparent)]"
      />
      <select
        value={actual}
        onChange={(evento) => {
          const elegido = evento.target.value as Idioma;
          if (elegido !== actual) cambiarIdioma(elegido);
        }}
        aria-label={t("layout.idioma", "Idioma")}
        title={t("layout.idioma", "Idioma")}
        className="cursor-pointer bg-transparent text-xs font-medium text-[var(--text)] outline-none"
      >
        {IDIOMAS.map((codigo) => (
          <option key={codigo} value={codigo} className="text-[var(--text)]">
            {NOMBRE_DE_IDIOMA[codigo]}
          </option>
        ))}
      </select>
    </div>
  );
}
