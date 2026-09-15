/**
 * Los resúmenes que ofrece cada pantalla, en el orden en que se enseñan.
 *
 * Viven en un fichero sin componentes a propósito: exportar constantes
 * junto al componente rompe el recargado en caliente de Vite, y el mando
 * se toca mucho mientras se prueba.
 *
 * Los textos pasan por `tx` al cargar el módulo: cambiar de idioma recarga la
 * página, así que se vuelven a leer en el idioma nuevo.
 */
import type { PitchZoneMethod } from "../services/api";
import { tx } from "../i18n/tx";

/** Un resumen posible, con las dos explicaciones que la pantalla enseña.
 *
 * Era una tupla de tres cadenas hasta el 2026-09-12. Con dos descripciones
 * de largos distintos una tupla se vuelve ilegible --`m[2]` contra `m[3]`--
 * y se equivoca sola la primera vez que alguien reordene los campos. */
export type ResumenDeZonas = {
  key: PitchZoneMethod;
  /** Lo que va en el botón. */
  label: string;
  /** Una línea, la que se lee sin pedirla. */
  short: string;
  /** CÓMO se saca el número, de verdad. El usuario pidió esto el 2026-09-12:
   *  el mando ofrecía cinco resúmenes y sólo los nombraba. Un nombre no dice
   *  qué le pasa a un partido raro, y ésa es justo la diferencia entre
   *  elegir promedio y elegir máximo. */
  long: string;
};

export const PITCH_ZONE_METHODS: ResumenDeZonas[] = [
  // El promedio va primero y es el que abre. Hubo una mediana delante hasta el
  // 2026-09-13: se retiró a pedido del usuario porque enredaba --dos botones
  // casi iguales con nombres que no se distinguen-- y el promedio la absorbe.
  {
    key: "average",
    label: tx("Promedio"),
    short: tx("el promedio de los partidos vistos, zona por zona"),
    long: tx(
      "Se suman los valores de esa zona en todos los partidos vistos y se " +
        "divide entre cuántos son. Usa todos los datos, también el partido " +
        "raro: un solo registro extremo tira de él hacia arriba o hacia abajo, " +
        "y con cuatro o cinco partidos eso se nota bastante. Es el que abre.",
    ),
  },
  {
    key: "max",
    label: tx("Máximo"),
    short: tx("el mejor registro en cada zona, de todos los partidos vistos"),
    long: tx(
      "El registro más alto de esa zona entre todos los partidos vistos. No " +
        "describe cómo suele jugar sino de lo que ha sido capaz alguna vez, y " +
        "cada zona puede venir de un partido distinto: el techo de las siete " +
        "zonas casi nunca ocurrió a la vez. Es el escenario pesimista cuando " +
        "se mira a un rival.",
    ),
  },
  {
    key: "max_parallel",
    label: tx("Máximo por carril"),
    short: tx("el mejor de los tres carriles paralelos, aplicado a los tres"),
    long: tx(
      "Primero el máximo de cada zona, y después, dentro de cada trío " +
        "paralelo --los tres carriles de defensa por un lado y los tres de " +
        "ataque por otro--, el más alto se le pone a los tres. Contesta a «¿y " +
        "si vuelca todo por aquí?»: un ataque que rompió por la izquierda " +
        "puede romper por la derecha si mueve a sus hombres. Por construcción " +
        "los tres carriles salen iguales y altos. El balón parado no pertenece " +
        "a ningún carril, así que se queda con su propio máximo.",
    ),
  },
  {
    key: "last",
    label: tx("Último partido"),
    short: tx("lo del último día, sin promediar nada"),
    long: tx(
      "Los valores tal cual salieron el día más reciente, sin mezclar nada. " +
        "Es el más al día --recoge un fichaje o una subida de entrenamiento " +
        "antes que ningún otro-- y también el más frágil: es un solo partido, " +
        "con toda su suerte dentro.",
    ),
  },
];

/** Solo del lado propio: de un rival las órdenes son privadas hasta que se
 *  juega el partido, así que esta opción no existe para él. */
export const SUBMITTED_METHOD: ResumenDeZonas = {
  key: "submitted",
  label: tx("Alineación enviada"),
  short: tx(
    "la predicción de minuto 0 que da Hattrick para las órdenes que ya mandaste",
  ),
  long: tx(
    "La única que no sale de partidos jugados: es la previsión de minuto 0 " +
      "que publica Hattrick para las órdenes que ya mandaste, así que describe " +
      "el partido que viene en vez de los anteriores. No cubre las acciones " +
      "indirectas a balón parado, que Hattrick no prevé: esas dos zonas caen a " +
      "tu resumen de lo ya jugado.",
  ),
};

/** Lo que vale para los cuatro resúmenes, y que ninguno explica por su cuenta. */
export const NOTA_DE_LOS_RESUMENES = tx(
  "Los partidos vistos son los de la misma competición que el partido que se " +
    "juega, y el resumen se aplica a cada zona por separado: el medio campo se " +
    "resume con los medios campos, no con el partido entero. Un partido al que " +
    "le falte alguna zona se descarta entero antes de resumir, para que todas " +
    "salgan siempre de los mismos partidos.",
);
