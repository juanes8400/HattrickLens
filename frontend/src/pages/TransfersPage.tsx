import { useValuations } from "../hooks/useTeam";
import { DataTable, type Column } from "../components/DataTable";
import { ErrorState, Loading, Note, Panel } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { number } from "../hooks/useFormat";
import type { Valuation } from "../services/api";

export function TransfersPage() {
  const { data, isLoading, isError, error } = useValuations();
  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const columns: Column<Valuation>[] = [
    {
      key: "player", header: "Jugador", align: "left", value: (v) => v.player,
      render: (v) => <PlayerLink htPlayerId={v.htPlayerId} name={v.player} />,
    },
    { key: "age", header: "Edad", value: (v) => parseFloat(v.age) },
    {
      key: "skill", header: "Skill dominante", align: "left",
      value: (v) => `${v.dominantSkill} ${v.dominantLevel}`,
    },
    { key: "price", header: "Precio esperado", value: (v) => v.expectedPrice,
      render: (v) => number(v.expectedPrice) },
    { key: "band", header: "Banda", value: (v) => v.low,
      render: (v) => <span className="text-[var(--muted)]">{number(v.low)}–{number(v.high)}</span> },
    { key: "verdict", header: "Recomendación", align: "left", value: (v) => v.verdict },
  ];

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Transferencias</h1>
        <p className="text-sm text-[var(--muted)]">Valoración de la plantilla y ventana de venta</p>
      </header>

      <DataTable
        rows={data}
        columns={columns}
        rowKey={(v) => v.htPlayerId}
        initialSort="price"
        csvName="valoraciones"
      />

      <Panel title="Fiabilidad de estas cifras">
        <Note>
          Los coeficientes de precio están marcados como supuestos: todavía no hemos observado
          ventas suficientes. La banda es deliberadamente ancha y el motor está construido para
          recalibrarse contra tus propias transferencias en cuanto haya muestras.
        </Note>
      </Panel>
    </div>
  );
}
