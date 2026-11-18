/** Personalizar: las clasificaciones propias del usuario (2026-11-18) y,
 *  dentro de cada una, sus grupos, con cada jugador en uno solo. Se arrastra
 *  la tarjeta a su columna o, en el móvil, se elige en la lista. */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BotonDeBorrado } from "../BotonDeBorrado";
import { PlayerLink } from "../PlayerLink";
import { TEAM_ID } from "../../hooks/useTeam";
import { tx } from "../../i18n/tx";
import { api, errorMessage } from "../../services/api";
import type {
  ClasesDeJugador,
  ClasificacionPropia,
  GrupoPropio,
  JugadorDeClases,
} from "../../services/api";
import { Tabs } from "../Tabs";
import { grupoPropioDe } from "./clasificaciones";
import { COLORES_DE_GRUPO, COLOR } from "./colores";
import { Punto } from "./comun";
import { useClasificacionPropiaElegida } from "./elegida";

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
  grupoActual,
  grupos,
  onMover,
}: {
  jugador: JugadorDeClases;
  grupoActual: number | null;
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
          value={grupoActual ?? SIN_GRUPO}
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
  grupoActual,
  grupos,
  onSoltar,
  onMover,
  cabecera,
}: {
  titulo: string;
  color: string;
  jugadores: JugadorDeClases[];
  /** El grupo de los de esta columna; null en «Sin grupo». */
  grupoActual: number | null;
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
              grupoActual={grupoActual}
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

/** Crear, renombrar y borrar clasificaciones propias, y elegir cuál se
 *  edita debajo. */
function ElegirClasificacion({
  datos,
  elegida,
  onElegir,
}: {
  datos: ClasesDeJugador;
  elegida: ClasificacionPropia | undefined;
  onElegir: (id: number | null) => void;
}) {
  const qc = useQueryClient();
  const [nueva, setNueva] = useState("");
  const [renombrando, setRenombrando] = useState(false);
  const [nombre, setNombre] = useState("");
  const refrescar = () =>
    qc.invalidateQueries({ queryKey: ["player-classes"] });
  const crear = useMutation({
    mutationFn: () => api.createPlayerClassification(TEAM_ID, nueva.trim()),
    onSuccess: (c) => {
      setNueva("");
      onElegir(c.id);
      void refrescar();
    },
  });
  const renombrar = useMutation({
    mutationFn: (v: { id: number; name: string }) =>
      api.renamePlayerClassification(TEAM_ID, v.id, v.name),
    onSuccess: () => {
      setRenombrando(false);
      void refrescar();
    },
  });
  const borrar = useMutation({
    mutationFn: (id: number) => api.deletePlayerClassification(TEAM_ID, id),
    onSuccess: () => {
      onElegir(null);
      void refrescar();
    },
  });
  const error = crear.error ?? renombrar.error ?? borrar.error;
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {datos.classifications.length > 0 && (
          <Tabs
            modo="filtro"
            label={tx("Tus clasificaciones")}
            tabs={datos.classifications.map((c) => ({
              key: String(c.id),
              label: c.classificationName,
            }))}
            active={elegida ? String(elegida.id) : ""}
            onChange={(k) => onElegir(Number(k))}
          />
        )}
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (nueva.trim()) crear.mutate();
          }}
        >
          <input
            value={nueva}
            maxLength={40}
            onChange={(e) => setNueva(e.target.value)}
            placeholder={tx("Mercado, Rol…")}
            aria-label={tx("Nombre de la clasificación nueva")}
            className="w-40 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-sm"
          />
          <button
            type="submit"
            disabled={!nueva.trim() || crear.isPending}
            className="rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium disabled:opacity-50"
          >
            {tx("+ Clasificación")}
          </button>
        </form>
      </div>
      {elegida && (
        <div className="flex flex-wrap items-center gap-3 text-xs">
          {renombrando ? (
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (nombre.trim())
                  renombrar.mutate({ id: elegida.id, name: nombre.trim() });
              }}
            >
              <input
                autoFocus
                value={nombre}
                maxLength={40}
                onChange={(e) => setNombre(e.target.value)}
                aria-label={tx("Nombre de la clasificación")}
                className="w-40 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm"
              />
              <button
                type="submit"
                className="font-medium text-[var(--accent)]"
              >
                {tx("Guardar")}
              </button>
              <button
                type="button"
                onClick={() => setRenombrando(false)}
                className="text-[var(--muted)]"
              >
                {tx("Cancelar")}
              </button>
            </form>
          ) : (
            <button
              type="button"
              onClick={() => {
                setNombre(elegida.classificationName);
                setRenombrando(true);
              }}
              className="text-[var(--muted)] hover:text-[var(--text)]"
            >
              {tx("Renombrar «{{c}}»", { c: elegida.classificationName })}
            </button>
          )}
          <BotonDeBorrado
            onConfirmar={() => borrar.mutate(elegida.id)}
            className="text-[var(--muted)] hover:text-[var(--danger)]"
            confirmacion={tx("¿Borrar «{{c}}» y sus grupos?", {
              c: elegida.classificationName,
            })}
          >
            {tx("Borrar «{{c}}»", { c: elegida.classificationName })}
          </BotonDeBorrado>
        </div>
      )}
      {error && (
        <p className="text-sm text-[var(--danger)]">{errorMessage(error)}</p>
      )}
    </div>
  );
}

/** Los grupos de UNA clasificación propia, como tablero. */
function Tablero({
  datos,
  clasificacion,
}: {
  datos: ClasesDeJugador;
  clasificacion: ClasificacionPropia;
}) {
  const qc = useQueryClient();
  const [nombre, setNombre] = useState("");
  const [color, setColor] = useState("blue");
  const refrescar = () =>
    qc.invalidateQueries({ queryKey: ["player-classes"] });
  const cid = clasificacion.id;
  const grupos = clasificacion.groups;

  const crear = useMutation({
    mutationFn: () => api.createPlayerGroup(TEAM_ID, cid, nombre.trim(), color),
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
      api.setPlayerGroup(TEAM_ID, v.htPlayerId, cid, v.groupId),
    onSuccess: refrescar,
  });
  const error = crear.error ?? cambiar.error ?? borrar.error ?? mover.error;

  const porNombre = [...datos.players].sort((a, b) =>
    a.name.localeCompare(b.name),
  );
  const sinGrupo = porNombre.filter((j) => grupoPropioDe(j, cid) == null);
  const moverA = (htPlayerId: number, groupId: number | null) =>
    mover.mutate({ htPlayerId, groupId });

  return (
    <div className="space-y-4">
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
          grupoActual={null}
          grupos={grupos}
          onSoltar={(id) => moverA(id, null)}
          onMover={moverA}
        />
        {grupos.map((g) => (
          <div key={g.id} className="relative">
            <Columna
              titulo={g.groupName}
              color={COLORES_DE_GRUPO[g.color] ?? COLOR.gris}
              jugadores={porNombre.filter(
                (j) => grupoPropioDe(j, cid) === g.id,
              )}
              grupoActual={g.id}
              grupos={grupos}
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

export function Personalizar({ datos }: { datos: ClasesDeJugador }) {
  const [elegidaId, setElegidaId] = useClasificacionPropiaElegida();
  const elegida =
    datos.classifications.find((c) => c.id === elegidaId) ??
    datos.classifications[0];
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Crea tus clasificaciones (por ejemplo «Mercado» o «Rol»), dale a cada una sus grupos con nombre y color, y arrastra a cada jugador al suyo. Dentro de una clasificación, un jugador va en un solo grupo. Cada clasificación es también una columna en Jugadores.",
        )}
      </p>
      <ElegirClasificacion
        datos={datos}
        elegida={elegida}
        onElegir={setElegidaId}
      />
      {elegida ? (
        <Tablero key={elegida.id} datos={datos} clasificacion={elegida} />
      ) : (
        <p className="text-sm text-[var(--muted)]">
          {tx("Empieza creando una clasificación.")}
        </p>
      )}
    </div>
  );
}
