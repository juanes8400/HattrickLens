/** Lo que ha costado la gente parecida a un jugador tuyo.
 *
 *  ES UNA DESCRIPCIÓN DEL MERCADO, NO UNA PREDICCIÓN. Dice qué se pagó por
 *  jugadores que se le parecen, y no lo que te darían por él: no corrige por
 *  forma, experiencia, especialidad ni bonos de club de origen. Esa distinción
 *  la decidió el usuario y gobierna todo lo que se escribe aquí.
 *
 *  Tres cosas que la pantalla está obligada a decir, y por eso ocupan sitio:
 *
 *  · **Cuántas son todavía pujas.** Una venta entra con la puja de precio
 *    hasta que su subasta cierra, y la puja se queda corta: el 2026-10-05
 *    Valerio Cataldi tenía 65.000.000 de puja y cerró en 77.720.000, un 16%
 *    más. Un número hecho de pujas tira a bajo.
 *  · **Cuánto se parecen**, y desde el 2026-10-27 sólo hay dos maneras:
 *    CLAVADO es el mismo jugador --misma edad y las tres habilidades más altas
 *    en el mismo nivel-- y AVALADO es que el propio Hattrick enseñaría esa
 *    venta al comparar al tuyo, sin ser el mismo. No hay nada en medio: lo que
 *    no es una de las dos cosas no entra en la lista.
 *  · **CON QUÉ FILTROS buscó Hattrick** (2026-10-27). Los siete, con sus
 *    rangos, y el dial que los ensancha. Es lo único que esta pantalla no
 *    podía decir --enseñaba las ventas pero no por qué ésas-- y el por qué
 *    está medido contra su propio Comparador, no supuesto.
 *  · **De cuándo son.** Una venta sigue contando pasadas las siete semanas si
 *    no apareció nada mejor, y entonces habla de un mercado que pudo cambiar.
 *
 *  No pide nada a Hattrick: todo sale del fondo que dejó el paso semanal, así
 *  que abrir y cerrar esto es gratis.
 */
import { useState, type ReactNode } from "react";

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
import { date, money, number } from "../hooks/useFormat";
import { usePrecioComparable } from "../hooks/useTeam";
import { tx } from "../i18n/tx";
import { terminoOficial } from "../i18n/glosario";
import { skillLevelLabel } from "../utils/skillLevels";
import type {
  ComparableDeMercado,
  CriterioDeHattrick,
  PrecioComparable,
  RasgoVisible,
} from "../services/api";

/** El nombre en español de cada habilidad, que es el respaldo del glosario.
 *  Sólo las seis que cuentan: la resistencia y el balón parado no entran en
 *  el parecido. */
const EN_ESPANOL: Record<string, string> = {
  keeper: "Portería",
  defending: "Defensa",
  playmaking: "Jugadas",
  winger: "Lateral",
  passing: "Pases",
  scoring: "Anotación",
};

/** «Anotación 18 · Pases 13 · Jugadas 7».
 *
 *  El nombre sale del glosario OFICIAL de Hattrick, no de una traducción
 *  nuestra: así el jugador lee exactamente la misma palabra que ve en el
 *  juego. Se calcula en el render y no en una constante del módulo para que
 *  cambie al vuelo cuando se cambia de idioma. */
function perfilLegible(perfil: RasgoVisible[]): string {
  return perfil
    .map(
      (r) =>
        `${terminoOficial("habilidades", r.habilidad, EN_ESPANOL[r.habilidad] ?? r.habilidad)} ${r.nivel}`,
    )
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
 *  EL DIAL SE ENSEÑA CON SUS CUENTAS. Decir «la búsqueda salió ancha» sin los
 *  números es pedir fe; con la rareza y el listón al lado, se comprueba. */
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
      <p className="prosa mt-2 text-xs text-[var(--muted)]">
        {datos.dialHolgado
          ? tx(
              "Búsqueda ancha: su rareza es {{v0}} y el listón que le toca {{v1}}, así que Hattrick abre la ventana de edad y las bandas.",
              { v0: datos.rareza, v1: datos.liston },
            )
          : tx(
              "Búsqueda estrecha: su rareza es {{v0}} y no llega al listón de {{v1}}, así que Hattrick le clava la edad y aprieta las bandas.",
              { v0: datos.rareza, v1: datos.liston },
            )}
      </p>
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

/** «en 11 h», «cerrando», «cerrada».
 *
 *  La columna enseñaba el sello entero --«08/10/2026 12:37»-- y eso hacia
 *  dos cosas malas: ocupaba el ancho que sacaba la tabla de su contenedor, y
 *  obligaba a restar mentalmente para saber lo unico que importa, que es
 *  cuanto le falta a esa puja para convertirse en precio (2026-10-08).
 *
 *  `firme` MANDA SOBRE EL PLAZO, y es el arreglo del 2026-10-09. El plazo no
 *  se borra al resolver una venta, asi que una ya vendida tenia el plazo
 *  pasado y salia «cerrando» --«todavia no he ido a mirar»-- al lado de su
 *  precio real: la fila se contradecia a si misma. Mituta, 792.000 US$ y
 *  «cerrando» en la misma linea. La rama de «cerrada» no se ejecutaba nunca,
 *  porque esperaba un plazo vacio que no llega jamas.
 */
function cuantoFalta(iso: string | null, firme: boolean): string {
  if (firme || !iso) return tx("cerrada");
  const horas = (new Date(iso).getTime() - Date.now()) / 3_600_000;
  if (horas <= 0) return tx("cerrando");
  if (horas < 48) return tx("en {{v0}} h", { v0: String(Math.round(horas)) });
  return tx("en {{v0}} d", { v0: String(Math.round(horas / 24)) });
}

/** El nombre oficial de una habilidad, para la cabecera de su columna. */
function nombreDeHabilidad(clave: string): string {
  return terminoOficial("habilidades", clave, EN_ESPANOL[clave] ?? clave);
}

/** Las columnas, armadas contra la terna del jugador que pregunta.
 *
 *  No son fijas porque la terna no lo es: a un delantero se le comparan
 *  anotación, pases y jugadas, y a un defensa otras tres. Como todos los
 *  comparables comparten la terna del objetivo --esa es la definición de
 *  comparable-- `perfil[i]` es la misma habilidad en todas las filas. */
function columnasDe(
  perfil: RasgoVisible[],
  moneda: string,
): Column<ComparableDeMercado>[] {
  return [
    // El precio va primero aunque no estuviera en el orden que pidió el
    // usuario (2026-10-07): es la respuesta de la tabla, y una tabla de
    // precios que empieza por el identificador entierra lo que se vino a
    // ver. El resto va exactamente como lo pidió.
    // DOS COLUMNAS Y NO UNA (2026-10-07, pedido del usuario). Antes había
    // un solo número que cambiaba de significado al resolverse --puja hasta
    // que cerraba, precio de verdad después-- y el salto entre los dos se
    // perdía. Ese salto es el dato que dice cuánto se queda corta una puja:
    // Cataldi +16%, Bernacki +2%, siempre hacia arriba.
    {
      key: "puja",
      header: tx("Puja detectada"),
      align: "right",
      value: (f) => f.puja,
      // EN LA FILA PROPIA, NADA. Tu jugador no esta en venta: no tiene puja,
      // ni precio, ni plazo, ni antiguedad. Un cero ahi se leeria como «vale
      // cero», que es justo lo contrario de lo que dice.
      render: (f) =>
        f.propio ? (
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span className="tabular-nums text-[var(--muted)]">
            {money(f.puja, moneda)}
          </span>
        ),
    },
    {
      key: "precio",
      header: tx("Se pagó"),
      align: "right",
      // Ordena por el precio que cuenta, que para un provisional es su
      // puja: dejarlo en cero mandaría al fondo justo lo que todavía no
      // se sabe, como si valiera menos que nada.
      value: (f) => f.precio,
      render: (f) =>
        f.propio ? (
          <span className="text-[var(--muted)]">—</span>
        ) : f.firme ? (
          <span className="tabular-nums">
            {money(f.precio, moneda)}
            {f.puja > 0 && f.precio !== f.puja && (
              <span className="ml-1 text-xs text-[var(--positive)]">
                {salto(f.puja, f.precio)}
              </span>
            )}
          </span>
        ) : (
          <span className="whitespace-nowrap text-xs text-[var(--warn)]">
            {/* Tres estados distintos, no dos. Un anuncio que nadie ha
                pujado tampoco cuenta, pero no es que fallara al
                confirmarse: es que todavía no hay precio que confirmar
                (2026-10-07, al ver que a Kurt Schönhueb no le salía ni un
                comparable con puja y sí ocho sin ella).

                Cortos y de una pieza: partidos en dos lineas estiraban toda
                la fila, porque el alto lo manda la celda mas alta. */}
            {f.puja <= 0
              ? tx("sin pujas")
              : f.cuenta
                ? tx("sin cerrar")
                : tx("sin confirmar")}
          </span>
        ),
    },
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
      value: (f) => f.edad,
    },
    ...perfil.map((rasgo, i) => ({
      key: `habilidad${i}`,
      header: nombreDeHabilidad(rasgo.habilidad),
      align: "right" as const,
      value: (f: ComparableDeMercado) => f.perfil[i]?.nivel ?? 0,
    })),
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
    {
      key: "tsi",
      header: "TSI",
      align: "right",
      value: (f) => f.tsi,
    },
    {
      key: "cierra",
      header: tx("Cierra"),
      align: "right",
      // Lo ya cerrado al final cuando se ordena por esta columna: un plazo
      // que no existe no es «hace mucho», es que ya no aplica.
      // Lo ya firme va al final tambien aqui: su plazo es historia, no una
      // espera, y ordenar por el mezclaba lo cerrado entre lo que falta.
      value: (f) =>
        f.firme || !f.cierra ? Infinity : new Date(f.cierra).getTime(),
      render: (f) =>
        f.propio ? (
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span className="whitespace-nowrap tabular-nums">
            {cuantoFalta(f.cierra, f.firme)}
          </span>
        ),
    },
    {
      key: "semanas",
      header: tx("Antigüedad"),
      align: "right",
      value: (f) => f.semanas,
      render: (f) =>
        f.propio ? (
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span
            className={`whitespace-nowrap tabular-nums ${f.viejo ? "text-[var(--warn)]" : ""}`}
          >
            {tx("{{v0}} sem", { v0: number(f.semanas) })}
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
  // EL MANDO DE LAS GRÁFICAS (2026-10-09, pedido del usuario).
  //
  // Arranca por sólo ventas cerradas, que es de lo que sale la cifra de
  // arriba. Con las pujas se ve más, pero se ve otra cosa: Edu Fuenllana
  // pujaba 6.000 US$ y se vendió en 1.241.000.
  //
  // HUBO UN SEGUNDO MANDO, de escala lineal o logarítmica, y duró una tarde.
  // La logarítmica resolvía que los tres precios baratos se amontonaran
  // contra el margen izquierdo... y esos tres eran pujas abiertas. Al dejar
  // las gráficas en sólo ventas cerradas, el rango se estrechó y el problema
  // desapareció con él. El usuario lo quitó: era un arreglo para algo que ya
  // no pasa, y la logarítmica tiene su propio precio --la distancia deja de
  // ser dinero--.
  const [soloCerradas, setSoloCerradas] = useState(true);
  const datos = consulta.data;
  // Lo que pinta la tira. Si se pidieron sólo las cerradas y no hay ninguna,
  // se enseñan todas: una gráfica vacía dice «aquí no hay nada», que no es
  // lo mismo que «aquí no ha cerrado nada todavía».
  const comparables = datos?.comparables ?? [];
  const paraLaTira =
    soloCerradas && comparables.some((f) => f.firme)
      ? comparables.filter((f) => f.firme)
      : comparables;

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
            un numero honesto y uno que aparenta mas de lo que sabe. */}
        {hayNumero && datos.faltan > 0 && (
          <p className="mb-3 rounded-lg bg-[var(--surface-2)] px-4 py-2 text-sm text-[var(--muted)]">
            {datos.n === 1
              ? tx(
                  "Ojo: este número sale de UNA sola venta. Con tan pocas, una venta rara lo mueve entero.",
                )
              : tx(
                  "Ojo: este número sale de {{v0}} ventas, no de {{v1}}. Con tan pocas, una venta rara lo mueve mucho.",
                  { v0: number(datos.n), v1: number(datos.n + datos.faltan) },
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
            {/* Sin NI UNA venta cerrada no hay nada que promediar, y eso no
                es una regla sino aritmetica. Las subastas vivas se enseñan en
                la tabla pero no cuentan: una puja no es un precio. */}
            {tx(
              "Todavía no hay ninguna venta cerrada de jugadores parecidos. Las subastas abiertas se enseñan abajo, pero una puja no es un precio.",
            )}
          </p>
        )}

        <CriteriosDeHattrick datos={datos} />
      </div>

      {/* EL REPARTO, justo debajo de las cifras. La media y la mediana
          dicen dónde está el centro; esto dice si hay un centro. Con el
          fondo de hoy se ve de golpe lo que cuesta leer en la tabla: un
          grupo pegado al cero --subastas que nadie ha pujado-- y el
          mercado de verdad mucho más arriba. */}
      {datos.comparables.length >= MINIMO_PARA_LA_TIRA && (
        <div className="px-4 pb-1">
          {/* EL MANDO, encima de las dos gráficas, porque gobierna a las dos.
              No toca la cifra de arriba: ésa sale sólo de ventas cerradas y
              es una decisión, no una vista (2026-10-09). */}
          <div className="mb-2 flex flex-wrap items-center gap-x-4 gap-y-2">
            <DosOpciones
              label={tx("Qué se dibuja")}
              valor={soloCerradas ? "cerradas" : "todo"}
              opciones={[
                ["cerradas", tx("Sólo ventas cerradas")],
                ["todo", tx("También pujas abiertas")],
              ]}
              onCambio={(v) => setSoloCerradas(v === "cerradas")}
            />
          </div>
          <Chart
            height={150}
            ariaLabel={tx("Reparto de los precios de las ventas comparables")}
            option={tiraDePuntosOption(
              paraLaTira.map(
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
              soloCerradas,
              conMedia: hayNumero,
              etiquetaMedia: soloCerradas
                ? tx("Media de las ventas cerradas")
                : tx("Media de todo lo de la lista"),
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
            filaFijada={datos.jugador}
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

/** Un mando de dos posiciones, con la forma de los de Alineación.
 *
 *  No es `SplitSelector`: aquél sólo admite números --es el reparto de una
 *  línea-- y aquí las opciones son palabras. Vive en este fichero mientras
 *  sea el único que lo usa; el día que haga falta en otra pantalla, se muda.
 */
function DosOpciones({
  label,
  valor,
  opciones,
  onCambio,
}: {
  label: string;
  valor: string;
  opciones: [string, string][];
  onCambio: (v: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
      {label}
      <span className="flex overflow-hidden rounded border border-[var(--border)]">
        {opciones.map(([clave, texto]) => (
          <button
            key={clave}
            type="button"
            onClick={() => onCambio(clave)}
            aria-pressed={clave === valor}
            className={`px-2.5 py-1 ${
              clave === valor
                ? "bg-[var(--accent)] text-white"
                : "bg-[var(--surface)] text-[var(--text)]"
            }`}
          >
            {texto}
          </button>
        ))}
      </span>
    </label>
  );
}
