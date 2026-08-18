"""
Database connection - MySQL on AWS EC2.
Uses aiomysql driver for async MySQL access.
Server starts even if DB connection fails (graceful degradation).
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
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
        pool_timeout=5,
        pool_recycle=1800,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
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
    """Dependency that yields a database session. Auto-commits on success."""
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


async def save_visitor_to_db(name: str, email: str = None, phone: str = None, company: str = None) -> bool:
    """
    Directly save a visitor to MySQL. Returns True on success.
    This is the RELIABLE save function - no HTTP calls, no dependencies.
    """
    if not AsyncSessionLocal:
        logger.error("Cannot save visitor - AsyncSessionLocal is None")
        return False

    try:
        async with AsyncSessionLocal() as session:
            # Check if visitor already exists
            result = await session.execute(
                text("SELECT id FROM visitor WHERE LOWER(name) = LOWER(:name)"),
                {"name": name.strip()}
            )
            existing = result.mappings().first()

            if existing:
                # Update last_seen
                await session.execute(
                    text("UPDATE visitor SET last_seen = NOW(), visit_count = visit_count + 1 WHERE id = :id"),
                    {"id": existing['id']}
                )
                await session.commit()
                logger.info("✅ Visitor updated (last_seen)", name=name, id=existing['id'])
                return True
            else:
                # Insert new visitor
                await session.execute(
                    text("""INSERT INTO visitor (name, email, phone, company, consent_status, first_seen, last_seen, visit_count)
                            VALUES (:name, :email, :phone, :company, 'granted', NOW(), NOW(), 1)"""),
                    {"name": name.strip(), "email": email, "phone": phone, "company": company}
                )
                await session.commit()
                logger.info("✅ NEW visitor saved to DB", name=name)
                return True
    except Exception as e:
        logger.error("❌ save_visitor_to_db FAILED", name=name, error=str(e))
        return False


async def save_conversation_to_db(visitor_name: str, role: str, message: str) -> bool:
    """
    Save a conversation message to MySQL. Returns True on success.
    Finds visitor by name, then inserts into conversations table.
    """
    if not AsyncSessionLocal:
        logger.error("Cannot save conversation - AsyncSessionLocal is None")
        return False

    try:
        async with AsyncSessionLocal() as session:
            # Find visitor
            result = await session.execute(
                text("SELECT id FROM visitor WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
                {"name": visitor_name.strip()}
            )
            row = result.mappings().first()

            if not row:
                logger.warning("Cannot save conversation - visitor not found", name=visitor_name)
                return False

            visitor_id = row['id']

            # Insert conversation message
            await session.execute(
                text("""INSERT INTO conversations (visitor_id, role, message, timestamp)
                        VALUES (:vid, :role, :msg, NOW())"""),
                {"vid": visitor_id, "role": role, "msg": message}
            )
            await session.commit()
            logger.info("✅ Conversation saved", visitor=visitor_name, role=role, msg_len=len(message))
            return True
    except Exception as e:
        logger.error("❌ save_conversation_to_db FAILED", visitor=visitor_name, error=str(e))
        return False


async def log_visit_to_db(visitor_name: str, purpose: str = None) -> bool:
    """Log a visit for a visitor. Returns True on success."""
    if not AsyncSessionLocal:
        return False

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id FROM visitor WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
                {"name": visitor_name.strip()}
            )
            row = result.mappings().first()
            if not row:
                return False

            await session.execute(
                text("""INSERT INTO visits (visitor_id, arrival_time, purpose, status)
                        VALUES (:vid, NOW(), :purpose, 'arrived')"""),
                {"vid": row['id'], "purpose": purpose}
            )
            await session.commit()
            logger.info("✅ Visit logged", visitor=visitor_name)
            return True
    except Exception as e:
        logger.error("❌ log_visit_to_db FAILED", error=str(e))
        return False


async def init_db():
    """Initialize database connection and verify connectivity."""
    if engine:
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Database connection verified (MySQL/myapp)")

            # Verify tables exist
            async with engine.connect() as conn:
                result = await conn.execute(text("SHOW TABLES"))
                tables = [row[0] for row in result.fetchall()]
                logger.info("✅ Tables found", tables=tables)
        except Exception as e:
            logger.error("❌ Database connectivity check failed", error=str(e))
    else:
        logger.warning("⚠️ Database not available - running without DB")


async def close_db():
    """Dispose the database engine on shutdown."""
    if engine:
        await engine.dispose()
        logger.info("Database connection closed")
