/** Privacidad y cookies.
 *
 *  POR QUÉ EXISTE. Dos motivos y los dos obligan. Google no acepta en AdSense
 *  un sitio sin política de privacidad que diga que terceros ponen cookies, y
 *  el RGPD pide poder RETIRAR un consentimiento con la misma facilidad con la
 *  que se dio --por eso el botón de abajo, que no es un adorno--.
 *
 *  SE ESCRIBE LO QUE DE VERDAD PASA. Es la parte que más fácil se copia de
 *  una plantilla y más fácil se queda mintiendo: aquí se nombran la cookie
 *  que existe, lo que guarda el navegador y lo que se queda en el servidor,
 *  y nada más. Si algún día se añade analítica, esta página se toca ANTES.
 */
import { Link } from "react-router-dom";

import { Panel } from "../components/Panels";
import { useConsentimiento } from "../components/Consentimiento";
import { hayAnuncios, preguntaGoogle } from "../config/anuncios";
import { decidir, olvidarLaDecision } from "../config/consentimiento";
import { tx } from "../i18n/tx";

function Seccion({
  titulo,
  children,
}: {
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <Panel title={titulo}>
      <div className="prosa space-y-3 px-4 py-3 text-sm text-[var(--text)]">
        {children}
      </div>
    </Panel>
  );
}

export function PrivacidadPage() {
  const decision = useConsentimiento();

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <Link
        to="/welcome"
        className="inline-block text-sm text-[var(--muted)] hover:text-[var(--text)]"
      >
        ← {tx("Volver")}
      </Link>

      <header>
        <h1 className="text-xl font-semibold">{tx("Privacidad y cookies")}</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          {tx(
            "Qué datos se piden, dónde se guardan y qué puedes hacer con ellos.",
          )}
        </p>
      </header>

      <Seccion titulo={tx("Qué es HT Lens")}>
        <p>
          {tx(
            "HT Lens es una herramienta independiente para managers de Hattrick. Lee los datos de tu propio club a través de CHPP, la interfaz oficial de Hattrick, y los presenta en forma de cuadro de mando: entrenamiento, plantilla, alineación, finanzas y precios de mercado.",
          )}
        </p>
        <p>
          {tx(
            "Esta aplicación utiliza información de Hattrick.org con la aprobación de sus desarrolladores. No está hecha ni respaldada por Hattrick ni por Extralives AB, y ni Hattrick ni Extralives se hacen responsables de ella.",
          )}
        </p>
      </Seccion>

      <Seccion titulo={tx("Qué datos se piden, y por qué")}>
        <p>
          {tx(
            "Nada hasta que tú lo autorizas. La conexión se hace con el flujo oficial de Hattrick (OAuth): eres tú quien da el permiso dentro de Hattrick, y HT Lens nunca ve ni guarda tu contraseña.",
          )}
        </p>
        <p>
          {tx(
            "Con ese permiso se leen los ficheros que publica CHPP sobre tu club: plantilla, entrenamiento, partidos, economía y mercado. Se guardan para poder enseñarte cómo cambian con el tiempo, que es justamente lo que Hattrick no conserva.",
          )}
        </p>
        <p>
          {tx(
            "El permiso de acceso se guarda cifrado, y puedes revocarlo cuando quieras desde tu propia cuenta de Hattrick, sin pasar por aquí.",
          )}
        </p>
      </Seccion>

      <Seccion titulo={tx("Qué guarda tu navegador")}>
        <p>
          {tx(
            "Una cookie propia de sesión, para no tener que pedirte permiso en cada visita. Dura treinta días y no sirve para seguirte por otros sitios.",
          )}
        </p>
        <p>
          {tx(
            "Y tres cosas en el almacenamiento local, que no viajan a ningún servidor: el tema claro u oscuro que elegiste, cuál es tu club activo, y tu decisión sobre las cookies de publicidad.",
          )}
        </p>
      </Seccion>

      <Seccion titulo={tx("Publicidad")}>
        {hayAnuncios() ? (
          <>
            <p>
              {tx(
                "Este sitio enseña anuncios de Google AdSense para pagarse el alojamiento. Google y sus socios pueden poner cookies en tu navegador para medir y personalizar lo que ves.",
              )}
            </p>
            <p>
              {preguntaGoogle()
                ? tx(
                    "Tu elección la gestiona el panel de consentimiento de Google, que es el que te preguntó. Desde él puedes cambiarla cuando quieras. Hasta que respondes, Google tiene prohibido usar cookies de publicidad y personalizar lo que ves.",
                  )
                : tx(
                    "No se cargan hasta que dices que sí. Mientras no decidas, o si dices que no, no se trae ni un solo script de Google y HT Lens funciona exactamente igual.",
                  )}
            </p>
            {/* LOS MANDOS SON NUESTROS Y SÓLO VALEN SI PREGUNTAMOS NOSOTROS.
                Con la plataforma de Google al mando, estos botones escribirían
                una decisión paralela a la suya: dos registros del mismo
                consentimiento que pueden decir cosas distintas, que es peor que
                no tener botón. Quien pregunta es quien manda. */}
            {!preguntaGoogle() && (
              <>
                <p>
                  {tx("Tu decisión ahora mismo es:")}{" "}
                  <strong>
                    {decision === "concedido"
                      ? tx("aceptadas")
                      : decision === "denegado"
                        ? tx("rechazadas")
                        : tx("sin decidir")}
                  </strong>
                </p>
                <div className="flex flex-wrap gap-2 pt-1">
                  {decision !== "denegado" && (
                    <button
                      type="button"
                      onClick={() => decidir("denegado")}
                      className="rounded border border-[var(--border)] px-3 py-1.5 text-xs"
                    >
                      {tx("Rechazar las cookies de publicidad")}
                    </button>
                  )}
                  {decision !== "concedido" && (
                    <button
                      type="button"
                      onClick={() => decidir("concedido")}
                      className="rounded border border-[var(--border)] px-3 py-1.5 text-xs"
                    >
                      {tx("Aceptar las cookies de publicidad")}
                    </button>
                  )}
                  {decision !== "sin-decidir" && (
                    <button
                      type="button"
                      onClick={olvidarLaDecision}
                      className="rounded border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)]"
                    >
                      {tx("Volver a preguntarme")}
                    </button>
                  )}
                </div>
              </>
            )}
          </>
        ) : (
          <p>
            {tx(
              "Este sitio no enseña publicidad ahora mismo, y no carga ningún script de terceros para ello.",
            )}
          </p>
        )}
      </Seccion>

      <Seccion titulo={tx("Qué NO se hace")}>
        <p>
          {tx(
            "No se venden ni se ceden tus datos. No hay analítica de terceros. No se lee nada de tu cuenta de Hattrick que no sean los ficheros que CHPP publica sobre tu propio club.",
          )}
        </p>
      </Seccion>

      <Seccion titulo={tx("Borrar tus datos")}>
        <p>
          {tx(
            "Puedes pedir que se borre todo lo guardado sobre tu club. También puedes cortar el acceso en cualquier momento revocando el permiso de HT Lens desde Hattrick, y entonces dejan de leerse datos nuevos.",
          )}
        </p>
      </Seccion>
    </div>
  );
}
