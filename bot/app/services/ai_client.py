# bot/app/services/ai_client.py
import aiohttp
import logging
from typing import Optional, Dict

from app.config import settings

logger = logging.getLogger(__name__)


class AIClient:
    """
    Client for AI-powered question answering
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.API_BASE_URL
    
    async def ask_question(
        self,
        question: str,
        user_id: str,
        language: str = "auto"
    ) -> Optional[Dict]:
        """
        Ask AI system a question
        
        Returns:
            dict with keys: action, answer_text, video_url, faq_id, confidence, message
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/ask",
                    json={
                        "question": question,
                        "user_id": user_id,
                        "language": language
                    }
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"Failed to ask question: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error asking question: {e}")
            return None