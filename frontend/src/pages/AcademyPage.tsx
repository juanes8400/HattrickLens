import { Column, DataTable } from "../components/DataTable";
import { Empty, ErrorState, Kpi, Loading, Note, Panel } from "../components/Panels";
import { useAcademy } from "../hooks/useTeam";
import { date, htAge, money } from "../hooks/useFormat";
import type { Academy } from "../services/api";

const CATEGORY_TONE: Record<string, string> = {
  crack: "text-[var(--positive)]",
  promesa: "text-[var(--positive)]",
  aceptable: "",
  vendible: "text-[var(--muted)]",
  fontanero: "text-[var(--danger)]",
};

/**
 * Juveniles. HL-110, HL-111, HL-112, HL-114, HL-115.
 *
 * Dos cosas que esta pantalla hace y Hattrick Control no: cruzar lo invertido
 * con lo ingresado (viven en pantallas distintas y nunca se encuentran), y
 * distinguir un techo *desconocido* de un techo *bajo*. Descartar a un
 * canterano porque el ojeador aún no ha mirado sería confundir ignorancia con
 * evidencia.
 */
export function AcademyPage() {
  const { data, isLoading, isError, error } = useAcademy();

  if (isLoading) return <Loading />;
  if (isError) return <ErrorState error={error} />;
  if (!data) return null;

  const profitable = data.net > 0;

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold">Juveniles</h1>
        <p className="text-sm text-[var(--muted)]">
          Quién merece plaza, quién se pierde pronto y si la academia sale a cuenta
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Canteranos" value={String(data.squadSize)} />
        <Kpi
          label="Invertido"
          value={money(data.invested, data.currency)}
          hint={`${money(data.weeklyCost, data.currency)} por semana · ${data.seasons} temporadas`}
        />
        <Kpi
          label="Ingresado"
          value={money(data.earned, data.currency)}
          hint="ventas de canteranos"
        />
        <Kpi
          label="Neto"
          value={money(data.net, data.currency)}
          hint={data.roiVerdict}
          tone={profitable ? "positive" : "danger"}
        />
      </div>

      {!profitable && data.invested > 0 && (
        <Note>
          La academia está en pérdidas por {money(-data.net, data.currency)}. Estas dos cifras existen en
          Hattrick Control, en pantallas distintas, y nunca se cruzan: el gasto es semanal y
          silencioso, el retorno llega temporadas después.
          {data.breakEvenSales > 0 && (
            <> Harían falta {data.breakEvenSales} venta(s) más al precio medio para equilibrar.</>
          )}
        </Note>
      )}

      {data.urgent.length > 0 && (
        <Panel title="Plazo a punto de vencer" meta="lo urgente manda sobre lo importante">
          <ul className="space-y-1 p-4 text-xs">
            {data.urgent.map((u, i) => (
              <li key={i} className="text-[var(--danger)]">
                {u}
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {data.notes.map((n, i) => (
        <Note key={i}>{n}</Note>
      ))}

      <Panel title="Plantilla juvenil" meta="ordenada por potencial, no por nivel actual">
        {data.squadSize === 0 ? (
          <Empty>Sin canteranos sincronizados todavía.</Empty>
        ) : (
          <YouthTable data={data} />
        )}
      </Panel>

      {data.squadSize > 0 && <SkillDetail data={data} />}

      {data.graduates.length > 0 && (
        <Panel title="Canteranos que pasaron por aquí" meta={`${data.graduates.length}`}>
          <GraduatesTable data={data} />
        </Panel>
      )}
    </div>
  );
}

function YouthTable({ data }: { data: Academy }) {
  type Row = Academy["players"][number];
  const columns: Column<Row>[] = [
    { key: "name", header: "Nombre", value: (r) => r.name },
    {
      key: "age",
      header: "Edad",
      align: "right",
      value: (r) => r.ageYears * 112 + r.ageDays,
      render: (r) => <span className="tabular-nums">{htAge(r.ageYears, r.ageDays)}</span>,
    },
    {
      key: "category",
      header: "Categoría",
      value: (r) => r.category,
      render: (r) => (
        <span className={CATEGORY_TONE[r.category] ?? ""}>
          {r.category}
          {r.verdictIsProvisional && (
            <span title="pocos techos revelados: provisional"> ?</span>
          )}
        </span>
      ),
    },
    {
      key: "potential",
      header: "Potencial",
      align: "right",
      value: (r) => r.potentialScore,
      render: (r) => <span className="tabular-nums">{r.potentialScore.toFixed(1)}</span>,
    },
    {
      key: "best",
      header: "Mejor habilidad",
      value: (r) => r.bestSkill,
      render: (r) => (
        <span>
          {r.bestSkill}
          {r.bestSkillMax != null && (
            <span className="text-[var(--muted)]"> (techo {r.bestSkillMax})</span>
          )}
        </span>
      ),
    },
    {
      key: "revealed",
      header: "Techos revelados",
      align: "right",
      value: (r) => r.revealedSkills,
      render: (r) => (
        <span className="tabular-nums">
          {r.revealedSkills}/{r.skills.length}
        </span>
      ),
    },
    {
      key: "deadline",
      header: "Plazo",
      align: "right",
      value: (r) => r.daysUntilDeadline,
      render: (r) => (
        <span
          className={
            r.daysUntilDeadline <= 21
              ? "tabular-nums text-[var(--danger)]"
              : "tabular-nums"
          }
        >
          {r.weeksUntilDeadline} sem.
        </span>
      ),
    },
    {
      key: "exposure",
      header: "Aprovechamiento",
      align: "right",
      value: (r) => r.trainingExposure,
      render: (r) => (
        <span className="tabular-nums">{(r.trainingExposure * 100).toFixed(0)}%</span>
      ),
      optional: true,
    },
    { key: "advice", header: "Consejo", value: (r) => r.promoteAdvice },
  ];
  return (
    <>
      <DataTable
        rows={data.players}
        columns={columns}
        rowKey={(r) => r.htYouthPlayerId}
        csvName="juveniles"
        filterPlaceholder="Filtrar canteranos…"
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        El signo «?» marca categorías provisionales: el ojeador ha revelado pocos techos, así
        que la categoría puede subir sin que el jugador mejore. Un techo sin revelar no es un
        techo bajo.
      </p>
    </>
  );
}

function SkillDetail({ data }: { data: Academy }) {
  return (
    <Panel title="Techos por habilidad" meta="lo alcanzado frente a lo revelado">
      <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
        {data.players.map((p) => (
          <div key={p.htYouthPlayerId} className="rounded-lg border border-[var(--border)] p-3">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-medium">{p.name}</span>
              <span className={`text-xs ${CATEGORY_TONE[p.category] ?? ""}`}>{p.category}</span>
            </div>
            <div className="mt-3 space-y-2">
              {p.skills.map((s) => (
                <div key={s.skill} className="text-xs">
                  <div className="flex justify-between text-[var(--muted)]">
                    <span>{s.skill}</span>
                    <span className="tabular-nums">
                      {s.current}
                      {s.isRevealed ? ` / ${s.maximum}` : " / ?"}
                    </span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded bg-[var(--surface-2)]">
                    <div
                      className={s.isRevealed ? "h-full bg-[#4f7cff]" : "h-full bg-[#6b7280]"}
                      style={{
                        width: `${Math.min(
                          (s.current / Math.max(s.maximum ?? 8, 1)) * 100,
                          100,
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        Las barras grises son habilidades cuyo techo no ha revelado el ojeador: la barra usa
        un supuesto conservador y no una medida.
      </p>
    </Panel>
  );
}

function GraduatesTable({ data }: { data: Academy }) {
  type Row = Academy["graduates"][number];
  const columns: Column<Row>[] = [
    { key: "name", header: "Nombre", value: (r) => r.name },
    {
      key: "promoted", header: "Promocionado",
      value: (r) => (r.promotedAt ? new Date(r.promotedAt).getTime() : -Infinity),
      render: (r) => date(r.promotedAt),
    },
    {
      key: "sold", header: "Vendido",
      value: (r) => (r.soldAt ? new Date(r.soldAt).getTime() : -Infinity),
      render: (r) => date(r.soldAt),
    },
    {
      key: "price",
      header: "Precio",
      align: "right",
      value: (r) => r.soldFor ?? 0,
      render: (r) =>
        r.soldFor == null ? (
          <span className="text-[var(--muted)]">—</span>
        ) : (
          <span className="tabular-nums">{money(r.soldFor, data.currency)}</span>
        ),
    },
    { key: "team", header: "Equipo actual", value: (r) => r.currentTeam ?? "—" },
    { key: "tsi", header: "TSI", align: "right", value: (r) => r.currentTsi ?? 0, optional: true },
  ];
  return (
    <>
      <DataTable
        rows={data.graduates}
        columns={columns}
        rowKey={(r) => r.name}
        csvName="canteranos"
        filterPlaceholder="Filtrar…"
      />
      <p className="border-t border-[var(--border)] px-4 py-3 text-xs text-[var(--muted)]">
        De los canteranos que ya no están sólo se guarda su situación actual, nunca su
        evolución: las reglas de CHPP permiten mostrar datos actuales de jugadores de otros
        clubes pero no llevar su histórico.
      </p>
    </>
  );
}
