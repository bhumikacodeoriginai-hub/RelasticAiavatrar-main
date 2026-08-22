"""
Database connection - MySQL on localhost.
Uses asyncmy driver for async MySQL access.
Server starts even if DB connection fails (graceful degradation).
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
        # Recycle connections well under MySQL's wait_timeout so stale
        # connections are replaced without needing pre-ping.
        pool_recycle=280,
        # NOTE: pool_pre_ping is intentionally DISABLED. The installed asyncmy
        # version's connection.ping() requires a 'reconnect' arg that
        # SQLAlchemy's pre-ping wrapper does not pass, which raised:
        #   AsyncAdapt_asyncmy_connection.ping() missing 1 required positional
        #   argument: 'reconnect'
        # and intermittently killed queries. pool_recycle handles staleness.
        pool_pre_ping=False,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    logger.info("Database engine created", url=settings.database_url.split("@")[-1])
except Exception as e:
    logger.error("Database engine creation failed (server will still run)", error=str(e))


async def get_db():
    """Dependency that yields a database session."""
    if not AsyncSessionLocal:
        yield None
        return
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Initialize database connection and verify connectivity."""
    if engine:
        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified (MySQL/myapp)")
        except Exception as e:
            logger.error("Database connectivity check failed", error=str(e))
    else:
        logger.warning("Database not available - running without DB")


async def close_db():
    """Dispose the database engine on shutdown."""
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")
