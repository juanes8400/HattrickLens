import { ApoyarProyecto, MensajeDeApoyo } from "../components/ApoyarProyecto";
import { ESCUDO, ImagenOpcional } from "../components/ImagenOpcional";
import { Panel } from "../components/Panels";
import { hayApoyo } from "../config/apoyo";
import autor from "../assets/autor.jpg";

/** Quién hay detrás de esto, y qué ha publicado.
 *
 *  2026-09-02, pedido del usuario. La aplicación explica de dónde sale cada
 *  número --para eso está Transparencia-- y no decía de dónde sale ella. En
 *  una herramienta hecha por una persona para una comunidad pequeña, eso no
 *  es vanidad: es a quién escribirle cuando algo no cuadra.
 *
 *  Va abajo del todo en el menú y sin datos del club, porque es lo único de
 *  la aplicación que no depende de haber sincronizado nada.
 */

type Publicacion = {
  titulo: string;
  donde: string;
  url?: string;
  tipo?: "patente";
};

/** Publicaciones científicas y la patente, de lo más reciente a lo más
 *  antiguo.
 *
 *  La lista la dio el propio autor. De las dos que se pudieron leer se
 *  verificó además que su nombre está en la lista de autores impresa, y de
 *  ahí salen la revista, el año y el DOI. Las otras dos NO llevan año: sus
 *  páginas bloquean la lectura automática y un año a ojo en un currículum es
 *  justo la clase de dato que nadie vuelve a comprobar.
 */
const CIENTIFICAS: Publicacion[] = [
  {
    titulo:
      "Estimation of Dissolved Oxygen Concentration in El Quimbo Hydropower Plant",
    donde:
      "International Journal of Environmental Science and Development · 2026 · 17(1) 1–8 · DOI 10.18178/ijesd.2026.17.1.1558",
    url: "https://www.ijesd.org/show-218-2135-1.html",
  },
  {
    titulo:
      "Sistema, método y medio legible por computador para obtener datos de ingreso asociados a transferencias periódicas",
    donde: "Resolución N.º 38958 · Expediente NC2021/0014429",
    tipo: "patente",
  },
  {
    titulo:
      "Evaluación de la costo-efectividad de un modelo integral de tratamiento ambulatorio en pacientes con síndrome coronario agudo: aplicación de un modelo de Markov probabilístico",
    donde:
      "Revista Panamericana de Salud Pública · 2018 · 42:e10 · DOI 10.26633/RPSP.2018.10",
    url: "https://iris.paho.org/server/api/core/bitstreams/9a24b343-a1a6-4e46-895e-a3c3581ee6ef/content",
  },
  {
    titulo:
      "Modelo de simulación-optimización para el mejoramiento de las políticas de inventario de una empresa del sector plástico en Medellín",
    donde: "Días de la Ciencia Aplicada",
    url: "https://www.researchgate.net/publication/234839938_DIAS_DE_LA_CIENCIA_APLICADA_Modelo_de_simulacion-optimizacion_para_el_mejoramiento_de_las_politicas_de_inventario_de_una_empresa_del_sector_plastico_en_Medellin",
  },
  {
    titulo:
      "Algoritmos constructivos, de búsqueda aleatoria, de búsqueda local, genéticos y genéticos híbridos para la solución de problemas de lot streaming en ambiente flow shop con makespan como función objetivo",
    donde: "Investigación de operaciones · programación de la producción",
    url: "https://www.researchgate.net/publication/234776781_Algoritmos_constructivos_de_busqueda_aleatoria_de_busqueda_local_geneticos_y_geneticos_hibridos_para_la_solucion_de_problemas_de_lot_streaming_en_ambiente_flow_shop_con_makespan_como_funcion_objetivo",
  },
];

/** Divulgación. Va al final y en su propio bloque, por debajo de lo
 *  científico: son cosas distintas y mezclarlas le quitaría peso a lo de
 *  arriba (2026-09-02, pedido del usuario). */
const DIVULGACION: { titulo: string; fecha: string; url: string }[] = [
  {
    titulo: "Why Bayesian Statistics Are Useless",
    fecha: "julio 2024",
    url: "https://juandelacalle.medium.com/why-bayesian-statistics-are-useless-86c0260520c3",
  },
  {
    titulo: "Why Agile Doesn't Work for Data Science — And That's Okay",
    fecha: "octubre 2023",
    url: "https://juandelacalle.medium.com/why-agile-doesnt-work-for-data-science-and-that-s-okay-2367ad289205",
  },
  {
    titulo:
      "I Declare Myself the #1 Enemy of Over/Undersampling, SMOTE and ADASYN",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/i-declare-myself-the-1-enemy-of-over-undersampling-smote-and-adasyn-heres-why-how-i-5889b5073419",
  },
  {
    titulo: "HalvingGridSearch: An Experimental Framework for Fine Tuning",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/halvinggridsearch-an-experimental-framework-for-fine-tuning-how-i-discovered-it-why-i-use-it-11b75a54a771",
  },
  {
    titulo:
      "K-Prototypes & Other Statistical Techniques to Cluster with Categorical and Numerical Features",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/k-prototypes-other-statistical-techniques-to-cluster-with-categorical-and-numerical-features-a-ac809a000316",
  },
  {
    titulo:
      "Drawing the Link: The Connection Between a 2x2 Contingency Table and Logistic Regression",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/drawing-the-link-understanding-the-connection-between-a-2x2-contingency-table-and-logistic-9e993d9d4de0",
  },
  {
    titulo:
      "How and Why I Switched from the ROC Curve to the Precision-Recall Curve",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/how-and-why-i-switched-from-the-roc-curve-to-the-precision-recall-curve-to-analyze-my-imbalanced-6171da91c6b8",
  },
  {
    titulo:
      "Optimizing Classification Models for Marketing with the Expected Profit Curve",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/optimizing-classification-models-for-marketing-with-the-expected-profit-curve-9028c63b9b8b",
  },
  {
    titulo: "10 Hidden Stories Found in a ROC Curve",
    fecha: "julio 2023",
    url: "https://juandelacalle.medium.com/10-hidden-stories-found-in-a-roc-curve-7df2bfb2af4c",
  },
  {
    titulo:
      "A Journey Through the Cosmos of Count Data: Zero-Inflated Poisson and Hurdle Models",
    fecha: "mayo 2023",
    url: "https://juandelacalle.medium.com/a-journey-through-the-cosmos-of-count-data-exploring-zero-inflated-poisson-and-hurdle-models-554cae0237b9",
  },
];

const PERFILES: { donde: string; url: string }[] = [
  // El club va primero: es de lo que trata la aplicación, y quien llega aquí
  // desde Hattrick suele querer ver el equipo antes que el LinkedIn.
  {
    donde: "Pulgas Arrechas",
    url: "https://www.hattrick.org/goto.ashx?path=/Club/?TeamID=537758",
  },
  { donde: "LinkedIn", url: "https://www.linkedin.com/in/juandelacalle/" },
  { donde: "Medium", url: "https://juandelacalle.medium.com" },
  { donde: "Kaggle", url: "https://www.kaggle.com/juandelacalle" },
];

const ENLACE =
  "hover:text-[var(--accent)] hover:underline focus-visible:underline";

/** El apoyo, con sitio para explicarse. En el menú sólo cabe el botón; aquí
 *  cabe decir que la herramienta es gratis y va a seguir siéndolo, que es lo
 *  que evita que un botón de dinero se lea como un peaje. */
function ApoyoPanel() {
  if (!hayApoyo()) return null;
  return (
    <Panel title="Apoyar el proyecto">
      <div className="flex flex-wrap items-center justify-between gap-4 p-4">
        <MensajeDeApoyo />
        <ApoyarProyecto forma="pagina" />
      </div>
    </Panel>
  );
}

export function AutorPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Autor</h1>
        <p className="text-sm text-[var(--muted)]">
          Quién hace HT Lens, y qué ha publicado.
        </p>
      </header>

      {/* El club, en grande y con su escudo. Antes iba de subtítulo del
          panel, en once píxeles y al lado del nombre del autor: en Hattrick
          uno se conoce por su equipo, así que es lo que más se reconoce de
          esta pantalla y era lo más pequeño de ella. */}
      <Panel title="Juan Esteban de la Calle">
        <a
          href="https://www.hattrick.org/goto.ashx?path=/Club/?TeamID=537758"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-4 border-b border-[var(--border)] px-4 py-4 hover:bg-[var(--surface-2)]"
        >
          <ImagenOpcional
            src={ESCUDO}
            alt="Escudo de Pulgas Arrechas"
            width={72}
            height={72}
            className="h-16 w-16 shrink-0 object-contain"
          />
          <span>
            <span className="block text-2xl font-semibold leading-tight">
              Pulgas Arrechas
            </span>
            <span className="block text-sm text-[var(--muted)]">
              V.92 · Colombia
            </span>
          </span>
        </a>
        <div className="flex flex-col gap-5 p-4 sm:flex-row sm:items-start">
          {/* El retrato lo puso el usuario (2026-09-03) y sustituye al que
              estaba dibujado a mano en SVG. Va recortado en círculo, que es
              como se veía el anterior, y con `object-cover` para que un
              recorte no cuadrado nunca lo estire. La imagen se guarda a 384
              píxeles: el original venía a 1254 y pesaba 2 MB para enseñarse
              a 112. */}
          <img
            src={autor}
            alt="Retrato de Juan Esteban de la Calle"
            width={112}
            height={112}
            loading="lazy"
            className="h-28 w-28 shrink-0 self-center rounded-full border border-[var(--border)] object-cover sm:self-start"
          />
          <div className="prosa space-y-3 text-sm leading-relaxed">
            {/* La gracia no es la lista de campos, es lo poco que se
                parecen entre sí. Se cuentan como cuatro cosas concretas
                porque «investigación de operaciones y evaluación económica en
                salud» no le dice nada a nadie, y «el oxígeno de un embalse y
                un infarto» sí. */}
            <p>
              Ingeniero matemático. Ha modelado el oxígeno disuelto de un
              embalse, lo que cuesta y lo que salva tratar a un paciente después
              de un infarto, el inventario de una fábrica de plásticos y el
              orden en que una planta debe sacar sus lotes.
            </p>
            <p>
              Son problemas que no se parecen en nada y se atacan casi igual:
              mirar qué varía de verdad, escribir el modelo y dejarlo
              equivocarse contra los datos hasta que deja de hacerlo. Sobre
              estadística escribe sin mucha diplomacia: tiene un artículo
              titulado «Por qué la estadística bayesiana es inútil» y se declara
              enemigo número uno del SMOTE.
            </p>
            <p>
              HT Lens es esa misma manía aplicada a un club de Hattrick. Empezó
              siendo una hoja de cálculo, se hizo demasiado grande, y acabó
              aquí.
            </p>
            <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--muted)]">
              {PERFILES.map((p) => (
                <li key={p.donde}>
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    data-track={`Autor: ${p.donde}`}
                    className="underline decoration-dotted underline-offset-2 hover:text-[var(--accent)]"
                  >
                    {p.donde}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Panel>

      {/* Aquí y no en el Panel: quien llega a esta pantalla ya quiso saber
          quién hay detrás, así que es el único sitio donde el botón no
          interrumpe a nadie. Sólo sale con la bandera encendida Y con
          enlace. */}
      <ApoyoPanel />

      <Panel
        title="Publicaciones científicas"
        meta={`${CIENTIFICAS.length} referencias`}
      >
        <ul className="divide-y divide-[var(--border)]">
          {CIENTIFICAS.map((p) => (
            <li key={p.titulo} className="px-4 py-3">
              <div className="flex flex-wrap items-baseline gap-x-2">
                {p.url ? (
                  <a
                    href={p.url}
                    target="_blank"
                    rel="noreferrer"
                    data-track="Autor: publicación científica"
                    className={`text-sm font-medium ${ENLACE}`}
                  >
                    {p.titulo}
                  </a>
                ) : (
                  <span className="text-sm font-medium">{p.titulo}</span>
                )}
                {p.tipo === "patente" && (
                  <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[10px] uppercase tracking-wide text-[var(--muted)]">
                    Patente
                  </span>
                )}
              </div>
              <div className="mt-0.5 text-xs text-[var(--muted)]">
                {p.donde}
              </div>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Divulgación" meta={`${DIVULGACION.length} artículos`}>
        <ul className="divide-y divide-[var(--border)]">
          {DIVULGACION.map((a) => (
            <li key={a.url} className="px-4 py-3">
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer"
                data-track="Autor: divulgación"
                className={`text-sm font-medium ${ENLACE}`}
              >
                {a.titulo}
              </a>
              <div className="mt-0.5 text-xs text-[var(--muted)]">
                {a.fecha} · Medium
              </div>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
