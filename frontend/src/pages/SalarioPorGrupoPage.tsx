/** Salario por grupo: pestaña de Jugadores desde la 8.0.0 (2026-11-26).
 *
 *  Antes era «Distribución del salario», la tercera pestaña de Profundidad de
 *  plantilla. Se mudó a Jugadores porque se parte por los grupos de las
 *  clasificaciones, que viven en la pestaña de al lado. Lo que se ve dentro no
 *  cambia. */
import { DistribucionDelSalario } from "../components/clases/DistribucionDelSalario";
import { tx } from "../i18n/tx";

export function SalarioPorGrupoPage() {
  return (
    <>
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "A qué grupo de cada clasificación se va el salario semanal de la plantilla.",
        )}
      </p>
      <DistribucionDelSalario />
    </>
  );
}
