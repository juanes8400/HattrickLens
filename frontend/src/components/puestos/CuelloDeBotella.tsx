/** Cuello de botella: el sector de tu equipo que menos ventaja le saca al
 *  mejor rival de tu serie en ese sector, y qué subida lo arregla antes.
 *
 *  Era el último panel de Profundidad; desde la 8.2.0 (2026-11-26, pedido del
 *  usuario) es la tercera pestaña de Puestos. Lo que se ve dentro no cambia.
 *  Profundidad conserva su cifra de cabecera y las 🍾 que marcan los puestos
 *  del sector. */
import { useTranslation } from "react-i18next";
import { Note, Panel } from "../Panels";
import type { Skills } from "../../services/api";
import { COLOR, decimal, sectorOficial } from "./comun";
import { Pastilla } from "./Pastilla";

export function CuelloDeBotella({ data }: { data: Skills }) {
  const { t } = useTranslation();
  const cuelloDeBotella = t("habilidades.cuello", "Cuello de botella");
  return (
    <Panel title={cuelloDeBotella}>
      {data.sectors.length === 0 ? (
        <Note>
          {t(
            "habilidades.cuelloVacio",
            "Aparece cuando haya partidos oficiales con sus ratings y la alineación del último.",
          )}
        </Note>
      ) : (
        <div className="space-y-5 px-4 py-4">
          <p className="prosa text-sm text-[var(--muted)]">
            {t(
              "habilidades.cuelloExplicacion",
              "Cada sector de tu equipo frente al mejor rival de tu serie en ese mismo sector, con la media de los últimos 5 partidos oficiales. El cuello de botella es donde menos ventaja le sacas.",
            )}
          </p>

          <div className="grid gap-4 md:grid-cols-3">
            {data.sectors.map((s) => {
              const tope = Math.max(s.rating, s.bestRivalValue ?? 0) || 1;
              return (
                <div
                  key={s.key}
                  className="rounded-lg border border-[var(--border)] p-3"
                  style={
                    s.label === data.bottleneck
                      ? { borderColor: COLOR[s.tone] }
                      : undefined
                  }
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">
                      {sectorOficial(s.key, s.label)}
                    </span>
                    <Pastilla tone={s.tone}>{s.verdict}</Pastilla>
                  </div>
                  <div className="mt-3 space-y-1.5 text-xs">
                    {[
                      {
                        id: "tu",
                        quien: t("habilidades.tuMayus", "Tú"),
                        valor: s.rating,
                        color: COLOR[s.tone],
                      },
                      {
                        id: "rival",
                        quien: s.bestRival,
                        valor: s.bestRivalValue ?? 0,
                        color: "var(--muted)",
                      },
                    ].map((b) => (
                      <div
                        key={b.id}
                        className="grid grid-cols-[minmax(0,6rem)_minmax(0,1fr)_2.5rem] items-center gap-2"
                      >
                        <span className="truncate" title={b.quien}>
                          {b.quien}
                        </span>
                        <span className="h-2 rounded bg-[var(--border)]">
                          <span
                            className="block h-2 rounded"
                            style={{
                              width: `${(b.valor / tope) * 100}%`,
                              background: b.color,
                            }}
                          />
                        </span>
                        <span className="text-right tabular-nums">
                          {decimal(b.valor)}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 text-sm">
                    {s.marginPct < 0
                      ? t(
                          "habilidades.vasDetras",
                          "Vas un {{pct}} % por detrás",
                          { pct: Math.round(-s.marginPct) },
                        )
                      : s.marginPct < 0.5
                        ? t("habilidades.empatas", "Empatas con el mejor rival")
                        : t(
                            "habilidades.leSacas",
                            "Le sacas un {{pct}} % de ventaja",
                            { pct: Math.round(s.marginPct) },
                          )}
                  </div>
                  {s.who && (
                    <div className="mt-1 text-xs text-[var(--muted)]">
                      {t("habilidades.loSostienen", "Lo sostienen: {{quien}}", {
                        quien: (s.whoItems ?? []).length
                          ? s.whoItems
                              .map((p) => `${p.player} (${p.sigla} ${p.nivel})`)
                              .join(" · ")
                          : s.who,
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {data.upgrades.length > 0 && data.bottleneck && (
            <div>
              <div className="text-sm font-medium">
                {t(
                  "habilidades.queSubir",
                  "Qué subir primero para el {{sector}}",
                  { sector: data.bottleneck.toLowerCase() },
                )}
              </div>
              <p className="prosa mt-0.5 text-xs text-[var(--muted)]">
                {t(
                  "habilidades.conTuOnce",
                  "Con tu once titular del {{fecha}}{{formacion}}: un nivel más de estas habilidades es lo que más empuja ese sector.",
                  {
                    fecha: data.lastMatchDate,
                    formacion: data.formation ? ` (${data.formation})` : "",
                  },
                )}
              </p>
              <div className="mt-2 divide-y divide-[var(--border)]">
                {data.upgrades.map((u, i) => (
                  <div
                    key={`${u.htPlayerId}-${u.skill}`}
                    className="grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-2 py-2 text-sm"
                  >
                    <span className="text-[var(--muted)]">{i + 1}</span>
                    <span className="min-w-0">
                      {t(
                        "habilidades.subida",
                        "{{habilidad}} de {{jugador}}: {{de}} → {{a}}",
                        {
                          habilidad: u.skillLabel,
                          jugador: u.player,
                          de: u.fromLevel,
                          a: u.fromLevel + 1,
                        },
                      )}
                      <span className="block text-xs text-[var(--muted)]">
                        {t(
                          "habilidades.subeUn",
                          "el {{sector}} del once sube un {{pct}} %",
                          {
                            sector: data.bottleneck?.toLowerCase(),
                            pct: decimal(u.gainPct),
                          },
                        )}
                      </span>
                    </span>
                    <Pastilla tone={u.impact === "Alto" ? "ok" : "warning"}>
                      {u.impact === "Alto"
                        ? t("habilidades.mayorEfecto", "Mayor efecto")
                        : t("habilidades.efectoMedio", "Efecto medio")}
                    </Pastilla>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}
