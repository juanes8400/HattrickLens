"""Ports (interfaces) que la infraestructura implementa. El dominio solo conoce esto."""
from datetime import datetime
from typing import Any, Protocol


class PlayerRepository(Protocol):
    async def upsert_identity(
        self, ht_player_id: int, team_id: int, first_name: str, last_name: str
    ) -> int:
        """Crea/actualiza la fila de identidad del jugador. Devuelve id interno."""
        ...

    async def get_last_snapshot_hash(self, ht_player_id: int) -> bytes | None:
        """Hash del último snapshot para diffing (None si nunca visto)."""
        ...

    async def get_last_snapshot(self, ht_player_id: int) -> dict[str, Any] | None:
        """Valores reales del último snapshot (no solo el hash) — HL-140:
        hace falta el valor anterior para poder describir qué cambió, no
        solo saber que cambió."""
        ...

    async def append_snapshot(
        self,
        sync_id: int,
        player_id: int,
        data: dict[str, Any],
        content_hash: bytes,
        captured_at: datetime,
    ) -> None:
        """Append-only: nunca sobrescribe."""
        ...

    async def count_snapshots(self, team_id: int) -> int: ...

    async def mark_departed(
        self, team_id: int, current_ht_player_ids: set[int], captured_at: datetime
    ) -> int:
        """Un jugador del equipo que no vino en el último `players.xml` ya no
        está: se marca `left_team_at`, nunca se borra (histórico). Devuelve
        cuántos se marcaron."""
        ...

    async def append_match_rating_if_new(
        self,
        player_id: int,
        ht_match_id: int,
        position_code: int,
        played_minutes: int,
        rating: float,
        captured_at: datetime,
    ) -> bool:
        """Histórico de rating por partido (HL-15x #21) — append-only,
        deduplicado por (player_id, ht_match_id). Devuelve True si insertó
        una fila nueva, False si ese partido ya estaba registrado."""
        ...


class TeamSnapshotRepository(Protocol):
    """Genérico para snapshots por-equipo (economy, training) con diffing."""

    async def get_last_hash(self, team_id: int) -> bytes | None: ...

    async def get_last_values(self, team_id: int) -> dict[str, Any] | None:
        """Valores reales del último snapshot — HL-140, mismo motivo que en
        `PlayerRepository.get_last_snapshot`."""
        ...

    async def append(
        self,
        sync_id: int,
        team_id: int,
        data: dict[str, Any],
        content_hash: bytes,
        captured_at: datetime,
    ) -> None: ...


class SyncRepository(Protocol):
    async def create(self, user_id: int, team_id: int, kind: str) -> int: ...
    async def finalize(self, sync_id: int, status: str, error: str | None = None) -> None: ...


class UnitOfWork(Protocol):
    players: PlayerRepository
    syncs: SyncRepository
    economy: TeamSnapshotRepository
    training: TeamSnapshotRepository

    @property
    def session(self) -> Any:
        """Acceso directo para escrituras que aún no tienen repositorio propio
        (staff, contexto del mundo, subidas de habilidad). Tipado como Any a
        propósito: el dominio no puede nombrar el tipo concreto de sesión sin
        importar infraestructura (violaría la capa hexagonal). Property, no
        atributo: de solo lectura tanto aquí como en la implementación."""
        ...

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, *args: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
