import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import settings
from handlers import start, faq

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    # ИСПРАВЛЕНИЕ: убрана DefaultBotProperties (не существует в aiogram 3.3)
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(faq.router)
    
    logger.info("Bot started")
    
    # Проверка режима работы (webhook или polling)
    if settings.WEBHOOK_ENABLED:
        logger.info(f"Starting webhook mode: {settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}")
        
        await bot.set_webhook(
            url=f"{settings.WEBHOOK_URL}{settings.WEBHOOK_PATH}",
            drop_pending_updates=True
        )
        
        logger.warning("Webhook mode not fully implemented in MVP, use polling instead")
        await bot.delete_webhook()
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    else:
        # Polling режим
        logger.info("Starting polling mode")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")