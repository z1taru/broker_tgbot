import aiohttp
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class VideoService:
    """
    Сервис для работы с видео
    """
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.API_BASE_URL
    
    async def download_video(self, video_filename: str) -> Optional[bytes]:
        """
        Скачать видео с API сервера
        """
        video_url = f"{self.base_url}/videos/{video_filename}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    else:
                        logger.error(f"Failed to download video {video_filename}: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Error downloading video {video_filename}: {e}")
            return None