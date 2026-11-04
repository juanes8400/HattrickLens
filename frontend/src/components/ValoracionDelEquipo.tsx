import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ErrorState, Loading, Panel, SinDatos } from "./Panels";
import { decimal, money, number } from "../hooks/useFormat";
import { terminoOficial } from "../i18n/glosario";
import { nombreDeHabilidad } from "../utils/abreviaturas";
import { usePreciosComparables } from "../hooks/useTeam";
import type { PrecioDeUnJugador } from "../services/api";
import { tx } from "../i18n/tx";

/** Lo que vale la plantilla, jugador a jugador y en total.
 *
 *  2026-11-04, pedido del usuario: «un Segment Toggle para Valoración del
 *  Equipo, con el valor de cada jugador y del total de la plantilla; esto se
 *  debe comunicar con Transferencias / Mi Plantilla».
 *
 *  SE COMUNICA REUSANDO LA MISMA FUENTE, no copiando la cuenta. Llama a
 *  `usePreciosComparables`, que es el mismísimo `/precios-comparables` que pide
 *  «Mi plantilla», y la clave de react-query es la misma, así que las dos
 *  pantallas comparten la respuesta en caché: una sola petición y, sobre todo,
 *  UN SOLO NÚMERO. Calcularlo aquí otra vez sería tener dos definiciones del
 *  mismo valor, que es el error que en este proyecto ya costó una cifra en la
 *  comisión del agente y otra en la flor.
 *
 *  LO QUE LA SUMA NO ES. No es una tasación: es lo que ha costado gente
 *  parecida. Y no suma a todos, porque a quien no tiene ni una venta cerrada
 *  parecida su precio le llega `null` --nunca cero, que diría que no vale
 *  nada--, así que el total declara cuántos cuenta de cuántos. Sin eso, una
 *  plantilla con la mitad sin medir enseñaría la mitad de su valor como si
 *  fuera el valor.
 */
/** Desde qué peso sobre el total se etiqueta a un jugador con su porcentaje.
 *
 *  Ver el comentario en `BarraDeJugador`: con una plantilla de veintisiete, la
 *  mayoría son un 1 % y el número sobra. */
const PESO_QUE_SE_ETIQUETA = 5;

/** Un jugador que SÍ tiene precio, con el `null` ya descartado por el tipo. */
export type ConPrecio = PrecioDeUnJugador & { media: number };

/** La cuenta entera, aparte de la pintura, para poder fijarla con pruebas.
 *
 *  Lo que hay que no perder de vista está aquí dentro: quién entra en la suma
 *  (sólo los que tienen precio), de qué plantilla hablan el suelo y el techo
 *  (de la misma, la de los que cuentan) y que la mediana de un número par de
 *  jugadores es el promedio de los dos de en medio. Los tres se equivocan sin
 *  hacer ruido: el total sigue saliendo, sólo que mal.
 */
export function resumenDeLaValoracion(
  jugadores: PrecioDeUnJugador[],
  sinMedir = 0,
) {
  const conPrecio = jugadores
    .filter((j): j is ConPrecio => j.media != null)
    .sort((a, b) => b.media - a.media || a.nombre.localeCompare(b.nombre));
  const total = conPrecio.reduce((t, j) => t + j.media, 0);
  // El suelo y el techo se suman SÓLO de quienes entran en el total, para que
  // la banda y la cifra hablen de la misma plantilla.
  const suelo = conPrecio.reduce((t, j) => t + (j.minimo ?? j.media), 0);
  const techo = conPrecio.reduce((t, j) => t + (j.maximo ?? j.media), 0);
  const medias = conPrecio.map((j) => j.media);
  const mitad = Math.floor(medias.length / 2);
  const mediana = medias.length
    ? medias.length % 2
      ? medias[mitad]!
      : Math.round(((medias[mitad - 1] ?? 0) + (medias[mitad] ?? 0)) / 2)
    : null;
  const sinPrecio = jugadores.filter((j) => j.media == null);
  return {
    conPrecio,
    sinPrecio,
    sinMedir,
    // LA PLANTILLA ENTERA, no las filas que llegaron. Es la diferencia entre
    // decir «de 23 de 27» y decir la verdad cuando tres no se han podido
    // medir: entonces son 30 y el que mira tiene derecho a saberlo.
    plantilla: conPrecio.length + sinPrecio.length + sinMedir,
    total,
    suelo,
    techo,
    mediana,
    tope: medias[0] ?? 0,
  };
}

export function ValoracionDelEquipo({
  activa,
  caja,
}: {
  activa: boolean;
  /** La caja de hoy, para poder decir la valoración EN VECES LA CAJA.
   *
   *  Es la razón de que esta sección viva en Economía y no en Transferencias:
   *  trece millones en jugadores no significan lo mismo con dos millones en
   *  el banco que con veinte. La cifra sola no lo dice; esta división sí. */
  caja: number;
}) {
  const { data, isLoading, isError, error } = usePreciosComparables({
    enabled: activa,
  });

  const cuentas = useMemo(
    () => resumenDeLaValoracion(data?.jugadores ?? [], data?.sinMedir ?? 0),
    [data],
  );

  if (!activa) return null;
  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;

  const moneda = data.moneda;
  const {
    conPrecio,
    sinPrecio,
    sinMedir,
    plantilla,
    total,
    suelo,
    techo,
    mediana,
    tope,
  } = cuentas;
  const contados = conPrecio.length;

  return (
    <Panel
      title={tx("Valoración del equipo")}
      meta={
        <Link
          to="/transfers/balance"
          className="text-xs text-[var(--accent)] hover:underline"
        >
          {tx("ver la tabla completa")}
        </Link>
      }
      ayuda={tx(
        "Lo que valdría vender hoy toda la plantilla, jugador a jugador. Sale del mismo sitio que la tabla de Transferencias / Mi plantilla --lo que ha costado gente parecida-- así que las dos pantallas dicen el mismo número. No es una tasación y no cuesta ninguna consulta a Hattrick.",
      )}
    >
      {contados === 0 ? (
        <p className="prosa px-4 py-6 text-sm text-[var(--muted)]">
          {tx(
            "Todavía no hay ninguna venta cerrada parecida a ningún jugador tuyo, así que no hay nada que sumar.",
          )}
        </p>
      ) : (
        <div className="space-y-5 px-4 py-4">
          {/* LA CIFRA, y debajo de qué está hecha. El orden importa: primero
              el número que se venía a ver, y pegado a él cuántos cuenta. */}
          <div className="space-y-2">
            <div className="text-3xl font-semibold tabular-nums tracking-tight">
              {money(total, moneda)}
            </div>
            <p className="text-xs text-[var(--muted)]">
              {tx("suma de {{v0}} de {{v1}} jugadores con ventas parecidas", {
                v0: number(contados),
                v1: number(plantilla),
              })}
            </p>
            {sinMedir > 0 && (
              <p className="text-xs text-[var(--muted)]">
                {tx(
                  "a {{v0}} de la plantilla no se les ha podido medir todavía",
                  { v0: number(sinMedir) },
                )}
              </p>
            )}
            {caja > 0 && (
              <p className="text-xs text-[var(--muted)]">
                {tx("{{v0}} veces tu caja de ahora, que son {{v1}}", {
                  v0: decimal(total / caja, 1),
                  v1: money(caja, moneda),
                })}
              </p>
            )}
            <BandaDelTotal
              suelo={suelo}
              techo={techo}
              total={total}
              moneda={moneda}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-3 [&>*]:min-w-0">
            <Dato
              etiqueta={tx("El más valioso")}
              valor={money(tope, moneda)}
              pie={conPrecio[0]?.nombre ?? ""}
            />
            <Dato
              etiqueta={tx("Jugador mediano")}
              valor={mediana == null ? "—" : money(mediana, moneda)}
              pie={tx("la mitad vale más y la mitad menos")}
            />
            <Dato
              etiqueta={tx("Sin precio todavía")}
              valor={number(sinPrecio.length)}
              pie={
                sinPrecio.length
                  ? tx("no entran en la suma")
                  : tx("todos tienen comparables")
              }
            />
          </div>

          <ul className="space-y-1.5">
            {conPrecio.map((j) => (
              <BarraDeJugador
                key={j.htPlayerId}
                jugador={j}
                tope={tope}
                total={total}
                moneda={moneda}
              />
            ))}
            {sinPrecio.map((j) => (
              <li
                key={j.htPlayerId}
                className="flex items-baseline justify-between gap-3 py-0.5 text-xs text-[var(--muted)]"
              >
                <span className="truncate">{j.nombre}</span>
                <span className="shrink-0">{tx("sin ventas parecidas")}</span>
              </li>
            ))}
          </ul>

          <p className="prosa text-[11px] leading-relaxed text-[var(--muted)]">
            {tx(
              "Las subastas abiertas se enseñan en la ficha pero no promedian, así que esta suma sólo cuenta ventas cerradas. Y es lo que pagó el mercado por gente parecida, no lo que alguien te vaya a pagar a ti.",
            )}
          </p>
        </div>
      )}
    </Panel>
  );
}

/** El total dentro de su horquilla: del mínimo de los comparables al máximo.
 *
 *  Es la parte que evita leer la cifra como una tasación. Si vendieras a todos
 *  al precio más bajo que ha pagado alguien por uno parecido, saldría el suelo;
 *  al más alto, el techo. La media está en medio y casi nunca centrada, y eso
 *  también dice algo. */
function BandaDelTotal({
  suelo,
  techo,
  total,
  moneda,
}: {
  suelo: number;
  techo: number;
  total: number;
  moneda: string;
}) {
  const ancho = techo - suelo;
  const donde = ancho > 0 ? ((total - suelo) / ancho) * 100 : 50;
  return (
    <div className="pt-1">
      <div
        className="relative h-1.5 rounded-full bg-[var(--surface-2)]"
        aria-hidden="true"
      >
        <div
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded-full bg-[var(--accent)]"
          style={{ left: `calc(${donde.toFixed(1)}% - 1px)` }}
        />
      </div>
      <div className="mt-1 flex items-baseline justify-between gap-3 text-[11px] text-[var(--muted)]">
        <span className="whitespace-nowrap tabular-nums">
          {money(suelo, moneda)}
        </span>
        {/* El rótulo se cae en pantalla estrecha: ahí no cabe sin partir las
            dos cifras en dos líneas cada una, y las cifras son lo que hay que
            leer. Lo que dice la banda queda en la ayuda del panel. */}
        <span className="hidden truncate sm:inline">
          {tx("del mínimo al máximo de sus comparables")}
        </span>
        <span className="whitespace-nowrap tabular-nums">
          {money(techo, moneda)}
        </span>
      </div>
    </div>
  );
}

/** Una cifra de apoyo, sin la caja de `Kpi`: aquí van dentro del panel y tres
 *  tarjetas con borde dentro de otra tarjeta con borde es una caja de más. */
function Dato({
  etiqueta,
  valor,
  pie,
}: {
  etiqueta: string;
  valor: string;
  pie: string;
}) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-[var(--muted)]">
        {etiqueta}
      </div>
      <div className="mt-0.5 text-lg font-medium tabular-nums">{valor}</div>
      <div className="truncate text-[11px] text-[var(--muted)]">{pie}</div>
    </div>
  );
}

/** «Portería 15 · 28 años», con el nombre de la habilidad del glosario.
 *
 *  Se queda con la PRIMERA del perfil, que es la más alta: el perfil llega ya
 *  ordenado desde el servidor y las otras dos sobran aquí --la ficha las tiene
 *  todas-- porque lo que esta línea tiene que contestar es «¿y éste quién es?»
 *  sin robarle sitio a la barra. */
function quienEs(jugador: PrecioDeUnJugador): string {
  const rasgo = jugador.perfil[0];
  const edad = tx("{{v0}} años", { v0: number(jugador.edad) });
  if (!rasgo) return edad;
  // El glosario OFICIAL manda; el respaldo en español sale de
  // `abreviaturas`, que es el único sitio que ya los tiene traducidos.
  const nombre = terminoOficial(
    "habilidades",
    rasgo.habilidad,
    nombreDeHabilidad(rasgo.habilidad),
  );
  return `${nombre} ${rasgo.nivel} · ${edad}`;
}

/** Un jugador: su nombre, su barra y su cifra.
 *
 *  La barra va contra el MÁS VALIOSO y no contra el total, porque lo que se
 *  compara aquí es a los jugadores entre sí; el peso sobre el total va en
 *  cifras al lado, que es donde se lee sin estimar longitudes. */
function BarraDeJugador({
  jugador,
  tope,
  total,
  moneda,
}: {
  jugador: PrecioDeUnJugador & { media: number };
  tope: number;
  total: number;
  moneda: string;
}) {
  const parte = tope > 0 ? (jugador.media / tope) * 100 : 0;
  const peso = total > 0 ? (jugador.media / total) * 100 : 0;
  return (
    // EN ESTRECHO, DOS FILAS Y NO TRES: nombre y cifra en la misma línea y la
    // barra debajo, cruzando las dos columnas. Con la barra en medio del flujo
    // cada jugador ocupaba tres renglones y doce jugadores no cabían en una
    // pantalla de teléfono. La colocación es explícita para poder mantener el
    // orden del DOM --nombre, barra, cifra-- en los dos tamaños.
    <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 sm:grid-cols-[11rem_minmax(0,1fr)_auto]">
      {/* EL NOMBRE Y QUIÉN ES. Una lista de doce nombres con doce barras no
          dice por qué el tercero vale la mitad que el primero; su mejor
          habilidad y su edad sí, y caben en la misma celda sin añadir un
          renglón a la fila. El nombre de la habilidad sale del glosario
          OFICIAL de Hattrick, no de una traducción nuestra. */}
      <span className="col-start-1 row-start-1 min-w-0">
        <span className="block truncate text-xs" title={jugador.nombre}>
          {jugador.nombre}
        </span>
        <span className="block truncate text-[10px] leading-tight text-[var(--muted)]">
          {quienEs(jugador)}
        </span>
      </span>
      <span
        className="col-span-2 col-start-1 row-start-2 h-1.5 rounded-full bg-[var(--surface-2)] sm:col-span-1 sm:col-start-2 sm:row-start-1"
        aria-hidden="true"
      >
        <span
          className="block h-1.5 rounded-full bg-[var(--accent)] transition-[width] duration-300"
          style={{ width: `${Math.max(parte, 1.5).toFixed(1)}%` }}
        />
      </span>
      <span className="col-start-2 row-start-1 shrink-0 text-right text-xs tabular-nums sm:col-start-3">
        {money(jugador.media, moneda)}
        {/* EL PESO, SÓLO EN QUIEN PESA. Con doce jugadores el porcentaje de
            cada uno dice algo; con veintisiete, veinte de ellos son un 1 % y lo
            único que hacen es ensuciar la columna. Se etiqueta a quien llega al
            5 %, que es la regla de siempre --etiquetar selectivamente, no en
            cada punto-- y se autoajusta al tamaño de la plantilla. El hueco se
            reserva igual para que la cifra no baile. */}
        <span className="ml-2 inline-block w-8 text-right text-[11px] text-[var(--muted)]">
          {peso >= PESO_QUE_SE_ETIQUETA ? `${peso.toFixed(0)}%` : ""}
        </span>
      </span>
    </li>
  );
}
