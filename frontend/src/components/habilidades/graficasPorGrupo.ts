/** «Mirar a» en Habilidades (6.9.0 y 6.10.0, 2026-11-17, decisiones del
 *  usuario): qué gráficas se dibujan según lo que esté marcado.
 *
 *  - Sólo la plantilla entera: las gráficas del resumen, tal cual.
 *  - Un grupo: las mismas gráficas con las medias del grupo. En Salario y TSI
 *    la segunda línea pasa a ser la plantilla entera, en gris: «los 11 de más
 *    TSI» de un grupo de cuatro son esos mismos cuatro.
 *  - Dos o más: una línea por grupo. En Habilidades, un dato cada vez, porque
 *    tres habilidades por gráfica y tres grupos serían nueve líneas.
 *
 *  Cada grupo puntea los tramos en que cambia cuántos de sus jugadores entran
 *  en la media: ese salto lo trae quien llega, no el entrenamiento. */
import { tx } from "../../i18n/tx";
import type {
  SerieDeUnGrupo,
  TeamOverview,
  TeamOverviewGroup,
} from "../../services/api";

export const PLANTILLA = "plantilla";

/** Algo marcado en «Mirar a»: la plantilla entera o un grupo. */
export interface Poblacion {
  clave: string;
  nombre: string;
  /** El color ya resuelto para el lienzo de la gráfica. */
  color?: string;
  /** Las medias del grupo; `null` en la plantilla entera. */
  serie: SerieDeUnGrupo | null;
}

export interface LineaDibujada {
  name: string;
  values: (number | null)[];
  reference?: boolean;
  color?: string;
  conteos?: number[];
}

export interface GraficaDibujada {
  key: string;
  title: string;
  scaleMin: number | null;
  scaleMax: number | null;
  band: boolean;
  series: LineaDibujada[];
}

export interface PestanaDibujada {
  charts: GraficaDibujada[];
  /** Las filas de «en la media» bajo el eje, una por grupo. */
  filas: { conteos: number[]; color?: string }[];
  note: string;
  /** Gráficas pequeñas en rejilla, con una sola leyenda arriba
   *  (`HABILIDADES_EN_REJILLA`). */
  rejilla?: boolean;
}

const NOTA_DE_MERCADO = () =>
  tx(
    "Cuatro unidades distintas, dinero, un índice, su suma y el coste de cada punto, así que ninguna comparte eje con las otras. La plantilla entera va en gris, como referencia. Los de TSI 0 se ignoran SOLO en el coste por punto: sin índice no hay cociente que calcular.",
  );

/** Las series de la plantilla entera por su clave, sacadas del resumen. Las
 *  del once de más TSI (`_top`) no son de la plantilla y se dejan fuera. */
export function seriesDeLaPlantilla(
  data: TeamOverview,
): Record<string, (number | null)[]> {
  const out: Record<string, (number | null)[]> = {};
  for (const g of data.groups)
    for (const ch of g.charts)
      for (const s of ch.series)
        if (!s.key.endsWith("_top") && !(s.key in out)) out[s.key] = s.values;
  return out;
}

/** Lo que se puede elegir en «Dato»: cada serie de las gráficas de
 *  Habilidades, con la escala de su gráfica. */
export function datosDeHabilidades(tab: TeamOverviewGroup) {
  return tab.charts.flatMap((ch) =>
    ch.series.map((s) => ({
      key: s.key,
      label: s.label,
      scaleMin: ch.scaleMin,
      scaleMax: ch.scaleMax,
    })),
  );
}

/** Las gráficas del resumen tal cual: la plantilla entera. */
export function pestanaDeLaPlantilla(tab: TeamOverviewGroup): PestanaDibujada {
  return {
    charts: tab.charts.map((ch) => ({
      key: ch.key,
      title: ch.title,
      scaleMin: ch.scaleMin,
      scaleMax: ch.scaleMax,
      band: ch.band,
      series: ch.series.map((s) => ({ name: s.label, values: s.values })),
    })),
    filas: [],
    note: tab.note,
  };
}

/** Un grupo: las gráficas de siempre con sus medias. */
export function pestanaDeUnGrupo(
  tab: TeamOverviewGroup,
  grupo: Poblacion & { serie: SerieDeUnGrupo },
  plantilla: Record<string, (number | null)[]>,
): PestanaDibujada {
  const de = (clave: string) => grupo.serie.fields[clave] ?? [];
  const mercado = tab.key === "market";
  return {
    charts: tab.charts.map((ch) => {
      if (mercado)
        return {
          key: ch.key,
          title: ch.title,
          scaleMin: ch.scaleMin,
          scaleMax: ch.scaleMax,
          // Entre la suma de TSI de cuatro y la de veinte, el hueco es el
          // resto de la plantilla, no una brecha: no se sombrea.
          band: ch.band && ch.key !== "tsi_total",
          series: [
            { name: grupo.nombre, values: de(ch.key), color: grupo.color },
            {
              name: tx("Plantilla entera"),
              values: plantilla[ch.key] ?? [],
              reference: true,
            },
          ],
        };
      const suma = ch.key === "htms_total";
      return {
        key: ch.key,
        title: suma ? tx("HTMS sumado del grupo") : ch.title,
        scaleMin: ch.scaleMin,
        scaleMax: ch.scaleMax,
        band: ch.band,
        series: ch.series.map((s) => ({
          name: suma ? grupo.nombre : s.label,
          values: de(s.key),
          ...(suma ? { color: grupo.color } : {}),
        })),
      };
    }),
    filas: [{ conteos: grupo.serie.counts }],
    note: mercado ? NOTA_DE_MERCADO() : tab.note,
  };
}

/** Dos o más: una línea por grupo, y la plantilla en gris si está marcada. */
export function pestanaComparada(
  tab: TeamOverviewGroup,
  poblaciones: Poblacion[],
  plantilla: Record<string, (number | null)[]>,
  dato: string,
): PestanaDibujada {
  const lineas = (clave: string): LineaDibujada[] =>
    poblaciones.map((p) =>
      p.serie
        ? {
            name: p.nombre,
            values: p.serie.fields[clave] ?? [],
            color: p.color,
            conteos: p.serie.counts,
          }
        : { name: p.nombre, values: plantilla[clave] ?? [], reference: true },
    );
  const filas = poblaciones.flatMap((p) =>
    p.serie ? [{ conteos: p.serie.counts, color: p.color }] : [],
  );

  if (tab.key === "skills") {
    const datos = datosDeHabilidades(tab);
    const d = datos.find((x) => x.key === dato) ?? datos[0];
    return {
      charts: d
        ? [
            {
              key: d.key,
              title: d.label,
              scaleMin: d.scaleMin,
              scaleMax: d.scaleMax,
              band: false,
              series: lineas(d.key),
            },
          ]
        : [],
      filas,
      note: "",
    };
  }
  // Salario y TSI y HTMS: una gráfica por medida. «HTMS actual y potencial»
  // lleva dos, así que se parte en dos gráficas.
  return {
    charts: tab.charts.flatMap((ch) => {
      const propias = ch.series.filter((s) => !s.key.endsWith("_top"));
      return propias.map((s) => ({
        key: s.key,
        title:
          ch.key === "htms_total"
            ? tx("HTMS sumado")
            : propias.length > 1
              ? s.label
              : ch.title,
        scaleMin: ch.scaleMin,
        scaleMax: ch.scaleMax,
        band: false,
        series: lineas(s.key),
      }));
    }),
    filas,
    note: tab.key === "market" ? NOTA_DE_MERCADO() : "",
  };
}

/** La forma fija (`HABILIDADES_EN_REJILLA`, 2026-11-18): una gráfica por
 *  dato --en Habilidades, todos los datos a la vez-- y en cada una una línea
 *  por cosa marcada, la plantilla en gris. Marcar otro grupo añade una línea
 *  en todas; nunca cambia la forma. */
export function pestanaEnRejilla(
  tab: TeamOverviewGroup,
  poblaciones: Poblacion[],
  plantilla: Record<string, (number | null)[]>,
): PestanaDibujada {
  if (tab.key !== "skills") {
    const p = pestanaComparada(tab, poblaciones, plantilla, "");
    // Sin los 11 de más TSI: el usuario los dio por desaparecidos
    // (2026-11-18). Sólo quedan en la forma anterior, tras la bandera.
    return { ...p, rejilla: true };
  }
  const una = (dato: string) =>
    pestanaComparada(tab, poblaciones, plantilla, dato);
  const datos = datosDeHabilidades(tab);
  return {
    charts: datos.flatMap((d) => una(d.key).charts),
    filas: una(datos[0]?.key ?? "").filas,
    note: "",
    rejilla: true,
  };
}
