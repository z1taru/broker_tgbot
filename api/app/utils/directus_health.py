# api/app/utils/directus_health.py
import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)


async def check_directus_health() -> bool:
    """
    Check if Directus is accessible from API container
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.DIRECTUS_URL}/server/health")
            
            if response.status_code == 200:
                logger.info(f"✅ Directus is healthy at {settings.DIRECTUS_URL}")
                return True
            else:
                logger.warning(f"⚠️ Directus unhealthy: {response.status_code}")
                return False
                
    except httpx.ConnectError as e:
        logger.error(f"❌ Cannot connect to Directus at {settings.DIRECTUS_URL}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Directus health check failed: {e}")
        return False