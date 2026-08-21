"""Sección Equipo — la plantilla promediada, semana a semana.

La idea es leer al equipo entero de un vistazo. Tres grupos son series en el
tiempo (cómo evoluciona la media de la plantilla) y uno es una foto de hoy:

* **Habilidades** lleva DOS gráficas: las siete habilidades más Experiencia y
  Fidelidad comparten la escala 0-20 y van juntas; Resistencia y Forma tienen
  escalas cortas propias y van aparte en un eje 1-9. Mezclarlas dejaba a Forma
  pegada al suelo de un eje que llega a 20, como si fuera mala.
* **Salario y TSI**: dinero, un índice, y lo que cuesta cada punto de índice.
  Tres unidades distintas, así que tres gráficas con la misma línea de tiempo.
  Compartir eje insinuaría que 18.000 de salario y 99.000 de TSI se comparan,
  y no se comparan.
* **Mejor posición** es la foto de hoy, dibujada sobre una cancha. Cada línea
  responde dos preguntas distintas y por eso mide dos poblaciones distintas,
  dicho sin mezclarlas:

  - *¿Quién es mi mejor ahí?* Se evalúa a TODA la plantilla en las variantes
    de esa línea — un central se mide como central normal, ofensivo y hacia
    lateral — y se resume con la mejor de todas. Un extremo que además sea
    buen central aparece aquí aunque su mejor puesto sea la banda.
  - *¿Cuántos la tienen como su mejor puesto?* Ese es el reparto de la
    plantilla, y puede ser cero mientras el mejor rating existe igual.

Personalidad se graficó un tiempo y se quitó a petición del usuario
(2026-08-16): carácter, agresividad y honestidad casi no se mueven, así que la
línea no decía nada. `leadership` se sigue leyendo, pero solo como marca de
snapshot incompleto — ver `INCOMPLETE_WITHOUT_LEADERSHIP`.

La media de cada semana se calcula sobre la ÚLTIMA lectura de cada jugador en
esa semana. Sin eso, un jugador sincronizado tres veces pesaría el triple que
otro sincronizado una.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.squad import SKILL_COLS, SquadQueryService
from app.domain.engines.position_engine import rate_all
from app.application.queries.weekly import backfill_leading_gaps, season_week_for_datetime
from app.domain.value_objects.ht_constants import skill_name
from app.domain.engines import htms as htms_motor
from app.infrastructure.db import models as m

SKILL_SCALE_MAX = 20.0
# Forma y Condición NO llegan a 20: son escalas propias de Hattrick, más
# cortas. Experiencia y Fidelidad sí van en la misma 0-20 que las habilidades.
FORM_SCALE_MAX = 8.0
STAMINA_SCALE_MAX = 9.0

SKILL_LABELS: dict[str, str] = {
    "keeper": "Portería",
    "defending": "Defensa",
    "playmaking": "Jugadas",
    "winger": "Lateral",
    "passing": "Pases",
    "scoring": "Anotación",
    "set_pieces": "Balón parado",
}
# 2026-08-16, pedido explícito: dentro de Habilidades pero repartidos en dos
# gráficas. Experiencia y Fidelidad comparten la escala 0-20 con las siete
# habilidades; Resistencia y Forma tienen escalas cortas y van aparte, en un
# eje 1-9 fijado por el usuario.
LEVEL_LABELS: dict[str, str] = {
    "experience": "Experiencia",
    "loyalty": "Fidelidad",
}
SHORT_SCALE_LABELS: dict[str, str] = {
    "stamina": "Resistencia",
    "form": "Forma",
}
SHORT_SCALE_MIN = 1.0
SHORT_SCALE_MAX = 9.0

# No se grafica: se lee solo para detectar los snapshots viejos incompletos.
LEADERSHIP_FIELD = "leadership"
MARKET_LABELS: dict[str, str] = {
    "salary": "Salario medio",
    "tsi": "TSI medio",
    "tsi_total": "Suma de TSI",
    "cost_per_tsi": "Salario por punto de TSI",
}

# 2026-08-16, pedido explícito: cada gráfica de Salario y TSI lleva además la
# línea del once más caro en índice. La media de la plantilla entera la
# arrastran los suplentes y los canteranos; el once que de verdad juega se
# comporta distinto, y verlos juntos es lo que hace legible la diferencia.
TOP_SQUAD_SIZE = 11
SQUAD_SERIES_LABEL = "Plantilla completa"
TOP_SERIES_LABEL = f"{TOP_SQUAD_SIZE} mejores TSI"
TOP_SUFFIX = "_top"

# Fidelidad no se persistía al principio: los snapshots del 26-27 de julio de
# 2026 la tienen en 0. Comprobado en la base — `loyalty` y `leadership` valen
# 0 exactamente en las mismas 73 filas y en ninguna posterior, así que se
# guardaron a la vez. Liderazgo empieza en 1 en Hattrick, de modo que un 0
# suyo delata la lectura incompleta y sirve de marca para descartarla.
INCOMPLETE_WITHOUT_LEADERSHIP = ("loyalty",)

# 2026-08-16, pedido explícito: los jugadores con TSI 0 se ignoran SOLO en el
# coste por punto de TSI. Un TSI 0 es un canterano al que Hattrick todavía no
# le ha puesto índice y deja el cociente sin definir. Las medias de salario y
# de TSI siguen contando a toda la plantilla — ahí sí son jugadores del club.
# Por eso el ratio se calcula aparte, sobre su propio subconjunto, y no
# dividiendo las dos medias publicadas.
COST_PER_TSI_FIELD = "cost_per_tsi"
# Edad media de la plantilla, en años de Hattrick con decimales: la temporada
# tiene 112 días, así que 27 años y 56 días son 27,5. Se calcula aquí y no en
# la pantalla porque promediar años y días por separado da un número que no
# existe (28 años y 90 días de media no es "28,90").
AGE_FIELD = "avg_age"
DAYS_PER_HT_YEAR = 112
TSI_TOTAL_FIELD = "tsi_total"

# HTMS: el valor de las habilidades segun la tabla de la comunidad, y su
# proyeccion a los 28. La distancia entre ambas lineas es el margen de
# crecimiento que le queda a la plantilla entera.
HTMS_FIELD = "htms"
HTMS28_FIELD = "htms28"
HTMS_TOTAL_FIELD = "htms_total"

# 2026-08-17, pedido explícito: en las gráficas donde las dos líneas son la
# MISMA magnitud sobre dos poblaciones (media de salario, media de TSI, suma de
# TSI), el hueco entre ellas se sombrea. Ese hueco es la brecha entre el once
# que juega y el resto del plantel, y sombreado se lee de un vistazo. En el
# coste por punto de TSI NO: ahí las líneas se cruzan y el área entre ellas no
# es ninguna cantidad — sería tinta que no significa nada.
BANDED_MARKET_CHARTS: frozenset[str] = frozenset({"salary", "tsi", TSI_TOTAL_FIELD})

# Línea de la cancha a la que pertenece cada familia de posiciones. La clave
# es el prefijo del `position` que devuelve el motor (`wingback_offensive`,
# `wingback_defensive`… caen todas en "Lateral"). El orden es de portería a
# delantera y lo usa el frontend para apilar las filas.
PITCH_LINES: tuple[tuple[str, str], ...] = (
    ("keeper", "Portería"),
    ("central_defender", "Defensa Central"),
    ("wingback", "Lateral"),
    ("inner_midfield", "Medio"),
    ("winger", "Extremo"),
    ("forward", "Delantero"),
)


# Roles que NO son un puesto en la cancha: no se dibujan sobre el campo para
# no confundirlos con posiciones. El motor devuelve también `penalty_taker`,
# que aquí se deja fuera a propósito — sólo se pidieron estos dos.
SPECIAL_ROLES: tuple[str, ...] = ("captain", "set_piece_taker")

# 2026-08-16, regla de juego dada por el usuario: el lanzador de faltas no
# puede ser un portero. El motor lo puntúa igual que a cualquiera —a veces
# incluso lo pone primero, porque el balón parado no distingue puesto— pero
# poner al arquero a rematar una falta no es una recomendación, es un error.
# El capitán SÍ puede serlo, y por eso el veto es sólo para este rol.
ROLES_FORBIDDEN_FOR_KEEPERS: frozenset[str] = frozenset({"set_piece_taker"})


def pitch_line_of(position: str) -> str | None:
    """Línea de la cancha de una posición concreta.

    Se resuelve por el prefijo MÁS LARGO que encaje: `winger` y `wingback`
    comparten las cinco primeras letras, así que buscar el primero que
    coincida metería a los laterales en la banda.
    """
    candidates = [key for key, _ in PITCH_LINES if position.startswith(key)]
    return max(candidates, key=len) if candidates else None


@dataclass
class OverviewMetric:
    """Foto de hoy — solo la usan los grupos que no son serie."""

    key: str
    label: str
    value: float
    scale_max: float
    display: str
    value_label: str | None = None


@dataclass
class OverviewSeries:
    key: str
    label: str
    # Un valor por semana, alineado con `weeks`. `None` cuando esa semana no
    # tiene lectura: nunca se rellena con ceros ni se interpola.
    values: list[float | None]
    display: str


@dataclass
class OverviewChart:
    """Una gráfica dentro de un grupo.

    Un grupo puede necesitar varias: las series solo comparten eje cuando
    comparten escala. `title` va vacío cuando el grupo tiene una sola.
    """

    key: str
    title: str
    series: list[OverviewSeries]
    scale_min: float | None = None
    scale_max: float | None = None
    # Sombrea el hueco entre las dos series. Solo tiene sentido cuando miden lo
    # mismo sobre poblaciones distintas — ver `BANDED_MARKET_CHARTS`.
    band: bool = False


@dataclass
class PitchSlot:
    """Una línea de la cancha, con dos lecturas que NO son la misma población.

    `best_rating`/`top_player`/`best_variant_label` salen de evaluar a toda la
    plantilla en las variantes de esa línea. `count` y `average_rating` miran
    SOLO a quienes la tienen como su mejor puesto — `count` puede ser 0 y aun
    así haber un mejor rating, que es justo el caso de una línea que nadie
    ocupa de forma natural pero alguien podría cubrir. Nunca se mezclan: el
    frontend las pinta en bloques separados.
    """

    key: str
    label: str
    count: int
    best_rating: float | None = None
    top_player: str | None = None
    best_variant_label: str | None = None
    # Media de los `count` naturales, con el rating de SU mejor puesto.
    average_rating: float | None = None


@dataclass
class SpecialRole:
    """Capitán y lanzador de faltas: recomendaciones, no puestos.

    Su `rating` NO está en la escala 0-20 de las posiciones — el motor los
    puntúa con su propia fórmula y salen valores por encima de 20. Por eso
    viaja sin techo y el frontend lo pinta como número pelado, sin barra.
    """

    key: str
    label: str
    top_player: str | None = None
    rating: float | None = None


@dataclass
class OverviewGroup:
    key: str
    label: str
    chart: str  # "line" | "bars"
    metrics: list[OverviewMetric] = field(default_factory=list)
    weeks: list[str] = field(default_factory=list)
    charts: list[OverviewChart] = field(default_factory=list)
    pitch: list[PitchSlot] = field(default_factory=list)
    special_roles: list[SpecialRole] = field(default_factory=list)
    note: str = ""


@dataclass
class TeamOverview:
    team_name: str
    player_count: int
    currency: str
    groups: list[OverviewGroup]


@dataclass
class _WeeklyAverages:
    weeks: list[str]
    by_field: dict[str, list[float | None]]


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


class TeamOverviewQueryService:
    # Columnas de PlayerSnapshot que entran en las medias semanales.
    _TIMELINE_FIELDS = (
        *SKILL_COLS, *LEVEL_LABELS, *SHORT_SCALE_LABELS,
        "tsi", "salary", LEADERSHIP_FIELD, "age_years", "age_days",
    )

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _weekly_averages(self, team_id: int) -> _WeeklyAverages:
        columns = [getattr(m.PlayerSnapshot, name) for name in self._TIMELINE_FIELDS]
        rows = (
            await self._s.execute(
                select(
                    m.PlayerSnapshot.player_id,
                    m.PlayerSnapshot.captured_at,
                    *columns,
                )
                .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
                .where(m.Player.team_id == team_id)
                .order_by(m.PlayerSnapshot.captured_at)
            )
        ).all()
        if not rows:
            return _WeeklyAverages(weeks=[], by_field={})

        team = await self._s.get(m.Team, team_id)
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(
                    m.WorldContext.ht_league_id == (team.ht_league_id if team else None)
                )
            )
            if team is not None and team.ht_league_id is not None else None
        )

        # Última lectura de cada jugador dentro de cada semana ISO: un jugador
        # sincronizado tres veces no puede pesar el triple que otro.
        latest: dict[tuple[int, int], dict[int, tuple[datetime, tuple]]] = defaultdict(dict)
        for row in rows:
            captured_at: datetime = row.captured_at
            iso = captured_at.isocalendar()
            bucket = latest[(iso.year, iso.week)]
            previous = bucket.get(row.player_id)
            values = tuple(getattr(row, name) for name in self._TIMELINE_FIELDS)
            if previous is None or captured_at > previous[0]:
                bucket[row.player_id] = (captured_at, values)

        # El salario se guarda en la moneda cruda de CHPP; el resto de la app
        # lo divide por `currency_rate` antes de mostrarlo. Sin esto la media
        # salía diez veces más alta que en Jugadores.
        rate = (team.currency_rate or 1.0) if team is not None else 1.0
        leadership_index = self._TIMELINE_FIELDS.index(LEADERSHIP_FIELD)
        tsi_index = self._TIMELINE_FIELDS.index("tsi")

        weeks: list[str] = []
        market_fields = ("tsi", "salary", COST_PER_TSI_FIELD, TSI_TOTAL_FIELD)
        by_field: dict[str, list[float | None]] = {
            name: [] for name in (
                *self._TIMELINE_FIELDS, COST_PER_TSI_FIELD, TSI_TOTAL_FIELD, AGE_FIELD,
                HTMS_FIELD, HTMS28_FIELD, HTMS_TOTAL_FIELD,
                *(f"{name}{TOP_SUFFIX}" for name in market_fields),
            )
        }
        salary_index = self._TIMELINE_FIELDS.index("salary")
        age_years_index = self._TIMELINE_FIELDS.index("age_years")
        age_days_index = self._TIMELINE_FIELDS.index("age_days")
        for key in sorted(latest):
            readings = list(latest[key].values())
            newest = max(reading[0] for reading in readings)
            label = season_week_for_datetime(world, newest)
            weeks.append(label or newest.date().isoformat())
            # Fidelidad no se persistía al principio y esos snapshots
            # quedaron con 0. Un 0 de fidelidad puede ser real en un fichaje
            # recién llegado, así que el descarte no se decide por su propio
            # valor sino por liderazgo, que en Hattrick empieza en 1 y por
            # tanto delata la fila incompleta.
            complete = [r for r in readings if (r[1][leadership_index] or 0) > 0]
            for index, name in enumerate(self._TIMELINE_FIELDS):
                source = complete if name in INCOMPLETE_WITHOUT_LEADERSHIP else readings
                present = [
                    float(reading[1][index]) for reading in source
                    if reading[1][index] is not None
                ]
                if not present:
                    by_field[name].append(None)
                    continue
                average = _mean(present)
                by_field[name].append(round(average / rate, 2) if name == "salary" else average)

            # Coste por punto de TSI: sobre los jugadores CON índice, y sumando
            # antes de dividir. Promediar el cociente jugador a jugador daría
            # infinito con un TSI 0 y estaría dominado por los índices bajos.
            def _market(subset: list[tuple], suffix: str = "") -> None:
                with_tsi = [r for r in subset if (r[1][tsi_index] or 0) > 0]
                total_tsi = sum(float(r[1][tsi_index]) for r in with_tsi)
                total_salary = sum(float(r[1][salary_index] or 0) for r in with_tsi) / rate
                by_field[f"{COST_PER_TSI_FIELD}{suffix}"].append(
                    round(total_salary / total_tsi, 4) if total_tsi else None
                )
                # La suma sale del mismo recuento: quien tiene TSI 0 no aporta
                # nada, así que excluirlo no cambia el total.
                by_field[f"{TSI_TOTAL_FIELD}{suffix}"].append(
                    total_tsi if subset else None
                )

            # Edad media: cada jugador se convierte primero a años con
            # decimales y después se promedia.
            edades = [
                float(r[1][age_years_index]) + float(r[1][age_days_index]) / DAYS_PER_HT_YEAR
                for r in readings
                if r[1][age_years_index] is not None and r[1][age_days_index] is not None
            ]
            by_field[AGE_FIELD].append(round(_mean(edades), 2) if edades else None)

            # HTMS de cada jugador con las habilidades y la edad de ESA semana.
            valores_htms = []
            for reading in readings:
                fila = reading[1]
                if fila[age_years_index] is None or fila[age_days_index] is None:
                    continue
                valores_htms.append(
                    htms_motor.de_habilidades(
                        int(fila[age_years_index]), int(fila[age_days_index]),
                        **{c: fila[self._TIMELINE_FIELDS.index(c)] for c in SKILL_COLS},
                    )
                )
            by_field[HTMS_FIELD].append(
                round(_mean([float(v.ability) for v in valores_htms]), 2)
                if valores_htms else None
            )
            by_field[HTMS28_FIELD].append(
                round(_mean([float(v.potential) for v in valores_htms]), 2)
                if valores_htms else None
            )
            by_field[HTMS_TOTAL_FIELD].append(
                float(sum(v.ability for v in valores_htms)) if valores_htms else None
            )

            _market(readings)

            # El once con más índice de esa semana. Se ordena por TSI y se
            # cortan los primeros: si la plantilla tuviera menos de once, se
            # toman los que haya en vez de inventar huecos.
            top = sorted(
                readings, key=lambda r: float(r[1][tsi_index] or 0), reverse=True,
            )[:TOP_SQUAD_SIZE]
            top_tsi = [float(r[1][tsi_index]) for r in top if r[1][tsi_index] is not None]
            top_salary = [float(r[1][salary_index]) for r in top if r[1][salary_index] is not None]
            by_field[f"tsi{TOP_SUFFIX}"].append(_mean(top_tsi) if top_tsi else None)
            by_field[f"salary{TOP_SUFFIX}"].append(
                round(_mean(top_salary) / rate, 2) if top_salary else None
            )
            _market(top, TOP_SUFFIX)
        return _WeeklyAverages(weeks=weeks, by_field=by_field)

    async def get(self, team_id: int) -> TeamOverview | None:
        squad = await SquadQueryService(self._s).get(team_id)
        if squad is None or not squad.players:
            return None
        players = squad.players
        weekly = await self._weekly_averages(team_id)

        def _series(col: str, label: str, display: str = "level") -> OverviewSeries:
            values = weekly.by_field.get(col, [])
            # Fidelidad arranca vacía en esta cuenta (la columna se añadió
            # después del primer sync). El tramo inicial se estira con la
            # primera lectura conocida SOLO para que la línea no salga
            # cortada — ver `backfill_leading_gaps`.
            if col == "loyalty":
                values = backfill_leading_gaps(values)
            return OverviewSeries(key=col, label=label, values=values, display=display)

        skills = OverviewGroup(
            key="skills", label="Habilidades", chart="line", weeks=weekly.weeks,
            charts=[
                OverviewChart(
                    key="levels", title="Habilidades, Experiencia y Fidelidad",
                    scale_min=0.0, scale_max=SKILL_SCALE_MAX,
                    series=[
                        _series(col, SKILL_LABELS.get(col, col)) for col in SKILL_COLS
                    ] + [
                        _series(col, label) for col, label in LEVEL_LABELS.items()
                    ],
                ),
                OverviewChart(
                    key="avg_age", title="Edad promedio",
                    series=[
                        OverviewSeries(
                            key=AGE_FIELD, label="Edad promedio",
                            values=weekly.by_field.get(AGE_FIELD, []), display="decimal",
                        )
                    ],
                ),
                OverviewChart(
                    key="short_scale", title="Resistencia y Forma",
                    scale_min=SHORT_SCALE_MIN, scale_max=SHORT_SCALE_MAX,
                    series=[
                        _series(col, label) for col, label in SHORT_SCALE_LABELS.items()
                    ],
                ),
            ],
            metrics=[
                OverviewMetric(
                    key=col, label=SKILL_LABELS.get(col, col),
                    value=(avg := _mean([float(p.skills.get(col) or 0) for p in players])),
                    scale_max=SKILL_SCALE_MAX, display="level",
                    value_label=skill_name(int(round(avg))),
                )
                for col in SKILL_COLS
            ] + [
                OverviewMetric(
                    key=col, label=label,
                    value=(avg := _mean([float(getattr(p, col) or 0) for p in players])),
                    scale_max=SKILL_SCALE_MAX, display="level",
                    value_label=skill_name(int(round(avg))),
                )
                for col, label in LEVEL_LABELS.items()
            ] + [
                OverviewMetric(
                    key=col, label=label,
                    value=_mean([float(getattr(p, col) or 0) for p in players]),
                    scale_max=SHORT_SCALE_MAX, display="level",
                )
                for col, label in SHORT_SCALE_LABELS.items()
            ],
            note=(
                f"Arriba, todo lo que se mide de 0 a {SKILL_SCALE_MAX:.0f}. Abajo, "
                f"Resistencia y Forma, que usan escalas mucho más cortas "
                f"({SHORT_SCALE_MIN:.0f} a {SHORT_SCALE_MAX:.0f}): en el eje de "
                "arriba quedarían pegadas al suelo como si fueran malas."
            ),
        )

        def _market_chart(key: str, display: str) -> OverviewChart:
            """Cada rubro con sus dos líneas: plantilla entera y el once de
            más TSI. Comparten eje porque son la MISMA medida sobre dos
            conjuntos distintos — eso es justo lo que se quiere comparar."""
            return OverviewChart(
                key=key, title=MARKET_LABELS[key],
                band=key in BANDED_MARKET_CHARTS,
                series=[
                    OverviewSeries(
                        key=key, label=SQUAD_SERIES_LABEL,
                        values=weekly.by_field.get(key, []), display=display,
                    ),
                    OverviewSeries(
                        key=f"{key}{TOP_SUFFIX}", label=TOP_SERIES_LABEL,
                        values=weekly.by_field.get(f"{key}{TOP_SUFFIX}", []),
                        display=display,
                    ),
                ],
            )

        market = OverviewGroup(
            key="market", label="Salario y TSI", chart="line", weeks=weekly.weeks,
            charts=[
                _market_chart("salary", "money"),
                _market_chart("tsi", "number"),
                _market_chart(TSI_TOTAL_FIELD, "number"),
                _market_chart(COST_PER_TSI_FIELD, "ratio"),
            ],
            note=(
                "Cuatro unidades distintas, dinero, un índice, su suma y el coste "
                "de cada punto, así que ninguna comparte eje con las otras. "
                f"Dentro de cada una, la plantilla entera contra sus {TOP_SQUAD_SIZE} "
                "jugadores de mayor TSI, con el hueco entre ambas sombreado; en el "
                "coste por punto no se sombrea porque ahí las líneas se cruzan y el "
                "área no sería ninguna cantidad. Los de TSI 0 se ignoran SOLO en el "
                "coste por punto: sin índice no hay cociente que calcular."
            ),
        )

        htms_grupo = OverviewGroup(
            key="htms", label="HTMS", chart="line", weeks=weekly.weeks,
            charts=[
                OverviewChart(
                    key="htms_avg", title="HTMS actual y potencial a los 28, promedio", band=True,
                    series=[
                        OverviewSeries(
                            key=HTMS_FIELD, label="HTMS de hoy",
                            values=weekly.by_field.get(HTMS_FIELD, []),
                            display="number",
                        ),
                        OverviewSeries(
                            key=HTMS28_FIELD, label="HTMS28 (potencial a los 28 años)",
                            values=weekly.by_field.get(HTMS28_FIELD, []),
                            display="number",
                        ),
                    ],
                ),
                OverviewChart(
                    key="htms_total", title="HTMS sumado de la plantilla",
                    series=[
                        OverviewSeries(
                            key=HTMS_TOTAL_FIELD, label="Plantilla entera",
                            values=weekly.by_field.get(HTMS_TOTAL_FIELD, []),
                            display="number",
                        ),
                    ],
                ),
            ],
            note=(
                "HTMS pone en puntos lo que valen las siete habilidades, con la "
                "tabla que usa la comunidad: subir de Excelente a Formidable en "
                "Defensa vale mucho más que subir de Pobre a Débil, y por eso no "
                "es una suma de niveles. HTMS28 proyecta esos puntos a los 28 años "
                "suponiendo entrenamiento continuo, entrenador bueno y ayudantes "
                "corrientes; el hueco sombreado entre las dos líneas es el margen "
                "que le queda a la plantilla por delante. En un equipo veterano "
                "las líneas se cruzan: ahí HTMS28 ya no dice cuánto puede crecer, "
                "sino cuánto valía cuando estaba en su punto."
            ),
        )

        # Quién es el MEJOR de cada línea: se evalúa a toda la plantilla en
        # las variantes de esa línea y se resume con la mejor de todas. Los
        # ratings se piden al motor con los snapshots crudos (`_latest`) y no
        # con el DTO de plantilla, que ya trae la especialidad traducida a
        # texto y rompería la fórmula.
        #
        # `form` y `stamina` son OBLIGATORIOS aunque no lo parezcan: sin ellos
        # `rate_all` no falla, devuelve 0.0 en silencio y la línea entera sale
        # vacía. Este dict debe llevar los mismos campos que el `roster()` del
        # endpoint de análisis.
        engine_players = [
            {
                "name": f"{ident.first_name} {ident.last_name}".strip(),
                "age_years": snap.age_years, "age_days": snap.age_days,
                "form": snap.form, "stamina": snap.stamina,
                "experience": snap.experience, "loyalty": snap.loyalty,
                "specialty": snap.specialty, "leadership": snap.leadership,
                "skills": {c: getattr(snap, c) or 0 for c in SKILL_COLS},
            }
            for snap, ident in await SquadQueryService(self._s)._latest(team_id)
        ]
        best_of_line: dict[str, tuple[float, str, str]] = {}
        best_role: dict[str, tuple[float, str, str]] = {}
        for engine_player in engine_players:
            ratings = rate_all(engine_player, include_special=True)
            field = [r for r in ratings if not getattr(r, "is_special_role", False)]
            # Su propio mejor puesto, calculado con estas MISMAS lecturas para
            # que el veto de portero no dependa de otra fuente.
            own_best = max(field, key=lambda r: r.rating, default=None)
            is_keeper = own_best is not None and pitch_line_of(own_best.position) == "keeper"

            for rating in ratings:
                if getattr(rating, "is_special_role", False):
                    if rating.position not in SPECIAL_ROLES:
                        continue
                    if is_keeper and rating.position in ROLES_FORBIDDEN_FOR_KEEPERS:
                        continue
                    current = best_role.get(rating.position)
                    if current is None or rating.rating > current[0]:
                        best_role[rating.position] = (
                            rating.rating, engine_player["name"], rating.label,
                        )
                    continue
                line = pitch_line_of(rating.position)
                if line is None:
                    continue
                current = best_of_line.get(line)
                if current is None or rating.rating > current[0]:
                    best_of_line[line] = (
                        rating.rating, engine_player["name"], rating.label,
                    )

        # Quiénes la tienen como su mejor puesto — otra pregunta, otra
        # población. Puede estar vacía y aun así existir un mejor rating.
        natural: dict[str, list[float]] = {key: [] for key, _ in PITCH_LINES}
        for p in players:
            line = pitch_line_of(p.best_position.position)
            if line is not None:
                natural[line].append(float(p.best_position.rating))

        pitch: list[PitchSlot] = []
        for key, label in PITCH_LINES:
            best = best_of_line.get(key)
            own = natural[key]
            pitch.append(PitchSlot(
                key=key, label=label, count=len(own),
                best_rating=round(best[0], 2) if best else None,
                top_player=best[1] if best else None,
                best_variant_label=best[2] if best else None,
                average_rating=round(sum(own) / len(own), 2) if own else None,
            ))

        counts: dict[str, int] = {}
        for p in players:
            counts[p.best_position.label] = counts.get(p.best_position.label, 0) + 1
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        special_roles = [
            SpecialRole(
                key=role, label=best_role[role][2],
                top_player=best_role[role][1],
                rating=round(best_role[role][0], 2),
            )
            for role in SPECIAL_ROLES if role in best_role
        ]

        best_position = OverviewGroup(
            key="best_position", label="Mejor posición", chart="pitch",
            pitch=pitch, special_roles=special_roles,
            metrics=[
                OverviewMetric(
                    key=label, label=label, value=float(n),
                    scale_max=float(max(counts.values())), display="count",
                )
                for label, n in ordered
            ],
            note=(
                "Reparto de hoy, no promedio. El motor distingue 19 variantes "
                "(lateral ofensivo, defensivo, hacia el medio…) y sobre la cancha "
                "se agrupan en sus seis líneas. Capitán y lanzador de faltas van "
                "aparte, fuera del campo: son recomendaciones de rol y su "
                "puntuación usa otra fórmula, no la escala 0-20 de los puestos. "
                "Los porteros quedan fuera del lanzamiento de faltas."
            ),
        )

        player_classes = OverviewGroup(
            key="player_classes", label="Clases de Jugador", chart="pending",
            note="Todavía no hay nada definido aquí.",
        )

        return TeamOverview(
            team_name=squad.team_name,
            player_count=len(players),
            currency=squad.currency,
            groups=[skills, market, htms_grupo, best_position, player_classes],
        )
