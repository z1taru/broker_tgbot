# api/app/api/routes/health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.core.database import get_session
from app.schemas.responses import HealthCheckResponse
from app.config import settings
from app.core.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """
    Проверка работоспособности API и подключения к БД
    """
    db_status = "healthy"
    
    try:
        # ✅ Используем уже открытую сессию с правильным await
        result = await session.execute(text("SELECT 1"))
        result.scalar()
        logger.debug("✅ Database health check passed")
    except Exception as e:
        db_status = "unhealthy"
        logger.error(f"❌ Database health check failed: {e}", exc_info=True)
    
    return HealthCheckResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        version="1.0.0",
        environment=settings.ENVIRONMENT
    )