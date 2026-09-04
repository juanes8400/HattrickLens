"""AcademyQueryService — HL-110, HL-111, HL-112, HL-114, HL-115.

La academia es la parte del club donde es más fácil perder dinero sin darse
cuenta: el gasto es semanal y silencioso, el retorno llega temporadas después,
y las dos cifras viven en pantallas distintas. Hattrick Control muestra lo
invertido y lo ingresado sin cruzarlos nunca. Aquí se cruzan.

Dos decisiones de diseño que importan:

**Un techo sin revelar no es un techo bajo.** Si el ojeador no ha destapado el
máximo de una habilidad, el motor lo trata como desconocido y lo dice, en vez
de asumir cero y descartar al jugador. Descartar una promesa por falta de
información del ojeador sería confundir ignorancia con evidencia.

**El plazo manda sobre el potencial.** Un canterano de 19 años se pierde al
cumplir el límite, por bueno que sea. Por eso los días restantes aparecen
siempre y el consejo de promoción los antepone a cualquier otra consideración.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_balance import PlayerBalanceQueryService
from app.application.queries.weekly import latest_per_iso_week
from app.domain.engines import academy_engine as ae
from app.domain.engines import youth_skill_score as yss
from app.domain.engines.academy_engine import (
    YOUTH_SKILLS,
    YouthSkill,
    academy_roi,
    evaluate,
    rank,
    training_exposure,
)
from app.domain.engines.position_engine import _config as position_config
from app.domain.value_objects.ht_constants import SKILL_LABELS, SPECIALTIES, training_target
from app.infrastructure.db import models as m

# Un año de Hattrick son 112 días. Mismo número que usa `academy_engine`.
DAYS_PER_HT_YEAR = 112

# Con menos techos revelados que esto, el veredicto sobre un canterano es
# provisional y conviene decirlo en la ficha. La regla vive en el motor: la
# misma cifra decide que no se recomiende un despido sobre una sola lectura.
from app.domain.engines.academy_engine import (  # noqa: E402
    veredicto_provisional,
)


@lru_cache(maxsize=1)
def position_contributions() -> dict[str, dict[str, dict[str, float]]]:
    """La matriz del Manual tal cual: posición -> sector -> habilidad -> coef.

    Se entrega SIN agregar. Antes se sumaba aquí sobre todas las posiciones y
    eso ya decidía el criterio a espaldas del motor; ahora el motor recibe el
    detalle y elige qué hacer con él (ver `block_trainable`).
    """
    return {
        position: {
            sector: {skill: float(coef) for skill, coef in skills.items()}
            for sector, skills in spec.get("contributions", {}).items()
        }
        for position, spec in position_config()["positions"].items()
    }


@dataclass
class SkillScoreRow:
    """Una habilidad de la academia, puntuada — ver `youth_skill_score`.

    Responde "¿qué entreno?", que en juveniles es la única pregunta que
    importa: se entrena una habilidad y la reciben todos a la vez.
    """

    skill: str
    label: str
    score: float
    counts: dict[str, int]
    trainable_count: float
    #  Todos los canteranos ordenados por lo que sacan en esta habilidad:
    #  es la respuesta a "¿a quién le doy los minutos?".
    players: list[yss.PlayerNote]
    #  Los que ya tocaron techo en esta habilidad: fuera de la cola, pero
    #  contados, para poder explicar el hueco en pantalla.
    at_max: list[yss.PlayerNote]


@dataclass
class SkillRow:
    """Una habilidad juvenil. Nivel actual y techo se revelan por SEPARADO.

    El ojeador puede haber dicho "juega a nivel 5" sin decir hasta dónde
    llegará, y al revés. Antes esto se aplastaba: el nivel desconocido se
    guardaba como 0 —indistinguible de un 0 real— y `is_revealed` miraba sólo
    el techo, así que una habilidad con nivel conocido se pintaba como si no
    se supiera nada de ella.
    """

    skill: str
    current: int | None
    maximum: int | None
    is_current_known: bool
    is_max_known: bool
    headroom: int
    #: `IsMaxReached` de CHPP: ya tocó su techo y no subirá más, aunque el
    #: techo siga oculto. Es lo que Hattrick pinta con un candado.
    max_reached: bool = False


@dataclass
class YouthRow:
    ht_youth_player_id: int
    name: str
    age_years: int
    age_days: int
    potential_score: float
    #: En que se puede convertir, en HTMS28, con lo que el ojeador ha dicho.
    #: Sustituye a `potential_score` en pantalla desde el 2026-08-24: aquel
    #: era un indice inventado por esta herramienta y ponia un 8 supuesto en
    #: cada techo sin revelar, asi que ordenaba por ignorancia.
    htms28_min: int
    htms28_max: int
    category: str
    best_skill: str
    best_skill_max: int | None
    days_until_deadline: int
    weeks_until_deadline: int
    #: `CanBePromotedIn` de CHPP: dias que faltan para poder subirlo al primer
    #: equipo. Es OTRA cosa que `days_until_deadline`, que cuenta hasta que se
    #: pierde por edad. Un canterano puede estar a 90 dias de poder subir y a
    #: 300 de perderse: entre esas dos fechas esta la ventana para decidir.
    can_be_promoted_in: int | None
    revealed_skills: int
    verdict_is_provisional: bool
    promote_advice: str
    training_exposure: float
    #: Minutos del ultimo partido oficial. Ya se usaba para calcular
    #: `training_exposure`, pero el numero en crudo hace falta en pantalla para
    #: poder preguntar "quien jugo" sin deducirlo de un porcentaje.
    minutes_last_match: int
    #: La especialidad, ya traducida -- el mismo texto que manda la plantilla
    #: principal, para que la pantalla la pinte con el mismo componente. Es lo
    #: unico de un canterano sin ojear que ya dice algo: llega desde el primer
    #: dia, cuando ninguna habilidad se ha revelado todavia.
    specialty: str
    skills: list[SkillRow]


@dataclass
class GraduateRow:
    name: str
    #: Cuando llego a su club actual. No es la fecha de ascenso.
    arrived_at_current_team: str | None
    sold_at: str | None
    sold_for: int | None
    current_team: str | None
    current_tsi: int | None


@dataclass
class AcademyResponse:
    team_name: str
    currency: str
    #: El pais del club, para la bandera de la tabla. Va en la respuesta y no
    #: por canterano a proposito: Hattrick no publica nacionalidad de un
    #: juvenil --su fichero no la trae-- porque salen todos de la cantera de tu
    #: propio pais. Una columna por fila diria lo mismo dieciocho veces, asi
    #: que el dato viaja una vez y la pantalla decide como pintarlo.
    country_code: str
    country_name: str
    squad_size: int
    players: list[YouthRow]
    #: Los de la academia ACTUAL. Es la lista que alimenta el ROI: sumar
    #: canteranos de academias anteriores contra la inversion de esta seria
    #: restar dos cosas que no se corresponden.
    graduates: list[GraduateRow]
    #: TODOS los que han pasado por el club, de cualquier academia. Es la que
    #: alimenta la pestaña «Antiguos canteranos»: alli la pregunta es "quien
    #: salio de aqui", y la academia de la que salio no la acota.
    all_graduates: list[GraduateRow]
    invested: int
    earned: int
    net: int
    seasons: int
    # Una academia recién abierta lleva semanas, no temporadas: mostrar "0
    # temporadas" convierte un dato correcto en uno que parece un error.
    weeks: int
    weekly_cost: int
    break_even_sales: int
    roi_verdict: str
    urgent: list[str]
    skill_scores: list[SkillScoreRow] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _fila_de_graduado(
    g: m.FormerYouthPlayer,
    ventas: dict[int, tuple[datetime | None, int | None]],
    conv: Callable[[int | None], int | None],
) -> GraduateRow:
    """Un ex-canterano, con su venta si la hubo.

    La venta se toma de su FICHA y no de `former_youth_players`: `viewOldies`
    no dice si se vendio ni por cuanto, y ese campo se quedaria vacio para
    siempre. Son el mismo jugador, enlazados por identificador.
    """
    vendido, precio = ventas.get(g.ht_player_id, (g.sold_at, g.sold_for))
    return GraduateRow(
        name=g.name,
        arrived_at_current_team=_iso(g.arrived_at_current_team),
        sold_at=_iso(vendido),
        sold_for=conv(precio) if precio else None,
        current_team=g.current_team_name,
        current_tsi=g.current_tsi,
    )


def _iso_o_nada(d: datetime | None) -> str | None:
    return d.isoformat() if d is not None else None


class AcademyQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def trainable_by_method(
        self, team_id: int, method: str, manual: dict[str, float] | None = None
    ) -> dict[str, float]:
        """El conteo de "entrenables" según el método elegido."""
        if method == yss.TrainableMethod.EDIT:
            return dict(manual or {})
        if method == yss.TrainableMethod.SLOTS:
            return yss.slot_trainable()
        if method == yss.TrainableMethod.SENIOR:
            return yss.senior_trainable(await self._senior_training_skill(team_id))
        return yss.block_trainable(method, position_contributions())

    async def _senior_training_skill(self, team_id: int) -> str | None:
        """Qué habilidad entrena hoy el primer equipo, si se sabe."""
        row = await self._s.scalar(
            select(m.TrainingSnapshot)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        )
        return training_target(row.training_type) if row is not None else None

    async def skill_scores(
        self,
        team_id: int,
        *,
        soon_max_days: int = yss.SOON_MAX_DAYS,
        weight_base: float = yss.DEFAULT_WEIGHT_BASE,
        trainable_weight: float | None = None,
        trainable: dict[str, float] | None = None,
        as_of: datetime | None = None,
    ) -> list[SkillScoreRow] | None:
        """El puntaje "qué entrenar" recalculado con otros parámetros.

        El MÉTODO es el de la hoja del usuario y no se toca; lo que se mueve
        son los dos números que son una opinión (dónde cae el corte del plazo,
        cuánto separa un peldaño del siguiente) y el conteo de a cuántos les
        llega el entrenamiento.
        """
        candidates = await self._candidates(team_id, as_of)
        if candidates is None:
            return None
        return [
            SkillScoreRow(
                skill=row.skill,
                label=SKILL_LABELS.get(row.skill, row.skill),
                score=row.score,
                counts=row.counts,
                trainable_count=row.trainable_count,
                players=row.players,
                at_max=row.at_max,
            )
            for row in yss.score_skills(
                candidates,
                trainable,
                soon_max_days=soon_max_days,
                weight_base=weight_base,
                trainable_weight=trainable_weight,
            )
        ]

    async def _candidates(
        self, team_id: int, as_of: datetime | None = None
    ) -> list[yss.YouthCandidate] | None:
        """Los canteranos, en la forma que espera el motor.

        Con `as_of`, los de entonces: es como se obtiene el puntaje contra el
        que comparar.
        """
        pairs = await self._latest_snapshots(team_id, as_of)
        if not pairs:
            return None
        out: list[yss.YouthCandidate] = []
        for snap, player in pairs:
            promotable_in = snap.can_be_promoted_in
            at_promotion = (
                snap.age_years * DAYS_PER_HT_YEAR + snap.age_days + promotable_in + 1
                if promotable_in is not None
                else None
            )
            out.append(
                yss.YouthCandidate(
                    name=f"{player.first_name} {player.last_name}",
                    age_years_at_deadline=(
                        at_promotion // DAYS_PER_HT_YEAR if at_promotion is not None else 0
                    ),
                    # Sin `CanBePromotedIn` no se sabe cuándo sale. El
                    # respaldo queda FUERA del alcance del mando para que
                    # moverlo no voltee de golpe a todos los que no tienen el
                    # dato — ver `UNKNOWN_DEADLINE_DAYS`.
                    age_days_at_deadline=(
                        at_promotion % DAYS_PER_HT_YEAR
                        if at_promotion is not None
                        else yss.UNKNOWN_DEADLINE_DAYS
                    ),
                    age_years=snap.age_years,
                    age_days=snap.age_days,
                    skills={
                        skill: yss.YouthSkillReading(
                            current=getattr(snap, skill),
                            maximum=getattr(snap, f"{skill}_max"),
                            max_reached=bool(getattr(snap, f"{skill}_max_reached", False)),
                        )
                        for skill in YOUTH_SKILLS
                    },
                )
            )
        return out

    async def comparativa(
        self,
        team_id: int,
        ventana: str = "cambio",
        *,
        soon_max_days: int = yss.SOON_MAX_DAYS,
        weight_base: float = yss.DEFAULT_WEIGHT_BASE,
        trainable_weight: float | None = None,
        trainable: dict[str, float] | None = None,
    ) -> dict[str, Any] | None:
        """Qué se movió en la academia, y por qué se movió el puntaje.

        Un puntaje que cambia sin decir por qué no sirve para decidir nada: lo
        que importa no es que Lateral subiera 0,041, sino que subió porque a
        Ireneo le subió el nivel y el ojeador reveló dos techos.

        `ventana` es «cambio» (el estado justo antes del último cambio) o un
        número de semanas. Manda sobre TODO lo que se compara aquí, igual que
        en Economía: dos ventanas distintas dentro de la misma pantalla es lo
        que hace imposible explicar un número (2026-09-04, decisión del
        usuario).
        """
        desde = (
            await self._momento_anterior(team_id)
            if ventana == "cambio"
            else datetime.now(UTC) - timedelta(weeks=int(ventana))
        )
        ahora = await self.skill_scores(
            team_id,
            soon_max_days=soon_max_days,
            weight_base=weight_base,
            trainable_weight=trainable_weight,
            trainable=trainable,
        )
        if ahora is None:
            return None

        antes = (
            None
            if desde is None
            else await self.skill_scores(
                team_id,
                soon_max_days=soon_max_days,
                weight_base=weight_base,
                trainable_weight=trainable_weight,
                trainable=trainable,
                as_of=desde,
            )
        )
        antes_por_habilidad = {r.skill: r.score for r in (antes or [])}
        # Los conteos de cada cubo, para poder enseñar el -1 en «desconocido»
        # junto al +1 en «insuficiente»: es lo que hace la fila auditable
        # (2026-09-04, pedido del usuario).
        cubos_antes = {r.skill: r.counts for r in (antes or [])}
        # Sin puntaje de antes no hay comparación posible, y entonces NADA se
        # compara: sin esto, una ventana que empieza antes del primer dato
        # marcaba a los 18 canteranos como recién llegados, porque ninguno
        # tenía foto vieja (2026-09-04).
        if antes is None:
            desde = None

        # Las dos fotos de la plantilla, emparejadas por canterano.
        viejas = {
            player.ht_youth_player_id: snap
            for snap, player in (
                await self._latest_snapshots(team_id, desde) if desde is not None else []
            )
        }
        nuevas = await self._latest_snapshots(team_id)

        jugadores: list[dict[str, Any]] = []
        subidas = techos_nuevos = 0
        for snap, player in nuevas:
            vieja = viejas.get(player.ht_youth_player_id)
            habilidades: dict[str, dict[str, Any]] = {}
            for skill in YOUTH_SKILLS:
                actual = getattr(snap, skill)
                techo = getattr(snap, f"{skill}_max")
                anterior = getattr(vieja, skill) if vieja is not None else None
                techo_antes = getattr(vieja, f"{skill}_max") if vieja is not None else None
                subio = anterior is not None and actual is not None and actual > anterior
                # Un techo recién revelado no mueve el nivel pero SÍ mueve el
                # puntaje: sin marcarlo, la cifra sube y no hay ninguna flecha
                # que lo explique.
                techo_revelado = vieja is not None and techo_antes is None and techo is not None
                if subio:
                    subidas += 1
                if techo_revelado:
                    techos_nuevos += 1
                habilidades[skill] = {
                    "current": actual,
                    "max": techo,
                    "before": anterior if subio else None,
                    "maxNewlyKnown": techo_revelado,
                }
            jugadores.append(
                {
                    "htYouthPlayerId": player.ht_youth_player_id,
                    "name": f"{player.first_name} {player.last_name}",
                    # Sin foto vieja es que no estaba: o llegó dentro de la
                    # ventana, o la ventana empieza antes de que hubiera datos.
                    "isNew": desde is not None and vieja is None,
                    "skills": habilidades,
                }
            )

        llegados = sum(1 for j in jugadores if j["isNew"])
        return {
            "window": ventana,
            "since": _iso_o_nada(desde),
            # Sin pasado con el que comparar no se inventa uno: la pantalla
            # enseña los puntajes quietos y lo dice.
            "hasBaseline": antes is not None,
            "scores": [
                {
                    "skill": r.skill,
                    "score": r.score,
                    "delta": (
                        round(r.score - antes_por_habilidad[r.skill], 3)
                        if r.skill in antes_por_habilidad
                        else None
                    ),
                    "counts": r.counts,
                    "countDeltas": (
                        {
                            cubo: r.counts[cubo] - cubos_antes[r.skill].get(cubo, 0)
                            for cubo in r.counts
                        }
                        if r.skill in cubos_antes
                        else None
                    ),
                }
                for r in ahora
            ],
            "players": jugadores,
            "summary": {
                "skillsUp": subidas,
                "ceilingsRevealed": techos_nuevos,
                "arrivals": llegados,
            },
        }

    async def _latest_snapshots(
        self, team_id: int, as_of: datetime | None = None
    ) -> list[tuple[m.YouthSnapshot, m.YouthPlayer]]:
        """La academia tal como estaba en un instante.

        Con `as_of` se queda la última foto de cada canterano tomada hasta esa
        fecha, que es lo que permite recalcular un puntaje del pasado con la
        MISMA fórmula de hoy: comparar dos números que salieron de dos
        fórmulas distintas no diría nada (2026-09-04).

        Los que ya se fueron siguen fuera. Un canterano que estaba en la foto
        vieja y hoy no está no aparece aquí, y su desaparición se nota en el
        puntaje, que es donde tiene que notarse.
        """
        consulta = (
            select(m.YouthSnapshot, m.YouthPlayer)
            .join(m.YouthPlayer, m.YouthPlayer.id == m.YouthSnapshot.youth_player_id)
            .where(m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None))
        )
        if as_of is not None:
            consulta = consulta.where(m.YouthSnapshot.captured_at <= as_of)
        rows = await self._s.execute(consulta.order_by(m.YouthSnapshot.captured_at))
        latest: dict[int, tuple[m.YouthSnapshot, m.YouthPlayer]] = {}
        for snap, player in rows.all():
            latest[player.id] = (snap, player)  # el orden asc deja el último
        return list(latest.values())

    async def _momento_anterior(self, team_id: int) -> datetime | None:
        """El instante justo ANTES del último cambio de la academia.

        Las fotos son de sólo-cuando-cambia-algo, así que la marca de tiempo
        inmediatamente anterior a la más nueva es el estado previo. Devuelve
        `None` cuando sólo hay una lectura: sin pasado no hay comparación, y
        una de cero es peor que ninguna.
        """
        marcas = list(
            (
                await self._s.execute(
                    select(m.YouthSnapshot.captured_at)
                    .join(m.YouthPlayer, m.YouthPlayer.id == m.YouthSnapshot.youth_player_id)
                    .where(m.YouthPlayer.team_id == team_id)
                    .distinct()
                    .order_by(m.YouthSnapshot.captured_at.desc())
                    .limit(2)
                )
            ).scalars()
        )
        return marcas[1] if len(marcas) > 1 else None

    async def get(self, team_id: int) -> AcademyResponse | None:
        team = await self._s.get(m.Team, team_id)
        if team is None:
            return None

        rate = team.currency_rate or 1.0

        def conv(v: float | None) -> int:
            return int(round((v or 0) / rate))

        pairs = await self._latest_snapshots(team_id)
        evaluations = []
        rows_by_name: dict[str, tuple[m.YouthSnapshot, m.YouthPlayer]] = {}
        for snap, player in pairs:
            skills = {
                s: YouthSkill(
                    current=getattr(snap, s) or 0,
                    maximum=getattr(snap, f"{s}_max"),
                )
                for s in YOUTH_SKILLS
            }
            name = f"{player.first_name} {player.last_name}"
            evaluations.append(
                evaluate(
                    name=name,
                    age_years=snap.age_years,
                    age_days=snap.age_days,
                    skills=skills,
                )
            )
            rows_by_name[name] = (snap, player)

        players: list[YouthRow] = []
        candidates: list[yss.YouthCandidate] = []
        for ev in rank(evaluations):
            snap, player = rows_by_name[ev.name]
            # "Edad al salir": la que tendrá el día que se le pueda promocionar
            # (`Juveniles!F`/`G` de la hoja). NO es el plazo para no perderlo
            # por edad — son dos relojes distintos y el que decide a quién da
            # tiempo de entrenar es éste.
            promotable_in = snap.can_be_promoted_in
            at_promotion = (
                snap.age_years * DAYS_PER_HT_YEAR + snap.age_days + promotable_in + 1
                if promotable_in is not None
                else None
            )
            candidates.append(
                yss.YouthCandidate(
                    name=ev.name,
                    age_years_at_deadline=(
                        at_promotion // DAYS_PER_HT_YEAR if at_promotion is not None else 0
                    ),
                    # Sin `CanBePromotedIn` no se sabe cuándo sale, y el cubo
                    # "le queda tiempo" es el que no le da ventaja a nadie.
                    # Sin `CanBePromotedIn` no se sabe cuándo sale. El
                    # respaldo queda FUERA del alcance del mando para que
                    # moverlo no voltee de golpe a todos los que no tienen el
                    # dato — ver `UNKNOWN_DEADLINE_DAYS`.
                    age_days_at_deadline=(
                        at_promotion % DAYS_PER_HT_YEAR
                        if at_promotion is not None
                        else yss.UNKNOWN_DEADLINE_DAYS
                    ),
                    age_years=snap.age_years,
                    age_days=snap.age_days,
                    skills={
                        skill: yss.YouthSkillReading(
                            current=getattr(snap, skill),
                            maximum=getattr(snap, f"{skill}_max"),
                            max_reached=bool(getattr(snap, f"{skill}_max_reached", False)),
                        )
                        for skill in YOUTH_SKILLS
                    },
                )
            )
            horquilla = candidates[-1].horquilla_htms28
            exposure = training_exposure(
                minutes_main_position=snap.minutes_last_match,
                minutes_secondary_position=0,
                is_official_match=True,
            )
            players.append(
                YouthRow(
                    ht_youth_player_id=player.ht_youth_player_id,
                    name=ev.name,
                    age_years=ev.age_years,
                    age_days=ev.age_days,
                    potential_score=ev.potential_score,
                    htms28_min=horquilla.minimo,
                    htms28_max=horquilla.maximo,
                    category=ev.category.value,
                    best_skill=ev.best_skill,
                    best_skill_max=ev.best_skill_max,
                    days_until_deadline=ev.days_until_deadline,
                    weeks_until_deadline=ev.days_until_deadline // 7,
                    can_be_promoted_in=snap.can_be_promoted_in,
                    revealed_skills=ev.revealed_skills,
                    verdict_is_provisional=veredicto_provisional(
                        ev.category, ev.revealed_skills, len(YOUTH_SKILLS)
                    ),
                    promote_advice=ev.promote_advice,
                    training_exposure=exposure,
                    minutes_last_match=snap.minutes_last_match or 0,
                    specialty=SPECIALTIES.get(player.specialty or 0, ""),
                    skills=[
                        SkillRow(
                            skill=s,
                            current=getattr(snap, s),
                            maximum=getattr(snap, f"{s}_max"),
                            is_current_known=getattr(snap, s) is not None,
                            is_max_known=getattr(snap, f"{s}_max") is not None,
                            headroom=YouthSkill(
                                current=getattr(snap, s) or 0,
                                maximum=getattr(snap, f"{s}_max"),
                            ).headroom,
                            max_reached=bool(getattr(snap, f"{s}_max_reached", False)),
                        )
                        for s in YOUTH_SKILLS
                    ],
                )
            )

        # La venta de cada ex-canterano NO viene en `viewOldies` --ese fichero
        # solo dice quien paso por aqui y donde esta ahora-- pero si esta en su
        # ficha: son los mismos, enlazados por identificador. Sin este cruce la
        # pantalla enseñaba una coma suelta donde deberia ir el precio.
        ventas = {
            pid: (vendido, precio)
            for pid, vendido, precio in (
                await self._s.execute(
                    select(m.Player.ht_player_id, m.Player.sold_at, m.Player.sale_price).where(
                        m.Player.team_id == team_id,
                        m.Player.sold_at.is_not(None),
                    )
                )
            ).all()
        }

        all_graduates = list(
            (
                await self._s.execute(
                    select(m.FormerYouthPlayer)
                    .where(m.FormerYouthPlayer.team_id == team_id)
                    .order_by(m.FormerYouthPlayer.arrived_at_current_team.desc())
                )
            ).scalars()
        )

        # 2026-08-15, pedido explícitamente: una academia se cierra y se
        # reabre, y cada apertura es una academia DISTINTA. Sumar los
        # canteranos de academias anteriores contra la inversión de la actual
        # es restar dos cosas que no se corresponden — en esta cuenta eran 43
        # ventas viejas (24,6M) contra una academia de dos semanas.
        # `youthteamdetails.CreatedDate` marca el corte. Sin ese dato todavía
        # sincronizado no se inventa un corte: se usa todo y se avisa.
        # El corte se hace por la fecha en que SALIO de aqui, que es la
        # unica de las dos que ocurre en nuestro club. Hasta el 2026-08-31
        # se hacia por `promoted_at`, que resulto ser cuando llego a su
        # club actual: una fecha posterior a la venta y ajena a nosotros,
        # asi que dejaba entrar canteranos de academias anteriores solo
        # porque hubieran cambiado de equipo hace poco.
        #
        # Quien no tiene venta registrada no se puede situar en el tiempo:
        # se queda fuera del corte y la nota de abajo lo declara.
        def salio_del_club(g: m.FormerYouthPlayer) -> datetime | None:
            """Cuando dejo NUESTRO club. Es la unica de sus fechas que
            ocurre aqui, y por eso es la que puede situarlo en una academia."""
            vendido, _ = ventas.get(g.ht_player_id, (None, None))
            return vendido or g.sold_at

        academy_since = team.youth_academy_created_at
        if academy_since is not None:
            graduates = [
                g
                for g in all_graduates
                if (fecha := salio_del_club(g)) is not None and fecha >= academy_since
            ]
        else:
            graduates = all_graduates

        # Inversión: suma del gasto juvenil de cada SEMANA observada.
        #
        # 2026-08-15, bug real encontrado al preguntar de dónde salía la cifra:
        # esto contaba `len(economy)`, es decir un "semana" por cada snapshot
        # económico. Pero los snapshots son por sync, no por semana: 34 lecturas
        # cubrían del 26/07 al 15/08 — tres semanas, no treinta y cuatro. La
        # inversión salía inflada ~11x (680.000 en vez de ~60.000).
        #
        # `latest_per_iso_week` colapsa a una lectura por semana ISO, que es lo
        # que el cálculo quería decir desde el principio.
        economy_rows = list(
            (
                await self._s.execute(
                    select(m.EconomySnapshot)
                    .where(m.EconomySnapshot.team_id == team_id)
                    .order_by(m.EconomySnapshot.captured_at)
                )
            ).scalars()
        )
        # La inversión tampoco puede empezar antes que la academia: cobrar
        # semanas anteriores a su apertura infla el coste igual que sumar
        # ventas viejas inflaba el ingreso.
        if academy_since is not None:
            economy_rows = [e for e in economy_rows if e.captured_at >= academy_since]
        economy = latest_per_iso_week(economy_rows, lambda s: s.captured_at)
        # 2026-08-16, corregido a petición del usuario: la inversión es la SUMA
        # del gasto juvenil de cada semana observada, no el gasto de la última
        # semana multiplicado por el número de semanas. Si subiste o bajaste la
        # inversión juvenil alguna vez, multiplicar reescribe todo el pasado con
        # el precio de hoy.
        invested = sum(conv(e.costs_youth) for e in economy)
        weekly_cost = conv(economy[-1].costs_youth) if economy else 0
        weeks = len(economy)

        # Lo ingresado por la cantera NO es el precio de venta bruto — 2026-08-15,
        # pedido explícitamente: "todos los pagos por club de origen y club
        # anterior". `Transferencias` ya calcula lo que de verdad entró por
        # cada canterano y este módulo se estaba quedando con `sold_for` crudo,
        # que ignora tres cosas:
        #   · la comisión del agente (para un canterano, la reducida de primera
        #     venta de cantera, no la de un fichaje),
        #   · los bonos de club anterior/origen que se siguen cobrando cuando el
        #     club comprador lo revende (`PreviousClubBonus`, importes exactos),
        #   · que un canterano no tuvo precio de compra.
        # Se reutiliza esa misma fuente para que las dos pantallas no puedan
        # discrepar sobre lo mismo.
        balance = await PlayerBalanceQueryService(self._s).get(team_id)
        # Un canterano de una academia anterior sigue teniendo `MotherClub` =
        # nosotros, así que `is_academy_graduate` por sí solo no distingue de
        # qué academia salió. El corte lo pone la lista ya filtrada arriba.
        current_graduate_ids = {g.ht_player_id for g in graduates}
        all_academy_rows = [
            r for r in (balance.players if balance else []) if r.is_academy_graduate
        ]
        academy_rows = [
            r
            for r in all_academy_rows
            if academy_since is None or r.ht_player_id in current_graduate_ids
        ]
        sold_rows = [r for r in academy_rows if r.is_sold and r.sale_price]
        net_sales = sum(round((r.sale_price or 0) * (1 - (r.agent_pct or 0.0))) for r in sold_rows)
        # Los bonos se cobran aunque el canterano ya no sea nuestro: cuentan
        # para TODOS los canteranos vendidos, no sólo los de esta temporada.
        resale_bonuses = round(sum(r.resale_bonus_share for r in academy_rows))

        # Un canterano promocionado y vendido puede vivir SOLO en
        # `former_youth_players` (sin fila en `players`, p. ej. si salió antes
        # de que empezáramos a guardar plantilla). Para esos no hay comisión ni
        # bonos que calcular: se cuenta el bruto, que es lo único que existe, y
        # se avisa en una nota — mejor un dato incompleto y señalado que
        # perderlo de la suma.
        detailed_ids = {r.ht_player_id for r in academy_rows}
        gross_only = [g for g in graduates if g.sold_for and g.ht_player_id not in detailed_ids]
        gross_only_total = sum(conv(g.sold_for) for g in gross_only)

        sales = net_sales + resale_bonuses + gross_only_total
        sold_count = len(sold_rows) + len(gross_only)
        avg_sale = (net_sales + gross_only_total) // sold_count if sold_count else 0
        roi = academy_roi(
            invested=invested,
            weeks_invested=weeks,
            sales_income=sales,
            average_sale_price=avg_sale,
            weekly_investment=weekly_cost,
        )

        urgent = [
            f"{p.name}: quedan {p.days_until_deadline} días "
            f"({p.weeks_until_deadline} semanas) para promocionarlo"
            for p in players
            if p.days_until_deadline <= 21
        ]

        # 2026-08-16: el usuario recorrió los caveats uno por uno y mandó borrar
        # todos los de esta pantalla. El único que queda es el que avisa de que
        # el ROI está inflado porque aún no sabemos cuándo abrió la academia.
        notes: list[str] = []
        if academy_since is None:
            notes.append(
                "Sincroniza para acotar la academia: sin su fecha de apertura se "
                "cuentan también los canteranos de canteras anteriores."
            )

        # `trainable` (`AuxiJuveniles!M`) se teclea a mano en la hoja: es
        # cuántos canteranos reciben de verdad cada entrenamiento, y depende
        # de la alineación juvenil, que CHPP no da en este fichero. Sin ese
        # dato el sumando vale 0 y el resto del puntaje es idéntico — se
        # prefiere un puntaje incompleto y honesto a uno estimado.
        # Quien sobra: UNO solo, el que menos aporta a los puntajes. Se marca
        # aqui --y no en `evaluate`-- porque es una decision de PLANTILLA, no
        # de canterano: despedir libera una plaza, asi que la pregunta es
        # quien es el ultimo de la fila, no si alguien es malo en abstracto.
        _marca_al_que_sobra(players, candidates)
        skill_scores = [
            SkillScoreRow(
                skill=row.skill,
                label=SKILL_LABELS.get(row.skill, row.skill),
                score=row.score,
                counts=row.counts,
                trainable_count=row.trainable_count,
                players=row.players,
                at_max=row.at_max,
            )
            for row in yss.score_skills(candidates)
        ]

        # El pais del club sale del contexto del mundo por su liga. Si esa fila
        # no esta sincronizada todavia, se devuelve vacio y la pantalla pinta el
        # hueco neutro que ya tiene: nunca una bandera adivinada.
        mundo = (
            await self._s.execute(
                select(m.WorldContext.country_code, m.WorldContext.country_name).where(
                    m.WorldContext.ht_league_id == team.ht_league_id
                )
            )
        ).first()

        return AcademyResponse(
            skill_scores=skill_scores,
            team_name=team.name,
            currency=team.currency_name or "",
            country_code=(mundo.country_code if mundo else "") or "",
            country_name=(mundo.country_name if mundo else "") or team.league_name or "",
            squad_size=len(players),
            players=players,
            graduates=[_fila_de_graduado(g, ventas, conv) for g in graduates],
            all_graduates=[_fila_de_graduado(g, ventas, conv) for g in all_graduates],
            invested=roi.invested,
            earned=roi.earned,
            net=roi.net,
            seasons=roi.seasons,
            weeks=weeks,
            weekly_cost=roi.weekly_cost,
            break_even_sales=roi.break_even_sales,
            roi_verdict=roi.verdict,
            urgent=urgent,
            notes=notes,
        )


def _iso(dt: datetime | None) -> str | None:
    return dt.date().isoformat() if dt else None


def _marca_al_que_sobra(
    players: list[YouthRow],
    candidates: list[yss.YouthCandidate],
) -> None:
    """Le cambia el consejo al canterano que menos aporta. Solo a uno.

    El aporte se mide con LOS MISMOS pesos que el ranking de entrenamiento:
    si un chico no mueve ninguno de los siete puntajes, es el que menos
    cuesta soltar. Empata el mas viejo.

    No se toca a quien tiene un aviso mas urgente --el plazo por vencerse-- ni
    a quien no tiene ni una habilidad revelada: de ese no se sabe si aporta
    poco o si simplemente no lo hemos mirado.
    """
    if not players:
        return
    pesos = yss.weights_for()
    cubos: dict[str, list[str]] = {}
    edades: dict[str, int] = {}
    for c in candidates:
        pronto = yss.leaves_soon(c)
        cubos[c.name] = [
            yss.bucket_of(yss.skill_note(r), leaves_soon=pronto, max_reached=r.max_reached)
            for r in c.skills.values()
        ]
        edades[c.name] = c.edad_en_dias

    # Fuera de la quiniela quien no tiene NADA revelado: aporta poco porque no
    # lo hemos mirado, no porque no valga.
    sin_ojear = {p.name for p in players if p.revealed_skills == 0}
    aportes = {n: v for n, v in ae.aporte_de_cada_uno(cubos, pesos).items() if n not in sin_ojear}
    sobra = ae.quien_sobra(aportes, edades)
    if sobra is None:
        return
    for p in players:
        if p.name == sobra and "URGENTE" not in p.promote_advice:
            p.promote_advice = (
                "es el que menos aporta de la academia: si necesitas la plaza, "
                "es a este a quien soltar"
            )
