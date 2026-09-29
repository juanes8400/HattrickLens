import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { tx } from "../i18n/tx";
import type { Articulo } from "./wiki/contenido";
import { ARTICULOS, GRUPOS } from "./wiki/contenido";

/**
 * Wiki (2026-09-14, pedido del usuario): la documentación de todo HT Lens,
 * escrita desde la pantalla.
 *
 * Aquí sólo está la pantalla: el índice, el buscador y cómo se pinta cada
 * artículo. El contenido es dato y vive en `wiki/contenido.ts`.
 */

/** Sin tildes ni mayúsculas, para que «posicion» encuentre «Posición». */
function normalizar(texto: string) {
  return texto.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}

function textoDe(a: Articulo) {
  return normalizar(
    [
      a.titulo,
      a.resumen,
      ...a.secciones.flatMap((s) => [
        s.titulo,
        ...(s.texto ?? []),
        ...(s.puntos ?? []),
        s.formula ?? "",
      ]),
    ].join(" "),
  );
}

export function WikiPage() {
  const [busqueda, setBusqueda] = useState("");
  const indice = useMemo(
    () => ARTICULOS.map((a) => ({ articulo: a, texto: textoDe(a) })),
    [],
  );
  const terminos = normalizar(busqueda).split(/\s+/).filter(Boolean);
  const visibles = indice
    .filter(({ texto }) => terminos.every((t) => texto.includes(t)))
    .map(({ articulo }) => articulo);

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">{tx("Wiki")}</h1>
        <p className="text-sm text-[var(--muted)]">
          {tx(
            "Todo HT Lens explicado: qué responde cada pantalla, cómo se calcula, cómo se lee y hasta dónde vale",
          )}
        </p>
      </header>

      <input
        type="search"
        value={busqueda}
        onChange={(e) => setBusqueda(e.target.value)}
        placeholder={tx(
          "Buscar en la Wiki: cuello de botella, HTMS, ampliar estadio…",
        )}
        aria-label={tx("Buscar en la Wiki")}
        className="w-full max-w-xl rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
      />

      <div className="grid gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav
          aria-label={tx("Índice de la Wiki")}
          className="self-start rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-sm lg:sticky lg:top-4"
        >
          {GRUPOS.map((grupo) => {
            const delGrupo = visibles.filter((a) => a.grupo === grupo.clave);
            if (delGrupo.length === 0) return null;
            return (
              <div key={grupo.clave} className="mb-3 last:mb-0">
                <div className="mb-1 text-xs text-[var(--muted)]">
                  {grupo.titulo}
                </div>
                <ul className="space-y-0.5">
                  {delGrupo.map((a) => (
                    <li key={a.id}>
                      <a
                        href={`#${a.id}`}
                        className="block rounded px-1.5 py-0.5 hover:bg-[var(--accent-soft)]"
                      >
                        {a.titulo}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="space-y-6">
          {visibles.length === 0 && (
            <p className="text-sm text-[var(--muted)]">
              {tx("Nada coincide con «")}
              {busqueda}
              {tx("». Prueba con otra palabra.")}
            </p>
          )}
          {GRUPOS.map((grupo) => {
            const delGrupo = visibles.filter((a) => a.grupo === grupo.clave);
            if (delGrupo.length === 0) return null;
            return (
              <section key={grupo.clave} className="space-y-4">
                <h2 className="text-sm font-semibold text-[var(--muted)]">
                  {grupo.titulo}
                </h2>
                {delGrupo.map((a) => (
                  <article
                    key={a.id}
                    id={a.id}
                    className="scroll-mt-4 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4"
                  >
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <h3 className="text-base font-semibold">{a.titulo}</h3>
                      {a.ruta && a.ruta !== "/wiki" && (
                        <Link
                          to={a.ruta}
                          className="text-xs text-[var(--accent)] hover:underline"
                        >
                          {tx("Abrir la pantalla")}
                        </Link>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-[var(--muted)]">
                      {a.resumen}
                    </p>
                    <div className="mt-4 space-y-4">
                      {a.secciones.map((s) => (
                        <div key={s.titulo}>
                          <h4 className="text-sm font-medium">{s.titulo}</h4>
                          {s.texto?.map((parrafo, i) => (
                            <p
                              key={i}
                              className="prosa mt-1 text-sm leading-relaxed"
                            >
                              {parrafo}
                            </p>
                          ))}
                          {s.puntos && (
                            <ul className="prosa mt-1 list-disc space-y-1 pl-5 text-sm leading-relaxed">
                              {s.puntos.map((punto, i) => (
                                <li key={i}>{punto}</li>
                              ))}
                            </ul>
                          )}
                          {s.formula && (
                            <pre className="mt-2 overflow-x-auto rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs leading-relaxed">
                              {s.formula}
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
