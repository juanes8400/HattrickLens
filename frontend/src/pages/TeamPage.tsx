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
import { useSquad } from "../hooks/useTeam";
import { htAge, money, number, relative } from "../hooks/useFormat";
import { abreviatura } from "../utils/abreviaturas";
import type { SquadPlayer, VentanaDeComparacion } from "../services/api";

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

  if (squad.isLoading) return <Loading />;
  if (squad.isError) return <ErrorState error={squad.error} />;
  if (!squad.data) return <SinDatos />;

  const data = squad.data;
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
    { key: "htms", header: "HTMS", value: (player) => player.htms },
    {
      key: "htms28",
      optional: true,
      header: "HTMS28",
      value: (player) => player.htms28,
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
    },
    {
      key: "leagueGoals",
      optional: true,
      header: t("jugadores.golesLiga", "G. liga"),
      value: (player) => player.leagueGoals,
    },
    {
      key: "character",
      optional: true,
      header: t("jugadores.caracter", "Carácter"),
      align: "left",
      value: (player) => player.agreeability,
      render: (player) => player.agreeabilityLabel,
    },
    {
      key: "aggressiveness",
      optional: true,
      header: t("jugadores.agresividad", "Agresividad"),
      align: "left",
      value: (player) => player.aggressiveness,
      render: (player) => player.aggressivenessLabel,
    },
    {
      key: "honesty",
      optional: true,
      header: t("jugadores.honestidad", "Honestidad"),
      align: "left",
      value: (player) => player.honesty,
      render: (player) => player.honestyLabel,
    },
    {
      key: "trainer",
      optional: true,
      header: t("entrenamiento.entrenador", "Entrenador"),
      align: "left",
      value: (player) => player.playerTrainerSkillLevel,
      render: (player) =>
        player.playerTrainerSkillLevel > 0
          ? `${player.playerTrainerSkillLevel}/5 · ${
              TRAINER_TYPES[player.playerTrainerType]
                ? t(
                    `jugadores.tipoEntrenador.${player.playerTrainerType}`,
                    TRAINER_TYPES[player.playerTrainerType]!,
                  )
                : "?"
            }`
          : "-",
    },
  ];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">
            {t("nav.jugadores", "Jugadores")}
          </h1>
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

      <DataTable
        emptyMessage={t(
          "jugadores.vacia",
          "Sin jugadores en la plantilla. Sincroniza para traerlos.",
        )}
        rows={data.players}
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
