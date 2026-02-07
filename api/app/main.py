"""
FastAPI точка входа с lifespan управлением и централизованной обработкой ошибок
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import faq, health, ask
from app.config import settings
from app.core.database import check_db_connection, close_db_connection
from app.core.exceptions import AppException
from app.core.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Управление жизненным циклом приложения
    """
    logger.info("🚀 Starting FAQ Bot API...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    try:
        await check_db_connection(max_retries=5, retry_delay=2)
        logger.info("✅ Database connection established")
    except Exception as e:
        logger.error(f"❌ Failed to connect to database: {e}")
        raise
    
    logger.info("✅ API started successfully")
    
    yield
    
    logger.info("🛑 Shutting down FAQ Bot API...")
    await close_db_connection()
    logger.info("✅ API shutdown complete")


app = FastAPI(
    title="FAQ Bot API",
    description="API для Telegram бота-куратора с видеоответами",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.is_development else None,
    redoc_url="/api/redoc" if settings.is_development else None,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Обработка кастомных исключений приложения"""
    logger.error(
        f"AppException: {exc.message} | Status: {exc.status_code} | "
        f"Path: {request.url.path} | Details: {exc.details}"
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message,
            "error_code": exc.__class__.__name__,
            "details": exc.details,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Обработка ошибок валидации Pydantic"""
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": "Ошибка валидации данных",
            "error_code": "ValidationError",
            "details": exc.errors(),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработка всех неожиданных ошибок"""
    logger.exception(f"Unexpected error on {request.url.path}: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Внутренняя ошибка сервера",
            "error_code": "InternalServerError",
            "details": {"error": str(exc)} if settings.is_development else {},
        },
    )


app.include_router(health.router, tags=["Health"])
app.include_router(faq.router, prefix="/faq", tags=["FAQ"])
app.include_router(ask.router, prefix="/api", tags=["AI"])


try:
    app.mount("/videos", StaticFiles(directory="/app/videos"), name="videos")
    logger.info("✅ Static files (videos) mounted at /videos")
except RuntimeError:
    logger.warning("⚠️ Videos directory not found, skipping static files mount")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Корневой endpoint"""
    return {
        "service": "FAQ Bot API",
        "status": "running",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }