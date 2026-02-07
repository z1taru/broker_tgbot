# bot/app/handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработчик команды /start
    """
    user_name = message.from_user.first_name or "дос"
    
    welcome_text = (
        f"Сәлем, {user_name}! 👋\n\n"
        f"Мен — сенің инвестициялар бойынша AI-кураторыңмын! 📊\n\n"
        f"Мұнда сен инвестициялар, акциялар, облигациялар және стратегиялар "
        f"туралы танымал сұрақтарға жауап таба аласың.\n\n"
        f"Қандай сұрағың бар? 🤔"
    )
    
    await message.answer(welcome_text)