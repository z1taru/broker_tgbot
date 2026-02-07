# bot/app/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from app.config import settings
from app.core.logging_config import setup_logging
from app.handlers import start, message, errors

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    """
    Основная функция запуска бота
    """
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    
    dp.include_router(start.router)
    dp.include_router(message.router)
    dp.include_router(errors.router)
    
    logger.info("Bot started")
    
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
        logger.info("Starting polling mode")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")