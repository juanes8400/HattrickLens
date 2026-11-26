/** Distribución del salario (2026-11-18, nombre del usuario): a qué grupo de
 *  cada clasificación se va el salario semanal de la plantilla.
 *
 *  Es una suma, no un modelo: el salario de cada jugador, tal como lo da su
 *  ficha, repartido según la clase que ya calcula `/player-classes`. Vive en
 *  Jugadores, pestaña «Salario por grupo», desde la 8.0.0 (2026-11-26); antes
 *  era la tercera pestaña de Profundidad de plantilla. */
import { useState } from "react";
import { ErrorState, Loading, Panel } from "../Panels";
import { Tabs } from "../Tabs";
import { money, number } from "../../hooks/useFormat";
import { usePlayerClasses } from "../../hooks/useTeam";
import i18n from "../../i18n";
import { tx } from "../../i18n/tx";
import { clasificacionesElegibles } from "./filtro";
import { Punto } from "./comun";
import { repartoDelSalario } from "./reparto";

export function DistribucionDelSalario() {
  const { data, isLoading, isError, error } = usePlayerClasses();
  const [clave, setClave] = useState("rentabilidad");
  if (isLoading) return <Loading />;
  if (isError || !data) return <ErrorState error={error} />;

  const lista = clasificacionesElegibles(data);
  const elegida = lista.find((c) => c.clave === clave) ?? lista[0];
  if (!elegida) return null;
  const { total, partes } = repartoDelSalario(elegida.grupos);
  const moneda = data.currency;

  return (
    <Panel
      title={tx("A quién va el salario, por clase")}
      meta={tx("{{total}} por semana", { total: money(total, moneda) })}
      acciones={
        <Tabs
          modo="filtro"
          label={i18n.t("modulos.jugadores.clasificacion", "Clasificación")}
          tabs={lista.map((c) => ({ key: c.clave, label: c.nombre }))}
          active={elegida.clave}
          onChange={setClave}
        />
      }
    >
      <div className="space-y-4 p-4">
        {/* La barra suma el 100 % del salario semanal. Cada tramo lleva un
            hueco de 2px del color de fondo, para que dos grupos vecinos no
            se confundan aunque sus colores se parezcan. */}
        <div
          className="flex h-6 w-full gap-[2px] overflow-hidden rounded"
          role="img"
          aria-label={tx("Reparto del salario semanal por {{clasificacion}}", {
            clasificacion: elegida.nombre,
          })}
        >
          {partes
            .filter((p) => p.salario > 0)
            .map((p) => (
              <div
                key={p.grupo.clave}
                className="h-full first:rounded-l last:rounded-r"
                style={{ width: `${p.pct}%`, background: p.grupo.color }}
                title={`${p.grupo.nombre} · ${Math.round(p.pct)} % · ${money(p.salario, moneda)}`}
              />
            ))}
        </div>
        <ul className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {partes.map((p) => (
            <li
              key={p.grupo.clave}
              className="flex items-baseline gap-2 text-sm"
            >
              <Punto color={p.grupo.color} />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{p.grupo.nombre}</span>{" "}
                <span className="text-[var(--muted)]">
                  ·{" "}
                  {tx("{{n}} jugadores", {
                    n: number(p.grupo.jugadores.length),
                  })}
                </span>
              </span>
              <span className="tabular-nums">{money(p.salario, moneda)}</span>
              <span className="w-12 text-right font-medium tabular-nums">
                {`${Math.round(p.pct)} %`}
              </span>
            </li>
          ))}
        </ul>
        <p className="text-xs text-[var(--muted)]">
          {tx(
            "El salario semanal de cada jugador, sumado por grupo. Los grupos son los de Clasificación de jugadores.",
          )}
        </p>
      </div>
    </Panel>
  );
}
