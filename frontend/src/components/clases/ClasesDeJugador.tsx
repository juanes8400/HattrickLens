/**
 * Clases de Jugador (2026-11-16): cuatro formas de partir la plantilla, y un
 * selector para escoger cuál se mira. Cada una tiene su propia gráfica, con
 * los ejes que explican por qué cada jugador cae en su grupo:
 *
 *  - Titularidad: las canchas de las formaciones con más experiencia.
 *  - Potencial: HTMS de hoy contra HTMS a los 28, cortado en las medianas.
 *  - Etapa de carrera: una fila por edad, con el dato que decide la etapa.
 *  - Personalizar: un tablero con los grupos que crea el usuario.
 *
 * Las reglas viven en el backend, `domain/engines/clases_de_jugador.py`.
 */
import { ErrorState, Loading } from "../Panels";
import { PanelDePestanas, Tabs } from "../Tabs";
import { usePlayerClasses } from "../../hooks/useTeam";
import { usePersistido } from "../../hooks/usePersistido";
import { tx } from "../../i18n/tx";
import { Etapa } from "./Etapa";
import { Personalizar } from "./Personalizar";
import { Potencial } from "./Potencial";
import { Titularidad } from "./Titularidad";

type Vista = "titularidad" | "potencial" | "etapa" | "personalizar";
const VISTAS: Vista[] = ["titularidad", "potencial", "etapa", "personalizar"];

export function ClasesDeJugador() {
  const { data, isLoading, isError, error } = usePlayerClasses();
  const [guardada, setVista] = usePersistido<Vista>(
    "clases-de-jugador.vista",
    "titularidad",
  );
  const vista = VISTAS.includes(guardada) ? guardada : "titularidad";

  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState error={error} />;

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-[var(--muted)]">{tx("Agrupar por")}</span>
        <Tabs
          grupo="clases-de-jugador"
          label={tx("Agrupar por")}
          tabs={[
            { key: "titularidad", label: tx("Titularidad") },
            { key: "potencial", label: tx("Potencial") },
            { key: "etapa", label: tx("Etapa de carrera") },
            { key: "personalizar", label: tx("Personalizar") },
          ]}
          active={vista}
          onChange={setVista}
        />
      </div>
      <PanelDePestanas grupo="clases-de-jugador" activa={vista}>
        {vista === "titularidad" ? (
          <Titularidad datos={data} />
        ) : vista === "potencial" ? (
          <Potencial datos={data} />
        ) : vista === "etapa" ? (
          <Etapa datos={data} />
        ) : (
          <Personalizar datos={data} />
        )}
      </PanelDePestanas>
    </div>
  );
}
