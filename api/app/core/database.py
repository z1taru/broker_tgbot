import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

Base = declarative_base()
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    
    if _engine is None:
        _engine = create_async_engine(
            str(settings.DATABASE_URL),
            echo=settings.is_development,
            future=True,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            poolclass=NullPool if settings.ENVIRONMENT == "testing" else None,
        )
        logger.info("Database engine created")
    
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _async_session_maker
    
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        logger.info("Session maker created")
    
    return _async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


async def check_db_connection(max_retries: int = 5, retry_delay: int = 2) -> bool:
    engine = get_engine()
    
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute("SELECT 1")
                logger.info("Database connection successful")
                return True
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {e}")
                raise
            
            logger.warning(
                f"Database connection attempt {attempt}/{max_retries} failed: {e}. "
                f"Retrying in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
    
    return False


async def close_db_connection() -> None:
    global _engine, _async_session_maker
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database connection closed")