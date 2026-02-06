from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.responses import HealthCheckResponse
from app.config import settings

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """
    Проверка работоспособности API и подключения к БД
    """
    db_status = "healthy"
    
    try:
        await session.execute("SELECT 1")
    except Exception:
        db_status = "unhealthy"
    
    return HealthCheckResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        version="1.0.0",
        environment=settings.ENVIRONMENT
    )