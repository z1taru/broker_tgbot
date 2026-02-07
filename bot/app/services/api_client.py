import aiohttp
from typing import List, Dict, Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class APIClient:
    """
    Клиент для взаимодействия с API
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.API_BASE_URL
    
    async def get_categories(self, language: str = "kk") -> List[str]:
        """
        Получить список категорий
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/faq/categories",
                    params={"language": language}
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("categories", [])
                    else:
                        logger.error(f"Failed to get categories: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            return []
    
    async def get_faqs_by_category(
        self,
        category: str,
        language: str = "kk"
    ) -> List[Dict]:
        """
        Получить FAQ по категории
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/faq/category/{category}",
                    params={"language": language}
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Failed to get FAQs for category {category}: {resp.status}")
                        return []
        except Exception as e:
            logger.error(f"Error getting FAQs for category {category}: {e}")
            return []
    
    async def get_faq_by_id(self, faq_id: int) -> Optional[Dict]:
        """
        Получить FAQ по ID
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/faq/{faq_id}") as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Failed to get FAQ {faq_id}: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error getting FAQ {faq_id}: {e}")
            return None