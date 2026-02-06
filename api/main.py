from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

# ИСПРАВЛЕНИЕ: абсолютные импорты вместо относительных
from routers import faq

app = FastAPI(
    title="FAQ Bot API",
    description="API для Telegram бота с видеоответами",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(faq.router)

# Раздача видео как статичных файлов
videos_path = "/app/videos"
if os.path.exists(videos_path):
    app.mount("/videos", StaticFiles(directory=videos_path), name="videos")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "FAQ Bot API is running"
    }


@app.get("/health")
async def health():
    """Health check для мониторинга"""
    return {"status": "healthy"}