"""
Базовый репозиторий для работы с БД
"""
from typing import Generic, TypeVar, Type, Optional, List, Any

from sqlalchemy import select, func, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base
from app.core.logging_config import get_logger

logger = get_logger(__name__)

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Базовый репозиторий с CRUD операциями
    """
    
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get_by_id(self, id: int) -> Optional[ModelType]:
        """Получить запись по ID"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        **filters: Any
    ) -> List[ModelType]:
        """Получить все записи с фильтрами"""
        query = select(self.model)
        
        # Применение фильтров
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        
        query = query.offset(skip).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create(self, obj_in: dict[str, Any]) -> ModelType:
        """Создать новую запись"""
        db_obj = self.model(**obj_in)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        logger.info(f"Created {self.model.__name__} with id={db_obj.id}")
        return db_obj
    
    async def update(self, id: int, obj_in: dict[str, Any]) -> Optional[ModelType]:
        """Обновить запись"""
        # Фильтруем None значения
        obj_in = {k: v for k, v in obj_in.items() if v is not None}
        
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**obj_in)
            .returning(self.model)
        )
        
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        updated_obj = result.scalar_one_or_none()
        if updated_obj:
            logger.info(f"Updated {self.model.__name__} with id={id}")
        
        return updated_obj
    
    async def delete(self, id: int) -> bool:
        """Удалить запись"""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        
        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted {self.model.__name__} with id={id}")
        
        return deleted
    
    async def count(self, **filters: Any) -> int:
        """Подсчёт записей с фильтрами"""
        query = select(func.count(self.model.id))
        
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.where(getattr(self.model, key) == value)
        
        result = await self.session.execute(query)
        return result.scalar_one()
    
    async def exists(self, id: int) -> bool:
        """Проверка существования записи"""
        result = await self.session.execute(
            select(func.count(self.model.id)).where(self.model.id == id)
        )
        return result.scalar_one() > 0