/** Contar un fallo, desde dentro y desde cualquier pantalla.
 *
 *  2026-10-25, cerrando un reporte de usuario que terminaba así: «By the way,
 *  I didn't see any "report bug" or such button on the site itself». No lo
 *  había: los dos reportes que llegaron vinieron por fuera, y eso significa
 *  que los que no se molestaron en buscar un canal no llegaron.
 *
 *  POR QUÉ UN FORMULARIO Y NO UN ENLACE A GITHUB. El repositorio es público y
 *  tiene las incidencias abiertas, así que un enlace habría costado cero. Pero
 *  quien usa esto es un manager de Hattrick, no un programador: pedirle una
 *  cuenta de GitHub para contar que el sincronizador se le corta es casi no
 *  darle el botón.
 *
 *  LA PANTALLA SE RELLENA SOLA. Es el dato que más veces falta en un reporte
 *  --«no me funciona» sin decir dónde-- y el único que no hay que pedir.
 *
 *  AL PIE DEL MENÚ Y NO FLOTANDO. Un botón fijo sobre el contenido tapa algo
 *  en todas las pantallas para servir en una; al pie del menú se encuentra
 *  cuando se busca, que es cuando hace falta.
 */
import { useState } from "react";
import { useLocation } from "react-router-dom";

import { api } from "../services/api";
import { moduloDe } from "../services/telemetria";
import { tx } from "../i18n/tx";

/** Tope del texto, el mismo que acepta el servidor. Se dice al llegar al
 *  final en vez de cortar en silencio. */
const MAXIMO = 4000;

export function ReportarFallo() {
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { pathname } = useLocation();

  // EL MISMO NOMBRE QUE USA LA TELEMETRÍA, no el título de la pestaña. El
  // título trae el sufijo «· HT Lens» pegado --se vio al probarlo-- y, más
  // importante, con otro nombre un reporte y las visitas de esa misma pantalla
  // no se podrían cruzar: dirían «Dashboard · HT Lens» y «Dashboard».
  const pantalla = moduloDe(pathname);

  const enviar = async () => {
    const limpio = texto.trim();
    if (!limpio || enviando) return;
    setEnviando(true);
    setError(null);
    try {
      await api.reportarFallo(limpio, pantalla);
      setListo(true);
      setTexto("");
    } catch {
      // Sin tragárselo: si el reporte no llegó, decirlo. Un «gracias» falso
      // deja a quien escribió creyendo que ya está contado.
      setError(tx("No se pudo enviar. Vuelve a intentarlo en un momento."));
    } finally {
      setEnviando(false);
    }
  };

  if (!abierto) {
    return (
      <button
        onClick={() => {
          setAbierto(true);
          setListo(false);
        }}
        data-track="Reportar un fallo: abrir"
        className="mt-2 w-full rounded-md border border-[var(--border)] px-2 py-1.5 text-left text-xs text-[var(--muted)] hover:text-[var(--text)]"
      >
        {tx("Reportar un fallo")}
      </button>
    );
  }

  return (
    <div className="mt-2 rounded-md border border-[var(--border)] p-2">
      {listo ? (
        <div className="space-y-2">
          <p className="text-xs text-[var(--positive)]">
            {tx("Contado. Gracias: con esto se puede buscar.")}
          </p>
          <button
            onClick={() => setAbierto(false)}
            className="text-xs text-[var(--muted)] hover:text-[var(--text)]"
          >
            {tx("Cerrar")}
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <label
            htmlFor="reporte-de-fallo"
            className="block text-xs font-medium"
          >
            {tx("¿Qué ha pasado?")}
          </label>
          {/* La pantalla, dicha y no escondida: quien escribe tiene que poder
              ver qué se manda con su texto. */}
          <p className="text-[11px] text-[var(--muted)]">
            {tx("Se envía desde «{{v0}}», con tu navegador.", { v0: pantalla })}
          </p>
          <textarea
            id="reporte-de-fallo"
            value={texto}
            maxLength={MAXIMO}
            onChange={(e) => setTexto(e.target.value)}
            rows={5}
            placeholder={tx("Qué hacías, qué esperabas y qué salió.")}
            className="w-full rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 text-xs"
          />
          {error && <p className="text-xs text-[var(--warning)]">{error}</p>}
          <div className="flex items-center gap-2">
            <button
              onClick={() => void enviar()}
              disabled={!texto.trim() || enviando}
              data-track="Reportar un fallo: enviar"
              className="rounded-md border border-[var(--accent)] px-2 py-1 text-xs text-[var(--accent)] disabled:opacity-40"
            >
              {enviando ? tx("Enviando…") : tx("Enviar")}
            </button>
            <button
              onClick={() => {
                setAbierto(false);
                setError(null);
              }}
              className="text-xs text-[var(--muted)] hover:text-[var(--text)]"
            >
              {tx("Cancelar")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
