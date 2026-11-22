import { useState } from "react";
import clsx from "clsx";
import { MatchSectorMap } from "./MatchSectorMap";
import { Empty, Loading, Panel } from "./Panels";
import { useMatchAutopsy, useMatchDetail } from "../hooks/useTeam";
import { decimal, number, percent } from "../hooks/useFormat";
import type {
  CapaDeLaAutopsia,
  LastMatchReport,
  MatchAutopsy,
  MatchDetail,
} from "../services/api";
import { terminoOficial } from "../i18n/glosario";
import { tx } from "../i18n/tx";

/**
 * La autopsia del último partido (2026-11-22, pedido del usuario: «hacerle una
 * autopsia completa al partido como tal y a la predicción»).
 *
 * Va DEBAJO del parte de siempre, que se queda arriba tal cual (decisión del
 * usuario: «ya haremos cambios si vale la pena»). Tres bloques:
 *
 *   · el veredicto, en una frase;
 *   · qué pasó: la cancha de duelos, posesión, ocasiones, conversión y quién
 *     jugó por debajo de su media;
 *   · la predicción desarmada: el mismo motor pasado tres veces, cuánto de la
 *     diferencia fue tuyo y cuánto del rival, y lo supuesto frente a lo real.
 *
 * Como en el parte, el servidor manda claves y números y TODA FRASE SE
 * ESCRIBE AQUÍ, entera, para que se pueda traducir.
 */

/** Los sectores con su nombre del glosario oficial de Hattrick. */
const SECTOR: Record<string, [string, string]> = {
  midfield: ["Midfield", "Mediocampo"],
  left_def: ["LeftDefense", "Defensa izquierda"],
  central_def: ["CentralDefense", "Defensa central"],
  right_def: ["RightDefense", "Defensa derecha"],
  left_att: ["LeftAttack", "Ataque izquierdo"],
  central_att: ["CentralAttack", "Ataque central"],
  right_att: ["RightAttack", "Ataque derecho"],
};

const nombreDelSector = (clave: string): string => {
  const [oficial, respaldo] = SECTOR[clave] ?? ["", clave];
  return terminoOficial("sectores", oficial, respaldo);
};

/** Media categoría: Hattrick parte cada nivel en cuatro escalones. */
const DIFERENCIA_QUE_SE_ENSENA = 2;

const valoracion = (v: number) =>
  Number.isInteger(v) ? number(v) : decimal(v, 1);

const conSigno = (v: number) => (v > 0 ? `+${v}` : v < 0 ? `−${-v}` : "0");

function fraseDelVeredicto(a: MatchAutopsy): string {
  const v = a.veredicto!;
  const sector = v.sector ? nombreDelSector(v.sector) : null;
  const capa = (clave: string) => a.capas!.find((c) => c.clave === clave);
  if (v.tipo === "sinPrediccion")
    return sector
      ? tx(
          "No guardamos qué dijimos de este partido. La diferencia estuvo en: {{v0}}.",
          { v0: sector },
        )
      : tx("No guardamos qué dijimos de este partido, y acabó en empate.");
  if (v.tipo === "esperado")
    return sector
      ? tx("Salió lo que esperábamos. La diferencia estuvo en: {{v0}}.", {
          v0: sector,
        })
      : tx("Salió lo que esperábamos: un empate.");
  if (v.tipo === "azar") {
    const real = capa("real")!;
    const favorito =
      real.gana >= real.empate && real.gana >= real.pierde
        ? "gana"
        : real.pierde >= real.empate
          ? "pierde"
          : "empate";
    if (favorito === "gana")
      return tx(
        "Pasó lo improbable: con lo que salió al campo, lo más probable era ganar.",
      );
    if (favorito === "pierde")
      return tx(
        "Pasó lo improbable: con lo que salió al campo, lo más probable era perder.",
      );
    return tx(
      "Pasó lo improbable: con lo que salió al campo, lo más probable era empatar.",
    );
  }
  // Información: con lo real, lo que pasó era lo más probable.
  if (v.culpa === "propio") {
    const peor = capa("realPropio")!.gana < capa("dicho")!.gana;
    return peor
      ? tx(
          "Tu equipo salió más flojo de lo que suponíamos, sobre todo en: {{v0}}.",
          { v0: sector },
        )
      : tx(
          "Tu equipo salió más fuerte de lo que suponíamos, sobre todo en: {{v0}}.",
          { v0: sector },
        );
  }
  if (v.culpa === "rival") {
    const peor = capa("real")!.gana < capa("realPropio")!.gana;
    return peor
      ? tx(
          "El rival vino más fuerte de lo que suponíamos, sobre todo en: {{v0}}.",
          { v0: sector },
        )
      : tx(
          "El rival vino más flojo de lo que suponíamos, sobre todo en: {{v0}}.",
          { v0: sector },
        );
  }
  return sector
    ? tx(
        "El partido no se jugó como suponíamos: con lo que salió al campo, lo que pasó era lo más probable. La diferencia estuvo en: {{v0}}.",
        { v0: sector },
      )
    : tx(
        "El partido no se jugó como suponíamos: con lo que salió al campo, lo que pasó era lo más probable.",
      );
}

function etiquetaDeLaCapa(clave: CapaDeLaAutopsia["clave"]): string {
  if (clave === "dicho") return tx("Lo que dijimos");
  if (clave === "realPropio")
    return tx("Con lo real tuyo y lo supuesto del rival");
  return tx("Con lo real de los dos");
}

function QuePaso({
  detalle,
  autopsia,
}: {
  detalle: MatchDetail | undefined;
  autopsia: MatchAutopsy;
}) {
  const flojos = autopsia.porDebajoDeSuMedia ?? [];
  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">{tx("1. Qué pasó")}</div>
      {detalle && <MatchSectorMap data={detalle} />}
      {detalle && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <Cifra
            etiqueta={tx("Posesión")}
            valor={percent(
              (detalle.possession[0] + detalle.possession[1]) / 2,
              0,
            )}
          />
          <Cifra
            etiqueta={tx("Ocasiones")}
            valor={`${detalle.ownChances.total} – ${detalle.opponentChances.total}`}
          />
          <Cifra
            etiqueta={tx("Conversión")}
            valor={`${percent(detalle.ownChances.conversion * 100, 0)} – ${percent(
              detalle.opponentChances.conversion * 100,
              0,
            )}`}
          />
        </div>
      )}
      <p className="text-sm">
        <span className="text-[var(--muted)]">
          {tx("Por debajo de su media:")}
        </span>{" "}
        {flojos.length === 0
          ? tx("nadie jugó una estrella o más por debajo de su media.")
          : flojos
              .map(
                (f) =>
                  `${f.nombre} ${tx("{{v0}}★ (suele {{v1}}★)", {
                    v0: decimal(f.estrellas, 1),
                    v1: decimal(f.media, 1),
                  })}`,
              )
              .join(" · ")}
      </p>
    </div>
  );
}

function Cifra({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div className="rounded-lg bg-[var(--surface-2)] px-3 py-2">
      <div className="text-xs text-[var(--muted)]">{etiqueta}</div>
      <div className="text-lg font-medium tabular-nums">{valor}</div>
    </div>
  );
}

function LaPrediccion({ autopsia }: { autopsia: MatchAutopsy }) {
  const [todas, setTodas] = useState(false);
  const capas = autopsia.capas ?? [];
  const dicho = capas.find((c) => c.clave === "dicho");
  const intermedia = capas.find((c) => c.clave === "realPropio");
  const real = capas.find((c) => c.clave === "real");
  const filas = (autopsia.supuestoVsReal ?? []).filter(
    (f) => todas || Math.abs(f.real - f.supuesto) >= DIFERENCIA_QUE_SE_ENSENA,
  );
  const pasa = autopsia.resultado;

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium">
        {tx("2. La predicción, desarmada")}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm tabular-nums">
          <thead>
            <tr className="text-xs text-[var(--muted)]">
              <th className="py-1 text-left font-medium" />
              <th className="px-2 py-1 text-right font-medium">{tx("Gana")}</th>
              <th className="px-2 py-1 text-right font-medium">
                {tx("Empate")}
              </th>
              <th className="px-2 py-1 text-right font-medium">
                {tx("Pierde")}
              </th>
              <th className="py-1 pl-2 text-right font-medium">
                {tx("Marcador")}
              </th>
            </tr>
          </thead>
          <tbody>
            {capas.map((c) => (
              <tr
                key={c.clave}
                className={clsx(
                  "border-t border-[var(--border)]",
                  c.clave === "real" && "font-medium",
                )}
              >
                <td className="py-1.5 pr-2 text-left">
                  {etiquetaDeLaCapa(c.clave)}
                </td>
                {(["gana", "empate", "pierde"] as const).map((k) => (
                  <td
                    key={k}
                    className={clsx(
                      "px-2 py-1.5 text-right",
                      k === pasa && "text-[var(--accent)]",
                    )}
                  >
                    {k === "empate" && autopsia.copa
                      ? "—"
                      : percent(c[k] * 100, 0)}
                  </td>
                ))}
                <td className="py-1.5 pl-2 text-right">{c.marcador}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-[var(--muted)]">
        {tx("En azul, lo que pasó.")}
      </p>

      {dicho && intermedia && real && (
        <p className="text-sm">
          {tx(
            "Tu probabilidad de ganar pasó de {{v0}} a {{v1}}: {{v2}} puntos por cómo salió tu equipo y {{v3}} por cómo vino el rival.",
            {
              v0: percent(dicho.gana * 100, 0),
              v1: percent(real.gana * 100, 0),
              v2: conSigno(Math.round((intermedia.gana - dicho.gana) * 100)),
              v3: conSigno(Math.round((real.gana - intermedia.gana) * 100)),
            },
          )}
        </p>
      )}

      {(autopsia.supuestoVsReal ?? []).length > 0 ? (
        <div className="space-y-1">
          <div className="flex items-baseline justify-between gap-2">
            <div className="text-xs text-[var(--muted)]">
              {tx("Lo que suponíamos frente a lo que salió")}
            </div>
            <button
              type="button"
              onClick={() => setTodas((t) => !t)}
              className="text-xs text-[var(--accent)] hover:underline"
            >
              {todas ? tx("Ver sólo las grandes") : tx("Ver todas")}
            </button>
          </div>
          {filas.length === 0 ? (
            <p className="text-sm text-[var(--muted)]">
              {tx("Nada salió a media categoría o más de lo que suponíamos.")}
            </p>
          ) : (
            <table className="w-full text-sm tabular-nums">
              <thead>
                <tr className="text-xs text-[var(--muted)]">
                  <th className="py-1 text-left font-medium" />
                  <th className="px-2 py-1 text-right font-medium">
                    {tx("Supuesto")}
                  </th>
                  <th className="px-2 py-1 text-right font-medium">
                    {tx("Real")}
                  </th>
                  <th className="py-1 pl-2 text-right font-medium">
                    {tx("Diferencia")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => {
                  const diferencia = f.real - f.supuesto;
                  // Malo para ti: tu sector por debajo, o el suyo por encima.
                  const malo =
                    f.lado === "propio" ? diferencia < 0 : diferencia > 0;
                  return (
                    <tr
                      key={`${f.lado}-${f.sector}`}
                      className="border-t border-[var(--border)]"
                    >
                      <td className="py-1.5 pr-2 text-left">
                        <span className="text-[var(--muted)]">
                          {f.lado === "propio" ? tx("Tú") : tx("Rival")} ·
                        </span>{" "}
                        {nombreDelSector(f.sector)}
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        {valoracion(f.supuesto)}
                      </td>
                      <td className="px-2 py-1.5 text-right">
                        {valoracion(f.real)}
                      </td>
                      <td
                        className={clsx(
                          "py-1.5 pl-2 text-right",
                          diferencia !== 0 &&
                            (malo
                              ? "text-[var(--danger)]"
                              : "text-[var(--positive)]"),
                        )}
                      >
                        {conSigno(Math.round(diferencia * 10) / 10)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          {!todas && (
            <p className="text-xs text-[var(--muted)]">
              {tx(
                "Sólo las diferencias de media categoría o más. Rojo: malo para ti; verde: bueno.",
              )}
            </p>
          )}
        </div>
      ) : (
        dicho && (
          <p className="text-xs text-[var(--muted)]">
            {autopsia.fuente === "goles"
              ? tx(
                  "Este partido se predijo con los goles de la temporada, sin valoraciones, así que no hay supuestos que comparar.",
                )
              : tx(
                  "Lo que suponíamos de cada lado se guarda desde la versión 7.1.0: este partido es de antes.",
                )}
          </p>
        )
      )}

      <p className="rounded-md border border-dashed border-[var(--border)] px-3 py-2 text-xs text-[var(--muted)]">
        {tx(
          "En un solo partido no se puede separar «el motor se equivocó» de «mala suerte». Eso sólo se ve sumando muchos partidos.",
        )}
      </p>
    </div>
  );
}

export function AutopsiaDelPartido({ parte }: { parte: LastMatchReport }) {
  const autopsia = useMatchAutopsy();
  const detalle = useMatchDetail(parte.htMatchId);
  if (autopsia.isLoading)
    return (
      <Panel title={tx("Autopsia del partido")}>
        <Loading />
      </Panel>
    );
  const a = autopsia.data;
  // Si falla, el parte de arriba sigue: la autopsia no se lleva la pantalla.
  if (autopsia.isError || a == null || a.htMatchId !== parte.htMatchId)
    return null;
  if (a.sinValoraciones)
    return (
      <Panel title={tx("Autopsia del partido")}>
        <Empty>
          {tx(
            "La autopsia necesita las valoraciones del partido, que llegan al sincronizar.",
          )}
        </Empty>
      </Panel>
    );
  return (
    <Panel title={tx("Autopsia del partido")}>
      <div className="space-y-5 p-4">
        <div className="rounded-lg bg-[var(--surface-2)] px-3 py-2.5 text-sm">
          <span className="font-medium">{tx("Veredicto:")}</span>{" "}
          {fraseDelVeredicto(a)}
        </div>
        <QuePaso detalle={detalle.data} autopsia={a} />
        <LaPrediccion autopsia={a} />
      </div>
    </Panel>
  );
}
