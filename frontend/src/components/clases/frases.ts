/** Las frases de pertenencia: en qué grupo cae un jugador en cada
 *  clasificación, y el dato que lo decide (2026-11-18, aprobadas por el
 *  usuario una a una). Las usan la tarjeta «Sus clases» de la ficha y, más
 *  adelante, Cambios.
 *
 *  Son funciones puras sobre la respuesta de `/player-classes`: no calculan
 *  ninguna clase, sólo cuentan la que ya mandó el servidor. */
import i18n from "../../i18n";
import { number } from "../../hooks/useFormat";
import { tx } from "../../i18n/tx";
import type {
  ClasesDeJugador,
  ClasificacionPropia,
  JugadorDeClases,
  OnceDeFormacion,
} from "../../services/api";
import { nombreDeEtapa } from "../../utils/etapasDeCarrera";
import { COLOR_DE_ETAPA, grupoPropioDe } from "./clasificaciones";
import { COLOR, COLORES_DE_GRUPO } from "./colores";

/** El nombre de una casilla sin orden («keeper», «winger»…). Los mismos
 *  nombres que la página de Posiciones. */
export function puesto(base: string): string {
  switch (base) {
    case "keeper":
      return tx("Portero");
    case "central_defender":
      return tx("Defensa Central");
    case "wingback":
      return tx("Defensa Lateral");
    case "inner_midfield":
      return tx("Mediocentro");
    case "winger":
      return tx("Extremo");
    default:
      return tx("Delantero");
  }
}

/** «4-4-2 y 3-5-2» en el idioma de la app, sin escribir la «y» a mano. */
export function enLista(partes: string[]): string {
  try {
    return new Intl.ListFormat(i18n.language || "es", {
      type: "conjunction",
    }).format(partes);
  } catch {
    return partes.join(", ");
  }
}

export interface Pertenencia {
  /** Qué clasificación: «Titularidad», «Rentabilidad deportiva»… */
  clasificacion: string;
  /** El grupo, ya con su nombre en pantalla. */
  grupo: string;
  color: string;
  frase: string;
  /** Sólo en las tres de la app: con qué clave las nombra el servidor en
   *  los cambios de clase. */
  clave?: ClaveDeLaApp;
}

export type ClaveDeLaApp = "titularidad" | "rentabilidad" | "etapa";

/** Dónde sale en los onces de una lista, puesto a puesto. */
function dondeSale(onces: OnceDeFormacion[], id: number) {
  const visto: { formacion: string; base: string }[] = [];
  for (const o of onces) {
    const casilla = o.slots.find((c) => c.htPlayerId === id);
    if (casilla) visto.push({ formacion: o.formation, base: casilla.base });
  }
  return visto;
}

/** «de Mediocentro en 4-4-2 y 3-5-2» o, con puestos distintos, «de
 *  Mediocentro en 4-4-2 y de Extremo en 3-5-2». */
function puestos(visto: { formacion: string; base: string }[]): string {
  const porPuesto = new Map<string, string[]>();
  for (const v of visto)
    porPuesto.set(v.base, [...(porPuesto.get(v.base) ?? []), v.formacion]);
  return enLista(
    [...porPuesto].map(([base, formaciones]) =>
      tx("de {{puesto}} en {{formaciones}}", {
        puesto: puesto(base),
        formaciones: enLista(formaciones),
      }),
    ),
  );
}

export function fraseDeTitularidad(
  datos: ClasesDeJugador,
  j: JugadorDeClases,
): Pertenencia {
  const clasificacion = tx("Titularidad");
  if (datos.formations.length === 0)
    return {
      clasificacion,
      grupo: tx("Sin datos"),
      color: COLOR.gris,
      frase: tx(
        "Sincroniza para leer la experiencia del equipo en cada formación.",
      ),
    };
  if (j.titularidad === "titular")
    return {
      clasificacion,
      grupo: tx("Titular"),
      color: COLOR.azul,
      frase: tx("Titular: sale en el mejor once, {{donde}}.", {
        donde: puestos(dondeSale(datos.starters, j.htPlayerId)),
      }),
    };
  if (j.titularidad === "suplencia")
    return {
      clasificacion,
      grupo: tx("Suplencia"),
      color: COLOR.verde,
      frase: tx("Suplencia: sale en el once sin titulares, {{donde}}.", {
        donde: puestos(dondeSale(datos.substitutes, j.htPlayerId)),
      }),
    };
  return {
    clasificacion,
    grupo: tx("Reserva"),
    color: COLOR.gris,
    frase: tx(
      "Reserva: no entra en ningún once ({{formaciones}}), ni siquiera sin los titulares.",
      { formaciones: datos.formations.join(", ") },
    ),
  };
}

const RENTABILIDAD = {
  estrellas: { nombre: () => tx("Estrella"), color: COLOR.azul },
  gangas: { nombre: () => tx("Ganga"), color: COLOR.verde },
  caros: { nombre: () => tx("Caro"), color: COLOR.rojo },
  economicos: { nombre: () => tx("Económico"), color: COLOR.gris },
} as const;

const TITULARIDAD: Record<string, () => string> = {
  titular: () => tx("Titular"),
  suplencia: () => tx("Suplencia"),
  reserva: () => tx("Reserva"),
};

/** El nombre en pantalla de un grupo de las clasificaciones de la app, a
 *  partir de la clave que guarda el servidor. Lo usa Cambios, que recibe
 *  claves de antes y de ahora. */
export function nombreDeGrupo(
  clasificacion: ClaveDeLaApp,
  clave: string,
): string {
  if (clasificacion === "titularidad") return TITULARIDAD[clave]?.() ?? clave;
  if (clasificacion === "rentabilidad")
    return clave in RENTABILIDAD
      ? RENTABILIDAD[clave as keyof typeof RENTABILIDAD].nombre()
      : clave;
  return nombreDeEtapa(clave);
}

/** Por encima, en o por debajo de la mediana. Justo en la mediana cuenta
 *  arriba (regla del usuario, 2026-11-17); la frase lo dice tal cual. */
function frenteALaMediana(v: number, mediana: number): string {
  if (v > mediana) return tx("por encima de la mediana");
  if (v === mediana) return tx("en la mediana");
  return tx("por debajo de la mediana");
}

export function fraseDeRentabilidad(
  datos: ClasesDeJugador,
  j: JugadorDeClases,
): Pertenencia | null {
  const m = datos.medians;
  if (!m) return null;
  const g = RENTABILIDAD[j.rentabilidad];
  const dinero = (v: number) => `${number(v)} ${datos.currency}`.trim();
  return {
    clasificacion: tx("Rentabilidad deportiva"),
    grupo: g.nombre(),
    color: g.color,
    frase: tx(
      "{{grupo}}: HTMS a los 28 de {{f}}, {{posF}} ({{mf}}), y sueldo de {{s}}, {{posS}} ({{ms}}).",
      {
        grupo: g.nombre(),
        f: number(j.htms28),
        posF: frenteALaMediana(j.htms28, m.htms28),
        mf: number(m.htms28),
        s: dinero(j.salary),
        posS: frenteALaMediana(j.salary, m.salary),
        ms: dinero(m.salary),
      },
    ),
  };
}

export function fraseDeEtapa(
  datos: ClasesDeJugador,
  j: JugadorDeClases,
): Pertenencia {
  const e = j.etapa;
  const etapa = nombreDeEtapa(e.stage);
  const edad = j.ageYears;
  let frase: string;
  if (e.confirmed) {
    frase = tx("{{etapa}}: confirmada a mano en su ficha.", { etapa });
  } else if (!e.hasSufficientHistory) {
    frase = tx(
      "{{etapa}}, provisional: sale de la edad ({{edad}} años). Hace falta otra sincronización, en otro día, para ver su tendencia.",
      { etapa, edad },
    );
  } else if (e.stage === "promesa") {
    frase =
      e.rising > 0
        ? tx(
            "{{etapa}}: {{edad}} años; desde el primer snapshot le subieron {{n}} de sus habilidades principales.",
            { etapa, edad, n: e.rising },
          )
        : tx("{{etapa}}: {{edad}} años; todavía no se le ve ninguna subida.", {
            etapa,
            edad,
          });
  } else if (e.stage === "pico" && e.percentile != null) {
    frase = tx(
      "{{etapa}}: {{edad}} años y percentil {{p}} en su habilidad dominante dentro de la plantilla.",
      { etapa, edad, p: Math.round(e.percentile) },
    );
  } else if (e.stage === "rotacion" && e.percentile != null) {
    frase = tx(
      "{{etapa}}: {{edad}} años y percentil {{p}} en su habilidad dominante, por debajo de {{corte}}.",
      {
        etapa,
        edad,
        p: Math.round(e.percentile),
        corte: datos.stageRules.rotationBelowPercentile,
      },
    );
  } else if (e.stage === "veterano" || e.stage === "declive") {
    frase = tx(
      "{{etapa}}: {{edad}} años; desde el primer snapshot le subieron {{s}} de sus habilidades principales y le bajaron {{b}}.",
      { etapa, edad, s: e.rising, b: e.falling },
    );
  } else {
    frase = tx("{{etapa}}: {{edad}} años.", { etapa, edad });
  }
  if (e.side === "titular") frase += ` ${tx("En el lado de titulares.")}`;
  if (e.side === "suplente") frase += ` ${tx("En el lado de suplentes.")}`;
  return {
    clasificacion: tx("Etapa de carrera"),
    grupo:
      e.hasSufficientHistory || e.confirmed
        ? etapa
        : tx("{{etapa}} · provisional", { etapa }),
    color: COLOR_DE_ETAPA[e.stage] ?? COLOR.gris,
    frase,
  };
}

/** Una clasificación propia (2026-11-18): en qué grupo de ella está. Sin
 *  grupos creados todavía no hay nada que decir y no sale la línea. */
export function fraseDePropia(
  c: ClasificacionPropia,
  j: JugadorDeClases,
): Pertenencia | null {
  if (c.groups.length === 0) return null;
  const id = grupoPropioDe(j, c.id);
  const g = c.groups.find((x) => x.id === id);
  return {
    clasificacion: c.classificationName,
    grupo: g ? g.groupName : tx("Sin grupo"),
    color: g ? (COLORES_DE_GRUPO[g.color] ?? COLOR.gris) : COLOR.gris,
    frase: g
      ? tx("En tu grupo «{{g}}».", { g: g.groupName })
      : tx("Sin grupo en «{{c}}».", { c: c.classificationName }),
  };
}

/** Las tres de la app y una por clasificación propia, en el orden de la
 *  pantalla de Clasificación de jugadores. */
export function pertenencias(
  datos: ClasesDeJugador,
  htPlayerId: number,
): Pertenencia[] | null {
  const j = datos.players.find((p) => p.htPlayerId === htPlayerId);
  if (!j) return null;
  const conClave = (p: Pertenencia | null, clave: ClaveDeLaApp) =>
    p ? { ...p, clave } : null;
  return [
    conClave(fraseDeTitularidad(datos, j), "titularidad"),
    conClave(fraseDeRentabilidad(datos, j), "rentabilidad"),
    conClave(fraseDeEtapa(datos, j), "etapa"),
    ...datos.classifications.map((c) => fraseDePropia(c, j)),
  ].filter((p): p is Pertenencia => p != null);
}
