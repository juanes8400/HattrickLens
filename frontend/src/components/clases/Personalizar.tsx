/** Personalizar: grupos que crea el usuario, y cada jugador en uno solo.
 *  Se arrastra la tarjeta a su columna o, en el móvil, se elige en la lista. */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BotonDeBorrado } from "../BotonDeBorrado";
import { PlayerLink } from "../PlayerLink";
import { TEAM_ID } from "../../hooks/useTeam";
import { tx } from "../../i18n/tx";
import { api, errorMessage } from "../../services/api";
import type {
  ClasesDeJugador,
  GrupoPropio,
  JugadorDeClases,
} from "../../services/api";
import { COLORES_DE_GRUPO, COLOR } from "./colores";
import { Punto } from "./comun";

const SIN_GRUPO = "sin";

function ElegirColor({
  valor,
  onChange,
}: {
  valor: string;
  onChange: (color: string) => void;
}) {
  return (
    <div
      className="flex gap-1"
      role="radiogroup"
      aria-label={tx("Color del grupo")}
    >
      {Object.entries(COLORES_DE_GRUPO).map(([clave, css]) => (
        <button
          key={clave}
          type="button"
          role="radio"
          aria-checked={valor === clave}
          aria-label={clave}
          onClick={() => onChange(clave)}
          className="h-5 w-5 rounded-full border-2"
          style={{
            background: css,
            borderColor: valor === clave ? "var(--text)" : "transparent",
          }}
        />
      ))}
    </div>
  );
}

function Tarjeta({
  jugador,
  grupos,
  onMover,
}: {
  jugador: JugadorDeClases;
  grupos: GrupoPropio[];
  onMover: (groupId: number | null) => void;
}) {
  return (
    <li
      draggable
      onDragStart={(e) =>
        e.dataTransfer.setData("text/plain", String(jugador.htPlayerId))
      }
      className="flex cursor-grab items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-sm active:cursor-grabbing"
    >
      <span aria-hidden className="text-[var(--muted)]">
        ⋮⋮
      </span>
      <span className="min-w-0 flex-1 truncate">
        <PlayerLink htPlayerId={jugador.htPlayerId} name={jugador.name} />
      </span>
      <span className="shrink-0 text-xs text-[var(--muted)]">
        {jugador.ageYears}
      </span>
      {grupos.length > 0 && (
        <select
          aria-label={tx("Mover a {{jugador}} a otro grupo", {
            jugador: jugador.name,
          })}
          value={jugador.groupId ?? SIN_GRUPO}
          onChange={(e) =>
            onMover(
              e.target.value === SIN_GRUPO ? null : Number(e.target.value),
            )
          }
          className="max-w-[7rem] shrink-0 rounded border border-[var(--border)] bg-[var(--surface)] px-1 py-0.5 text-xs"
        >
          <option value={SIN_GRUPO}>{tx("Sin grupo")}</option>
          {grupos.map((g) => (
            <option key={g.id} value={g.id}>
              {g.groupName}
            </option>
          ))}
        </select>
      )}
    </li>
  );
}

function Columna({
  titulo,
  color,
  jugadores,
  grupos,
  onSoltar,
  onMover,
  cabecera,
}: {
  titulo: string;
  color: string;
  jugadores: JugadorDeClases[];
  grupos: GrupoPropio[];
  onSoltar: (htPlayerId: number) => void;
  onMover: (htPlayerId: number, groupId: number | null) => void;
  cabecera?: React.ReactNode;
}) {
  const [encima, setEncima] = useState(false);
  return (
    <section
      onDragOver={(e) => {
        e.preventDefault();
        setEncima(true);
      }}
      onDragLeave={() => setEncima(false)}
      onDrop={(e) => {
        e.preventDefault();
        setEncima(false);
        const id = Number(e.dataTransfer.getData("text/plain"));
        if (id) onSoltar(id);
      }}
      className="min-w-0 rounded-lg border p-2.5"
      style={{
        background: "var(--surface-2)",
        borderColor: encima ? color : "var(--border)",
      }}
    >
      <header className="mb-2 flex items-center gap-2">
        <Punto color={color} />
        <h3 className="min-w-0 flex-1 truncate text-sm font-semibold">
          {titulo}{" "}
          <span className="font-normal text-[var(--muted)]">
            · {jugadores.length}
          </span>
        </h3>
        {cabecera}
      </header>
      {jugadores.length === 0 ? (
        <p className="px-1 py-3 text-center text-xs text-[var(--muted)]">
          {tx("Arrastra aquí a un jugador.")}
        </p>
      ) : (
        <ul className="space-y-1.5">
          {jugadores.map((j) => (
            <Tarjeta
              key={j.htPlayerId}
              jugador={j}
              grupos={grupos}
              onMover={(g) => onMover(j.htPlayerId, g)}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function CabeceraDeGrupo({
  grupo,
  onCambiar,
  onBorrar,
}: {
  grupo: GrupoPropio;
  onCambiar: (cambio: { name?: string; color?: string }) => void;
  onBorrar: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [nombre, setNombre] = useState(grupo.groupName);
  const [color, setColor] = useState(grupo.color);
  if (editando) {
    return (
      <form
        className="absolute inset-x-2 top-2 z-10 space-y-2 rounded-md border border-[var(--border)] bg-[var(--surface)] p-2 shadow-md"
        onSubmit={(e) => {
          e.preventDefault();
          if (nombre.trim()) onCambiar({ name: nombre.trim(), color });
          setEditando(false);
        }}
      >
        <input
          autoFocus
          value={nombre}
          maxLength={40}
          onChange={(e) => setNombre(e.target.value)}
          aria-label={tx("Nombre del grupo")}
          className="w-full rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm"
        />
        <ElegirColor valor={color} onChange={setColor} />
        <div className="flex justify-end gap-2 text-xs">
          <button
            type="button"
            onClick={() => setEditando(false)}
            className="text-[var(--muted)]"
          >
            {tx("Cancelar")}
          </button>
          <button type="submit" className="font-medium text-[var(--accent)]">
            {tx("Guardar")}
          </button>
        </div>
      </form>
    );
  }
  return (
    <span className="flex shrink-0 gap-2 text-xs">
      <button
        type="button"
        onClick={() => setEditando(true)}
        className="text-[var(--muted)] hover:text-[var(--text)]"
      >
        {tx("Renombrar")}
      </button>
      <BotonDeBorrado
        onConfirmar={onBorrar}
        className="text-[var(--muted)] hover:text-[var(--danger)]"
        confirmacion={tx("¿Borrar?")}
      >
        {tx("Borrar")}
      </BotonDeBorrado>
    </span>
  );
}

export function Personalizar({ datos }: { datos: ClasesDeJugador }) {
  const qc = useQueryClient();
  const [nombre, setNombre] = useState("");
  const [color, setColor] = useState("blue");
  const refrescar = () =>
    qc.invalidateQueries({ queryKey: ["player-classes"] });

  const crear = useMutation({
    mutationFn: () => api.createPlayerGroup(TEAM_ID, nombre.trim(), color),
    onSuccess: () => {
      setNombre("");
      void refrescar();
    },
  });
  const cambiar = useMutation({
    mutationFn: (v: {
      id: number;
      cambio: { name?: string; color?: string };
    }) => api.updatePlayerGroup(TEAM_ID, v.id, v.cambio),
    onSuccess: refrescar,
  });
  const borrar = useMutation({
    mutationFn: (id: number) => api.deletePlayerGroup(TEAM_ID, id),
    onSuccess: refrescar,
  });
  const mover = useMutation({
    mutationFn: (v: { htPlayerId: number; groupId: number | null }) =>
      api.setPlayerGroup(TEAM_ID, v.htPlayerId, v.groupId),
    onSuccess: refrescar,
  });
  const error = crear.error ?? cambiar.error ?? borrar.error ?? mover.error;

  const porNombre = [...datos.players].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  const sinGrupo = porNombre.filter((j) => j.groupId == null);
  const moverA = (htPlayerId: number, groupId: number | null) =>
    mover.mutate({ htPlayerId, groupId });

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Crea tus grupos, ponles nombre y color, y arrastra a cada jugador al suyo. Un jugador va en un solo grupo.",
        )}
      </p>
      <form
        className="flex flex-wrap items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (nombre.trim()) crear.mutate();
        }}
      >
        <input
          value={nombre}
          maxLength={40}
          onChange={(e) => setNombre(e.target.value)}
          placeholder={tx("Nombre del grupo nuevo")}
          aria-label={tx("Nombre del grupo nuevo")}
          className="w-52 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-sm"
        />
        <ElegirColor valor={color} onChange={setColor} />
        <button
          type="submit"
          disabled={!nombre.trim() || crear.isPending}
          className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
        >
          {tx("+ Grupo")}
        </button>
      </form>
      {error && (
        <p className="text-sm text-[var(--danger)]">{errorMessage(error)}</p>
      )}
      <div
        className="grid gap-3"
        style={{ gridTemplateColumns: "repeat(auto-fill, minmax(15rem, 1fr))" }}
      >
        <Columna
          titulo={tx("Sin grupo")}
          color={COLOR.gris}
          jugadores={sinGrupo}
          grupos={datos.groups}
          onSoltar={(id) => moverA(id, null)}
          onMover={moverA}
        />
        {datos.groups.map((g) => (
          <div key={g.id} className="relative">
            <Columna
              titulo={g.groupName}
              color={COLORES_DE_GRUPO[g.color] ?? COLOR.gris}
              jugadores={porNombre.filter((j) => j.groupId === g.id)}
              grupos={datos.groups}
              onSoltar={(id) => moverA(id, g.id)}
              onMover={moverA}
              cabecera={
                <CabeceraDeGrupo
                  grupo={g}
                  onCambiar={(cambio) => cambiar.mutate({ id: g.id, cambio })}
                  onBorrar={() => borrar.mutate(g.id)}
                />
              }
            />
          </div>
        ))}
      </div>
    </div>
  );
}
