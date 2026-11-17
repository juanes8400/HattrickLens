/** Etapa de carrera: una fila por edad, con el dato que decide la etapa de
 *  cada uno al lado de su nombre. Es la misma etapa de la ficha. */
import { tx } from "../../i18n/tx";
import type {
  ClasesDeJugador,
  EtapaDeCarrera,
  JugadorDeClases,
} from "../../services/api";
import { COLOR, type Grupo } from "./colores";
import { ListaDeGrupos, Punto } from "./comun";

const ETAPAS: { clave: EtapaDeCarrera; nombre: () => string; color: string }[] =
  [
    {
      clave: "promesa",
      nombre: () => tx("Promesa en desarrollo"),
      color: COLOR.verde,
    },
    { clave: "pico", nombre: () => tx("En su pico"), color: COLOR.azul },
    {
      clave: "rotacion",
      nombre: () => tx("Pieza de rotación"),
      color: COLOR.morado,
    },
    {
      clave: "veterano",
      nombre: () => tx("Veterano estable"),
      color: COLOR.naranja,
    },
    { clave: "declive", nombre: () => tx("En declive"), color: COLOR.rojo },
    {
      clave: "sin_historial",
      nombre: () => tx("Sin historial suficiente"),
      color: COLOR.gris,
    },
  ];

const FRANJAS: {
  titulo: () => string;
  regla: () => string;
  color: string;
  entra: (edad: number) => boolean;
}[] = [
  {
    titulo: () => tx("Hasta 21 años"),
    regla: () =>
      tx("Promesa en desarrollo, o Sin historial si sólo hay un snapshot."),
    color: COLOR.verde,
    entra: (e) => e <= 21,
  },
  {
    titulo: () => tx("De 22 a 27 años"),
    regla: () =>
      tx(
        "En su pico con percentil 60 o más; Pieza de rotación con menos de 40.",
      ),
    color: COLOR.azul,
    entra: (e) => e >= 22 && e <= 27,
  },
  {
    titulo: () => tx("28 años o más"),
    regla: () =>
      tx(
        "Veterano estable; En declive si le bajan más habilidades de las que le suben.",
      ),
    color: COLOR.naranja,
    entra: (e) => e >= 28,
  },
];

/** Lo que decidió su etapa, junto a su nombre. */
function dato(j: JugadorDeClases): string {
  if (j.etapa.confirmed) return tx("confirmada a mano");
  if (!j.etapa.hasSufficientHistory) return tx("un snapshot");
  if (j.ageYears >= 22 && j.ageYears <= 27 && j.etapa.percentile != null)
    return tx("percentil {{v}}", { v: Math.round(j.etapa.percentile) });
  if (j.ageYears >= 28) return `↑${j.etapa.rising} ↓${j.etapa.falling}`;
  return "";
}

export function Etapa({ datos }: { datos: ClasesDeJugador }) {
  const color = Object.fromEntries(ETAPAS.map((e) => [e.clave, e.color]));
  const edades = [...new Set(datos.players.map((j) => j.ageYears))].sort(
    (a, b) => a - b,
  );

  // Las columnas de abajo: una por etapa, o dos si la etapa se partió.
  const grupos: Grupo[] = ETAPAS.flatMap((e) => {
    const de = datos.players
      .filter((j) => j.etapa.stage === e.clave)
      .sort((a, b) => a.ageYears - b.ageYears || a.ageDays - b.ageDays);
    const partida = de.some((j) => j.etapa.side != null);
    if (!partida)
      return [
        { clave: e.clave, nombre: e.nombre(), color: e.color, jugadores: de },
      ];
    return [
      {
        clave: `${e.clave}-t`,
        nombre: tx("{{etapa}} · titulares", { etapa: e.nombre() }),
        color: e.color,
        jugadores: de.filter((j) => j.etapa.side === "titular"),
      },
      {
        clave: `${e.clave}-s`,
        nombre: tx("{{etapa}} · suplentes", { etapa: e.nombre() }),
        color: e.color,
        jugadores: de.filter((j) => j.etapa.side === "suplente"),
      },
    ];
  });

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "La misma etapa de la ficha de cada jugador; si la corriges a mano allí, manda también aquí. Una etapa con más de 11 jugadores se parte en titulares y suplentes.",
        )}
      </p>
      <div className="space-y-3">
        {FRANJAS.map((f) => {
          const filas = edades.filter(f.entra);
          if (filas.length === 0) return null;
          return (
            <section
              key={f.titulo()}
              className="grid gap-x-4 gap-y-2 rounded-lg p-3 md:grid-cols-[14rem_1fr]"
              style={{
                background: `color-mix(in srgb, ${f.color} 7%, transparent)`,
              }}
            >
              <div>
                <h3
                  className="text-sm font-semibold"
                  style={{ color: f.color }}
                >
                  {f.titulo()}
                </h3>
                <p className="text-xs text-[var(--muted)]">{f.regla()}</p>
              </div>
              <div className="space-y-1.5">
                {filas.map((edad) => (
                  <div key={edad} className="flex items-start gap-3">
                    <span className="w-6 shrink-0 pt-1 text-right text-sm text-[var(--muted)]">
                      {edad}
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {datos.players
                        .filter((j) => j.ageYears === edad)
                        .sort((a, b) => a.ageDays - b.ageDays)
                        .map((j) => (
                          <span
                            key={j.htPlayerId}
                            className="inline-flex items-center gap-1.5 rounded-full border bg-[var(--surface)] px-2.5 py-1 text-sm"
                            style={{ borderColor: color[j.etapa.stage] }}
                            title={`${j.name} · ${ETAPAS.find((e) => e.clave === j.etapa.stage)?.nombre() ?? ""}`}
                          >
                            <Punto color={color[j.etapa.stage] ?? COLOR.gris} />
                            {j.shortName}
                            {dato(j) && (
                              <span className="text-xs text-[var(--muted)]">
                                {dato(j)}
                              </span>
                            )}
                          </span>
                        ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
      <p className="text-xs text-[var(--muted)]">
        {tx(
          "↑ y ↓: de sus habilidades principales, cuántas subieron y cuántas bajaron desde el primer snapshot guardado.",
        )}
      </p>
      <ListaDeGrupos grupos={grupos} />
    </div>
  );
}
