"""
Репозиторий для работы с FAQ
"""
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import FAQ
from app.repositories.base import BaseRepository
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class FAQRepository(BaseRepository[FAQ]):
    """
    Репозиторий для FAQ с дополнительными методами
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(FAQ, session)
    
    async def get_by_category(
        self,
        category: str,
        language: str = "kk",
        skip: int = 0,
        limit: int = 100
    ) -> List[FAQ]:
        """
        Получить FAQ по категории и языку
        
        Args:
            category: Категория FAQ
            language: Язык (по умолчанию казахский)
            skip: Количество пропускаемых записей
            limit: Максимальное количество записей
        
        Returns:
            Список FAQ записей
        """
        query = (
            select(FAQ)
            .where(FAQ.category == category, FAQ.language == language)
            .order_by(FAQ.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        faqs = list(result.scalars().all())
        
        logger.debug(f"Found {len(faqs)} FAQs for category '{category}'")
        return faqs
    
    async def get_all_categories(self, language: str = "kk") -> List[str]:
        """
        Получить все уникальные категории
        
        Args:
            language: Язык фильтрации
        
        Returns:
            Список названий категорий
        """
        query = (
            select(FAQ.category)
            .where(FAQ.language == language)
            .distinct()
            .order_by(FAQ.category)
        )
        
        result = await self.session.execute(query)
        categories = [row[0] for row in result.all()]
        
        logger.debug(f"Found {len(categories)} categories for language '{language}'")
        return categories
    
    async def search_by_question(
        self,
        search_term: str,
        language: str = "kk",
        limit: int = 10
    ) -> List[FAQ]:
        """
        Поиск FAQ по тексту вопроса (для будущего расширения)
        
        Args:
            search_term: Поисковый запрос
            language: Язык
            limit: Максимальное количество результатов
        
        Returns:
            Список FAQ записей
        """
        query = (
            select(FAQ)
            .where(
                FAQ.language == language,
                FAQ.question.ilike(f"%{search_term}%")
            )
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_stats(self) -> dict[str, int]:
        """
        Получить статистику по FAQ
        
        Returns:
            Словарь со статистикой
        """
        # Общее количество
        total_count_query = select(func.count(FAQ.id))
        total_result = await self.session.execute(total_count_query)
        total = total_result.scalar_one()
        
        # Количество с видео
        video_count_query = select(func.count(FAQ.id)).where(FAQ.video_url.isnot(None))
        video_result = await self.session.execute(video_count_query)
        with_video = video_result.scalar_one()
        
        # Количество по языкам
        kk_count_query = select(func.count(FAQ.id)).where(FAQ.language == "kk")
        kk_result = await self.session.execute(kk_count_query)
        kazakh = kk_result.scalar_one()
        
        return {
            "total": total,
            "with_video": with_video,
            "kazakh": kazakh,
        }