/** Etapa de carrera: una fila por edad, con el dato que decide la etapa de
 *  cada uno al lado de su nombre. Es la misma etapa de la ficha. */
import { tx } from "../../i18n/tx";
import type {
  ClasesDeJugador,
  EtapaDeCarrera,
  JugadorDeClases,
  ReglasDeEtapa,
} from "../../services/api";
import { ETAPAS_DE_CARRERA, nombreDeEtapa } from "../../utils/etapasDeCarrera";
import { COLOR, type Grupo } from "./colores";
import { ListaDeGrupos, Punto } from "./comun";

/** El color de cada etapa; los nombres salen de `utils/etapasDeCarrera`. */
const COLOR_DE_ETAPA: Record<EtapaDeCarrera, string> = {
  promesa: COLOR.verde,
  pico: COLOR.azul,
  rotacion: COLOR.morado,
  veterano: COLOR.naranja,
  declive: COLOR.rojo,
  sin_historial: COLOR.gris,
};

/** Las tres franjas de edad, con los cortes que usa el motor (los manda el
 *  servidor: una copia escrita aquí se quedaría vieja si cambiaran). */
function franjas(r: ReglasDeEtapa) {
  return [
    {
      titulo: tx("Hasta {{a}} años", { a: r.youngMaxAge }),
      regla: tx("Promesa en desarrollo."),
      color: COLOR.verde,
      entra: (e: number) => e <= r.youngMaxAge,
    },
    {
      titulo: tx("De {{a}} a {{b}} años", {
        a: r.youngMaxAge + 1,
        b: r.peakMaxAge,
      }),
      regla: tx(
        "En su pico; Pieza de rotación si su percentil está por debajo de {{p}}.",
        { p: r.rotationBelowPercentile },
      ),
      color: COLOR.azul,
      entra: (e: number) => e > r.youngMaxAge && e <= r.peakMaxAge,
    },
    {
      titulo: tx("{{a}} años o más", { a: r.peakMaxAge + 1 }),
      regla: tx(
        "Veterano estable; En declive si le bajan más habilidades de las que le suben.",
      ),
      color: COLOR.naranja,
      entra: (e: number) => e > r.peakMaxAge,
    },
  ];
}

/** Lo que decidió su etapa, junto a su nombre. */
function dato(j: JugadorDeClases, r: ReglasDeEtapa): string {
  if (j.etapa.confirmed) return tx("confirmada a mano");
  if (!j.etapa.hasSufficientHistory) return tx("un snapshot");
  if (
    j.ageYears > r.youngMaxAge &&
    j.ageYears <= r.peakMaxAge &&
    j.etapa.percentile != null
  )
    return tx("percentil {{v}}", { v: Math.round(j.etapa.percentile) });
  if (j.ageYears > r.peakMaxAge)
    return `↑${j.etapa.rising} ↓${j.etapa.falling}`;
  return "";
}

export function Etapa({ datos }: { datos: ClasesDeJugador }) {
  const reglas = datos.stageRules;
  const color: Record<string, string> = COLOR_DE_ETAPA;
  const edades = [...new Set(datos.players.map((j) => j.ageYears))].sort(
    (a, b) => a - b,
  );

  // Las columnas de abajo: una por etapa, o dos si la etapa se partió.
  const grupos: Grupo[] = ETAPAS_DE_CARRERA.flatMap((e) => {
    const de = datos.players
      .filter((j) => j.etapa.stage === e.clave)
      .sort((a, b) => a.ageYears - b.ageYears || a.ageDays - b.ageDays);
    const partida = de.some((j) => j.etapa.side != null);
    if (!partida)
      return [
        {
          clave: e.clave,
          nombre: e.nombre(),
          color: COLOR_DE_ETAPA[e.clave],
          jugadores: de,
        },
      ];
    return [
      {
        clave: `${e.clave}-t`,
        nombre: tx("{{etapa}} · titulares", { etapa: e.nombre() }),
        color: COLOR_DE_ETAPA[e.clave],
        jugadores: de.filter((j) => j.etapa.side === "titular"),
      },
      {
        clave: `${e.clave}-s`,
        nombre: tx("{{etapa}} · suplentes", { etapa: e.nombre() }),
        color: COLOR_DE_ETAPA[e.clave],
        jugadores: de.filter((j) => j.etapa.side === "suplente"),
      },
    ];
  });

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "La misma etapa de la ficha de cada jugador; si la corriges a mano allí, manda también aquí. Una etapa con más de {{n}} jugadores se parte en titulares y suplentes.",
          { n: reglas.splitAbove },
        )}
      </p>
      <div className="space-y-3">
        {franjas(reglas).map((f) => {
          const filas = edades.filter(f.entra);
          if (filas.length === 0) return null;
          return (
            <section
              key={f.titulo}
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
                  {f.titulo}
                </h3>
                <p className="text-xs text-[var(--muted)]">{f.regla}</p>
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
                            title={`${j.name} · ${nombreDeEtapa(j.etapa.stage)}`}
                          >
                            <Punto color={color[j.etapa.stage] ?? COLOR.gris} />
                            {j.shortName}
                            {dato(j, reglas) && (
                              <span className="text-xs text-[var(--muted)]">
                                {dato(j, reglas)}
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
        )}{" "}
        {tx(
          "A cualquier edad, con un solo snapshot no hay tendencia que mirar y la etapa es Sin historial suficiente.",
        )}
      </p>
      <ListaDeGrupos grupos={grupos} />
    </div>
  );
}
