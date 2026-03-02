# bot/app/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.core.logging_config import setup_logging
from app.handlers import start, errors
from app.handlers import message as message_handler
from app.handlers import clarify as clarify_handler  # НОВЫЙ

setup_logging()
logger = logging.getLogger(__name__)


async def main():
    storage = MemoryStorage()
    bot = Bot(token=settings.BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=storage)

    # ПОРЯДОК ВАЖЕН:
    # 1. start — команды /start /language
    # 2. clarify — должен быть ПЕРЕД message, перехватывает "1"-"4" и callback
    # 3. message — основной handler
    # 4. errors — глобальный обработчик ошибок
    dp.include_router(start.router)
    dp.include_router(clarify_handler.router)  # ← перехватывает clarify РАНЬШЕ message
    dp.include_router(message_handler.router)
    dp.include_router(errors.router)

    logger.info("🤖 Bot started")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped")