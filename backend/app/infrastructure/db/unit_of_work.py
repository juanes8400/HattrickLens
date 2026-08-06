from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.ports.repositories import PlayerRepository, SyncRepository, TeamSnapshotRepository
from app.infrastructure.db.repositories import (
    SqlAlchemyEconomyRepository,
    SqlAlchemyPlayerRepository,
    SqlAlchemySyncRepository,
    SqlAlchemyTrainingRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self._session = self._factory()
        self.players: PlayerRepository = SqlAlchemyPlayerRepository(self._session)
        self.syncs: SyncRepository = SqlAlchemySyncRepository(self._session)
        self.economy: TeamSnapshotRepository = SqlAlchemyEconomyRepository(self._session)
        self.training: TeamSnapshotRepository = SqlAlchemyTrainingRepository(self._session)
        return self

    @property
    def session(self) -> AsyncSession:
        """Acceso directo para escrituras que aún no tienen repositorio propio
        (staff, contexto del mundo, subidas de habilidad). El resto de la app
        las lee por query services con el mismo patrón."""
        return self._session

    async def __aexit__(self, *args: object) -> None:
        exc_type = args[0] if args else None
        if exc_type is not None:
            await self.rollback()
        await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
