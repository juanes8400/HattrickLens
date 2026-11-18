/** Las cuatro formas de partir la plantilla, con sus grupos, nombres y
 *  colores (2026-11-17). Las usan Clases de Jugador y el «Mirar a» de
 *  Habilidades: un jugador no puede caer en un grupo en una pantalla y en otro
 *  en la otra, ni un grupo llevar un color distinto en cada una. */
import { tx } from "../../i18n/tx";
import type { ClasesDeJugador, EtapaDeCarrera } from "../../services/api";
import { ETAPAS_DE_CARRERA } from "../../utils/etapasDeCarrera";
import { COLOR, COLORES_DE_GRUPO, type Grupo } from "./colores";

/** Las de la app por su nombre; las propias, «propia-<id>». */
export type ClaveDeClasificacion =
  "rentabilidad" | "titularidad" | "etapa" | `propia-${number}`;

/** El grupo de un jugador en una clasificación propia, o null. */
export function grupoPropioDe(
  j: { groupIds: Record<string, number> },
  clasificacionId: number,
): number | null {
  return j.groupIds[String(clasificacionId)] ?? null;
}

export interface Clasificacion {
  clave: ClaveDeClasificacion;
  nombre: string;
  grupos: Grupo[];
}

/** El color de cada etapa; los nombres salen de `utils/etapasDeCarrera`. */
export const COLOR_DE_ETAPA: Record<EtapaDeCarrera, string> = {
  promesa: COLOR.verde,
  pico: COLOR.azul,
  rotacion: COLOR.morado,
  veterano: COLOR.naranja,
  declive: COLOR.rojo,
  sin_historial: COLOR.gris,
};

/** Una columna por etapa, o dos si el servidor la partió en titulares y
 *  suplentes por pasar de su tope. */
export function gruposDeEtapa(datos: ClasesDeJugador): Grupo[] {
  return ETAPAS_DE_CARRERA.flatMap((e) => {
    const de = datos.players
      .filter((j) => j.etapa.stage === e.clave)
      .sort((a, b) => a.ageYears - b.ageYears || a.ageDays - b.ageDays);
    const partida = de.some((j) => j.etapa.side != null);
    if (!partida)
      return [
        {
          clave: e.clave,
          nombre: e.nombre(),
          color: COLOR_DE_ETAPA[e.clave],
          jugadores: de,
        },
      ];
    return [
      {
        clave: `${e.clave}-t`,
        nombre: tx("{{etapa}} · titulares", { etapa: e.nombre() }),
        color: COLOR_DE_ETAPA[e.clave],
        jugadores: de.filter((j) => j.etapa.side === "titular"),
      },
      {
        clave: `${e.clave}-s`,
        nombre: tx("{{etapa}} · suplentes", { etapa: e.nombre() }),
        color: COLOR_DE_ETAPA[e.clave],
        jugadores: de.filter((j) => j.etapa.side === "suplente"),
      },
    ];
  });
}

export function clasificaciones(datos: ClasesDeJugador): Clasificacion[] {
  const por = <K extends string>(
    lista: { clave: K; nombre: string; color: string }[],
    de: (clave: K) => ClasesDeJugador["players"],
  ): Grupo[] => lista.map((g) => ({ ...g, jugadores: de(g.clave) }));
  return [
    {
      clave: "rentabilidad",
      nombre: tx("Rentabilidad deportiva"),
      grupos: por(
        [
          { clave: "estrellas", nombre: tx("Estrellas"), color: COLOR.azul },
          { clave: "gangas", nombre: tx("Gangas"), color: COLOR.verde },
          { clave: "caros", nombre: tx("Caros"), color: COLOR.rojo },
          { clave: "economicos", nombre: tx("Económicos"), color: COLOR.gris },
        ],
        (k) => datos.players.filter((j) => j.rentabilidad === k),
      ),
    },
    {
      clave: "titularidad",
      nombre: tx("Titularidad"),
      grupos: por(
        [
          { clave: "titular", nombre: tx("Titular"), color: COLOR.azul },
          { clave: "suplencia", nombre: tx("Suplencia"), color: COLOR.verde },
          { clave: "reserva", nombre: tx("Reserva"), color: COLOR.gris },
        ],
        (k) => datos.players.filter((j) => j.titularidad === k),
      ),
    },
    {
      clave: "etapa",
      nombre: tx("Etapa de carrera"),
      grupos: gruposDeEtapa(datos),
    },
    // Las propias del usuario, una por clasificación (2026-11-18).
    ...datos.classifications.map((c) => ({
      clave: `propia-${c.id}` as const,
      nombre: c.classificationName,
      grupos: c.groups.map((g) => ({
        clave: String(g.id),
        nombre: g.groupName,
        color: COLORES_DE_GRUPO[g.color] ?? COLOR.gris,
        jugadores: datos.players.filter((j) => grupoPropioDe(j, c.id) === g.id),
      })),
    })),
  ];
}
