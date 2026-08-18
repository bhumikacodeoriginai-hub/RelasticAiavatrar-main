"""
Database connection - MySQL on AWS (optional - server starts without it).
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog

logger = structlog.get_logger()

class Base(DeclarativeBase):
    pass

# Try to create engine - if it fails, server still runs
engine = None
AsyncSessionLocal = None

try:
    from config import settings
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_size=5,
        max_overflow=3,
        pool_timeout=10,
        pool_recycle=1800,
        pool_pre_ping=False,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("Database engine created")
except Exception as e:
    logger.error("Database engine creation failed (server will still run)", error=str(e))


async def get_db() -> AsyncSession:
    if not AsyncSessionLocal:
        yield None
        return
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    if engine:
        logger.info("Database ready")
    else:
        logger.warning("Database not available - running without DB")


async def close_db():
    if engine:
        await engine.dispose()
        logger.info("Database closed")
