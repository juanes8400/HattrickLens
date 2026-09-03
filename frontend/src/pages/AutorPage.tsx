import { Panel } from "../components/Panels";
import autor from "../assets/autor.svg";

/** Quién hay detrás de esto, y qué ha escrito.
 *
 *  2026-09-02, pedido del usuario. La aplicación explica de dónde sale cada
 *  número --para eso está Transparencia-- y no decía de dónde sale ella. En
 *  una herramienta hecha por una persona para una comunidad pequeña, eso no
 *  es vanidad: es a quién escribirle cuando algo no cuadra.
 *
 *  Va abajo del todo en el menú y sin datos del club, porque es lo único de
 *  la aplicación que no depende de haber sincronizado nada.
 */

/** Lo publicado, de lo más reciente a lo más antiguo.
 *
 *  Los enlaces se sacaron del perfil público del autor y NO se escribieron de
 *  memoria: inventar la dirección de un artículo es la clase de error que
 *  nadie revisa y que deja un enlace roto para siempre. Dos títulos se
 *  verificaron además por búsqueda exacta, y los dos salen firmados con su
 *  nombre.
 */
const ARTICULOS: { titulo: string; fecha: string; url: string }[] = [
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
  { donde: "LinkedIn", url: "https://www.linkedin.com/in/juandelacalle/" },
  { donde: "Medium", url: "https://juandelacalle.medium.com" },
  { donde: "Kaggle", url: "https://www.kaggle.com/juandelacalle" },
];

export function AutorPage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Autor</h1>
        <p className="text-sm text-[var(--muted)]">
          Quién hace HT Lens, y qué ha escrito.
        </p>
      </header>

      <Panel title="Juan Esteban de la Calle" meta="Pulgas Arrechas · Colombia">
        <div className="flex flex-col gap-5 p-4 sm:flex-row sm:items-start">
          {/* El retrato no se encoge ni estira: es un dibujo con contorno, y
              deformarlo se nota mucho más que en una fotografía. */}
          <img
            src={autor}
            alt="Retrato dibujado de Juan Esteban de la Calle"
            width={112}
            height={112}
            className="h-28 w-28 shrink-0 self-center sm:self-start"
          />
          <div className="prosa space-y-3 text-sm leading-relaxed">
            <p>
              HT Lens nació de una hoja de cálculo que se hizo demasiado grande.
              Es una herramienta personal que mira los datos de tu propio club y
              saca de ellos lo que Hattrick no enseña: cuántas semanas le faltan
              a un jugador para subir, qué habilidad conviene entrenar en la
              cantera, qué te dejó de verdad cada traspaso.
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

      <Panel title="Lo que ha publicado" meta={`${ARTICULOS.length} artículos`}>
        <ul className="divide-y divide-[var(--border)]">
          {ARTICULOS.map((a) => (
            <li key={a.url} className="px-4 py-3">
              <a
                href={a.url}
                target="_blank"
                rel="noreferrer"
                data-track="Autor: artículo"
                className="text-sm font-medium hover:text-[var(--accent)] hover:underline"
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
