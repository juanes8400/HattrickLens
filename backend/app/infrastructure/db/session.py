from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# `pool_pre_ping` y `pool_recycle` (2026-09-15, visto en producción): Neon cierra
# las conexiones que se quedan quietas, y el pool las devolvía como si siguieran
# vivas. El primer usuario que llegaba tras un rato sin tráfico se comía un 500
# al conectar con Hattrick; el segundo intento ya entraba. Con el ping la
# conexión muerta se descarta y se abre otra antes de usarla.
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
