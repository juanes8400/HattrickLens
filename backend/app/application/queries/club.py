"""Estado e historial del club y cuerpo técnico.

Hattrick Control separaba esta información en Club, Gráfico y Empleados.  En
Lens sale de los snapshots CHPP que ya se guardan en cada sincronización: no
requiere una llamada adicional ni infiere estados que Hattrick no entregue.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.weekly import (
    changes_only,
    season_week_for_datetime,
)
from app.domain.engines import psicologia as psi
from app.domain.engines.staff_effects import STAFF_FIELD_TO_EFFECT_FN
from app.domain.value_objects.ht_constants import (
    CONFIDENCE,
    STAFF_FIELD_LABELS,
    STAFF_TYPE_TO_FIELD,
    TEAM_SPIRIT,
)
from app.infrastructure.db import models as m

# Los seis puestos que Hattrick deja contratar, en el orden y con los nombres
# de su propia página de Empleados. Nada de inventar: la lista y las etiquetas
# viven en `ht_constants` junto al mapa de códigos, y `staff_effects.py` tiene
# una función de efecto para cada uno — un puesto sin efecto que contar sería
# la señal de que no existe.
STAFF_FIELDS: tuple[tuple[str, str], ...] = tuple(
    (field, STAFF_FIELD_LABELS[field])
    for field in (
        "assistant_trainer_levels",
        "form_coach_levels",
        "medic_levels",
        "sport_psychologist_levels",
        "tactical_assistant_levels",
        "financial_director_levels",
    )
)
# El mismo código StaffType de stafflist.xml, invertido, para agrupar el roster
# real (los nombres) bajo cada puesto.
STAFF_FIELD_TO_TYPE: dict[str, int] = {field: code for code, field in STAFF_TYPE_TO_FIELD.items()}

TRAINER_TYPES = {0: "Defensivo", 1: "Ofensivo", 2: "Equilibrado"}
POPULARITY = {
    0: "muy baja",
    1: "furiosos",
    2: "irritados",
    3: "calmados",
    4: "contentos",
    5: "satisfechos",
    6: "eufóricos",
    7: "muy alta",
    8: "bailando en las calles",
    9: "enviando poemas de amor",
}


def _date(value: Any) -> str:
    return value.isoformat() if value is not None else ""


def _staff_members(row: m.StaffSnapshot) -> list[dict[str, Any]]:
    if not row.staff_members_json:
        return []
    try:
        return list(json.loads(row.staff_members_json))
    except (ValueError, TypeError):
        return []


def _staff_levels(row: m.StaffSnapshot) -> list[dict[str, Any]]:
    members = _staff_members(row)
    return [
        {
            "key": key,
            "label": label,
            "level": int(getattr(row, key) or 0),
            "members": [
                {"name": mem.get("name", ""), "level": mem.get("level", 0)}
                for mem in members
                if mem.get("staff_type") == STAFF_FIELD_TO_TYPE[key]
            ],
            # El aporte real del puesto, según las tablas oficiales de
            # Hattrick. Los seis lo tienen; que un puesto no tuviera efecto
            # que calcular era justo la pista de que no existía.
            "effect": STAFF_FIELD_TO_EFFECT_FN[key](int(getattr(row, key) or 0)),
        }
        for key, label in STAFF_FIELDS
    ]


def _movimiento_json(x: psi.Movimiento) -> dict[str, Any]:
    return {
        "at": x.at.isoformat(),
        "from": x.desde,
        "to": x.hasta,
        "delta": x.delta,
        "cause": x.cause,
        "buys": x.buys,
        "sales": x.sales,
    }


def _bajadas_de_intensidad(lecturas: list[m.TrainingSnapshot]) -> list[datetime]:
    """Cuándo se BAJÓ el % de entrenamiento.

    Sólo las bajadas: el manual dice que reducir la intensidad da un impulso
    momentáneo al espíritu y que volver a subirla lo hunde. Subirla no es la
    misma noticia, así que no se cuenta aquí.
    """
    salida: list[datetime] = []
    anterior: int | None = None
    for row in lecturas:
        if anterior is not None and row.training_level < anterior:
            salida.append(row.captured_at)
        anterior = row.training_level
    return salida


def _nivel_psicologico_real(value: Any) -> bool:
    """Un nivel publicado por Hattrick, no el -1 temporal ni NULL."""
    return isinstance(value, int) and value >= 0


def _ultimo_nivel_valido(lecturas: Sequence[Any], campo: str) -> int | None:
    """La última lectura REAL de un indicador, mirando hacia atrás.

    Sirve para los tres --Espíritu, Confianza y popularidad con la afición--
    y por eso no se ata al tipo de una tabla: los dos primeros viven en las
    fotos de entrenamiento y el tercero en las de economía.
    """
    for row in reversed(lecturas):
        value = getattr(row, campo)
        if _nivel_psicologico_real(value):
            return int(value)
    return None


def _historial_psicologico(lecturas: list[m.TrainingSnapshot]) -> list[dict[str, Any]]:
    """Parejas observadas aplicando forward-fill independiente.

    ``moodHistory`` es el contrato antiguo que reúne ambos indicadores en una
    fila. Si uno viene oculto durante el partido, se conserva únicamente ese
    último valor y el otro todavía puede cambiar. La fila se omite hasta que
    existan observaciones reales de los dos.
    """
    spirit: int | None = None
    confidence: int | None = None
    anterior: tuple[int, int] | None = None
    salida: list[dict[str, Any]] = []
    for row in lecturas:
        morale = row.morale
        self_confidence = row.self_confidence
        if morale is not None and morale >= 0:
            spirit = morale
        if self_confidence is not None and self_confidence >= 0:
            confidence = self_confidence
        if spirit is None or confidence is None:
            continue
        actual = (spirit, confidence)
        if actual == anterior:
            continue
        salida.append(
            {
                "capturedAt": _date(row.captured_at),
                "spirit": spirit,
                "confidence": confidence,
            }
        )
        anterior = actual
    return salida


class ClubQueryService:
    """Read-only club view composed from append-only CHPP snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _psicologia(
        self,
        team: m.Team,
        lecturas: list[m.TrainingSnapshot],
        semanas: int = 8,
    ) -> dict[str, Any]:
        """Espíritu y confianza con el motivo de cada movimiento.

        Las dos series comparten origen pero no comparten causas, y por eso
        salen por separado: al espíritu lo mueven la actitud del partido y el
        mercado; a la confianza, los resultados. Mezclarlas invita a leer una
        causa donde el manual no la pone.
        """
        desde = datetime.utcnow() - timedelta(weeks=semanas)
        recientes = [x for x in lecturas if x.captured_at >= desde]

        def serie(campo: str) -> list[psi.Lectura]:
            """Un punto por CAMBIO real, MÁS la última lectura.

            Dos lecturas iguales seguidas no son un dato nuevo, y por eso la
            serie se queda con los cambios. Pero terminarla en el último
            cambio deja fuera todo lo que se sabe desde entonces: la confianza
            no se movía desde el 21 de agosto y la línea moría ahí, con diez
            días conocidos sin dibujar y con pinta de que faltaba el dato
            (2026-08-31, visto por el usuario).

            Que un valor lleve diez días quieto ES información. La línea llega
            hasta donde llega lo que sabemos, y un tramo plano lo dice.
            """
            validas = [row for row in recientes if _nivel_psicologico_real(getattr(row, campo))]
            puntos = [
                psi.Lectura(at=row.captured_at, level=int(getattr(row, campo)))
                for row in changes_only(
                    validas, lambda i: i.captured_at, lambda i: getattr(i, campo)
                )
            ]
            if validas:
                # Aunque la última respuesta fuese el -1 temporal, el estado
                # efectivo sigue siendo la última lectura real. La meseta debe
                # llegar hasta la captura más reciente para no fingir que el
                # historial terminó antes del partido.
                extremo = recientes[-1].captured_at
                ultimo_nivel = int(getattr(validas[-1], campo))
                if not puntos or puntos[-1].at != extremo:
                    puntos.append(psi.Lectura(at=extremo, level=ultimo_nivel))
            return puntos

        partidos = await self._partidos_que_cuentan(team, desde)
        compras, ventas = await self._mercado_por_dia(team.id, desde)
        bajadas = _bajadas_de_intensidad(recientes)

        espiritu = serie("morale")
        confianza = serie("self_confidence")

        return {
            "weeks": semanas,
            "spirit": {
                "scale": psi.escala("spirit"),
                "equilibrium": psi.EQUILIBRIO_BASE,
                "readings": [{"at": x.at.isoformat(), "level": x.level} for x in espiritu],
                "movements": [
                    _movimiento_json(x)
                    for x in psi.movimientos_de_espiritu(
                        espiritu, partidos, compras, ventas, bajadas
                    )
                ],
            },
            "confidence": {
                "scale": psi.escala("confidence"),
                # SIN punto medio. El manual dice que la confianza tiende a
                # uno y que el psicólogo lo sube de forma no lineal, pero no
                # publica su valor. Aquí se dibujaba la MEDIANA de las
                # lecturas, que es un estadístico de nuestros propios datos y
                # no el del juego: con tres lecturas coincidía con el valor
                # actual, así que la línea caía sobre la meseta y sugería
                # «estás en tu equilibrio», que es justo lo que no se sabe
                # (2026-08-31, señalado por el usuario).
                "equilibrium": None,
                "readings": [{"at": x.at.isoformat(), "level": x.level} for x in confianza],
                "movements": [
                    _movimiento_json(x) for x in psi.movimientos_de_confianza(confianza, partidos)
                ],
            },
            "matches": [
                {
                    "playedAt": p.played_at.isoformat(),
                    "rival": p.rival,
                    "isHome": p.is_home,
                    "goalsFor": p.goals_for,
                    "goalsAgainst": p.goals_against,
                    "result": p.resultado,
                    "attitude": p.attitude,
                    "attitudeLabel": psi.ACTITUDES.get(p.attitude)
                    if p.attitude is not None
                    else None,
                }
                for p in partidos
            ],
            "buyDays": [{"day": d, "count": n} for d, n in sorted(compras.items())],
            "sellDays": [{"day": d, "count": n} for d, n in sorted(ventas.items())],
            # La cuarta palanca. Que esté en cero también es información: dice
            # que se vigila y que ahí no pasó nada.
            "intensityDrops": [t.isoformat() for t in bajadas],
        }

    async def _partidos_que_cuentan(self, team: m.Team, desde: datetime) -> list[psi.Partido]:
        """Los partidos que mueven el ánimo, con la actitud realmente jugada.

        La actitud sale del DETALLE del partido y no de las órdenes: las
        órdenes sólo existen si se capturaron antes de jugar, mientras que el
        detalle las trae siempre, también para los partidos viejos.
        """
        ratings = m.Base.metadata.tables["match_ratings"]
        filas = (
            await self._s.execute(
                select(m.Match)
                .where(
                    m.Match.played_at >= desde,
                    m.Match.home_goals >= 0,
                    m.Match.match_type.in_(psi.TIPOS_QUE_CUENTAN),
                )
                .order_by(m.Match.played_at)
            )
        ).scalars()

        salida: list[psi.Partido] = []
        for x in filas:
            if team.ht_team_id not in (x.home_team_ht_id, x.away_team_ht_id):
                continue
            en_casa = x.home_team_ht_id == team.ht_team_id
            fila = (
                await self._s.execute(
                    select(ratings.c.attitude).where(
                        ratings.c.ht_match_id == x.ht_match_id,
                        ratings.c.team_ht_id == team.ht_team_id,
                    )
                )
            ).first()
            gf, gc = (x.home_goals, x.away_goals) if en_casa else (x.away_goals, x.home_goals)
            salida.append(
                psi.Partido(
                    played_at=x.played_at,
                    rival=(x.away_team_name if en_casa else x.home_team_name) or "?",
                    is_home=en_casa,
                    goals_for=gf,
                    goals_against=gc,
                    attitude=fila[0] if fila else None,
                )
            )
        return salida

    async def _mercado_por_dia(
        self, team_id: int, desde: datetime
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Compras y ventas contadas por día.

        Por día y no una por una: en ocho semanas reales hubo más de treinta,
        y un marcador por operación tapa la línea entera.
        """
        transfers = m.Base.metadata.tables["team_transfers"]
        compras: dict[str, int] = {}
        ventas: dict[str, int] = {}
        for fila in await self._s.execute(
            transfers.select().where(transfers.c.team_id == team_id, transfers.c.deadline >= desde)
        ):
            d = fila._mapping
            dia = d["deadline"].date().isoformat()
            destino = compras if d["is_buy"] else ventas
            destino[dia] = destino.get(dia, 0) + 1
        return compras, ventas

    async def get(self, team_id: int) -> dict[str, Any] | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        training = list(
            (
                await self._s.execute(
                    select(m.TrainingSnapshot)
                    .where(m.TrainingSnapshot.team_id == team_id)
                    .order_by(m.TrainingSnapshot.captured_at, m.TrainingSnapshot.id)
                )
            ).scalars()
        )
        economy = list(
            (
                await self._s.execute(
                    select(m.EconomySnapshot)
                    .where(m.EconomySnapshot.team_id == team_id)
                    .order_by(m.EconomySnapshot.captured_at)
                )
            ).scalars()
        )
        staff = list(
            (
                await self._s.execute(
                    select(m.StaffSnapshot)
                    .where(m.StaffSnapshot.team_id == team_id)
                    .order_by(m.StaffSnapshot.captured_at)
                )
            ).scalars()
        )

        # "TT-ss" para "Evolución del staff" — mismo patrón que economy.py:
        # ancla al WorldContext del país del equipo (por ht_league_id), no
        # inventa temporada/semana si worlddetails no se ha sincronizado.
        world = (
            await self._s.scalar(
                select(m.WorldContext).where(m.WorldContext.ht_league_id == team.ht_league_id)
            )
            if team.ht_league_id is not None
            else None
        )

        latest_spirit = _ultimo_nivel_valido(training, "morale")
        latest_confidence = _ultimo_nivel_valido(training, "self_confidence")
        popularidad_afición = _ultimo_nivel_valido(economy, "supporters_popularity")
        latest_economy = economy[-1] if economy else None
        latest_staff = staff[-1] if staff else None

        current_staff = (
            {
                "capturedAt": _date(latest_staff.captured_at),
                "trainer": {
                    "skillLevel": latest_staff.trainer_skill_level,
                    "type": latest_staff.trainer_type,
                    "typeLabel": TRAINER_TYPES.get(latest_staff.trainer_type, ", "),
                    "leadership": latest_staff.trainer_leadership,
                },
                "roles": _staff_levels(latest_staff),
                "totalLevels": sum(item["level"] for item in _staff_levels(latest_staff)),
                # 2026-08-15, verificado con un fetch en vivo: `club.xml`
                # devuelve `<YouthSquad><Investment>0</Investment>` aunque el
                # club SÍ esté invirtiendo — ese campo no refleja el gasto
                # real. El gasto semanal de verdad es `CostsYouth` de
                # economy.xml (200.000 SEK ÷ tasa = 20.000 US$/semana en esta
                # cuenta), así que la cifra sale de ahí, ya convertida a
                # moneda local igual que en Economía.
                "youthInvestment": (
                    round(latest_economy.costs_youth / (team.currency_rate or 1.0))
                    if latest_economy is not None and latest_economy.costs_youth is not None
                    else None
                ),
                "youthInvestmentCurrency": team.currency_name,
                "youthLevel": latest_staff.youth_level,
            }
            if latest_staff is not None
            else None
        )

        return {
            "teamName": team.name,
            "current": {
                "spirit": (
                    {
                        "level": latest_spirit,
                        "label": TEAM_SPIRIT.get(latest_spirit, "Sin dato"),
                    }
                    if latest_spirit is not None
                    else None
                ),
                "confidence": (
                    {
                        "level": latest_confidence,
                        "label": CONFIDENCE.get(latest_confidence, "Sin dato"),
                    }
                    if latest_confidence is not None
                    else None
                ),
                "supporters": (
                    {
                        "fanClubSize": latest_economy.fan_club_size,
                        # La última popularidad REAL, no la de la última foto:
                        # si la de hoy vino sin dato, lo que sigue siendo
                        # cierto es la anterior. Mismo criterio que el
                        # Espíritu y la Confianza, que ya se resuelven cada
                        # uno por su cuenta.
                        "popularity": popularidad_afición,
                        "popularityLabel": (
                            POPULARITY.get(popularidad_afición, "Sin dato")
                            if popularidad_afición is not None
                            else "Sin dato"
                        ),
                    }
                    if latest_economy is not None
                    else None
                ),
            },
            "staff": current_staff,
            # El módulo de Psicología. Sustituye a «Ánimo competitivo», que
            # metía espíritu y confianza en un solo eje pese a tener escalas
            # y causas distintas, y que no decía por qué se movía nada.
            "psychology": await self._psicologia(team, training),
            "moodHistory": _historial_psicologico(training),
            # Las fotos sin popularidad real quedan fuera de la serie: una
            # ausencia dibujada como un cero sería un desplome inventado.
            "supporterHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "fanClubSize": row.fan_club_size,
                    "supportersPopularity": row.supporters_popularity,
                }
                for row in changes_only(
                    [x for x in economy if _nivel_psicologico_real(x.supporters_popularity)],
                    lambda item: item.captured_at,
                    lambda item: (item.fan_club_size, item.supporters_popularity),
                )
            ],
            "staffHistory": [
                {
                    "capturedAt": _date(row.captured_at),
                    "seasonWeek": season_week_for_datetime(world, row.captured_at),
                    "roles": _staff_levels(row),
                    "trainerSkillLevel": row.trainer_skill_level,
                }
                for row in changes_only(
                    staff,
                    lambda item: item.captured_at,
                    lambda item: tuple(getattr(item, key) for key, _ in STAFF_FIELDS),
                )
            ],
            "notes": [],
        }
