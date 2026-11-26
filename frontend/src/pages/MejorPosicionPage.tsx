/** Mejor posición: pestaña de Puestos desde la 8.1.0 (2026-11-26).
 *
 *  Antes era la segunda pestaña de Profundidad de plantilla, en la misma
 *  dirección. Lo que se ve dentro no cambia: cuántos jugadores tienen cada
 *  puesto como su mejor posición, sobre la cancha, con capitán y lanzador de
 *  faltas aparte. Es la columna «Mejor posición» de la tabla de Jugadores,
 *  contada.
 *
 *  Sale de las medias de la plantilla (`/overview`), no de `/skills`: por eso
 *  es su propia pantalla y no espera a la de Profundidad. */
import { useTranslation } from "react-i18next";
import { MejorPosicion } from "../components/MejorPosicion";
import { ErrorState, Loading, Note, Panel } from "../components/Panels";
import { useTeamOverview } from "../hooks/useTeam";
import { tx } from "../i18n/tx";

export function MejorPosicionPage() {
  const { t } = useTranslation();
  const { data, isLoading, isError, error } = useTeamOverview();
  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;

  const grupo = data?.groups.find((g) => g.key === "best_position");
  return (
    <>
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Cuántos jugadores tienen cada puesto como su mejor posición, de portería a delantera.",
        )}
      </p>
      {grupo ? (
        <Panel
          title={grupo.label}
          meta={t("comun.nJugadores", "{{n}} jugadores", {
            n: data?.playerCount ?? 0,
          })}
        >
          <MejorPosicion group={grupo} />
          {grupo.note && <Note>{grupo.note}</Note>}
        </Panel>
      ) : (
        <Panel title={t("habilidades.mejorPosicion", "Mejor posición")}>
          <Note>
            {t(
              "habilidades.mejorPosicionVacia",
              "Aparece en cuanto haya medias de la plantilla sincronizadas.",
            )}
          </Note>
        </Panel>
      )}
    </>
  );
}
