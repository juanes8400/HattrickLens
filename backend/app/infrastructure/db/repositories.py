"""Implementaciones SQLAlchemy de los ports de repositorio."""
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db import models as m


class SqlAlchemyPlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert_identity(
        self, ht_player_id: int, team_id: int, first_name: str, last_name: str
    ) -> int:
        row = await self._s.scalar(
            select(m.Player).where(m.Player.ht_player_id == ht_player_id)
        )
        if row is None:
            row = m.Player(
                ht_player_id=ht_player_id,
                team_id=team_id,
                first_name=first_name,
                last_name=last_name,
            )
            self._s.add(row)
            await self._s.flush()
        else:
            if row.team_id != team_id:
                row.team_id = team_id  # llegó al club (transfer detectable aquí)
            if row.left_team_at is not None:
                # 2026-08-05, edge case real encontrado en vivo: un jugador
                # que se fue (venta real o despido) y vuelve a aparecer en
                # players.xml está de vuelta en la plantilla HOY — nunca
                # debe seguir contando como "fuera" solo porque algún día
                # se fue. No se toca sold_at/sale_price (esa venta sí fue
                # real e histórica), solo se limpia la marca de salida.
                row.left_team_at = None
        return row.id

    async def get_last_snapshot_hash(self, ht_player_id: int) -> bytes | None:
        stmt = (
            select(m.PlayerSnapshot.content_hash)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.ht_player_id == ht_player_id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        return cast(bytes | None, await self._s.scalar(stmt))

    async def get_last_snapshot(self, ht_player_id: int) -> dict[str, Any] | None:
        stmt = (
            select(m.PlayerSnapshot)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.ht_player_id == ht_player_id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        snap = await self._s.scalar(stmt)
        if snap is None:
            return None
        return {
            "age_years": snap.age_years, "age_days": snap.age_days, "tsi": snap.tsi,
            "form": snap.form, "stamina": snap.stamina, "experience": snap.experience,
            "salary": snap.salary, "injury_level": snap.injury_level,
            "is_transfer_listed": snap.is_transfer_listed,
            "specialty": snap.specialty, "loyalty": snap.loyalty,
            "leadership": snap.leadership, "agreeability": snap.agreeability,
            "aggressiveness": snap.aggressiveness, "honesty": snap.honesty,
            "mother_club_bonus": snap.mother_club_bonus, "country_id": snap.country_id,
            "league_goals": snap.league_goals, "cup_goals": snap.cup_goals,
            "friendlies_goals": snap.friendlies_goals, "career_goals": snap.career_goals,
            "career_hattricks": snap.career_hattricks, "career_assists": snap.career_assists,
            "player_trainer_skill_level": snap.player_trainer_skill_level,
            "player_trainer_type": snap.player_trainer_type,
            "skills": {
                "keeper": snap.keeper, "defending": snap.defending,
                "playmaking": snap.playmaking, "winger": snap.winger,
                "passing": snap.passing, "scoring": snap.scoring,
                "set_pieces": snap.set_pieces,
            },
        }

    async def append_snapshot(
        self,
        sync_id: int,
        player_id: int,
        data: dict[str, Any],
        content_hash: bytes,
        captured_at: datetime,
    ) -> None:
        skills = data.get("skills", {})
        # `career_assists` y `last_match_*` NO vienen en el payload de
        # `players.xml` (solo en `playerdetails.xml`, fase B — HL-15x): si
        # este append crea una fila nueva por un cambio de otro campo, sin
        # esto se perdería lo que una sincronización de fase B ya había
        # escrito en la fila anterior. Se arrastran desde la última fila en
        # vez de resetearse a 0/None.
        previous = await self._s.scalar(
            select(m.PlayerSnapshot)
            .where(m.PlayerSnapshot.player_id == player_id)
            .order_by(m.PlayerSnapshot.captured_at.desc())
            .limit(1)
        )
        self._s.add(
            m.PlayerSnapshot(
                sync_id=sync_id,
                player_id=player_id,
                captured_at=captured_at,
                age_years=data["age_years"],
                age_days=data["age_days"],
                tsi=data["tsi"],
                form=data["form"],
                stamina=data["stamina"],
                experience=data["experience"],
                salary=data["salary"],
                keeper=skills.get("keeper"),
                defending=skills.get("defending"),
                playmaking=skills.get("playmaking"),
                winger=skills.get("winger"),
                passing=skills.get("passing"),
                scoring=skills.get("scoring"),
                set_pieces=skills.get("set_pieces"),
                injury_level=data.get("injury_level", -1),
                # HL-15x: is_transfer_listed se parseaba pero nunca se escribía
                # aquí — toda fila salía con el default False del modelo
                # aunque el jugador estuviera realmente en la lista.
                is_transfer_listed=data.get("is_transfer_listed", False),
                specialty=data.get("specialty", 0),
                loyalty=data.get("loyalty", 0),
                leadership=data.get("leadership", 0),
                agreeability=data.get("agreeability", 0),
                aggressiveness=data.get("aggressiveness", 0),
                honesty=data.get("honesty", 0),
                mother_club_bonus=data.get("mother_club_bonus", False),
                country_id=data.get("country_id", 0),
                league_goals=data.get("league_goals", 0),
                cup_goals=data.get("cup_goals", 0),
                friendlies_goals=data.get("friendlies_goals", 0),
                career_goals=data.get("career_goals", 0),
                career_hattricks=data.get("career_hattricks", 0),
                career_assists=data.get(
                    "career_assists", previous.career_assists if previous else 0
                ),
                player_trainer_skill_level=data.get("player_trainer_skill_level", 0),
                player_trainer_type=data.get("player_trainer_type", 0),
                last_match_ht_id=previous.last_match_ht_id if previous else None,
                last_match_position_code=(
                    previous.last_match_position_code if previous else None
                ),
                last_match_played_minutes=(
                    previous.last_match_played_minutes if previous else None
                ),
                last_match_rating=previous.last_match_rating if previous else None,
                career_caps=previous.career_caps if previous else None,
                career_caps_u20=previous.career_caps_u20 if previous else None,
                content_hash=content_hash,
            )
        )

    async def count_snapshots(self, team_id: int) -> int:
        stmt = (
            select(func.count())
            .select_from(m.PlayerSnapshot)
            .join(m.Player, m.Player.id == m.PlayerSnapshot.player_id)
            .where(m.Player.team_id == team_id)
        )
        return int(await self._s.scalar(stmt) or 0)

    async def mark_departed(
        self, team_id: int, current_ht_player_ids: set[int], captured_at: datetime
    ) -> list[m.Player]:
        rows = (
            await self._s.execute(
                select(m.Player).where(
                    m.Player.team_id == team_id, m.Player.left_team_at.is_(None)
                )
            )
        ).scalars().all()
        departed = [p for p in rows if p.ht_player_id not in current_ht_player_ids]
        for p in departed:
            p.left_team_at = captured_at
        return departed

    async def append_match_rating_if_new(
        self,
        player_id: int,
        ht_match_id: int,
        position_code: int,
        played_minutes: int,
        rating: float,
        captured_at: datetime,
    ) -> bool:
        if not ht_match_id:
            return False  # LastMatch sin MatchId real: nada que guardar
        exists = await self._s.scalar(
            select(m.PlayerMatchRating.id).where(
                m.PlayerMatchRating.player_id == player_id,
                m.PlayerMatchRating.ht_match_id == ht_match_id,
            )
        )
        if exists:
            return False
        self._s.add(m.PlayerMatchRating(
            player_id=player_id, ht_match_id=ht_match_id,
            position_code=position_code, played_minutes=played_minutes,
            rating=rating, captured_at=captured_at,
        ))
        return True


class SqlAlchemyEconomyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_last_hash(self, team_id: int) -> bytes | None:
        return cast(bytes | None, await self._s.scalar(
            select(m.EconomySnapshot.content_hash)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at.desc())
            .limit(1)
        ))

    async def get_last_values(self, team_id: int) -> dict[str, Any] | None:
        snap = await self._s.scalar(
            select(m.EconomySnapshot)
            .where(m.EconomySnapshot.team_id == team_id)
            .order_by(m.EconomySnapshot.captured_at.desc())
            .limit(1)
        )
        if snap is None:
            return None
        return {
            "cash": snap.cash,
            "sponsors_popularity": snap.sponsors_popularity,
            "supporters_popularity": snap.supporters_popularity,
            "fan_club_size": snap.fan_club_size,
            "income_sum": snap.income_sum,
            "costs_sum": snap.costs_sum,
        }

    async def append(
        self,
        sync_id: int,
        team_id: int,
        data: dict[str, Any],
        content_hash: bytes,
        captured_at: datetime,
    ) -> None:
        cols = {c.key for c in m.EconomySnapshot.__table__.columns}
        payload = {k: v for k, v in data.items() if k in cols}
        self._s.add(
            m.EconomySnapshot(
                sync_id=sync_id, team_id=team_id, captured_at=captured_at,
                content_hash=content_hash, **payload,
            )
        )


class SqlAlchemyTrainingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_last_hash(self, team_id: int) -> bytes | None:
        return cast(bytes | None, await self._s.scalar(
            select(m.TrainingSnapshot.content_hash)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        ))

    async def get_last_values(self, team_id: int) -> dict[str, Any] | None:
        snap = await self._s.scalar(
            select(m.TrainingSnapshot)
            .where(m.TrainingSnapshot.team_id == team_id)
            .order_by(m.TrainingSnapshot.captured_at.desc())
            .limit(1)
        )
        if snap is None:
            return None
        return {
            "training_type": snap.training_type,
            "training_level": snap.training_level,
            "trainer_name": snap.trainer_name,
            # Estos dos campos también forman parte de `diff_training`.
            # Omitirlos convertía el centinela -1 de «sin dato» en un nivel
            # anterior ficticio y producía cambios como «-1 -> Calmados».
            "morale": snap.morale,
            "self_confidence": snap.self_confidence,
        }

    async def append(
        self,
        sync_id: int,
        team_id: int,
        data: dict[str, Any],
        content_hash: bytes,
        captured_at: datetime,
    ) -> None:
        import json as _json

        cols = {c.key for c in m.TrainingSnapshot.__table__.columns}
        payload = {k: v for k, v in data.items() if k in cols}
        formation_xp = data.get("formation_xp")
        self._s.add(
            m.TrainingSnapshot(
                sync_id=sync_id, team_id=team_id, captured_at=captured_at,
                content_hash=content_hash,
                formation_xp_json=_json.dumps(formation_xp) if formation_xp else None,
                **payload,
            )
        )


class SqlAlchemySyncRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, user_id: int, team_id: int, kind: str) -> int:
        sync = m.Sync(
            user_id=user_id,
            team_id=team_id,
            kind=kind,
            status="running",
            started_at=datetime.now(UTC),
        )
        self._s.add(sync)
        await self._s.flush()
        return sync.id

    async def finalize(self, sync_id: int, status: str, error: str | None = None) -> None:
        await self._s.execute(
            update(m.Sync)
            .where(m.Sync.id == sync_id)
            .values(status=status, error=error, finished_at=datetime.now(UTC))
        )
