# bot/app/services/ai_client.py
import aiohttp
import logging
from typing import Optional, Dict

from app.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.API_BASE_URL

    async def ask_question(
        self,
        question: str,
        user_id: str,
        language: str = "auto",
    ) -> Optional[Dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/ask",
                    json={"question": question, "user_id": user_id, "language": language},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"[AIClient] ask status={resp.status}")
                    return None
        except Exception as e:
            logger.error(f"[AIClient] ask error: {e}")
            return None

    async def ask_by_faq_id(self, faq_id: int) -> Optional[Dict]:
        """Получить прямой ответ по faq_id — без поиска."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/faq-direct/{faq_id}",
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"[AIClient] faq-direct status={resp.status} id={faq_id}")
                    return None
        except Exception as e:
            logger.error(f"[AIClient] faq-direct error: {e}")
            return None