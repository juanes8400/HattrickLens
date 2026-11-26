import { EnlaceATransparencia } from "../components/EnlaceATransparencia";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import clsx from "clsx";
import { CountryCell } from "../components/CountryFlag";
import { DataTable, type Column } from "../components/DataTable";
import { Tabs } from "../components/Tabs";
import { ErrorState, Loading, SinDatos } from "../components/Panels";
import { PlayerLink } from "../components/PlayerLink";
import { Specialty } from "../components/Specialty";
import { usePlayerClasses, useSquad } from "../hooks/useTeam";
import { usePersistido } from "../hooks/usePersistido";
import { FiltroDeClases } from "../components/clases/FiltroDeClases";
import { Pastilla } from "../components/clases/comun";
import { grupoPropioDe } from "../components/clases/clasificaciones";
import {
  idsDelFiltro,
  SIN_FILTRO,
  type ValorDelFiltro,
} from "../components/clases/filtro";
import {
  fraseDeEtapa,
  fraseDePropia,
  fraseDeRentabilidad,
  fraseDeTitularidad,
  type Pertenencia,
} from "../components/clases/frases";
import { ETAPAS_DE_CARRERA } from "../utils/etapasDeCarrera";
import { tx } from "../i18n/tx";
import { htAge, money, number, relative } from "../hooks/useFormat";
import { abreviatura } from "../utils/abreviaturas";
import { explicacionesDeLaHolgura, holgura } from "../utils/holgura";
import type {
  ClasesDeJugador,
  JugadorDeClases,
  SquadPlayer,
  VentanaDeComparacion,
} from "../services/api";

const SKILLS = [
  "keeper",
  "defending",
  "playmaking",
  "winger",
  "passing",
  "scoring",
  "set_pieces",
] as const;

const TRAINER_TYPES: Record<number, string> = {
  0: "defensivo",
  1: "ofensivo",
  2: "equilibrado",
};

function signed(value: number | undefined): string {
  if (!value) return "";
  return `${value > 0 ? "+" : ""}${number(value)}`;
}

/** El valor y, pegado a su derecha, cuánto cambió desde el snapshot que se
 *  compara. Un solo renglón: el cambio es un apunte al margen del número, no
 *  otro dato que merezca su propia línea.
 *
 *  Sin cambio no se pinta nada. Antes iba un punto de relleno, que gastaba una
 *  línea en cada celda de la tabla para decir que no había noticia, y como
 *  casi ninguna habilidad se mueve entre dos sincronizaciones, la tabla entera
 *  quedaba al doble de alto para mostrar puntos. */
function MetricCell({ value, delta }: { value: number; delta?: number }) {
  return (
    <span className="inline-flex min-w-12 items-baseline justify-end gap-1 whitespace-nowrap tabular-nums">
      <span>{number(value)}</span>
      {delta ? (
        <span
          className={clsx(
            "text-[10px] font-semibold",
            delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]",
          )}
        >
          {signed(delta)}
        </span>
      ) : null}
    </span>
  );
}

/** Un valor que se lee como palabra pero se mueve como número: el carácter,
 *  la agresividad, la honradez, el nivel de entrenador.
 *
 *  Aquí un «+1» no dice nada --nadie sabe cuánto es un carácter más-- así que
 *  la marca es una flecha: lo que importa es que SE MOVIÓ y hacia dónde. El
 *  cuánto va en el título, para quien lo quiera (2026-09-26). */
function EtiquetaConCambio({
  texto,
  delta,
}: {
  texto: React.ReactNode;
  delta?: number;
}) {
  if (!delta) return <>{texto}</>;
  return (
    <span className="inline-flex items-baseline gap-1 whitespace-nowrap">
      <span>{texto}</span>
      <span
        title={signed(delta)}
        className={clsx(
          "text-[10px] font-semibold",
          delta > 0 ? "text-[var(--positive)]" : "text-[var(--danger)]",
        )}
      >
        {delta > 0 ? "▲" : "▼"}
      </span>
    </span>
  );
}

/** Las ventanas contra las que se pueden mirar las diferencias, con el texto
 *  de cada una. Cuál se puede usar y contra qué cierre compara lo decide el
 *  servidor, que es quien tiene los cierres guardados. */
const VENTANAS: { key: VentanaDeComparacion; clave: string; texto: string }[] =
  [
    { key: "change", clave: "jugadores.ventanaCambio", texto: "Último cambio" },
    { key: "w1", clave: "jugadores.ventana1", texto: "Última semana" },
    { key: "w2", clave: "jugadores.ventana2", texto: "Últimas 2 semanas" },
    { key: "w4", clave: "jugadores.ventana4", texto: "Últimas 4 semanas" },
    { key: "w8", clave: "jugadores.ventana8", texto: "Últimas 8 semanas" },
    { key: "w16", clave: "jugadores.ventana16", texto: "Últimas 16 semanas" },
    { key: "all", clave: "jugadores.ventanaSiempre", texto: "Siempre" },
  ];

/** El orden en que se ordenan las columnas de clase: el de la pantalla de
 *  Clasificación de jugadores, no el alfabético. */
const ORDEN_TITULARIDAD = ["titular", "suplencia", "reserva"];
const ORDEN_RENTABILIDAD = ["estrellas", "gangas", "caros", "economicos"];
const ORDEN_ETAPA = ETAPAS_DE_CARRERA.map((e) => e.clave as string);

/** Una columna de clase (2026-11-18): la pastilla del grupo, el mismo nombre
 *  y color que la tarjeta «Sus clases» de la ficha. Nace `optional` para que
 *  en un móvil empiece oculta, como el resto de columnas que no son las
 *  esenciales. */
function columnaDeClase(
  key: string,
  header: string,
  datos: ClasesDeJugador | undefined,
  porId: Map<number, JugadorDeClases>,
  pertenencia: (d: ClasesDeJugador, j: JugadorDeClases) => Pertenencia | null,
  orden: (j: JugadorDeClases) => number,
): Column<SquadPlayer> {
  const de = (p: SquadPlayer) => {
    const j = porId.get(p.htPlayerId);
    return datos && j ? { j, p: pertenencia(datos, j) } : null;
  };
  return {
    key,
    header,
    align: "left",
    optional: true,
    value: (p) => de(p)?.p?.grupo ?? "",
    sortValue: (p) => {
      const x = de(p);
      return x ? -orden(x.j) : -99;
    },
    render: (p) => {
      const x = de(p)?.p;
      return x ? (
        <span title={x.frase}>
          <Pastilla texto={x.grupo} color={x.color} />
        </span>
      ) : (
        <span className="text-[var(--muted)]">—</span>
      );
    },
  };
}

/**
 * Jugadores es la tabla maestra. La ficha, posiciones y análisis individual
 * viven en /players/:id para no convertir la vista de plantilla en un
 * dashboard de un jugador seleccionado.
 */
export function TeamPage() {
  const { t } = useTranslation();
  // SE GUARDA LA VENTANA, NO EL CIERRE (2026-09-20). Un id de sincronización
  // elegido a mano deja de existir en cuanto entra una semana nueva y sale la
  // vigésima; «cuatro semanas» sigue queriendo decir lo mismo mañana. Contra
  // qué cierre cae cada ventana lo resuelve el servidor.
  const [ventana, setVentana] = useState<VentanaDeComparacion>("change");
  const squad = useSquad(undefined, ventana);
  // Las clases van en su propia petición: si tarda o falla, la tabla sale
  // igual y sus columnas se quedan con un guion.
  const clases = usePlayerClasses();
  const [filtroDeClases, setFiltroDeClases] = usePersistido<ValorDelFiltro>(
    "jugadores.filtro-de-clases",
    SIN_FILTRO,
  );

  if (squad.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (!squad.data) return <SinDatos />;

  const data = squad.data;
  const datosDeClases = clases.data;
  const porId = new Map(
    (datosDeClases?.players ?? []).map((j) => [j.htPlayerId, j]),
  );
  const ids = datosDeClases
    ? idsDelFiltro(datosDeClases, filtroDeClases)
    : null;
  const filas = ids
    ? data.players.filter((p) => ids.has(p.htPlayerId))
    : data.players;
  // 2026-08-16, pedido explícito: aquí NINGUNA columna nace oculta. Es la tabla
  // maestra de la plantilla y quien la abre quiere verlo todo; el selector
  // "Columnas" sigue estando para quitar lo que estorbe. Por eso ninguna lleva
  // `optional`, que en `DataTable` significa "oculta de salida".
  const columns: Column<SquadPlayer>[] = [
    {
      key: "name",
      header: t("jugadores.jugador", "Jugador"),
      align: "left",
      value: (player) => player.name,
      // Sin `nowrap` un nombre de dos palabras parte la fila en dos altos y
      // la tabla entera se lee peor por una sola columna. Se nota sobre todo
      // en un móvil, donde la columna es estrecha y casi todos se parten.
      render: (player) => (
        <span className="whitespace-nowrap">
          <PlayerLink htPlayerId={player.htPlayerId} name={player.name} />
        </span>
      ),
    },
    {
      key: "origin",
      optional: true,
      header: t("jugadores.origen", "Origen"),
      align: "left",
      value: (player) => player.nativeLeagueName ?? String(player.countryId),
      render: (player) => (
        <CountryCell
          code={player.countryCode}
          country={player.nativeLeagueName}
          fallback={`#${player.countryId}`}
        />
      ),
    },
    {
      key: "best",
      header: t("jugadores.mejorPosicion", "Mejor posición"),
      align: "left",
      value: (player) => player.bestPosition.rating,
      render: (player) => (
        <span className="whitespace-nowrap">
          {player.bestPosition.label}{" "}
          <b className="text-[var(--accent)]">
            {player.bestPosition.rating.toFixed(2)}
          </b>
        </span>
      ),
    },
    {
      key: "specialty",
      header: t("jugadores.especialidad", "Especialidad"),
      align: "left",
      // `value` se queda en texto plano: es lo que ordena, lo que filtra el
      // buscador de la tabla y lo que sale al CSV. El icono vive sólo en
      // `render`, donde no puede estorbar ninguna de las tres cosas.
      value: (player) => player.specialty,
      render: (player) => <Specialty specialty={player.specialty} />,
    },
    columnaDeClase(
      "titularidad",
      tx("Titularidad"),
      datosDeClases,
      porId,
      fraseDeTitularidad,
      (j) => ORDEN_TITULARIDAD.indexOf(j.titularidad),
    ),
    columnaDeClase(
      "rentabilidad",
      tx("Rentabilidad deportiva"),
      datosDeClases,
      porId,
      fraseDeRentabilidad,
      (j) => ORDEN_RENTABILIDAD.indexOf(j.rentabilidad),
    ),
    columnaDeClase(
      "etapa",
      tx("Etapa de carrera"),
      datosDeClases,
      porId,
      fraseDeEtapa,
      (j) => ORDEN_ETAPA.indexOf(j.etapa.stage),
    ),
    // UNA COLUMNA POR CLASIFICACIÓN PROPIA (2026-11-18): crear «Mercado»
    // añade la columna «Mercado», borrarla la quita. Sólo las que ya tienen
    // grupos: una columna llena de guiones no diría nada.
    ...(datosDeClases?.classifications ?? [])
      .filter((c) => c.groups.length > 0)
      .map((c) =>
        columnaDeClase(
          `propia-${c.id}`,
          c.classificationName,
          datosDeClases,
          porId,
          (_d, j) => fraseDePropia(c, j),
          (j) => {
            const id = grupoPropioDe(j, c.id);
            return id == null ? 99 : c.groups.findIndex((g) => g.id === id);
          },
        ),
      ),
    {
      key: "lastMatch",
      optional: true,
      header: t("jugadores.ultPartido", "Últ. partido"),
      align: "left",
      value: (player) => player.lastMatchRating ?? -1,
      render: (player) =>
        player.lastMatchPosition ? (
          <span className="whitespace-nowrap">
            {player.lastMatchPosition} ·{" "}
            <b>{player.lastMatchRating?.toFixed(1) ?? "-"}</b>
          </span>
        ) : (
          <span className="text-[var(--muted)]">-</span>
        ),
    },
    {
      key: "market",
      optional: true,
      header: t("jugadores.mercado", "Mercado"),
      align: "left",
      value: (player) => Number(player.isTransferListed),
      render: (player) => (
        <span
          className={clsx(
            "text-xs font-semibold",
            player.isTransferListed
              ? "text-[var(--accent)]"
              : "text-[var(--muted)]",
          )}
        >
          {player.isTransferListed ? t("jugadores.enVenta", "en venta") : "-"}
        </span>
      ),
    },
    // LA HOLGURA PARA VENDER (2026-11-23, pedido del usuario): siempre a la
    // vista, no en el selector de columnas. Ver `utils/holgura.ts`.
    {
      key: "matchesWithClub",
      header: tx("Partidos con el club"),
      headerTitle: explicacionesDeLaHolgura().partidos,
      value: (player) => player.matchesWithClub ?? -1,
      render: (player) =>
        player.matchesWithClub == null ? (
          <span className="text-[var(--muted)]">-</span>
        ) : (
          number(player.matchesWithClub)
        ),
    },
    {
      key: "listingsWithClub",
      header: tx("Veces en venta"),
      headerTitle: explicacionesDeLaHolgura().vecesEnVenta,
      value: (player) => player.listingsWithClub,
      render: (player) => number(player.listingsWithClub),
    },
    {
      key: "holgura",
      header: tx("Holgura"),
      headerTitle: explicacionesDeLaHolgura().holgura,
      // Sin el dato de Hattrick va al final al ordenar de menor a mayor,
      // que es como se busca a quien menos margen le queda.
      value: (player) =>
        holgura(player.matchesWithClub, player.listingsWithClub) ?? 9999,
      render: (player) => {
        const margen = holgura(player.matchesWithClub, player.listingsWithClub);
        return margen == null ? (
          <span className="text-[var(--muted)]">-</span>
        ) : (
          <span
            className={clsx(
              "font-semibold",
              margen <= 0 && "text-[var(--danger)]",
            )}
          >
            {number(margen)}
          </span>
        );
      },
    },
    // Edad abre la banda numérica en vez de partir en dos el bloque de texto
    // de la izquierda, que era donde se producían dos de los cuatro quiebres
    // de alineación que quedaban.
    {
      key: "age",
      header: t("jugadores.edad", "Edad"),
      value: (player) => player.ageYears + player.ageDays / 112,
      render: (player) => htAge(player.ageYears, player.ageDays),
    },
    {
      key: "form",
      header: abreviatura("form"),
      value: (player) => player.form,
      render: (player) => (
        <MetricCell value={player.form} delta={player.deltas.form} />
      ),
    },
    {
      key: "experience",
      header: abreviatura("experience"),
      value: (player) => player.experience,
      render: (player) => (
        <MetricCell
          value={player.experience}
          delta={player.deltas.experience}
        />
      ),
    },
    {
      key: "stamina",
      header: abreviatura("stamina"),
      value: (player) => player.stamina,
      render: (player) => (
        <MetricCell value={player.stamina} delta={player.deltas.stamina} />
      ),
    },
    // Fidelidad es un nivel de jugador como Forma, Experiencia o Condición, no
    // un dato de ficha: va con ellas y con su mismo código corto (el que ya usa
    // Posiciones), no perdida entre Especialidad y Carácter. Y como ellas se
    // pinta con `MetricCell`: un número pelado aquí medía 39 px contra los 72
    // de sus vecinas y le faltaba la línea del delta, así que rompía la banda.
    {
      key: "loyalty",
      header: abreviatura("loyalty"),
      value: (player) => player.loyalty,
      render: (player) => (
        <MetricCell value={player.loyalty} delta={player.deltas.loyalty} />
      ),
    },
    ...SKILLS.map((key): Column<SquadPlayer> => ({
      key,
      header: abreviatura(key),
      value: (player) => player.skills[key] ?? 0,
      render: (player) => (
        <MetricCell
          value={player.skills[key] ?? 0}
          delta={player.deltas[key]}
        />
      ),
    })),
    {
      key: "tsi",
      header: "TSI",
      value: (player) => player.tsi,
      render: (player) => (
        <MetricCell value={player.tsi} delta={player.deltas.tsi} />
      ),
    },
    // HTMS junto a TSI: las tres son la misma pregunta ("cuanto vale"),
    // solo que TSI la responde con el mercado y HTMS con las habilidades.
    {
      key: "htms",
      header: "HTMS",
      value: (player) => player.htms,
      render: (player) => (
        <MetricCell value={player.htms} delta={player.deltas.htms} />
      ),
    },
    {
      key: "htms28",
      optional: true,
      header: "HTMS28",
      value: (player) => player.htms28,
      render: (player) => (
        <MetricCell value={player.htms28} delta={player.deltas.htms28} />
      ),
    },
    {
      key: "salary",
      optional: true,
      header: t("jugadores.salario", "Salario"),
      value: (player) => player.salary,
      render: (player) => (
        <MetricCell value={player.salary} delta={player.deltas.salary} />
      ),
    },
    {
      key: "purchase",
      optional: true,
      header: t("jugadores.precioCompra", "Precio compra"),
      value: (player) => player.purchasePrice ?? -1,
      render: (player) =>
        player.purchasePrice == null ? (
          <span className="text-[var(--muted)]">-</span>
        ) : (
          money(player.purchasePrice, data.currency)
        ),
    },
    // Números primero y textos después, sin mezclarlos. Con las 27 columnas a
    // la vista, la cola alternaba alineación seis veces (4 textos a la
    // izquierda, Liderazgo a la derecha, Entrenador a la izquierda, G. liga a
    // la derecha) y eso es lo que hacía zigzaguear la tabla. Ahora hay una
    // sola frontera entre la banda numérica y la de texto.
    {
      key: "leadership",
      optional: true,
      header: t("club.liderazgo", "Liderazgo"),
      value: (player) => player.leadership,
      render: (player) => (
        <MetricCell
          value={player.leadership}
          delta={player.deltas.leadership}
        />
      ),
    },
    {
      key: "leagueGoals",
      optional: true,
      header: t("jugadores.golesLiga", "G. liga"),
      value: (player) => player.leagueGoals,
      render: (player) => (
        <MetricCell
          value={player.leagueGoals}
          delta={player.deltas.league_goals}
        />
      ),
    },
    {
      key: "character",
      optional: true,
      header: t("jugadores.caracter", "Carácter"),
      align: "left",
      value: (player) => player.agreeability,
      render: (player) => (
        <EtiquetaConCambio
          texto={player.agreeabilityLabel}
          delta={player.deltas.agreeability}
        />
      ),
    },
    {
      key: "aggressiveness",
      optional: true,
      header: t("jugadores.agresividad", "Agresividad"),
      align: "left",
      value: (player) => player.aggressiveness,
      render: (player) => (
        <EtiquetaConCambio
          texto={player.aggressivenessLabel}
          delta={player.deltas.aggressiveness}
        />
      ),
    },
    {
      key: "honesty",
      optional: true,
      header: t("jugadores.honestidad", "Honestidad"),
      align: "left",
      value: (player) => player.honesty,
      render: (player) => (
        <EtiquetaConCambio
          texto={player.honestyLabel}
          delta={player.deltas.honesty}
        />
      ),
    },
    {
      key: "trainer",
      optional: true,
      header: t("entrenamiento.entrenador", "Entrenador"),
      align: "left",
      value: (player) => player.playerTrainerSkillLevel,
      render: (player) =>
        player.playerTrainerSkillLevel > 0 ? (
          <EtiquetaConCambio
            texto={`${player.playerTrainerSkillLevel}/5 · ${
              TRAINER_TYPES[player.playerTrainerType]
                ? t(
                    `jugadores.tipoEntrenador.${player.playerTrainerType}`,
                    TRAINER_TYPES[player.playerTrainerType]!,
                  )
                : "?"
            }`}
            delta={player.deltas.player_trainer_skill_level}
          />
        ) : (
          "-"
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-[var(--muted)]">
            {t(
              "jugadores.intro",
              "Tabla maestra de {{club}}. Abre un nombre para ver sus detalles.",
              { club: data.teamName },
            )}
          </p>
          {/* Las columnas HTMS y HTMS28 son las únicas de esta tabla que no
              se leen de Hattrick sino que se calculan aquí. */}
          <EnlaceATransparencia seccion="htms" calculo="htms-ability" />
        </div>
        <div className="flex flex-col items-start gap-1">
          <span className="text-xs text-[var(--muted)]">
            {t("jugadores.diferenciasContra", "Diferencias semanales contra")}
          </span>
          <Tabs
            modo="filtro"
            label={t(
              "jugadores.diferenciasContra",
              "Diferencias semanales contra",
            )}
            active={ventana}
            onChange={setVentana}
            tabs={VENTANAS.map((v) => {
              // Apagada, no escondida: así la barra tiene las mismas siete
              // opciones para todo el mundo y dice por qué una no se puede.
              // Con `?? []` porque la caché guardada de una versión
              // anterior no trae este campo: sin él la pantalla se caía
              // entera mientras llegaba la respuesta nueva.
              const sinHistoria = (data.comparisonWindows ?? []).some(
                (w) => w.key === v.key && !w.available,
              );
              return {
                key: v.key,
                label: t(v.clave, v.texto),
                disabled: sinHistoria,
                title: sinHistoria
                  ? t(
                      "jugadores.sinHistoria",
                      "Todavía no hay cierres semanales guardados que lleguen tan atrás.",
                    )
                  : undefined,
              };
            })}
          />
        </div>
      </header>

      {datosDeClases && (
        <FiltroDeClases
          id="jugadores-filtro"
          datos={datosDeClases}
          valor={filtroDeClases}
          onChange={setFiltroDeClases}
        />
      )}

      <DataTable
        emptyMessage={t(
          "jugadores.vacia",
          "Sin jugadores en la plantilla. Sincroniza para traerlos.",
        )}
        rows={filas}
        columns={columns}
        rowKey={(player) => player.htPlayerId}
        initialSort="tsi"
        csvName="jugadores"
        filterPlaceholder={t(
          "jugadores.filtrar",
          "Filtrar por jugador, posición o habilidad…",
        )}
      />

      <p className="text-xs text-[var(--muted)]">
        {t(
          "jugadores.pie",
          "Variaciones basadas en cierres semanales de Hattrick. Referencia actual: {{referencia}}. El valor estimado no es un dato oficial de Hattrick.",
          {
            referencia: data.comparison.baselineCapturedAt
              ? relative(data.comparison.baselineCapturedAt)
              : t("jugadores.cierreAnterior", "cierre semanal anterior"),
          },
        )}
      </p>
    </div>
  );
}
