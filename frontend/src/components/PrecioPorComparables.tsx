/** Lo que ha costado la gente parecida a un jugador tuyo.
 *
 *  ES UNA DESCRIPCIÓN DEL MERCADO, NO UNA PREDICCIÓN. Dice qué se pagó por
 *  jugadores que se le parecen, y no lo que te darían por él: no corrige por
 *  forma, experiencia, especialidad ni bonos de club de origen. Esa distinción
 *  la decidió el usuario y gobierna todo lo que se escribe aquí.
 *
 *  SÓLO VENTAS CERRADAS, Y NADA MÁS (2026-11-07, decisión del usuario: «los
 *  jugadores que nunca se vendieron, no deben ir en la lista»). La tabla
 *  llevaba también las subastas vivas y los anuncios que nadie pujó, y por
 *  ellos existían dos columnas y tres rótulos: «Cierra», «Antigüedad», «sin
 *  cerrar», «sin confirmar», «NO PUJA DETECTADA». Todo eso contestaba a «por
 *  qué esta fila no trae precio», que es una pregunta sobre nuestra cocina y
 *  no sobre el mercado. Desde que el barrido es diario, además, esas filas
 *  eran la mayoría: una lista de gente que no se vendió delante de la que sí.
 *
 *  No se pierden: siguen en el fondo, se siguen vigilando, y la pastilla de
 *  «pujas abiertas» dice cuántas esperan su precio. Lo que se deja de hacer es
 *  ponerlas delante.
 *
 *  Tres cosas que la pantalla está obligada a decir, y por eso ocupan sitio:
 *
 *  · **Cuántas subastas siguen abiertas**, que son las que todavía no están en
 *    la lista. Una puja se queda corta: el 2026-10-05 Valerio Cataldi tenía
 *    65.000.000 de puja y cerró en 77.720.000, un 16% más.
 *  · **Cuánto se parecen**, y desde el 2026-10-27 sólo hay dos maneras:
 *    CLAVADO es el mismo jugador --misma edad y las tres habilidades más altas
 *    en el mismo nivel-- y AVALADO es que el propio Hattrick enseñaría esa
 *    venta al comparar al tuyo, sin ser el mismo. No hay nada en medio: lo que
 *    no es una de las dos cosas no entra en la lista.
 *  · **CON QUÉ FILTROS buscó Hattrick** (2026-10-27). Los siete, con sus
 *    rangos, y el dial que los ensancha. Es lo único que esta pantalla no
 *    podía decir --enseñaba las ventas pero no por qué ésas-- y el por qué
 *    está medido contra su propio Comparador, no supuesto.
 *  · **De cuándo son.** Una venta sigue contando pasadas sus veinticuatro
 *    semanas si
 *    no apareció nada mejor, y entonces habla de un mercado que pudo cambiar.
 *
 *  No pide nada a Hattrick: todo sale del fondo que dejó el paso semanal, así
 *  que abrir y cerrar esto es gratis.
 */
import type { ReactNode } from "react";

import { Panel } from "./Panels";
import { Ayuda } from "./Ayuda";
import { DataTable } from "./DataTable";
import type { Column } from "./DataTable";
import { Specialty } from "./Specialty";
import { CountryCell } from "./CountryFlag";
import { Chart } from "../charts/Chart";
import {
  serieDePuntosOption,
  tiraDePuntosOption,
} from "../charts/chartOptions";
import {
  date,
  dateTime,
  htAge,
  money,
  number,
  parseUtc,
} from "../hooks/useFormat";
import { usePrecioComparable } from "../hooks/useTeam";
import { tx } from "../i18n/tx";
import { nombreDeHabilidad } from "../i18n/habilidades";
import { skillLevelLabel } from "../utils/skillLevels";
import type {
  ComparableDeMercado,
  CriterioDeHattrick,
  PrecioComparable,
  RasgoVisible,
} from "../services/api";

/** «Anotación 18 · Pases 13 · Jugadas 7».
 *
 *  El nombre sale del glosario OFICIAL de Hattrick, no de una traducción
 *  nuestra: así el jugador lee exactamente la misma palabra que ve en el
 *  juego. Se calcula en el render y no en una constante del módulo para que
 *  cambie al vuelo cuando se cambia de idioma. */
function perfilLegible(perfil: RasgoVisible[]): string {
  return perfil
    .map((r) => `${nombreDeHabilidad(r.habilidad)} ${r.nivel}`)
    .join(" · ");
}

/** Desde cuántas lecturas vale la pena dibujar la serie. Con una no hay
 *  nada que unir. */
const MINIMO_PARA_LA_SERIE = 2;

/** Desde cuántas ventas vale la pena dibujar el reparto. Con dos o tres, la
 *  tira no dice nada que la tabla no diga mejor. */
const MINIMO_PARA_LA_TIRA = 4;

/** El peso en color, y desde el 2026-10-27 sólo hay dos.
 *
 *  El 100 es el clavado --misma edad y las tres habilidades más altas en el
 *  mismo nivel, «el mismo jugador»-- y va en verde porque no existe nada
 *  mejor. El 90 es el sello: el propio Hattrick enseñaría esa venta al
 *  comparar a este jugador, pero no es exactamente el mismo, así que se queda
 *  en el color del texto.
 *
 *  Antes había cuatro peldaños más, de 95 a 75, y el apagado era para ellos.
 *  Se fueron con la escalera, y con ellos el tercer color. */
function colorDelPeso(peso: number): string {
  return peso >= 100 ? "text-[var(--ok)]" : "text-[var(--text)]";
}

/** «idéntico» o «equivalente», que es lo único que un peso puede ser.
 *
 *  LOS NOMBRES CAMBIARON EL 2026-10-31: en pantalla decía «clavado» y
 *  «avalado», y eran palabras raras de leer. El dominio los sigue llamando
 *  así --`esta_clavado`, `avalado_por_hattrick`-- porque ahí sí dicen lo que
 *  hacen; lo que se enseña es otra cosa.
 *
 *  LA PALABRA Y NO EL PORCENTAJE (2026-10-27). La columna decía «100%» y
 *  «90%», y un porcentaje invita a leer una escala continua que ya no existe:
 *  no hay 95 ni 80, no hay nada en medio, y el número no dice QUÉ pasó. La
 *  palabra sí. */
function comoSeParece(peso: number): string {
  return peso >= 100 ? tx("idéntico") : tx("equivalente");
}

/** Un dato suelto con su rótulo, del tamaño de una pastilla.
 *
 *  Vive aquí mientras sea el único sitio que lo usa, igual que `DosOpciones`. */
function Pastilla({
  children,
  tono = "normal",
  ayuda,
}: {
  children: ReactNode;
  tono?: "normal" | "aviso" | "bien";
  ayuda?: string;
}) {
  const color =
    tono === "aviso"
      ? "border-[var(--warn)] text-[var(--warn)]"
      : tono === "bien"
        ? "border-[var(--ok)] text-[var(--ok)]"
        : "border-[var(--border)] text-[var(--muted)]";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs ${color}`}
    >
      {children}
      {ayuda && <Ayuda texto={ayuda} />}
    </span>
  );
}

/** Cómo se lee un criterio: «magnífico», «entre bueno y destacado», «≤ débil».
 *
 *  Las palabras salen del glosario OFICIAL, igual que el perfil: quien mira
 *  lee exactamente lo que le pone Hattrick en su propio buscador. */
function criterioLegible(c: CriterioDeHattrick): string {
  if (c.operador === "=") return skillLevelLabel(c.minimo);
  if (c.operador === "<=") return `≤ ${skillLevelLabel(c.maximo)}`;
  return `${skillLevelLabel(c.minimo)} – ${skillLevelLabel(c.maximo)}`;
}

/** CON QUÉ FILTROS BUSCÓ HATTRICK, que es el por qué de la lista de abajo.
 *
 *  Los criterios no son una opinión nuestra: salen de sondear su propio
 *  Comparador de Transferencias --unas 460 consultas a su panel «Editar
 *  búsqueda»-- y el motor los reproduce con un 98 % de acierto fuera de
 *  muestra. Por eso se pueden enseñar como lo que pide el juego y no como lo
 *  que creemos que pide.
 *
 *  EL DIAL YA NO SE ENSEÑA (2026-11-04, pedido del usuario: «quita este tipo
 *  de mensajes, ya que no aportan nada y son información del algoritmo»).
 *  Debajo de los filtros había una frase --«su rareza es 35 y el listón que le
 *  toca 23, así que Hattrick abre la ventana de edad»-- que explicaba por qué
 *  la búsqueda salía ancha. Y tenía razón él: lo que ESTA pantalla contesta es
 *  con qué buscó Hattrick, y eso ya está arriba, en las pastillas. La rareza y
 *  el listón son nuestra cocina, no su pregunta.
 *
 *  Los tres campos --`rareza`, `liston` y `dialHolgado`-- se fueron también
 *  del DTO, en la misma vuelta: quitada la frase no los pintaba nadie, y un
 *  campo que viaja sin que nadie lo lea es deuda, no previsión. El motor no
 *  pierde nada --`es_holgado` y `liston_de` siguen decidiendo la forma de los
 *  criterios-- y si algún día hay que enseñar la cocina, su sitio es
 *  Transparencia y se vuelve a exponer entonces. */
function CriteriosDeHattrick({ datos }: { datos: PrecioComparable }) {
  const edad =
    datos.edadMinima === datos.edadMaxima
      ? String(datos.edadMinima)
      : `${datos.edadMinima} – ${datos.edadMaxima}`;
  return (
    <section className="mt-4">
      <div className="mb-2 flex items-center gap-1 text-xs uppercase tracking-wide text-[var(--muted)]">
        {tx("Con qué filtros buscó Hattrick")}
        <Ayuda
          texto={tx(
            "Los filtros que el propio juego usa en su Comparador de Transferencias para este jugador. No son nuestros: salen de sondear su pantalla y el motor los reproduce con un 98% de acierto fuera de muestra. Una venta sólo entra en la lista si los cumple o si es idéntica.",
          )}
        />
      </div>
      <div className="flex flex-wrap gap-1.5">
        <Filtro nombre={tx("Edad")} valor={edad} />
        {datos.topeDeDias != null && (
          <Filtro
            nombre={tx("Días")}
            valor={`≤ ${datos.topeDeDias}`}
            ayuda={tx(
              "A los 17 años Hattrick añade un tope de días, y es una constante: el mismo perfil pedido desde dos fichas con días distintos da el mismo número.",
            )}
          />
        )}
        {datos.criterios.map((c) => (
          <Filtro
            key={c.habilidad}
            nombre={nombreDeHabilidad(c.habilidad)}
            valor={criterioLegible(c)}
          />
        ))}
      </div>
    </section>
  );
}

/** Un filtro: la habilidad y lo que pide, en una pastilla. */
function Filtro({
  nombre,
  valor,
  ayuda,
}: {
  nombre: string;
  valor: string;
  ayuda?: string;
}) {
  return (
    <span className="inline-flex items-baseline gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-2 py-1 text-xs">
      <span className="text-[var(--muted)]">{nombre}</span>
      <span className="font-medium text-[var(--text)]">{valor}</span>
      {ayuda && <Ayuda texto={ayuda} />}
    </span>
  );
}

/** «+2,0%»: cuánto subió del momento en que la vimos al cierre.
 *
 *  Siempre sube, porque una puja no puede bajar y el precio de cierre ES la
 *  puja ganadora. Por eso va en verde sin mirar el signo. */
function salto(puja: number, precio: number): string {
  const pct = ((precio / puja - 1) * 100).toFixed(1).replace(".", ",");
  return `+${pct}%`;
}

/** Las columnas, armadas contra la terna del jugador que pregunta.
 *
 *  No son fijas porque la terna no lo es: a un delantero se le comparan
 *  anotación, pases y jugadas, y a un defensa otras tres. Como todos los
 *  comparables comparten la terna del objetivo --esa es la definición de
 *  comparable-- `perfil[i]` es la misma habilidad en todas las filas.
 *
 *  EL ORDEN ES EL QUE DICTÓ EL USUARIO (2026-11-07): «ID, País, Jugador, Se
 *  parece, Edad, TSI, Forma, Habilidades (1,2,3), Fecha, Precio». Lo dijo dos
 *  veces, y la segunda --«haz caso a lo último que dije hoy»-- cerró una
 *  discusión en la que yo defendía otras dos cosas. Quedan escritas porque
 *  perdieron por decisión suya y no por estar mal, así que si alguna vez se
 *  vuelve sobre esto, se vuelve sabiendo qué se descartó:
 *
 *  · EL PRECIO IBA PRIMERO, desde el 2026-10-07, con el argumento de que es
 *    la respuesta de la tabla y que empezar por el identificador entierra lo
 *    que se vino a ver. Él lo puso último las dos veces.
 *  · TSI Y FORMA IBAN DETRÁS DE LAS HABILIDADES, agrupando «por esto se
 *    parece» (Se parece, Edad, las tres habilidades) y luego «esto no entra»
 *    (TSI, Forma, Especialidad), que es lo que el propio pie del panel
 *    declara. Él las puso delante.
 *
 *  Y DOS COLUMNAS DE DINERO SE FUERON con ese orden, porque su lista nombra
 *  UNA, «Precio»:
 *
 *  · «Puja detectada», la puja con la que entró. Existía para enseñar el
 *    salto hasta el cierre --Cataldi +16%-- y ese salto no se pierde: sigue
 *    en verde al lado del precio, que es donde de verdad se lee.
 *  · «Pedía», lo que pedía el vendedor. El DATO NO SE PIERDE --se sigue
 *    guardando en `market_sales.asking_price` desde la migración 0112, que es
 *    lo que él pidió: «guardar el precio inicial, para analizar la relación
 *    entre precio inicial, final y horario»-- pero deja de ocupar columna.
 *    Ese análisis no era esta tabla.
 *
 *  `Especialidad` no estaba en su lista ninguna de las dos veces. Se queda,
 *  porque la pidió por su nombre el 2026-10-09, y va junto a TSI y Forma: es
 *  del mismo grupo, lo que describe al jugador sin entrar en el parecido. */
// SE EXPORTA SÓLO PARA PROBARLA (2026-11-08). La marca de las 24 semanas
// vive dentro de una celda, y sin esta puerta no hay forma de afirmar que
// sale cuando toca y no sale cuando no: la tabla entera pide datos por su
// cuenta. El aviso de fast-refresh se calla aquí porque el coste es de
// desarrollo --recargar un módulo entero en vez de medio-- y la
// alternativa era mover 250 líneas de columnas a otro fichero.
// eslint-disable-next-line react-refresh/only-export-components
export function columnasDe(
  perfil: RasgoVisible[],
  moneda: string,
): Column<ComparableDeMercado>[] {
  return [
    {
      key: "htPlayerId",
      header: "ID",
      // En crudo: es un nombre escrito con dígitos, no una cantidad que
      // nadie sume, así que no lleva separador de miles.
      raw: true,
      align: "right",
      value: (f) => f.htPlayerId,
    },
    {
      key: "pais",
      header: tx("País"),
      align: "left",
      value: (f) => f.paisNombre || f.paisCodigo,
      render: (f) => (
        <CountryCell code={f.paisCodigo} country={f.paisNombre} compact />
      ),
    },
    {
      key: "nombre",
      header: tx("Jugador"),
      align: "left",
      value: (f) => f.nombre,
      render: (f) => <span className="whitespace-nowrap">{f.nombre}</span>,
    },
    {
      key: "peso",
      header: tx("Se parece"),
      align: "left",
      // Ordena por el peso y no por la palabra: el 100 tiene que ir arriba,
      // y «avalado» va antes que «clavado» en el alfabeto.
      value: (f) => f.peso,
      // En la fila propia, «él mismo»: se parece a sí mismo por definición, y
      // decir «clavado» ahí sonaría a que encontramos un gemelo suyo.
      render: (f) =>
        f.propio ? (
          <span className="whitespace-nowrap text-[var(--muted)]">
            {tx("él mismo")}
          </span>
        ) : (
          <span className={`whitespace-nowrap ${colorDelPeso(f.peso)}`}>
            {comoSeParece(f.peso)}
          </span>
        ),
    },
    {
      key: "edad",
      header: tx("Edad"),
      align: "right",
      // ORDENA POR LA EDAD EXACTA, no por los años (2026-11-07). Dentro del
      // mismo año, el de 24 días es más viejo que el de 2, y en el mercado eso
      // se paga: ordenar sólo por años dejaba el orden interno al azar.
      // 112 días tiene el año de Hattrick.
      value: (f) => f.edad * 112 + Math.max(0, f.dias),
      // EL MISMO FORMATO QUE LA TABLA DE JUGADORES (2026-11-07, pedido del
      // usuario), que es `htAge`: «28;101». Antes esta columna inventaba el
      // suyo --«28 a 101 d»-- y eso obligaba a traducir mentalmente entre dos
      // pantallas que hablan de lo mismo. Un formato por pantalla es un
      // formato de más.
      //
      // `-1` es «no los sabemos»: las ventas anotadas antes de que hubiera
      // columna. Ahi va el año solo, sin inventar unos dias que no tenemos, y
      // sin el `;000` que se leeria como «cumplio hoy».
      render: (f) => (
        <span className="whitespace-nowrap tabular-nums">
          {f.dias >= 0 ? htAge(f.edad, f.dias) : number(f.edad)}
        </span>
      ),
    },
    {
      key: "tsi",
      header: "TSI",
      align: "right",
      value: (f) => f.tsi,
    },
    {
      key: "forma",
      header: tx("Forma"),
      align: "right",
      value: (f) => f.forma,
      // EL NOMBRE OFICIAL Y NO EL NUMERO. La forma se mide de 1 a 8 y Hattrick
      // la dice con las MISMAS palabras que un nivel de habilidad --«excelente»,
      // «aceptable»-- asi que sale del glosario oficial por `skillLevelLabel` y
      // no de una traduccion nuestra: se lee igual que en el juego. El numero se
      // queda para ordenar.
      //
      // `-1` es «no la sabemos»: toda venta anotada antes del 2026-11-07, el
      // dia que se empezo a guardar. Un 0 ahi diria «forma nula», que es un
      // nivel de verdad del juego y seria mentira.
      render: (f) =>
        f.forma >= 1 ? (
          <span className="whitespace-nowrap">
            {skillLevelLabel(f.forma, true)}
          </span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "especialidad",
      header: tx("Especialidad"),
      align: "left",
      value: (f) => f.especialidad,
      // EL NOMBRE Y EL ICONO (2026-10-09, pedido del usuario). Antes iba solo
      // el icono, por sitio: con el nombre al lado, «Sin especialidad» se
      // partia en dos lineas y estiraba TODA la fila, porque el alto lo manda
      // la celda mas alta. `whitespace-nowrap` lo evita sin quitar la palabra,
      // que es lo que el usuario queria leer sin pasar el raton por encima.
      render: (f) => (
        <span className="whitespace-nowrap">
          <Specialty specialty={f.especialidad} />
        </span>
      ),
    },
    ...perfil.map((rasgo, i) => ({
      key: `habilidad${i}`,
      header: nombreDeHabilidad(rasgo.habilidad),
      align: "right" as const,
      value: (f: ComparableDeMercado) => f.perfil[i]?.nivel ?? 0,
    })),
    // AQUÍ VIVÍA «Cierra», y se fue con las subastas abiertas (2026-11-07).
    // Decía cuánto le faltaba a una puja para convertirse en precio --«en 11
    // h», «cerrando»-- y en una venta ya cerrada no le quedaba nada que decir:
    // ponía «cerrada» en todas las filas, una columna entera con una sola
    // palabra. La misma marca de tiempo sigue, leída para la pregunta que sí
    // tiene respuesta: «Fecha».
    {
      key: "fecha",
      header: tx("Fecha"),
      align: "right",
      // LA FECHA DE LA VENTA, que es columna del Comparador de Transferencias
      // (2026-11-07, pedido del usuario). «Cierra» decia cuanto FALTA y
      // «Fecha» dice CUANDO fue: son la misma marca de tiempo leida para dos
      // preguntas distintas, y la segunda es la que sirve para poner una venta
      // en su contexto --«esto se pago en septiembre»-- sin restar mentalmente.
      //
      // Y EN NARANJA SI YA CUMPLIÓ SU VIDA. Esa marca vivía en «Antigüedad»,
      // la columna que el usuario quitó el 2026-11-07 por llamarse «Edad» dos
      // veces en la misma tabla. La columna sobraba --«hace 3 sem» es la misma
      // cosa que la fecha, contada al revés-- pero el aviso no: dice que esta
      // venta sigue en la lista sólo porque no ha aparecido nada más fresco.
      // Así que se muda al color de la fecha y la columna no vuelve.
      // `parseUtc` Y NO `new Date` (2026-11-08). El servidor manda la
      // fecha SIN desfase --«2026-11-03T20:56:09»-- y JavaScript lee esa
      // forma como hora LOCAL, mientras que lo que se PINTA pasa por
      // `parseUtc`, que la lee como UTC. Dos lecturas de la misma cadena
      // en la misma celda: el orden salía bien de milagro, porque el
      // desfase es el mismo para todas las filas.
      value: (f) => (f.cierra ? parseUtc(f.cierra).getTime() : 0),
      render: (f) =>
        f.propio || !f.cierra ? (
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span
            className={`whitespace-nowrap tabular-nums ${f.viejo ? "text-[var(--warn)]" : ""}`}
            title={
              f.viejo
                ? tx(
                    "Ya cumplió sus 24 semanas y sigue contando: sólo deja su sitio cuando la lista llega a 30 y aparece algo mejor.",
                  )
                : undefined
            }
          >
            {/* EL RELOJ DE ARENA (2026-11-08, elegido por el usuario entre
                tres propuestas). Hasta hoy el aviso era SÓLO la fecha en
                ámbar, y el color solo no basta: ni para quien no lo distingue,
                ni para quien ve una fecha de otro color y no sabe qué le están
                diciendo. Añadir una forma lo arregla sin robarle ancho a una
                tabla de trece columnas: cuesta 15 px.

                POR QUÉ UN RELOJ Y NO UN TRIÁNGULO: aquí no hay nada roto. El
                dato está haciendo su trabajo, sólo que es viejo. Un triángulo
                rojo diría «error» y mentiría.

                Y POR QUÉ NO UNA CHINCHETA, que fue la palabra que él usó al
                pedirlo --«un signo ahí como de advertencia, pin»--: una
                chincheta se lee como «esto lo fijé yo a propósito», que es
                justo lo contrario. Esta fila sigue ahí porque no hemos
                encontrado nada mejor, no porque nadie la haya clavado.

                Lleva `role="img"` y su nombre: sin eso, para un lector de
                pantalla la marca no existiría y el aviso volvería a depender
                del color. El porqué entero va en el `title` de la fecha. */}
            {f.viejo && (
              <svg
                width="10"
                height="11"
                viewBox="0 0 10 11"
                fill="none"
                role="img"
                aria-label={tx("Pasó sus 24 semanas")}
                className="mr-1 inline-block align-[-1px]"
              >
                <path
                  d="M2 1h6M2 10h6M2.6 1v1.7c0 1 2.4 2.3 2.4 2.8s-2.4 1.8-2.4 2.8V10M7.4 1v1.7c0 1-2.4 2.3-2.4 2.8s2.4 1.8 2.4 2.8V10"
                  stroke="currentColor"
                  strokeWidth="1.1"
                  strokeLinecap="round"
                />
              </svg>
            )}
            {date(f.cierra)}
          </span>
        ),
    },
    {
      key: "precio",
      // «Precio» Y NO «Se pagó» (2026-11-07). El rótulo decía «Se pagó» para
      // distinguirlo de la puja de al lado, y sin esa columna la distinción no
      // existe: lo que hay en la tabla son precios pagados y nada más. Él la
      // llamó «Precio» las dos veces.
      header: tx("Precio"),
      align: "right",
      value: (f) => f.precio,
      // UN SOLO ESTADO DESDE EL 2026-11-07, porque ya no hay más: la lista es
      // sólo de ventas cerradas. Aquí vivían tres rótulos --«sin cerrar», «sin
      // confirmar», «NO PUJA DETECTADA»-- y los tres decían por qué esa fila
      // no traía precio. Sin esas filas, no hay nada que explicar.
      //
      // La raya se queda para la fila del jugador propio: no está en venta, y
      // un cero ahí diría «vale cero».
      render: (f) =>
        f.propio ? (
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span className="tabular-nums">
            {money(f.precio, moneda)}
            {/* EL SALTO DESDE LA PUJA, que es lo único que sobrevive de la
                columna «Puja detectada»: cuánto subió del momento en que la
                vimos al cierre. Cataldi +16%, Bernacki +2%, siempre hacia
                arriba, porque el precio de cierre ES la puja ganadora. */}
            {f.puja > 0 && f.precio !== f.puja && (
              <span className="ml-1 text-xs text-[var(--positive)]">
                {salto(f.puja, f.precio)}
              </span>
            )}
            {/* UNA VENTA CERRADA A LA QUE NUNCA LE VIMOS PUJA (2026-11-07).
                Es el caso que el usuario encontro: el 472301981 se vendio de
                verdad y para nosotros estuvo a cero hasta el final. El sello
                dice por que no hay salto que enseñar al lado del precio: no es
                que la puja fuera igual, es que no llegamos a ver ninguna. */}
            {f.sinPuja && (
              <span className="ml-1 text-xs text-[var(--muted)]">
                {tx("sin puja vista")}
              </span>
            )}
          </span>
        ),
    },
  ];
}

/** Las columnas de la tabla de STAND-BY (2026-11-08, pedido del usuario:
 *  «¿será que ponemos la tabla de stand-by más abajo que la tabla de
 *  transferencias?»).
 *
 *  LAS MISMAS DE ARRIBA HASTA LA ESPECIALIDAD, y a propósito: es la misma
 *  gente mirada en otro momento, así que leerla no puede pedir aprender otra
 *  tabla. Lo que cambia es la cola, y cambia porque aquí NO HAY PRECIO:
 *  nadie ha pagado nada todavía.
 *
 *  · «Cierra» en vez de «Fecha». Arriba la marca de tiempo contesta «cuándo
 *    fue»; aquí contesta «cuándo se sabrá», que es lo único que importa de
 *    una subasta viva. Va con la hora, no sólo el día: un plazo son las
 *    21:14, no «el martes».
 *  · «Precio inicial», que es lo que pide el dueño. El nombre lo puso él, y
 *    es el mismo que usó al pedir que se guardara el 2026-11-07: «guardar el
 *    precio inicial, para analizar la relación entre precio inicial, final y
 *    horario». Se guarda desde la migración 0112; lo anterior vale cero y
 *    aquí sale como raya.
 *  · «Puja», lo ofrecido ahora mismo. Cero no es «vale cero», es «nadie ha
 *    pujado todavía», y se escribe así: la mitad de lo que hay en stand-by
 *    está a cero y confundir las dos cosas sería leer un mercado vacío donde
 *    hay anuncios vivos.
 *
 *  NINGUNA DE LAS TRES ENTRA EN NINGÚN NÚMERO. Esta tabla no promedia nada
 *  --ver `en_espera` en el backend-- y está aquí para explicar por qué el
 *  precio de arriba va a moverse en los próximos días. */
// eslint-disable-next-line react-refresh/only-export-components
export function columnasEnEspera(
  perfil: RasgoVisible[],
  moneda: string,
): Column<ComparableDeMercado>[] {
  return [
    {
      key: "htPlayerId",
      header: "ID",
      raw: true,
      align: "right",
      value: (f) => f.htPlayerId,
    },
    {
      key: "pais",
      header: tx("País"),
      align: "left",
      value: (f) => f.paisNombre || f.paisCodigo,
      render: (f) => (
        <CountryCell code={f.paisCodigo} country={f.paisNombre} compact />
      ),
    },
    {
      key: "nombre",
      header: tx("Jugador"),
      align: "left",
      value: (f) => f.nombre,
      render: (f) => <span className="whitespace-nowrap">{f.nombre}</span>,
    },
    {
      key: "peso",
      header: tx("Se parece"),
      align: "left",
      value: (f) => f.peso,
      render: (f) => (
        <span className={`whitespace-nowrap ${colorDelPeso(f.peso)}`}>
          {comoSeParece(f.peso)}
        </span>
      ),
    },
    {
      key: "edad",
      header: tx("Edad"),
      align: "right",
      value: (f) => f.edad * 112 + Math.max(0, f.dias),
      render: (f) => (
        <span className="whitespace-nowrap tabular-nums">
          {f.dias >= 0 ? htAge(f.edad, f.dias) : number(f.edad)}
        </span>
      ),
    },
    { key: "tsi", header: "TSI", align: "right", value: (f) => f.tsi },
    {
      key: "forma",
      header: tx("Forma"),
      align: "right",
      value: (f) => f.forma,
      render: (f) =>
        f.forma >= 1 ? (
          <span className="whitespace-nowrap">
            {skillLevelLabel(f.forma, true)}
          </span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "especialidad",
      header: tx("Especialidad"),
      align: "left",
      value: (f) => f.especialidad,
      render: (f) => (
        <span className="whitespace-nowrap">
          <Specialty specialty={f.especialidad} />
        </span>
      ),
    },
    ...perfil.map((rasgo, i) => ({
      key: `habilidad${i}`,
      header: nombreDeHabilidad(rasgo.habilidad),
      align: "right" as const,
      value: (f: ComparableDeMercado) => f.perfil[i]?.nivel ?? 0,
    })),
    {
      key: "cierra",
      header: tx("Cierra"),
      align: "right",
      // `parseUtc` Y NO `new Date` (2026-11-08). El servidor manda la
      // fecha SIN desfase --«2026-11-03T20:56:09»-- y JavaScript lee esa
      // forma como hora LOCAL, mientras que lo que se PINTA pasa por
      // `parseUtc`, que la lee como UTC. Dos lecturas de la misma cadena
      // en la misma celda: el orden salía bien de milagro, porque el
      // desfase es el mismo para todas las filas.
      value: (f) => (f.cierra ? parseUtc(f.cierra).getTime() : 0),
      render: (f) =>
        f.cierra ? (
          <span className="whitespace-nowrap tabular-nums">
            {dateTime(f.cierra)}
          </span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "precioPedido",
      header: tx("Precio inicial"),
      align: "right",
      value: (f) => f.precioPedido,
      // CERO ES «NO LO SABEMOS», no «lo regala»: las ventas anotadas antes de
      // la migración 0112 no lo traen. Una raya lo dice; un 0 US$ mentiría.
      render: (f) =>
        f.precioPedido > 0 ? (
          <span className="tabular-nums">{money(f.precioPedido, moneda)}</span>
        ) : (
          <span className="text-[var(--muted)]">—</span>
        ),
    },
    {
      key: "puja",
      header: tx("Puja"),
      align: "right",
      value: (f) => f.puja,
      render: (f) =>
        f.puja > 0 ? (
          <span className="tabular-nums">{money(f.puja, moneda)}</span>
        ) : (
          <span className="whitespace-nowrap text-xs text-[var(--muted)]">
            {tx("sin pujas todavía")}
          </span>
        ),
    },
  ];
}

export function PrecioPorComparables({
  htPlayerId,
  activo = true,
}: {
  htPlayerId: number | null;
  /** Para no pedirlo mientras la pestaña está cerrada. */
  activo?: boolean;
}) {
  const consulta = usePrecioComparable(htPlayerId, { enabled: activo });
  const datos = consulta.data;
  // AQUÍ VIVÍA EL MANDO «QUÉ SE DIBUJA», de «sólo ventas cerradas» a «también
  // pujas abiertas», y se fue el 2026-11-07 con las pujas mismas: «quitar el
  // Qué se dibuja, porque de ahora en adelante solo tendremos ventas
  // cerradas». Un mando de dos posiciones en el que las dos pintan lo mismo
  // no es una opción, es una pregunta sin respuesta distinta.
  //
  // Y con él se fue el filtro que había debajo: la lista que llega del
  // servidor ya es sólo de ventas cerradas, así que las dos gráficas y la
  // tabla pintan exactamente lo mismo que promedia la cifra de arriba. No hay
  // dos versiones de los mismos datos en la misma pantalla.

  if (consulta.isLoading || !datos) {
    return (
      <Panel title={tx("Lo que ha costado gente como él")}>
        <p className="px-4 py-3 text-sm text-[var(--muted)]">
          {consulta.isLoading ? tx("Cargando…") : tx("Sin datos todavía.")}
        </p>
      </Panel>
    );
  }

  const hayNumero = datos.media != null;
  // Las dos clases que puede tener una venta que cuenta, para decir de qué
  // está hecho el número sin que nadie tenga que contar filas.
  const cerradas = datos.comparables.filter((f) => f.firme);
  const clavadas = cerradas.filter((f) => f.peso >= 100).length;
  const avaladas = cerradas.length - clavadas;

  return (
    <Panel
      title={tx("Lo que ha costado gente como él")}
      ayuda={tx(
        "Ventas reales de jugadores con las mismas tres habilidades más altas, en el mismo orden, y una edad parecida. Cuanto más haya que abrir la búsqueda para encontrarlos, menos pesa cada uno.",
      )}
      meta={
        <span className="text-xs text-[var(--muted)]">
          {perfilLegible(datos.perfil)}
        </span>
      }
    >
      <div className="px-4 py-3">
        {/* EL NUMERO FLOJO SE AVISA (2026-10-26). Desde que se da precio con
            las ventas que haya --«precio con los que hayan», decision del
            usuario-- un jugador puede tener cifra apoyada en tres ventas, y
            antes eso no podia pasar: por debajo de ocho no habia numero, asi
            que el aviso era innecesario. Ahora el aviso ES la diferencia entre
            un numero honesto y uno que aparenta mas de lo que sabe.

            Y SE DICE SOLO `n`, SIN OBJETIVO AL LADO (2026-11-08, decision del
            usuario). La frase decia «sale de 3 ventas, NO DE 8», y ese ocho
            hacia dos trabajos a la vez: era el objetivo de recogida y era el
            umbral del aviso. Al rehacer el algoritmo el objetivo paso a 30, y
            ponerlo aqui haria leer como flojo un precio apoyado en veintinueve
            ventas reales. El umbral sigue en ocho --`VENTAS_PARA_FIARSE`, en
            el backend-- pero ya no se ensena: no es un objetivo, es la raya por
            debajo de la cual una venta rara mueve demasiado. */}
        {hayNumero && datos.faltan > 0 && (
          <p className="mb-3 rounded-lg bg-[var(--surface-2)] px-4 py-2 text-sm text-[var(--muted)]">
            {datos.n === 1
              ? tx(
                  "Ojo: este número sale de UNA sola venta. Con tan pocas, una venta rara lo mueve entero.",
                )
              : tx(
                  "Ojo: este número sale de {{v0}} ventas. Con tan pocas, una venta rara lo mueve mucho.",
                  { v0: number(datos.n) },
                )}
          </p>
        )}
        {hayNumero ? (
          <>
            {/* TARJETAS Y NO UNA LINEA APRETADA. Las tres cifras compartian
                renglon con sus rotulos minusculos encima, y a ancho de
                escritorio quedaban perdidas contra el margen izquierdo
                (2026-10-08, el usuario: «ese layout espantoso»). */}
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg bg-[var(--surface-2)] px-4 py-3">
                <div className="flex items-center gap-1 text-xs uppercase tracking-wide text-[var(--muted)]">
                  {tx("Media")}
                  <Ayuda
                    texto={tx(
                      "El promedio de lo que costaron, pero pesando a cada uno por lo que se parece: un gemelo cuenta el doble que un primo lejano. Sube cuando entra una venta cara de alguien muy parecido.",
                    )}
                  />
                </div>
                <div className="text-2xl font-semibold tabular-nums text-[var(--text)]">
                  {money(datos.media as number, datos.moneda)}
                </div>
              </div>
              <div className="rounded-lg bg-[var(--surface-2)] px-4 py-3">
                <div className="flex items-center gap-1 text-xs uppercase tracking-wide text-[var(--muted)]">
                  {tx("Mediana")}
                  <Ayuda
                    texto={tx(
                      "El precio que parte la lista por la mitad, contando también el parecido. Si la media y la mediana se separan mucho, es que una sola venta muy cara o muy barata está tirando del promedio.",
                    )}
                  />
                </div>
                <div className="text-lg tabular-nums text-[var(--text)]">
                  {money(datos.mediana as number, datos.moneda)}
                </div>
              </div>
              <div className="rounded-lg bg-[var(--surface-2)] px-4 py-3">
                <div className="flex items-center gap-1 text-xs uppercase tracking-wide text-[var(--muted)]">
                  {/* Ya siempre «se pagó», y es correcto desde el
                      2026-10-09: los dos extremos salen de las que cuentan, y
                      desde esa fecha sólo cuentan las ventas cerradas. El
                      rótulo alternaba porque antes una puja podía ser el
                      extremo, y entonces el panel decía «DE VERDAD SE PAGÓ
                      ENTRE 10.000 – 13.260.000» mientras cada fila ponía
                      «puja» al lado del número (2026-10-07). */}
                  {tx("De verdad se pagó entre")}
                  <Ayuda
                    texto={tx(
                      "Los dos extremos de la lista, sin ponderar: lo más barato y lo más caro que hay en ella. Dice cuánto se abre el mercado de este perfil.",
                    )}
                  />
                </div>
                <div className="text-lg tabular-nums text-[var(--text)]">
                  {money(datos.minimo as number, datos.moneda)} –{" "}
                  {money(datos.maximo as number, datos.moneda)}
                </div>
              </div>
            </div>
            {/* DE QUÉ ESTÁ HECHO EL NÚMERO, en pastillas y pegado a él.
                Era una frase que decía «de N ventas, el que menos se parece
                cuenta un X%», y ese X dejó de existir el 2026-10-27: con dos
                pesos, lo que informa es CUÁNTAS de cada clase. Y lo que no
                promedia se dice aquí, no en una nota al pie. */}
            <div className="mt-3 flex flex-wrap gap-1.5">
              <Pastilla>
                {tx("{{v0}} ventas cerradas", { v0: number(datos.n) })}
              </Pastilla>
              {clavadas > 0 && (
                <Pastilla
                  tono="bien"
                  ayuda={tx(
                    "Idéntico es el mismo jugador: su misma edad y las tres habilidades más altas en el mismo nivel. No existe comparable mejor, y por eso no caduca.",
                  )}
                >
                  {tx("{{v0}} idénticas", { v0: number(clavadas) })}
                </Pastilla>
              )}
              {avaladas > 0 && (
                <Pastilla
                  ayuda={tx(
                    "Equivalente es que el propio Hattrick enseñaría esa venta al comparar a tu jugador, sin ser el mismo jugador. Pesa 90, y una idéntica puede sustituirla.",
                  )}
                >
                  {tx("{{v0}} equivalentes", { v0: number(avaladas) })}
                </Pastilla>
              )}
              {datos.provisionales > 0 && (
                <Pastilla
                  tono="aviso"
                  ayuda={tx(
                    "Una puja no es un precio, y no por poco: el 5 de octubre una de 65.000.000 cerró en 77.720.000. Se guardan y se vigilan para sacarles el precio cuando cierren, pero no promedian.",
                  )}
                >
                  {datos.provisionales === 1
                    ? tx("1 puja abierta, fuera del número")
                    : tx("{{v0}} pujas abiertas, fuera del número", {
                        v0: number(datos.provisionales),
                      })}
                </Pastilla>
              )}
              {datos.semanasDelMasViejo >= 7 && (
                <Pastilla
                  tono="aviso"
                  ayuda={tx(
                    "Sigue contando porque no ha aparecido nada más reciente: un dato viejo informa más que ninguno. Pero habla de un mercado que pudo cambiar.",
                  )}
                >
                  {tx("la más vieja, de hace {{v0}} sem", {
                    v0: number(datos.semanasDelMasViejo),
                  })}
                </Pastilla>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-[var(--text)]">
            {/* Sin NI UNA venta cerrada no hay nada que promediar, y eso no es
                una regla sino aritmética. La frase decía «las subastas
                abiertas se enseñan abajo» y dejó de ser verdad el 2026-11-07,
                el día que las filas sin venta salieron de la tabla: debajo ya
                no hay nada. Lo que sí se puede decir es qué pasará con ellas.
            */}
            {tx(
              "Todavía no se ha vendido ningún jugador parecido. Las subastas que haya en marcha entran en la lista cuando cierren, con el precio que se pagó de verdad.",
            )}
          </p>
        )}

        <CriteriosDeHattrick datos={datos} />
      </div>

      {/* EL REPARTO, justo debajo de las cifras. La media y la mediana
          dicen dónde está el centro; esto dice si hay un centro, que es la
          pregunta que una cifra sola no contesta: ocho ventas apretadas y
          ocho repartidas de 10.000 a 13.000.000 dan la misma media.

          El comentario de aquí decía que se veía «un grupo pegado al cero,
          subastas que nadie ha pujado»: eso ya no pasa desde el 2026-11-07,
          porque esas filas no llegan. Lo que queda son precios pagados. */}
      {datos.comparables.length >= MINIMO_PARA_LA_TIRA && (
        <div className="px-4 pb-1">
          <Chart
            height={150}
            ariaLabel={tx("Reparto de los precios de las ventas comparables")}
            option={tiraDePuntosOption(
              datos.comparables.map(
                (f) => [f.precio, f.firme, f.peso] as [number, boolean, number],
              ),
              {
                media: datos.media,
                mediana: datos.mediana,
                detalle: (v) => money(v, datos.moneda),
                etiquetaMedia: tx("Media"),
                etiquetaMediana: tx("Mediana"),
              },
            )}
          />
        </div>
      )}

      {/* LA SERIE, entre el número y la tabla: es el puente. El número dice
          cuánto; la tabla, de dónde sale; esto, si puedes fiarte todavía.
          Desde dos lecturas, porque con una no hay nada que unir.
          
          SIN LÍNEA CUANDO NO HAY NÚMERO (2026-10-24). Esta gráfica se pintaba
          mirando sólo cuántas lecturas había, sin mirar si el panel tenía
          precio que dar. El resultado era una pantalla que se contradecía a sí
          misma: arriba «hay 6 y hacen falta 2 más», y justo debajo una línea
          subiendo hasta 530.327 US$ rotulada «Media de las ventas cerradas».
          Quien mira se queda con el número, no con la advertencia.
          
          Y no era la cifra del panel sino OTRA: la línea es la media simple de
          lo que se ve en cada lectura, mientras que el número de arriba es una
          media ponderada que exige llegar al objetivo. Dos reglas distintas
          dando dos respuestas, una de ellas negada por el texto.
          
          Los puntos se quedan: son ventas que existieron a precios que se
          pagaron, y enseñarlas es lo que deja ver cómo se va llenando el
          fondo. Lo que se va es la respuesta que todavía no toca. */}
      {datos.serie.length >= MINIMO_PARA_LA_SERIE && (
        <div className="px-4 pb-2">
          <Chart
            height={200}
            ariaLabel={
              hayNumero
                ? tx("Cómo ha ido cambiando el precio de sus comparables")
                : tx("Las ventas encontradas hasta ahora, sin media todavía")
            }
            option={serieDePuntosOption(datos.serie, {
              etiqueta: (iso) => date(iso),
              detalle: (v) => money(v, datos.moneda),
              conMedia: hayNumero,
              etiquetaMedia: tx("Media de las ventas cerradas"),
            })}
          />
          {!hayNumero && (
            <p className="prosa text-xs text-[var(--muted)]">
              {tx(
                "Son las ventas encontradas hasta ahora, una por punto. La línea de la media aparece cuando haya bastantes para dar un precio.",
              )}
            </p>
          )}
        </div>
      )}

      {datos.comparables.length > 0 && (
        <div className="px-4 pb-3">
          {/* Ordenada por parecido y no por precio (2026-10-07, pedido del
              usuario). Es el orden en el que el número está hecho: arriba
              los que más mandan en él. Dentro del mismo peso se conserva el
              orden que trae el servidor --más reciente, más caro, y en el
              último empate el que comparte especialidad-- porque la
              ordenación de la tabla es estable. */}
          <DataTable
            rows={datos.comparables}
            columns={columnasDe(datos.perfil, datos.moneda)}
            rowKey={(f) => f.htPlayerId}
            initialSort="peso"
            csvName="comparables"
            emptyMessage={tx("Sin ventas de jugadores parecidos todavía.")}
            sinFiltro
            sinHerramientas
            filaFijada={datos.jugador}
          />
        </div>
      )}

      {/* LO QUE TODAVÍA NO HA CERRADO, en su propia tabla y DEBAJO
          (2026-11-08, pedido del usuario).

          No contradice su regla del 2026-11-07 --«los jugadores que nunca se
          vendieron, no deben ir en la lista»--: aquélla era para que la lista
          de comparables no mezclara lo que promedia con lo que no. Esto es
          una segunda tabla, con su propio título, que dice que todavía no
          cuenta. Y va debajo porque se lee después: primero el precio y de
          qué está hecho, luego lo que puede cambiarlo.

          VA FUERA DEL `hayNumero` a propósito. Un jugador puede no tener
          precio y sí tener cosas esperando --es el caso de Kurt Schönhueb el
          2026-11-08: cero ventas cerradas y dos anuncios vivos-- y
          esconderle justo esa tabla sería esconderle la única explicación de
          por qué su panel está vacío. */}
      {datos.enEspera.length > 0 && (
        <div className="px-4 pb-3">
          <h3 className="mb-2 text-[10px] uppercase tracking-wide text-[var(--muted)]">
            {tx("Esperando su precio")}
          </h3>
          <p className="prosa mb-3 max-w-[70ch] text-xs leading-relaxed text-[var(--muted)]">
            {tx(
              "Anuncios y subastas que todavía no han cerrado. No entran en el número: una puja no es un precio. Cuando cierren, las que se vendan pasan a la tabla de arriba con lo que de verdad se pagó, y las que no se vendan se descartan.",
            )}
          </p>
          <DataTable
            rows={datos.enEspera}
            columns={columnasEnEspera(datos.perfil, datos.moneda)}
            rowKey={(f) => f.htPlayerId}
            initialSort="cierra"
            initialDescending={false}
            emptyMessage={tx("Nada esperando su precio ahora mismo.")}
            sinFiltro
            sinHerramientas
          />
        </div>
      )}

      <p className="prosa px-4 py-3 text-xs leading-relaxed text-[var(--muted)]">
        {tx(
          "Esto dice lo que se pagó por otros, no lo que te darían a ti: no tiene en cuenta su forma, su experiencia ni su especialidad.",
        )}
      </p>
    </Panel>
  );
}
