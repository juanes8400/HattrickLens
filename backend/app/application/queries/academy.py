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
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.engines.academy_engine import (
    YOUTH_SKILLS,
    YouthSkill,
    academy_roi,
    evaluate,
    rank,
    training_exposure,
)
from app.infrastructure.db import models as m

SEASON_WEEKS = 16
# Por debajo de esto, el ojeador ha revelado tan poco que cualquier categoría
# es provisional y conviene decirlo en la ficha.
MIN_REVEALED_FOR_A_VERDICT = 3


@dataclass
class SkillRow:
    skill: str
    current: int
    maximum: int | None
    is_revealed: bool
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
    weekly_cost: int
    break_even_sales: int
    roi_verdict: str
    urgent: list[str]
    notes: list[str] = field(default_factory=list)


class AcademyQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

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
        for ev in rank(evaluations):
            snap, player = rows_by_name[ev.name]
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
                            current=getattr(snap, s) or 0,
                            maximum=getattr(snap, f"{s}_max"),
                            is_revealed=getattr(snap, f"{s}_max") is not None,
                            headroom=YouthSkill(
                                current=getattr(snap, s) or 0,
                                maximum=getattr(snap, f"{s}_max"),
                            ).headroom,
                        )
                        for s in YOUTH_SKILLS
                    ],
                )
            )

        graduates = list(
            (
                await self._s.execute(
                    select(m.FormerYouthPlayer)
                    .where(m.FormerYouthPlayer.team_id == team_id)
                    .order_by(m.FormerYouthPlayer.promoted_at.desc())
                )
            ).scalars()
        )

        # Inversión: coste semanal de juveniles × semanas con snapshot económico.
        economy = list(
            (
                await self._s.execute(
                    select(m.EconomySnapshot)
                    .where(m.EconomySnapshot.team_id == team_id)
                    .order_by(m.EconomySnapshot.captured_at)
                )
            ).scalars()
        )
        weekly_cost = conv(economy[-1].costs_youth) if economy else 0
        weeks = len(economy)
        sales = sum(conv(g.sold_for) for g in graduates if g.sold_for)
        sold = [g for g in graduates if g.sold_for]
        avg_sale = sales // len(sold) if sold else 0
        roi = academy_roi(
            weekly_investment=weekly_cost,
            weeks_invested=weeks,
            sales_income=sales,
            average_sale_price=avg_sale,
        )

        urgent = [
            f"{p.name}: quedan {p.days_until_deadline} días "
            f"({p.weeks_until_deadline} semanas) para promocionarlo"
            for p in players
            if p.days_until_deadline <= 21
        ]

        notes: list[str] = []
        if not players:
            notes.append(
                "Todavía no hay juveniles sincronizados. La plantilla juvenil "
                "llega con el fichero youthteamdetails de CHPP; el resto del "
                "módulo (retorno de la academia, canteranos promocionados) ya "
                "funciona con lo que hay."
            )
        provisional = [p.name for p in players if p.verdict_is_provisional]
        if provisional:
            notes.append(
                f"Categoría provisional para {', '.join(provisional)}: el ojeador "
                f"ha revelado menos de {MIN_REVEALED_FOR_A_VERDICT} techos. Un "
                "techo sin revelar no es un techo bajo, así que la categoría "
                "puede subir sin que el jugador mejore."
            )
        if weeks and weekly_cost:
            notes.append(
                f"La inversión se calcula como {weekly_cost:,} por semana × "
                f"{weeks} semanas con lectura económica. Con más histórico "
                "sincronizado la cifra se afina sola."
            )

        return AcademyResponse(
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
            weekly_cost=roi.weekly_cost,
            break_even_sales=roi.break_even_sales,
            roi_verdict=roi.verdict,
            urgent=urgent,
            notes=notes,
        )


def _iso(dt: datetime | None) -> str | None:
    return dt.date().isoformat() if dt else None
