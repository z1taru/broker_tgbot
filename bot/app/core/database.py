from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from bot.app.config import settings

Base = declarative_base()
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    
    if _engine is None:
        _engine = create_async_engine(
            "postgresql+asyncpg://user:password@db:5432/faqbot",
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
    
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    global _async_session_maker
    
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    return _async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()