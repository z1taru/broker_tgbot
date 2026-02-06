from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from config import settings

# Создание асинхронного движка
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=True,
    future=True
)

# Фабрика сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base класс для моделей
Base = declarative_base()


async def get_session() -> AsyncSession:
    """Dependency для получения сессии БД"""
    async with async_session_maker() as session:
        yield session