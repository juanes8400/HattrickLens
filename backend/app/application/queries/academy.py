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
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.queries.player_balance import PlayerBalanceQueryService
from app.application.queries.weekly import latest_per_iso_week
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
from app.domain.value_objects.ht_constants import SKILL_LABELS, training_target
from app.infrastructure.db import models as m

# Un año de Hattrick son 112 días. Mismo número que usa `academy_engine`.
DAYS_PER_HT_YEAR = 112

# Con menos techos revelados que esto, el veredicto sobre un canterano
# es provisional y conviene decirlo en la ficha.
MIN_REVEALED_FOR_A_VERDICT = 3


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


@dataclass
class YouthRow:
    ht_youth_player_id: int
    name: str
    age_years: int
    age_days: int
    potential_score: float
    category: str
    best_skill: str
    best_skill_max: int | None
    days_until_deadline: int
    weeks_until_deadline: int
    revealed_skills: int
    verdict_is_provisional: bool
    promote_advice: str
    training_exposure: float
    skills: list[SkillRow]


@dataclass
class GraduateRow:
    name: str
    promoted_at: str | None
    sold_at: str | None
    sold_for: int | None
    current_team: str | None
    current_tsi: int | None


@dataclass
class AcademyResponse:
    team_name: str
    currency: str
    squad_size: int
    players: list[YouthRow]
    graduates: list[GraduateRow]
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
    ) -> list[SkillScoreRow] | None:
        """El puntaje "qué entrenar" recalculado con otros parámetros.

        El MÉTODO es el de la hoja del usuario y no se toca; lo que se mueve
        son los dos números que son una opinión (dónde cae el corte del plazo,
        cuánto separa un peldaño del siguiente) y el conteo de a cuántos les
        llega el entrenamiento.
        """
        candidates = await self._candidates(team_id)
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
            )
            for row in yss.score_skills(
                candidates,
                trainable,
                soon_max_days=soon_max_days,
                weight_base=weight_base,
                trainable_weight=trainable_weight,
            )
        ]

    async def _candidates(self, team_id: int) -> list[yss.YouthCandidate] | None:
        """Los canteranos de hoy, en la forma que espera el motor."""
        pairs = await self._latest_snapshots(team_id)
        if not pairs:
            return None
        out: list[yss.YouthCandidate] = []
        for snap, player in pairs:
            promotable_in = snap.can_be_promoted_in
            at_promotion = (
                snap.age_years * DAYS_PER_HT_YEAR + snap.age_days + promotable_in + 1
                if promotable_in is not None else None
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
                        if at_promotion is not None else yss.UNKNOWN_DEADLINE_DAYS
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

    async def _latest_snapshots(self, team_id: int) -> list[tuple[m.YouthSnapshot, m.YouthPlayer]]:
        rows = await self._s.execute(
            select(m.YouthSnapshot, m.YouthPlayer)
            .join(m.YouthPlayer, m.YouthPlayer.id == m.YouthSnapshot.youth_player_id)
            .where(m.YouthPlayer.team_id == team_id, m.YouthPlayer.left_at.is_(None))
            .order_by(m.YouthSnapshot.captured_at)
        )
        latest: dict[int, tuple[m.YouthSnapshot, m.YouthPlayer]] = {}
        for snap, player in rows.all():
            latest[player.id] = (snap, player)      # el orden asc deja el último
        return list(latest.values())

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
                if promotable_in is not None else None
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
                        if at_promotion is not None else yss.UNKNOWN_DEADLINE_DAYS
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
                    category=ev.category.value,
                    best_skill=ev.best_skill,
                    best_skill_max=ev.best_skill_max,
                    days_until_deadline=ev.days_until_deadline,
                    weeks_until_deadline=ev.days_until_deadline // 7,
                    revealed_skills=ev.revealed_skills,
                    verdict_is_provisional=ev.revealed_skills < MIN_REVEALED_FOR_A_VERDICT,
                    promote_advice=ev.promote_advice,
                    training_exposure=exposure,
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
                        )
                        for s in YOUTH_SKILLS
                    ],
                )
            )

        all_graduates = list(
            (
                await self._s.execute(
                    select(m.FormerYouthPlayer)
                    .where(m.FormerYouthPlayer.team_id == team_id)
                    .order_by(m.FormerYouthPlayer.promoted_at.desc())
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
        academy_since = team.youth_academy_created_at
        if academy_since is not None:
            graduates = [
                g for g in all_graduates
                if g.promoted_at is not None and g.promoted_at >= academy_since
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
        economy_rows = list((
            await self._s.execute(
                select(m.EconomySnapshot)
                .where(m.EconomySnapshot.team_id == team_id)
                .order_by(m.EconomySnapshot.captured_at)
            )
        ).scalars())
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
            r for r in all_academy_rows
            if academy_since is None or r.ht_player_id in current_graduate_ids
        ]
        sold_rows = [r for r in academy_rows if r.is_sold and r.sale_price]
        net_sales = sum(
            round((r.sale_price or 0) * (1 - (r.agent_pct or 0.0))) for r in sold_rows
        )
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
        gross_only = [
            g for g in graduates
            if g.sold_for and g.ht_player_id not in detailed_ids
        ]
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
        skill_scores = [
            SkillScoreRow(
                skill=row.skill,
                label=SKILL_LABELS.get(row.skill, row.skill),
                score=row.score,
                counts=row.counts,
                trainable_count=row.trainable_count,
                players=row.players,
            )
            for row in yss.score_skills(candidates)
        ]

        return AcademyResponse(
            skill_scores=skill_scores,
            team_name=team.name,
            currency=team.currency_name or "",
            squad_size=len(players),
            players=players,
            graduates=[
                GraduateRow(
                    name=g.name,
                    promoted_at=_iso(g.promoted_at),
                    sold_at=_iso(g.sold_at),
                    sold_for=conv(g.sold_for) if g.sold_for else None,
                    current_team=g.current_team_name,
                    current_tsi=g.current_tsi,
                )
                for g in graduates
            ],
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
