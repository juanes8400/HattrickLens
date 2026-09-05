import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { ApiError, api } from "../services/api";
import { setActiveTeamId, useSessionProfile } from "../hooks/useTeam";
import { ImagenOpcional, SELLO_PROVEEDOR } from "../components/ImagenOpcional";
import { hayApoyo } from "../config/apoyo";

function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (error.status === 0 || error.status === 502) {
      return "No se pudo contactar el servicio local. Comprueba que el backend esté en marcha.";
    }
  }
  return "No fue posible iniciar la conexión. Inténtalo de nuevo en unos segundos.";
}

/** Primer punto de contacto. Ningún dato de Hattrick se solicita hasta que el
 * manager decide iniciar el flujo OAuth oficial. */
export function WelcomePage() {
  const [error, setError] = useState<string | null>(null);
  const [params] = useSearchParams();
  const sessionExpired = params.get("reason") === "session_expired";

  // Antes de pedir nada, PREGUNTAR si ya hay sesión.
  //
  // 2026-09-04, reportado por el usuario: «cierro el navegador, vuelvo a
  // abrir y me pide Permitir otra vez». La cookie de sesión dura 30 días y
  // seguía viva; lo que fallaba es que el guardián de rutas mira
  // `localStorage` --de donde sale el equipo activo-- y esta pantalla no
  // preguntaba nada: enseñaba «Conecta tu club» y su único botón arranca el
  // baile de OAuth, que es cuando Hattrick pide «Permitir».
  //
  // Así que bastaba con que `localStorage` se vaciara --el navegador lo
  // limpia al cerrar en muchas configuraciones, y `expireLocalSession()` lo
  // borra ante un 401-- para tener que volver a autorizar con la sesión
  // intacta.
  const perfil = useSessionProfile();
  const equipoRecuperable = perfil.data?.teams?.[0];

  useEffect(() => {
    if (!equipoRecuperable) return;
    setActiveTeamId(equipoRecuperable.id);
    // `replace` y no `assign`: volver atrás no debe traer de vuelta a una
    // bienvenida que ya no aplica.
    window.location.replace("/dashboard");
  }, [equipoRecuperable]);

  const connect = useMutation({
    mutationFn: api.connectChpp,
    onSuccess: ({ authorizeUrl }) => {
      window.location.assign(authorizeUrl);
    },
    onError: (reason) => setError(messageFor(reason)),
  });

  // Mientras se pregunta no se enseña «Conecta tu club»: hacerlo y saltar
  // medio segundo después es peor que esperar ese medio segundo.
  if (perfil.isLoading || equipoRecuperable) {
    return (
      <main className="grid min-h-screen place-items-center bg-[var(--bg)] px-6">
        <p className="text-sm text-[var(--muted)]">
          {equipoRecuperable
            ? "Recuperando tu sesión…"
            : "Comprobando si ya has conectado…"}
        </p>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] px-6 py-12">
      <section className="w-full max-w-xl rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-8 shadow-sm sm:p-10">
        <div className="mb-8 flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-[var(--accent)] font-bold text-white">
            HL
          </span>
          <div>
            <p className="text-lg font-semibold">HT Lens</p>
            <p className="text-sm text-[var(--muted)]">
              Tu centro de mando para Hattrick
            </p>
          </div>
        </div>

        <p className="text-xs font-medium uppercase tracking-[0.16em] text-[var(--accent)]">
          Empieza con tus datos reales
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight">
          Conecta tu club
        </h1>
        <p className="mt-3 max-w-md leading-6 text-[var(--muted)]">
          Autoriza HT Lens mediante la conexión oficial de Hattrick. Después
          podrás sincronizar tu plantilla, entrenamiento, finanzas y partidos
          cuando tú lo decidas.
        </p>

        {sessionExpired && (
          <p
            role="status"
            className="mt-5 rounded-lg border border-[var(--warning)]/30 bg-[var(--warning)]/10 p-3 text-sm text-[var(--warning)]"
          >
            Tu sesión venció. Reconecta con Hattrick para continuar; tus datos
            guardados no se perderán.
          </p>
        )}

        <div className="mt-7 space-y-3 rounded-xl bg-[var(--surface-2)] p-4 text-sm">
          <div className="flex gap-3">
            <span className="font-semibold text-[var(--accent)]">01</span>
            <p>
              <b>Inicia sesión en Hattrick.</b>
              <br />
              <span className="text-[var(--muted)]">
                La autorización se realiza en Hattrick.org.
              </span>
            </p>
          </div>
          <div className="flex gap-3">
            <span className="font-semibold text-[var(--accent)]">02</span>
            <p>
              <b>Confirma tu club.</b>
              <br />
              <span className="text-[var(--muted)]">
                Si administras más de uno, podrás escoger con cuál trabajar.
              </span>
            </p>
          </div>
          <div className="flex gap-3">
            <span className="font-semibold text-[var(--accent)]">03</span>
            <p>
              <b>Importa bajo demanda.</b>
              <br />
              <span className="text-[var(--muted)]">
                HT Lens no hace una sincronización completa hasta que tú la
                solicitas.
              </span>
            </p>
          </div>
        </div>

        {error && (
          <p
            role="alert"
            className="mt-5 rounded-lg bg-[var(--danger)]/10 p-3 text-sm text-[var(--danger)]"
          >
            {error}
          </p>
        )}

        <button
          type="button"
          onClick={() => {
            setError(null);
            connect.mutate();
          }}
          disabled={connect.isPending}
          className="mt-7 w-full rounded-lg bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-white transition hover:brightness-95 disabled:cursor-wait disabled:opacity-70"
        >
          {connect.isPending ? "Abriendo Hattrick…" : "Conectar con Hattrick"}
        </button>
        <p className="mt-4 text-center text-xs leading-5 text-[var(--muted)]">
          HT Lens usa información de Hattrick.org con autorización de sus
          propietarios. Tus credenciales de Hattrick nunca pasan por esta
          aplicación.
        </p>
        {/* El apoyo va DEBAJO del botón de conectar y con la mitad de peso
            visual: quien llega aquí todavía no ha usado nada, así que esto no
            puede competir con lo único que tiene que hacer en esta pantalla.
            Sin fondo de color ni botón grande, por eso mismo. */}
        {hayApoyo() && (
          <div className="mt-5 flex flex-wrap items-center justify-center gap-x-3 gap-y-2 rounded-lg border border-[var(--border)] px-3 py-3 text-center">
            <span className="text-xs leading-5 text-[var(--muted)]">
              HT Lens es gratis. El servidor lo pago yo, 7 US$ al mes.
            </span>
            {/* `a` y no `Link`: la bienvenida vive FUERA del enrutador de la
                aplicación, así que aquí un `Link` no tendría contexto. */}
            <a
              href="/apoyar"
              className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs text-[var(--muted)] transition-colors hover:border-[var(--accent)] hover:text-[var(--text)]"
            >
              <span aria-hidden="true">☕</span>
              Invítame a un café
            </a>
          </div>
        )}

        {/* El sello va junto a la frase que dice de dónde salen los datos, y
            no suelto arriba: ahí es donde alguien que duda de si esto es de
            fiar está mirando. */}
        <div className="mt-4 flex justify-center">
          <ImagenOpcional
            src={SELLO_PROVEEDOR}
            alt="Proveedor certificado de productos Hattrick"
            width={160}
            height={64}
            className="h-14 w-auto object-contain"
          />
        </div>
      </section>
    </main>
  );
}
