from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.faq_repository import FAQRepository
from app.models.database import FAQ
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class FAQService:
    """
    Сервис для бизнес-логики FAQ
    """
    
    def __init__(self, session: AsyncSession):
        self.repo = FAQRepository(session)
    
    async def get_faq_by_id(self, faq_id: int) -> Optional[FAQ]:
        """
        Получить FAQ по ID
        """
        return await self.repo.get_by_id(faq_id)
    
    async def get_faqs_by_category(
        self,
        category: str,
        language: str = "kk",
        skip: int = 0,
        limit: int = 100
    ) -> List[FAQ]:
        """
        Получить FAQ по категории
        """
        return await self.repo.get_by_category(
            category=category,
            language=language,
            skip=skip,
            limit=limit
        )
    
    async def get_all_categories(self, language: str = "kk") -> List[str]:
        """
        Получить все категории
        """
        return await self.repo.get_all_categories(language=language)
    
    async def search_faqs(
        self,
        search_term: str,
        language: str = "kk",
        limit: int = 10
    ) -> List[FAQ]:
        """
        Поиск FAQ
        """
        return await self.repo.search_by_question(
            search_term=search_term,
            language=language,
            limit=limit
        )