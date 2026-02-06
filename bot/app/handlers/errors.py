from aiogram import Router
from aiogram.types import ErrorEvent
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.error()
async def error_handler(event: ErrorEvent):
    """
    Глобальный обработчик ошибок
    """
    logger.exception(f"Update {event.update} caused error: {event.exception}")