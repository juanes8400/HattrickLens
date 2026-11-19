/**
 * «Enviar a Hattrick», en Alineación (2026-11-19, pedido del usuario).
 *
 * Con el once que se está viendo se eligen táctica, capitán, lanzador de
 * tiros libres y el orden de los lanzadores de penales, y se manda a
 * Hattrick EN DOS TIEMPOS:
 *
 * 1. «Ver ratings en Hattrick»: Hattrick calcula los siete ratings de esa
 *    alineación y no guarda nada.
 * 2. «Enviar a Hattrick», con confirmación: sustituye las órdenes de ese
 *    partido. Después el servidor las vuelve a leer y dice si quedaron como
 *    se mandaron.
 *
 * Lo que la app no propone --actitud, estilo del entrenador, marcaje y cambios
 * programados-- se conserva tal y como esté en Hattrick.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { date } from "../../hooks/useFormat";
import { TEAM_ID, usePartidosParaEnviar } from "../../hooks/useTeam";
import { nivelOficial, terminoOficial } from "../../i18n/glosario";
import { tx } from "../../i18n/tx";
import {
  ApiError,
  api,
  type Lineup,
  type RespuestaDeEnvio,
} from "../../services/api";
import { Panel } from "../Panels";

/** Los siete sectores que prevé Hattrick, con su nombre oficial. */
const SECTORES: [string, string, string][] = [
  ["midfield", "Midfield", "Mediocampo"],
  ["right_def", "RightDefense", "Defensa derecha"],
  ["central_def", "CentralDefense", "Defensa central"],
  ["left_def", "LeftDefense", "Defensa izquierda"],
  ["right_att", "RightAttack", "Ataque derecho"],
  ["central_att", "CentralAttack", "Ataque central"],
  ["left_att", "LeftAttack", "Ataque izquierdo"],
];

const selectClase =
  "w-full rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm";

export function EnviarAHattrick({
  lineup,
  ordenes,
  fuera,
}: {
  lineup: Lineup;
  /** Las órdenes individuales fijadas a mano, como las pide `/lineup`. */
  ordenes: Record<number, string>;
  /** Quién quedó fuera del reparto. */
  fuera: number[];
}) {
  const qc = useQueryClient();
  const partidos = usePartidosParaEnviar();
  const once = lineup.lineup;
  const roles = lineup.roles;
  const [partido, setPartido] = useState<number | null>(null);
  const [tactica, setTactica] = useState(0);
  const [capitan, setCapitan] = useState(roles?.captain?.htPlayerId ?? 0);
  const [tiroLibre, setTiroLibre] = useState(roles?.setPieces?.htPlayerId ?? 0);
  const [penales, setPenales] = useState<number[]>(
    (roles?.penaltyTakers ?? []).map((p) => p.htPlayerId),
  );
  const [confirmando, setConfirmando] = useState(false);
  const [prevision, setPrevision] = useState<RespuestaDeEnvio | null>(null);
  const [envio, setEnvio] = useState<RespuestaDeEnvio | null>(null);

  // QUÉ PERMISOS TIENE DE VERDAD TU ACCESO (2026-11-19). Tras reconectar,
  // el envío seguía pidiendo el permiso y no había forma de saber por qué:
  // se le pregunta a Hattrick y, si falta, se ofrece reconectar aquí mismo.
  const permisos = useQuery({
    queryKey: ["permisos-de-hattrick"],
    queryFn: api.permisosDeHattrick,
    staleTime: 60_000,
  });
  const sinPermiso = permisos.data?.puedeEnviarAlineacion === false;
  const reconectar = useMutation({
    mutationFn: api.connectChpp,
    onSuccess: ({ authorizeUrl }) => window.location.assign(authorizeUrl),
  });

  const lista = partidos.data?.matches ?? [];
  const elegido = lista.find((p) => p.htMatchId === partido) ?? lista[0];
  const nombre = new Map(once.map((f) => [f.htPlayerId, f.player]));

  const mandar = useMutation({
    mutationFn: (guardar: boolean) =>
      api.enviarAlineacion(TEAM_ID, {
        htMatchId: elegido!.htMatchId,
        formation: lineup.formation,
        centralDefenders: lineup.centralDefenders,
        innerMidfielders: lineup.innerMidfielders,
        orders:
          Object.entries(ordenes)
            .map(([casilla, pos]) => `${casilla}:${pos}`)
            .join(",") || null,
        exclude: fuera.join(",") || null,
        tactica,
        capitan,
        tiroLibre,
        penales,
        titulares: once.map((f) => f.htPlayerId),
        guardar,
      }),
    onSuccess: (r) => {
      if (r.guardar) {
        setEnvio(r);
        setConfirmando(false);
        // Partidos, Rivales y el Dashboard dicen si hay órdenes enviadas.
        qc.invalidateQueries();
      } else {
        setPrevision(r);
        setEnvio(null);
      }
    },
  });

  const mover = (indice: number, paso: -1 | 1) =>
    setPenales((actual) => {
      const nuevo = [...actual];
      const otro = indice + paso;
      if (otro < 0 || otro >= nuevo.length) return actual;
      const este = nuevo[indice]!;
      nuevo[indice] = nuevo[otro]!;
      nuevo[otro] = este;
      return nuevo;
    });

  const nombreDeTactica = (code: number, label: string) =>
    nivelOficial("tacticas", code) ?? tx(label);
  const tactica_ = partidos.data?.tactics ?? [];
  const tacticaPrevia =
    prevision?.tacticaPrevia != null
      ? (tactica_.find((t) => t.code === prevision.tacticaPrevia)?.label ??
        String(prevision.tacticaPrevia))
      : null;

  const error = mandar.error;
  const faltaElPermiso =
    sinPermiso || (error instanceof ApiError && error.status === 403);
  const mensajeDeError =
    error instanceof ApiError && error.status === 403
      ? tx(
          "Hattrick no deja enviar la alineación con tu acceso actual. Reconecta con Hattrick para darle a Hattrick Lens el permiso de órdenes de partido.",
        )
      : error
        ? error.message
        : null;

  return (
    <Panel
      title={tx("Enviar a Hattrick")}
      meta={tx("primero ves los ratings; enviar lo confirmas tú")}
    >
      <div className="space-y-4 p-4 text-sm">
        {partidos.isLoading ? (
          <p className="text-[var(--muted)]">{tx("Cargando partidos…")}</p>
        ) : lista.length === 0 ? (
          <p className="text-[var(--muted)]">
            {tx("No tienes ningún partido pendiente al que enviar alineación.")}
          </p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">
                  {tx("Partido")}
                </span>
                <select
                  className={selectClase}
                  value={elegido?.htMatchId ?? ""}
                  onChange={(e) => {
                    setPartido(Number(e.target.value));
                    setPrevision(null);
                    setEnvio(null);
                  }}
                >
                  {lista.map((p) => (
                    <option key={p.htMatchId} value={p.htMatchId}>
                      {date(p.playedAt)} · {p.tournament} ·{" "}
                      {p.isHome ? tx("en casa") : tx("fuera")} · {p.rival}
                      {p.ordersGiven ? ` · ${tx("órdenes ya enviadas")}` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">
                  {tx("Táctica")}
                </span>
                <select
                  className={selectClase}
                  value={tactica}
                  onChange={(e) => setTactica(Number(e.target.value))}
                >
                  {tactica_.map((t) => (
                    <option key={t.code} value={t.code}>
                      {nombreDeTactica(t.code, t.label)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">
                  {tx("Capitán")}
                  {roles?.captain && (
                    <span>
                      {" "}
                      · {tx("sugerido")}: {roles.captain.player}
                    </span>
                  )}
                </span>
                <select
                  className={selectClase}
                  value={capitan}
                  onChange={(e) => setCapitan(Number(e.target.value))}
                >
                  {once.map((f) => (
                    <option key={f.htPlayerId} value={f.htPlayerId}>
                      {f.player}
                    </option>
                  ))}
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-xs text-[var(--muted)]">
                  {tx("Tiros libres")}
                  {roles?.setPieces && (
                    <span>
                      {" "}
                      · {tx("sugerido")}: {roles.setPieces.player}
                    </span>
                  )}
                </span>
                <select
                  className={selectClase}
                  value={tiroLibre}
                  onChange={(e) => setTiroLibre(Number(e.target.value))}
                >
                  {once.map((f) => (
                    <option key={f.htPlayerId} value={f.htPlayerId}>
                      {f.player}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-[var(--muted)]">
                {tx(
                  "Lanzadores de penales, en orden. Sugeridos por experiencia, balón parado y anotación; cámbialos con las flechas.",
                )}
              </div>
              <ol className="divide-y divide-[var(--border)] rounded border border-[var(--border)]">
                {penales.map((id, i) => (
                  <li
                    key={id}
                    className="flex items-center justify-between gap-2 px-2 py-1"
                  >
                    <span>
                      <span className="mr-2 inline-block w-5 text-right tabular-nums text-[var(--muted)]">
                        {i + 1}.
                      </span>
                      {nombre.get(id) ?? id}
                    </span>
                    <span className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => mover(i, -1)}
                        disabled={i === 0}
                        aria-label={tx("Subir")}
                        className="min-h-6 rounded border border-[var(--border)] px-2 text-xs disabled:opacity-40"
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={() => mover(i, 1)}
                        disabled={i === penales.length - 1}
                        aria-label={tx("Bajar")}
                        className="min-h-6 rounded border border-[var(--border)] px-2 text-xs disabled:opacity-40"
                      >
                        ↓
                      </button>
                    </span>
                  </li>
                ))}
              </ol>
            </div>

            <p className="text-xs leading-relaxed text-[var(--muted)]">
              {tx(
                "Se envía el once que ves arriba, con sus órdenes individuales y el banquillo de la app. Tu actitud, el estilo del entrenador, el marcaje y los cambios programados se conservan como estén en Hattrick.",
              )}
            </p>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => mandar.mutate(false)}
                disabled={mandar.isPending || !elegido}
                data-track="Alineación: ver ratings en Hattrick"
                className="rounded-md border border-[var(--border)] px-3 py-1.5 hover:border-[var(--accent)] disabled:opacity-60"
              >
                {mandar.isPending && !confirmando
                  ? tx("Preguntando a Hattrick…")
                  : tx("Ver ratings en Hattrick")}
              </button>
              {!confirmando ? (
                <button
                  type="button"
                  onClick={() => setConfirmando(true)}
                  disabled={mandar.isPending || !elegido || sinPermiso}
                  data-track="Alineación: enviar a Hattrick"
                  className="rounded-md bg-[var(--accent)] px-3 py-1.5 font-medium text-white disabled:opacity-60"
                >
                  {tx("Enviar a Hattrick")}
                </button>
              ) : null}
            </div>

            {confirmando && elegido && (
              <div
                role="alertdialog"
                className="space-y-2 rounded-lg border border-[var(--warning)] bg-[var(--warning)]/10 p-3"
              >
                <p>
                  {tx(
                    "Esto sustituye en Hattrick las órdenes del partido del {{fecha}} contra {{rival}}.",
                    { fecha: date(elegido.playedAt), rival: elegido.rival },
                  )}{" "}
                  {elegido.ordersGiven
                    ? tx("Ese partido ya tiene órdenes enviadas.")
                    : ""}
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => mandar.mutate(true)}
                    disabled={mandar.isPending}
                    data-track="Alineación: confirmar envío"
                    className="rounded-md bg-[var(--accent)] px-3 py-1.5 font-medium text-white disabled:opacity-60"
                  >
                    {mandar.isPending ? tx("Enviando…") : tx("Sí, enviar")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmando(false)}
                    disabled={mandar.isPending}
                    className="rounded-md border border-[var(--border)] px-3 py-1.5"
                  >
                    {tx("Cancelar")}
                  </button>
                </div>
              </div>
            )}

            {mensajeDeError && (
              <p role="alert" className="text-[var(--danger)]">
                {mensajeDeError}
              </p>
            )}

            {faltaElPermiso && (
              <div className="space-y-2 rounded-lg border border-[var(--warning)] bg-[var(--warning)]/10 p-3">
                <p>
                  {tx(
                    "Tu acceso a Hattrick no tiene el permiso de enviar órdenes de partido. Ver los ratings sí funciona; para enviar, reconecta y acepta en la página de Hattrick el permiso de órdenes de partido.",
                  )}
                </p>
                {permisos.data?.permisos && (
                  <p className="text-xs text-[var(--muted)]">
                    {tx(
                      "Lo que Hattrick dice que tiene tu acceso: {{lista}}.",
                      {
                        lista:
                          permisos.data.permisos.join(", ") ||
                          tx("sólo lectura"),
                      },
                    )}
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => reconectar.mutate()}
                  disabled={reconectar.isPending}
                  data-track="Alineación: reconectar para enviar"
                  className="rounded-md bg-[var(--accent)] px-3 py-1.5 font-medium text-white disabled:opacity-60"
                >
                  {tx("Reconectar con Hattrick")}
                </button>
              </div>
            )}

            {prevision && (
              <div className="space-y-2">
                <div className="text-xs font-medium text-[var(--muted)]">
                  {tx("Lo que prevé Hattrick para esta alineación (minuto 0)")}
                </div>
                {prevision.prediccion ? (
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
                    {SECTORES.map(([clave, oficial, respaldo]) => (
                      <div
                        key={clave}
                        className="flex justify-between gap-2 border-b border-[var(--border)] py-0.5"
                      >
                        <dt className="text-[var(--muted)]">
                          {terminoOficial("sectores", oficial, respaldo)}
                        </dt>
                        <dd className="tabular-nums font-medium">
                          {prevision.prediccion![clave]}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="text-[var(--warning)]">
                    {tx("Hattrick no devolvió ratings para esta alineación.")}{" "}
                    {prevision.motivo ?? ""}
                  </p>
                )}
                {prevision.habiaOrdenes && (
                  <p className="text-xs text-[var(--muted)]">
                    {tacticaPrevia
                      ? tx(
                          "Ya hay órdenes enviadas para este partido (táctica: {{tactica}}). Enviar las sustituye.",
                          {
                            tactica: nombreDeTactica(
                              prevision.tacticaPrevia!,
                              tacticaPrevia,
                            ),
                          },
                        )
                      : tx(
                          "Ya hay órdenes enviadas para este partido. Enviar las sustituye.",
                        )}
                  </p>
                )}
                {prevision.cambiosQuitados > 0 && (
                  <p className="text-xs text-[var(--warning)]">
                    {tx(
                      "{{n}} cambio(s) programado(s) nombran a jugadores que no están en este once ni en el banquillo: se quitarán al enviar.",
                      { n: prevision.cambiosQuitados },
                    )}
                  </p>
                )}
              </div>
            )}

            {envio && (
              <p
                role="status"
                className={
                  envio.confirmada
                    ? "text-[var(--positive)]"
                    : "text-[var(--warning)]"
                }
              >
                {envio.confirmada
                  ? tx(
                      "Enviada. Se volvieron a leer las órdenes en Hattrick y son las que mandaste.",
                    )
                  : envio.guardada
                    ? tx(
                        "Hattrick dice que la guardó, pero al releer las órdenes no coinciden. Revísalas en Hattrick.",
                      )
                    : tx("Hattrick no guardó la alineación.") +
                      (envio.motivo ? ` ${envio.motivo}` : "")}
              </p>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}
