from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
import aiohttp
import logging

from config import settings
from keyboards.inline import get_categories_keyboard

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start (приветствие на казахском)"""
    user_name = message.from_user.first_name or "дос"
    
    welcome_text = (
        f"Сәлем, {user_name}! 👋\n\n"
        f"Мен — сенің инвестициялар бойынша AI-кураторыңмын! 📊\n\n"
        f"Мұнда сен инвестициялар, акциялар, облигациялар және стратегиялар "
        f"туралы танымал сұрақтарға жауап таба аласың.\n\n"
        f"Өзіңді қызықтыратын санатты таңда:"
    )
    
    # Получаем категории из API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_BASE_URL}/faq/categories") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    categories = data.get("categories", [])
                    
                    keyboard = get_categories_keyboard(categories)
                    await message.answer(welcome_text, reply_markup=keyboard)
                else:
                    await message.answer(
                        "Санаттарды жүктеу кезінде қате орын алды. Кейінірек қайталап көріңіз."
                    )
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        await message.answer(
            "Серверге қосылу кезінде қате орын алды. Кейінірек қайталап көріңіз."
        )


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: CallbackQuery):
    """Возврат к списку категорий"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{settings.API_BASE_URL}/faq/categories") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    categories = data.get("categories", [])
                    
                    keyboard = get_categories_keyboard(categories)
                    
                    await callback.message.edit_text(
                        "Өзіңді қызықтыратын санатты таңда:",
                        reply_markup=keyboard
                    )
                    await callback.answer()
                else:
                    await callback.answer("Санаттарды жүктеу қатесі", show_alert=True)
    except Exception as e:
        logger.error(f"Error going back to categories: {e}")
        await callback.answer("Қате орын алды", show_alert=True)