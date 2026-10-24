/** El mapa que alumbra con cada clic.
 *
 *  2026-10-23, pedido del usuario: «otro mapa que alumbre cada vez que un
 *  usuario de ese país dé un clic».
 *
 *  SE PUEDE, Y DE DOS MANERAS QUE NO SON LO MISMO. Las dos están aquí porque
 *  cada una falla donde la otra sirve:
 *
 *    EN VIVO · sondea el registro cada pocos segundos y enciende lo que haya
 *      llegado desde la última vuelta. Es lo que se pidió literalmente, y con
 *      doce usuarios va a estar apagado casi todo el tiempo: un destello cada
 *      tanto, y tardes enteras en negro. No es un fallo, es el tráfico que hay,
 *      y la pantalla lo dice en vez de dejar creer que se rompió.
 *
 *    REPETICIÓN · recorre los clics YA GUARDADOS del plazo elegido, en orden y
 *      con su propio ritmo comprimido. Siempre tiene algo que enseñar, y es la
 *      única de las dos que deja ver la forma de un día: las rachas salen como
 *      rachas y los huecos como huecos.
 *
 *  SÓLO EXISTE MIENTRAS SE MIRA. Hasta el 2026-10-24 traía su propio botón de
 *  encendido, porque montarlo cuesta un mapa del mundo entero --otras ciento
 *  ochenta siluetas en el DOM-- y un sondeo cada cinco segundos. Desde que la
 *  pantalla elige UN mapa con un solo selector, eso lo da el montaje: este
 *  componente no existe mientras no se escoja, y al escoger otra vista se
 *  desmonta y se lleva el sondeo con él. Un interruptor menos para la misma
 *  garantía.
 *
 *  NO HAY NADA NUEVO QUE MEDIR. Sale del mismo registro de siempre y del mismo
 *  país de la liga del club; aquí no se pregunta nada ni se mira de dónde viene
 *  ninguna conexión.
 */
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { useQuery } from "@tanstack/react-query";

import {
  ALTO_DEL_MUNDO,
  ANCHO_DEL_MUNDO,
  CENTROS_DE_PAIS,
  PAISES_DEL_MUNDO,
} from "../data/paisesDelMundo";
import { CountryFlag } from "./CountryFlag";
import { Panel } from "./Panels";
import { api } from "../services/api";
import { creaDestellos } from "../utils/destellos";
import { nombreDePais } from "../utils/countryCodes";
import { tx } from "../i18n/tx";

/** Cuánto dura un destello. Por debajo de medio segundo no se ve llegar; por
 *  encima de dos, dos clics seguidos del mismo país se leen como uno largo. */
const DURACION_DEL_DESTELLO = 1100;

/** Cada cuánto se pregunta por lo nuevo, en vivo. Cinco segundos es el
 *  compromiso: por debajo son muchas vueltas para un tráfico que no las
 *  llena, y por encima el destello deja de sentirse como «ahora». */
const CADA_CUANTO_SE_PREGUNTA = 5_000;

/** Cuántos clics se traen de una. En vivo es un margen de seguridad --si una
 *  vuelta tarda, lo de en medio no se pierde--; en repetición es cuánto dura
 *  la película. */
const CUANTOS_EN_VIVO = 60;
const CUANTOS_EN_REPETICION = 400;

/** Lo que se quiere que dure una repetición entera, y el silencio más largo
 *  que se tolera dentro. El ritmo real se comprime a esa duración, pero un
 *  hueco de nueve horas no puede convertirse en nueve segundos de nada: se
 *  recorta, y por eso la repetición enseña el ORDEN y las rachas, no el
 *  reloj. */
const LO_QUE_DURA_UNA_REPETICION = 25_000;
const SILENCIO_MAXIMO = 700;
const SILENCIO_MINIMO = 30;

export interface PaisDeCadaUno {
  code: string;
  name: string;
}

export function MapaEnVivo({
  paisDe,
  dias,
  excluirme,
  selector,
}: {
  /** El país de cada persona, por su id de fila. Viene de `byUser`, que es
   *  quien ya lo trae; pedirlo otra vez sería una consulta para nada. */
  paisDe: Record<number, PaisDeCadaUno>;
  dias: number;
  excluirme: boolean;
  /** El selector de vista, para la cabecera del panel. Lo pasa la pantalla:
   *  es el mismo que elige entre este mapa y el de magnitud. */
  selector?: React.ReactNode;
}) {

  // Los destellos viven FUERA de React, en un almacén con su propio reloj, y
  // esta pantalla se suscribe. No es un rodeo: el efecto que mira si llegaron
  // clics nuevos tiene que encender países, y hacerlo con `setState` desde
  // dentro de un efecto es una cascada de renders --el linter lo rechaza, y
  // tiene razón--. Empujar un suceso a un almacén de fuera y leerlo con
  // `useSyncExternalStore` es el caso que esa API existe para cubrir. Mismo
  // patrón que `config/consentimiento.ts`.
  const destellos = useMemo(() => creaDestellos(DURACION_DEL_DESTELLO), []);
  const { encendidos, vistos, ultimo } = useSyncExternalStore(
    destellos.subscribe,
    destellos.getSnapshot,
    destellos.getSnapshot,
  );

  // La marca de agua: el id más alto ya enseñado. Es un ref y no estado porque
  // se lee y escribe dentro del efecto que reparte los destellos, y como
  // estado provocaría una vuelta más por cada tanda.
  const hastaAqui = useRef<number>(0);

  // El contador de cortes. Una repetición dura veinticinco segundos dentro de
  // un bucle con esperas, y nada de lo que pase fuera --pulsar «Apagar»,
  // cambiar de pestaña, salir de la pantalla-- puede interrumpir un `await`.
  // Sin esto, apagar el mapa lo dejaba destellando hasta que la película
  // acabara sola, y salir de la pantalla acababa escribiendo estado de un
  // componente que ya no existe. Desmontar y empezar otra película suben el
  // número; la que corre se queda con el suyo y se calla en cuanto deja de
  // coincidir.
  const corte = useRef(0);

  /** Apaga todo y corta lo que estuviera en marcha. */
  const apagarTodo = useCallback(() => {
    corte.current += 1;
    destellos.apagarTodo();
  }, [destellos]);

  // Al desmontar sólo se sueltan los relojes, sin avisar: tocar el almacén
  // cuando ya nadie lo lee no hace falta, y corta la repetición igual.
  useEffect(() => {
    const soltar = destellos.soltarRelojes;
    return () => {
      corte.current += 1;
      soltar();
    };
  }, [destellos]);

  // ── En vivo ──────────────────────────────────────────────────────────────

  const { data: nuevos, isFetching } = useQuery({
    queryKey: ["uso-en-vivo", excluirme],
    queryFn: () =>
      api.usageLog({
        // Un día, no el plazo de la pantalla: «en vivo» es ahora, y pedir
        // noventa días para quedarse con los diez últimos es hacer trabajar a
        // la base para nada en cada vuelta.
        dias: 1,
        tipo: "click",
        cuantas: CUANTOS_EN_VIVO,
        excluirme,
      }),
    refetchInterval: CADA_CUANTO_SE_PREGUNTA,
    // Sin esto el sondeo sigue con la pestaña en segundo plano, y al volver
    // caerían de golpe todos los destellos de un rato en el que nadie miraba.
    refetchIntervalInBackground: false,
  });

  useEffect(() => {
    if (!nuevos) return;
    // El registro viene del más nuevo al más viejo; para encender en el orden
    // en que pasaron hay que recorrerlo al revés.
    const filas = [...nuevos.rows].reverse();
    const tope = filas.reduce((max, f) => Math.max(max, f.id), 0);

    // LA PRIMERA TANDA NO SE ENCIENDE. Son los sesenta clics anteriores a
    // encender el mapa: soltarlos todos de golpe sería un fuego artificial que
    // no ha pasado ahora, y justo lo contrario de lo que este mapa afirma.
    if (hastaAqui.current === 0) {
      hastaAqui.current = tope;
      return;
    }
    for (const f of filas) {
      if (f.id <= hastaAqui.current) continue;
      const pais = paisDe[f.userId];
      if (!pais?.code) continue;
      destellos.encender(pais.code, f.at);
    }
    hastaAqui.current = Math.max(hastaAqui.current, tope);
  }, [nuevos, paisDe, destellos]);

  // ── Repetición ───────────────────────────────────────────────────────────

  const [repitiendo, setRepitiendo] = useState(false);

  const repetir = useCallback(async () => {
    apagarTodo();
    setRepitiendo(true);
    // Se toma DESPUÉS de `apagarTodo`, que es quien lo sube: así este número
    // es el de esta película y no el de la anterior.
    const mio = corte.current;
    try {
      const log = await api.usageLog({
        dias,
        tipo: "click",
        cuantas: CUANTOS_EN_REPETICION,
        excluirme,
      });
      // Entre pedir y recibir pueden haber pasado cosas: que lo apagaran, o
      // que pulsaran «Repetición» otra vez. En los dos casos esta película ya
      // no es la que se está viendo.
      if (mio !== corte.current) return;

      const filas = [...log.rows]
        .reverse()
        .filter((f) => paisDe[f.userId]?.code);
      if (filas.length === 0) return;

      // El ritmo real, comprimido. `factor` lleva el tramo entero a la
      // duración que se quiere; el recorte de cada hueco evita que una noche
      // sin nadie se coma la película.
      const t = filas.map((f) => new Date(f.at).getTime());
      const tramo = Math.max(1, (t.at(-1) ?? 0) - (t[0] ?? 0));
      const factor = LO_QUE_DURA_UNA_REPETICION / tramo;

      for (let i = 0; i < filas.length; i++) {
        if (mio !== corte.current) return;
        const fila = filas[i];
        const pais = fila ? paisDe[fila.userId] : undefined;
        if (!fila || !pais?.code) continue;
        destellos.encender(pais.code, fila.at);
        const hueco = (t[i + 1] ?? t[i] ?? 0) - (t[i] ?? 0);
        await new Promise((listo) =>
          setTimeout(
            listo,
            Math.min(SILENCIO_MAXIMO, Math.max(SILENCIO_MINIMO, hueco * factor)),
          ),
        );
      }
    } finally {
      // Sólo si sigue siendo la película de este corte: si otra empezó
      // mientras, apagarle el botón sería apagárselo a ella.
      if (mio === corte.current) setRepitiendo(false);
    }
  }, [apagarTodo, dias, excluirme, paisDe, destellos]);

  // ── El dibujo ────────────────────────────────────────────────────────────

  const cuantosConPais = Object.values(paisDe).filter((p) => p.code).length;

  return (
    <Panel
      title={tx("El mapa que alumbra")}
      meta={
        vistos === 1 ? tx("1 clic") : tx("{{v0}} clics", { v0: vistos })
      }
      ayuda={tx(
        "Cada destello es un clic de alguien de ese país. En vivo sondea lo nuevo cada cinco segundos; en repetición recorre los clics ya guardados del plazo elegido, con su ritmo comprimido. No se mide nada nuevo: sale del mismo registro y del mismo país de la liga del club.",
      )}
      acciones={
        // El selector de vista lo pone la pantalla; «Repetición» es de este
        // mapa y va al lado, porque es una ACCIÓN --reproduce una vez y
        // termina-- y no una tercera forma de mirar.
        <div className="flex items-center gap-1">
          {selector}
          <button
            onClick={() => void repetir()}
            disabled={repitiendo}
            data-track="Uso: mapa repeticion"
            className="rounded-md border border-[var(--border)] px-2 py-1 text-xs text-[var(--muted)] disabled:opacity-50"
          >
            {repitiendo ? tx("Reproduciendo…") : tx("Repetición")}
          </button>
        </div>
      }
    >
      {/* Sin país de nadie no hay dónde alumbrar, y un mapa entero en negro
          sin explicación se lee como una avería. */}
      {cuantosConPais === 0 ? (
        <p className="p-4 text-sm text-[var(--muted)]">
          {tx(
            "Todavía no consta el país de nadie, así que no habría dónde alumbrar: sale de la liga del club y aparece en cuanto alguien sincroniza.",
          )}
        </p>
      ) : (
        <div className="p-4">
          <div className="overflow-x-auto">
            <svg
              viewBox={`0 0 ${ANCHO_DEL_MUNDO} ${ALTO_DEL_MUNDO}`}
              role="img"
              aria-label={tx(
                "Mapa del mundo que destella en el país de cada clic",
              )}
              className="block h-auto w-full min-w-[520px]"
            >
              {/* El fondo va apagado a propósito: un mapa ya coloreado por
                  magnitud no deja ver un destello encima. El de arriba
                  contesta «cuánta gente»; éste, «ahora mismo, dónde». */}
              {PAISES_DEL_MUNDO.map((pais, i) => {
                const vivo = pais.code ? encendidos[pais.code] : undefined;
                return (
                  <path
                    key={`${pais.code}-${i}`}
                    d={pais.d}
                    fill={vivo ? "var(--accent)" : "var(--surface-2)"}
                    stroke="var(--surface)"
                    strokeWidth={0.4}
                    style={{
                      transition: vivo
                        ? "none"
                        : `fill ${DURACION_DEL_DESTELLO}ms ease-out`,
                    }}
                  >
                    {vivo && (
                      <title>{`${nombreDePais(pais.code, pais.name) ?? pais.name}`}</title>
                    )}
                  </path>
                );
              })}

              {/* El anillo. Hace falta por lo mismo que los puntos del otro
                  mapa: a esta escala veinte de los países de Hattrick no
                  llegan a un píxel, y un destello en una silueta invisible no
                  es un destello. */}
              {Object.entries(encendidos).map(([code]) => {
                const centro = CENTROS_DE_PAIS[code];
                if (!centro) return null;
                return (
                  <g key={code}>
                    <circle
                      cx={centro[0]}
                      cy={centro[1]}
                      r={4}
                      fill="var(--accent)"
                      stroke="var(--surface)"
                      strokeWidth={1.5}
                    />
                    {/* `motion-safe`: quien pidió menos movimiento se queda
                        con el cambio de color, que ya dice lo mismo. */}
                    <circle
                      cx={centro[0]}
                      cy={centro[1]}
                      r={4}
                      fill="none"
                      stroke="var(--accent)"
                      strokeWidth={1.5}
                      className="motion-safe:animate-ping"
                      style={{ transformOrigin: `${centro[0]}px ${centro[1]}px` }}
                    />
                  </g>
                );
              })}
            </svg>
          </div>

          {/* La fila de estado. Un mapa en negro tiene que poder distinguirse
              de un mapa roto, y eso sólo lo dice el texto. */}
          <p className="mt-3 min-h-[1.5rem] text-sm">
            {ultimo ? (
              <span className="inline-flex items-center gap-2">
                <CountryFlag
                  code={ultimo.code}
                  country={nombreDePais(ultimo.code, null) ?? ultimo.code}
                />
                <span className="font-medium">
                  {nombreDePais(ultimo.code, null) ?? ultimo.code.toUpperCase()}
                </span>
                <span className="text-xs tabular-nums text-[var(--muted)]">
                  {new Date(ultimo.cuando).toLocaleTimeString()}
                </span>
              </span>
            ) : (
              <span className="text-xs text-[var(--muted)]">
                {isFetching
                  ? tx("Escuchando…")
                  : tx(
                      "Sin clics nuevos todavía. Con doce personas, esto pasa la mayor parte del tiempo.",
                    )}
              </span>
            )}
          </p>
        </div>
      )}
    </Panel>
  );
}
