/** Cuello de botella: pestaña de Puestos desde la 8.2.0 (2026-11-26).
 *
 *  Sale de la misma consulta que Profundidad (`/skills`), sin la formación
 *  que se elija allí: el cuello de botella se mide con los partidos
 *  oficiales y el once del último, no con la formación de Profundidad. */
import { ErrorState, Loading, SinDatos } from "../components/Panels";
import { CuelloDeBotella } from "../components/puestos/CuelloDeBotella";
import { useSkills } from "../hooks/useTeam";

export function CuelloDeBotellaPage() {
  const { data, isLoading, isError, error } = useSkills();
  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return <SinDatos />;
  return <CuelloDeBotella data={data} />;
}
