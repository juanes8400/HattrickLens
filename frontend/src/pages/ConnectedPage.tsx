import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { setActiveTeamId } from "../hooks/useTeam";

/**
 * Destino del redirect tras `GET /auth/chpp/callback`. El backend ya dejó la
 * cookie de sesión puesta; aquí solo queda guardar qué equipo es el activo y
 * recargar de verdad (no navegar con el router) para que todo el módulo de
 * hooks — que lee `TEAM_ID` una vez al cargar — se reevalúe con el valor real.
 */
export function ConnectedPage() {
  const [params] = useSearchParams();

  useEffect(() => {
    const teamId = Number(params.get("teamId"));
    if (teamId) setActiveTeamId(teamId);
    window.location.href = "/dashboard";
  }, [params]);

  return (
    <div className="flex min-h-screen items-center justify-center text-sm text-[var(--muted)]">
      Conectado. Cargando tu club…
    </div>
  );
}
